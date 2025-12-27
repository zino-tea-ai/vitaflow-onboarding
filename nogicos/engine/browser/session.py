# -*- coding: utf-8 -*-
"""
Browser Session - Playwright wrapper

Handles browser lifecycle and page state capture.
"""

import asyncio
import gc
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from tempfile import TemporaryDirectory
from typing import Optional, Dict, Any

import PIL.Image
from playwright.async_api import (
    async_playwright,
    Browser as PlaywrightBrowser,
    BrowserContext,
    Page,
    Playwright,
)

from engine.browser.visual import visual_feedback


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"


@dataclass
class PageState:
    """Snapshot of current page state"""
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


class BrowserSession:
    """
    Browser session manager
    
    Usage:
        async with BrowserSession() as browser:
            await browser.goto("https://example.com")
            state = await browser.observe()
    """
    
    def __init__(self, headless: bool = False):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[PlaywrightBrowser] = None
        self._context: Optional[BrowserContext] = None
        self.active_page: Optional[Page] = None
        self._temp_dir = TemporaryDirectory()
        self._screenshot_count = 0
        self._cdp_sessions: Dict[Page, Any] = {}
        self._headless = headless
    
    @property
    def page(self) -> Optional[Page]:
        """Alias for active_page (compatibility with CDPBrowser)"""
        return self.active_page
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(
        self,
        url: str = "about:blank",
        headless: bool = False,
        width: int = 1280,
        height: int = 720,
    ) -> "BrowserSession":
        """Start browser and navigate to URL"""
        self._playwright = await async_playwright().start()
        
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--ignore-certificate-errors",
            ],
        )
        
        self._context = await self._browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": width, "height": height},
            locale="en-US",
        )
        self._context.set_default_timeout(15000)
        self._context.set_default_navigation_timeout(30000)
        
        self.active_page = await self._context.new_page()
        
        if url != "about:blank":
            await self.active_page.goto(url)
        
        print(f"[Browser] Started, navigated to {url}")
        return self
    
    async def close(self):
        """Close browser"""
        try:
            if self.active_page:
                await self.active_page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            print(f"[Browser] Error closing: {e}")
    
    async def stop(self):
        """Alias for close()"""
        await self.close()
    
    async def goto(self, url: str):
        """Navigate to URL"""
        await self.active_page.goto(url)
        await self.active_page.wait_for_load_state("load")
        # Reset visual feedback state for new page
        visual_feedback.reset()
    
    async def observe(self) -> PageState:
        """Capture current page state"""
        await self.active_page.wait_for_load_state("load")
        
        screenshot = await self._take_screenshot()
        ax_tree = await self._capture_accessibility_tree()
        
        return PageState(
            id=uuid.uuid4().hex,
            url=self.active_page.url,
            title=await self.active_page.title(),
            timestamp=time.time(),
            screenshot=screenshot,
            accessibility_tree=ax_tree,
        )
    
    async def _take_screenshot(self) -> Optional[PIL.Image.Image]:
        """Take screenshot"""
        self._screenshot_count += 1
        path = os.path.join(
            self._temp_dir.name,
            f"screenshot_{self._screenshot_count}.png"
        )
        
        try:
            await self.active_page.screenshot(path=path, timeout=15000)
            
            with PIL.Image.open(path) as img:
                screenshot = img.copy()
            
            # Cleanup
            if sys.platform == 'win32':
                gc.collect()
                try:
                    os.remove(path)
                except PermissionError:
                    pass
            else:
                os.remove(path)
            
            return screenshot
        except Exception as e:
            print(f"[Browser] Screenshot error: {e}")
            return None
    
    async def _capture_accessibility_tree(self) -> dict:
        """Capture accessibility tree via CDP"""
        try:
            if self.active_page not in self._cdp_sessions:
                self._cdp_sessions[self.active_page] = await self._context.new_cdp_session(self.active_page)
            
            cdp = self._cdp_sessions[self.active_page]
            result = await cdp.send("Accessibility.getFullAXTree")
            nodes = result.get("nodes", [])
            
            if nodes:
                return self._build_tree(nodes)
            return {}
        except Exception as e:
            print(f"[Browser] AX tree error: {e}")
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


async def create_browser(
    url: str = "https://news.ycombinator.com",
    headless: bool = False,
) -> BrowserSession:
    """Factory to create and start browser"""
    session = BrowserSession()
    await session.start(url=url, headless=headless)
    return session

