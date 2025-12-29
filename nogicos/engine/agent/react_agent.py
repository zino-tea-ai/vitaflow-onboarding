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
import copy
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

# Anthropic client
try:
    import anthropic
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None
    AsyncAnthropic = None

# Logging
from engine.observability import get_logger
logger = get_logger("react_agent")

# Import tool registry
from engine.tools.base import ToolRegistry, ToolCategory
from engine.tools import create_full_registry

# Import knowledge store (B2)
try:
    from engine.knowledge import KnowledgeStore, UserProfile, Trajectory
    from engine.knowledge.store import get_store
    KNOWLEDGE_AVAILABLE = True
except ImportError:
    KNOWLEDGE_AVAILABLE = False
    KnowledgeStore = None
    UserProfile = None
    Trajectory = None

# Import long-term memory system
try:
    from engine.knowledge import (
        get_memory_store, 
        SemanticMemorySearch,
        BackgroundMemoryProcessor,
        format_memories_for_prompt,
    )
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    get_memory_store = None
    SemanticMemorySearch = None
    BackgroundMemoryProcessor = None
    format_memories_for_prompt = None

# Import task planner
try:
    from engine.agent.planner import TaskPlanner, Plan, PlanExecuteState
    PLANNER_AVAILABLE = True
except ImportError:
    PLANNER_AVAILABLE = False
    TaskPlanner = None
    Plan = None
    PlanExecuteState = None


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
        self.client = None
        self.async_client = None
        
        if ANTHROPIC_AVAILABLE:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self.client = anthropic.Anthropic(api_key=api_key)
                if AsyncAnthropic:
                    self.async_client = AsyncAnthropic(api_key=api_key)
        
        # Tool registry - create once and reuse
        self.registry = create_full_registry()
        
        # Knowledge store (B2.1)
        self.knowledge_store = get_store() if KNOWLEDGE_AVAILABLE else None
        
        # Long-term memory store
        self.memory_store = get_memory_store() if MEMORY_AVAILABLE else None
        self.memory_search = SemanticMemorySearch(self.memory_store) if MEMORY_AVAILABLE and self.memory_store else None
        self.memory_processor = BackgroundMemoryProcessor(self.memory_store) if MEMORY_AVAILABLE and self.memory_store else None
        
        # Task planner for complex tasks
        self.planner = TaskPlanner(model=model) if PLANNER_AVAILABLE else None
        
        # Base system prompt (will be customized per request with history)
        self.base_system_prompt = build_system_prompt(self.registry)
        
        # Cache warming state (tracks which sessions have warm caches)
        self._warm_caches: Dict[str, float] = {}  # session_id -> timestamp
        self._cache_ttl = 300  # Cache warm for 5 minutes
    
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
        
        for attempt in range(max_retries + 1):
            result = await self.registry.execute(tool_name, args)
            
            if result.success:
                # Mark if this was a retry success
                if attempt > 0:
                    logger.info(f"Tool {tool_name} succeeded on retry {attempt}")
                    result.retried = True
                return result
            
            last_error = result.error or "Unknown error"
            error_lower = str(last_error).lower()
            
            # Smart retry strategy based on error type
            if attempt >= max_retries:
                # Max retries exhausted
                break
                
            # Don't retry deterministic failures
            if any(keyword in error_lower for keyword in [
                "not found", "does not exist", "no such file",
                "permission denied", "access denied",
                "invalid argument", "invalid parameter",
                "syntax error", "parse error",
            ]):
                logger.debug(f"Tool {tool_name} failed with non-retryable error: {last_error}")
                break
            
            # Timeout errors: exponential backoff
            if any(keyword in error_lower for keyword in [
                "timeout", "timed out", "connection reset",
                "connection refused", "network error",
            ]):
                backoff = 1.0 * (2 ** attempt)  # 1s, 2s, 4s...
                logger.info(f"Tool {tool_name} timeout, retrying in {backoff}s (attempt {attempt + 1})")
                await asyncio.sleep(backoff)
                continue
            
            # Rate limiting: longer backoff
            if any(keyword in error_lower for keyword in [
                "rate limit", "too many requests", "429",
            ]):
                backoff = 5.0 * (attempt + 1)  # 5s, 10s, 15s...
                logger.info(f"Tool {tool_name} rate limited, retrying in {backoff}s")
                await asyncio.sleep(backoff)
                continue
            
            # Default: quick retry for transient errors
            await asyncio.sleep(0.5)
            logger.info(f"Tool {tool_name} failed, quick retry (attempt {attempt + 1})")
        
        # Return the last failed result
        logger.warning(f"Tool {tool_name} failed after {max_retries} retries: {last_error}")
        return result
    
    async def run(
        self,
        task: str,
        session_id: str = "default",
        context: Optional[str] = None,
    ) -> AgentResult:
        """
        Execute a task autonomously using ReAct loop.
        
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
        
        # Get tools in Anthropic format
        tools = self.registry.to_anthropic_format()
        
        # Build system prompt with session history and long-term memory (async)
        system_prompt = await self._build_system_prompt_with_memory(session_id, task)
        
        # Build initial message
        user_content = task
        if context:
            user_content = f"{context}\n\n{task}"
        
        messages = [{"role": "user", "content": user_content}]
        
        # Generate unique message ID
        import uuid
        message_id = str(uuid.uuid4())[:8]
        
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
        
        while iteration < self.max_iterations:
            iteration += 1
            
            try:
                # Call Claude with tools (use cached system prompt if available)
                if use_caching:
                    # Use cached system prompt format
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=4096,
                        extra_headers={"anthropic-beta": self.PROMPT_CACHE_BETA},
                        system=self._build_cached_system(system_prompt),
                        tools=tools,
                        messages=messages,
                    )
                else:
                    # Standard call without caching
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=4096,
                        system=system_prompt,
                        tools=tools,
                        messages=messages,
                    )
                
                # Record TTFT (Time to First Token) - A3.1
                if not ttft_recorded:
                    ttft_ms = (time.time() - task_start_time) * 1000
                    ttft_recorded = True
                    if self.status_server:
                        # Broadcast TTFT immediately
                        await self.status_server.broadcast_performance(
                            message_id=message_id,
                            ttft_ms=ttft_ms,
                        )
                
                # Process response
                text_content = ""
                tool_uses = []
                
                for block in response.content:
                    if block.type == "text":
                        text_content += block.text
                    elif block.type == "tool_use":
                        tool_uses.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                
                # Stream thinking/content
                if text_content and self.status_server:
                    await self.status_server.stream_content(message_id, text_content)
                
                # Check if we're done (no tool calls)
                has_tool_use = len(tool_uses) > 0
                
                if not has_tool_use:
                    # Agent decided to respond without tools
                    final_response = text_content
                    break
                
                # Execute tools with smart retry
                tool_results = []
                
                for tool_use in tool_uses:
                    tool_name = tool_use["name"]
                    tool_args = tool_use["input"]
                    tool_id = tool_use["id"]
                    
                    # Stream tool start
                    if self.status_server:
                        await self.status_server.stream_tool_start(
                            message_id, tool_id, tool_name
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
                
                action, result = await self.planner.replan(
                    state=state,
                    current_step=current_step,
                    error=step_result.error or "Unknown error",
                )
                
                if action == "continue" and isinstance(result, Plan):
                    # Continue with new plan
                    state.plan = result
                    logger.info(f"Replanned with {len(result)} remaining steps")
                elif action == "respond":
                    # Task completed with partial result
                    state.response = result
                    break
                else:
                    # Task failed
                    return AgentResult(
                        success=False,
                        response="",
                        error=result if isinstance(result, str) else "Task failed",
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
