# -*- coding: utf-8 -*-
"""
CDP Client - Python 端 CDP 命令发送器

通过 WebSocket 向 Electron 发送 CDP 命令，实现内部浏览器控制（方案 A）
这是一个独立模块，不影响现有的 Playwright 方案

用法：
    client = CDPClient(ws_send_func)
    await client.navigate("https://example.com")
    await client.click_selector("button.submit")
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Awaitable
import logging

logger = logging.getLogger("nogicos.cdp")


@dataclass
class PendingRequest:
    """等待响应的请求"""
    request_id: str
    method: str
    future: asyncio.Future
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class CDPClient:
    """
    CDP 命令客户端
    
    通过 WebSocket 向 Electron 发送 CDP 命令
    """
    
    def __init__(self, ws_send: Callable[[dict], Awaitable[None]]):
        """
        Args:
            ws_send: WebSocket 发送函数，接收 dict 参数
        """
        self._ws_send = ws_send
        self._pending: Dict[str, PendingRequest] = {}
        self._ready = False
        self._timeout = 30.0  # 默认超时 30 秒
    
    @property
    def ready(self) -> bool:
        """CDP Bridge 是否就绪"""
        return self._ready
    
    def set_ready(self, ready: bool):
        """设置就绪状态（由 WebSocket 消息处理器调用）"""
        self._ready = ready
        if ready:
            logger.info("[CDPClient] Bridge is ready")
    
    def handle_response(self, data: dict):
        """
        处理来自 Electron 的 CDP 响应
        
        Args:
            data: { requestId, result, error }
        """
        request_id = data.get("requestId")
        if not request_id or request_id not in self._pending:
            logger.warning(f"[CDPClient] Unknown response: {request_id}")
            return
        
        pending = self._pending.pop(request_id)
        
        error = data.get("error")
        if error:
            pending.future.set_exception(CDPError(error))
        else:
            pending.future.set_result(data.get("result"))
    
    async def _send_command(self, method: str, params: dict = None) -> Any:
        """
        发送 CDP 命令并等待响应
        
        Args:
            method: 命令方法名
            params: 命令参数
            
        Returns:
            命令执行结果
        """
        if not self._ready:
            raise CDPError("CDP Bridge not ready")
        
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        
        self._pending[request_id] = PendingRequest(
            request_id=request_id,
            method=method,
            future=future,
        )
        
        # 发送命令
        await self._ws_send({
            "type": "cdp_command",
            "data": {
                "requestId": request_id,
                "method": method,
                "params": params or {},
            }
        })
        
        # 等待响应
        try:
            result = await asyncio.wait_for(future, timeout=self._timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise CDPError(f"Command timeout: {method}")
    
    # ============================================================
    # 导航控制
    # ============================================================
    
    async def navigate(self, url: str) -> dict:
        """导航到 URL"""
        return await self._send_command("navigate", {"url": url})
    
    async def reload(self) -> dict:
        """刷新页面"""
        return await self._send_command("Page.reload")
    
    async def get_url(self) -> str:
        """获取当前 URL"""
        result = await self._send_command("getURL")
        return result.get("url", "")
    
    async def get_title(self) -> str:
        """获取页面标题"""
        result = await self._send_command("getTitle")
        return result.get("title", "")
    
    # ============================================================
    # 鼠标控制
    # ============================================================
    
    async def click(self, x: int, y: int, options: dict = None) -> dict:
        """点击指定坐标"""
        return await self._send_command("click", {
            "x": x,
            "y": y,
            "options": options or {},
        })
    
    async def click_selector(self, selector: str) -> dict:
        """点击选择器匹配的元素"""
        return await self._send_command("clickSelector", {"selector": selector})
    
    async def double_click(self, x: int, y: int) -> dict:
        """双击"""
        return await self._send_command("click", {
            "x": x,
            "y": y,
            "options": {"clickCount": 2},
        })
    
    # ============================================================
    # 键盘控制
    # ============================================================
    
    async def type_text(self, text: str) -> dict:
        """输入文本"""
        return await self._send_command("type", {"text": text})
    
    async def type_in_selector(self, selector: str, text: str) -> dict:
        """在元素中输入文本"""
        return await self._send_command("typeInSelector", {
            "selector": selector,
            "text": text,
        })
    
    async def press_key(self, key: str) -> dict:
        """按下按键"""
        return await self._send_command("pressKey", {"key": key})
    
    # ============================================================
    # DOM 操作
    # ============================================================
    
    async def query_selector(self, selector: str) -> Optional[int]:
        """查询元素，返回节点 ID"""
        result = await self._send_command("querySelector", {"selector": selector})
        return result.get("nodeId")
    
    async def get_bounding_box(self, node_id: int) -> Optional[dict]:
        """获取元素边界框"""
        result = await self._send_command("getBoundingBox", {"nodeId": node_id})
        return result.get("box")
    
    # ============================================================
    # 截图
    # ============================================================
    
    async def screenshot(self, options: dict = None) -> str:
        """截取页面截图，返回 base64"""
        result = await self._send_command("screenshot", {"options": options or {}})
        return result.get("data", "")
    
    # ============================================================
    # JavaScript 执行
    # ============================================================
    
    async def evaluate(self, expression: str) -> Any:
        """执行 JavaScript"""
        result = await self._send_command("evaluate", {"expression": expression})
        return result.get("value")
    
    # ============================================================
    # 高级操作（组合命令）
    # ============================================================
    
    async def fill_form(self, selector: str, value: str) -> dict:
        """
        填写表单字段
        1. 点击元素
        2. 清空现有内容
        3. 输入新内容
        """
        await self.click_selector(selector)
        await asyncio.sleep(0.1)
        # 全选并删除
        await self._send_command("evaluate", {
            "expression": f"document.querySelector('{selector}').select()"
        })
        await asyncio.sleep(0.05)
        await self.type_text(value)
        return {"success": True}
    
    async def wait_for_selector(
        self,
        selector: str,
        timeout: float = 10.0,
        interval: float = 0.5,
    ) -> bool:
        """
        等待元素出现
        
        Args:
            selector: CSS 选择器
            timeout: 超时时间（秒）
            interval: 检查间隔（秒）
            
        Returns:
            元素是否出现
        """
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            node_id = await self.query_selector(selector)
            if node_id:
                return True
            await asyncio.sleep(interval)
        return False


class CDPError(Exception):
    """CDP 命令执行错误"""
    pass

