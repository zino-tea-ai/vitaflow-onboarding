"""
NogicOS 并发管理器
==================

控制 Agent 系统的并发资源，包括：
1. 任务槽位管理 - 限制同时运行的任务数
2. 窗口独占锁 - 防止多任务同时操作同一窗口
3. API 调用限流 - 避免触发速率限制

参考:
- ByteBot 并发控制
- asyncio Semaphore + Lock
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional, Dict, Set, TYPE_CHECKING
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from .host_agent import AgentConfig

logger = logging.getLogger(__name__)


@dataclass
class ConcurrencyConfig:
    """
    并发配置
    
    独立配置类，可与 AgentConfig 分离使用
    """
    # 任务并发
    max_concurrent_tasks: int = 3
    
    # API 限流
    max_api_concurrency: int = 5
    
    # 窗口锁超时
    window_lock_timeout_s: float = 300.0  # 5 分钟
    
    # API 调用间隔（避免触发速率限制）
    min_api_interval_ms: int = 100


@dataclass
class TaskSlotInfo:
    """任务槽位信息"""
    task_id: str
    acquired_at: datetime
    target_hwnds: Set[int] = field(default_factory=set)


@dataclass
class WindowLockInfo:
    """窗口锁信息"""
    hwnd: int
    task_id: str
    acquired_at: datetime


class ConcurrencyManager:
    """
    并发管理器
    
    负责管理：
    1. 任务槽位 - 限制同时运行的任务数量
    2. 窗口锁 - 确保同一窗口不被多个任务同时操作
    3. API 限流 - 使用 Semaphore 限制并发 API 调用
    
    使用示例:
    ```python
    manager = ConcurrencyManager(config)
    
    # 获取任务槽位
    if await manager.acquire_task_slot(task_id):
        try:
            # 获取窗口锁
            await manager.acquire_window(hwnd)
            
            # 执行 API 调用（带限流）
            async with manager.api_slot():
                result = await llm_call()
        finally:
            manager.release_window(hwnd)
            manager.release_task_slot(task_id)
    ```
    """
    
    def __init__(
        self, 
        config: Optional[ConcurrencyConfig] = None,
    ):
        """
        初始化并发管理器
        
        Args:
            config: 并发配置（可选）
        """
        self.config = config or ConcurrencyConfig()
        
        # 任务槽位
        self._active_tasks: Dict[str, TaskSlotInfo] = {}
        self._task_lock = asyncio.Lock()
        
        # 窗口锁
        self._window_locks: Dict[int, asyncio.Lock] = {}
        self._window_owners: Dict[int, WindowLockInfo] = {}
        self._window_meta_lock = asyncio.Lock()
        
        # API 限流
        self._api_semaphore = asyncio.Semaphore(self.config.max_api_concurrency)
        self._last_api_call: Optional[datetime] = None
        self._api_call_lock = asyncio.Lock()
        
        logger.info(
            f"ConcurrencyManager initialized: "
            f"max_tasks={self.config.max_concurrent_tasks}, "
            f"max_api={self.config.max_api_concurrency}"
        )
    
    # ========== 任务槽位管理 ==========
    
    async def acquire_task_slot(
        self, 
        task_id: str,
        target_hwnds: Optional[Set[int]] = None,
    ) -> bool:
        """
        获取任务槽位
        
        Args:
            task_id: 任务 ID
            target_hwnds: 目标窗口集合
            
        Returns:
            是否成功获取槽位
        """
        async with self._task_lock:
            # 检查是否已有该任务
            if task_id in self._active_tasks:
                logger.warning(f"Task {task_id} already has a slot")
                return True
            
            # 检查槽位数量
            if len(self._active_tasks) >= self.config.max_concurrent_tasks:
                logger.info(
                    f"No available task slots: "
                    f"{len(self._active_tasks)}/{self.config.max_concurrent_tasks}"
                )
                return False
            
            # 分配槽位
            self._active_tasks[task_id] = TaskSlotInfo(
                task_id=task_id,
                acquired_at=datetime.now(),
                target_hwnds=target_hwnds or set(),
            )
            
            logger.debug(
                f"Task slot acquired: {task_id} "
                f"({len(self._active_tasks)}/{self.config.max_concurrent_tasks})"
            )
            return True
    
    def release_task_slot(self, task_id: str):
        """
        释放任务槽位
        
        Args:
            task_id: 任务 ID
        """
        if task_id in self._active_tasks:
            del self._active_tasks[task_id]
            logger.debug(
                f"Task slot released: {task_id} "
                f"({len(self._active_tasks)}/{self.config.max_concurrent_tasks})"
            )
    
    def get_active_tasks(self) -> Dict[str, TaskSlotInfo]:
        """获取活动任务列表"""
        return dict(self._active_tasks)
    
    @property
    def available_slots(self) -> int:
        """可用槽位数"""
        return self.config.max_concurrent_tasks - len(self._active_tasks)
    
    # ========== 窗口锁管理 ==========
    
    async def acquire_window(
        self, 
        hwnd: int,
        task_id: str = "",
        timeout: Optional[float] = None,
    ) -> bool:
        """
        获取窗口独占锁
        
        Args:
            hwnd: 窗口句柄
            task_id: 请求的任务 ID
            timeout: 超时时间（秒），None 表示使用默认值
            
        Returns:
            是否成功获取锁
        """
        timeout = timeout or self.config.window_lock_timeout_s
        
        # 获取或创建窗口锁
        async with self._window_meta_lock:
            if hwnd not in self._window_locks:
                self._window_locks[hwnd] = asyncio.Lock()
            lock = self._window_locks[hwnd]
        
        try:
            # 尝试获取锁
            acquired = await asyncio.wait_for(
                lock.acquire(),
                timeout=timeout,
            )
            
            if acquired:
                self._window_owners[hwnd] = WindowLockInfo(
                    hwnd=hwnd,
                    task_id=task_id,
                    acquired_at=datetime.now(),
                )
                logger.debug(f"Window lock acquired: hwnd={hwnd}, task={task_id}")
            
            return acquired
            
        except asyncio.TimeoutError:
            owner = self._window_owners.get(hwnd)
            owner_task = owner.task_id if owner else "unknown"
            logger.warning(
                f"Window lock timeout: hwnd={hwnd}, "
                f"current_owner={owner_task}"
            )
            return False
    
    def release_window(self, hwnd: int):
        """
        释放窗口锁
        
        Args:
            hwnd: 窗口句柄
        """
        if hwnd in self._window_locks:
            lock = self._window_locks[hwnd]
            if lock.locked():
                lock.release()
                self._window_owners.pop(hwnd, None)
                logger.debug(f"Window lock released: hwnd={hwnd}")
    
    def get_window_owner(self, hwnd: int) -> Optional[str]:
        """
        获取窗口当前所有者
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            拥有该窗口锁的任务 ID，或 None
        """
        info = self._window_owners.get(hwnd)
        return info.task_id if info else None
    
    def is_window_locked(self, hwnd: int) -> bool:
        """检查窗口是否被锁定"""
        if hwnd in self._window_locks:
            return self._window_locks[hwnd].locked()
        return False
    
    @asynccontextmanager
    async def window_lock(self, hwnd: int, task_id: str = ""):
        """
        窗口锁上下文管理器
        
        使用示例:
        ```python
        async with manager.window_lock(hwnd, task_id):
            # 独占操作窗口
            await perform_action(hwnd)
        ```
        """
        acquired = await self.acquire_window(hwnd, task_id)
        if not acquired:
            raise RuntimeError(f"Failed to acquire window lock: hwnd={hwnd}")
        try:
            yield
        finally:
            self.release_window(hwnd)
    
    # ========== API 限流 ==========
    
    @asynccontextmanager
    async def api_slot(self):
        """
        API 调用槽位（限流）
        
        使用 Semaphore 限制并发 API 调用数量，
        并确保调用间隔不小于 min_api_interval_ms
        
        使用示例:
        ```python
        async with manager.api_slot():
            result = await claude_api.call()
        ```
        """
        await self._api_semaphore.acquire()
        try:
            # 确保调用间隔
            async with self._api_call_lock:
                if self._last_api_call is not None:
                    elapsed = (datetime.now() - self._last_api_call).total_seconds() * 1000
                    if elapsed < self.config.min_api_interval_ms:
                        wait_ms = self.config.min_api_interval_ms - elapsed
                        await asyncio.sleep(wait_ms / 1000)
                
                self._last_api_call = datetime.now()
            
            yield
            
        finally:
            self._api_semaphore.release()
    
    @property
    def available_api_slots(self) -> int:
        """可用 API 槽位数（近似值）"""
        # Semaphore 没有直接获取当前值的方法，这是近似值
        return self._api_semaphore._value  # type: ignore
    
    # ========== 批量操作 ==========
    
    async def acquire_windows(
        self, 
        hwnds: Set[int],
        task_id: str,
    ) -> bool:
        """
        批量获取窗口锁
        
        要么全部获取成功，要么全部不获取（原子性）
        
        Args:
            hwnds: 窗口句柄集合
            task_id: 任务 ID
            
        Returns:
            是否全部获取成功
        """
        acquired_hwnds: Set[int] = set()
        
        try:
            for hwnd in hwnds:
                if await self.acquire_window(hwnd, task_id, timeout=10.0):
                    acquired_hwnds.add(hwnd)
                else:
                    # 获取失败，回滚
                    raise RuntimeError(f"Failed to acquire window: {hwnd}")
            
            return True
            
        except Exception:
            # 回滚已获取的锁
            for hwnd in acquired_hwnds:
                self.release_window(hwnd)
            return False
    
    def release_windows(self, hwnds: Set[int]):
        """批量释放窗口锁"""
        for hwnd in hwnds:
            self.release_window(hwnd)
    
    # ========== 资源清理 ==========
    
    async def cleanup_stale_locks(self, max_age_s: float = 600.0):
        """
        清理过期的窗口锁
        
        防止任务异常退出导致的锁泄漏
        
        Args:
            max_age_s: 最大锁持有时间（秒）
        """
        now = datetime.now()
        stale_hwnds = []
        
        for hwnd, info in self._window_owners.items():
            age = (now - info.acquired_at).total_seconds()
            if age > max_age_s:
                stale_hwnds.append(hwnd)
                logger.warning(
                    f"Releasing stale window lock: hwnd={hwnd}, "
                    f"task={info.task_id}, age={age:.1f}s"
                )
        
        for hwnd in stale_hwnds:
            self.release_window(hwnd)
    
    def reset(self):
        """
        重置所有状态（用于测试）
        
        警告：会释放所有锁和槽位
        """
        self._active_tasks.clear()
        
        for hwnd in list(self._window_locks.keys()):
            self.release_window(hwnd)
        self._window_locks.clear()
        self._window_owners.clear()
        
        self._last_api_call = None
        
        logger.info("ConcurrencyManager reset")
    
    def get_stats(self) -> Dict:
        """获取并发统计信息"""
        return {
            "active_tasks": len(self._active_tasks),
            "max_tasks": self.config.max_concurrent_tasks,
            "locked_windows": len(self._window_owners),
            "api_semaphore_value": self._api_semaphore._value,  # type: ignore
            "max_api_concurrency": self.config.max_api_concurrency,
        }
    
    def __repr__(self) -> str:
        return (
            f"ConcurrencyManager("
            f"tasks={len(self._active_tasks)}/{self.config.max_concurrent_tasks}, "
            f"windows={len(self._window_owners)})"
        )


# ========== 单例模式 ==========

_concurrency_manager: Optional[ConcurrencyManager] = None


def get_concurrency_manager(
    config: Optional[ConcurrencyConfig] = None,
) -> ConcurrencyManager:
    """获取全局并发管理器（单例）"""
    global _concurrency_manager
    if _concurrency_manager is None:
        _concurrency_manager = ConcurrencyManager(config)
    return _concurrency_manager


def set_concurrency_manager(manager: ConcurrencyManager):
    """设置全局并发管理器（用于测试）"""
    global _concurrency_manager
    _concurrency_manager = manager
