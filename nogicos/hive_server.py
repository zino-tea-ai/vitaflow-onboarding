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

# 【修复】确保用户安装的包可以被找到
import sys
import os
_user_site = os.path.expanduser("~\\AppData\\Roaming\\Python\\Python314\\site-packages")
if _user_site not in sys.path:
    sys.path.insert(0, _user_site)

# 【调试】启用 faulthandler 捕获 Segmentation Fault 堆栈
import faulthandler
faulthandler.enable(file=sys.stderr, all_threads=True)

import warnings
import asyncio
import os
import sys
import json
import time
import logging
import aiohttp
from typing import Optional, List, Dict, Any
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
    from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
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

# Phase 6: HostAgent 已删除，由 UnifiedAgentManager 取代
HOST_AGENT_AVAILABLE = False
from engine.agent.events import EventType, AgentEvent
from engine.agent.event_bus import get_event_bus
from engine.agent.state_manager import TaskStatus

# Phase 7: UnifiedAgentManager - 统一 Agent 入口
try:
    from engine.agent.unified_manager import UnifiedAgentManager, get_unified_manager
    UNIFIED_AGENT_AVAILABLE = True
    logger.info("UnifiedAgentManager available - using ReActAgent as core")
except ImportError as e:
    UNIFIED_AGENT_AVAILABLE = False
    UnifiedAgentManager = None
    get_unified_manager = None
    logger.warning(f"UnifiedAgentManager not available: {e}")


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


# ============================================================================
# Phase 6: Agent Control API Models
# ============================================================================

class AgentStartRequest(BaseModel):
    """Agent task start request - Phase 6"""
    task: str                          # 任务描述
    target_hwnds: Optional[List[int]] = None  # 目标窗口句柄列表
    max_iterations: int = 50           # 最大迭代次数
    session_id: str = "default"        # 会话 ID
    
    model_config = {"extra": "allow"}  # 允许扩展字段


class AgentStopRequest(BaseModel):
    """Agent task stop request - Phase 6"""
    task_id: str
    reason: str = "User requested"


class AgentResumeRequest(BaseModel):
    """Agent task resume request - Phase 6"""
    task_id: str


class AgentStatusResponse(BaseModel):
    """Agent status response - Phase 6"""
    task_id: str
    status: str                        # idle, running, paused, completed, failed, etc.
    iteration: int = 0
    max_iterations: int = 50
    current_action: Optional[str] = None
    error: Optional[str] = None
    progress: float = 0.0              # 0.0 - 1.0
    elapsed_seconds: float = 0.0
    tool_calls_count: int = 0


class AgentEventType(str):
    """Agent event types for WebSocket streaming"""
    THINKING = "thinking"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    PROGRESS = "progress"
    CONFIRM_REQUIRED = "confirm_required"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"


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
# Phase 6: Global HostAgent Manager (Review Fixed v2)
# ============================================================================

# Phase 6 Fix v2: Enhanced security with HMAC, Origin validation, IP whitelist
from collections import defaultdict
from dataclasses import dataclass, field
import uuid as uuid_module
import hmac
import hashlib


# ============================================================================
# Event Priority System (for backpressure handling)
# ============================================================================

class EventPriority:
    """事件优先级 - 高优先级事件在背压时不会被丢弃"""
    CRITICAL = 0   # confirm_required, failed, error - 永不丢弃
    HIGH = 1       # completed, stopped, cancelled, needs_help
    NORMAL = 2     # tool_start, tool_end, progress
    LOW = 3        # thinking, heartbeat, backpressure_warning


# 事件类型到优先级的映射
EVENT_PRIORITY_MAP: Dict[str, int] = {
    # Critical - 永不丢弃
    "confirm_required": EventPriority.CRITICAL,
    "failed": EventPriority.CRITICAL,
    "error": EventPriority.CRITICAL,
    "auth_error": EventPriority.CRITICAL,
    
    # High - 仅在极端情况下丢弃
    "completed": EventPriority.HIGH,
    "stopped": EventPriority.HIGH,
    "cancelled": EventPriority.HIGH,
    "needs_help": EventPriority.HIGH,
    "started": EventPriority.HIGH,
    "resumed": EventPriority.HIGH,
    "connected": EventPriority.HIGH,
    "connection_closing": EventPriority.HIGH,
    "pending_confirmations": EventPriority.HIGH,
    
    # Normal - 可以丢弃
    "tool_start": EventPriority.NORMAL,
    "tool_end": EventPriority.NORMAL,
    "progress": EventPriority.NORMAL,
    "status": EventPriority.NORMAL,
    
    # Low - 优先丢弃
    "thinking": EventPriority.LOW,
    "heartbeat": EventPriority.LOW,
    "backpressure_warning": EventPriority.LOW,
}


def _get_default_event_priority() -> int:
    """
    获取默认事件优先级 - Review Fix v6
    
    可通过环境变量 NOGICOS_DEFAULT_EVENT_PRIORITY 配置:
    - CRITICAL: 永不丢弃
    - HIGH: 仅极端情况丢弃（默认）
    - NORMAL: 可丢弃
    - LOW: 优先丢弃
    """
    priority_str = os.environ.get("NOGICOS_DEFAULT_EVENT_PRIORITY", "HIGH").upper()
    priority_map = {
        "CRITICAL": EventPriority.CRITICAL,
        "HIGH": EventPriority.HIGH,
        "NORMAL": EventPriority.NORMAL,
        "LOW": EventPriority.LOW,
    }
    return priority_map.get(priority_str, EventPriority.HIGH)


def get_event_priority(event_type: str) -> int:
    """
    获取事件优先级 - Review Fix v6
    
    未注册的事件类型使用 NOGICOS_DEFAULT_EVENT_PRIORITY 配置的值（默认 HIGH）
    """
    return EVENT_PRIORITY_MAP.get(event_type, _get_default_event_priority())


# ============================================================================
# Enhanced Rate Limiter with IP Whitelist and Logging
# ============================================================================

@dataclass
class RateLimitState:
    """速率限制状态"""
    requests: List[float] = field(default_factory=list)
    blocked_count: int = 0
    last_blocked_at: Optional[float] = None
    
    def is_allowed(self, max_requests: int, window_seconds: float) -> bool:
        """检查是否允许请求"""
        now = time.time()
        # 清理过期记录
        self.requests = [t for t in self.requests if now - t < window_seconds]
        if len(self.requests) >= max_requests:
            self.blocked_count += 1
            self.last_blocked_at = now
            return False
        self.requests.append(now)
        return True


class AgentAPIRateLimiter:
    """
    Agent API 速率限制器 - Review Fix v3
    
    增强功能：
    - IP 白名单支持
    - 日志限频（避免日志爆炸）
    - 统计信息
    - 可选 Redis 后端（多进程/分布式部署）
    """
    
    def __init__(
        self, 
        max_requests: int = 20, 
        window_seconds: float = 60.0,
        log_interval_seconds: float = 60.0,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.log_interval_seconds = log_interval_seconds
        self._states: Dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._last_log_time: Dict[str, float] = {}
        
        # IP 白名单
        whitelist_str = os.environ.get("NOGICOS_RATE_LIMIT_WHITELIST", "")
        self._whitelist: set = set(w.strip() for w in whitelist_str.split(",") if w.strip())
        self._whitelist.update({"127.0.0.1", "localhost", "::1"})
        
        # Review Fix v3: 可选 Redis 后端
        self._redis_client = None
        self._use_redis = False
        redis_url = os.environ.get("NOGICOS_REDIS_URL", "")
        if redis_url:
            try:
                import redis
                self._redis_client = redis.from_url(redis_url)
                self._redis_client.ping()  # 测试连接
                self._use_redis = True
                logger.info(f"[RateLimit] Using Redis backend: {redis_url.split('@')[-1]}")
            except ImportError:
                logger.warning("[RateLimit] redis package not installed, using memory backend")
            except Exception as e:
                logger.warning(f"[RateLimit] Redis connection failed: {e}, using memory backend")
    
    def check(self, client_id: str) -> bool:
        """检查客户端是否允许请求"""
        if client_id in self._whitelist:
            return True
        
        if self._use_redis and self._redis_client:
            return self._check_redis(client_id)
        else:
            return self._check_memory(client_id)
    
    def _check_memory(self, client_id: str) -> bool:
        """内存版速率检查"""
        allowed = self._states[client_id].is_allowed(self.max_requests, self.window_seconds)
        
        if not allowed:
            self._log_blocked(client_id, self._states[client_id].blocked_count)
        
        return allowed
    
    def _check_redis(self, client_id: str) -> bool:
        """Redis 版速率检查（滑动窗口）"""
        try:
            key = f"nogicos:ratelimit:{client_id}"
            now = time.time()
            window_start = now - self.window_seconds
            
            pipe = self._redis_client.pipeline()
            # 移除过期记录
            pipe.zremrangebyscore(key, 0, window_start)
            # 获取当前窗口内的请求数
            pipe.zcard(key)
            # 添加当前请求
            pipe.zadd(key, {str(now): now})
            # 设置过期时间
            pipe.expire(key, int(self.window_seconds) + 1)
            
            results = pipe.execute()
            current_count = results[1]
            
            if current_count >= self.max_requests:
                # 移除刚添加的请求（超限）
                self._redis_client.zrem(key, str(now))
                
                # 获取累计被阻止次数
                blocked_key = f"nogicos:ratelimit:blocked:{client_id}"
                blocked_count = self._redis_client.incr(blocked_key)
                self._redis_client.expire(blocked_key, 3600)  # 1小时过期
                
                self._log_blocked(client_id, blocked_count)
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"[RateLimit] Redis error: {e}, falling back to allow")
            return True
    
    def _log_blocked(self, client_id: str, blocked_count: int):
        """日志限频"""
        now = time.time()
        last_log = self._last_log_time.get(client_id, 0)
        if now - last_log >= self.log_interval_seconds:
            logger.warning(f"[RateLimit] Client {client_id} blocked (total: {blocked_count})")
            self._last_log_time[client_id] = now
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取速率限制统计 - Review Fix v4
        
        使用 SCAN 替代 KEYS 避免阻塞 Redis
        """
        if self._use_redis and self._redis_client:
            try:
                # Review Fix v4: 使用 SCAN 替代 KEYS，避免阻塞
                total_blocked = 0
                client_count = 0
                cursor = 0
                pattern = "nogicos:ratelimit:blocked:*"
                
                while True:
                    cursor, keys = self._redis_client.scan(
                        cursor=cursor,
                        match=pattern,
                        count=100  # 每批最多扫描 100 个
                    )
                    
                    if keys:
                        # 使用 MGET 批量获取值
                        values = self._redis_client.mget(keys)
                        for v in values:
                            if v:
                                total_blocked += int(v)
                        client_count += len(keys)
                    
                    # cursor 为 0 表示扫描完成
                    if cursor == 0:
                        break
                
                return {
                    "backend": "redis",
                    "total_clients": client_count,
                    "total_blocked_requests": total_blocked,
                    "whitelist_size": len(self._whitelist),
                }
            except Exception:
                pass
        
        total_blocked = sum(s.blocked_count for s in self._states.values())
        return {
            "backend": "memory",
            "total_clients": len(self._states),
            "total_blocked_requests": total_blocked,
            "whitelist_size": len(self._whitelist),
        }


# Global rate limiter for Agent API
_agent_rate_limiter = AgentAPIRateLimiter(max_requests=20, window_seconds=60.0)


# ============================================================================
# Review Fix v7: WebSocket Connection Limiter
# ============================================================================

class WebSocketConnectionLimiter:
    """
    WebSocket 连接限制器 - Review Fix v7
    
    功能：
    - 连接速率限制（防止连接洪泛）
    - 并发连接上限（防止资源耗尽）
    - 按 IP 统计
    """
    
    def __init__(
        self,
        max_connections_per_ip: int = 10,
        max_total_connections: int = 100,
        connect_rate_limit: int = 5,  # 每分钟最多建立连接数
        rate_window_seconds: float = 60.0,
    ):
        self.max_connections_per_ip = int(os.environ.get(
            "NOGICOS_WS_MAX_CONN_PER_IP", max_connections_per_ip
        ))
        self.max_total_connections = int(os.environ.get(
            "NOGICOS_WS_MAX_TOTAL_CONN", max_total_connections
        ))
        self.connect_rate_limit = int(os.environ.get(
            "NOGICOS_WS_CONNECT_RATE", connect_rate_limit
        ))
        self.rate_window_seconds = rate_window_seconds
        
        # IP -> 活跃连接数
        self._active_connections: Dict[str, int] = defaultdict(int)
        # IP -> 连接时间戳列表（用于速率限制）
        self._connect_times: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def try_acquire(self, client_ip: str) -> tuple[bool, str]:
        """
        尝试获取连接许可
        
        Returns:
            (allowed, error_message)
        """
        async with self._lock:
            now = time.time()
            
            # 检查总连接数
            total = sum(self._active_connections.values())
            if total >= self.max_total_connections:
                return False, f"Server connection limit reached ({self.max_total_connections})"
            
            # 检查单 IP 连接数
            if self._active_connections[client_ip] >= self.max_connections_per_ip:
                return False, f"Per-IP connection limit reached ({self.max_connections_per_ip})"
            
            # 检查连接速率
            times = self._connect_times[client_ip]
            # 清理过期记录
            times[:] = [t for t in times if now - t < self.rate_window_seconds]
            
            if len(times) >= self.connect_rate_limit:
                return False, f"Connection rate limit exceeded ({self.connect_rate_limit}/min)"
            
            # 记录连接
            self._active_connections[client_ip] += 1
            times.append(now)
            
            return True, ""
    
    async def release(self, client_ip: str):
        """释放连接"""
        async with self._lock:
            if self._active_connections[client_ip] > 0:
                self._active_connections[client_ip] -= 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_connections": sum(self._active_connections.values()),
            "unique_ips": len([k for k, v in self._active_connections.items() if v > 0]),
            "max_total": self.max_total_connections,
            "max_per_ip": self.max_connections_per_ip,
            "rate_limit": self.connect_rate_limit,
        }


class WebSocketMessageRateLimiter:
    """
    WebSocket 消息速率限制器 - Review Fix v8
    
    防止客户端消息洪泛，按连接跟踪消息发送速率
    """
    
    def __init__(
        self,
        max_messages_per_second: int = 10,
        burst_limit: int = 20,  # 允许短时突发
    ):
        self.max_messages_per_second = int(os.environ.get(
            "NOGICOS_WS_MSG_RATE", max_messages_per_second
        ))
        self.burst_limit = int(os.environ.get(
            "NOGICOS_WS_MSG_BURST", burst_limit
        ))
        
        # connection_id -> (message_times, warning_sent)
        self._message_times: Dict[str, List[float]] = {}
        self._warning_sent: Dict[str, bool] = {}
    
    def register_connection(self, connection_id: str):
        """注册新连接"""
        self._message_times[connection_id] = []
        self._warning_sent[connection_id] = False
    
    def unregister_connection(self, connection_id: str):
        """注销连接"""
        self._message_times.pop(connection_id, None)
        self._warning_sent.pop(connection_id, None)
    
    def check_rate(self, connection_id: str) -> tuple[bool, bool, str]:
        """
        检查消息速率
        
        Returns:
            (allowed, should_warn, error_message)
            - allowed: 是否允许发送
            - should_warn: 是否应发送警告（首次接近限制时）
            - error_message: 错误信息
        """
        if connection_id not in self._message_times:
            return True, False, ""
        
        now = time.time()
        times = self._message_times[connection_id]
        
        # 清理超过 1 秒的记录
        times[:] = [t for t in times if now - t < 1.0]
        
        # 检查突发限制（硬限制）
        if len(times) >= self.burst_limit:
            return False, False, f"Message rate limit exceeded ({self.burst_limit}/s burst)"
        
        # 检查持续速率（软限制，发警告）
        should_warn = False
        if len(times) >= self.max_messages_per_second:
            if not self._warning_sent.get(connection_id, False):
                should_warn = True
                self._warning_sent[connection_id] = True
        else:
            # 速率恢复正常，重置警告状态
            self._warning_sent[connection_id] = False
        
        # 记录消息
        times.append(now)
        
        return True, should_warn, ""
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "active_connections": len(self._message_times),
            "max_rate": self.max_messages_per_second,
            "burst_limit": self.burst_limit,
        }


# Global WebSocket connection limiter
_ws_connection_limiter = WebSocketConnectionLimiter()

# Global WebSocket message rate limiter
_ws_message_limiter = WebSocketMessageRateLimiter()


# ============================================================================
# HMAC Token Generation and Validation for WebSocket
# ============================================================================

# ============================================================================
# Review Fix v3: Separate WS Secret + HTTPS Enforcement
# ============================================================================

def get_ws_secret() -> str:
    """
    获取 WebSocket 专用密钥 - Review Fix v3
    
    优先使用 NOGICOS_WS_SECRET，若未配置则回退到 NOGICOS_API_KEY
    """
    return os.environ.get("NOGICOS_WS_SECRET") or \
           os.environ.get("NOGICOS_API_KEY") or \
           "default_secret_for_local"


def is_https_required() -> bool:
    """检查是否要求 HTTPS/WSS"""
    return os.environ.get("NOGICOS_REQUIRE_HTTPS", "").lower() in ("true", "1", "yes")


def _parse_forwarded_proto(headers) -> Optional[str]:
    """
    解析代理协议头 - Review Fix v6
    
    支持：
    - X-Forwarded-Proto: https / wss (常见)
    - Forwarded: proto=https / proto=wss (RFC 7239 标准)
    
    Returns:
        协议字符串 ("https", "wss" 或 None)
    """
    # 安全协议集合（Review Fix v6: 支持 wss）
    secure_protos = {"https", "wss"}
    
    # 优先检查 X-Forwarded-Proto（更常见）
    x_forwarded = headers.get("X-Forwarded-Proto", "")
    if x_forwarded.lower() in secure_protos:
        return x_forwarded.lower()
    
    # 检查 RFC 7239 标准 Forwarded 头
    # 格式: Forwarded: for=192.0.2.60;proto=https;by=203.0.113.43
    forwarded = headers.get("Forwarded", "")
    if forwarded:
        # 解析 proto=xxx
        for part in forwarded.split(";"):
            part = part.strip()
            if part.lower().startswith("proto="):
                proto = part[6:].strip().strip('"').lower()
                if proto in secure_protos:
                    return proto
    
    return None


def check_secure_connection(request_or_websocket, is_websocket: bool = False) -> tuple[bool, str]:
    """
    检查连接是否安全 - Review Fix v5
    
    当 NOGICOS_REQUIRE_HTTPS=true 时，强制要求 HTTPS/WSS
    
    检查顺序：
    1. url.scheme（直连场景）
    2. X-Forwarded-Proto / Forwarded 头（代理场景）
    3. 本地连接豁免
    
    Returns:
        (is_secure, error_message)
    """
    if not is_https_required():
        return True, ""
    
    # 获取客户端地址（用于本地豁免）
    client_host = ""
    if hasattr(request_or_websocket, 'client') and request_or_websocket.client:
        client_host = request_or_websocket.client.host or ""
    
    # 检查协议
    if is_websocket:
        # WebSocket: 检查 url.scheme 和代理头
        url_scheme = ""
        if hasattr(request_or_websocket, 'url') and request_or_websocket.url:
            url_scheme = getattr(request_or_websocket.url, 'scheme', '') or ""
        
        # wss 或通过 HTTPS 代理升级
        if url_scheme in ("wss", "https"):
            return True, ""
        
        # Review Fix v6: 支持 Forwarded 标准头（https 和 wss）
        forwarded_proto = _parse_forwarded_proto(request_or_websocket.headers)
        if forwarded_proto in ("https", "wss"):
            return True, ""
        
        # 本地连接允许非 WSS
        if client_host in ("127.0.0.1", "localhost", "::1"):
            return True, ""
        
        return False, "WSS required for non-local connections"
    else:
        # HTTP: 检查 scheme
        url_scheme = ""
        if hasattr(request_or_websocket, 'url') and request_or_websocket.url:
            url_scheme = getattr(request_or_websocket.url, 'scheme', '') or ""
        
        if url_scheme == "https":
            return True, ""
        
        # Review Fix v6: 支持 Forwarded 标准头
        forwarded_proto = _parse_forwarded_proto(request_or_websocket.headers)
        if forwarded_proto == "https":
            return True, ""
        
        # 本地连接允许非 HTTPS
        if client_host in ("127.0.0.1", "localhost", "::1"):
            return True, ""
        
        return False, "HTTPS required for non-local connections"


def generate_ws_token(task_id: str, expires_in_seconds: int = 300) -> str:
    """
    生成 WebSocket 连接令牌 - HMAC + 时间戳 - Review Fix v3
    
    使用独立的 WS 密钥 (NOGICOS_WS_SECRET)
    
    Args:
        task_id: 任务 ID
        expires_in_seconds: 令牌有效期（秒）
        
    Returns:
        格式: {timestamp}.{hmac_signature}
    """
    secret = get_ws_secret()
    timestamp = int(time.time()) + expires_in_seconds
    message = f"{task_id}:{timestamp}"
    
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()[:32]
    
    return f"{timestamp}.{signature}"


def verify_ws_token(task_id: str, token: str) -> tuple[bool, str]:
    """
    验证 WebSocket 令牌 - Review Fix v3
    
    使用独立的 WS 密钥 (NOGICOS_WS_SECRET)
    
    Args:
        task_id: 任务 ID
        token: 令牌字符串
        
    Returns:
        (is_valid, error_message)
    """
    if not token:
        return False, "Missing token"
    
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False, "Invalid token format"
        
        timestamp_str, signature = parts
        timestamp = int(timestamp_str)
        
        # 检查过期
        if timestamp < time.time():
            return False, "Token expired"
        
        # 验证签名（使用独立密钥）
        secret = get_ws_secret()
        message = f"{task_id}:{timestamp}"
        expected_signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()[:32]
        
        if not hmac.compare_digest(signature, expected_signature):
            return False, "Invalid signature"
        
        return True, ""
        
    except (ValueError, TypeError) as e:
        return False, f"Token parse error: {e}"


# ============================================================================
# Enhanced Auth Verification
# ============================================================================

# Allowed Origins for WebSocket (from environment or defaults)
def get_allowed_origins() -> set:
    """获取允许的 Origin 列表"""
    origins_str = os.environ.get("NOGICOS_ALLOWED_ORIGINS", "")
    if origins_str:
        return set(origins_str.split(","))
    
    # 默认允许的 Origins
    return {
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "file://",  # Electron
    }


def _get_trusted_proxies() -> set:
    """
    获取可信代理 IP 列表 - Review Fix v6
    
    从环境变量 NOGICOS_TRUSTED_PROXIES 加载，逗号分隔
    默认信任 localhost
    """
    proxies_str = os.environ.get("NOGICOS_TRUSTED_PROXIES", "")
    proxies = set(p.strip() for p in proxies_str.split(",") if p.strip())
    # 始终信任 localhost
    proxies.update({"127.0.0.1", "localhost", "::1"})
    return proxies


def get_real_client_ip(request_or_websocket) -> str:
    """
    获取真实客户端 IP - Review Fix v6
    
    在代理场景下解析 X-Forwarded-For / Forwarded 头获取真实 IP
    
    检查顺序：
    1. X-Forwarded-For（最常见）
    2. Forwarded: for=xxx（RFC 7239）
    3. X-Real-IP（Nginx 常用）
    4. request.client.host（直连）
    
    安全措施 (Review Fix v6)：
    - NOGICOS_TRUST_PROXY=true 启用代理信任
    - NOGICOS_TRUSTED_PROXIES=ip1,ip2 限制可信代理 IP
    - 仅当连接来自可信代理时才解析转发头
    """
    # 获取连接 IP
    direct_ip = ""
    if hasattr(request_or_websocket, 'client') and request_or_websocket.client:
        direct_ip = request_or_websocket.client.host or ""
    
    # 如果未启用代理信任，直接返回连接 IP
    if os.environ.get("NOGICOS_TRUST_PROXY", "").lower() not in ("true", "1", "yes"):
        return direct_ip or "unknown"
    
    # Review Fix v6: 检查连接是否来自可信代理
    trusted_proxies = _get_trusted_proxies()
    if direct_ip and direct_ip not in trusted_proxies:
        # 连接不是来自可信代理，忽略转发头（防止伪造）
        logger.debug(f"[Security] Ignoring forwarded headers from untrusted IP: {direct_ip}")
        return direct_ip
    
    headers = request_or_websocket.headers
    
    # 1. X-Forwarded-For: client, proxy1, proxy2
    x_forwarded_for = headers.get("X-Forwarded-For", "")
    if x_forwarded_for:
        # 取第一个（最左边是原始客户端）
        client_ip = x_forwarded_for.split(",")[0].strip()
        if client_ip:
            return client_ip
    
    # 2. Forwarded: for="[2001:db8::1]";proto=https
    forwarded = headers.get("Forwarded", "")
    if forwarded:
        for part in forwarded.split(";"):
            part = part.strip()
            if part.lower().startswith("for="):
                # 移除 for= 和可能的引号/方括号
                client_ip = part[4:].strip().strip('"').strip("[]")
                if client_ip:
                    return client_ip
    
    # 3. X-Real-IP（Nginx）
    x_real_ip = headers.get("X-Real-IP", "")
    if x_real_ip:
        return x_real_ip.strip()
    
    return direct_ip or "unknown"


def verify_agent_api_auth(request: Request) -> str:
    """
    验证 Agent API 鉴权 - Phase 6 Security Fix v5
    
    增强功能：
    - HTTPS 强制（NOGICOS_REQUIRE_HTTPS=true）
    - Origin 校验（可选）
    - 真实 IP 识别（NOGICOS_TRUST_PROXY=true）
    - 速率限制（基于真实 IP）
    
    Returns:
        client_id: 用于速率限制的客户端标识（真实 IP）
        
    Raises:
        HTTPException: 鉴权失败或速率限制
    """
    # 获取配置的 API Key
    expected_key = os.environ.get("NOGICOS_API_KEY", "")
    
    # Review Fix v5: 获取真实客户端 IP（代理场景）
    client_ip = get_real_client_ip(request)
    direct_ip = request.client.host if request.client else "unknown"
    
    # Review Fix v5: HTTPS 强制检查（REST 端点）
    is_secure, https_error = check_secure_connection(request, is_websocket=False)
    if not is_secure:
        logger.warning(f"[Security] REST API insecure connection from {client_ip}: {https_error}")
        raise HTTPException(status_code=403, detail=https_error)
    
    # Origin 校验（如果启用）
    if os.environ.get("NOGICOS_CHECK_ORIGIN", "").lower() == "true":
        origin = request.headers.get("Origin", "")
        allowed_origins = get_allowed_origins()
        if origin and origin not in allowed_origins:
            logger.warning(f"[Security] Blocked request from disallowed origin: {origin}")
            raise HTTPException(status_code=403, detail="Origin not allowed")
    
    if not expected_key:
        # 未配置 Key 时，仅允许 localhost
        # 注意：检查直连 IP 而非代理后的 IP，防止伪造
        if direct_ip not in ("127.0.0.1", "localhost", "::1"):
            logger.warning(f"[Security] Agent API blocked non-local request from {client_ip}")
            raise HTTPException(status_code=403, detail="Agent API only available locally")
        client_id = client_ip
    else:
        # 验证 API Key
        auth_header = request.headers.get("Authorization", "")
        api_key_header = request.headers.get("X-API-Key", "")
        
        is_valid = (
            auth_header == f"Bearer {expected_key}" or
            api_key_header == expected_key
        )
        
        if not is_valid:
            logger.warning(f"[Security] Agent API unauthorized request from {client_ip}")
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Review Fix v5: 使用真实 IP 作为客户端 ID
        client_id = client_ip
    
    # 速率限制检查（基于真实 IP）
    if not _agent_rate_limiter.check(client_id):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    return client_id


# HostAgentManager 已删除 - 由 UnifiedAgentManager 取代
# 删除日期: 2026-01-07
# 原因: HostAgent 是空壳，实际能力在 ReActAgent 中

# Global UnifiedAgentManager (new - Phase 7)
unified_agent_manager: Optional[UnifiedAgentManager] = None


# ============================================================================
# FastAPI App
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan manager"""
    global engine, server_start_time, unified_agent_manager
    
    logger.info("=" * 60)
    logger.info("NogicOS Hive Server V2 Starting...")
    logger.info("=" * 60)
    
    server_start_time = time.time()
    
    # Initialize engine
    engine = NogicEngine()
    await engine.start_websocket()
    
    # Initialize UnifiedAgentManager (唯一的 Agent 管理器)
    if UNIFIED_AGENT_AVAILABLE:
        unified_agent_manager = UnifiedAgentManager()
        await unified_agent_manager.initialize(status_server=engine.status_server)
        stats = unified_agent_manager.get_stats()
        logger.info("=" * 40)
        logger.info("UnifiedAgentManager initialized!")
        logger.info(f"  Modules connected:")
        for module, available in stats.get("modules", {}).items():
            status = "OK" if available else "N/A"
            logger.info(f"    - {module}: {status}")
        logger.info("=" * 40)
    else:
        logger.warning("UnifiedAgentManager not available, Agent API will be disabled")
    
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
    if UNIFIED_AGENT_AVAILABLE:
        logger.info(f"  Agent API: /api/agent/*")
    logger.info("=" * 60)
    
    yield
    
    # Cleanup
    logger.info("Shutting down...")
    
    # Close UnifiedAgentManager
    if unified_agent_manager:
        await unified_agent_manager.close()
    
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
    "http://localhost:5176",   # Vite alternative port
    "http://localhost:5177",   # Vite alternative port
    "http://localhost:3000",   # React dev server
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5176",
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
# Review Fix v7: Global HTTPS Enforcement Middleware
# ============================================================================

@app.middleware("http")
async def https_enforcement_middleware(request: Request, call_next):
    """
    全局 HTTPS 强制中间件 - Review Fix v7
    
    当 NOGICOS_REQUIRE_HTTPS=true 时：
    - 对所有非本地请求强制 HTTPS
    - 豁免路径: /health, /ready (健康检查)
    
    配置:
    - NOGICOS_REQUIRE_HTTPS=true 启用
    - NOGICOS_HTTPS_EXEMPT_PATHS=/health,/ready 豁免路径
    """
    # 检查是否启用 HTTPS 强制
    if not is_https_required():
        return await call_next(request)
    
    # 获取豁免路径
    exempt_paths_str = os.environ.get("NOGICOS_HTTPS_EXEMPT_PATHS", "/health,/ready")
    exempt_paths = set(p.strip() for p in exempt_paths_str.split(",") if p.strip())
    
    # 检查是否豁免路径
    if request.url.path in exempt_paths:
        return await call_next(request)
    
    # 检查安全连接
    is_secure, error = check_secure_connection(request, is_websocket=False)
    if not is_secure:
        client_host = request.client.host if request.client else "unknown"
        logger.warning(f"[Security] HTTP blocked insecure request from {client_host} to {request.url.path}")
        return JSONResponse(
            status_code=403,
            content={"detail": error, "path": request.url.path}
        )
    
    return await call_next(request)


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

    # #region debug log D
    import json as json_lib
    with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
        f.write(json_lib.dumps({"location":"hive_server.py:1953","message":"Getting agent instance","data":{"engineExists":engine is not None},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"})+'\n')
    # #endregion

    # Reuse global agent instance with lock protection
    # This avoids 1-2s initialization overhead per request
    if engine:
        agent = await engine.get_agent()
        # #region debug log D
        with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_lib.dumps({"location":"hive_server.py:1957","message":"Agent retrieved from engine","data":{"agentExists":agent is not None},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"})+'\n')
        # #endregion
    else:
        # #region debug log D
        with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_lib.dumps({"location":"hive_server.py:1959","message":"Creating new ReActAgent","data":{},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"})+'\n')
        # #endregion
        agent = ReActAgent(
            status_server=None,
            max_iterations=20,
        )
        # #region debug log D
        with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_lib.dumps({"location":"hive_server.py:1963","message":"ReActAgent created","data":{"agentExists":agent is not None},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"})+'\n')
        # #endregion
    
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
                # #region debug log H1
                import json as json_lib
                with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json_lib.dumps({"location":"hive_server.py:run_agent","message":"conversation_history received","data":{"history_count":len(conversation_history),"history_preview":[{"role":m.get("role"),"content_len":len(str(m.get("content","")))} for m in conversation_history[:5]]},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H1"})+'\n')
                # #endregion
                
                # Format previous messages as context
                context_parts = []
                for msg in conversation_history[:-1]:  # Exclude current message
                    role = msg.get("role", "")
                    
                    # #region debug log H2 - inspect message structure
                    with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json_lib.dumps({"location":"hive_server.py:msg_inspect","message":"Inspecting message","data":{"role":role,"msg_keys":list(msg.keys()),"content_type":type(msg.get("content")).__name__,"parts_exists":"parts" in msg,"content_preview":str(msg.get("content",""))[:200]},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H2"})+'\n')
                    # #endregion
                    
                    # AI SDK 5.0 uses "parts" array instead of "content" for messages
                    content = ""
                    
                    # Try parts array first (AI SDK 5.0 format)
                    if "parts" in msg and msg["parts"]:
                        for part in msg["parts"]:
                            if isinstance(part, dict) and part.get("type") == "text":
                                content += part.get("text", "")
                    # Fallback to content field
                    elif msg.get("content"):
                        content = msg.get("content", "")
                        if isinstance(content, list):
                            # Handle parts-based format in content
                            content = " ".join(
                                p.get("text", "") for p in content 
                                if isinstance(p, dict) and p.get("type") == "text"
                            )
                    if role == "user":
                        context_parts.append(f"用户: {content}")
                    elif role == "assistant":
                        # [FIX] Increased truncation limit from 500 to 2000
                        # This preserves suggested answers for confirmation flow
                        if len(content) > 2000:
                            content = content[:2000] + "..."
                        context_parts.append(f"助手: {content}")
                
                if context_parts:
                    context = "## 之前的对话:\n" + "\n".join(context_parts[-6:])  # Keep last 3 turns (6 messages)
                    logger.info(f"[Chat] Injecting {len(context_parts)} previous messages as context")
                    # #region debug log H1
                    with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json_lib.dumps({"location":"hive_server.py:context_built","message":"Context built from history","data":{"context_preview":context[:500] if context else "","context_parts_count":len(context_parts)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H1"})+'\n')
                    # #endregion
            
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
            
            # #region debug log D,E
            import json as json_lib
            with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_lib.dumps({"location":"hive_server.py:2086","message":"Calling agent.run_with_planning","data":{"task":task[:50],"sessionId":session_id},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D,E"})+'\n')
            # #endregion
            
            # 使用 run_with_planning() 激活 Plan-and-Execute 架构
            # - 简单任务：直接执行
            # - 复杂任务：生成计划，逐步执行，失败时重新规划
            result = await agent.run_with_planning(
                task=task,
                session_id=session_id,
                context=context,  # Pass conversation history as context
                on_text_delta=text_callback,
                on_thinking_delta=thinking_callback,
                on_tool_start=tool_start_callback,
                on_tool_end=tool_end_callback,
            )
            
            # #region debug log E
            with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_lib.dumps({"location":"hive_server.py:2098","message":"Agent run completed","data":{"success":result.success if hasattr(result,'success') else None},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"E"})+'\n')
            # #endregion
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
            logger.error(f"Agent error: {e}", exc_info=True)
            # #region debug log E - error details
            import json as json_lib
            with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_lib.dumps({"location":"hive_server.py:2135","message":"Agent exception","data":{"error":str(e),"type":type(e).__name__},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"E"})+'\n')
            # #endregion
            
            # Send error message to frontend - MUST send text-start before text-delta
            error_msg = str(e)
            if "api" in error_msg.lower() and "key" in error_msg.lower():
                error_msg = "API Key 配置错误，请检查 api_keys.py"
            
            # 【修复】先发送 text-start，再发送 text-delta，最后发送 text-end
            if not text_started:
                await event_queue.put(sse({"type": "text-start", "id": text_id}))
            await event_queue.put(sse({
                "type": "text-delta", 
                "id": text_id, 
                "delta": f"\n\n❌ 错误: {error_msg}"
            }))
            await event_queue.put(sse({"type": "text-end", "id": text_id}))
            await event_queue.put(sse({"type": "finish", "finishReason": "error"}))
        finally:
            agent_done.set()
    
    # 【修复 #9】Start agent in background with exception handling
    agent_task = asyncio.create_task(run_agent())
    agent_task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.exception() else None)
    
    # #region debug log E
    import json as json_lib
    with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
        f.write(json_lib.dumps({"location":"hive_server.py:2117","message":"Sending stream start","data":{"messageId":message_id},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"E"})+'\n')
    # #endregion
    
    # Send stream start
    yield sse({"type": "start", "messageId": message_id})
    
    try:
        event_count = 0
        while not agent_done.is_set() or not event_queue.empty():
            try:
                # Reduced timeout for faster response (was 0.1s, now 0.01s)
                event = await asyncio.wait_for(event_queue.get(), timeout=0.01)
                event_count += 1
                # #region debug log E
                if event_count <= 5:  # Log first 5 events
                    with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json_lib.dumps({"location":"hive_server.py:2124","message":"Yielding event","data":{"eventCount":event_count,"eventPreview":event[:100] if isinstance(event,str) else str(event)[:100]},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"E"})+'\n')
                # #endregion
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
    # #region debug log B
    import json as json_lib
    with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
        f.write(json_lib.dumps({"location":"hive_server.py:2141","message":"chat_endpoint called","data":{},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"B"})+'\n')
    # #endregion
    
    if not engine:
        # #region debug log D
        with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_lib.dumps({"location":"hive_server.py:2159","message":"engine not ready","data":{},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"})+'\n')
        # #endregion
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    try:
        body = await request.json()
        # #region debug log C
        with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_lib.dumps({"location":"hive_server.py:2163","message":"JSON parsed","data":{"bodyKeys":list(body.keys())},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"C"})+'\n')
        # #endregion
        logger.info(f"[Chat] Received request: {json.dumps(body, ensure_ascii=False)[:200]}...")
    except Exception as e:
        # #region debug log C
        with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_lib.dumps({"location":"hive_server.py:2167","message":"JSON parse error","data":{"error":str(e)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"C"})+'\n')
        # #endregion
        logger.error(f"[Chat] Failed to parse JSON: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    
    # Extract user message and conversation history
    user_message = ""
    conversation_history = []
    session_id = body.get("session_id", "default")
    
    # [FIX] Always extract messages array for conversation history (AI SDK sends both)
    if "messages" in body and body["messages"]:
        conversation_history = body["messages"]
    
    # Format 1: New Vercel AI SDK format { text: "..." }
    # Note: AI SDK sends BOTH text AND messages array
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
        # #region debug log C
        import json as json_lib
        with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_lib.dumps({"location":"hive_server.py:2198","message":"No user message found","data":{"body":body},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"C"})+'\n')
        # #endregion
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
    
    # #region debug log D,E
    import json as json_lib
    with open(r'c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log', 'a', encoding='utf-8') as f:
        f.write(json_lib.dumps({"location":"hive_server.py:2214","message":"Starting stream generation","data":{"userMessage":user_message[:50],"sessionId":session_id},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D,E"})+'\n')
    # #endregion
    
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
# CDP Browser Connection API（直接控制用户浏览器）
# ============================================================================

class CDPConnectRequest(BaseModel):
    """CDP connection request"""
    cdp_url: str = "http://localhost:9222"


# Global browser session for CDP connection
_cdp_browser_session = None


@app.post("/api/browser/connect-cdp")
async def connect_browser_cdp(request: CDPConnectRequest):
    """
    Connect to user's browser via Chrome DevTools Protocol (CDP).
    
    This enables direct DOM manipulation without mouse simulation.
    
    User must start Chrome with: chrome.exe --remote-debugging-port=9222
    
    Args:
        cdp_url: CDP endpoint URL (default: http://localhost:9222)
    
    Returns:
        Connection status and current page info
    """
    global _cdp_browser_session
    
    try:
        from engine.browser.session import BrowserSession
        
        # Stop existing session if any
        if _cdp_browser_session:
            try:
                await _cdp_browser_session.stop()
            except Exception:
                pass
        
        # Create new session and connect via CDP
        _cdp_browser_session = BrowserSession()
        success = await _cdp_browser_session.connect_to_browser(request.cdp_url)
        
        if success:
            # Get current page info
            title = await _cdp_browser_session.get_title()
            url = await _cdp_browser_session.get_current_url()
            
            # Inject session into Agent's tool registry
            from engine.tools import get_registry
            registry = get_registry()
            registry.set_context("browser_session", _cdp_browser_session)
            
            logger.info(f"[CDP] Connected to browser: {title} ({url})")
            
            return {
                "success": True,
                "message": f"Connected to browser via CDP",
                "page": {
                    "title": title,
                    "url": url,
                },
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail="Failed to connect via CDP. Make sure Chrome is running with --remote-debugging-port=9222"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CDP] Connection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/browser/cdp-status")
async def get_cdp_status():
    """
    Get CDP connection status.
    
    Returns:
        Connection status and current page info if connected
    """
    global _cdp_browser_session
    
    if not _cdp_browser_session or not _cdp_browser_session.is_started:
        return {"connected": False}
    
    try:
        title = await _cdp_browser_session.get_title()
        url = await _cdp_browser_session.get_current_url()
        
        return {
            "connected": True,
            "page": {
                "title": title,
                "url": url,
            },
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


@app.post("/api/browser/disconnect-cdp")
async def disconnect_browser_cdp():
    """
    Disconnect from browser CDP session.
    """
    global _cdp_browser_session
    
    if _cdp_browser_session:
        try:
            await _cdp_browser_session.stop()
            _cdp_browser_session = None
            
            # Remove session from registry
            from engine.tools import get_registry
            registry = get_registry()
            registry.set_context("browser_session", None)
            
            logger.info("[CDP] Disconnected from browser")
            return {"success": True, "message": "Disconnected from CDP"}
        except Exception as e:
            logger.error(f"[CDP] Disconnect failed: {e}")
            return {"success": False, "error": str(e)}
    
    return {"success": True, "message": "No active CDP connection"}


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


# ============================================================================
# Phase 6: Agent Control API Endpoints
# ============================================================================

@app.post("/api/agent/start")
async def start_agent(request: AgentStartRequest, req: Request):
    """
    启动 Agent 任务 - Phase 7 (UnifiedAgentManager)
    
    启动一个新的 Agent 任务，返回任务 ID 用于后续状态查询和控制。
    
    Phase 7 改进：
        - 使用 UnifiedAgentManager 作为核心（基于 ReActAgent）
        - 自动串联 PlanCache、Memory、ContextStore、Verification
        - 支持计划复用和学习
    
    Security:
        - 需要 API Key 鉴权（或仅允许本地请求）
        - 速率限制：20 requests/minute
    
    Args:
        request: 包含任务描述和目标窗口等信息
        
    Returns:
        {"task_id": str, "status": "running"}
    """
    # Security: 验证鉴权和速率限制
    verify_agent_api_auth(req)
    
    # Phase 7: 优先使用 UnifiedAgentManager
    if UNIFIED_AGENT_AVAILABLE and unified_agent_manager:
        try:
            result = await unified_agent_manager.start_task(
                task=request.task,
                target_hwnds=request.target_hwnds,
                max_iterations=request.max_iterations,
                session_id=request.session_id,
            )
            return result
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to start agent (unified): {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Fallback: HostAgentManager (legacy)
    if HOST_AGENT_AVAILABLE and host_agent_manager:
        try:
            result = await host_agent_manager.start_task(
                task=request.task,
                target_hwnds=request.target_hwnds,
                max_iterations=request.max_iterations,
                session_id=request.session_id,
            )
            return result
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to start agent (legacy): {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=501, detail="No Agent available")


@app.post("/api/agent/stop")
async def stop_agent(request: AgentStopRequest, req: Request):
    """
    停止 Agent 任务（用户接管）- Phase 7
    
    参考 ByteBot takeover 模式，用户可以接管正在执行的任务。
    
    Security:
        - 需要 API Key 鉴权（或仅允许本地请求）
    
    Args:
        request: 包含任务 ID 和停止原因
        
    Returns:
        {"success": bool, "status": "stopped"}
    """
    # Security: 验证鉴权
    verify_agent_api_auth(req)
    
    # Phase 7: 优先使用 UnifiedAgentManager
    if UNIFIED_AGENT_AVAILABLE and unified_agent_manager:
        try:
            result = await unified_agent_manager.stop_task(
                task_id=request.task_id,
                reason=request.reason,
            )
            return result
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to stop agent: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Fallback: HostAgentManager (legacy)
    if HOST_AGENT_AVAILABLE and host_agent_manager:
        try:
            result = await host_agent_manager.stop_task(
                task_id=request.task_id,
                reason=request.reason,
            )
            return result
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to stop agent: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=501, detail="No Agent available")


@app.post("/api/agent/resume")
async def resume_agent(request: AgentResumeRequest, req: Request):
    """
    恢复 Agent 任务 - Phase 6 (Security Fixed)
    
    参考 ByteBot resume 模式，从检查点恢复暂停或中断的任务。
    
    Security:
        - 需要 API Key 鉴权（或仅允许本地请求）
    
    Args:
        request: 包含要恢复的任务 ID
        
    Returns:
        {"task_id": str, "status": "resuming"}
    """
    # Security: 验证鉴权
    verify_agent_api_auth(req)
    
    if not HOST_AGENT_AVAILABLE or not host_agent_manager:
        raise HTTPException(status_code=501, detail="HostAgent not available")
    
    try:
        result = await host_agent_manager.resume_task(task_id=request.task_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to resume agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/status/{task_id}")
async def get_agent_status(task_id: str, req: Request):
    """
    获取 Agent 任务状态 - Phase 7
    
    Security:
        - 需要 API Key 鉴权（或仅允许本地请求）
    
    Args:
        task_id: 任务 ID
        
    Returns:
        AgentStatusResponse 包含详细的任务状态信息
    """
    # Security: 验证鉴权
    verify_agent_api_auth(req)
    
    # Phase 7: 优先使用 UnifiedAgentManager
    if UNIFIED_AGENT_AVAILABLE and unified_agent_manager:
        try:
            status = await unified_agent_manager.get_task_status(task_id)
            if "error" in status:
                raise HTTPException(status_code=404, detail=status["error"])
            return status
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get agent status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Fallback: HostAgentManager (legacy)
    if HOST_AGENT_AVAILABLE and host_agent_manager:
        try:
            status = host_agent_manager.get_status(task_id)
            return status
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to get agent status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=501, detail="No Agent available")


@app.post("/api/agent/confirm/{action_id}")
async def confirm_agent_action(action_id: str, approved: bool = True, req: Request = None):
    """
    确认/拒绝敏感操作 - Phase 6 (Security Fixed)
    
    当 Agent 请求执行敏感操作时，用户通过此端点批准或拒绝。
    
    Security:
        - 需要 API Key 鉴权（或仅允许本地请求）
    
    Args:
        action_id: 操作 ID（从 WebSocket 事件获取）
        approved: True=批准, False=拒绝
        
    Returns:
        {"success": bool}
    """
    # Security: 验证鉴权
    if req:
        verify_agent_api_auth(req)
    
    if not HOST_AGENT_AVAILABLE or not host_agent_manager:
        raise HTTPException(status_code=501, detail="HostAgent not available")
    
    if approved:
        success = await host_agent_manager.approve_action(action_id)
    else:
        success = await host_agent_manager.deny_action(action_id)
    
    return {"success": success, "action_id": action_id, "approved": approved}


@app.get("/api/agent/confirmations")
async def get_pending_confirmations(req: Request):
    """
    获取待确认的敏感操作列表 - Phase 6 Fix
    
    返回当前所有等待用户确认的敏感操作。
    
    Security:
        - 需要 API Key 鉴权（或仅允许本地请求）
    """
    # Security: 验证鉴权
    verify_agent_api_auth(req)
    
    if not HOST_AGENT_AVAILABLE or not host_agent_manager:
        raise HTTPException(status_code=501, detail="HostAgent not available")
    
    confirmations = host_agent_manager.get_pending_confirmations()
    return {"pending": confirmations, "count": len(confirmations)}


# ============================================================================
# YC Workflow Confirmation System
# ============================================================================

# Global pending confirmations for YC workflow
_yc_pending_confirmations: Dict[str, asyncio.Future] = {}


class WorkflowConfirmRequest(BaseModel):
    """YC workflow confirmation request"""
    request_id: str
    confirmed: bool


@app.post("/api/workflow/confirm")
async def confirm_yc_workflow(request: WorkflowConfirmRequest):
    """
    Confirm or cancel YC workflow action.
    
    Called from frontend ConfirmDialog when user clicks Confirm/Cancel.
    
    Args:
        request_id: The confirmation request ID
        confirmed: True to proceed, False to cancel
        
    Returns:
        {"success": bool}
    """
    request_id = request.request_id
    confirmed = request.confirmed
    
    if request_id not in _yc_pending_confirmations:
        raise HTTPException(status_code=404, detail=f"Confirmation request {request_id} not found or expired")
    
    future = _yc_pending_confirmations.pop(request_id)
    
    if not future.done():
        future.set_result(confirmed)
        logger.info(f"[YC Workflow] Confirmation {request_id}: {'approved' if confirmed else 'rejected'}")
    
    return {"success": True, "request_id": request_id, "confirmed": confirmed}


async def request_yc_confirmation(
    status_server: StatusServer,
    title: str,
    question: str,
    answer: str,
    execution_count: int,
    source_file: str = "PITCH_CONTEXT.md",
) -> bool:
    """
    Request user confirmation for YC workflow via WebSocket.
    
    Sends a confirm_request event to frontend and waits for response.
    
    Args:
        status_server: WebSocket server for broadcasting
        title: Dialog title
        question: YC question text
        answer: Answer to fill
        execution_count: Which run this is (1st, 2nd, etc.)
        source_file: Source document filename
        
    Returns:
        True if user confirmed, False if cancelled
    """
    import uuid
    request_id = f"yc-{uuid.uuid4().hex[:8]}"
    
    # Create future for async waiting
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    _yc_pending_confirmations[request_id] = future
    
    # Send confirmation request to frontend
    await status_server.broadcast({
        "type": "confirm_request",
        "data": {
            "request_id": request_id,
            "title": title,
            "question": question,
            "answer": answer,
            "execution_count": execution_count,
            "source_file": source_file,
        }
    })
    logger.info(f"[YC Workflow] Sent confirmation request {request_id}")
    
    try:
        # Wait for user response (timeout: 5 minutes)
        confirmed = await asyncio.wait_for(future, timeout=300)
        return confirmed
    except asyncio.TimeoutError:
        _yc_pending_confirmations.pop(request_id, None)
        logger.warning(f"[YC Workflow] Confirmation {request_id} timed out")
        return False


@app.get("/api/agent/stats")
async def get_agent_stats(req: Request):
    """
    获取 Agent 系统统计信息 - Phase 7
    
    返回 UnifiedAgentManager 的模块状态和统计信息。
    
    Security:
        - 需要 API Key 鉴权（或仅允许本地请求）
    """
    # Security: 验证鉴权
    verify_agent_api_auth(req)
    
    # Phase 7: UnifiedAgentManager stats
    if UNIFIED_AGENT_AVAILABLE and unified_agent_manager:
        stats = unified_agent_manager.get_stats()
        stats["manager_type"] = "UnifiedAgentManager"
        stats["core_agent"] = "ReActAgent"
        return stats
    
    # Legacy
    if HOST_AGENT_AVAILABLE and host_agent_manager:
        return {
            "manager_type": "HostAgentManager (legacy)",
            "core_agent": "HostAgent",
            "modules": {
                "plan_cache": False,
                "context_store": False,
                "memory": False,
                "verification": False,
            },
        }
    
    raise HTTPException(status_code=501, detail="No Agent available")


# ============================================================================
# Phase 6: WebSocket Agent Event Stream
# ============================================================================

@app.get("/api/agent/ws-token/{task_id}")
async def get_ws_token(task_id: str, req: Request):
    """
    获取 WebSocket 连接令牌 - Phase 6 Fix v2
    
    返回一个 HMAC 签名的令牌，用于 WebSocket 连接鉴权。
    令牌有效期 5 分钟。
    
    Security:
        - 需要 API Key 鉴权
    """
    # 验证 API 鉴权
    verify_agent_api_auth(req)
    
    token = generate_ws_token(task_id, expires_in_seconds=300)
    return {
        "task_id": task_id,
        "token": token,
        "expires_in": 300,
        "ws_url": f"/ws/agent/{task_id}?token={token}",
    }


@app.websocket("/ws/agent/{task_id}")
async def agent_event_stream(websocket: WebSocket, task_id: str, token: Optional[str] = None):
    """
    WebSocket 流式推送 Agent 事件 - Phase 6 (Security Fixed v3)
    
    为指定任务建立 WebSocket 连接，实时接收：
    - started: 任务开始
    - thinking: AI 思考过程
    - tool_start: 工具调用开始
    - tool_end: 工具调用结束
    - progress: 进度更新
    - confirm_required: 需要用户确认
    - needs_help: 需要人工干预
    - completed: 任务完成
    - failed: 任务失败
    - cancelled: 任务取消
    - stopped: 任务停止
    - backpressure_warning: 事件队列积压警告
    - heartbeat: 心跳
    
    Security (v3):
        - HTTPS/WSS 强制（NOGICOS_REQUIRE_HTTPS=true）
        - HMAC 签名令牌（独立密钥 NOGICOS_WS_SECRET）
        - Origin 校验
        - 仅允许本地连接（未配置 API Key 时）
        - 鉴权失败时发送错误事件后再关闭
    
    Args:
        task_id: 任务 ID
        token: HMAC 签名令牌（通过 query 参数传递）
    """
    # Review Fix v5: 使用真实客户端 IP
    client_host = get_real_client_ip(websocket)
    direct_host = websocket.client.host if websocket.client else "unknown"
    
    # Review Fix v7: 连接速率限制（在 accept 前检查）
    allowed, limit_error = await _ws_connection_limiter.try_acquire(client_host)
    if not allowed:
        logger.warning(f"[Security] WebSocket connection limited for {client_host}: {limit_error}")
        # 连接限制时直接关闭，不 accept
        await websocket.close(code=1008, reason=limit_error)
        return
    
    # 确保连接结束时释放配额
    connection_acquired = True
    
    # Fix v7: 鉴权失败时先 accept，发送错误事件，再关闭，并释放连接配额
    async def reject_with_error(code: int, reason: str, error_type: str):
        """拒绝连接并发送错误事件"""
        nonlocal connection_acquired
        try:
            await websocket.accept()
            await websocket.send_json({
                "type": "auth_error",
                "data": {
                    "error": reason,
                    "error_type": error_type,
                    "code": code,
                },
                "timestamp": time.time(),
                "task_id": task_id,
            })
            await websocket.close(code=code, reason=reason)
        finally:
            # 释放连接配额
            if connection_acquired:
                await _ws_connection_limiter.release(client_host)
                connection_acquired = False
    
    # Security v3: HTTPS/WSS 强制检查
    is_secure, https_error = check_secure_connection(websocket, is_websocket=True)
    if not is_secure:
        logger.warning(f"[Security] WebSocket insecure connection from {client_host}: {https_error}")
        await reject_with_error(4003, https_error, "insecure_connection")
        return
    
    # Security v3: Origin 校验
    if os.environ.get("NOGICOS_CHECK_ORIGIN", "").lower() == "true":
        origin = websocket.headers.get("Origin", "")
        allowed_origins = get_allowed_origins()
        if origin and origin not in allowed_origins:
            logger.warning(f"[Security] WebSocket blocked origin: {origin} from {client_host}")
            await reject_with_error(4003, f"Origin not allowed: {origin}", "origin_blocked")
            return
    
    # Security v3: HMAC 令牌验证（使用独立密钥）或本地访问
    ws_secret = get_ws_secret()
    if ws_secret != "default_secret_for_local":
        # 需要 HMAC 令牌验证
        is_valid, error_msg = verify_ws_token(task_id, token or "")
        if not is_valid:
            logger.warning(f"[Security] WebSocket auth failed from {client_host}: {error_msg}")
            await reject_with_error(4001, f"Authentication failed: {error_msg}", "auth_failed")
            return
    else:
        # 未配置密钥时，仅允许 localhost
        # Review Fix v5: 检查直连 IP 而非代理后的 IP，防止伪造
        if direct_host not in ("127.0.0.1", "localhost", "::1"):
            logger.warning(f"[Security] WebSocket blocked non-local from {client_host} (direct: {direct_host})")
            await reject_with_error(4003, "Local access only", "local_only")
            return
    
    # 检查 HostAgent 可用性
    if not HOST_AGENT_AVAILABLE or not host_agent_manager:
        await reject_with_error(1011, "HostAgent not available", "service_unavailable")
        return
    
    # 鉴权成功，接受连接
    await websocket.accept()
    logger.info(f"[Agent WS] Connected for task: {task_id} from {client_host}")
    
    # 发送连接成功事件
    await websocket.send_json({
        "type": "connected",
        "data": {"task_id": task_id, "client": client_host},
        "timestamp": time.time(),
    })
    
    # 订阅任务事件
    event_queue = host_agent_manager.subscribe(task_id)
    
    # Review Fix v8: 注册消息速率限制器
    connection_id = f"{task_id}:{client_host}:{time.time()}"
    _ws_message_limiter.register_connection(connection_id)
    
    try:
        # 发送当前状态
        try:
            status = host_agent_manager.get_status(task_id)
            await websocket.send_json({
                "type": "status",
                "data": status,
                "timestamp": time.time(),
            })
        except ValueError:
            # 任务不存在，发送 not_found 状态
            await websocket.send_json({
                "type": "status",
                "data": {"task_id": task_id, "status": "not_found"},
                "timestamp": time.time(),
            })
        
        # 发送待确认的操作（如果有）
        pending = host_agent_manager.get_pending_confirmations()
        task_pending = [p for p in pending if p.get("task_id") == task_id]
        if task_pending:
            await websocket.send_json({
                "type": "pending_confirmations",
                "data": task_pending,
                "timestamp": time.time(),
            })
        
        # 持续推送事件
        while True:
            try:
                # 等待事件，超时则发送心跳
                event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                
                # Review Fix v8: 检查消息发送速率
                event_type = event.get("type", "")
                event_priority = event.get("priority", get_event_priority(event_type))
                
                allowed, should_warn, rate_error = _ws_message_limiter.check_rate(connection_id)
                
                if not allowed:
                    # 超过突发限制，跳过低优先级事件
                    if event_priority > EventPriority.HIGH:
                        logger.debug(f"[Agent WS] Dropping {event_type} due to rate limit")
                        continue
                    # 高优先级事件仍然发送，但记录警告
                    logger.warning(f"[Agent WS] Rate limit exceeded but sending {event_type} (priority={event_priority})")
                
                if should_warn:
                    # 发送速率警告
                    await websocket.send_json({
                        "type": "rate_warning",
                        "data": {"message": "Message rate approaching limit"},
                        "timestamp": time.time(),
                    })
                
                await websocket.send_json(event)
                
                # 检查是否任务结束
                if event_type in ("completed", "failed", "cancelled", "stopped"):
                    logger.info(f"[Agent WS] Task {task_id} ended ({event_type}), closing")
                    # 发送最终状态
                    await websocket.send_json({
                        "type": "connection_closing",
                        "data": {"reason": f"Task {event_type}"},
                        "timestamp": time.time(),
                    })
                    break
                    
            except asyncio.TimeoutError:
                # 发送心跳保持连接
                try:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": time.time(),
                    })
                except Exception:
                    # 发送失败，连接可能已断开
                    break
                
    except WebSocketDisconnect:
        logger.info(f"[Agent WS] Disconnected for task: {task_id}")
    except Exception as e:
        logger.error(f"[Agent WS] Error for task {task_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)},
                "timestamp": time.time(),
            })
        except Exception:
            pass
    finally:
        host_agent_manager.unsubscribe(task_id, event_queue)
        # Review Fix v7: 释放连接配额
        if connection_acquired:
            await _ws_connection_limiter.release(client_host)
        # Review Fix v8: 注销消息速率限制器
        _ws_message_limiter.unregister_connection(connection_id)
        logger.debug(f"[Agent WS] Cleanup completed for task: {task_id}")
        logger.info(f"WebSocket cleanup for task: {task_id}")


# Debug endpoint to test pyautogui in backend process
@app.get("/test-pyautogui")
async def test_pyautogui():
    """Test pyautogui movement in backend process"""
    import pyautogui
    import ctypes
    
    results = {}
    
    # Check DPI awareness
    try:
        awareness = ctypes.c_int()
        ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
        results["dpi_awareness"] = awareness.value
    except:
        results["dpi_awareness"] = "unknown"
    
    # Current position
    before = pyautogui.position()
    results["before"] = f"({before.x}, {before.y})"
    
    # Try to move
    target_x, target_y = 500, 500
    pyautogui.moveTo(target_x, target_y)
    
    # Check after
    import time
    time.sleep(0.1)
    after = pyautogui.position()
    results["target"] = f"({target_x}, {target_y})"
    results["after"] = f"({after.x}, {after.y})"
    results["success"] = after.x == target_x and after.y == target_y
    
    # Check pyautogui settings
    results["failsafe"] = pyautogui.FAILSAFE
    results["pause"] = pyautogui.PAUSE
    results["screen_size"] = f"{pyautogui.size()}"
    
    return results


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
