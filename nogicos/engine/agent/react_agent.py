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
- LangSmith Integration: Full observability and tracing

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
from typing import Optional, List, Dict, Any, TYPE_CHECKING, Callable, Awaitable
from dataclasses import dataclass, field

# Logging
from engine.observability import get_logger
logger = get_logger("react_agent")

# LangSmith integration (optional)
try:
    from engine.observability.langsmith_tracer import (
        is_enabled as langsmith_enabled,
        trace_agent_run,
        trace_tool_call,
        wrap_anthropic_client,
        trace_span,
    )
    LANGSMITH_AVAILABLE = langsmith_enabled()
    if LANGSMITH_AVAILABLE:
        logger.info("[Agent] LangSmith tracing enabled")
except ImportError:
    LANGSMITH_AVAILABLE = False
    trace_agent_run = lambda **kw: lambda f: f  # No-op decorator
    trace_tool_call = lambda **kw: lambda f: f
    wrap_anthropic_client = lambda c: c
    trace_span = None

# Prometheus metrics (optional)
try:
    from monitoring.prometheus.metrics import get_metrics, AgentMetrics
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    get_metrics = None

# Import tool registry
from engine.tools.base import ToolRegistry, ToolCategory
from engine.tools import create_full_registry

# Import mode router
from engine.agent.modes import AgentMode, ModeRouter, get_mode_router

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

# Verification module (optional)
try:
    from engine.agent.verification import AnswerVerifier, verify_answer
    VERIFICATION_AVAILABLE = True
except ImportError:
    VERIFICATION_AVAILABLE = False
    AnswerVerifier = None

# Context injection module (Cursor-style context)
try:
    from engine.context import ContextInjector, ContextConfig, get_context_injector
    CONTEXT_INJECTION_AVAILABLE = True
except ImportError:
    CONTEXT_INJECTION_AVAILABLE = False
    ContextInjector = None
    ContextConfig = None
    get_context_injector = None


@dataclass
class AgentResult:
    """Result from agent execution"""
    success: bool
    response: str
    error: Optional[str] = None
    iterations: int = 0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReflectionResult:
    """Result from reflection check before answer submission"""
    needs_revision: bool
    feedback: str
    confidence: float = 1.0
    issues: List[str] = field(default_factory=list)


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

## Efficiency Principle

**Complete tasks in as few iterations as possible.**

- When calling tools, batch related operations together
- Don't ask clarifying questions unless truly necessary
- If you have enough context, ACT immediately
- After executing tools, provide a complete response - don't iterate unnecessarily
- If the task is complete, say so and stop

## Understanding User Intent

When user says something vague, INTERPRET and ACT:
| User says | You understand | You do |
|-----------|---------------|--------|
| "整理桌面" | Organize desktop files | list_directory → create folders → move files |
| "当前目录有什么" | Check current directory contents | list_directory → show files and folders |
| "还原刚才的整理" | Undo my previous actions | Check operation history → reverse moves |
| "你自己判断" | User trusts you | Proceed with best judgment |
| "帮我看看" | User wants info | list_directory → report findings |

## Tool Selection Priority (CRITICAL)

**For file/folder queries, ALWAYS prefer `list_directory` over `desktop_screenshot`:**

| User says | Use | Reason |
|-----------|-----|--------|
| "桌面有什么" | list_directory | Need accurate file list |
| "帮我看看桌面" | list_directory | "看" = check contents |
| "目录里有什么文件" | list_directory | File query |
| "桌面长什么样" | desktop_screenshot | Visual appearance |
| "能看到我的壁纸吗" | desktop_screenshot | Visual content |
| "截个图看看" | desktop_screenshot | Explicit screenshot request |

**Why:** 
- `list_directory` = 100% accurate file names
- `desktop_screenshot` = Visual recognition is unreliable, may hallucinate file names

**Rule:** Only use `desktop_screenshot` when user explicitly asks about visual appearance, wallpaper, or icon arrangement - NOT for listing files.

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

### Long-term Memory (User Preferences & Facts)
{{long_term_memory}}

**Memory Application Rules:**
- When you see user preferences in memory (e.g., "prefers pnpm", "likes vim"), ALWAYS apply them
- Example: If memory says "prefers pnpm over npm", use `pnpm install X` instead of `npm install X`
- These preferences were explicitly saved by the user - following them is mandatory
- If a task involves a domain where user has stored preference, use it without asking

## Response Format Requirements

**CRITICAL**: You must ALWAYS provide a visible response to the user.
Even if tools execute successfully, you must give a clear summary of what you found/did.

For directory queries like "当前目录有什么":
1. Use list_directory tool to get contents
2. Format the results clearly for the user
3. Include file names, types, and brief description
4. If the directory is empty, explicitly say so
5. If there's an error, explain what went wrong

## Safety Rules (simple version)

Only TWO rules:
1. **Don't touch code projects**: Skip folders withh .git or code files (.py, .js, etc.)
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

## Decision Guidelines (Cursor-style)

**BE EFFICIENT** - These rules come from high-performing AI agents:

1. **Direct answers**: After getting a result, answer immediately. Don't add extra verification steps.
2. **Simple interpretation**: When task is ambiguous, choose the simpler approach.
   - "files in directory" = direct children only (not recursive unless specified)
   - "count files" = simple ls + count, not complex find commands
3. **No over-verification**: Trust your first correct result. Don't add "let me double-check" steps.
4. **Tight iteration**: Target completion in ≤8 tool calls. Each call should make progress.

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
    # Extended Thinking beta header (required for thinking parameter)
    THINKING_BETA = "interleaved-thinking-2025-05-14"
    
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
        
        # Wrap clients with LangSmith tracing if enabled
        if LANGSMITH_AVAILABLE:
            self.client = wrap_anthropic_client(self.client)
            self.async_client = wrap_anthropic_client(self.async_client)
            logger.info("[Agent] Anthropic clients wrapped with LangSmith tracing")
        
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
        
        # Memory search result cache (avoid repeated semantic searches)
        self._memory_cache: Dict[str, Dict] = {}  # task_hash -> {result, timestamp}
        self._memory_cache_ttl = 300  # Memory cache valid for 5 minutes
        
        # Tool category cache (dynamically populated from registry)
        self._tool_categories_cache: Dict[str, str] = {}
        self._refresh_tool_categories()
        
        # Browser session state (lazy initialized for browser tasks)
        self._browser_session = None
        self._browser_session_active = False
        
        # Context injector (Cursor-style context injection)
        self.context_injector = get_context_injector() if CONTEXT_INJECTION_AVAILABLE else None
        
        # Track first message per session (for full context injection)
        self._session_first_message: Dict[str, bool] = {}
        
        # Mode router for Agent/Ask/Plan modes (Cursor-style)
        self.mode_router = get_mode_router()
    
    def _refresh_tool_categories(self) -> None:
        """Refresh tool categories cache from registry"""
        self._tool_categories_cache.clear()
        for tool in self.registry.get_all():
            self._tool_categories_cache[tool.name] = tool.category.value
        logger.debug(f"Refreshed tool categories: {len(self._tool_categories_cache)} tools")
    
    def _is_simple_chat(self, task: str) -> bool:
        """
        Detect if task is simple chat that doesn't need tools.
        
        Simple chats include:
        - Greetings (hi, hello, 你好, etc.)
        - Confirmations (yes, no, ok, etc.)
        - Basic questions about the AI
        
        NOT simple (needs tools):
        - Tasks with action verbs (看、找、打开、列出, etc.)
        - Any request that implies file/browser/system operations
        
        Returns:
            True if task is simple chat (no tools needed)
        """
        task_lower = task.lower().strip()
        
        # Action verbs indicate tool usage is needed (NOT simple)
        action_patterns = [
            # Chinese action verbs
            '看', '找', '打开', '列出', '运行', '创建', '删除', '移动', '复制',
            '搜索', '查找', '整理', '修改', '编辑', '下载', '上传', '安装',
            '桌面', '文件', '文件夹', '目录', '浏览器', '网页', '网站',
            # English action verbs
            'look', 'find', 'open', 'list', 'run', 'create', 'delete', 'move', 'copy',
            'search', 'organize', 'modify', 'edit', 'download', 'upload', 'install',
            'desktop', 'file', 'folder', 'directory', 'browser', 'website', 'page',
            'show me', 'tell me about', 'what is in', 'what\'s in',
        ]
        if any(p in task_lower for p in action_patterns):
            return False  # Needs tools
        
        # Greeting patterns (simple)
        greetings = {'hi', 'hello', 'hey', '你好', '嗨', 'hola', 'bonjour', 'yo', 'sup'}
        if task_lower in greetings or any(task_lower.startswith(g) for g in greetings):
            return True
        
        # Very short messages without action intent (simple)
        if len(task) < 6:
            return True
        
        # Confirmation patterns (simple)
        confirmations = {'yes', 'no', 'ok', 'okay', '好', '是', '否', 'sure', 'yep', 'nope'}
        if task_lower in confirmations:
            return True
        
        # Simple questions about the AI (simple)
        simple_patterns = ['how are you', 'what time', "what's up", '怎么样', '你是谁', 'who are you']
        if any(p in task_lower for p in simple_patterns):
            return True
        
        # Default: not simple (give tools)
        return False
    
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
    
    async def _build_system_prompt_with_memory(
        self, session_id: str, task: str, skip_memory: bool = False
    ) -> str:
        """
        Build system prompt with long-term memory (async version).
        
        Retrieves semantically relevant memories based on the current task.
        Uses caching to avoid repeated semantic searches for similar tasks.
        
        Args:
            session_id: Session ID for memory scoping
            task: Current task for semantic search
            skip_memory: If True, skip memory search for faster response (simple chats)
            
        Returns:
            System prompt with injected memory context
        """
        import hashlib
        
        # Start with base prompt + operation history
        history = format_operation_history(session_id)
        prompt = self.base_system_prompt.replace("{operation_history}", history)
        
        # Inject long-term memory if available (skip for simple chats to save ~3s)
        memory_context = ""
        if self.memory_search and MEMORY_AVAILABLE and not skip_memory:
            try:
                # Create cache key from task + session_id
                cache_key = hashlib.md5(f"{session_id}:{task}".encode()).hexdigest()
                current_time = time.time()
                
                # Check cache first
                if cache_key in self._memory_cache:
                    cached = self._memory_cache[cache_key]
                    if current_time - cached["timestamp"] < self._memory_cache_ttl:
                        memory_context = cached["result"]
                        logger.debug(f"[Agent] Memory cache hit for task '{task[:30]}...'")
                    else:
                        # Cache expired, remove it
                        del self._memory_cache[cache_key]
                
                # If not in cache, perform search
                if not memory_context:
                    memory_context = await self.memory_search.search_for_prompt(
                        query=task,
                        session_id=session_id,
                        max_tokens=400,  # Limit to ~400 tokens for memory
                    )
                    # Cache the result
                    self._memory_cache[cache_key] = {
                        "result": memory_context or "",
                        "timestamp": current_time,
                    }
                    if memory_context:
                        logger.debug(f"[Agent] Memory search: {len(memory_context)} chars cached")
                    
                    # Clean up old cache entries (keep cache size manageable)
                    if len(self._memory_cache) > 100:
                        # Remove oldest entries
                        sorted_keys = sorted(
                            self._memory_cache.keys(),
                            key=lambda k: self._memory_cache[k]["timestamp"]
                        )
                        for key in sorted_keys[:50]:  # Remove oldest 50
                            del self._memory_cache[key]
                            
            except Exception as e:
                logger.warning(f"Failed to load memory context: {e}")
        elif skip_memory:
            logger.debug("[Agent] Skipping memory search for simple chat")
        
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
    
    def _build_cached_tools(self, tools: list) -> list:
        """
        Build tools list with cache_control for Anthropic API.
        
        Adds cache_control to the last tool in the list, which tells
        Anthropic to cache all tools up to and including that point.
        
        This significantly reduces input tokens on repeated calls since
        tool definitions are typically static.
        
        Args:
            tools: List of tools in Anthropic format
            
        Returns:
            Tools list with cache_control on last element
        """
        if not tools:
            return tools
        
        # Deep copy to avoid modifying original
        cached_tools = [dict(t) for t in tools]
        
        # Add cache_control to last tool (caches all tools before it too)
        cached_tools[-1]["cache_control"] = {"type": "ephemeral"}
        
        return cached_tools
    
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
    
    def _should_reflect(self, text_content: str, task: str) -> bool:
        """
        Determine if reflection is needed before submitting an answer.
        
        Reflection is triggered for:
        - Tasks that expect specific answers (numbers, paths, counts)
        - Tasks with answer() action pattern
        - Non-trivial responses
        
        Args:
            text_content: The agent's proposed response
            task: The original task
            
        Returns:
            True if reflection should be performed
        """
        if not text_content:
            return False
        
        response_stripped = text_content.strip()
        
        # Skip reflection for simple acknowledgments
        simple_responses = ["ok", "done", "finished", "完成", "好的", "已完成"]
        if response_stripped.lower() in simple_responses:
            return False
        
        # Skip very short non-numeric responses (but allow short numbers like "42")
        if len(response_stripped) < 5 and not response_stripped.isdigit():
            return False
        
        # Trigger reflection for tasks expecting specific answers
        answer_indicators = [
            "how many", "count", "number of", "total",
            "what is", "find", "calculate", "determine",
            "多少", "统计", "计算", "查找", "数量",
            "integer", "answer", "result", "lines", "files"
        ]
        
        task_lower = task.lower()
        for indicator in answer_indicators:
            if indicator in task_lower:
                return True
        
        # Check if response looks like a specific answer (number, path, etc.)
        if response_stripped.isdigit():
            return True  # Numeric answer - worth verifying
        
        return False
    
    async def _reflect_before_submit(
        self,
        task: str,
        answer: str,
        tool_calls: List[Dict[str, Any]],
    ) -> ReflectionResult:
        """
        Perform reflection before submitting an answer.
        
        Uses a lightweight LLM call to verify:
        1. Answer format matches task requirements
        2. Answer is derived from tool outputs
        3. Action selection is correct (answer vs finish)
        
        Args:
            task: Original task
            answer: Proposed answer
            tool_calls: List of tool calls made
            
        Returns:
            ReflectionResult with revision needs and feedback
        """
        issues = []
        
        # Check 1: Numeric answer format
        task_lower = task.lower()
        expects_number = any(kw in task_lower for kw in [
            "how many", "count", "number", "integer", "total",
            "多少", "数量", "统计", "计算"
        ])
        
        if expects_number:
            # Extract potential number from answer
            import re
            numbers = re.findall(r'\d+', answer)
            if not numbers:
                issues.append("Task expects a numeric answer but response contains no numbers")
            elif len(numbers) > 1:
                # Multiple numbers - might be ambiguous
                issues.append(f"Multiple numbers found in answer ({numbers}). Ensure the correct one is provided.")
        
        # Check 2: Answer derived from tool outputs
        if tool_calls:
            last_successful = [tc for tc in tool_calls if tc.get("success")]
            if last_successful:
                last_output = str(last_successful[-1].get("output", ""))
                # Simple check: key parts of answer should appear in tool output
                answer_core = answer.strip().split()[0] if answer.strip() else ""
                if answer_core and answer_core not in last_output:
                    issues.append(f"Answer '{answer_core}' not found in last tool output. Verify correctness.")
        
        # Check 3: Action selection (for AgentBench compatibility)
        # If task asks for an answer, ensure we're using answer() format
        if expects_number and "answer(" not in answer.lower() and not answer.strip().isdigit():
            issues.append("Task expects a specific answer. Consider using answer(VALUE) format.")
        
        # Determine if revision is needed
        needs_revision = len(issues) > 0
        
        if needs_revision:
            feedback = "Before submitting, please verify:\n" + "\n".join(f"- {issue}" for issue in issues)
            feedback += "\n\nReview your answer and tool outputs, then provide the correct response."
            logger.info(f"[Reflection] Issues found: {issues}")
        else:
            feedback = ""
            logger.debug("[Reflection] No issues found, proceeding with answer")
        
        return ReflectionResult(
            needs_revision=needs_revision,
            feedback=feedback,
            confidence=0.5 if needs_revision else 0.9,
            issues=issues,
        )
    
    def _detect_loop(self, tool_calls: List[Dict[str, Any]], window: int = 3) -> bool:
        """
        Detect if the agent is stuck in a repetitive loop.
        
        Checks if the last N tool calls are identical (same tool + same args).
        
        Args:
            tool_calls: List of tool calls made so far
            window: Number of recent calls to check
            
        Returns:
            True if a loop is detected
        """
        if len(tool_calls) < window:
            return False
        
        recent = tool_calls[-window:]
        
        # Check if all recent calls are the same tool with same args
        first = recent[0]
        for call in recent[1:]:
            if call["name"] != first["name"]:
                return False
            if call["args"] != first["args"]:
                return False
        
        # All calls are identical - loop detected
        logger.warning(f"[Loop Detection] Detected {window} identical calls to {first['name']}")
        return True
    
    async def _handle_plan_mode(
        self,
        task: str,
        session_id: str,
        context: Optional[str],
        message_id: str,
    ) -> AgentResult:
        """
        Handle Plan mode: generate editable plan without executing.
        
        In Plan mode, we:
        1. Analyze the task and explore context (read-only)
        2. Generate a detailed, editable plan
        3. Return the plan for user to review/edit
        4. User can then confirm to execute
        
        Args:
            task: User's task description
            session_id: Session ID
            context: Optional context
            message_id: Message ID for WebSocket
            
        Returns:
            AgentResult with plan in response (JSON format)
        """
        from engine.agent.planner import EditablePlan
        
        logger.info(f"[Plan Mode] Generating editable plan for: {task[:50]}...")
        
        # Broadcast plan generation start
        if self.status_server:
            await self.status_server.broadcast({
                "type": "plan_generating",
                "message_id": message_id,
            })
        
        try:
            # Use planner to generate detailed plan
            if self.planner and PLANNER_AVAILABLE:
                editable_plan = await self.planner.generate_editable_plan(
                    task=task,
                    context=context,
                )
            else:
                # Fallback: create simple plan
                from engine.agent.planner import EditablePlanStep, TaskComplexity
                editable_plan = EditablePlan(
                    summary=task,
                    steps=[EditablePlanStep(
                        step_number=1,
                        description=task,
                    )],
                    complexity=TaskComplexity.SIMPLE,
                    estimated_time="Unknown",
                )
            
            # Convert to dict for response
            plan_data = editable_plan.to_dict()
            plan_markdown = editable_plan.to_markdown()
            
            # Broadcast plan to frontend
            if self.status_server:
                await self.status_server.broadcast({
                    "type": "plan_generated",
                    "message_id": message_id,
                    "plan": plan_data,
                    "markdown": plan_markdown,
                })
            
            logger.info(f"[Plan Mode] Generated plan with {len(editable_plan.steps)} steps")
            
            # Return plan as response (user needs to confirm)
            import json
            return AgentResult(
                success=True,
                response=json.dumps(plan_data, ensure_ascii=False, indent=2),
                iterations=0,
                tool_calls=[],
            )
            
        except Exception as e:
            logger.error(f"[Plan Mode] Failed to generate plan: {e}")
            
            if self.status_server:
                await self.status_server.broadcast({
                    "type": "plan_error",
                    "message_id": message_id,
                    "error": str(e),
                })
            
            return AgentResult(
                success=False,
                response="",
                error=f"Failed to generate plan: {e}",
            )
    
    async def run(
        self,
        task: str,
        session_id: str = "default",
        context: Optional[str] = None,
        mode: AgentMode = AgentMode.AGENT,
        confirmed_plan: Optional[Plan] = None,
        on_text_delta: Optional[Callable[[str], Awaitable[None]]] = None,
        on_thinking_delta: Optional[Callable[[str], Awaitable[None]]] = None,
        on_tool_start: Optional[Callable[[str, str, Dict[str, Any]], Awaitable[None]]] = None,
        on_tool_end: Optional[Callable[[str, bool, str], Awaitable[None]]] = None,
    ) -> AgentResult:
        """
        Execute a task using ReAct loop with mode-based routing.
        
        Modes:
        - AGENT: Autonomous execution, all tools available
        - ASK: Read-only exploration, restricted to read-only tools
        - PLAN: Generate editable plan, return for user confirmation
        
        Flow:
        1. Check mode and apply mode-specific logic
        2. Classify task (browser/local/mixed)
        3. Filter tools based on task type AND mode
        4. Generate/execute based on mode
        
        Args:
            task: User's task/question
            session_id: Session ID for message grouping
            context: Optional additional context
            mode: Agent mode (AGENT/ASK/PLAN)
            confirmed_plan: User-confirmed plan for execution (Plan mode)
            on_text_delta: Callback for real-time text streaming (delta: str)
            on_thinking_delta: Callback for thinking content streaming
            on_tool_start: Callback when tool execution starts (tool_id, tool_name)
            on_tool_end: Callback when tool execution ends (tool_id, success, result)
            
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
        # PHASE 0: Mode-specific handling
        # ===========================================
        logger.info(f"[Agent] Running in {mode.value} mode")
        
        # Broadcast mode to frontend
        if self.status_server:
            await self.status_server.broadcast({
                "type": "mode_active",
                "message_id": message_id,
                "mode": mode.value,
            })
        
        # PLAN MODE: Generate editable plan and return (don't execute)
        if mode == AgentMode.PLAN and confirmed_plan is None:
            return await self._handle_plan_mode(task, session_id, context, message_id)
        
        # If we have a confirmed plan (from Plan mode), use it
        if confirmed_plan is not None:
            logger.info(f"[Agent] Executing confirmed plan with {len(confirmed_plan.steps)} steps")
        
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
        # PHASE 2: Tool Selection based on task type AND mode
        # ===========================================
        tools = self._get_tools_by_task_type(task_type_str)
        
        # Filter tools based on mode (ASK mode = read-only tools only)
        if mode in (AgentMode.ASK, AgentMode.PLAN):
            tools = self.mode_router.get_allowed_tools(mode, tools)
            logger.info(f"[Agent] Mode {mode.value}: filtered to {len(tools)} read-only tools")
        
        logger.info(f"Using {len(tools)} tools for {task_type_str} task in {mode.value} mode")
        
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
        
        # Early simple chat detection for optimization
        is_simple_chat = self._is_simple_chat(task)
        if is_simple_chat:
            logger.info(f"[Agent] Simple chat detected early, will skip memory search")
        
        # Build system prompt with session history and long-term memory (async)
        # Skip memory search for simple chats to save ~3s
        system_prompt = await self._build_system_prompt_with_memory(
            session_id, task, skip_memory=is_simple_chat
        )
        
        # Add mode-specific prompt modifier (ASK/PLAN modes)
        mode_modifier = self.mode_router.get_system_prompt_modifier(mode)
        if mode_modifier:
            system_prompt = mode_modifier + "\n\n" + system_prompt
            logger.debug(f"[Agent] Added {mode.value} mode prompt modifier")
        
        # Inject plan into context if we have one
        user_content = task
        if context:
            user_content = f"{context}\n\n{task}"
        
        # Cursor-style context injection
        if self.context_injector and CONTEXT_INJECTION_AVAILABLE:
            try:
                # Determine if this is first message in session
                is_first_message = session_id not in self._session_first_message
                
                if is_first_message:
                    # Full context for first message
                    ctx_config = self.context_injector.create_first_message_context(
                        workspace_path=os.getcwd(),
                        session_id=session_id,
                    )
                    self._session_first_message[session_id] = True
                else:
                    # Lighter context for subsequent messages
                    ctx_config = self.context_injector.create_subsequent_message_context(
                        workspace_path=os.getcwd(),
                        session_id=session_id,
                    )
                
                # Inject context into user message
                user_content = self.context_injector.inject(
                    message=user_content,
                    session_id=session_id,
                    config=ctx_config,
                )
                logger.debug(f"[Context] Injected {'full' if is_first_message else 'light'} context for session {session_id}")
            except Exception as e:
                logger.warning(f"[Context] Failed to inject context: {e}")
        
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
        
        # Prometheus metrics
        metrics = get_metrics() if PROMETHEUS_AVAILABLE else None
        if metrics:
            metrics.request_in_progress.inc()
        
        # Always enable prompt caching for better performance
        # Anthropic's caching is automatic: first call caches, subsequent calls use cache
        # No need to pre-warm; just always send cache_control headers
        use_caching = True
        
        # Track if this session had warm cache (for debugging)
        had_warm_cache = self._is_cache_warm(session_id)
        if had_warm_cache:
            logger.debug(f"Session {session_id} had pre-warmed cache")
        
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
                # Dynamically adjust model and Extended Thinking based on task complexity
                is_simple = is_simple_chat  # Use early detection result
                logger.info(f"[Agent] Task '{task[:30]}...' is_simple={is_simple}")
                
                # Extended Thinking requires Opus model (Sonnet doesn't support it)
                # Always use Opus for consistent UX with thinking feedback
                # Simple chats: smaller thinking budget + output for fast response
                thinking_budget = 2048 if is_simple else 4096
                max_tokens = 2048 if is_simple else 16384
                
                api_params = {
                    "model": self.model,  # Always Opus for thinking support
                    "max_tokens": max_tokens,
                    "messages": messages,
                    "thinking": {
                        "type": "enabled",
                        "budget_tokens": thinking_budget,
                    },
                }
                # Only include tools if we have any (empty array causes API error)
                if not is_simple and tools:
                    # Use cached tools when caching is enabled for better performance
                    if use_caching:
                        api_params["tools"] = self._build_cached_tools(tools)
                    else:
                        api_params["tools"] = tools
                logger.info(f"[Agent] {'Simple' if is_simple else 'Complex'} chat: {self.model}, thinking={thinking_budget}, max_tokens={max_tokens}, tools={len(tools) if not is_simple else 0}, caching={use_caching}")
                
                # Extended Thinking requires beta header
                # Combine with prompt caching header if using caching
                beta_headers = [self.THINKING_BETA]
                if use_caching:
                    beta_headers.append(self.PROMPT_CACHE_BETA)
                    api_params["system"] = self._build_cached_system(system_prompt)
                else:
                    api_params["system"] = system_prompt
                api_params["extra_headers"] = {"anthropic-beta": ",".join(beta_headers)}
                
                # Track thinking state
                is_thinking = False
                thinking_content = ""
                thinking_start_time = None
                current_block_type = None  # Track current block type
                
                # Use ASYNC streaming API for true real-time feedback
                async with self.async_client.messages.stream(**api_params) as stream:
                    async for event in stream:
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
                                    # Call thinking callback (for ChatKit integration)
                                    if on_thinking_delta and thinking_text:
                                        await on_thinking_delta(thinking_text)
                                    # Broadcast via WebSocket (for traditional UI)
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
                                    # Call streaming callback (for ChatKit integration)
                                    if on_text_delta and text_delta:
                                        logger.debug(f"[Agent] Calling on_text_delta: {text_delta[:20]}...")
                                        await on_text_delta(text_delta)
                                    # Broadcast via WebSocket (for traditional UI)
                                    if self.status_server and text_delta:
                                        await self.status_server.broadcast({
                                            "type": "content",
                                            "message_id": message_id,
                                            "content": text_delta,
                                        })
                                
                                # Handle input JSON delta (tool args)
                                elif delta_type == "input_json_delta":
                                    current_tool_args += event.delta.partial_json
                        
                        # NOTE: Do NOT handle "input_json" event separately!
                        # The SDK helper event "input_json" contains a cumulative snapshot,
                        # while "input_json_delta" in content_block_delta provides incremental parts.
                        # Handling both causes double-accumulation and corrupted JSON.
                        
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
                    
                    # Get final message for stop_reason (async)
                    response = await stream.get_final_message()
                
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
                # Use parallel execution for independent tools (non-browser tools)
                tool_results = []
                
                # Check if we can parallelize - browser tools must be sequential
                browser_tool_names = {"browser_navigate", "browser_click", "browser_type", 
                                      "browser_extract", "browser_screenshot", "browser_scroll",
                                      "browser_back", "browser_wait", "browser_send_keys"}
                has_browser_tools = any(tu["name"] in browser_tool_names for tu in tool_uses)
                can_parallelize = len(tool_uses) > 1 and not has_browser_tools
                
                if can_parallelize:
                    # Parallel execution for non-browser tools
                    logger.info(f"[Agent] Executing {len(tool_uses)} tools in parallel")
                    
                    async def execute_tool_wrapper(tool_index, tool_use):
                        """Wrapper for parallel execution with callbacks"""
                        tool_name = tool_use["name"]
                        tool_args = tool_use["input"]
                        tool_id = tool_use["id"]
                        
                        # Stream tool start
                        if on_tool_start:
                            await on_tool_start(tool_id, tool_name, tool_args)
                        if self.status_server:
                            await self.status_server.stream_tool_start(
                                message_id, tool_id, tool_name
                            )
                        
                        # Execute with timeout
                        try:
                            result = await asyncio.wait_for(
                                self._execute_with_retry(tool_name, tool_args),
                                timeout=10.0  # 10 second timeout per tool
                            )
                        except asyncio.TimeoutError:
                            from engine.tools.base import ToolResult
                            result = ToolResult(success=False, output="", error="Tool execution timed out (10s)")
                        
                        # Stream tool result
                        if on_tool_end:
                            await on_tool_end(
                                tool_id,
                                result.success,
                                result.output if result.success else result.error or ""
                            )
                        if self.status_server:
                            await self.status_server.stream_tool_result(
                                message_id, tool_id,
                                result=result.output if result.success else None,
                                error=result.error if not result.success else None,
                            )
                        
                        return tool_index, tool_use, result
                    
                    # Execute all tools in parallel
                    tasks = [execute_tool_wrapper(i, tu) for i, tu in enumerate(tool_uses)]
                    parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Process results in original order
                    for item in sorted(parallel_results, key=lambda x: x[0] if isinstance(x, tuple) else float('inf')):
                        if isinstance(item, Exception):
                            logger.error(f"Parallel tool execution error: {item}")
                            continue
                        
                        tool_index, tool_use, result = item
                        tool_name = tool_use["name"]
                        tool_args = tool_use["input"]
                        tool_id = tool_use["id"]
                        
                        # Record tool call
                        tool_calls_made.append({
                            "name": tool_name,
                            "args": tool_args,
                            "success": result.success,
                            "output": result.output if result.success else result.error,
                            "retried": getattr(result, 'retried', False),
                        })
                        
                        # Add to session history
                        if tool_name in ["move_file", "create_directory", "delete_file", "write_file", "copy_file"]:
                            add_to_session_history(session_id, {
                                "tool": tool_name,
                                "args": tool_args,
                                "success": result.success,
                                "timestamp": time.time(),
                            })
                        
                        # Format result for Claude
                        result_content = str(result.output) if result.success else f"Error: {result.error}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result_content,
                        })
                else:
                    # Sequential execution (for browser tools or single tool)
                    for tool_index, tool_use in enumerate(tool_uses):
                        tool_name = tool_use["name"]
                        tool_args = tool_use["input"]
                        tool_id = tool_use["id"]
                        
                        # Stream tool start with args
                        if on_tool_start:
                            await on_tool_start(tool_id, tool_name, tool_args)
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
                        if on_tool_end:
                            await on_tool_end(
                                tool_id, 
                                result.success, 
                                result.output if result.success else result.error or ""
                            )
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
                
                # Record Prometheus metrics for error
                if metrics:
                    elapsed = time.time() - task_start_time
                    metrics.request_in_progress.dec()
                    metrics.record_request(
                        task_type=task_type_str,
                        success=False,
                        duration_seconds=elapsed,
                        iterations=iteration,
                    )
                    metrics.record_error(type(e).__name__)
                
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
        
        # Record Prometheus metrics
        if metrics:
            elapsed = time.time() - task_start_time
            metrics.request_in_progress.dec()
            metrics.record_request(
                task_type=task_type_str,
                success=True,
                duration_seconds=elapsed,
                iterations=iteration,
            )
        
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
