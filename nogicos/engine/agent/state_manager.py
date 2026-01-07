"""
NogicOS 状态管理器
==================

建立单一状态写入点，解决状态不一致问题。

设计原则:
1. 所有状态修改必须通过此类
2. 修改前自动验证合法性
3. 修改后自动持久化 + 事件广播

参考:
- LangGraph Checkpointer (get_state / update_state)
- UFO Blackboard (状态共享)
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from .events import AgentEvent, EventType
from .event_bus import EventBus, get_event_bus
from .async_db import AsyncTaskStore
from .types import TaskStatus, AgentStatus  # 从 types.py 统一导入

logger = logging.getLogger(__name__)


class InvalidTransitionError(Exception):
    """非法状态转换"""
    pass


class TaskNotFoundError(Exception):
    """任务不存在"""
    pass


@dataclass
class TaskState:
    """任务完整状态"""
    task_id: str
    status: TaskStatus
    agent_status: AgentStatus
    iteration: int
    current_hwnd: Optional[int]
    messages: List[Dict[str, Any]]
    last_tool_result: Optional[Dict[str, Any]]
    error: Optional[str]


class TaskStateManager:
    """
    任务状态管理器 - 唯一的状态修改入口
    
    使用示例:
    ```python
    manager = TaskStateManager(task_store, event_bus)
    
    # 状态转换
    await manager.transition(task_id, TaskStatus.RUNNING)
    
    # 获取状态
    status = await manager.get_status(task_id)
    
    # 获取完整状态（对齐 LangGraph）
    state = await manager.get_state(task_id)
    ```
    """
    
    # 合法的状态转换
    VALID_TRANSITIONS: Dict[TaskStatus, List[TaskStatus]] = {
        TaskStatus.PENDING: [TaskStatus.RUNNING, TaskStatus.CANCELLED],
        TaskStatus.RUNNING: [
            TaskStatus.COMPLETED, 
            TaskStatus.FAILED, 
            TaskStatus.NEEDS_HELP, 
            TaskStatus.INTERRUPTED, 
            TaskStatus.PAUSED
        ],
        TaskStatus.PAUSED: [TaskStatus.RUNNING, TaskStatus.CANCELLED],
        TaskStatus.INTERRUPTED: [TaskStatus.RUNNING, TaskStatus.CANCELLED],
        TaskStatus.NEEDS_HELP: [TaskStatus.RUNNING, TaskStatus.CANCELLED],
        TaskStatus.COMPLETED: [],  # 终态
        TaskStatus.FAILED: [],     # 终态
        TaskStatus.CANCELLED: [],  # 终态
    }
    
    def __init__(
        self, 
        task_store: AsyncTaskStore, 
        event_bus: Optional[EventBus] = None,
    ):
        """
        初始化状态管理器
        
        Args:
            task_store: 异步任务存储
            event_bus: 事件总线（默认使用全局单例）
        """
        self.task_store = task_store
        self.event_bus = event_bus or get_event_bus()
        self._cache: Dict[str, TaskStatus] = {}  # 内存缓存
        self._agent_status_cache: Dict[str, AgentStatus] = {}
    
    async def create_task(
        self, 
        task_id: str, 
        task_text: str,
        target_hwnds: Optional[List[int]] = None,
    ) -> bool:
        """
        创建新任务
        
        Args:
            task_id: 任务 ID
            task_text: 任务描述
            target_hwnds: 目标窗口句柄列表
            
        Returns:
            是否创建成功
        """
        # 创建任务记录
        await self.task_store.create_task(task_id, task_text, target_hwnds)
        
        # 初始化缓存
        self._cache[task_id] = TaskStatus.PENDING
        self._agent_status_cache[task_id] = AgentStatus.IDLE
        
        # 发布事件
        await self.event_bus.publish(AgentEvent.create(
            event_type=EventType.TASK_CREATED,
            task_id=task_id,
            payload={
                "task_text": task_text,
                "target_hwnds": target_hwnds or [],
            }
        ))
        
        logger.info(f"Task created: {task_id}")
        return True
    
    async def transition(
        self, 
        task_id: str, 
        new_status: TaskStatus,
        reason: Optional[str] = None,
    ) -> bool:
        """
        状态转换 - 唯一的状态修改入口
        
        Args:
            task_id: 任务 ID
            new_status: 新状态
            reason: 转换原因（可选）
            
        Returns:
            是否转换成功
            
        Raises:
            TaskNotFoundError: 任务不存在
            InvalidTransitionError: 非法状态转换
        """
        # 1. 获取当前状态
        current = await self._get_current_status(task_id)
        if current is None:
            raise TaskNotFoundError(f"Task {task_id} not found")
        
        # 2. 检查是否是同一状态（幂等）
        if current == new_status:
            logger.debug(f"Task {task_id} already in status {new_status.value}")
            return True
        
        # 3. 验证转换合法性
        valid_targets = self.VALID_TRANSITIONS.get(current, [])
        if new_status not in valid_targets:
            raise InvalidTransitionError(
                f"Invalid transition: {current.value} -> {new_status.value}. "
                f"Valid targets: {[s.value for s in valid_targets]}"
            )
        
        # 4. 持久化
        await self.task_store.update_status(task_id, new_status.value)
        
        # 5. 更新缓存
        self._cache[task_id] = new_status
        
        # 6. 更新 Agent 状态
        agent_status = self._derive_agent_status(new_status)
        self._agent_status_cache[task_id] = agent_status
        
        # 7. 发布事件
        event_type = self._status_to_event_type(new_status)
        await self.event_bus.publish(AgentEvent.create(
            event_type=event_type,
            task_id=task_id,
            payload={
                "status": new_status.value,
                "previous_status": current.value,
                "reason": reason,
                "agent_status": agent_status.value,
            }
        ))
        
        logger.info(f"Task {task_id}: {current.value} -> {new_status.value}")
        return True
    
    async def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        获取任务状态（优先内存缓存）
        
        Args:
            task_id: 任务 ID
            
        Returns:
            任务状态，或 None（任务不存在）
        """
        if task_id in self._cache:
            return self._cache[task_id]
        return await self._get_current_status(task_id)
    
    async def get_agent_status(self, task_id: str) -> Optional[AgentStatus]:
        """获取 Agent 状态"""
        if task_id in self._agent_status_cache:
            return self._agent_status_cache[task_id]
        
        task_status = await self.get_status(task_id)
        if task_status:
            return self._derive_agent_status(task_status)
        return None
    
    async def get_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取完整状态（对齐 LangGraph）
        
        Args:
            task_id: 任务 ID
            
        Returns:
            完整状态字典
        """
        task = await self.task_store.get_task(task_id)
        if not task:
            return None
        
        checkpoint = await self.task_store.restore_checkpoint(task_id)
        messages = await self.task_store.get_messages(task_id)
        
        # 从缓存获取状态，否则安全解析
        if task_id in self._cache:
            status = self._cache[task_id]
        else:
            status = await self._get_current_status(task_id) or TaskStatus.PENDING
        
        return {
            "task": task,
            "checkpoint": checkpoint,
            "messages": messages,
            "status": status,
            "agent_status": self._agent_status_cache.get(task_id, AgentStatus.IDLE),
        }
    
    async def update_state(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新状态（对齐 LangGraph）
        
        Args:
            task_id: 任务 ID
            updates: 更新字典
            
        Returns:
            是否更新成功
        """
        # 状态更新
        if "status" in updates:
            status = updates["status"]
            if isinstance(status, str):
                status = TaskStatus(status)
            await self.transition(task_id, status)
        
        # 检查点更新
        if "checkpoint" in updates:
            await self.task_store.save_checkpoint(
                task_id, 
                updates["checkpoint"].get("iteration", 0),
                updates["checkpoint"].get("state", {})
            )
        
        # 消息更新
        if "messages" in updates:
            for msg in updates["messages"]:
                await self.task_store.save_message(
                    task_id,
                    msg.get("role", "user"),
                    msg.get("content", "")
                )
        
        return True
    
    async def set_agent_status(self, task_id: str, agent_status: AgentStatus):
        """
        设置 Agent 状态（不改变任务状态）
        
        用于细粒度状态控制，如：等待确认、思考中等
        """
        self._agent_status_cache[task_id] = agent_status
        
        # 根据 AgentStatus 选择正确的事件类型
        event_type_map = {
            AgentStatus.CONFIRM: EventType.USER_CONFIRM_REQUIRED,  # 明确需要用户确认
            AgentStatus.IDLE: EventType.AGENT_IDLE,
            AgentStatus.PAUSED: EventType.AGENT_WAITING,
            AgentStatus.ACTIVE: EventType.AGENT_EXECUTING,
        }
        event_type = event_type_map.get(agent_status, EventType.AGENT_EXECUTING)
        
        await self.event_bus.publish(AgentEvent.create(
            event_type=event_type,
            task_id=task_id,
            payload={"agent_status": agent_status.value}
        ))
    
    async def _get_current_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        从持久化存储获取状态
        
        对未知状态值进行兜底处理，避免版本迁移或数据异常导致崩溃
        """
        task = await self.task_store.get_task(task_id)
        if not task:
            return None
        
        status_value = task.get("status")
        if status_value is None:
            logger.warning(f"Task {task_id} has no status, defaulting to PENDING")
            status = TaskStatus.PENDING
        else:
            try:
                status = TaskStatus(status_value)
            except ValueError:
                # 未知状态值，记录警告并回退到 FAILED
                logger.warning(
                    f"Task {task_id} has unknown status '{status_value}', "
                    f"defaulting to FAILED for safety"
                )
                status = TaskStatus.FAILED
                # 持久化修正后的状态
                await self.task_store.update_status(task_id, status.value)
        
        self._cache[task_id] = status
        return status
    
    def _status_to_event_type(self, status: TaskStatus) -> EventType:
        """状态映射到事件类型"""
        mapping = {
            TaskStatus.RUNNING: EventType.TASK_STARTED,
            TaskStatus.COMPLETED: EventType.TASK_COMPLETED,
            TaskStatus.FAILED: EventType.TASK_FAILED,
            TaskStatus.INTERRUPTED: EventType.TASK_INTERRUPTED,
            TaskStatus.PAUSED: EventType.TASK_PAUSED,
            TaskStatus.CANCELLED: EventType.TASK_CANCELLED,
        }
        return mapping.get(status, EventType.TASK_STARTED)
    
    def _derive_agent_status(self, task_status: TaskStatus) -> AgentStatus:
        """从任务状态推导 Agent 状态"""
        if task_status == TaskStatus.RUNNING:
            return AgentStatus.ACTIVE
        elif task_status == TaskStatus.PAUSED:
            return AgentStatus.PAUSED
        elif task_status == TaskStatus.NEEDS_HELP:
            return AgentStatus.CONFIRM
        else:
            return AgentStatus.IDLE
    
    def is_terminal(self, status: TaskStatus) -> bool:
        """检查是否为终态"""
        return status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    def clear_cache(self, task_id: Optional[str] = None):
        """
        清除缓存
        
        Args:
            task_id: 指定任务 ID，或 None 清除所有
        """
        if task_id:
            self._cache.pop(task_id, None)
            self._agent_status_cache.pop(task_id, None)
        else:
            self._cache.clear()
            self._agent_status_cache.clear()


# ========== 单例模式 ==========

_state_manager: Optional[TaskStateManager] = None


async def get_state_manager(task_store: Optional[AsyncTaskStore] = None) -> TaskStateManager:
    """获取全局状态管理器（单例）"""
    global _state_manager
    if _state_manager is None:
        if task_store is None:
            from .async_db import get_task_store
            task_store = await get_task_store()
        _state_manager = TaskStateManager(task_store)
    return _state_manager


def set_state_manager(manager: TaskStateManager):
    """设置全局状态管理器（用于测试）"""
    global _state_manager
    _state_manager = manager
