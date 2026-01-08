"""
NogicOS Agent 事件系统
========================

定义统一的事件类型和消息格式，解决模块间耦合问题。

参考:
- UFO Agent Interaction Protocol (AIP) 五层协议
- LangGraph Checkpointer 事件模型
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any, Dict
import time
import uuid


class EventType(Enum):
    """
    事件类型枚举 - 不允许随意字符串
    
    所有事件必须使用预定义的类型，确保类型安全和可追踪性
    """
    
    # ========== 任务生命周期 ==========
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_INTERRUPTED = "task.interrupted"
    TASK_PAUSED = "task.paused"
    TASK_RESUMED = "task.resumed"
    TASK_CANCELLED = "task.cancelled"
    
    # ========== Agent 状态 ==========
    AGENT_THINKING = "agent.thinking"
    AGENT_PLANNING = "agent.planning"
    AGENT_EXECUTING = "agent.executing"
    AGENT_WAITING = "agent.waiting"
    AGENT_IDLE = "agent.idle"
    AGENT_NEEDS_HELP = "agent.needs_help"  # 需要人工介入（与敏感确认语义分离）
    
    # ========== 工具调用 ==========
    TOOL_START = "tool.start"
    TOOL_END = "tool.end"
    TOOL_ERROR = "tool.error"
    TOOL_RETRY = "tool.retry"
    
    # ========== 用户交互 ==========
    USER_CONFIRM_REQUIRED = "user.confirm_required"
    USER_CONFIRM_RESPONSE = "user.confirm_response"
    USER_TAKEOVER = "user.takeover"
    USER_INPUT = "user.input"
    
    # ========== 系统事件 ==========
    SCREENSHOT_CAPTURED = "system.screenshot"
    CONTEXT_COMPRESSED = "system.context_compressed"
    CHECKPOINT_SAVED = "system.checkpoint_saved"
    CHECKPOINT_RESTORED = "system.checkpoint_restored"
    
    # ========== LLM 事件 ==========
    LLM_REQUEST_START = "llm.request_start"
    LLM_RESPONSE_CHUNK = "llm.response_chunk"
    LLM_RESPONSE_END = "llm.response_end"
    LLM_ERROR = "llm.error"
    
    # ========== Overlay 事件 ==========
    OVERLAY_CONNECTED = "overlay.connected"
    OVERLAY_DISCONNECTED = "overlay.disconnected"
    OVERLAY_STATUS_UPDATE = "overlay.status_update"


class EventPriority(Enum):
    """事件优先级 - 用于背压控制"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class AgentEvent:
    """
    统一事件格式
    
    所有模块间的通信都应该使用 AgentEvent，确保：
    1. 可追踪性（每个事件有唯一 ID）
    2. 可序列化（支持 JSON 传输）
    3. 类型安全（使用枚举类型）
    4. 关联性（通过 task_id 关联任务）
    """
    
    id: str                          # 唯一 ID
    type: EventType                  # 事件类型（枚举，不是字符串）
    task_id: str                     # 关联任务
    timestamp: float                 # Unix 时间戳
    payload: Dict[str, Any]          # 事件数据
    source: str = "host_agent"       # 事件来源
    target: Optional[str] = None     # 目标（可选）
    priority: EventPriority = EventPriority.NORMAL  # 优先级
    correlation_id: Optional[str] = None  # 关联 ID（用于追踪因果链）
    
    @classmethod
    def create(
        cls, 
        event_type: EventType, 
        task_id: str, 
        payload: Dict[str, Any],
        source: str = "host_agent",
        target: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None,
    ) -> "AgentEvent":
        """工厂方法：创建新事件"""
        return cls(
            id=str(uuid.uuid4()),
            type=event_type,
            task_id=task_id,
            timestamp=time.time(),
            payload=payload,
            source=source,
            target=target,
            priority=priority,
            correlation_id=correlation_id,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        序列化为字典
        
        用于 WebSocket/IPC 传输，枚举转为字符串值
        """
        return {
            "id": self.id,
            "type": self.type.value,  # 枚举转字符串
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "source": self.source,
            "target": self.target,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentEvent":
        """
        从字典反序列化
        
        用于接收外部消息时重建事件对象
        """
        return cls(
            id=data["id"],
            type=EventType(data["type"]),  # 字符串转枚举
            task_id=data["task_id"],
            timestamp=data["timestamp"],
            payload=data["payload"],
            source=data.get("source", "unknown"),
            target=data.get("target"),
            priority=EventPriority(data.get("priority", 1)),
            correlation_id=data.get("correlation_id"),
        )
    
    def with_correlation(self, correlation_id: str) -> "AgentEvent":
        """创建带关联 ID 的新事件（用于追踪因果链）"""
        return AgentEvent(
            id=self.id,
            type=self.type,
            task_id=self.task_id,
            timestamp=self.timestamp,
            payload=self.payload,
            source=self.source,
            target=self.target,
            priority=self.priority,
            correlation_id=correlation_id,
        )
    
    def __repr__(self) -> str:
        return f"AgentEvent(type={self.type.value}, task_id={self.task_id[:8]}..., source={self.source})"


# ========== 便捷工厂函数 ==========

def task_started_event(task_id: str, task_description: str) -> AgentEvent:
    """创建任务开始事件"""
    return AgentEvent.create(
        EventType.TASK_STARTED,
        task_id,
        {"description": task_description},
    )


def task_completed_event(task_id: str, result: str) -> AgentEvent:
    """创建任务完成事件"""
    return AgentEvent.create(
        EventType.TASK_COMPLETED,
        task_id,
        {"result": result},
    )


def task_failed_event(task_id: str, error: str, recoverable: bool = False) -> AgentEvent:
    """创建任务失败事件"""
    return AgentEvent.create(
        EventType.TASK_FAILED,
        task_id,
        {"error": error, "recoverable": recoverable},
        priority=EventPriority.HIGH,
    )


def tool_start_event(task_id: str, tool_name: str, args: Dict[str, Any]) -> AgentEvent:
    """创建工具开始执行事件"""
    return AgentEvent.create(
        EventType.TOOL_START,
        task_id,
        {"tool_name": tool_name, "args": args},
    )


def tool_end_event(task_id: str, tool_name: str, result: Any, duration_ms: float) -> AgentEvent:
    """创建工具执行完成事件"""
    return AgentEvent.create(
        EventType.TOOL_END,
        task_id,
        {"tool_name": tool_name, "result": result, "duration_ms": duration_ms},
    )


def tool_error_event(task_id: str, tool_name: str, error: str) -> AgentEvent:
    """创建工具执行错误事件"""
    return AgentEvent.create(
        EventType.TOOL_ERROR,
        task_id,
        {"tool_name": tool_name, "error": error},
        priority=EventPriority.HIGH,
    )


def confirm_required_event(
    task_id: str, 
    action_id: str, 
    action_description: str,
    risk_level: str = "medium",
) -> AgentEvent:
    """创建需要用户确认事件"""
    return AgentEvent.create(
        EventType.USER_CONFIRM_REQUIRED,
        task_id,
        {
            "action_id": action_id,
            "description": action_description,
            "risk_level": risk_level,
        },
        priority=EventPriority.CRITICAL,
    )


def llm_chunk_event(task_id: str, chunk: str, token_count: int = 0) -> AgentEvent:
    """创建 LLM 响应块事件（用于流式输出）"""
    return AgentEvent.create(
        EventType.LLM_RESPONSE_CHUNK,
        task_id,
        {"chunk": chunk, "token_count": token_count},
    )
