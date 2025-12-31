"""
NogicOS ChatKit Server - OpenAI ChatKit 集成

实现 ChatKitServer 接口，将 NogicOS ReAct Agent 与 ChatKit UI 框架连接。
支持流式响应、Widget 渲染、客户端工具等高级功能。

Architecture:
    ChatKit Frontend → HTTP Stream → ChatKitServer → ReActAgent → Tools
                  ↑___________ Widget/Text Events _____|
"""

from __future__ import annotations

import logging
import asyncio
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

# ChatKit imports
try:
    from chatkit.server import ChatKitServer, stream_widget
    from chatkit.store import NotFoundError
    from chatkit.types import (
        Action,
        AssistantMessageContent,
        AssistantMessageContentPartTextDelta,
        AssistantMessageItem,
        Attachment,
        Page,
        StreamOptions,
        ThreadItem,
        ThreadItemAddedEvent,
        ThreadItemUpdatedEvent,
        ThreadItemDoneEvent,
        ThreadMetadata,
        ThreadStreamEvent,
        UserMessageItem,
        WidgetItem,
    )
    # Widget components for streaming text with animation
    from chatkit.widgets import Card, Markdown, Text
    CHATKIT_AVAILABLE = True
except ImportError:
    CHATKIT_AVAILABLE = False
    ChatKitServer = object  # Fallback for type hints
    Page = None
    NotFoundError = Exception
    stream_widget = None
    Card = None
    Markdown = None
    Text = None

# OpenAI types for message content
try:
    from openai.types.responses import ResponseInputContentParam
except ImportError:
    ResponseInputContentParam = Any

# Local imports
from engine.observability import get_logger
from engine.agent.react_agent import ReActAgent, AgentResult
from engine.server.widgets import (
    build_progress_widget,
    ProgressState,
    format_progress_text,
    build_tool_card_widget,
    ToolCardState,
    format_tool_text,
)

logger = get_logger("chatkit_server")


class InMemoryStore:
    """
    Simple in-memory store for ChatKit threads and items.
    
    基于官方 MemoryStore 实现，使用正确的 Page 类型。
    生产环境应替换为持久化存储（Redis, PostgreSQL等）。
    """
    
    def __init__(self):
        self._threads: Dict[str, ThreadMetadata] = {}
        self._items: Dict[str, List[Any]] = {}  # thread_id -> items
        self._counter = 0
    
    def generate_item_id(self, prefix: str, thread: ThreadMetadata, context: Dict[str, Any]) -> str:
        """Generate unique item ID."""
        self._counter += 1
        return f"{prefix}-{thread.id}-{self._counter}"
    
    def generate_thread_id(self, context: Dict[str, Any]) -> str:
        """Generate unique thread ID."""
        import uuid
        return f"thread-{uuid.uuid4().hex[:12]}"
    
    def _paginate(self, rows: list, after: Optional[str], limit: int, order: str, sort_key, cursor_key):
        """通用分页方法，返回 Page 类型"""
        sorted_rows = sorted(rows, key=sort_key, reverse=(order == "desc"))
        start = 0
        if after:
            for idx, row in enumerate(sorted_rows):
                if cursor_key(row) == after:
                    start = idx + 1
                    break
        data = sorted_rows[start:start + limit] if limit else sorted_rows[start:]
        has_more = (start + limit < len(sorted_rows)) if limit else False
        next_after = cursor_key(data[-1]) if has_more and data else None
        return Page(data=data, has_more=has_more, after=next_after)
    
    async def load_thread(self, thread_id: str, context: Dict[str, Any]) -> ThreadMetadata:
        """Load thread by ID."""
        if thread_id not in self._threads:
            raise NotFoundError(f"Thread {thread_id} not found")
        return self._threads[thread_id]
    
    async def load_threads(
        self,
        limit: int,
        after: Optional[str],
        order: str,
        context: Dict[str, Any],
    ):
        """Load all threads with pagination."""
        threads = list(self._threads.values())
        return self._paginate(
            threads, after, limit, order,
            sort_key=lambda t: getattr(t, 'created_at', datetime.min),
            cursor_key=lambda t: t.id
        )
    
    async def save_thread(self, thread: ThreadMetadata, context: Dict[str, Any]) -> None:
        """Save or update thread."""
        self._threads[thread.id] = thread
    
    async def load_thread_items(
        self,
        thread_id: str,
        after: Optional[str],
        limit: int,
        order: str,
        context: Dict[str, Any],
    ):
        """Load thread items with pagination."""
        items = self._items.get(thread_id, [])
        return self._paginate(
            items, after, limit, order,
            sort_key=lambda i: getattr(i, 'created_at', datetime.min),
            cursor_key=lambda i: i.id
        )
    
    async def add_thread_item(
        self,
        thread_id: str,
        item: Any,
        context: Dict[str, Any],
    ) -> None:
        """Add item to thread."""
        if thread_id not in self._items:
            self._items[thread_id] = []
        self._items[thread_id].append(item)
    
    async def save_item(self, thread_id: str, item: Any, context: Dict[str, Any]) -> None:
        """Save or update item."""
        items = self._items.get(thread_id, [])
        for idx, existing in enumerate(items):
            if existing.id == item.id:
                items[idx] = item
                return
        if thread_id not in self._items:
            self._items[thread_id] = []
        self._items[thread_id].append(item)
    
    async def delete_thread(self, thread_id: str, context: Dict[str, Any]) -> None:
        """Delete a thread and its items."""
        self._threads.pop(thread_id, None)
        self._items.pop(thread_id, None)


class NogicOSChatServer(ChatKitServer if CHATKIT_AVAILABLE else object):
    """
    NogicOS ChatKit Server - 集成 ReAct Agent。
    
    功能:
    - 流式响应用户消息
    - 支持客户端工具（show_visualization, highlight_element等）
    - Widget 渲染（进度、截图等）
    - 会话历史管理
    
    客户端工具 (Client Tools):
    - show_visualization: 触发显示可视化面板
    - highlight_element: 高亮指定元素区域
    - move_cursor: 移动 AI 光标到指定位置
    - play_sound: 播放提示音
    """
    
    # 客户端工具定义
    CLIENT_TOOLS = [
        {
            "name": "show_visualization",
            "description": "显示可视化面板，展示 AI 操作的实时画面",
            "parameters": {},
        },
        {
            "name": "highlight_element",
            "description": "高亮页面上的指定区域",
            "parameters": {
                "x": {"type": "number", "description": "高亮区域左上角 X 坐标"},
                "y": {"type": "number", "description": "高亮区域左上角 Y 坐标"},
                "width": {"type": "number", "description": "高亮区域宽度"},
                "height": {"type": "number", "description": "高亮区域高度"},
                "label": {"type": "string", "description": "高亮标签（可选）"},
            },
        },
        {
            "name": "move_cursor",
            "description": "移动 AI 光标到指定位置",
            "parameters": {
                "x": {"type": "number", "description": "目标 X 坐标"},
                "y": {"type": "number", "description": "目标 Y 坐标"},
            },
        },
        {
            "name": "play_sound",
            "description": "播放提示音",
            "parameters": {
                "type": {"type": "string", "description": "提示音类型：complete, error, notification"},
            },
        },
    ]
    
    def __init__(self, status_server=None):
        """
        初始化 ChatKit 服务器。
        
        Args:
            status_server: WebSocket 状态服务器，用于可视化面板同步
        """
        self.store = InMemoryStore()
        
        if CHATKIT_AVAILABLE:
            super().__init__(self.store)
        
        self.status_server = status_server
        
        # 创建 ReAct Agent（延迟初始化以避免循环依赖）
        self._agent: Optional[ReActAgent] = None
        
        logger.info("[ChatKit] NogicOS ChatKit Server initialized")
    
    @property
    def agent(self) -> ReActAgent:
        """获取或创建 ReAct Agent（延迟初始化）。"""
        if self._agent is None:
            self._agent = ReActAgent(status_server=self.status_server)
        return self._agent
    
    # ============================================================
    # 可视化面板联动方法
    # ============================================================
    
    async def _broadcast_visualization_event(self, event_type: str, data: Dict[str, Any] = None):
        """
        通过 WebSocket 广播可视化事件到前端。
        
        这使得 ChatKit 响应可以触发 VisualizationPanel 的动画。
        
        Args:
            event_type: 事件类型（cursor_move, highlight, glow 等）
            data: 事件数据
        """
        if self.status_server:
            await self.status_server.broadcast({
                "type": event_type,
                "data": data or {},
            })
    
    async def trigger_show_visualization(self):
        """触发显示可视化面板。"""
        await self._broadcast_visualization_event("screen_glow", {"intensity": "medium"})
        logger.debug("[ChatKit] Triggered show_visualization")
    
    async def trigger_highlight(self, x: int, y: int, width: int, height: int, label: str = None):
        """触发高亮指定区域。"""
        await self._broadcast_visualization_event("highlight", {
            "rect": {"x": x, "y": y, "width": width, "height": height},
            "label": label,
        })
        logger.debug(f"[ChatKit] Triggered highlight at ({x}, {y})")
    
    async def trigger_cursor_move(self, x: int, y: int):
        """触发光标移动。"""
        await self._broadcast_visualization_event("cursor_move", {
            "x": x,
            "y": y,
            "duration": 0.5,
        })
        logger.debug(f"[ChatKit] Triggered cursor_move to ({x}, {y})")
    
    async def trigger_task_complete(self):
        """触发任务完成动画。"""
        await self._broadcast_visualization_event("task_complete", {})
        logger.debug("[ChatKit] Triggered task_complete")
    
    # ============================================================
    # Required ChatKitServer Overrides
    # ============================================================
    
    async def action(
        self,
        thread: ThreadMetadata,
        action: Action[str, Any],
        sender: Optional[WidgetItem],
        context: Dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        """
        处理来自 Widget 的动作（如按钮点击）。
        
        Args:
            thread: 当前会话
            action: 触发的动作
            sender: 发送动作的 Widget
            context: 请求上下文
        """
        logger.info(f"[ChatKit] Action received: {action.type}")
        
        # 处理不同的动作类型
        if action.type == "nogicos.stop_execution":
            # 停止当前执行
            # TODO: 实现停止逻辑
            yield ThreadItemDoneEvent(
                item=AssistantMessageItem(
                    id=self.store.generate_item_id("message", thread, context),
                    thread_id=thread.id,
                    created_at=datetime.now(),
                    content=[AssistantMessageContent(text="执行已停止。")],
                )
            )
            return
        
        # 默认：不处理未知动作
        return
    
    async def respond(
        self,
        thread: ThreadMetadata,
        item: Optional[UserMessageItem],
        context: Dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        """
        响应用户消息 - 包含 Thinking + Response 双区域流式展示！
        
        复刻 Cursor 的效果：
        1. Thinking 区域：显示 AI 思考过程（灰色斜体）
        2. Response 区域：显示最终回复（Markdown 流式）
        
        关键：只有带 id 的 <Text>/<Markdown> 组件才会有流式动画。
        """
        if not item or not item.content:
            return
        
        # 提取用户消息文本
        user_message = ""
        for content_part in item.content:
            if hasattr(content_part, 'text'):
                user_message += content_part.text
        
        if not user_message:
            return
        
        logger.info(f"[ChatKit] Processing message: {user_message[:50]}...")
        
        # 累积文本（分别存储 thinking 和 response）
        thinking_text = ""
        response_text = ""
        is_thinking = True  # 标记当前是否在 thinking 阶段
        
        # 使用 asyncio.Queue 传递事件，格式：("thinking", delta) 或 ("response", delta) 或 None
        event_queue: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue()
        agent_result: Optional[Any] = None
        
        # ============================================
        # 定义流式回调函数
        # ============================================
        
        async def on_thinking_delta(delta: str):
            """Claude Extended Thinking 每输出一段思考就调用此回调"""
            await event_queue.put(("thinking", delta))
        
        async def on_text_delta(delta: str):
            """Claude 每输出一段文字就调用此回调"""
            await event_queue.put(("response", delta))
        
        async def on_tool_start(tool_id: str, tool_name: str):
            """工具开始执行时调用"""
            await event_queue.put(("response", f"\n🔧 正在执行 {tool_name}..."))
        
        async def on_tool_end(tool_id: str, success: bool, result: str):
            """工具执行完成时调用"""
            status = "✓" if success else "✗"
            await event_queue.put(("response", f" {status}\n"))
        
        # ============================================
        # 异步执行 Agent（后台任务）
        # ============================================
        
        async def run_agent():
            """后台执行 Agent，传递 thinking 回调"""
            nonlocal agent_result
            try:
                agent_result = await self.agent.run(
                    task=user_message,
                    session_id=thread.id,
                    on_thinking_delta=on_thinking_delta,  # 新增：thinking 回调
                    on_text_delta=on_text_delta,
                    on_tool_start=on_tool_start,
                    on_tool_end=on_tool_end,
                )
                
                if agent_result.success:
                    await self.trigger_task_complete()
                
            except Exception as e:
                logger.error(f"[ChatKit] Agent error: {e}")
                await event_queue.put(("response", f"\n⚠️ 出错了: {str(e)}"))
            finally:
                # 发送结束信号
                await event_queue.put(None)
        
        # ============================================
        # Widget Generator - 产生 Thinking + Response 双区域
        # ============================================
        
        async def widget_generator():
            """
            异步生成器：构建 Thinking + Response 双区域 Widget。
            
            Widget 结构:
            Card
            ├── Text (id="thinking", 灰色斜体，显示思考过程)
            └── Markdown (id="response", 显示最终回复)
            """
            nonlocal thinking_text, response_text
            
            while True:
                try:
                    # 等待新事件（带超时避免死锁）
                    event = await asyncio.wait_for(event_queue.get(), timeout=120.0)
                    
                    if event is None:
                        # Agent 完成
                        break
                    
                    event_type, delta = event
                    
                    if event_type == "thinking":
                        thinking_text += delta
                    else:  # response
                        response_text += delta
                    
                    # 构建 Widget：Thinking 在上，Response 在下，视觉分隔
                    children = []
                    
                    # Thinking 区域（灰色小字，折叠显示）
                    if thinking_text:
                        # 截断显示，只显示前 200 字符
                        truncated = thinking_text[:200] + "..." if len(thinking_text) > 200 else thinking_text
                        children.append(
                            Text(
                                id="thinking-text",
                                value=f"💭 Thinking...",
                                size="sm",
                                color="secondary",  # 灰色
                                streaming=True,
                            )
                        )
                    
                    # 分隔线（如果有 thinking）
                    if thinking_text and response_text:
                        children.append(
                            Text(
                                id="divider",
                                value="───────────────",
                                size="sm",
                                color="secondary",
                            )
                        )
                    
                    # Response 区域
                    if response_text:
                        children.append(
                            Markdown(
                                id="response-text",
                                value=response_text,
                                streaming=True,
                            )
                        )
                    
                    # 如果两个都空，显示等待状态
                    if not children:
                        children.append(
                            Text(
                                id="status-text",
                                value="⏳ 正在思考...",
                                size="sm",
                                color="secondary",
                                streaming=True,
                            )
                        )
                    
                    yield Card(children=children)
                    
                except asyncio.TimeoutError:
                    logger.warning("[ChatKit] Timeout waiting for event")
                    break
            
            # 最终 Widget - 只显示 Response，Thinking 已完成
            final_children = []
            
            # Thinking 完成标记（简短）
            if thinking_text:
                final_children.append(
                    Text(
                        id="thinking-text",
                        value=f"💭 Thought for {len(thinking_text)} chars",
                        size="sm",
                        color="secondary",
                        streaming=False,
                    )
                )
                final_children.append(
                    Text(
                        id="divider",
                        value="───────────────",
                        size="sm",
                        color="secondary",
                    )
                )
            
            # Response 区域
            final_response = response_text
            if not final_response.strip() and agent_result and agent_result.response:
                final_response = agent_result.response
            elif not final_response.strip():
                final_response = "✅ 任务完成！"
            
            final_children.append(
                Markdown(
                    id="response-text",
                    value=final_response,
                    streaming=False,
                )
            )
            
            yield Card(children=final_children)
        
        # 启动 Agent（后台）
        agent_task = asyncio.create_task(run_agent())
        
        # ============================================
        # 使用 stream_widget 流式发送 Widget
        # ============================================
        try:
            async for event in stream_widget(
                thread,
                widget_generator(),
                copy_text=response_text,  # 复制时只复制 response
                generate_id=lambda item_type: self.store.generate_item_id(
                    item_type, thread, context
                ),
            ):
                yield event
        finally:
            # 确保 Agent 任务完成
            if not agent_task.done():
                agent_task.cancel()
                try:
                    await agent_task
                except asyncio.CancelledError:
                    pass
    
    def get_stream_options(
        self,
        thread: ThreadMetadata,
        context: Dict[str, Any],
    ) -> StreamOptions:
        """
        配置流式选项。
        
        Returns:
            StreamOptions 配置
        """
        return StreamOptions(allow_cancel=True)
    
    async def to_message_content(
        self,
        attachment: Attachment,
    ) -> ResponseInputContentParam:
        """
        处理附件（图片、文件等）。
        
        当前版本不支持附件，后续可扩展。
        """
        raise NotImplementedError("附件功能暂未实现。请直接描述您的需求。")


def create_chatkit_server(status_server=None) -> Optional[NogicOSChatServer]:
    """
    创建 ChatKit 服务器实例。
    
    Args:
        status_server: WebSocket 状态服务器（可选）
        
    Returns:
        NogicOSChatServer 实例，如果依赖不可用则返回 None
    """
    if not CHATKIT_AVAILABLE:
        logger.warning("[ChatKit] ChatKit SDK not available. Install with: pip install openai-chatkit")
        return None
    
    return NogicOSChatServer(status_server=status_server)

