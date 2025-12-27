# -*- coding: utf-8 -*-
"""
CDP Bridge - Connect Playwright to External Browser via Chrome DevTools Protocol

This module enables Python to control an Electron webview or any Chromium browser
that exposes a CDP endpoint.

Usage:
    # Connect to Electron with CDP enabled
    async with CDPBrowser("http://localhost:9222") as browser:
        page = browser.page
        await page.goto("https://example.com")
        state = await browser.observe()
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import time
import uuid

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("nogicos.cdp")


@dataclass
class PageState:
    """Snapshot of current page state"""
    id: str
    url: str
    title: str
    timestamp: float
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


class CDPBrowser:
    """
    CDP Browser - Connect to external browser via Chrome DevTools Protocol
    
    Architecture:
        ┌─────────────────┐       CDP        ┌─────────────────┐
        │  Electron App   │ ◄───────────────►│  Python Engine  │
        │  (Port 9222)    │    WebSocket     │  (Playwright)   │
        └─────────────────┘                  └─────────────────┘
    
    Usage:
        browser = CDPBrowser("http://localhost:9222")
        await browser.connect()
        page = browser.page
        await page.click("button")
        await browser.close()
    
    Or with context manager:
        async with CDPBrowser("http://localhost:9222") as browser:
            await browser.page.goto("https://example.com")
    """
    
    def __init__(
        self,
        cdp_url: str = "http://localhost:9222",
        timeout: int = 30000,
    ):
        self.cdp_url = cdp_url
        self.timeout = timeout
        
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._cdp_session = None
        self._connected = False
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    @property
    def page(self) -> Optional[Page]:
        """Get the active page"""
        return self._page
    
    @property
    def active_page(self) -> Optional[Page]:
        """Alias for page (compatibility with BrowserSession)"""
        return self._page
    
    @property
    def connected(self) -> bool:
        """Check if connected to CDP"""
        return self._connected
    
    async def connect(self, max_retries: int = 5, retry_delay: float = 1.0) -> bool:
        """
        Connect to browser via CDP
        
        Args:
            max_retries: Maximum connection attempts
            retry_delay: Delay between retries (seconds)
        
        Returns:
            True if connected successfully
        """
        self._playwright = await async_playwright().start()
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[CDP] Connecting to {self.cdp_url} (attempt {attempt + 1}/{max_retries})")
                
                # Connect over CDP
                self._browser = await self._playwright.chromium.connect_over_cdp(
                    self.cdp_url,
                    timeout=self.timeout,
                )
                
                # Get existing context and page
                contexts = self._browser.contexts
                if contexts:
                    self._context = contexts[0]
                    pages = self._context.pages
                    if pages:
                        self._page = pages[0]
                    else:
                        self._page = await self._context.new_page()
                else:
                    # Create new context if none exists
                    self._context = await self._browser.new_context()
                    self._page = await self._context.new_page()
                
                # Set default timeouts
                self._context.set_default_timeout(15000)
                self._context.set_default_navigation_timeout(30000)
                
                self._connected = True
                logger.info(f"[CDP] Connected! Page: {self._page.url}")
                return True
                
            except Exception as e:
                logger.warning(f"[CDP] Connection failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"[CDP] All connection attempts failed")
                    raise ConnectionError(f"Could not connect to CDP at {self.cdp_url}: {e}")
        
        return False
    
    async def close(self):
        """Disconnect from CDP"""
        try:
            # Don't close the browser itself, just disconnect
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            self._connected = False
            logger.info("[CDP] Disconnected")
        except Exception as e:
            logger.warning(f"[CDP] Error during disconnect: {e}")
    
    async def goto(self, url: str):
        """Navigate to URL"""
        if not self._page:
            raise RuntimeError("Not connected to browser")
        await self._page.goto(url)
        await self._page.wait_for_load_state("load")
    
    async def observe(self) -> PageState:
        """Capture current page state"""
        if not self._page:
            raise RuntimeError("Not connected to browser")
        
        await self._page.wait_for_load_state("load")
        
        ax_tree = await self._capture_accessibility_tree()
        
        return PageState(
            id=uuid.uuid4().hex,
            url=self._page.url,
            title=await self._page.title(),
            timestamp=time.time(),
            accessibility_tree=ax_tree,
        )
    
    async def _capture_accessibility_tree(self) -> dict:
        """Capture accessibility tree via CDP"""
        try:
            if not self._cdp_session:
                self._cdp_session = await self._context.new_cdp_session(self._page)
            
            result = await self._cdp_session.send("Accessibility.getFullAXTree")
            nodes = result.get("nodes", [])
            
            if nodes:
                return self._build_tree(nodes)
            return {}
        except Exception as e:
            logger.warning(f"[CDP] AX tree error: {e}")
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
    
    async def wait_for_selector(self, selector: str, timeout: int = 15000):
        """Wait for element to appear"""
        if not self._page:
            raise RuntimeError("Not connected to browser")
        await self._page.wait_for_selector(selector, timeout=timeout)
    
    async def click(self, selector: str, timeout: int = 15000):
        """Click an element"""
        if not self._page:
            raise RuntimeError("Not connected to browser")
        await self._page.click(selector, timeout=timeout)
    
    async def fill(self, selector: str, value: str, timeout: int = 15000):
        """Fill an input field"""
        if not self._page:
            raise RuntimeError("Not connected to browser")
        await self._page.fill(selector, value, timeout=timeout)
    
    async def evaluate(self, expression: str):
        """Evaluate JavaScript in page context"""
        if not self._page:
            raise RuntimeError("Not connected to browser")
        return await self._page.evaluate(expression)


async def connect_to_electron(
    port: int = 9222,
    host: str = "localhost",
    timeout: int = 30000,
) -> CDPBrowser:
    """
    Factory function to connect to Electron browser
    
    Args:
        port: CDP port (default 9222)
        host: CDP host (default localhost)
        timeout: Connection timeout in ms
    
    Returns:
        Connected CDPBrowser instance
    """
    cdp_url = f"http://{host}:{port}"
    browser = CDPBrowser(cdp_url, timeout=timeout)
    await browser.connect()
    return browser


# Quick test
if __name__ == "__main__":
    import sys
    
    async def test_cdp():
        print("=" * 50)
        print("CDP Bridge Test")
        print("=" * 50)
        
        # Check if port is provided
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 9222
        cdp_url = f"http://localhost:{port}"
        
        print(f"\n[1] Testing connection to {cdp_url}")
        
        try:
            async with CDPBrowser(cdp_url) as browser:
                print(f"[OK] Connected to browser")
                print(f"     URL: {browser.page.url}")
                
                print(f"\n[2] Getting page state")
                state = await browser.observe()
                print(f"[OK] Page state captured")
                print(f"     Title: {state.title}")
                print(f"     AXTree lines: {len(state.get_axtree_string().split(chr(10)))}")
                
                print("\n" + "=" * 50)
                print("CDP Bridge Test PASSED!")
                print("=" * 50)
                
        except ConnectionError as e:
            print(f"\n[INFO] No browser found at {cdp_url}")
            print(f"       Start Electron with: --remote-debugging-port={port}")
            print(f"       Or run a Chromium browser with the same flag")
            print("\n[SKIP] CDP test skipped (no browser)")
    
    asyncio.run(test_cdp())

