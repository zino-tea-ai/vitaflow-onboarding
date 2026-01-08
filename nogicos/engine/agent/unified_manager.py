# -*- coding: utf-8 -*-
"""
NogicOS Unified Agent Manager
=============================

统一的 Agent 管理器，使用 ReActAgent 作为核心。
串联所有已有模块：PlanCache、Memory、ContextStore、Verification。

这是 NogicOS 的"大脑"，负责：
1. 任务调度和生命周期管理
2. 上下文注入（从 Hook 系统获取）
3. 计划缓存（复用成功模式）
4. 记忆管理（长期学习）
5. 执行验证（确保结果正确）
"""

import asyncio
import logging
import time
import uuid
from typing import Optional, Dict, List, Any, Callable, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 核心 Agent
from .react_agent import ReActAgent, AgentResult
from .modes import AgentMode

# 已有模块 - 现在要串联起来
# Plan Cache
try:
    from .plan_cache import PlanCache, get_plan_cache, CachedPlan
    PLAN_CACHE_AVAILABLE = True
except ImportError as e:
    PLAN_CACHE_AVAILABLE = False
    PlanCache = None
    get_plan_cache = None
    CachedPlan = None
    logger.warning(f"[UnifiedManager] PlanCache not available: {e}")

# Context Store - Hook 系统的上下文
try:
    from ..context import get_context_store, ContextStore, get_context_injector, ContextConfig
    CONTEXT_STORE_AVAILABLE = True
except ImportError:
    CONTEXT_STORE_AVAILABLE = False
    get_context_store = None
    get_context_injector = None
    ContextConfig = None
    logger.warning("[UnifiedManager] ContextStore not available")

# Memory - 长期记忆
try:
    from ..knowledge.store import SemanticMemoryStore, get_memory_store
    MEMORY_AVAILABLE = True
    get_memory_manager = get_memory_store  # 别名
except ImportError:
    try:
        from .imports import MEMORY_AVAILABLE, get_memory_store
        if MEMORY_AVAILABLE:
            get_memory_manager = get_memory_store
        else:
            get_memory_manager = None
    except ImportError:
        MEMORY_AVAILABLE = False
        get_memory_manager = None
        logger.warning("[UnifiedManager] Memory not available")

# Verification - 结果验证
try:
    from .verification import AnswerVerifier, VerifyResult
    VERIFICATION_AVAILABLE = True
except ImportError:
    VERIFICATION_AVAILABLE = False
    AnswerVerifier = None
    logger.warning("[UnifiedManager] Verification not available")

# WebSocket 广播
try:
    from ..server.websocket import StatusServer
except ImportError:
    StatusServer = None


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    task_text: str
    target_hwnds: Optional[List[int]] = None
    session_id: str = "default"
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # 执行统计
    cache_hit: bool = False
    iterations: int = 0
    verification_passed: bool = False


class UnifiedAgentManager:
    """
    统一的 Agent 管理器
    
    核心：ReActAgent（已串联 PlanCache、Memory）
    增强：ContextStore 注入、Verification 验证
    """
    
    def __init__(self):
        self._initialized = False
        self._lock = asyncio.Lock()
        
        # 核心 Agent
        self._agent: Optional[ReActAgent] = None
        
        # 已有模块
        self._plan_cache: Optional[PlanCache] = None
        self._context_store = None
        self._memory_manager = None
        self._verifier = None
        
        # 任务管理
        self._active_tasks: Dict[str, TaskInfo] = {}
        self._running_task: Optional[asyncio.Task] = None
        
        # WebSocket 广播
        self._status_server: Optional[StatusServer] = None
    
    async def initialize(self, status_server=None):
        """初始化管理器，串联所有模块"""
        if self._initialized:
            return
        
        self._status_server = status_server
        
        # 1. 初始化核心 Agent
        self._agent = ReActAgent(status_server=status_server)
        logger.info("[UnifiedManager] ReActAgent initialized")
        
        # 2. 串联 PlanCache（ReActAgent 内部已有，但我们也保留引用）
        if PLAN_CACHE_AVAILABLE:
            self._plan_cache = get_plan_cache()
            stats = self._plan_cache.get_stats()
            logger.info(f"[UnifiedManager] PlanCache connected: {stats.get('total_plans', 0)} cached plans")
        
        # 3. 串联 ContextStore（从 Hook 系统获取上下文）
        if CONTEXT_STORE_AVAILABLE and get_context_store:
            self._context_store = get_context_store()
            logger.info("[UnifiedManager] ContextStore connected")
        
        # 4. 串联 Memory（长期记忆）
        if MEMORY_AVAILABLE and get_memory_manager:
            try:
                self._memory_manager = get_memory_manager()
                logger.info("[UnifiedManager] Memory connected")
            except Exception as e:
                logger.warning(f"[UnifiedManager] Memory init failed: {e}")
        
        # 5. 串联 Verification（结果验证）
        if VERIFICATION_AVAILABLE and AnswerVerifier:
            self._verifier = AnswerVerifier()
            logger.info("[UnifiedManager] Verification connected")
        
        self._initialized = True
        logger.info("[UnifiedManager] All modules connected!")
    
    def _build_context_from_hooks(self, target_hwnds: Optional[List[int]] = None) -> str:
        """从 Hook 系统构建上下文，并使用 ContextInjector 增强"""
        context_parts = []
        
        # === 1. 从 Hook 系统获取实时上下文 ===
        if self._context_store:
            try:
                # 1a. 获取连接的窗口信息
                if hasattr(self._context_store, 'get_connected_windows'):
                    windows = self._context_store.get_connected_windows()
                    if windows:
                        context_parts.append("## 已连接的应用窗口")
                        for w in windows:
                            context_parts.append(f"- {w.get('title', 'Unknown')} (HWND: {w.get('hwnd')})")
                
                # 1b. 如果有目标窗口，获取其详细信息
                if target_hwnds:
                    context_parts.append(f"\n## 目标窗口: {target_hwnds}")
                
                # 1c. 获取最近的上下文
                if hasattr(self._context_store, 'format_context_prompt'):
                    hook_context = self._context_store.format_context_prompt()
                    if hook_context:
                        context_parts.append(f"\n## 环境上下文\n{hook_context}")
            except Exception as e:
                logger.warning(f"[UnifiedManager] Hook context failed: {e}")
        
        # === 2. 使用 ContextInjector 增强上下文（用户信息、记忆等）===
        if get_context_injector is not None and ContextConfig is not None:
            try:
                injector = get_context_injector()
                config = ContextConfig(
                    include_user_info=True,
                    include_workspace_layout=False,  # 避免过长
                    include_terminal_info=False,  # Hook 系统已有
                    include_memories=True,
                )
                # inject("") 返回纯上下文字符串
                enhanced = injector.inject("", session_id="default", config=config)
                if enhanced and enhanced.strip():
                    # 移除空的 user_query 包装
                    enhanced = enhanced.replace("<user_query>\n\n</user_query>", "").strip()
                    if enhanced:
                        context_parts.append(f"\n{enhanced}")
            except Exception as e:
                logger.warning(f"[UnifiedManager] ContextInjector failed: {e}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    async def start_task(
        self,
        task: str,
        target_hwnds: Optional[List[int]] = None,
        max_iterations: int = 50,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """
        启动任务 - 入口方法
        
        流程：
        1. 读取 ContextStore（知道当前窗口状态）
        2. 查询 PlanCache（有成功模式？复用！）
        3. 执行任务（通过 ReActAgent）
        4. 验证结果（通过 Verification）
        5. 学习（存入 PlanCache）
        """
        if not self._initialized:
            raise RuntimeError("UnifiedAgentManager not initialized")
        
        async with self._lock:
            # 检查是否有任务正在运行
            if self._running_task and not self._running_task.done():
                raise RuntimeError("Agent busy with another task")
            
            # 生成任务 ID
            task_id = f"task_{uuid.uuid4().hex[:12]}"
            
            # 创建任务信息
            task_info = TaskInfo(
                task_id=task_id,
                task_text=task,
                target_hwnds=target_hwnds,
                session_id=session_id,
                status="starting",
            )
            self._active_tasks[task_id] = task_info
            
            # 启动后台任务
            self._running_task = asyncio.create_task(
                self._execute_task(task_info),
                name=f"unified_task_{task_id}"
            )
            self._running_task.add_done_callback(
                lambda t: self._on_task_done(task_id, t)
            )
        
        return {
            "task_id": task_id,
            "status": "running",
        }
    
    async def _execute_task(self, task_info: TaskInfo):
        """执行任务的核心流程"""
        task_id = task_info.task_id
        task = task_info.task_text
        
        try:
            task_info.status = "running"
            await self._broadcast_event(task_id, "started", {
                "task_text": task,
                "target_hwnds": task_info.target_hwnds,
            })
            
            # === 1. 构建上下文（从 Hook 系统）===
            context = self._build_context_from_hooks(task_info.target_hwnds)
            if context:
                logger.info(f"[UnifiedManager] Context injected: {len(context)} chars")
            
            # === 2. 检查 PlanCache（ReActAgent 内部也会检查，这里是额外的日志）===
            cache_hit = False
            if self._plan_cache:
                try:
                    cache_result = self._plan_cache.find_similar(task, threshold=0.80)
                    if cache_result:
                        cached_plan, similarity = cache_result  # 解包元组
                        if cached_plan.success:
                            cache_hit = True
                            task_info.cache_hit = True
                            logger.info(f"[UnifiedManager] Cache HIT! (similarity={similarity:.2f}) Reusing plan from: {cached_plan.task[:50]}...")
                            await self._broadcast_event(task_id, "cache_hit", {
                                "original_task": cached_plan.task,
                                "use_count": cached_plan.use_count,
                                "similarity": similarity,
                            })
                except Exception as e:
                    logger.warning(f"[UnifiedManager] PlanCache lookup failed: {e}")
            
            # === 3. 执行任务（通过 ReActAgent.run_with_planning）===
            # 关键改动：使用 run_with_planning 激活已有的：
            # - 复杂度分类（内部第 3082 行）
            # - 逐步执行（第 3107-3143 行）
            # - 失败重新规划（第 3137 行调用 planner.replan）
            start_time = time.time()
            
            result: AgentResult = await self._agent.run_with_planning(
                task=task,
                session_id=task_info.session_id,
                context=context if context else None,
            )
            
            execution_time = time.time() - start_time
            task_info.iterations = result.iterations if hasattr(result, 'iterations') else 0
            
            # === 4. 验证结果 ===
            verification_passed = True
            if self._verifier and result.success:
                try:
                    # 提取工具输出用于验证（tool_calls 中的结果）
                    tool_outputs = []
                    if result.tool_calls:
                        for tc in result.tool_calls:
                            if "result" in tc:
                                tool_outputs.append(str(tc["result"]))
                    
                    verify_result = self._verifier.verify(
                        answer=result.response or "",  # AgentResult 用的是 response
                        task=task,
                        tool_outputs=tool_outputs,
                    )
                    verification_passed = verify_result.is_valid
                    task_info.verification_passed = verification_passed
                    
                    if not verification_passed:
                        logger.warning(f"[UnifiedManager] Verification failed: {verify_result.message}")
                        await self._broadcast_event(task_id, "verification_failed", {
                            "message": verify_result.message,
                            "suggestions": verify_result.suggestions,
                        })
                except Exception as e:
                    logger.warning(f"[UnifiedManager] Verification error: {e}")
            
            # === 5. 学习（存入 PlanCache）===
            if result.success and verification_passed and self._plan_cache:
                try:
                    # 构建计划步骤
                    plan_steps = []
                    if hasattr(result, 'tool_calls') and result.tool_calls:
                        for tc in result.tool_calls:
                            plan_steps.append({
                                "tool": tc.get("name", "unknown"),
                                "args": tc.get("input", {}),
                            })
                    
                    if plan_steps:
                        self._plan_cache.cache_plan(
                            task=task,
                            plan_steps=plan_steps,
                            execution_time=execution_time,
                            success=True,
                        )
                        logger.info(f"[UnifiedManager] Plan cached: {len(plan_steps)} steps")
                except Exception as e:
                    logger.warning(f"[UnifiedManager] Failed to cache plan: {e}")
            
            # === 6. 完成 ===
            task_info.status = "completed" if result.success else "failed"
            task_info.completed_at = time.time()
            task_info.result = {
                "success": result.success,
                "response": result.response,  # AgentResult 用的是 response
                "iterations": task_info.iterations,
                "execution_time": execution_time,
                "cache_hit": cache_hit,
                "verification_passed": verification_passed,
            }
            
            await self._broadcast_event(task_id, "completed", task_info.result)
            
        except asyncio.CancelledError:
            logger.info(f"[UnifiedManager] Task {task_id} cancelled")
            task_info.status = "cancelled"
            await self._broadcast_event(task_id, "cancelled", {"reason": "Task cancelled"})
            raise
            
        except Exception as e:
            logger.error(f"[UnifiedManager] Task {task_id} failed: {e}", exc_info=True)
            task_info.status = "failed"
            task_info.error = str(e)
            await self._broadcast_event(task_id, "failed", {
                "error": str(e),
                "error_type": type(e).__name__,
            })
    
    def _on_task_done(self, task_id: str, task: asyncio.Task):
        """任务完成回调"""
        try:
            exc = task.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                logger.error(f"[UnifiedManager] Task {task_id} exception: {exc}")
        except asyncio.InvalidStateError:
            pass
    
    async def _broadcast_event(self, task_id: str, event_type: str, data: Dict[str, Any]):
        """广播事件到 WebSocket"""
        if self._status_server:
            try:
                await self._status_server.broadcast({
                    "type": f"agent_{event_type}",
                    "task_id": task_id,
                    "timestamp": time.time(),
                    **data,
                })
            except Exception as e:
                logger.warning(f"[UnifiedManager] Broadcast failed: {e}")
    
    async def stop_task(self, task_id: str, reason: str = "User requested") -> Dict[str, Any]:
        """停止任务"""
        async with self._lock:
            if task_id not in self._active_tasks:
                return {"success": False, "message": f"Task {task_id} not found"}
            
            if self._running_task and not self._running_task.done():
                self._running_task.cancel()
                try:
                    await self._running_task
                except asyncio.CancelledError:
                    pass
            
            self._active_tasks[task_id].status = "stopped"
            return {"success": True, "status": "stopped", "reason": reason}
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        if task_id not in self._active_tasks:
            return {"error": f"Task {task_id} not found"}
        
        task_info = self._active_tasks[task_id]
        return {
            "task_id": task_info.task_id,
            "status": task_info.status,
            "task_text": task_info.task_text,
            "started_at": task_info.started_at,
            "completed_at": task_info.completed_at,
            "result": task_info.result,
            "error": task_info.error,
            "cache_hit": task_info.cache_hit,
            "iterations": task_info.iterations,
            "verification_passed": task_info.verification_passed,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "initialized": self._initialized,
            "modules": {
                "plan_cache": PLAN_CACHE_AVAILABLE,
                "context_store": CONTEXT_STORE_AVAILABLE,
                "memory": MEMORY_AVAILABLE,
                "verification": VERIFICATION_AVAILABLE,
            },
            "total_tasks": len(self._active_tasks),
        }
        
        if self._plan_cache:
            stats["plan_cache_stats"] = self._plan_cache.get_stats()
        
        return stats
    
    async def close(self):
        """关闭管理器"""
        if self._running_task and not self._running_task.done():
            self._running_task.cancel()
            try:
                await self._running_task
            except asyncio.CancelledError:
                pass
        
        self._initialized = False
        logger.info("[UnifiedManager] Closed")


# 全局实例
_unified_manager: Optional[UnifiedAgentManager] = None


def get_unified_manager() -> UnifiedAgentManager:
    """获取全局 UnifiedAgentManager 实例"""
    global _unified_manager
    if _unified_manager is None:
        _unified_manager = UnifiedAgentManager()
    return _unified_manager
