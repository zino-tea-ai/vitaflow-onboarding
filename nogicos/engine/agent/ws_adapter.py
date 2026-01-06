"""
NogicOS WebSocket 事件适配器
============================

统一前后端通信，将 WebSocket 消息转换为 AgentEvent。

安全特性:
- 限制前端只能发送特定事件类型
- 验证消息结构和内容
- 防止注入攻击

参考:
- Electron IPC 安全最佳实践
- OWASP WebSocket 安全指南
"""

from typing import Dict, Set, Optional, Any, Callable
import logging
import json
from dataclasses import dataclass

from .events import AgentEvent, EventType
from .event_bus import EventBus, get_event_bus

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """安全错误 - 检测到恶意或非法操作"""
    pass


class ValidationError(Exception):
    """验证错误 - 消息格式或内容不合法"""
    pass


@dataclass
class WebSocketConnection:
    """WebSocket 连接信息"""
    task_id: str
    websocket: Any  # FastAPI WebSocket 或其他实现
    authenticated: bool = False
    created_at: float = 0.0


class WebSocketEventAdapter:
    """
    WebSocket 事件适配器 - 统一前后端通信（含安全验证）
    
    职责:
    1. 将后端事件转发到前端 WebSocket
    2. 将前端消息验证并转换为 AgentEvent
    3. 管理 WebSocket 连接生命周期
    
    安全原则:
    - 永远不要信任来自渲染进程/前端的数据
    - 限制前端只能发送特定事件类型
    - 验证所有消息结构和内容
    """
    
    # 🔴 关键：限制前端只能发送特定事件类型
    ALLOWED_FROM_RENDERER: Set[EventType] = {
        EventType.USER_CONFIRM_RESPONSE,  # 用户确认响应
        EventType.USER_TAKEOVER,          # 用户接管
        EventType.USER_INPUT,             # 用户输入
    }
    
    # 允许的 payload 字段（按事件类型）
    ALLOWED_PAYLOAD_FIELDS: Dict[EventType, Set[str]] = {
        EventType.USER_CONFIRM_RESPONSE: {"action_id", "approved", "reason"},
        EventType.USER_TAKEOVER: {"reason"},
        EventType.USER_INPUT: {"text", "files"},
    }
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        初始化适配器
        
        Args:
            event_bus: 事件总线实例（默认使用全局单例）
        """
        self.event_bus = event_bus or get_event_bus()
        self._connections: Dict[str, WebSocketConnection] = {}  # task_id -> connection
        self._message_count = 0
        self._rejected_count = 0
        
        # 订阅所有事件，转发到 WebSocket
        self.event_bus.subscribe_all(
            self._forward_to_websocket,
            priority=-100,  # 最低优先级，确保其他处理器先执行
            name="ws_forward",
        )
    
    async def _forward_to_websocket(self, event: AgentEvent):
        """将事件转发到对应的 WebSocket"""
        conn = self._connections.get(event.task_id)
        if conn and conn.websocket:
            try:
                await conn.websocket.send_json(event.to_dict())
            except Exception as e:
                logger.warning(f"Failed to send event to WebSocket: {e}")
    
    async def handle_ws_message(
        self, 
        task_id: str, 
        message: Dict[str, Any],
    ) -> AgentEvent:
        """
        处理来自前端的 WebSocket 消息（含安全验证）
        
        Args:
            task_id: 任务 ID（从 URL 参数获取，已在路由层验证）
            message: 原始消息（从 WebSocket 接收）
        
        Returns:
            验证通过的 AgentEvent
        
        Raises:
            SecurityError: 安全检测失败
            ValidationError: 消息格式或内容不合法
        """
        self._message_count += 1
        
        # 1. 验证消息结构
        if not self._validate_schema(message):
            self._rejected_count += 1
            raise ValidationError("Invalid message schema: missing required fields")
        
        # 2. 验证 task_id 匹配（防止跨任务攻击）
        if message.get("task_id") != task_id:
            self._rejected_count += 1
            raise SecurityError(
                f"Task ID mismatch: URL={task_id}, message={message.get('task_id')}"
            )
        
        # 3. 🔴 限制允许的事件类型（前端只能发特定类型）
        try:
            event_type = EventType(message.get("type"))
        except ValueError:
            self._rejected_count += 1
            raise SecurityError(f"Unknown event type: {message.get('type')}")
        
        if event_type not in self.ALLOWED_FROM_RENDERER:
            self._rejected_count += 1
            raise SecurityError(
                f"Event type '{event_type.value}' not allowed from renderer. "
                f"Allowed: {[e.value for e in self.ALLOWED_FROM_RENDERER]}"
            )
        
        # 4. 验证 payload 内容（防止注入）
        payload = message.get("payload", {})
        if not self._validate_payload(event_type, payload):
            self._rejected_count += 1
            raise ValidationError(f"Invalid payload for event type '{event_type.value}'")
        
        # 5. 清理 payload（移除不允许的字段）
        cleaned_payload = self._sanitize_payload(event_type, payload)
        
        # 6. 通过验证，创建事件
        event = AgentEvent.create(
            event_type=event_type,
            task_id=task_id,
            payload=cleaned_payload,
            source="renderer",  # 标记来源为前端
        )
        
        # 7. 发布到事件总线
        await self.event_bus.publish(event)
        
        logger.debug(f"Processed message from renderer: {event_type.value}")
        return event
    
    def _validate_schema(self, message: Dict[str, Any]) -> bool:
        """验证消息基本结构"""
        required_fields = {"type", "task_id"}
        return all(field in message for field in required_fields)
    
    def _validate_payload(self, event_type: EventType, payload: Dict[str, Any]) -> bool:
        """验证 payload 内容"""
        if event_type == EventType.USER_CONFIRM_RESPONSE:
            # 确认响应必须有 action_id 和 approved 字段
            if "action_id" not in payload:
                return False
            if "approved" not in payload or not isinstance(payload["approved"], bool):
                return False
        
        elif event_type == EventType.USER_TAKEOVER:
            # 用户接管，payload 可以为空或包含 reason
            pass
        
        elif event_type == EventType.USER_INPUT:
            # 用户输入必须有 text 字段
            if "text" not in payload:
                return False
        
        return True
    
    def _sanitize_payload(self, event_type: EventType, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理 payload，只保留允许的字段
        
        这是最后一道防线，即使前面的验证通过，也只保留白名单字段
        """
        allowed_fields = self.ALLOWED_PAYLOAD_FIELDS.get(event_type, set())
        if not allowed_fields:
            return {}
        
        return {k: v for k, v in payload.items() if k in allowed_fields}
    
    # ========== 连接管理 ==========
    
    def register_connection(self, task_id: str, websocket: Any):
        """
        注册任务的 WebSocket 连接
        
        Args:
            task_id: 任务 ID
            websocket: WebSocket 对象
        """
        import time
        self._connections[task_id] = WebSocketConnection(
            task_id=task_id,
            websocket=websocket,
            authenticated=True,
            created_at=time.time(),
        )
        logger.info(f"WebSocket connection registered for task: {task_id}")
    
    def unregister_connection(self, task_id: str):
        """
        注销任务的 WebSocket 连接
        
        Args:
            task_id: 任务 ID
        """
        if task_id in self._connections:
            del self._connections[task_id]
            logger.info(f"WebSocket connection unregistered for task: {task_id}")
    
    def get_connection(self, task_id: str) -> Optional[WebSocketConnection]:
        """获取任务的 WebSocket 连接"""
        return self._connections.get(task_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "active_connections": len(self._connections),
            "message_count": self._message_count,
            "rejected_count": self._rejected_count,
            "rejection_rate": self._rejected_count / max(self._message_count, 1),
        }


# ========== 单例模式 ==========

_default_adapter: Optional[WebSocketEventAdapter] = None


def get_ws_adapter() -> WebSocketEventAdapter:
    """获取默认 WebSocket 适配器（单例）"""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = WebSocketEventAdapter()
    return _default_adapter


def set_ws_adapter(adapter: WebSocketEventAdapter):
    """设置默认 WebSocket 适配器（用于测试）"""
    global _default_adapter
    _default_adapter = adapter
