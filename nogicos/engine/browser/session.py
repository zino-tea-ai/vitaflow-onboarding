# -*- coding: utf-8 -*-
"""
Browser Session Manager - CDP/Playwright based browser control

Provides a unified interface for browser automation that works with:
1. Electron's WebContentsView via CDP (when available)
2. Playwright in headless mode (fallback)

This module bridges the gap between NogicOS tools and actual browser control.
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger("nogicos.browser.session")

# ============================================================================
# Playwright Integration (Fallback for headless browser automation)
# ============================================================================

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
    logger.info("[BrowserSession] Playwright available")
except ImportError:
    logger.warning("[BrowserSession] Playwright not installed. Run: pip install playwright && playwright install")
    Browser = None
    Page = None
    BrowserContext = None


@dataclass
class BrowserState:
    """Current state of the browser session"""
    url: str = ""
    title: str = ""
    is_loading: bool = False
    can_go_back: bool = False
    can_go_forward: bool = False


class BrowserSession:
    """
    Unified browser session manager.
    
    Supports:
    - Playwright-based headless browsing (default)
    - CDP-based control via Electron (when connected)
    
    Usage:
        session = BrowserSession()
        await session.start()
        await session.navigate("https://google.com")
        content = await session.get_page_content()
        await session.stop()
    """
    
    def __init__(
        self,
        headless: bool = True,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize browser session.
        
        Args:
            headless: Run browser in headless mode (default: True)
            viewport: Custom viewport size {"width": 1280, "height": 720}
            user_agent: Custom user agent string
        """
        self.headless = headless
        self.viewport = viewport or {"width": 1280, "height": 720}
        self.user_agent = user_agent
        
        # Playwright objects
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
        # State
        self._started = False
        self._state = BrowserState()
    
    @property
    def is_started(self) -> bool:
        """Check if browser session is started"""
        return self._started and self._page is not None
    
    @property
    def state(self) -> BrowserState:
        """Get current browser state"""
        return self._state
    
    async def start(self) -> bool:
        """
        Start the browser session.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self._started:
            logger.warning("[BrowserSession] Already started")
            return True
        
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("[BrowserSession] Playwright not available, cannot start")
            return False
        
        try:
            self._playwright = await async_playwright().start()
            
            # Launch browser
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                ]
            )
            
            # Create context with viewport and user agent
            context_options = {
                "viewport": self.viewport,
            }
            if self.user_agent:
                context_options["user_agent"] = self.user_agent
            
            self._context = await self._browser.new_context(**context_options)
            
            # Create page
            self._page = await self._context.new_page()
            
            # Setup event listeners
            self._page.on("load", self._on_load)
            self._page.on("framenavigated", self._on_navigated)
            
            self._started = True
            logger.info("[BrowserSession] Started successfully")
            return True
            
        except Exception as e:
            logger.error(f"[BrowserSession] Failed to start: {e}")
            await self.stop()
            return False
    
    async def stop(self) -> None:
        """Stop the browser session and cleanup resources"""
        try:
            if self._page:
                await self._page.close()
                self._page = None
            
            if self._context:
                await self._context.close()
                self._context = None
            
            if self._browser:
                await self._browser.close()
                self._browser = None
            
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            
            self._started = False
            logger.info("[BrowserSession] Stopped")
            
        except Exception as e:
            logger.warning(f"[BrowserSession] Error during stop: {e}")
    
    def _on_load(self, page: Page) -> None:
        """Handle page load event"""
        self._state.is_loading = False
    
    def _on_navigated(self, frame) -> None:
        """Handle frame navigation event"""
        if frame == self._page.main_frame:
            self._state.url = frame.url
    
    # ========================================================================
    # Navigation Methods
    # ========================================================================
    
    async def navigate(self, url: str, timeout: float = 30.0) -> bool:
        """
        Navigate to a URL.
        
        Args:
            url: URL to navigate to
            timeout: Navigation timeout in seconds
            
        Returns:
            True if navigation successful
        """
        if not self._page:
            logger.error("[BrowserSession] Page not available")
            return False
        
        try:
            self._state.is_loading = True
            await self._page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            self._state.url = url
            self._state.title = await self._page.title()
            self._state.is_loading = False
            
            # Update navigation state
            self._state.can_go_back = await self._can_go_back()
            
            logger.info(f"[BrowserSession] Navigated to: {url}")
            return True
            
        except Exception as e:
            logger.error(f"[BrowserSession] Navigation failed: {e}")
            self._state.is_loading = False
            return False
    
    async def _can_go_back(self) -> bool:
        """Check if can go back in history"""
        try:
            # Playwright doesn't have direct history access, so we track state
            return len(self._page.url) > 0
        except:
            return False
    
    async def go_back(self) -> bool:
        """Go back in browser history"""
        if not self._page:
            return False
        
        try:
            await self._page.go_back(timeout=10000)
            self._state.url = self._page.url
            self._state.title = await self._page.title()
            return True
        except Exception as e:
            logger.error(f"[BrowserSession] Go back failed: {e}")
            return False
    
    async def go_forward(self) -> bool:
        """Go forward in browser history"""
        if not self._page:
            return False
        
        try:
            await self._page.go_forward(timeout=10000)
            self._state.url = self._page.url
            self._state.title = await self._page.title()
            return True
        except Exception as e:
            logger.error(f"[BrowserSession] Go forward failed: {e}")
            return False
    
    async def reload(self) -> bool:
        """Reload the current page"""
        if not self._page:
            return False
        
        try:
            await self._page.reload(timeout=30000)
            return True
        except Exception as e:
            logger.error(f"[BrowserSession] Reload failed: {e}")
            return False
    
    async def get_current_url(self) -> str:
        """Get the current page URL"""
        if not self._page:
            return ""
        return self._page.url
    
    async def get_title(self) -> str:
        """Get the current page title"""
        if not self._page:
            return ""
        try:
            return await self._page.title()
        except:
            return ""
    
    # ========================================================================
    # Interaction Methods
    # ========================================================================
    
    async def click(self, selector: str, timeout: float = 5.0) -> bool:
        """
        Click an element by selector.
        
        Args:
            selector: CSS selector or text selector
            timeout: Click timeout in seconds
            
        Returns:
            True if click successful
        """
        if not self._page:
            return False
        
        try:
            # Try CSS selector first
            await self._page.click(selector, timeout=timeout * 1000)
            return True
        except Exception as e:
            # Try text-based selector
            try:
                await self._page.click(f"text={selector}", timeout=timeout * 1000)
                return True
            except:
                logger.error(f"[BrowserSession] Click failed: {e}")
                return False
    
    async def type(self, selector: str, text: str, delay: float = 0.05) -> bool:
        """
        Type text into an element.
        
        Args:
            selector: CSS selector for input element
            text: Text to type
            delay: Delay between keystrokes in seconds
            
        Returns:
            True if typing successful
        """
        if not self._page:
            return False
        
        try:
            await self._page.fill(selector, text)
            return True
        except Exception as e:
            # Fallback to type with delay for non-input elements
            try:
                await self._page.click(selector, timeout=5000)
                await self._page.keyboard.type(text, delay=delay * 1000)
                return True
            except:
                logger.error(f"[BrowserSession] Type failed: {e}")
                return False
    
    async def send_keys(self, keys: str) -> bool:
        """
        Send keyboard keys.
        
        Args:
            keys: Key or key combination (e.g., "Enter", "Control+A")
            
        Returns:
            True if successful
        """
        if not self._page:
            return False
        
        try:
            await self._page.keyboard.press(keys)
            return True
        except Exception as e:
            logger.error(f"[BrowserSession] Send keys failed: {e}")
            return False
    
    async def scroll(self, direction: str = "down", amount: int = 500) -> bool:
        """
        Scroll the page.
        
        Args:
            direction: "up", "down", "top", or "bottom"
            amount: Scroll amount in pixels (for up/down)
            
        Returns:
            True if successful
        """
        if not self._page:
            return False
        
        try:
            if direction == "top":
                await self._page.evaluate("window.scrollTo(0, 0)")
            elif direction == "bottom":
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction == "up":
                await self._page.evaluate(f"window.scrollBy(0, -{amount})")
            else:  # down
                await self._page.evaluate(f"window.scrollBy(0, {amount})")
            return True
        except Exception as e:
            logger.error(f"[BrowserSession] Scroll failed: {e}")
            return False
    
    # ========================================================================
    # Content Extraction
    # ========================================================================
    
    async def get_page_content(self) -> str:
        """
        Get the full text content of the page.
        
        Returns:
            Page text content
        """
        if not self._page:
            return ""
        
        try:
            return await self._page.evaluate("document.body.innerText")
        except Exception as e:
            logger.error(f"[BrowserSession] Get content failed: {e}")
            return ""
    
    async def extract_text(self, selector: str) -> str:
        """
        Extract text from a specific element.
        
        Args:
            selector: CSS selector
            
        Returns:
            Element text content
        """
        if not self._page:
            return ""
        
        try:
            element = await self._page.query_selector(selector)
            if element:
                return await element.inner_text()
            return ""
        except Exception as e:
            logger.error(f"[BrowserSession] Extract text failed: {e}")
            return ""
    
    async def screenshot(self, full_page: bool = False) -> bytes:
        """
        Take a screenshot of the page.
        
        Args:
            full_page: Capture full scrollable page
            
        Returns:
            Screenshot as PNG bytes
        """
        if not self._page:
            return b""
        
        try:
            return await self._page.screenshot(full_page=full_page, type="png")
        except Exception as e:
            logger.error(f"[BrowserSession] Screenshot failed: {e}")
            return b""
    
    async def get_element_at(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        """
        Get element information at specific coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Element info dict or None
        """
        if not self._page:
            return None
        
        try:
            element_info = await self._page.evaluate(f"""
                () => {{
                    const elem = document.elementFromPoint({x}, {y});
                    if (!elem) return null;
                    return {{
                        tagName: elem.tagName,
                        id: elem.id,
                        className: elem.className,
                        text: elem.innerText?.slice(0, 100),
                        href: elem.href || null,
                    }};
                }}
            """)
            return element_info
        except Exception as e:
            logger.error(f"[BrowserSession] Get element failed: {e}")
            return None
    
    async def wait_for_selector(
        self,
        selector: str,
        timeout: float = 10.0,
        state: str = "visible"
    ) -> bool:
        """
        Wait for an element to appear.
        
        Args:
            selector: CSS selector
            timeout: Wait timeout in seconds
            state: "attached", "detached", "visible", or "hidden"
            
        Returns:
            True if element found within timeout
        """
        if not self._page:
            return False
        
        try:
            await self._page.wait_for_selector(
                selector,
                timeout=timeout * 1000,
                state=state
            )
            return True
        except Exception as e:
            logger.warning(f"[BrowserSession] Wait for selector timeout: {e}")
            return False


# ============================================================================
# Session Manager (Singleton for managing the active session)
# ============================================================================

_active_session: Optional[BrowserSession] = None


async def get_browser_session() -> BrowserSession:
    """
    Get or create the active browser session.
    
    Returns:
        Active BrowserSession instance
    """
    global _active_session
    
    if _active_session is None or not _active_session.is_started:
        _active_session = BrowserSession(headless=True)
        await _active_session.start()
    
    return _active_session


async def close_browser_session() -> None:
    """Close the active browser session"""
    global _active_session
    
    if _active_session:
        await _active_session.stop()
        _active_session = None

