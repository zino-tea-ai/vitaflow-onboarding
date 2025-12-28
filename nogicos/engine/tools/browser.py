# -*- coding: utf-8 -*-
"""
Browser Tools - Web automation tools for NogicOS Agent

Reference: browser-use/actor/page.py, browser-use/dom/service.py
"""

import logging
import base64
from typing import Optional, Dict, Any, List

from .base import ToolRegistry, ToolCategory, get_registry

logger = logging.getLogger(__name__)


def register_browser_tools(registry: Optional[ToolRegistry] = None) -> ToolRegistry:
    """
    Register all browser tools to the registry.
    
    Args:
        registry: Optional registry to use. If None, uses global registry.
        
    Returns:
        The registry with browser tools registered.
    """
    if registry is None:
        registry = get_registry()
    
    @registry.action(
        description="Navigate to a URL in the browser. Returns the page title after navigation.",
        category=ToolCategory.BROWSER,
        requires_context=["browser_session"]
    )
    async def browser_navigate(url: str, browser_session=None) -> str:
        """Navigate to a URL"""
        if browser_session is None:
            return "Error: No browser session available"
        
        try:
            # Use the existing CDP session to navigate
            await browser_session.navigate(url)
            title = await browser_session.get_title()
            return f"Navigated to {url}. Page title: {title}"
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return f"Error navigating to {url}: {str(e)}"
    
    @registry.action(
        description="Click on an element identified by CSS selector or text content.",
        category=ToolCategory.BROWSER,
        requires_context=["browser_session"]
    )
    async def browser_click(selector: str, browser_session=None) -> str:
        """Click an element"""
        if browser_session is None:
            return "Error: No browser session available"
        
        try:
            await browser_session.click(selector)
            return f"Clicked element: {selector}"
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return f"Error clicking {selector}: {str(e)}"
    
    @registry.action(
        description="Type text into an input field identified by CSS selector.",
        category=ToolCategory.BROWSER,
        requires_context=["browser_session"]
    )
    async def browser_type(selector: str, text: str, browser_session=None) -> str:
        """Type text into an element"""
        if browser_session is None:
            return "Error: No browser session available"
        
        try:
            await browser_session.type(selector, text)
            return f"Typed '{text}' into {selector}"
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return f"Error typing into {selector}: {str(e)}"
    
    @registry.action(
        description="Take a screenshot of the current page. Returns base64-encoded image.",
        category=ToolCategory.BROWSER,
        requires_context=["browser_session"]
    )
    async def browser_screenshot(browser_session=None) -> str:
        """Take a screenshot"""
        if browser_session is None:
            return "Error: No browser session available"
        
        try:
            screenshot_data = await browser_session.screenshot()
            if isinstance(screenshot_data, bytes):
                screenshot_b64 = base64.b64encode(screenshot_data).decode('utf-8')
            else:
                screenshot_b64 = screenshot_data
            return f"Screenshot captured (base64 length: {len(screenshot_b64)})"
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return f"Error taking screenshot: {str(e)}"
    
    @registry.action(
        description="Extract text content from the page or a specific element. Use a CSS selector to target specific elements, or leave empty to extract all visible text.",
        category=ToolCategory.BROWSER,
        requires_context=["browser_session"]
    )
    async def browser_extract(selector: str = "", browser_session=None) -> str:
        """Extract text from page or element"""
        if browser_session is None:
            return "Error: No browser session available"
        
        try:
            if selector:
                content = await browser_session.extract_text(selector)
            else:
                content = await browser_session.get_page_content()
            return content[:5000] if len(content) > 5000 else content  # Limit output
        except Exception as e:
            logger.error(f"Extract failed: {e}")
            return f"Error extracting content: {str(e)}"
    
    @registry.action(
        description="Get the current page URL.",
        category=ToolCategory.BROWSER,
        requires_context=["browser_session"]
    )
    async def browser_get_url(browser_session=None) -> str:
        """Get current URL"""
        if browser_session is None:
            return "Error: No browser session available"
        
        try:
            url = await browser_session.get_current_url()
            return url
        except Exception as e:
            logger.error(f"Get URL failed: {e}")
            return f"Error getting URL: {str(e)}"
    
    @registry.action(
        description="Scroll the page. Direction can be 'up', 'down', 'top', or 'bottom'.",
        category=ToolCategory.BROWSER,
        requires_context=["browser_session"]
    )
    async def browser_scroll(direction: str = "down", browser_session=None) -> str:
        """Scroll the page"""
        if browser_session is None:
            return "Error: No browser session available"
        
        try:
            await browser_session.scroll(direction)
            return f"Scrolled {direction}"
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return f"Error scrolling: {str(e)}"
    
    @registry.action(
        description="Go back to the previous page in browser history.",
        category=ToolCategory.BROWSER,
        requires_context=["browser_session"]
    )
    async def browser_back(browser_session=None) -> str:
        """Go back"""
        if browser_session is None:
            return "Error: No browser session available"
        
        try:
            await browser_session.go_back()
            return "Navigated back"
        except Exception as e:
            logger.error(f"Back navigation failed: {e}")
            return f"Error going back: {str(e)}"
    
    @registry.action(
        description="Wait for a specified number of seconds.",
        category=ToolCategory.BROWSER
    )
    async def browser_wait(seconds: int = 1) -> str:
        """Wait for seconds"""
        import asyncio
        await asyncio.sleep(seconds)
        return f"Waited {seconds} seconds"
    
    @registry.action(
        description="Send keyboard keys to the browser. Supports special keys like 'Enter', 'Tab', 'Escape', 'ArrowDown', etc.",
        category=ToolCategory.BROWSER,
        requires_context=["browser_session"]
    )
    async def browser_send_keys(keys: str, browser_session=None) -> str:
        """Send keyboard keys"""
        if browser_session is None:
            return "Error: No browser session available"
        
        try:
            await browser_session.send_keys(keys)
            return f"Sent keys: {keys}"
        except Exception as e:
            logger.error(f"Send keys failed: {e}")
            return f"Error sending keys: {str(e)}"
    
    logger.info(f"Registered {len(registry.get_by_category(ToolCategory.BROWSER))} browser tools")
    return registry


