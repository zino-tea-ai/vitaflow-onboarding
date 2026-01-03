# -*- coding: utf-8 -*-
"""
NogicOS Hive Server - V2 Architecture

Simplified HTTP + WebSocket API using Pure ReAct Agent.

Architecture:
    HTTP (8080)          WebSocket (8765)
        |                     |
        v                     v
    /v2/execute  ───────►  broadcast status
    /v2/tools                 |
    /health                   v
                         Electron UI

Usage:
    python hive_server.py
"""

import warnings
import asyncio
import os
import sys
import json
import time
import logging
from typing import Optional
from contextlib import asynccontextmanager

# Filter known deprecation warnings
warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality isn't compatible")
warnings.filterwarnings("ignore", message="ForwardRef._evaluate is a private API")
warnings.filterwarnings("ignore", message="websockets.server.WebSocketServerProtocol is deprecated")
warnings.filterwarnings("ignore", message="websockets.legacy is deprecated")

# Ensure UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# Setup logging
from engine.observability import setup_logging, get_logger
setup_logging(level="INFO")
logger = get_logger("hive_server")

# FastAPI imports
try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import Response, StreamingResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    logger.error("FastAPI not installed. Run: pip install fastapi uvicorn")
    sys.exit(1)

# ChatKit Server (optional - graceful degradation if not available)
try:
    from chatkit.server import StreamingResult
    from engine.server.chatkit_server import create_chatkit_server, NogicOSChatServer
    CHATKIT_AVAILABLE = True
except ImportError:
    CHATKIT_AVAILABLE = False
    StreamingResult = None
    create_chatkit_server = None
    NogicOSChatServer = None
    logger.warning("ChatKit SDK not available. Install with: pip install openai-chatkit")

# V2 imports
from engine.server.websocket import StatusServer
from engine.agent.react_agent import ReActAgent
from engine.tools import create_full_registry
from engine.watchdog import start_watchdog, get_watchdog, ConnectionState
from engine.knowledge.store import get_session_store


# ============================================================================
# Request/Response Models
# ============================================================================

class ExecuteRequest(BaseModel):
    """Task execution request"""
    task: Optional[str] = None      # New field name (preferred)
    message: Optional[str] = None   # Legacy field name (alias)
    session_id: str = "default"
    max_steps: int = 20
    mode: str = "agent"             # Agent mode: "agent", "ask", "plan"
    confirmed_plan: Optional[dict] = None  # Confirmed plan for Plan mode execution
    
    @property
    def task_content(self) -> str:
        """Get the task content, supporting both 'task' and 'message' fields"""
        return self.task or self.message or ""


class ExecuteResponse(BaseModel):
    """Task execution response"""
    success: bool
    response: str
    session_id: str
    time_seconds: float
    error: Optional[str] = None


class StatusResponse(BaseModel):
    """Server status response"""
    status: str
    version: str
    engine_ready: bool


class StatsResponse(BaseModel):
    """Server statistics"""
    tasks_executed: int
    tasks_succeeded: int
    tasks_failed: int
    uptime_seconds: float


# ============================================================================
# Engine - Simplified V2
# ============================================================================

class NogicEngine:
    """Simplified engine for V2 architecture"""
    
    def __init__(self):
        self.status_server: Optional[StatusServer] = None
        self.chatkit_server: Optional["NogicOSChatServer"] = None  # ChatKit 服务器
        self.agent: Optional[ReActAgent] = None  # Reusable agent instance
        self._executing = False
        self._current_task: Optional[str] = None
        self._stats = {
            "executed": 0,
            "succeeded": 0,
            "failed": 0,
        }
        self._start_time = time.time()
    
    async def start_websocket(self):
        """Start WebSocket server"""
        self.status_server = StatusServer(port=8765)
        await self.status_server.start()
        logger.info("WebSocket server started on port 8765")
        
        # Initialize reusable ReAct Agent (avoids 1-2s init overhead per request)
        logger.info("Initializing ReAct Agent...")
        init_start = time.time()
        self.agent = ReActAgent(
            status_server=self.status_server,
            max_iterations=20,
        )
        logger.info(f"ReAct Agent initialized in {time.time() - init_start:.2f}s")
        
        # 初始化 ChatKit 服务器
        if CHATKIT_AVAILABLE and create_chatkit_server:
            self.chatkit_server = create_chatkit_server(status_server=self.status_server)
            if self.chatkit_server:
                logger.info("ChatKit server initialized")
    
    async def stop_websocket(self):
        """Stop WebSocket server"""
        if self.status_server:
            await self.status_server.stop()
            logger.info("WebSocket server stopped")
    
    async def execute(self, request: ExecuteRequest) -> ExecuteResponse:
        """Execute task using ReAct Agent with mode support"""
        if self._executing:
            raise HTTPException(status_code=429, detail="Another task is executing")
        
        self._executing = True
        task_content = request.task_content
        self._current_task = task_content[:100]
        start_time = time.time()
        
        # Parse mode
        from engine.agent.modes import AgentMode
        try:
            mode = AgentMode(request.mode)
        except ValueError:
            mode = AgentMode.AGENT
        
        logger.info(f"[Engine] Executing in {mode.value} mode: {task_content[:50]}...")
        
        # Parse confirmed plan if provided (for Plan mode execution)
        confirmed_plan = None
        if request.confirmed_plan and mode == AgentMode.AGENT:
            # User confirmed a plan, execute it
            from engine.agent.planner import Plan, PlanStep
            try:
                plan_data = request.confirmed_plan
                steps = [s.get("description", "") for s in plan_data.get("steps", [])]
                confirmed_plan = Plan(
                    steps=steps,
                    detailed_steps=[
                        PlanStep(
                            description=s.get("description", ""),
                            suggested_tool=s.get("tool"),
                        )
                        for s in plan_data.get("steps", [])
                    ],
                )
                logger.info(f"[Engine] Executing confirmed plan with {len(steps)} steps")
            except Exception as e:
                logger.warning(f"[Engine] Failed to parse confirmed plan: {e}")
        
        try:
            # Create ReAct Agent
            agent = ReActAgent(
                status_server=self.status_server,
                max_iterations=request.max_steps,
            )
            
            # Execute based on mode
            if confirmed_plan:
                # Execute confirmed plan
                result = await agent.run(
                    task=task_content,
                    session_id=request.session_id,
                    mode=AgentMode.AGENT,
                    confirmed_plan=confirmed_plan,
                )
            elif mode == AgentMode.PLAN:
                # Plan mode: generate plan without executing
                result = await agent.run(
                    task=task_content,
                    session_id=request.session_id,
                    mode=mode,
                )
            elif mode == AgentMode.ASK:
                # Ask mode: read-only exploration
                result = await agent.run(
                    task=task_content,
                    session_id=request.session_id,
                    mode=mode,
                )
            else:
                # Agent mode: full execution
                result = await agent.run_with_planning(
                    task=task_content,
                    session_id=request.session_id,
                )
            
            elapsed = time.time() - start_time
            
            # Update stats
            self._stats["executed"] += 1
            if result.success:
                self._stats["succeeded"] += 1
            else:
                self._stats["failed"] += 1
            
            return ExecuteResponse(
                success=result.success,
                response=result.response,
                session_id=request.session_id,
                time_seconds=elapsed,
                error=result.error,
            )
            
        except Exception as e:
            logger.error(f"Execution error: {e}", exc_info=True)
            self._stats["executed"] += 1
            self._stats["failed"] += 1
            return ExecuteResponse(
                success=False,
                response="",
                session_id=request.session_id,
                time_seconds=time.time() - start_time,
                error=str(e),
            )
        finally:
            self._executing = False
            self._current_task = None
    
    def get_stats(self) -> StatsResponse:
        """Get server statistics"""
        return StatsResponse(
            tasks_executed=self._stats["executed"],
            tasks_succeeded=self._stats["succeeded"],
            tasks_failed=self._stats["failed"],
            uptime_seconds=time.time() - self._start_time,
        )


# Global engine instance
engine: Optional[NogicEngine] = None
server_start_time = time.time()


# ============================================================================
# FastAPI App
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan manager"""
    global engine, server_start_time
    
    logger.info("=" * 60)
    logger.info("NogicOS Hive Server V2 Starting...")
    logger.info("=" * 60)
    
    server_start_time = time.time()
    
    # Initialize engine
    engine = NogicEngine()
    await engine.start_websocket()
    
    # Start watchdog for connection monitoring
    def on_state_change(status):
        logger.info(f"[Watchdog] State change: WS={status.websocket.value}, API={status.api.value}")
    
    watchdog = await start_watchdog(
        ws_server=engine.status_server,
        on_state_change=on_state_change,
    )
    logger.info("Watchdog started")
    
    logger.info("Server ready!")
    logger.info(f"  HTTP: http://localhost:8080")
    logger.info(f"  WebSocket: ws://localhost:8765")
    logger.info("=" * 60)
    
    yield
    
    # Cleanup
    logger.info("Shutting down...")
    
    # Stop watchdog
    watchdog = get_watchdog()
    if watchdog:
        await watchdog.stop()
    
    if engine:
        await engine.stop_websocket()
    logger.info("Shutdown complete")


app = FastAPI(
    title="NogicOS Hive Server",
    description="AI Agent execution server with ReAct architecture",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_model=StatusResponse)
async def root():
    """Server status"""
    return StatusResponse(
        status="running",
        version="2.0.0",
        engine_ready=engine is not None,
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get server statistics"""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    return engine.get_stats()


@app.post("/v2/execute", response_model=ExecuteResponse)
@app.post("/execute", response_model=ExecuteResponse)  # Legacy route alias
async def execute_v2(request: ExecuteRequest):
    """
    Execute task using Pure ReAct Agent.
    
    Features:
    - Pure ReAct loop (no pre-planning)
    - Autonomous decision-making
    - Dynamic tool selection
    - Streaming via WebSocket
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    return await engine.execute(request)


@app.get("/v2/tools")
async def list_v2_tools():
    """List all available tools"""
    registry = create_full_registry()
    tools = registry.to_anthropic_format()
    
    return {
        "count": len(tools),
        "tools": tools,
    }


class QuickSearchRequest(BaseModel):
    """Quick search request - bypasses Agent for speed"""
    query: str
    max_results: int = 5


@app.post("/v2/quick-search")
async def quick_search(request: QuickSearchRequest):
    """
    快速搜索 - 直接调用 Tavily API，跳过 Agent 流程
    
    速度: 1-3 秒 (vs Agent 的 20-30 秒)
    用途: 简单搜索查询
    """
    import aiohttp
    import time
    
    start = time.time()
    
    # Get API key
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        try:
            from api_keys import TAVILY_API_KEY
            api_key = TAVILY_API_KEY
        except ImportError:
            pass
    
    if not api_key:
        raise HTTPException(status_code=500, detail="TAVILY_API_KEY not configured")
    
    # Direct Tavily API call
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": request.query,
                "max_results": request.max_results,
                "include_answer": True,
                "include_raw_content": False,
            }
        ) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail="Tavily API error")
            data = await resp.json()
    
    elapsed = time.time() - start
    
    return {
        "success": True,
        "query": request.query,
        "answer": data.get("answer", ""),
        "results": [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")[:200],
            }
            for r in data.get("results", [])
        ],
        "time_seconds": round(elapsed, 2),
    }


# =============================================================================
# Smart Search - Cursor 风格 (Query优化 + 搜索 + 结果整合)
# =============================================================================

class SmartSearchRequest(BaseModel):
    """Smart search request - Cursor style"""
    query: str
    max_results: int = 5
    force_search: bool = False  # 跳过判断，强制搜索


@app.post("/v2/smart-search")
async def smart_search_endpoint(request: SmartSearchRequest):
    """
    智能搜索 - Cursor 风格
    
    特性:
    1. 调用精确度 - 自动判断是否需要搜索
    2. Query 优化 - LLM 优化搜索词
    3. 结果整合 - LLM 整合并引用来源
    
    参数:
    - force_search: True 跳过判断强制搜索
    """
    from engine.tools.smart_search import smart_search
    
    result = await smart_search(request.query, request.max_results, request.force_search)
    return result


class WarmCacheRequest(BaseModel):
    """Cache warming request"""
    session_id: str = "default"


@app.post("/v2/warm-cache")
async def warm_cache(request: WarmCacheRequest):
    """
    Pre-warm the prompt cache for faster TTFT.
    
    Call this when user focuses on input field.
    Implements Speculative Prompt Caching from Anthropic Cookbook.
    Can reduce TTFT by 90%+.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    # Create a temporary agent to warm the cache
    agent = ReActAgent(
        status_server=engine.status_server,
    )
    
    success = await agent.warm_cache(request.session_id)
    
    return {
        "success": success,
        "session_id": request.session_id,
        "message": "Cache warmed" if success else "Cache warming failed",
    }


@app.get("/read_file")
async def read_file(path: str):
    """Read file content (for frontend)"""
    try:
        # Security: only allow reading from workspace
        workspace = os.path.dirname(__file__)
        full_path = os.path.normpath(os.path.join(workspace, path))
        
        if not full_path.startswith(workspace):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {"path": path, "content": content}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Session Persistence Endpoints
# ============================================================================

class SaveSessionRequest(BaseModel):
    """Save session request"""
    session_id: str
    history: list
    preferences: dict = {}
    title: Optional[str] = None


@app.post("/v2/sessions/save")
async def save_session(request: SaveSessionRequest):
    """
    Save session history and preferences for persistence.
    
    This enables cross-session memory - users can resume previous sessions.
    """
    try:
        store = get_session_store()
        store.save_session(
            session_id=request.session_id,
            history=request.history,
            preferences=request.preferences,
            title=request.title,
        )
        return {
            "success": True,
            "session_id": request.session_id,
            "message": "Session saved",
        }
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/sessions/{session_id}")
async def load_session(session_id: str):
    """
    Load a saved session by ID.
    
    Returns session history, preferences, and metadata.
    """
    try:
        store = get_session_store()
        session = store.load_session(session_id)
        return session
    except Exception as e:
        logger.error(f"Failed to load session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/sessions")
async def list_sessions(limit: int = 20, offset: int = 0):
    """
    List recent sessions.
    
    Returns session summaries without full history for performance.
    """
    try:
        store = get_session_store()
        sessions = store.list_sessions(limit=limit, offset=offset)
        stats = store.get_session_stats()
        
        return {
            "sessions": sessions,
            "total": stats["session_count"],
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v2/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a saved session"""
    try:
        store = get_session_store()
        deleted = store.delete_session(session_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"success": True, "message": "Session deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Memory Management Endpoints (Long-term Semantic Memory)
# ============================================================================

# Import memory store
try:
    from engine.knowledge.store import get_memory_store
    MEMORY_STORE_AVAILABLE = True
except ImportError:
    MEMORY_STORE_AVAILABLE = False


class AddMemoryRequest(BaseModel):
    """Add memory request"""
    subject: str
    predicate: str
    object: str
    session_id: str = "default"
    memory_type: str = "fact"
    importance: str = "medium"
    context: Optional[str] = None


class SearchMemoryRequest(BaseModel):
    """Search memory request"""
    query: str
    session_id: str = "default"
    limit: int = 5
    threshold: float = 0.5


@app.post("/v2/memories/add")
async def add_memory(request: AddMemoryRequest):
    """
    Add a new memory to long-term storage.
    
    Memories are stored as subject-predicate-object triples
    with optional importance scoring and context.
    
    Example:
        {"subject": "user", "predicate": "prefers", "object": "dark mode"}
    """
    if not MEMORY_STORE_AVAILABLE:
        raise HTTPException(status_code=501, detail="Memory store not available")
    
    try:
        store = get_memory_store()
        memory_id = await store.add_memory(
            subject=request.subject,
            predicate=request.predicate,
            obj=request.object,
            session_id=request.session_id,
            memory_type=request.memory_type,
            importance=request.importance,
            context=request.context,
        )
        
        return {
            "success": True,
            "memory_id": memory_id,
            "message": f"Memory added: {request.subject} {request.predicate} {request.object}",
        }
    except Exception as e:
        logger.error(f"Failed to add memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v2/memories/search")
async def search_memories(request: SearchMemoryRequest):
    """
    Semantic search for relevant memories.
    
    Uses embedding similarity to find memories related to the query.
    Falls back to keyword search if embeddings are unavailable.
    """
    if not MEMORY_STORE_AVAILABLE:
        raise HTTPException(status_code=501, detail="Memory store not available")
    
    try:
        store = get_memory_store()
        results = await store.search_memories(
            query=request.query,
            session_id=request.session_id,
            limit=request.limit,
            threshold=request.threshold,
        )
        
        return {
            "query": request.query,
            "count": len(results),
            "memories": results,
        }
    except Exception as e:
        logger.error(f"Failed to search memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/memories/{session_id}")
async def list_memories(
    session_id: str,
    memory_type: Optional[str] = None,
    importance: Optional[str] = None,
    limit: int = 50,
):
    """
    List memories for a session.
    
    Optional filters:
    - memory_type: fact, preference, event, relationship, instruction
    - importance: high, medium, low
    """
    if not MEMORY_STORE_AVAILABLE:
        raise HTTPException(status_code=501, detail="Memory store not available")
    
    try:
        store = get_memory_store()
        memories = store.list_memories(
            session_id=session_id,
            memory_type=memory_type,
            importance=importance,
            limit=limit,
        )
        
        return {
            "session_id": session_id,
            "count": len(memories),
            "memories": memories,
        }
    except Exception as e:
        logger.error(f"Failed to list memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v2/memories/{memory_id}")
async def delete_memory(memory_id: str):
    """
    Delete a memory (soft delete - marks as inactive).
    
    The memory is retained in the database but excluded from searches.
    """
    if not MEMORY_STORE_AVAILABLE:
        raise HTTPException(status_code=501, detail="Memory store not available")
    
    try:
        store = get_memory_store()
        deleted = store.delete_memory(memory_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return {"success": True, "message": "Memory deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/memories/stats")
async def memory_stats():
    """
    Get memory store statistics.
    
    Returns counts of active memories, embeddings, and breakdown by importance.
    """
    if not MEMORY_STORE_AVAILABLE:
        raise HTTPException(status_code=501, detail="Memory store not available")
    
    try:
        store = get_memory_store()
        stats = store.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Vercel AI SDK Chat Endpoint
# ============================================================================

class ChatRequest(BaseModel):
    """Vercel AI SDK chat request"""
    messages: Optional[list] = None  # Traditional format
    text: Optional[str] = None  # New sendMessage format
    session_id: str = "default"
    
    class Config:
        extra = "allow"  # Allow extra fields like temperature, etc.


async def generate_ai_sdk_stream(task: str, session_id: str, conversation_history: list = None):
    """
    Generate SSE stream compatible with Vercel AI SDK 5.0 Data Stream Protocol.
    
    Stream format (SSE with JSON):
    - Start: data: {"type":"start","messageId":"..."}
    - Text: data: {"type":"text-start/delta/end","id":"...","delta":"..."}
    - Reasoning: data: {"type":"reasoning-start/delta/end","id":"...","delta":"..."}
    - Finish: data: {"type":"finish","finishReason":"stop"}
    
    Note: Requires x-vercel-ai-ui-message-stream: v1 header for custom backends.
    
    Args:
        task: Current user message
        session_id: Session identifier
        conversation_history: Previous messages for context (optional)
    """
    import uuid
    
    # Reuse global agent instance (initialized once at server startup)
    # This avoids 1-2s initialization overhead per request
    agent = engine.agent if engine else ReActAgent(
        status_server=None,
        max_iterations=20,
    )
    
    message_id = str(uuid.uuid4())
    text_id = f"text_{uuid.uuid4().hex[:8]}"
    reasoning_id = f"reasoning_{uuid.uuid4().hex[:8]}"
    text_started = False
    reasoning_started = False
    
    # Helper to format SSE
    def sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"
    
    # Use queue to collect events from callbacks
    event_queue: asyncio.Queue = asyncio.Queue()
    agent_done = asyncio.Event()
    
    async def thinking_callback(delta: str):
        nonlocal reasoning_started
        if not reasoning_started:
            await event_queue.put(sse({"type": "reasoning-start", "id": reasoning_id}))
            reasoning_started = True
        await event_queue.put(sse({"type": "reasoning-delta", "id": reasoning_id, "delta": delta}))
    
    async def text_callback(delta: str):
        nonlocal text_started
        if not text_started:
            await event_queue.put(sse({"type": "text-start", "id": text_id}))
            text_started = True
        await event_queue.put(sse({"type": "text-delta", "id": text_id, "delta": delta}))
    
    # Track tool names for output events
    tool_names: dict = {}
    
    async def tool_start_callback(tool_id: str, tool_name: str, tool_args: dict):
        tool_names[tool_id] = tool_name
        # AI SDK Data Stream Protocol: tool-input-start -> tool-input-available -> (execution) -> tool-output-available
        await event_queue.put(sse({
            "type": "tool-input-start",
            "toolCallId": tool_id,
            "toolName": tool_name,
        }))
        await event_queue.put(sse({
            "type": "tool-input-available",
            "toolCallId": tool_id,
            "toolName": tool_name,
            "input": tool_args,
        }))
    
    async def tool_end_callback(tool_id: str, success: bool, result: str):
        if success:
            await event_queue.put(sse({
                "type": "tool-output-available",
                "toolCallId": tool_id,
                "output": result,
            }))
        else:
            await event_queue.put(sse({
                "type": "tool-output-error",
                "toolCallId": tool_id,
                "errorText": result,
            }))
    
    async def run_agent():
        try:
            # Build context from conversation history
            context = None
            if conversation_history:
                # Format previous messages as context
                context_parts = []
                for msg in conversation_history[:-1]:  # Exclude current message
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        # Handle parts-based format
                        content = " ".join(
                            p.get("text", "") for p in content 
                            if isinstance(p, dict) and p.get("type") == "text"
                        )
                    if role == "user":
                        context_parts.append(f"用户: {content}")
                    elif role == "assistant":
                        # Truncate long assistant responses
                        if len(content) > 500:
                            content = content[:500] + "..."
                        context_parts.append(f"助手: {content}")
                
                if context_parts:
                    context = "## 之前的对话:\n" + "\n".join(context_parts[-6:])  # Keep last 3 turns (6 messages)
                    logger.info(f"[Chat] Injecting {len(context_parts)} previous messages as context")
            
            result = await agent.run(
                task=task,
                session_id=session_id,
                context=context,  # Pass conversation history as context
                on_text_delta=text_callback,
                on_thinking_delta=thinking_callback,
                on_tool_start=tool_start_callback,
                on_tool_end=tool_end_callback,
            )
            # Send text-end if text was started
            if text_started:
                await event_queue.put(sse({"type": "text-end", "id": text_id}))
            # Send reasoning-end if reasoning was started
            if reasoning_started:
                await event_queue.put(sse({"type": "reasoning-end", "id": reasoning_id}))
            # Send finish message
            await event_queue.put(sse({
                "type": "finish",
                "finishReason": "stop" if result.success else "error",
            }))
        except Exception as e:
            logger.error(f"Agent error: {e}")
            await event_queue.put(sse({"type": "finish", "finishReason": "error"}))
        finally:
            agent_done.set()
    
    # Start agent in background
    agent_task = asyncio.create_task(run_agent())
    
    # Send stream start
    yield sse({"type": "start", "messageId": message_id})
    
    try:
        while not agent_done.is_set() or not event_queue.empty():
            try:
                # Reduced timeout for faster response (was 0.1s, now 0.01s)
                event = await asyncio.wait_for(event_queue.get(), timeout=0.01)
                yield event
            except asyncio.TimeoutError:
                continue
    finally:
        if not agent_task.done():
            agent_task.cancel()


@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """
    Vercel AI SDK compatible chat endpoint.
    
    Accepts multiple formats:
    1. New format: { text: "message" }
    2. Traditional: { messages: [{ role: "user", content: "..." }] }
    
    Returns SSE stream with:
    - Text deltas (type 0)
    - Reasoning/thinking deltas (type g, h)
    - Tool calls (type 9, a)
    - Finish signal (type d)
    
    Frontend uses @ai-sdk/react useChat hook to consume this stream.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    try:
        body = await request.json()
        logger.info(f"[Chat] Received request: {json.dumps(body, ensure_ascii=False)[:200]}...")
    except Exception as e:
        logger.error(f"[Chat] Failed to parse JSON: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    
    # Extract user message and conversation history
    user_message = ""
    conversation_history = []
    session_id = body.get("session_id", "default")
    
    # Format 1: New Vercel AI SDK format { text: "..." }
    if "text" in body and body["text"]:
        user_message = body["text"]
    
    # Format 2: Messages array (traditional or new parts-based)
    elif "messages" in body and body["messages"]:
        # Keep full conversation history for context
        conversation_history = body["messages"]
        
        # Extract latest user message
        for msg in reversed(body["messages"]):
            if isinstance(msg, dict) and msg.get("role") == "user":
                # New AI SDK format: parts array
                if "parts" in msg and msg["parts"]:
                    for part in msg["parts"]:
                        if isinstance(part, dict) and part.get("type") == "text":
                            user_message = part.get("text", "")
                            break
                    if user_message:
                        break
                
                # Traditional format: content field
                content = msg.get("content", "")
                if isinstance(content, str) and content:
                    user_message = content
                    break
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            user_message = part.get("text", "")
                            break
                    if user_message:
                        break
    
    if not user_message:
        logger.warning(f"[Chat] No user message found in request: {body}")
        raise HTTPException(status_code=400, detail="No user message found")
    
    # Log context info
    if conversation_history:
        logger.info(f"[Chat] Processing: {user_message[:100]}... (with {len(conversation_history)} history messages)")
    else:
        logger.info(f"[Chat] Processing: {user_message[:100]}...")
    
    return StreamingResponse(
        generate_ai_sdk_stream(user_message, session_id, conversation_history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "x-vercel-ai-ui-message-stream": "v1",  # Required for AI SDK 5.0
        }
    )


# ============================================================================
# ChatKit Endpoint (OpenAI ChatKit Protocol)
# ============================================================================

@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    """
    ChatKit 协议端点 - 支持 OpenAI ChatKit UI 框架。
    
    此端点实现完整的 ChatKit 服务器协议，支持：
    - 流式响应
    - Widget 渲染
    - 客户端工具
    - 会话管理
    
    前端使用 @openai/chatkit-react 连接此端点。
    """
    if not CHATKIT_AVAILABLE:
        return JSONResponse(
            status_code=501,
            content={
                "error": "ChatKit SDK not available",
                "detail": "Install with: pip install openai-chatkit",
            }
        )
    
    if not engine or not engine.chatkit_server:
        return JSONResponse(
            status_code=503,
            content={
                "error": "ChatKit server not ready",
                "detail": "Engine not initialized",
            }
        )
    
    try:
        payload = await request.body()
        result = await engine.chatkit_server.process(payload, {"request": request})
        
        if isinstance(result, StreamingResult):
            # SSE 响应需要禁用缓冲才能实现真正的流式效果
            return StreamingResponse(
                result, 
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
                }
            )
        
        if hasattr(result, "json"):
            return Response(content=result.json, media_type="application/json")
        
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"ChatKit endpoint error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
    except:
        memory_mb = 0
    
    uptime = time.time() - server_start_time
    
    status = "healthy"
    if engine is None:
        status = "unhealthy"
    elif engine._executing:
        status = "busy"
    elif memory_mb > 1024:
        status = "degraded"
    
    # Include watchdog status
    watchdog = get_watchdog()
    watchdog_status = None
    if watchdog:
        watchdog_status = {
            "websocket": watchdog.status.websocket.value,
            "api": watchdog.status.api.value,
            "recovery_attempts": watchdog.status.recovery_attempts,
            "is_healthy": watchdog.is_healthy,
        }
    
    return {
        "status": status,
        "engine": engine is not None,
        "executing": engine._executing if engine else False,
        "current_task": engine._current_task[:50] if engine and engine._current_task else None,
        "uptime_seconds": round(uptime, 1),
        "memory_mb": round(memory_mb, 1),
        "watchdog": watchdog_status,
    }


# ============================================================================
# Main Entry
# ============================================================================

if __name__ == "__main__":
    # Load API keys
    try:
        from api_keys import setup_env
        setup_env()
        logger.info("API keys loaded from api_keys.py")
    except ImportError:
        logger.info("Using environment variables for API keys")
    
    # Run server
    uvicorn.run(
        "hive_server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )
