# -*- coding: utf-8 -*-
"""
CDP Browser Session - Electron 内部浏览器控制

使用 StatusServer.send_cdp_command 通过 WebSocket 控制 Electron 窗口内的浏览器
兼容 BrowserSession 接口，可作为 Playwright 的替代方案

用法：
    session = CDPBrowserSession(status_server)
    await session.start(url="https://example.com")
    state = await session.observe()
    await session.close()
"""

import asyncio
import base64
import io
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Awaitable, TYPE_CHECKING

import PIL.Image

if TYPE_CHECKING:
    from engine.server.websocket import StatusServer

class CDPError(Exception):
    """CDP 命令执行错误"""
    pass


class CDPLocator:
    """
    Playwright Locator 兼容层
    
    模拟 Playwright 的 Locator API，使 AI 生成的代码能够在 CDP 模式下运行。
    
    支持的 API:
        - locator.first
        - locator.click()
        - locator.fill(value)
        - locator.press(key)
        - locator.type(text)
    """
    
    def __init__(self, session: "CDPBrowserSession", selector: str):
        self._session = session
        self._selector = selector
    
    @property
    def first(self) -> "CDPLocator":
        """返回第一个匹配的元素（CDP 模式下就是自身）"""
        return self
    
    async def click(self, **kwargs):
        """点击元素"""
        await self._session._send_cdp("clickSelector", {"selector": self._selector})
    
    async def fill(self, value: str, **kwargs):
        """填充文本"""
        await self._session._send_cdp("typeInSelector", {"selector": self._selector, "text": value})
    
    async def type(self, text: str, **kwargs):
        """输入文本"""
        await self._session._send_cdp("typeInSelector", {"selector": self._selector, "text": text})
    
    async def press(self, key: str, **kwargs):
        """按键"""
        # 先聚焦到元素，然后按键
        await self._session._send_cdp("clickSelector", {"selector": self._selector})
        await self._session._send_cdp("pressKey", {"key": key})
    
    async def inner_text(self) -> str:
        """获取元素文本"""
        result = await self._session._send_cdp("evaluate", {
            "expression": f"document.querySelector('{self._selector}')?.innerText || ''"
        })
        return result.get("value", "") if result else ""
    
    async def get_attribute(self, name: str) -> str:
        """获取元素属性"""
        result = await self._session._send_cdp("evaluate", {
            "expression": f"document.querySelector('{self._selector}')?.getAttribute('{name}') || ''"
        })
        return result.get("value", "") if result else ""


@dataclass
class PageState:
    """Snapshot of current page state (兼容 session.py 的 PageState)"""
    id: str
    url: str
    title: str
    timestamp: float
    screenshot: Optional[PIL.Image.Image] = None
    accessibility_tree: Dict[str, Any] = field(default_factory=dict)
    
    def get_axtree_string(self) -> str:
        """Format accessibility tree as string"""
        if not self.accessibility_tree:
            return "[No accessibility tree]"
        return self._format_node(self.accessibility_tree)
    
    def _format_node(self, node: dict, indent: int = 0) -> str:
        """Recursively format tree node"""
        lines = []
        role = node.get("role", "unknown")
        name = node.get("name", "")
        
        prefix = "  " * indent
        line = f"{prefix}[{node.get('id', '?')}] {role}"
        if name:
            line += f' "{name[:50]}"'
        lines.append(line)
        
        for child in node.get("children", []):
            lines.append(self._format_node(child, indent + 1))
        
        return "\n".join(lines)


class CDPBrowserSession:
    """
    CDP-based browser session for Electron internal control
    
    兼容 BrowserSession 接口，使用 CDP 命令而非 Playwright
    
    Usage:
        async with CDPBrowserSession(status_server) as browser:
            await browser.goto("https://example.com")
            state = await browser.observe()
    """
    
    def __init__(self, status_server: "StatusServer"):
        """
        Args:
            status_server: StatusServer 实例（用于发送 CDP 命令到 Electron）
        """
        self._server = status_server
        self._current_url = ""
        self._started = False
    
    @property
    def active_page(self):
        """Compatibility property (CDP 模式下没有实际的 Page 对象)"""
        return self
    
    @property
    def page(self):
        """Alias for active_page"""
        return self
    
    @property
    def url(self) -> str:
        """Current URL"""
        return self._current_url
    
    async def _send_cdp(self, method: str, params: dict = None, timeout: float = 30.0) -> Any:
        """发送 CDP 命令"""
        return await self._server.send_cdp_command(method, params, timeout)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(
        self,
        url: str = "about:blank",
        headless: bool = True,  # 忽略，CDP 模式始终使用 Electron 窗口
        width: int = 1280,
        height: int = 720,
    ) -> "CDPBrowserSession":
        """Start browser session and navigate to URL"""
        self._started = True
        
        if url != "about:blank":
            await self.goto(url)
        
        print(f"[CDPBrowser] Started, navigated to {url}")
        return self
    
    async def close(self):
        """Close browser session (CDP 模式下仅重置状态)"""
        self._started = False
        self._current_url = ""
    
    async def stop(self):
        """Alias for close()"""
        await self.close()
    
    async def goto(self, url: str):
        """Navigate to URL"""
        await self._send_cdp("navigate", {"url": url})
        self._current_url = url
        # 等待页面加载
        await asyncio.sleep(1.5)  # 简单等待，后续可改进
    
    async def observe(self) -> PageState:
        """Capture current page state"""
        # 获取基本信息
        url_result = await self._send_cdp("getURL")
        url = url_result.get("url", "") if url_result else ""
        
        title_result = await self._send_cdp("getTitle")
        title = title_result.get("title", "") if title_result else ""
        
        # 截图
        screenshot = await self._take_screenshot()
        
        # 获取可访问性树
        ax_tree = await self._capture_accessibility_tree()
        
        return PageState(
            id=uuid.uuid4().hex,
            url=url,
            title=title,
            timestamp=time.time(),
            screenshot=screenshot,
            accessibility_tree=ax_tree,
        )
    
    async def _take_screenshot(self) -> Optional[PIL.Image.Image]:
        """Take screenshot via CDP"""
        try:
            result = await self._send_cdp("screenshot", {"options": {"format": "png"}})
            image_base64 = result.get("data", "") if result else ""
            if image_base64:
                image_data = base64.b64decode(image_base64)
                return PIL.Image.open(io.BytesIO(image_data))
            return None
        except Exception as e:
            print(f"[CDPBrowser] Screenshot error: {e}")
            return None
    
    async def _capture_accessibility_tree(self) -> dict:
        """Capture accessibility tree via CDP"""
        try:
            result = await self._send_cdp("Accessibility.getFullAXTree")
            nodes = result.get("nodes", []) if result else []
            
            if nodes:
                return self._build_tree(nodes)
            return {}
        except Exception as e:
            print(f"[CDPBrowser] AX tree error: {e}")
            return {}
    
    def _build_tree(self, nodes: list) -> dict:
        """Build hierarchical tree from flat nodes"""
        if not nodes:
            return {}
        
        node_map = {}
        for i, node in enumerate(nodes):
            node_id = node.get("nodeId", str(i))
            node_map[node_id] = {
                "id": node_id,
                "role": node.get("role", {}).get("value", "unknown"),
                "name": node.get("name", {}).get("value", ""),
                "children": [],
            }
        
        for node in nodes:
            node_id = node.get("nodeId")
            parent_id = node.get("parentId")
            if parent_id and parent_id in node_map and node_id in node_map:
                node_map[parent_id]["children"].append(node_map[node_id])
        
        root_id = nodes[0].get("nodeId") if nodes else None
        return node_map.get(root_id, {})
    
    # ============================================================
    # 浏览器操作方法（兼容 Playwright Page 接口）
    # ============================================================
    
    async def click(self, selector: str, **kwargs):
        """Click an element by selector"""
        await self._send_cdp("clickSelector", {"selector": selector})
    
    async def fill(self, selector: str, value: str, **kwargs):
        """Fill text into an element"""
        await self._send_cdp("typeInSelector", {"selector": selector, "text": value})
    
    async def type(self, selector: str, text: str, **kwargs):
        """Type text into an element"""
        await self._send_cdp("typeInSelector", {"selector": selector, "text": text})
    
    async def press(self, key: str, **kwargs):
        """Press a key"""
        await self._send_cdp("pressKey", {"key": key})
    
    async def wait_for_selector(
        self,
        selector: str,
        timeout: float = 10000,  # 毫秒
        **kwargs
    ):
        """Wait for an element to appear"""
        timeout_sec = timeout / 1000
        start = time.time()
        while time.time() - start < timeout_sec:
            result = await self._send_cdp("querySelector", {"selector": selector})
            if result and result.get("nodeId"):
                return
            await asyncio.sleep(0.5)
        raise CDPError(f"Timeout waiting for selector: {selector}")
    
    async def wait_for_load_state(self, state: str = "load", **kwargs):
        """Wait for page load state"""
        # 简单实现：等待一段时间
        await asyncio.sleep(0.5)
    
    async def evaluate(self, expression: str, *args, **kwargs):
        """
        Execute JavaScript in the page
        
        兼容 Playwright 的 evaluate API:
        - page.evaluate("() => 1 + 1")
        - page.evaluate("(a, b) => a + b", 1, 2)
        """
        # 如果有额外参数，将它们注入到 JS 代码中
        if args:
            # 将参数序列化为 JSON 并在 JS 中解析
            import json
            args_json = json.dumps(args)
            # 包装表达式，将参数传入
            wrapped_expression = f"""
                (function() {{
                    const __args = {args_json};
                    const __fn = {expression};
                    return __fn(...__args);
                }})()
            """
            expression = wrapped_expression
        
        result = await self._send_cdp("evaluate", {"expression": expression})
        return result.get("value") if result else None
    
    async def query_selector(self, selector: str):
        """Query for an element"""
        result = await self._send_cdp("querySelector", {"selector": selector})
        return result.get("nodeId") if result else None
    
    # ============================================================
    # Playwright Locator 兼容 API
    # ============================================================
    
    def locator(self, selector: str) -> CDPLocator:
        """
        Playwright locator() 兼容方法
        
        支持的选择器格式:
        - CSS: 'input[type="text"]', '.class', '#id'
        - Text: 'text=Submit' (直接传递给 Electron 处理)
        """
        # 直接传递选择器，Electron 端会处理 text= 和 XPath
        return CDPLocator(self, selector)
    
    def get_by_role(self, role: str, name: str = None, **kwargs) -> CDPLocator:
        """
        Playwright get_by_role() 兼容方法
        
        Args:
            role: ARIA 角色 (button, textbox, link, etc.)
            name: 元素的可访问名称
        """
        if name:
            # 使用 XPath 来匹配 role 和包含特定文本的元素
            # 这比 CSS 选择器更可靠
            selector = f'xpath=//*[@role="{role}"][contains(., "{name}")]'
        else:
            selector = f'[role="{role}"]'
        
        return CDPLocator(self, selector)
    
    def get_by_text(self, text: str, **kwargs) -> CDPLocator:
        """Playwright get_by_text() 兼容方法"""
        return self.locator(f"text={text}")
    
    def get_by_placeholder(self, placeholder: str, **kwargs) -> CDPLocator:
        """Playwright get_by_placeholder() 兼容方法"""
        return CDPLocator(self, f'[placeholder*="{placeholder}"]')
    
    def get_by_label(self, label: str, **kwargs) -> CDPLocator:
        """Playwright get_by_label() 兼容方法"""
        return CDPLocator(self, f'[aria-label*="{label}"]')
    
    async def screenshot(self, **kwargs) -> bytes:
        """Take screenshot and return bytes"""
        path = kwargs.get("path")
        result = await self._send_cdp("screenshot", {"options": {"format": "png"}})
        image_base64 = result.get("data", "") if result else ""
        image_bytes = base64.b64decode(image_base64)
        
        if path:
            with open(path, "wb") as f:
                f.write(image_bytes)
        
        return image_bytes
    
    async def title(self) -> str:
        """Get page title"""
        result = await self._send_cdp("getTitle")
        return result.get("title", "") if result else ""
    
    async def get_screenshot_base64(self, format: str = "jpeg", quality: int = 70) -> str:
        """Get screenshot as base64 string"""
        result = await self._send_cdp("screenshot", {"options": {"format": format, "quality": quality}})
        return result.get("data", "") if result else ""


async def create_cdp_browser(
    status_server: "StatusServer",
    url: str = "https://news.ycombinator.com",
) -> CDPBrowserSession:
    """Factory to create and start CDP browser session"""
    session = CDPBrowserSession(status_server)
    await session.start(url=url)
    return session

