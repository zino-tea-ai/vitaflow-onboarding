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
        """Execute task using ReAct Agent"""
        if self._executing:
            raise HTTPException(status_code=429, detail="Another task is executing")
        
        self._executing = True
        task_content = request.task_content
        self._current_task = task_content[:100]
        start_time = time.time()
        
        try:
            # Create ReAct Agent
            agent = ReActAgent(
                status_server=self.status_server,
                max_iterations=request.max_steps,
            )
            
            # Execute with planning for complex tasks
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


async def generate_ai_sdk_stream(task: str, session_id: str):
    """
    Generate SSE stream compatible with Vercel AI SDK 5.0 Data Stream Protocol.
    
    Stream format (SSE with JSON):
    - Start: data: {"type":"start","messageId":"..."}
    - Text: data: {"type":"text-start/delta/end","id":"...","delta":"..."}
    - Reasoning: data: {"type":"reasoning-start/delta/end","id":"...","delta":"..."}
    - Finish: data: {"type":"finish","finishReason":"stop"}
    
    Note: Requires x-vercel-ai-ui-message-stream: v1 header for custom backends.
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
    
    async def tool_start_callback(tool_id: str, tool_name: str):
        await event_queue.put(sse({"type": "tool-call-start", "toolCallId": tool_id, "toolName": tool_name}))
    
    async def tool_end_callback(tool_id: str, success: bool, result: str):
        await event_queue.put(sse({"type": "tool-result", "toolCallId": tool_id, "result": result if success else f"Error: {result}"}))
    
    async def run_agent():
        try:
            result = await agent.run(
                task=task,
                session_id=session_id,
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
    
    # Extract user message - support multiple formats
    user_message = ""
    session_id = body.get("session_id", "default")
    
    # Format 1: New Vercel AI SDK format { text: "..." }
    if "text" in body and body["text"]:
        user_message = body["text"]
    
    # Format 2: Messages array (traditional or new parts-based)
    elif "messages" in body and body["messages"]:
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
    
    logger.info(f"[Chat] Processing: {user_message[:100]}...")
    
    return StreamingResponse(
        generate_ai_sdk_stream(user_message, session_id),
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
