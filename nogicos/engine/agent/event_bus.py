"""
NogicOS 事件总线
================

提供事件发布/订阅机制，解耦组件通信。

特性:
- 支持同步和异步处理器
- 背压控制（可选，在 Phase 0.25 增强）
- 全局订阅（用于日志、追踪）
- 优先级队列支持

参考:
- UFO Agent Interaction Protocol (AIP)
- Node.js EventEmitter
"""

from typing import Callable, Dict, List, Set, Optional, Union, Awaitable
from collections import defaultdict
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum

from .events import AgentEvent, EventType, EventPriority

logger = logging.getLogger(__name__)


# Handler 类型定义
EventHandler = Callable[[AgentEvent], Union[None, Awaitable[None]]]


@dataclass
class HandlerInfo:
    """处理器信息"""
    handler: EventHandler
    is_async: bool
    priority: int = 0  # 数字越大优先级越高
    name: str = ""     # 用于调试


class EventBus:
    """
    事件总线 - 解耦组件通信
    
    使用示例:
    ```python
    bus = EventBus()
    
    # 订阅特定事件
    async def handle_task_started(event: AgentEvent):
        print(f"Task started: {event.task_id}")
    
    bus.subscribe(EventType.TASK_STARTED, handle_task_started)
    
    # 订阅所有事件（用于日志）
    bus.subscribe_all(lambda e: logger.info(f"Event: {e.type}"))
    
    # 发布事件
    await bus.publish(AgentEvent.create(
        EventType.TASK_STARTED,
        task_id="123",
        payload={"description": "Test task"}
    ))
    ```
    """
    
    def __init__(self, max_queue_size: int = 1000):
        """
        初始化事件总线
        
        Args:
            max_queue_size: 最大队列大小（用于背压控制，Phase 0.25 启用）
        """
        self._handlers: Dict[EventType, List[HandlerInfo]] = defaultdict(list)
        self._global_handlers: List[HandlerInfo] = []
        self._max_queue_size = max_queue_size
        self._event_count = 0
        self._error_count = 0
        self._paused = False
        self._lock = asyncio.Lock()
    
    def subscribe(
        self, 
        event_type: EventType, 
        handler: EventHandler,
        priority: int = 0,
        name: str = "",
    ) -> Callable[[], None]:
        """
        订阅特定事件类型
        
        Args:
            event_type: 要订阅的事件类型
            handler: 事件处理函数（同步或异步）
            priority: 优先级（数字越大越先执行）
            name: 处理器名称（用于调试）
        
        Returns:
            取消订阅的函数
        """
        is_async = asyncio.iscoroutinefunction(handler)
        info = HandlerInfo(
            handler=handler,
            is_async=is_async,
            priority=priority,
            name=name or handler.__name__ if hasattr(handler, '__name__') else "anonymous",
        )
        
        self._handlers[event_type].append(info)
        # 按优先级排序（高优先级在前）
        self._handlers[event_type].sort(key=lambda h: -h.priority)
        
        logger.debug(f"Subscribed handler '{info.name}' to {event_type.value}")
        
        # 返回取消订阅函数
        def unsubscribe():
            self._handlers[event_type].remove(info)
            logger.debug(f"Unsubscribed handler '{info.name}' from {event_type.value}")
        
        return unsubscribe
    
    def subscribe_all(
        self, 
        handler: EventHandler,
        priority: int = 0,
        name: str = "",
    ) -> Callable[[], None]:
        """
        订阅所有事件（用于日志、追踪）
        
        Args:
            handler: 事件处理函数
            priority: 优先级
            name: 处理器名称
        
        Returns:
            取消订阅的函数
        """
        is_async = asyncio.iscoroutinefunction(handler)
        info = HandlerInfo(
            handler=handler,
            is_async=is_async,
            priority=priority,
            name=name or handler.__name__ if hasattr(handler, '__name__') else "global_handler",
        )
        
        self._global_handlers.append(info)
        self._global_handlers.sort(key=lambda h: -h.priority)
        
        logger.debug(f"Subscribed global handler '{info.name}'")
        
        def unsubscribe():
            self._global_handlers.remove(info)
            logger.debug(f"Unsubscribed global handler '{info.name}'")
        
        return unsubscribe
    
    async def publish(self, event: AgentEvent) -> bool:
        """
        发布事件
        
        Args:
            event: 要发布的事件
        
        Returns:
            是否成功发布（背压时可能返回 False）
        """
        if self._paused:
            logger.warning(f"EventBus paused, dropping event: {event.type.value}")
            return False
        
        self._event_count += 1
        
        # 全局处理器先执行
        for handler_info in self._global_handlers:
            try:
                await self._call_handler(handler_info, event)
            except Exception as e:
                self._error_count += 1
                logger.error(f"Global handler '{handler_info.name}' error: {e}")
        
        # 特定类型处理器
        for handler_info in self._handlers[event.type]:
            try:
                await self._call_handler(handler_info, event)
            except Exception as e:
                self._error_count += 1
                logger.error(f"Handler '{handler_info.name}' error for {event.type.value}: {e}")
        
        return True
    
    async def _call_handler(self, handler_info: HandlerInfo, event: AgentEvent):
        """调用处理器（支持同步和异步）"""
        if handler_info.is_async:
            await handler_info.handler(event)
        else:
            handler_info.handler(event)
    
    def pause(self):
        """暂停事件处理"""
        self._paused = True
        logger.info("EventBus paused")
    
    def resume(self):
        """恢复事件处理"""
        self._paused = False
        logger.info("EventBus resumed")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "event_count": self._event_count,
            "error_count": self._error_count,
            "handler_count": sum(len(h) for h in self._handlers.values()),
            "global_handler_count": len(self._global_handlers),
            "paused": self._paused,
        }
    
    def clear(self):
        """清除所有处理器"""
        self._handlers.clear()
        self._global_handlers.clear()
        logger.info("EventBus cleared")


# ========== 单例模式 ==========

_default_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取默认事件总线（单例）"""
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus


def set_event_bus(bus: EventBus):
    """设置默认事件总线（用于测试）"""
    global _default_bus
    _default_bus = bus


# ========== 装饰器 ==========

def on_event(event_type: EventType, priority: int = 0):
    """
    事件处理器装饰器
    
    使用示例:
    ```python
    @on_event(EventType.TASK_STARTED)
    async def handle_task_started(event: AgentEvent):
        print(f"Task started: {event.task_id}")
    ```
    """
    def decorator(func: EventHandler) -> EventHandler:
        bus = get_event_bus()
        bus.subscribe(event_type, func, priority=priority, name=func.__name__)
        return func
    return decorator


def on_all_events(priority: int = 0):
    """
    全局事件处理器装饰器
    
    使用示例:
    ```python
    @on_all_events()
    async def log_all_events(event: AgentEvent):
        logger.info(f"Event: {event.type}")
    ```
    """
    def decorator(func: EventHandler) -> EventHandler:
        bus = get_event_bus()
        bus.subscribe_all(func, priority=priority, name=func.__name__)
        return func
    return decorator
