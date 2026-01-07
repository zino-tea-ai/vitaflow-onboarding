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


# ========== 背压事件总线 (Phase 0.25) ==========

class EventBusOverflowError(Exception):
    """事件总线溢出错误"""
    pass


class BackpressureEventBus(EventBus):
    """
    带背压控制的事件总线
    
    特性:
    - 优先级队列：高优先级事件优先处理
    - 背压控制：队列满时丢弃低优先级事件
    - 批量处理：Worker 批量消费事件
    - 统计监控：丢弃率、延迟等指标
    
    使用示例:
    ```python
    bus = BackpressureEventBus(max_queue_size=1000)
    await bus.start()  # 启动 worker
    
    # 发布事件（高优先级不会被丢弃）
    await bus.publish(AgentEvent.create(
        EventType.TASK_FAILED,
        task_id="123",
        payload={"error": "..."},
        priority=EventPriority.CRITICAL,
    ))
    
    await bus.stop()  # 停止 worker
    ```
    """
    
    # 事件优先级映射（数字越小优先级越高）
    PRIORITY_MAP: Dict[EventType, int] = {
        # 最高优先级 (0) - 不可丢弃
        EventType.TASK_FAILED: 0,
        EventType.USER_TAKEOVER: 0,
        EventType.USER_CONFIRM_REQUIRED: 0,
        EventType.USER_CONFIRM_RESPONSE: 0,
        
        # 高优先级 (1)
        EventType.TASK_COMPLETED: 1,
        EventType.TASK_INTERRUPTED: 1,
        EventType.TOOL_ERROR: 1,
        
        # 普通优先级 (2)
        EventType.TASK_STARTED: 2,
        EventType.TOOL_START: 2,
        EventType.TOOL_END: 2,
        EventType.AGENT_EXECUTING: 2,
        
        # 低优先级 (3) - 可丢弃
        EventType.AGENT_THINKING: 3,
        EventType.AGENT_PLANNING: 3,
        EventType.LLM_RESPONSE_CHUNK: 3,
        
        # 最低优先级 (4) - 优先丢弃
        EventType.SCREENSHOT_CAPTURED: 4,
        EventType.CHECKPOINT_SAVED: 4,
        EventType.CONTEXT_COMPRESSED: 4,
    }
    
    # 可丢弃的优先级阈值
    DROPPABLE_THRESHOLD = 3
    
    # 批量处理大小
    BATCH_SIZE = 10
    
    def __init__(self, max_queue_size: int = 1000):
        super().__init__(max_queue_size)
        
        # 优先级队列：(priority, timestamp, event)
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 统计
        self._events_queued = 0
        self._events_dropped = 0
        self._events_processed = 0
        self._queue_wait_times: List[float] = []
    
    async def start(self):
        """启动 worker"""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("BackpressureEventBus worker started")
    
    async def stop(self):
        """停止 worker"""
        self._running = False
        
        if self._worker_task:
            # 发送哨兵事件终止 worker
            try:
                self._queue.put_nowait((999, 0, None))
            except asyncio.QueueFull:
                pass
            
            try:
                await asyncio.wait_for(self._worker_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._worker_task.cancel()
            
            self._worker_task = None
        
        logger.info("BackpressureEventBus worker stopped")
    
    async def publish(self, event: AgentEvent) -> bool:
        """
        发布事件到队列
        
        Args:
            event: 要发布的事件
            
        Returns:
            是否成功入队（高优先级事件总是成功）
            
        Raises:
            EventBusOverflowError: 队列满且事件不可丢弃时抛出
        """
        if self._paused:
            logger.warning(f"EventBus paused, dropping event: {event.type.value}")
            return False
        
        import time
        priority = self._get_priority(event)
        timestamp = time.time()
        
        try:
            self._queue.put_nowait((priority, timestamp, event))
            self._events_queued += 1
            self._event_count += 1
            return True
            
        except asyncio.QueueFull:
            # 队列满，检查是否可丢弃
            if priority >= self.DROPPABLE_THRESHOLD:
                self._events_dropped += 1
                logger.debug(f"Dropped low-priority event: {event.type.value}")
                return False
            
            # 高优先级事件不可丢弃，抛出异常
            raise EventBusOverflowError(
                f"Queue full and event {event.type.value} (priority={priority}) cannot be dropped"
            )
    
    def _get_priority(self, event: AgentEvent) -> int:
        """获取事件优先级"""
        # 先检查事件自带的优先级
        if event.priority == EventPriority.CRITICAL:
            return 0
        elif event.priority == EventPriority.HIGH:
            return 1
        elif event.priority == EventPriority.LOW:
            return 4
        
        # 使用类型映射
        return self.PRIORITY_MAP.get(event.type, 2)
    
    async def _worker(self):
        """Worker 协程：批量处理事件"""
        import time
        
        while self._running:
            batch: List[AgentEvent] = []
            
            try:
                # 获取第一个事件（阻塞）
                priority, enqueue_time, event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                
                # 哨兵事件
                if event is None:
                    break
                
                batch.append(event)
                wait_time = time.time() - enqueue_time
                self._queue_wait_times.append(wait_time)
                
                # 尝试获取更多事件（非阻塞）
                while len(batch) < self.BATCH_SIZE:
                    try:
                        priority, enqueue_time, event = self._queue.get_nowait()
                        if event is None:
                            break
                        batch.append(event)
                    except asyncio.QueueEmpty:
                        break
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker error getting events: {e}")
                continue
            
            # 批量处理
            await self._process_batch(batch)
    
    async def _process_batch(self, batch: List[AgentEvent]):
        """批量处理事件"""
        for event in batch:
            try:
                # 调用父类的处理逻辑
                await self._dispatch_event(event)
                self._events_processed += 1
            except Exception as e:
                self._error_count += 1
                logger.error(f"Error processing event {event.type.value}: {e}")
    
    async def _dispatch_event(self, event: AgentEvent):
        """分发事件到处理器"""
        # 全局处理器
        for handler_info in self._global_handlers:
            try:
                await self._call_handler(handler_info, event)
            except Exception as e:
                logger.error(f"Global handler '{handler_info.name}' error: {e}")
        
        # 特定类型处理器
        for handler_info in self._handlers[event.type]:
            try:
                await self._call_handler(handler_info, event)
            except Exception as e:
                logger.error(f"Handler '{handler_info.name}' error: {e}")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        base_stats = super().get_stats()
        
        # 计算队列等待时间
        recent_waits = self._queue_wait_times[-100:] if self._queue_wait_times else []
        avg_wait = sum(recent_waits) / len(recent_waits) if recent_waits else 0
        
        return {
            **base_stats,
            "queue_size": self._queue.qsize(),
            "max_queue_size": self._max_queue_size,
            "events_queued": self._events_queued,
            "events_dropped": self._events_dropped,
            "events_processed": self._events_processed,
            "drop_rate": self._events_dropped / max(self._events_queued, 1),
            "avg_queue_wait_ms": avg_wait * 1000,
            "running": self._running,
        }
    
    async def drain(self, timeout: float = 5.0):
        """等待队列清空"""
        import time
        start = time.time()
        
        while not self._queue.empty():
            if time.time() - start > timeout:
                logger.warning(f"Drain timeout, {self._queue.qsize()} events remaining")
                break
            await asyncio.sleep(0.1)


# ========== 工厂函数 ==========

_backpressure_bus: Optional[BackpressureEventBus] = None


def get_backpressure_bus() -> BackpressureEventBus:
    """获取背压事件总线（单例）"""
    global _backpressure_bus
    if _backpressure_bus is None:
        _backpressure_bus = BackpressureEventBus()
    return _backpressure_bus


async def init_backpressure_bus() -> BackpressureEventBus:
    """初始化并启动背压事件总线"""
    bus = get_backpressure_bus()
    await bus.start()
    return bus
