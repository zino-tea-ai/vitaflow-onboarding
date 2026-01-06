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
import aiohttp
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
        self._agent_lock = asyncio.Lock()  # Lock for agent access
        self._executing = False
        self._current_task: Optional[str] = None
        self._stats = {
            "executed": 0,
            "succeeded": 0,
            "failed": 0,
        }
        self._start_time = time.time()

    async def get_agent(self) -> ReActAgent:
        """Get agent instance with lock protection for thread safety"""
        async with self._agent_lock:
            if self.agent is None:
                self.agent = ReActAgent(
                    status_server=self.status_server,
                    max_iterations=20,
                )
            return self.agent

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
        # [P0-5 FIX] Use lock for thread-safe execution check with guaranteed cleanup
        async with self._agent_lock:
            if self._executing:
                raise HTTPException(status_code=429, detail="Another task is executing")
            self._executing = True

        task_content = request.task_content
        self._current_task = task_content[:100]
        start_time = time.time()

        # [P0-5 FIX] Wrap everything in try-finally to ensure state cleanup
        try:
            return await self._execute_task(request, task_content, start_time)
        finally:
            # [P0-5 FIX] Always reset execution state, even on unexpected errors
            self._executing = False
            self._current_task = None

    async def _execute_task(self, request: ExecuteRequest, task_content: str, start_time: float) -> ExecuteResponse:
        """Internal task execution logic - separated for clean error handling"""
        
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
            # [P1 FIX] Reuse existing agent instance instead of creating new one each time
            # This saves 1-2s initialization overhead per request
            agent = await self.get_agent()
            # Update max_iterations if different from default
            if agent.max_iterations != request.max_steps:
                agent.max_iterations = request.max_steps

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
        # [P0-5 FIX] finally block removed - cleanup now handled in outer execute() method
    
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

# CORS - Security: Limit allowed origins
# In production, set ALLOWED_ORIGINS env var
# Note: file:// removed for security - use proper Electron protocol handling
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").split(",") if os.environ.get("ALLOWED_ORIGINS") else [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:5174",   # Vite alternative port
    "http://localhost:5175",   # Vite alternative port
    "http://localhost:3000",   # React dev server
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://localhost:8080",   # Local server
    "http://127.0.0.1:8080",   # Local server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Session-ID"],
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
async def quick_search(request: QuickSearchRequest, req: Request):
    """
    快速搜索 - 直接调用 Tavily API，跳过 Agent 流程

    速度: 1-3 秒 (vs Agent 的 20-30 秒)
    用途: 简单搜索查询

    Security: Requires authentication via Authorization header or X-API-Key
    """
    # Security: Verify authentication
    auth_header = req.headers.get("Authorization", "")
    api_key_header = req.headers.get("X-API-Key", "")
    expected_key = os.environ.get("NOGICOS_API_KEY", "")

    if expected_key:
        is_valid = (
            auth_header == f"Bearer {expected_key}" or
            api_key_header == expected_key
        )
        if not is_valid:
            raise HTTPException(status_code=401, detail="Unauthorized")

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
    
    # [P1 FIX] Direct Tavily API call with enhanced error handling and timeout
    try:
        timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": request.query[:500],  # [P1 FIX] Limit query length
                    "max_results": min(request.max_results, 10),  # [P1 FIX] Limit results
                    "include_answer": True,
                    "include_raw_content": False,
                }
            ) as resp:
                if resp.status != 200:
                    # [P1 FIX] Log error details but don't expose to client
                    error_text = await resp.text()
                    logger.error(f"[Tavily] API error {resp.status}: {error_text[:200]}")
                    raise HTTPException(status_code=502, detail="External search service error")
                data = await resp.json()
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Search request timeout")
    except aiohttp.ClientError as e:
        logger.error(f"[Tavily] Client error: {e}")
        raise HTTPException(status_code=502, detail="Search service unavailable")
    
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
        # [P0-4 FIX] Enhanced path validation

        # 1. Input validation - reject obviously malicious inputs early
        # [P0 FIX Round 2] Block absolute paths including Windows drive letters
        if not path or '..' in path or path.startswith('/') or path.startswith('\\'):
            logger.warning(f"[Security] Blocked malicious path input: {path[:50]}")
            raise HTTPException(status_code=400, detail="Invalid path")

        # [P0 FIX Round 2] Block Windows absolute paths (C:\, D:\, etc.)
        if len(path) >= 2 and path[1] == ':':
            logger.warning(f"[Security] Blocked Windows absolute path: {path[:50]}")
            raise HTTPException(status_code=400, detail="Invalid path")

        # 2. Normalize workspace path
        workspace = os.path.realpath(os.path.dirname(__file__))

        # 3. Safely join and resolve the full path
        requested_path = os.path.normpath(path)
        full_path = os.path.realpath(os.path.join(workspace, requested_path))

        # 4. [P0-4 FIX] Use commonpath for robust path containment check
        # This works correctly on both Windows and Unix
        try:
            common = os.path.commonpath([workspace, full_path])
            if common != workspace:
                logger.warning(f"[Security] Path traversal blocked: {path} -> {full_path}")
                raise HTTPException(status_code=403, detail="Access denied")
        except ValueError:
            # Different drives on Windows
            logger.warning(f"[Security] Cross-drive access blocked: {path}")
            raise HTTPException(status_code=403, detail="Access denied")

        # 5. [P0-4 FIX] Check for symbolic links (prevent symlink attacks)
        if os.path.islink(full_path):
            logger.warning(f"[Security] Symbolic link access blocked: {full_path}")
            raise HTTPException(status_code=403, detail="Symbolic links not allowed")

        # 6. [P0-4 FIX] Block sensitive file patterns (case-insensitive)
        path_lower = full_path.lower()
        sensitive_patterns = [
            '.env', '.ssh', 'credentials', 'secrets', '.git/config',
            'api_keys', 'password', 'token', '.npmrc', '.pypirc',
            'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519',
            '.aws/credentials', '.azure', '.kube/config',
        ]
        for pattern in sensitive_patterns:
            if pattern in path_lower:
                logger.warning(f"[Security] Blocked access to sensitive file: {path}")
                raise HTTPException(status_code=403, detail="Access denied to sensitive file")

        # 7. Check file existence and type
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="File not found")

        if not os.path.isfile(full_path):
            raise HTTPException(status_code=400, detail="Not a file")

        # 8. [P0-4 FIX] File size limit (prevent DoS)
        file_size = os.path.getsize(full_path)
        max_file_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_file_size:
            raise HTTPException(status_code=413, detail="File too large")

        # 9. Read file safely
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return {"path": requested_path, "content": content}

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not text/UTF-8")
    except Exception as e:
        logger.error(f"[Security] File read error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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

    model_config = {"extra": "allow"}  # Pydantic v2: Allow extra fields like temperature


async def generate_ai_sdk_stream(
    task: str, 
    session_id: str, 
    conversation_history: list = None,
    file_context: dict = None,  # NEW: Current file context
):
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
        file_context: Current file context from IDE (optional)
            {
                "path": "path/to/file.py",
                "content": "file content...",
                "selected": "selected code...",
                "cursorLine": 42,
                "cursorColumn": 10,
                "visibleRange": [30, 60]
            }
    """
    import uuid

    # Reuse global agent instance with lock protection
    # This avoids 1-2s initialization overhead per request
    if engine:
        agent = await engine.get_agent()
    else:
        agent = ReActAgent(
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
    
    # 【修复 #8】限制 event_queue 大小防止内存爆炸
    event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
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
            
            # Build file context section (Cursor-style auto-injection)
            if file_context:
                file_context_parts = []
                
                if file_context.get("path"):
                    file_context_parts.append(f"当前文件: {file_context['path']}")
                
                if file_context.get("cursorLine"):
                    col = file_context.get("cursorColumn", "")
                    col_str = f":{col}" if col else ""
                    file_context_parts.append(f"光标位置: 第 {file_context['cursorLine']} 行{col_str}")
                
                if file_context.get("selected"):
                    file_context_parts.append(f"\n--- 选中代码 ---\n{file_context['selected']}\n--- 选中结束 ---")
                elif file_context.get("content"):
                    content = file_context["content"]
                    lines = content.split('\n')
                    if len(lines) <= 50:
                        # Small file, include all
                        file_context_parts.append(f"\n--- 文件内容 ---\n{content}\n--- 文件结束 ---")
                    elif file_context.get("cursorLine"):
                        # Large file, show context around cursor
                        cursor_line = file_context["cursorLine"]
                        start = max(0, cursor_line - 15)
                        end = min(len(lines), cursor_line + 15)
                        context_lines = lines[start:end]
                        numbered = [f"{i+start+1:4d}|{line}" for i, line in enumerate(context_lines)]
                        file_context_parts.append(f"\n--- 光标附近代码 (行 {start+1}-{end}) ---\n" + "\n".join(numbered) + "\n--- 代码结束 ---")
                
                if file_context_parts:
                    file_context_str = "\n".join(file_context_parts)
                    context = f"## 当前文件上下文:\n{file_context_str}\n\n" + (context or "")
                    logger.info(f"[Chat] Injecting file context: {file_context.get('path', 'unknown')}")
            
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
    
    # 【修复 #9】Start agent in background with exception handling
    agent_task = asyncio.create_task(run_agent())
    agent_task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.exception() else None)
    
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
    
    # Extract file context (Cursor-style auto-injection from IDE)
    # Frontend can send: { fileContext: { path, content, selected, cursorLine, cursorColumn, visibleRange } }
    file_context = body.get("fileContext") or body.get("file_context")
    
    # Log context info
    if file_context:
        logger.info(f"[Chat] Processing: {user_message[:100]}... (file: {file_context.get('path', 'unknown')})")
    elif conversation_history:
        logger.info(f"[Chat] Processing: {user_message[:100]}... (with {len(conversation_history)} history messages)")
    else:
        logger.info(f"[Chat] Processing: {user_message[:100]}...")
    
    return StreamingResponse(
        generate_ai_sdk_stream(user_message, session_id, conversation_history, file_context),
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


# ============================================================================
# Hook System API Endpoints
# ============================================================================

# Import Hook Manager
try:
    from engine.context import get_hook_manager, ConnectionTarget
    HOOK_SYSTEM_AVAILABLE = True
except ImportError:
    HOOK_SYSTEM_AVAILABLE = False
    logger.warning("Hook system not available")


class HookConnectRequest(BaseModel):
    """Hook connect request"""
    type: str  # browser, desktop, file
    target: str = ""  # Optional target (e.g., chrome, directory path)


@app.get("/api/hooks/status")
async def get_hook_status():
    """
    Get current Hook system status.
    
    Returns all connected hooks and their current context.
    """
    if not HOOK_SYSTEM_AVAILABLE:
        return {"hooks": {}, "available": False}
    
    try:
        manager = await get_hook_manager()
        status = manager.get_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get hook status: {e}")
        return {"hooks": {}, "error": str(e)}


@app.post("/api/hooks/connect")
async def connect_hook(request: HookConnectRequest):
    """
    Connect to an application/resource.
    
    Supported types:
    - browser: Connect to user's browser (Chrome, Firefox, Edge)
    - desktop: Monitor active windows
    - file: Watch file changes in a directory
    """
    if not HOOK_SYSTEM_AVAILABLE:
        raise HTTPException(status_code=501, detail="Hook system not available")
    
    try:
        manager = await get_hook_manager()
        
        success = await manager.connect(ConnectionTarget(
            type=request.type,
            target=request.target,
        ))
        
        # 【修复】连接后立即 capture 一次上下文，确保 API 响应包含完整数据
        if success:
            hook = manager.get_hook(request.type)
            if hook:
                context = await hook.capture()  # 立即获取第一次上下文
                if context:
                    hook._notify_context_update(context)  # 手动更新到 state.context
        
        if success:
            return {
                "success": True,
                "message": f"Connected to {request.type}",
                "status": manager.get_status(),
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to connect to {request.type}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to connect hook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hooks/disconnect/{hook_id}")
async def disconnect_hook(hook_id: str):
    """
    Disconnect a hook by ID.
    """
    if not HOOK_SYSTEM_AVAILABLE:
        raise HTTPException(status_code=501, detail="Hook system not available")
    
    try:
        manager = await get_hook_manager()
        success = await manager.disconnect(hook_id)
        
        return {
            "success": success,
            "message": f"Disconnected {hook_id}" if success else f"Failed to disconnect {hook_id}",
        }
    except Exception as e:
        logger.error(f"Failed to disconnect hook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hooks/context")
async def get_hook_context():
    """
    Get current context from all connected hooks.
    
    This is the context that gets injected into the Agent.
    """
    if not HOOK_SYSTEM_AVAILABLE:
        return {"context": {}, "prompt": ""}
    
    try:
        from engine.context import get_context_store
        store = get_context_store()
        
        return {
            "context": store.get_context_for_agent(),
            "prompt": store.format_context_prompt(),
        }
    except Exception as e:
        logger.error(f"Failed to get hook context: {e}")
        return {"context": {}, "prompt": "", "error": str(e)}


# ============================================================================
# Window Discovery API（用于通用应用连接器）
# ============================================================================

@app.get("/api/windows")
async def get_all_windows():
    """
    Get all visible windows for the window selector UI.
    
    Returns:
        List of windows with hwnd, title, app_name, is_browser, etc.
    
    Used by:
        - ConnectorPanel window list selector
        - Drag-and-drop connector target identification
    """
    try:
        from engine.context.hooks.desktop_hook import get_all_windows as _get_all_windows

        windows = _get_all_windows()

        # Security: Update discovered HWNDs whitelist
        global _discovered_hwnds
        _discovered_hwnds = {w.hwnd for w in windows}

        return {
            "success": True,
            "count": len(windows),
            "windows": [w.to_dict() for w in windows],
        }
    except ImportError as e:
        logger.warning(f"Window discovery not available: {e}")
        return {
            "success": False,
            "count": 0,
            "windows": [],
            "error": "Window discovery not available on this platform",
        }
    except Exception as e:
        logger.error(f"Failed to get windows: {e}")
        return {
            "success": False,
            "count": 0,
            "windows": [],
            "error": str(e),
        }


class ConnectWindowRequest(BaseModel):
    """Connect to a specific window by HWND"""
    hwnd: int
    window_title: str = ""  # Optional, for display


# Security: HWND whitelist - only allow connecting to windows that were discovered
_discovered_hwnds: set = set()


@app.post("/api/windows/connect")
async def connect_to_window(request: ConnectWindowRequest):
    """
    Connect to a specific window by HWND.
    
    This is the unified app connector - works for browsers, IDEs, and any app.
    
    Args:
        hwnd: Window handle to connect to
        window_title: Optional window title for display
    
    Returns:
        Connection status and context
    """
    if not HOOK_SYSTEM_AVAILABLE:
        raise HTTPException(status_code=501, detail="Hook system not available")

    # Security: Validate HWND against whitelist
    global _discovered_hwnds
    if request.hwnd not in _discovered_hwnds:
        logger.warning(f"[Security] Attempted connection to non-whitelisted HWND: {request.hwnd}")
        raise HTTPException(status_code=403, detail="HWND not in discovered windows whitelist")

    try:
        from engine.context.hooks.desktop_hook import get_all_windows as _get_all_windows, BROWSER_PROCESSES

        # Find window info by HWND
        windows = _get_all_windows()
        target_window = None
        for w in windows:
            if w.hwnd == request.hwnd:
                target_window = w
                break

        if not target_window:
            raise HTTPException(status_code=404, detail=f"Window with HWND {request.hwnd} not found")
        
        # Determine hook type based on app
        hook_type = "browser" if target_window.is_browser else "desktop"
        
        # Connect using appropriate hook
        manager = await get_hook_manager()
        # 使用 hwnd 作为 target，让 DesktopHook 锁定到特定窗口
        success = await manager.connect(ConnectionTarget(
            type=hook_type,
            target=str(request.hwnd),  # 传递 HWND，不是 app_name
        ))
        
        if success:
            # Get hook and update context with window info
            hook = manager.get_hook(hook_type)
            if hook:
                context = await hook.capture()
                if context:
                    # Inject HWND into context for Overlay
                    if hasattr(context, 'hwnd'):
                        context.hwnd = request.hwnd
                    hook._notify_context_update(context)
            
            return {
                "success": True,
                "hook_type": hook_type,
                "window": target_window.to_dict(),
                "status": manager.get_status(),
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to connect to window")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to connect to window: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint"""
    memory_mb = 0
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
    except ImportError:
        pass  # psutil not installed
    except (OSError, AttributeError, Exception):
        pass  # Process or memory info not available
    
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
