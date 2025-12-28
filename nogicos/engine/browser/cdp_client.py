# -*- coding: utf-8 -*-
"""
CDP Client - Python-side CDP command sender

Sends CDP commands to Electron via WebSocket for internal browser control (Option A).
This is an independent module that doesn't affect the existing Playwright solution.

Usage:
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
    """Request awaiting response"""
    request_id: str
    method: str
    future: asyncio.Future
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class CDPClient:
    """
    CDP command client
    
    Sends CDP commands to Electron via WebSocket
    """
    
    def __init__(self, ws_send: Callable[[dict], Awaitable[None]]):
        """
        Args:
            ws_send: WebSocket send function that accepts dict parameter
        """
        self._ws_send = ws_send
        self._pending: Dict[str, PendingRequest] = {}
        self._ready = False
        self._timeout = 30.0  # Default timeout 30 seconds
    
    @property
    def ready(self) -> bool:
        """Whether CDP Bridge is ready"""
        return self._ready
    
    def set_ready(self, ready: bool):
        """Set ready state (called by WebSocket message handler)"""
        self._ready = ready
        if ready:
            logger.info("[CDPClient] Bridge is ready")
    
    def handle_response(self, data: dict):
        """
        Handle CDP response from Electron
        
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
        Send CDP command and wait for response
        
        Args:
            method: Command method name
            params: Command parameters
            
        Returns:
            Command execution result
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
        
        # Send command
        await self._ws_send({
            "type": "cdp_command",
            "data": {
                "requestId": request_id,
                "method": method,
                "params": params or {},
            }
        })
        
        # Wait for response
        try:
            result = await asyncio.wait_for(future, timeout=self._timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise CDPError(f"Command timeout: {method}")
    
    # ============================================================
    # Navigation Control
    # ============================================================
    
    async def navigate(self, url: str) -> dict:
        """Navigate to URL"""
        return await self._send_command("navigate", {"url": url})
    
    async def reload(self) -> dict:
        """Reload page"""
        return await self._send_command("Page.reload")
    
    async def get_url(self) -> str:
        """Get current URL"""
        result = await self._send_command("getURL")
        return result.get("url", "")
    
    async def get_title(self) -> str:
        """Get page title"""
        result = await self._send_command("getTitle")
        return result.get("title", "")
    
    # ============================================================
    # Mouse Control
    # ============================================================
    
    async def click(self, x: int, y: int, options: dict = None) -> dict:
        """Click at specified coordinates"""
        return await self._send_command("click", {
            "x": x,
            "y": y,
            "options": options or {},
        })
    
    async def click_selector(self, selector: str) -> dict:
        """Click element matching selector"""
        return await self._send_command("clickSelector", {"selector": selector})
    
    async def double_click(self, x: int, y: int) -> dict:
        """Double click"""
        return await self._send_command("click", {
            "x": x,
            "y": y,
            "options": {"clickCount": 2},
        })
    
    # ============================================================
    # Keyboard Control
    # ============================================================
    
    async def type_text(self, text: str) -> dict:
        """Type text"""
        return await self._send_command("type", {"text": text})
    
    async def type_in_selector(self, selector: str, text: str) -> dict:
        """Type text into element"""
        return await self._send_command("typeInSelector", {
            "selector": selector,
            "text": text,
        })
    
    async def press_key(self, key: str) -> dict:
        """Press a key"""
        return await self._send_command("pressKey", {"key": key})
    
    # ============================================================
    # DOM Operations
    # ============================================================
    
    async def query_selector(self, selector: str) -> Optional[int]:
        """Query element, returns node ID"""
        result = await self._send_command("querySelector", {"selector": selector})
        return result.get("nodeId")
    
    async def get_bounding_box(self, node_id: int) -> Optional[dict]:
        """Get element bounding box"""
        result = await self._send_command("getBoundingBox", {"nodeId": node_id})
        return result.get("box")
    
    # ============================================================
    # Screenshot
    # ============================================================
    
    async def screenshot(self, options: dict = None) -> str:
        """Take page screenshot, returns base64"""
        result = await self._send_command("screenshot", {"options": options or {}})
        return result.get("data", "")
    
    # ============================================================
    # JavaScript Execution
    # ============================================================
    
    async def evaluate(self, expression: str) -> Any:
        """Execute JavaScript"""
        result = await self._send_command("evaluate", {"expression": expression})
        return result.get("value")
    
    # ============================================================
    # Advanced Operations (Combined Commands)
    # ============================================================
    
    async def fill_form(self, selector: str, value: str) -> dict:
        """
        Fill form field
        1. Click element
        2. Clear existing content
        3. Type new content
        """
        await self.click_selector(selector)
        await asyncio.sleep(0.1)
        # Select all and delete
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
        Wait for element to appear
        
        Args:
            selector: CSS selector
            timeout: Timeout in seconds
            interval: Check interval in seconds
            
        Returns:
            Whether element appeared
        """
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            node_id = await self.query_selector(selector)
            if node_id:
                return True
            await asyncio.sleep(interval)
        return False


class CDPError(Exception):
    """CDP command execution error"""
    pass

