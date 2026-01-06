"""
NogicOS Blackboard 共享状态
===========================

实现 Agent 间共享状态的黑板模式。

参考:
- UFO Blackboard (状态共享)
- LangGraph State (get_state / update_state)
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from enum import Enum
import asyncio
import logging

if TYPE_CHECKING:
    from .types import ToolResult

logger = logging.getLogger(__name__)


class RequestStatus(Enum):
    """请求状态 - 参考 UFO"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_HELP = "needs_help"


@dataclass
class SubTask:
    """
    子任务定义
    
    HostAgent 分解任务后产生的子任务单元
    """
    id: str
    description: str
    target_hwnd: Optional[int] = None
    app_type: Optional[str] = None
    status: RequestStatus = RequestStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    assigned_agent: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def mark_completed(self, result: str):
        """标记完成"""
        self.status = RequestStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now()
    
    def mark_failed(self, error: str):
        """标记失败"""
        self.status = RequestStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "id": self.id,
            "description": self.description,
            "target_hwnd": self.target_hwnd,
            "app_type": self.app_type,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "assigned_agent": self.assigned_agent,
            "dependencies": self.dependencies,
        }


@dataclass
class AgentMessage:
    """
    Agent 间消息
    
    用于 HostAgent 和 AppAgent 间通信
    """
    from_agent: str
    to_agent: str
    content: str
    message_type: str = "info"  # info, request, response, error
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_agent,
            "to": self.to_agent,
            "content": self.content,
            "type": self.message_type,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class Blackboard:
    """
    黑板 - Agent 间共享状态
    
    参考 UFO Blackboard，提供：
    1. 子任务管理
    2. 执行结果共享
    3. Agent 间消息传递
    4. 全局上下文
    
    使用示例:
    ```python
    blackboard = Blackboard()
    
    # HostAgent 添加子任务
    blackboard.add_subtask(SubTask(
        id="sub1",
        description="打开浏览器",
        app_type="browser"
    ))
    
    # AppAgent 更新结果
    blackboard.set_result("sub1", "浏览器已打开")
    
    # 检查是否所有子任务完成
    if blackboard.all_completed:
        print("任务完成")
    ```
    """
    
    def __init__(self, task_id: Optional[str] = None):
        """
        初始化黑板
        
        Args:
            task_id: 关联的任务 ID
        """
        self.task_id = task_id
        self._lock = asyncio.Lock()
        
        # 子任务管理
        self._subtasks: Dict[str, SubTask] = {}
        self._subtask_order: List[str] = []  # 保持顺序
        
        # 执行结果
        self._results: Dict[str, Any] = {}
        
        # Agent 消息
        self._messages: List[AgentMessage] = []
        
        # 全局上下文
        self._context: Dict[str, Any] = {}
        
        # 执行轨迹
        self._trajectory: List[Dict[str, Any]] = []
        
        # 请求状态
        self.request_status: RequestStatus = RequestStatus.PENDING
        self.request_error: Optional[str] = None
    
    # ========== 子任务管理 ==========
    
    async def add_subtask(self, subtask: SubTask) -> bool:
        """
        添加子任务
        
        Args:
            subtask: 子任务
            
        Returns:
            是否添加成功
        """
        async with self._lock:
            if subtask.id in self._subtasks:
                logger.warning(f"Subtask {subtask.id} already exists")
                return False
            
            self._subtasks[subtask.id] = subtask
            self._subtask_order.append(subtask.id)
            logger.debug(f"Added subtask: {subtask.id}")
            return True
    
    async def add_subtasks(self, subtasks: List[SubTask]):
        """批量添加子任务"""
        for subtask in subtasks:
            await self.add_subtask(subtask)
    
    async def get_subtask(self, subtask_id: str) -> Optional[SubTask]:
        """获取子任务"""
        return self._subtasks.get(subtask_id)
    
    async def update_subtask_status(
        self, 
        subtask_id: str, 
        status: RequestStatus,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """
        更新子任务状态
        
        Args:
            subtask_id: 子任务 ID
            status: 新状态
            result: 结果（成功时）
            error: 错误信息（失败时）
        """
        async with self._lock:
            subtask = self._subtasks.get(subtask_id)
            if not subtask:
                logger.warning(f"Subtask {subtask_id} not found")
                return
            
            subtask.status = status
            if status == RequestStatus.COMPLETED:
                subtask.mark_completed(result or "")
            elif status == RequestStatus.FAILED:
                subtask.mark_failed(error or "Unknown error")
            
            logger.debug(f"Subtask {subtask_id} status: {status.value}")
    
    async def get_next_subtask(self) -> Optional[SubTask]:
        """
        获取下一个待执行的子任务
        
        考虑依赖关系，返回依赖已满足的待执行任务
        """
        async with self._lock:
            for subtask_id in self._subtask_order:
                subtask = self._subtasks[subtask_id]
                
                # 跳过非 pending 状态
                if subtask.status != RequestStatus.PENDING:
                    continue
                
                # 检查依赖
                deps_satisfied = all(
                    self._subtasks.get(dep_id, SubTask(id="", description="")).status 
                    == RequestStatus.COMPLETED
                    for dep_id in subtask.dependencies
                )
                
                if deps_satisfied:
                    return subtask
            
            return None
    
    async def get_pending_subtasks(self) -> List[SubTask]:
        """获取所有待执行的子任务"""
        return [
            st for st in self._subtasks.values()
            if st.status == RequestStatus.PENDING
        ]
    
    @property
    def all_completed(self) -> bool:
        """是否所有子任务都已完成"""
        if not self._subtasks:
            return False
        return all(
            st.status in [RequestStatus.COMPLETED, RequestStatus.FAILED]
            for st in self._subtasks.values()
        )
    
    @property
    def has_failures(self) -> bool:
        """是否有失败的子任务"""
        return any(
            st.status == RequestStatus.FAILED
            for st in self._subtasks.values()
        )
    
    # ========== 结果管理 ==========
    
    async def set_result(self, key: str, value: Any):
        """
        设置结果
        
        Args:
            key: 结果键（通常是子任务 ID）
            value: 结果值
        """
        async with self._lock:
            self._results[key] = value
            logger.debug(f"Set result: {key}")
    
    async def get_result(self, key: str) -> Optional[Any]:
        """获取结果"""
        return self._results.get(key)
    
    async def get_all_results(self) -> Dict[str, Any]:
        """获取所有结果"""
        return self._results.copy()
    
    # ========== 消息传递 ==========
    
    async def send_message(
        self, 
        from_agent: str, 
        to_agent: str, 
        content: str,
        message_type: str = "info",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        发送 Agent 间消息
        
        Args:
            from_agent: 发送方 Agent
            to_agent: 接收方 Agent
            content: 消息内容
            message_type: 消息类型
            metadata: 附加元数据
        """
        async with self._lock:
            message = AgentMessage(
                from_agent=from_agent,
                to_agent=to_agent,
                content=content,
                message_type=message_type,
                metadata=metadata or {},
            )
            self._messages.append(message)
            logger.debug(f"Message: {from_agent} -> {to_agent}")
    
    async def get_messages_for(self, agent_name: str) -> List[AgentMessage]:
        """获取发给指定 Agent 的消息"""
        return [m for m in self._messages if m.to_agent == agent_name]
    
    async def get_all_messages(self) -> List[AgentMessage]:
        """获取所有消息"""
        return self._messages.copy()
    
    # ========== 上下文管理 ==========
    
    async def set_context(self, key: str, value: Any):
        """设置上下文"""
        async with self._lock:
            self._context[key] = value
    
    async def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文"""
        return self._context.get(key, default)
    
    async def update_context(self, updates: Dict[str, Any]):
        """批量更新上下文"""
        async with self._lock:
            self._context.update(updates)
    
    # ========== 轨迹记录 ==========
    
    async def add_trajectory(
        self, 
        action: str, 
        agent: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        添加执行轨迹
        
        用于审计和回放
        """
        async with self._lock:
            self._trajectory.append({
                "action": action,
                "agent": agent,
                "details": details or {},
                "timestamp": datetime.now().isoformat(),
            })
    
    async def get_trajectory(self) -> List[Dict[str, Any]]:
        """获取执行轨迹"""
        return self._trajectory.copy()
    
    # ========== 序列化 ==========
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化整个黑板状态"""
        return {
            "task_id": self.task_id,
            "request_status": self.request_status.value,
            "request_error": self.request_error,
            "subtasks": {
                sid: st.to_dict() 
                for sid, st in self._subtasks.items()
            },
            "subtask_order": self._subtask_order,
            "results": self._results,
            "messages": [m.to_dict() for m in self._messages],
            "context": self._context,
            "trajectory": self._trajectory,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Blackboard":
        """从字典恢复黑板状态"""
        bb = cls(task_id=data.get("task_id"))
        bb.request_status = RequestStatus(data.get("request_status", "pending"))
        bb.request_error = data.get("request_error")
        bb._subtask_order = data.get("subtask_order", [])
        bb._results = data.get("results", {})
        bb._context = data.get("context", {})
        bb._trajectory = data.get("trajectory", [])
        
        # 恢复子任务
        for sid, st_data in data.get("subtasks", {}).items():
            bb._subtasks[sid] = SubTask(
                id=st_data["id"],
                description=st_data["description"],
                target_hwnd=st_data.get("target_hwnd"),
                app_type=st_data.get("app_type"),
                status=RequestStatus(st_data.get("status", "pending")),
                result=st_data.get("result"),
                error=st_data.get("error"),
                assigned_agent=st_data.get("assigned_agent"),
                dependencies=st_data.get("dependencies", []),
            )
        
        # 恢复消息
        for m_data in data.get("messages", []):
            bb._messages.append(AgentMessage(
                from_agent=m_data["from"],
                to_agent=m_data["to"],
                content=m_data["content"],
                message_type=m_data.get("type", "info"),
                metadata=m_data.get("metadata", {}),
            ))
        
        return bb
    
    def clear(self):
        """清空黑板"""
        self._subtasks.clear()
        self._subtask_order.clear()
        self._results.clear()
        self._messages.clear()
        self._context.clear()
        self._trajectory.clear()
        self.request_status = RequestStatus.PENDING
        self.request_error = None
    
    def __repr__(self) -> str:
        return (
            f"Blackboard(task_id={self.task_id}, "
            f"subtasks={len(self._subtasks)}, "
            f"status={self.request_status.value})"
        )
