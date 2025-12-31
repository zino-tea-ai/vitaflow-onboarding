# -*- coding: utf-8 -*-
"""
NogicOS Tools - V2 Unified Tool System

This module provides:
- ToolRegistry: Central registry for all tools
- Browser Tools: Web automation capabilities (via Electron IPC)
- Local Tools: File system and shell operations
"""

from .base import (
    ToolRegistry,
    ToolCategory,
    ToolDefinition,
    ToolResult,
    get_registry,
    reset_registry,
)
from .browser import register_browser_tools
from .local import register_local_tools
from .cursor_tools import register_cursor_tools

# Desktop tools (Phase C) - optional, requires pyautogui
try:
    from .desktop import register_desktop_tools
    DESKTOP_TOOLS_AVAILABLE = True
except ImportError:
    DESKTOP_TOOLS_AVAILABLE = False
    register_desktop_tools = None

# Vision tools (Phase C4) - optional, requires anthropic
try:
    from .vision import register_vision_tools
    VISION_TOOLS_AVAILABLE = True
except ImportError:
    VISION_TOOLS_AVAILABLE = False
    register_vision_tools = None


def create_full_registry() -> ToolRegistry:
    """
    Create a fully populated tool registry with all tools.
    
    Returns:
        ToolRegistry with browser, local, desktop, and vision tools registered.
    """
    registry = ToolRegistry()
    register_browser_tools(registry)
    register_local_tools(registry)
    register_cursor_tools(registry)
    
    # Register desktop tools if available (Phase C)
    if DESKTOP_TOOLS_AVAILABLE and register_desktop_tools:
        register_desktop_tools(registry)
    
    # Register vision tools if available (Phase C4)
    if VISION_TOOLS_AVAILABLE and register_vision_tools:
        register_vision_tools(registry)
    
    return registry


__all__ = [
    'ToolRegistry',
    'ToolCategory',
    'ToolDefinition',
    'ToolResult',
    'get_registry',
    'reset_registry',
    'register_browser_tools',
    'register_local_tools',
    'register_cursor_tools',
    'create_full_registry',
]
