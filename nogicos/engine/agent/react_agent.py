# -*- coding: utf-8 -*-
"""
Pure ReAct Agent - Autonomous AI Agent

This agent uses a pure ReAct (Reasoning + Acting) loop without pre-planning.
It dynamically decides what to do based on the current context and available tools.

Key Features:
- No pre-planning: Agent decides actions on-the-fly
- Autonomous: Agent handles tasks without step-by-step instructions
- Dynamic tool selection: Agent chooses tools based on task requirements
- Streaming: Real-time feedback via WebSocket
- Speculative Prompt Caching: Pre-warm cache while user types for faster TTFT

Architecture:
    User Task → ReAct Loop → Tool Execution → Response
                    ↑              |
                    └──────────────┘
                    (iterate until done)
"""

import os
import json
import time
import asyncio
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field

# Logging
from engine.observability import get_logger
logger = get_logger("react_agent")

# Import tool registry
from engine.tools.base import ToolRegistry, ToolCategory
from engine.tools import create_full_registry

# Centralized optional imports (reduces ~80 lines of try/except boilerplate)
from engine.agent.imports import (
    # Anthropic
    ANTHROPIC_AVAILABLE,
    anthropic,
    create_anthropic_client,
    create_async_anthropic_client,
    # Knowledge
    KNOWLEDGE_AVAILABLE,
    KnowledgeStore,
    UserProfile,
    Trajectory,
    get_store,
    # Memory
    MEMORY_AVAILABLE,
    get_memory_store,
    SemanticMemorySearch,
    BackgroundMemoryProcessor,
    format_memories_for_prompt,
    # Visualization
    VISUALIZATION_AVAILABLE,
    visualize_tool_start,
    visualize_tool_end,
    visualize_task_start,
    visualize_task_complete,
    visualize_task_error,
    # Planner
    PLANNER_AVAILABLE,
    TaskPlanner,
    Plan,
    PlanStep,
    PlanExecuteState,
    # Classifier
    CLASSIFIER_AVAILABLE,
    TaskClassifier,
    ClassifierComplexity,
    # Browser
    BROWSER_SESSION_AVAILABLE,
    get_browser_session,
    close_browser_session,
)


@dataclass
class AgentResult:
    """Result from agent execution"""
    success: bool
    response: str
    error: Optional[str] = None
    iterations: int = 0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


# Base System Prompt template - tool list will be dynamically generated
REACT_SYSTEM_PROMPT_TEMPLATE = """You are NogicOS, an autonomous AI agent. You ACT first, explain later.

## Your Capabilities

{tools_section}

## Core Principle: BE AUTONOMOUS

You are NOT a chatbot. You are an AGENT. The difference:
- Chatbot: Asks questions, waits for answers, explains options
- Agent: Takes action, shows results, only asks when TRULY necessary

**Default behavior: ACT, don't ask.**

## How You Work

1. **Understand** → What does the user want? (interpret generously)
2. **Act** → Use tools to accomplish it
3. **Report** → Brief summary of what you did

## Understanding User Intent

When user says something vague, INTERPRET and ACT:
| User says | You understand | You do |
|-----------|---------------|--------|
| "整理桌面" | Organize desktop files | list_directory → create folders → move files |
| "还原刚才的整理" | Undo my previous actions | Check operation history → reverse moves |
| "你自己判断" | User trusts you | Proceed with best judgment |
| "帮我看看" | User wants info | list_directory → report findings |

## Context Understanding (CRITICAL)

### Reference Resolution
When user uses pronouns or references, resolve them using context:

| User says | Look for | Action |
|-----------|----------|--------|
| "它"/"这个"/"那个文件" | Last operated file/folder | Use that path |
| "刚才的"/"之前的" | Last operation result | Reference that result |
| "还原"/"撤销"/"undo" | Last modifying operation | Reverse it |
| "改一下"/"再试" | Last failed operation | Retry with adjustment |
| "那个文件夹" | Last mentioned/created folder | Use that folder |
| "放到那里" | Last destination used | Use same destination |

### Correction Handling
| User says | Meaning | Your response |
|-----------|---------|---------------|
| "不对"/"错了" | Wrong understanding | Ask what's correct, briefly |
| "我是说..." | Clarification | Update understanding, execute immediately |
| "还有"/"另外" | Additional task | Keep progress, add new task |
| "等一下"/"先不要" | Pause | Stop current action, await instruction |

### Recent Operations (for reference resolution)
{{operation_history}}

### Long-term Memory
{{long_term_memory}}

## Safety Rules (simple version)

Only TWO rules:
1. **Don't touch code projects**: Skip folders with .git or code files (.py, .js, etc.)
2. **Desktop = C:\\Users\\WIN\\Desktop**: When user says "桌面", that's the only path

If a path is protected, skip it silently and continue with others. Don't ask permission.

## Response Style

- **Be brief**: No lengthy explanations unless asked
- **Be action-oriented**: "已移动 5 个文件到 文档 文件夹" not "我可以帮你移动文件..."
- **Match language**: 用户说中文，你回中文
- **No menus**: Don't list what you CAN do. Just DO what they asked.

## ANTI-PATTERNS (Never do these)

❌ "请告诉我您想要..." (asking for clarification when you can infer)
❌ "我可以帮您..." (offering options instead of acting)
❌ "您是指..." (asking which option when context is clear)
❌ Listing capabilities when user gave a task

✅ Correct: User says "整理桌面" → You immediately list_directory and start organizing

Now execute the user's request. Act first, explain briefly after."""


def build_system_prompt(registry: ToolRegistry) -> str:
    """
    Build system prompt dynamically from tool registry.
    
    Args:
        registry: Tool registry with all registered tools
        
    Returns:
        Complete system prompt with tool descriptions
    """
    tools = registry.get_all()
    
    # Group tools by category
    browser_tools = []
    local_tools = []
    other_tools = []
    
    for tool in tools:
        if tool.category == ToolCategory.BROWSER:
            browser_tools.append(f"- {tool.name}: {tool.description}")
        elif tool.category == ToolCategory.LOCAL:
            local_tools.append(f"- {tool.name}: {tool.description}")
        else:
            other_tools.append(f"- {tool.name}: {tool.description}")
    
    # Build tools section
    tools_sections = []
    
    if browser_tools:
        tools_sections.append("**Browser Tools:**")
        tools_sections.extend(browser_tools)
        tools_sections.append("")  # Empty line
    
    if local_tools:
        tools_sections.append("**Local Tools:**")
        tools_sections.extend(local_tools)
        tools_sections.append("")  # Empty line
    
    if other_tools:
        tools_sections.append("**Other Tools:**")
        tools_sections.extend(other_tools)
        tools_sections.append("")  # Empty line
    
    tools_section = "\n".join(tools_sections).strip()
    
    # If no tools, provide fallback
    if not tools_section:
        tools_section = "No tools available."
    
    return REACT_SYSTEM_PROMPT_TEMPLATE.format(tools_section=tools_section)


# Global session history storage (persists across requests in same server instance)
_session_histories: Dict[str, List[Dict[str, Any]]] = {}


def get_session_history(session_id: str) -> List[Dict[str, Any]]:
    """Get operation history for a session"""
    return _session_histories.get(session_id, [])


def add_to_session_history(session_id: str, operation: Dict[str, Any]):
    """Add an operation to session history"""
    if session_id not in _session_histories:
        _session_histories[session_id] = []
    _session_histories[session_id].append(operation)
    # Keep only last 20 operations
    if len(_session_histories[session_id]) > 20:
        _session_histories[session_id] = _session_histories[session_id][-20:]


def format_operation_history(session_id: str) -> str:
    """
    Format operation history for system prompt with reference resolution context.
    
    Provides structured context for pronoun/reference resolution:
    - Last operated objects (for "它", "这个")
    - Last destination (for "那里", "那个文件夹")
    - Reversible operations (for "还原", "撤销")
    """
    history = get_session_history(session_id)
    if not history:
        return "No operations yet. (User references like '刚才' have no target)"
    
    lines = []
    
    # Extract key references for pronoun resolution
    last_file = None
    last_folder = None
    last_destination = None
    reversible_ops = []
    
    for op in history[-10:]:
        tool = op.get("tool", "")
        args = op.get("args", {})
        success = op.get("success", False)
        
        # Track references
        if tool == "move_file" and success:
            last_file = args.get("source", "")
            last_destination = args.get("destination", "")
            reversible_ops.append(f"move {last_file} → {last_destination}")
        elif tool == "create_directory" and success:
            last_folder = args.get("path", "")
            reversible_ops.append(f"create folder {last_folder}")
        elif tool == "delete_file" and success:
            last_file = args.get("path", "")
            reversible_ops.append(f"delete {last_file}")
        elif tool in ["list_directory", "read_file"]:
            path = args.get("path", "") or args.get("file_path", "")
            if path:
                if "." in path.split("/")[-1].split("\\")[-1]:
                    last_file = path
                else:
                    last_folder = path
    
    # Reference resolution section
    lines.append("**Reference Targets:**")
    if last_file:
        lines.append(f"- '它'/'这个文件' = {last_file}")
    if last_folder:
        lines.append(f"- '那个文件夹' = {last_folder}")
    if last_destination:
        lines.append(f"- '那里'/'同样位置' = {last_destination}")
    
    if not (last_file or last_folder or last_destination):
        lines.append("- (No specific targets yet)")
    
    # Reversible operations for "撤销"
    if reversible_ops:
        lines.append(f"\n**Last reversible action:** {reversible_ops[-1]}")
    
    # Operation timeline
    lines.append("\n**Recent operations:**")
    for i, op in enumerate(history[-5:], 1):  # Last 5 ops (condensed)
        tool = op.get("tool", "unknown")
        args = op.get("args", {})
        success = "✓" if op.get("success", False) else "✗"
        
        if tool == "move_file":
            src = args.get("source", "?").split("\\")[-1].split("/")[-1]
            dst = args.get("destination", "?").split("\\")[-1].split("/")[-1]
            lines.append(f"{i}. {success} Moved {src} → {dst}")
        elif tool == "create_directory":
            folder = args.get("path", "?").split("\\")[-1].split("/")[-1]
            lines.append(f"{i}. {success} Created folder: {folder}")
        elif tool == "list_directory":
            path = args.get("path", "?").split("\\")[-1].split("/")[-1]
            lines.append(f"{i}. {success} Listed: {path}")
        elif tool == "delete_file":
            path = args.get("path", "?").split("\\")[-1].split("/")[-1]
            lines.append(f"{i}. {success} Deleted: {path}")
        else:
            lines.append(f"{i}. {success} {tool}")
    
    return "\n".join(lines)


class ReActAgent:
    """
    Pure ReAct Agent - Autonomous task execution without pre-planning.
    
    This agent uses a simple Think-Act-Observe loop to handle any task.
    It dynamically selects tools and decides when to stop based on context.
    
    Features:
    - Loads user profile on startup for personalization
    - Saves execution history for learning
    - Injects user context into prompts
    - Speculative Prompt Caching for faster TTFT (90% improvement)
    """
    
    # Prompt caching beta header
    PROMPT_CACHE_BETA = "prompt-caching-2024-07-31"
    
    def __init__(
        self,
        status_server=None,
        max_iterations: int = 20,
        model: str = "claude-opus-4-5-20251101",
    ):
        """
        Initialize ReAct Agent.
        
        Args:
            status_server: WebSocket status server for streaming
            max_iterations: Maximum number of Think-Act-Observe cycles
            model: Anthropic model to use
        """
        self.status_server = status_server
        self.max_iterations = max_iterations
        self.model = model
        
        # Initialize Anthropic clients (sync and async)
        self.client = create_anthropic_client()
        self.async_client = create_async_anthropic_client()
        
        # Tool registry - create once and reuse
        self.registry = create_full_registry()
        
        # Knowledge store (B2.1)
        self.knowledge_store = get_store() if KNOWLEDGE_AVAILABLE else None
        
        # Long-term memory store
        self.memory_store = get_memory_store() if MEMORY_AVAILABLE else None
        self.memory_search = SemanticMemorySearch(self.memory_store) if MEMORY_AVAILABLE and self.memory_store else None
        self.memory_processor = BackgroundMemoryProcessor(self.memory_store) if MEMORY_AVAILABLE and self.memory_store else None
        
        # Task classifier for routing
        self.classifier = TaskClassifier() if CLASSIFIER_AVAILABLE else None
        
        # Task planner for complex tasks - connect to registry for dynamic tools
        self.planner = TaskPlanner(model=model, registry=self.registry) if PLANNER_AVAILABLE else None
        
        # Base system prompt (will be customized per request with history)
        self.base_system_prompt = build_system_prompt(self.registry)
        
        # Cache warming state (tracks which sessions have warm caches)
        self._warm_caches: Dict[str, float] = {}  # session_id -> timestamp
        self._cache_ttl = 300  # Cache warm for 5 minutes
        
        # Tool category cache (dynamically populated from registry)
        self._tool_categories_cache: Dict[str, str] = {}
        self._refresh_tool_categories()
        
        # Browser session state (lazy initialized for browser tasks)
        self._browser_session = None
        self._browser_session_active = False
    
    def _refresh_tool_categories(self) -> None:
        """Refresh tool categories cache from registry"""
        self._tool_categories_cache.clear()
        for tool in self.registry.get_all():
            self._tool_categories_cache[tool.name] = tool.category.value
        logger.debug(f"Refreshed tool categories: {len(self._tool_categories_cache)} tools")
    
    async def cleanup_browser_session(self) -> None:
        """
        Cleanup browser session after task completion.
        Call this when browser session is no longer needed.
        """
        if self._browser_session_active and close_browser_session:
            try:
                await close_browser_session()
                self._browser_session = None
                self._browser_session_active = False
                self.registry.set_context("browser_session", None)
                logger.info("[Agent] Browser session cleaned up")
            except Exception as e:
                logger.warning(f"[Agent] Error cleaning up browser session: {e}")
    
    def _get_tools_by_task_type(self, task_type: str) -> List[Dict[str, Any]]:
        """
        Get tools filtered by task type using registry categories.
        
        Args:
            task_type: 'browser', 'local', or 'mixed'
            
        Returns:
            List of tools in Anthropic format
        """
        all_tools = self.registry.to_anthropic_format()
        
        if task_type == "browser":
            # Browser + Vision tools
            allowed_categories = {"browser", "plan"}
            return [t for t in all_tools 
                    if self._tool_categories_cache.get(t["name"]) in allowed_categories]
        elif task_type == "local":
            # Local + Desktop tools
            allowed_categories = {"local", "plan"}
            return [t for t in all_tools 
                    if self._tool_categories_cache.get(t["name"]) in allowed_categories]
        else:
            # Mixed or unknown: return all
            return all_tools
    
    def _build_system_prompt_with_history(self, session_id: str, task: str = "") -> str:
        """
        Build system prompt with operation history, user context, and long-term memory.
        
        B2.3: Injects user profile context into prompt for personalization.
        Long-term memory: Injects semantically relevant memories from past sessions.
        """
        # Get operation history
        history = format_operation_history(session_id)
        prompt = self.base_system_prompt.replace("{operation_history}", history)
        
        # Remove long-term memory placeholder by default (sync version)
        prompt = prompt.replace("{long_term_memory}", "")
        
        # B2.3: Inject user context from profile
        if self.knowledge_store and KNOWLEDGE_AVAILABLE:
            try:
                profile = self.knowledge_store.get_profile(session_id)
                user_context = profile.get_context_for_prompt()
                if user_context:
                    # Insert user context before the final instruction
                    prompt = prompt.replace(
                        "Now execute the user's request.",
                        f"{user_context}\n\nNow execute the user's request."
                    )
            except Exception as e:
                # Don't fail if context loading fails
                pass
        
        return prompt
    
    async def _build_system_prompt_with_memory(self, session_id: str, task: str) -> str:
        """
        Build system prompt with long-term memory (async version).
        
        Retrieves semantically relevant memories based on the current task.
        
        Args:
            session_id: Session ID for memory scoping
            task: Current task for semantic search
            
        Returns:
            System prompt with injected memory context
        """
        # Start with base prompt + operation history
        history = format_operation_history(session_id)
        prompt = self.base_system_prompt.replace("{operation_history}", history)
        
        # Inject long-term memory if available
        memory_context = ""
        if self.memory_search and MEMORY_AVAILABLE:
            try:
                # Search for relevant memories based on current task
                memory_context = await self.memory_search.search_for_prompt(
                    query=task,
                    session_id=session_id,
                    max_tokens=400,  # Limit to ~400 tokens for memory
                )
                if memory_context:
                    logger.debug(f"Injected {len(memory_context)} chars of memory context")
            except Exception as e:
                logger.warning(f"Failed to load memory context: {e}")
        
        prompt = prompt.replace("{long_term_memory}", memory_context if memory_context else "")
        
        # B2.3: Inject user context from profile
        if self.knowledge_store and KNOWLEDGE_AVAILABLE:
            try:
                profile = self.knowledge_store.get_profile(session_id)
                user_context = profile.get_context_for_prompt()
                if user_context:
                    prompt = prompt.replace(
                        "Now execute the user's request.",
                        f"{user_context}\n\nNow execute the user's request."
                    )
            except Exception as e:
                pass
        
        return prompt
    
    def _is_cache_warm(self, session_id: str) -> bool:
        """Check if cache is still warm for this session."""
        if session_id not in self._warm_caches:
            return False
        cache_time = self._warm_caches[session_id]
        return (time.time() - cache_time) < self._cache_ttl
    
    async def warm_cache(self, session_id: str = "default") -> bool:
        """
        Pre-warm the prompt cache while user is typing.
        
        This implements Speculative Prompt Caching from Anthropic Cookbook.
        Call this when user focuses on input field to reduce TTFT by 90%+.
        
        Args:
            session_id: Session ID for building the correct system prompt
            
        Returns:
            True if cache was successfully warmed
        """
        if not self.async_client:
            logger.warning("Async client not available, skipping cache warm")
            return False
        
        # Skip if cache is already warm
        if self._is_cache_warm(session_id):
            logger.debug(f"Cache already warm for session {session_id}")
            return True
        
        try:
            # Build the system prompt that will be used
            system_prompt = self._build_system_prompt_with_history(session_id)
            
            logger.info(f"Warming cache for session {session_id}...")
            start_time = time.time()
            
            # Send a 1-token request to warm the cache
            # The cache_control directive tells Anthropic to cache this prompt
            await self.async_client.messages.create(
                model=self.model,
                max_tokens=1,
                extra_headers={"anthropic-beta": self.PROMPT_CACHE_BETA},
                system=[{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }],
                messages=[{"role": "user", "content": "."}],
            )
            
            # Mark cache as warm
            self._warm_caches[session_id] = time.time()
            
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"Cache warmed in {elapsed_ms:.0f}ms for session {session_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to warm cache: {e}")
            return False
    
    def _build_cached_system(self, system_prompt: str) -> list:
        """
        Build system prompt with cache_control for Anthropic API.
        
        Returns:
            List format required by Anthropic for cached system prompts
        """
        return [{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"}
        }]
    
    def _classify_error(self, error: str) -> tuple[str, bool, str]:
        """
        Classify an error for smart handling.
        
        Returns:
            Tuple of (error_type, is_retryable, suggested_action)
            
        Error types:
        - not_found: File/resource doesn't exist
        - permission: Access denied
        - timeout: Operation timed out
        - rate_limit: API rate limited
        - network: Network connectivity issue
        - invalid_input: Bad arguments
        - resource_busy: Resource locked
        - unknown: Unclassified error
        """
        error_lower = error.lower()
        
        # File not found
        if any(kw in error_lower for kw in ["not found", "does not exist", "no such file", "cannot find"]):
            return ("not_found", False, "Use list_directory to verify path exists")
        
        # Permission denied
        if any(kw in error_lower for kw in ["permission denied", "access denied", "protected"]):
            return ("permission", False, "Path is protected or requires elevated permissions")
        
        # Timeout
        if any(kw in error_lower for kw in ["timeout", "timed out"]):
            return ("timeout", True, "Retry with exponential backoff")
        
        # Rate limiting
        if any(kw in error_lower for kw in ["rate limit", "too many requests", "429"]):
            return ("rate_limit", True, "Wait and retry with longer delay")
        
        # Network issues
        if any(kw in error_lower for kw in ["connection refused", "connection reset", "network error", "dns"]):
            return ("network", True, "Check network connectivity, retry")
        
        # Invalid input
        if any(kw in error_lower for kw in ["invalid argument", "invalid parameter", "syntax error", "parse error"]):
            return ("invalid_input", False, "Fix the input arguments")
        
        # Resource busy
        if any(kw in error_lower for kw in ["in use", "locked", "busy", "cannot access"]):
            return ("resource_busy", True, "Resource locked, retry after delay")
        
        # Unknown
        return ("unknown", True, "May be transient, try again")
    
    async def _execute_with_retry(
        self,
        tool_name: str,
        args: dict,
        max_retries: int = 2,
    ):
        """
        Execute tool with intelligent retry logic.
        
        Implements smart retry strategies based on error type:
        - Timeout errors: Exponential backoff
        - Not found errors: No retry (deterministic failure)
        - Transient errors: Quick retry
        
        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments
            max_retries: Maximum retry attempts
            
        Returns:
            ToolResult with success/error status
        """
        last_error = None
        error_type = "unknown"
        
        for attempt in range(max_retries + 1):
            result = await self.registry.execute(tool_name, args)
            
            if result.success:
                # Mark if this was a retry success
                if attempt > 0:
                    logger.info(f"Tool {tool_name} succeeded on retry {attempt}")
                    result.retried = True  # type: ignore
                return result
            
            last_error = result.error or "Unknown error"
            
            # Classify the error for smart handling
            error_type, is_retryable, suggestion = self._classify_error(last_error)
            
            # Log error classification
            if attempt == 0:
                logger.info(f"Tool {tool_name} failed: {error_type} - {suggestion}")
            
            # Smart retry strategy based on error type
            if attempt >= max_retries:
                break
            
            if not is_retryable:
                logger.debug(f"Tool {tool_name} failed with non-retryable error ({error_type})")
                break
            
            # Calculate backoff based on error type
            if error_type == "timeout":
                backoff = 1.0 * (2 ** attempt)  # 1s, 2s, 4s...
            elif error_type == "rate_limit":
                backoff = 5.0 * (attempt + 1)  # 5s, 10s, 15s...
            elif error_type == "resource_busy":
                backoff = 2.0 * (attempt + 1)  # 2s, 4s, 6s...
            else:
                backoff = 0.5  # Quick retry for unknown transient errors
            
            logger.info(f"Tool {tool_name} retrying in {backoff}s (attempt {attempt + 1}, {error_type})")
            await asyncio.sleep(backoff)
        
        # Return the last failed result with error metadata
        final_attempts = max_retries + 1
        logger.warning(f"Tool {tool_name} failed after {final_attempts} attempts: {error_type} - {last_error}")
        return result  # type: ignore
    
    async def run(
        self,
        task: str,
        session_id: str = "default",
        context: Optional[str] = None,
    ) -> AgentResult:
        """
        Execute a task autonomously using ReAct loop with smart routing.
        
        Flow:
        1. Classify task (browser/local/mixed)
        2. Filter tools based on task type
        3. Generate plan for complex tasks
        4. Execute with ReAct loop
        
        Args:
            task: User's task/question
            session_id: Session ID for message grouping
            context: Optional additional context
            
        Returns:
            AgentResult with success status and response
        """
        if not self.client:
            return AgentResult(
                success=False,
                response="",
                error="Anthropic client not available. Check API key.",
            )
        
        # Generate unique message ID
        import uuid
        message_id = str(uuid.uuid4())[:8]
        
        # ===========================================
        # PHASE 1: Task Classification
        # ===========================================
        classification = None
        task_type_str = "local"  # Default to local
        
        if self.classifier and CLASSIFIER_AVAILABLE:
            classification = self.classifier.classify(task)
            task_type_str = classification.task_type.value
            
            logger.info(f"Task classified as {task_type_str} (confidence={classification.confidence:.2f})")
            
            # Broadcast classification to frontend
            if self.status_server:
                await self.status_server.broadcast({
                    "type": "classification",
                    "message_id": message_id,
                    "task_type": task_type_str,
                    "complexity": classification.complexity.value,
                    "confidence": classification.confidence,
                    "reasoning": classification.reasoning,
                })
        
        # ===========================================
        # PHASE 2: Tool Selection based on task type
        # ===========================================
        tools = self._get_tools_by_task_type(task_type_str)
        logger.info(f"Using {len(tools)} tools for {task_type_str} task")
        
        # ===========================================
        # PHASE 2.5: Browser Session Initialization
        # ===========================================
        if task_type_str in ("browser", "mixed") and BROWSER_SESSION_AVAILABLE:
            try:
                if not self._browser_session_active:
                    self._browser_session = await get_browser_session()
                    self._browser_session_active = True
                    # Inject browser session into registry context
                    self.registry.set_context("browser_session", self._browser_session)
                    logger.info("[Agent] Browser session initialized and injected")
            except Exception as e:
                logger.warning(f"[Agent] Failed to initialize browser session: {e}")
                # Continue without browser session - tools will return errors
        
        # ===========================================
        # PHASE 3: Planning for complex tasks
        # ===========================================
        plan = None
        if self.planner and PLANNER_AVAILABLE and classification:
            if classification.complexity != ClassifierComplexity.SIMPLE:
                plan = await self.planner.plan(task, category_filter=task_type_str)
                
                if plan and len(plan.steps) > 1:
                    logger.info(f"Generated plan with {len(plan.steps)} steps")
                    
                    # Broadcast plan to frontend
                    if self.status_server:
                        await self.status_server.broadcast({
                            "type": "plan",
                            "message_id": message_id,
                            "steps": plan.steps,
                            "complexity": plan.complexity.value,
                        })
        
        # Build system prompt with session history and long-term memory (async)
        system_prompt = await self._build_system_prompt_with_memory(session_id, task)
        
        # Inject plan into context if we have one
        user_content = task
        if context:
            user_content = f"{context}\n\n{task}"
        
        if plan and len(plan.steps) > 1:
            plan_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(plan.steps)])
            user_content = f"{user_content}\n\n**Suggested Plan:**\n{plan_text}\n\nFollow this plan step by step."
        
        messages = [{"role": "user", "content": user_content}]
        
        # ReAct loop
        iteration = 0
        tool_calls_made = []
        final_response = ""
        
        # Performance metrics (A3.1 TTFT Monitoring)
        task_start_time = time.time()
        ttft_recorded = False
        ttft_ms = None
        
        # Check if cache is warm and use cached system prompt
        use_caching = self._is_cache_warm(session_id)
        if use_caching:
            logger.info(f"Using warm cache for session {session_id}")
        
        # Visualization: task start
        if VISUALIZATION_AVAILABLE and self.status_server:
            await visualize_task_start(self.status_server, max_steps=self.max_iterations)
        
        while iteration < self.max_iterations:
            iteration += 1
            
            try:
                # Call Claude with streaming for real-time feedback
                text_content = ""
                tool_uses = []
                current_tool_args = ""  # Accumulate tool args JSON
                current_tool_index = -1
                
                # Build API call params
                api_params = {
                    "model": self.model,
                    "max_tokens": 16384,  # Increased for thinking budget
                    "tools": tools,
                    "messages": messages,
                    # Enable Extended Thinking for Claude Opus 4.5
                    "thinking": {
                        "type": "enabled",
                        "budget_tokens": 8192,  # Budget for reasoning
                    },
                }
                
                if use_caching:
                    api_params["extra_headers"] = {"anthropic-beta": self.PROMPT_CACHE_BETA}
                    api_params["system"] = self._build_cached_system(system_prompt)
                else:
                    api_params["system"] = system_prompt
                
                # Track thinking state
                is_thinking = False
                thinking_content = ""
                thinking_start_time = None
                current_block_type = None  # Track current block type
                
                # Use streaming API for real-time feedback
                with self.client.messages.stream(**api_params) as stream:
                    for event in stream:
                        # Record TTFT on first event
                        if not ttft_recorded:
                            ttft_ms = (time.time() - task_start_time) * 1000
                            ttft_recorded = True
                            if self.status_server:
                                await self.status_server.broadcast_performance(
                                    message_id=message_id,
                                    ttft_ms=ttft_ms,
                                )
                        
                        # Handle different event types
                        # Note: "text" events are deprecated, use content_block_delta with text_delta instead
                        # The old "text" event handling was removed to avoid duplicate broadcasts
                        
                        if event.type == "content_block_start":
                            if hasattr(event, 'content_block'):
                                block_type = event.content_block.type
                                current_block_type = block_type  # Track current block
                                
                                # Handle thinking block start
                                if block_type == "thinking":
                                    is_thinking = True
                                    thinking_content = ""
                                    thinking_start_time = time.time()
                                    if self.status_server:
                                        await self.status_server.broadcast({
                                            "type": "thinking_start",
                                            "message_id": message_id,
                                        })
                                
                                # Handle tool use block start
                                elif block_type == "tool_use":
                                    current_tool_index = event.index
                                    current_tool_args = ""
                                    tool_uses.append({
                                        "id": event.content_block.id,
                                        "name": event.content_block.name,
                                        "input": {},
                                    })
                                    # Stream tool start to frontend
                                    if self.status_server:
                                        await self.status_server.stream_tool_start(
                                            message_id,
                                            event.content_block.id,
                                            event.content_block.name,
                                        )
                        
                        elif event.type == "content_block_delta":
                            if hasattr(event, 'delta'):
                                delta_type = event.delta.type
                                
                                # Handle thinking delta
                                if delta_type == "thinking_delta":
                                    thinking_text = event.delta.thinking
                                    thinking_content += thinking_text
                                    if self.status_server and thinking_text:
                                        await self.status_server.broadcast({
                                            "type": "thinking_delta",
                                            "message_id": message_id,
                                            "thinking": thinking_text,
                                        })
                                
                                # Handle text delta
                                elif delta_type == "text_delta":
                                    text_delta = event.delta.text
                                    text_content += text_delta
                                    if self.status_server and text_delta:
                                        await self.status_server.broadcast({
                                            "type": "content",
                                            "message_id": message_id,
                                            "content": text_delta,
                                        })
                                
                                # Handle input JSON delta (tool args)
                                elif delta_type == "input_json_delta":
                                    current_tool_args += event.delta.partial_json
                        
                        elif event.type == "input_json":
                            # Accumulate tool arguments (streaming JSON) - fallback
                            current_tool_args += event.partial_json
                        
                        elif event.type == "content_block_stop":
                            # End thinking block (use current_block_type for robustness)
                            if current_block_type == "thinking" or is_thinking:
                                duration_ms = int((time.time() - thinking_start_time) * 1000) if thinking_start_time else None
                                if self.status_server:
                                    await self.status_server.broadcast({
                                        "type": "thinking_end",
                                        "message_id": message_id,
                                        "duration_ms": duration_ms,
                                    })
                                is_thinking = False
                                thinking_start_time = None
                            
                            current_block_type = None  # Reset block type
                            
                            # Finalize tool args if we were building a tool call
                            if current_tool_index >= 0 and current_tool_args:
                                try:
                                    tool_uses[-1]["input"] = json.loads(current_tool_args)
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to parse tool args: {current_tool_args[:100]}...")
                                current_tool_args = ""
                                current_tool_index = -1
                    
                    # Get final message for stop_reason
                    response = stream.get_final_message()
                
                # Signal end of streaming content
                if text_content and self.status_server:
                    await self.status_server.broadcast({
                        "type": "content_end",
                        "message_id": message_id,
                    })
                
                # Check if we're done (no tool calls)
                has_tool_use = len(tool_uses) > 0
                
                if not has_tool_use:
                    # Agent decided to respond without tools
                    final_response = text_content
                    break
                
                # Execute tools with smart retry
                tool_results = []
                
                for tool_index, tool_use in enumerate(tool_uses):
                    tool_name = tool_use["name"]
                    tool_args = tool_use["input"]
                    tool_id = tool_use["id"]
                    
                    # Stream tool start
                    if self.status_server:
                        await self.status_server.stream_tool_start(
                            message_id, tool_id, tool_name
                        )
                    
                    # Visualization: tool start
                    if VISUALIZATION_AVAILABLE and self.status_server:
                        await visualize_tool_start(
                            self.status_server, 
                            tool_name, 
                            tool_args, 
                            step=len(tool_calls_made) + tool_index
                        )
                    
                    # Execute tool with smart retry
                    result = await self._execute_with_retry(tool_name, tool_args)
                    
                    # Stream tool result
                    if self.status_server:
                        await self.status_server.stream_tool_result(
                            message_id,
                            tool_id,
                            result=result.output if result.success else None,
                            error=result.error if not result.success else None,
                        )
                    
                    # Visualization: tool end
                    if VISUALIZATION_AVAILABLE and self.status_server:
                        await visualize_tool_end(
                            self.status_server,
                            tool_name,
                            result.success,
                            step=len(tool_calls_made) + tool_index
                        )
                    
                    # Record tool call
                    tool_calls_made.append({
                        "name": tool_name,
                        "args": tool_args,
                        "success": result.success,
                        "output": result.output if result.success else result.error,
                        "retried": getattr(result, 'retried', False),
                    })
                    
                    # Add to session history (for "undo" functionality)
                    # Only record file-modifying operations
                    if tool_name in ["move_file", "create_directory", "delete_file", "write_file", "copy_file"]:
                        add_to_session_history(session_id, {
                            "tool": tool_name,
                            "args": tool_args,
                            "success": result.success,
                            "timestamp": time.time(),
                        })
                    
                    # Format result for Claude
                    if result.success:
                        result_content = str(result.output)
                    else:
                        result_content = f"Error: {result.error}"
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_content,
                    })
                
                # Add assistant message and tool results to history
                messages.append({
                    "role": "assistant",
                    "content": response.content,
                })
                messages.append({
                    "role": "user",
                    "content": tool_results,
                })
                
                # Check stop reason
                if response.stop_reason == "end_turn":
                    final_response = text_content
                    break
                    
            except Exception as e:
                # Visualization: task error
                if VISUALIZATION_AVAILABLE and self.status_server:
                    await visualize_task_error(self.status_server)
                return AgentResult(
                    success=False,
                    response="",
                    error=f"Agent error: {str(e)}",
                    iterations=iteration,
                    tool_calls=tool_calls_made,
                )
        
        # Record final performance metrics (A3.1)
        total_time_ms = (time.time() - task_start_time) * 1000
        if self.status_server:
            await self.status_server.broadcast_performance(
                message_id=message_id,
                ttft_ms=ttft_ms,
                total_time_ms=total_time_ms,
                tool_calls=len(tool_calls_made),
                iterations=iteration,
            )
        
        # B2.2: Save execution history to knowledge store
        if self.knowledge_store and KNOWLEDGE_AVAILABLE:
            try:
                trajectory = Trajectory(
                    session_id=session_id,
                    task=task,
                    tool_calls=tool_calls_made,
                    success=True,
                    duration_ms=total_time_ms,
                    iterations=iteration,
                )
                self.knowledge_store.save_trajectory(trajectory)
                
                # B2.4: Update user preferences from execution
                self.knowledge_store.update_profile_from_execution(
                    profile_id=session_id,
                    task=task,
                    tool_calls=tool_calls_made,
                )
            except Exception as e:
                # Don't fail if saving fails
                pass
        
        # Long-term memory: Extract memories from this conversation (background)
        if self.memory_processor and MEMORY_AVAILABLE:
            try:
                # Convert messages to simple format for extraction
                extraction_messages = []
                extraction_messages.append({"role": "user", "content": task})
                if final_response:
                    extraction_messages.append({"role": "assistant", "content": final_response})
                
                # Schedule background extraction (non-blocking)
                self.memory_processor.schedule_extraction(
                    messages=extraction_messages,
                    session_id=session_id,
                    source_task=task[:100],  # Truncate long tasks
                )
                logger.debug(f"Scheduled memory extraction for session {session_id}")
            except Exception as e:
                # Don't fail if memory extraction fails
                logger.warning(f"Failed to schedule memory extraction: {e}")
        
        # Visualization: task complete
        if VISUALIZATION_AVAILABLE and self.status_server:
            await visualize_task_complete(self.status_server)
        
        # Return result
        return AgentResult(
            success=True,
            response=final_response,
            iterations=iteration,
            tool_calls=tool_calls_made,
        )
    
    async def run_with_planning(
        self,
        task: str,
        session_id: str = "default",
        context: Optional[str] = None,
    ) -> AgentResult:
        """
        Execute a task with optional planning for complex tasks.
        
        This method adds a planning layer on top of the ReAct agent:
        1. Analyze task complexity
        2. If simple: execute directly with run()
        3. If complex: generate plan, execute step by step
        4. On error: attempt to replan and continue
        
        Args:
            task: User's task/question
            session_id: Session ID for message grouping
            context: Optional additional context
            
        Returns:
            AgentResult with success status and response
        """
        if not self.planner or not PLANNER_AVAILABLE:
            # Fallback to regular execution
            return await self.run(task, session_id, context)
        
        # Generate plan
        try:
            plan = await self.planner.plan(task)
        except Exception as e:
            raise
        
        # Simple task: execute directly
        if plan.complexity.value == "simple" or len(plan) <= 1:
            logger.debug(f"Simple task, executing directly")
            return await self.run(task, session_id, context)
        
        # Complex task: execute step by step
        logger.info(f"Complex task with {len(plan)} steps, executing with planning")
        
        # Broadcast plan to UI
        if self.status_server:
            import uuid
            message_id = str(uuid.uuid4())[:8]
            plan_text = "**执行计划:**\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan.steps))
            await self.status_server.stream_content(message_id, plan_text)
        
        # Create state
        state = PlanExecuteState(
            input=task,
            plan=plan,
            past_steps=[],
        )
        
        all_tool_calls = []
        total_iterations = 0
        
        # Execute steps
        step_num = 0
        while state.plan.remaining > 0:
            step_num += 1
            current_step = state.plan.pop_first()
            
            if not current_step:
                break
            
            logger.info(f"Executing step {step_num}: {current_step[:50]}...")
            
            # Execute step using regular run()
            step_result = await self.run(
                task=current_step,
                session_id=session_id,
                context=f"This is step {step_num} of a larger task: {task[:100]}"
            )
            
            total_iterations += step_result.iterations
            all_tool_calls.extend(step_result.tool_calls)
            
            if step_result.success:
                # Record completed step
                state.past_steps.append((current_step, step_result.response[:200]))
                logger.debug(f"Step {step_num} completed successfully")
            else:
                # Step failed - attempt replan
                logger.warning(f"Step {step_num} failed: {step_result.error}")
                
                # replan now returns 3 values: (action, result, error_type)
                replan_result = await self.planner.replan(
                    state=state,
                    current_step=current_step,
                    error=step_result.error or "Unknown error",
                )
                action, result, error_type = replan_result
                
                logger.info(f"Replan result: action={action}, error_type={error_type}")
                
                if action == "continue" and Plan and isinstance(result, Plan):
                    # Continue with new plan
                    state.plan = result
                    logger.info(f"Replanned with {len(result)} remaining steps")
                elif action == "respond":
                    # Task completed with partial result
                    state.response = str(result) if result else ""
                    break
                else:
                    # Task failed
                    return AgentResult(
                        success=False,
                        response="",
                        error=str(result) if result else "Task failed",
                        iterations=total_iterations,
                        tool_calls=all_tool_calls,
                    )
            
            # Safety limit
            if step_num >= 10:
                logger.warning("Too many steps, stopping")
                break
        
        # Generate final response
        if state.response:
            final_response = state.response
        else:
            # Summarize completed steps
            steps_summary = "\n".join(f"✓ {step}" for step, _ in state.past_steps)
            final_response = f"任务完成！\n\n{steps_summary}"
        
        return AgentResult(
            success=True,
            response=final_response,
            iterations=total_iterations,
            tool_calls=all_tool_calls,
        )
