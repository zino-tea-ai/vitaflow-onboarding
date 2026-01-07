# -*- coding: utf-8 -*-
"""
NogicOS Tools - V2 Unified Tool System

This module provides:
- ToolRegistry: Central registry for all tools
- Browser Tools: Web automation capabilities (via Electron IPC)
- Local Tools: File system and shell operations
- Window Tools: PostMessage-based window automation (Phase 4)
- System Tools: Task control and system utilities (Phase 4)
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

# Window tools (Phase 4) - Windows only, PostMessage-based
try:
    from .window_tools import register_window_tools, WindowTools, WindowLostError
    WINDOW_TOOLS_AVAILABLE = True
except ImportError:
    WINDOW_TOOLS_AVAILABLE = False
    register_window_tools = None
    WindowTools = None
    WindowLostError = None

# System tools (Phase 4) - Task control and system utilities
try:
    from .system_tools import register_system_tools, SystemTools, TaskStatus
    SYSTEM_TOOLS_AVAILABLE = True
except ImportError:
    SYSTEM_TOOLS_AVAILABLE = False
    register_system_tools = None
    SystemTools = None
    TaskStatus = None

# Windows compatibility modules (Phase 4.5)
try:
    from .windows_compat import WindowInputController, InputResult, InputMethod
    from .hwnd_manager import HwndManager, get_hwnd_manager
    from .coordinate_system import CoordinateTransformer, scale_coordinates
    from .dpi_handler import DPIHandler, get_dpi_handler
    from .uipi_checker import UIPIChecker, can_control_window
    from .window_state import WindowStateChecker, is_window_operable
    from .multi_monitor import MultiMonitorManager, get_monitor_manager
    from .win11_compat import Windows11Compatibility, is_windows_11
    WINDOWS_COMPAT_AVAILABLE = True
except ImportError:
    WINDOWS_COMPAT_AVAILABLE = False


def create_full_registry() -> ToolRegistry:
    """
    Create a fully populated tool registry with all tools.
    
    Returns:
        ToolRegistry with browser, local, desktop, window, system, and vision tools registered.
    """
    registry = ToolRegistry()
    
    # Core tools (always available)
    register_browser_tools(registry)    # CDP 浏览器
    register_local_tools(registry)      # 文件系统
    register_cursor_tools(registry)     # Cursor IDE
    
    # Desktop tools (Phase C) - pyautogui based
    if DESKTOP_TOOLS_AVAILABLE and register_desktop_tools:
        register_desktop_tools(registry)
    
    # Vision tools (Phase C4) - Claude Vision
    if VISION_TOOLS_AVAILABLE and register_vision_tools:
        register_vision_tools(registry)
    
    # Window tools (Phase 4) - PostMessage based, window isolation
    if WINDOW_TOOLS_AVAILABLE and register_window_tools:
        register_window_tools(registry)
    
    # System tools (Phase 4) - Task control
    if SYSTEM_TOOLS_AVAILABLE and register_system_tools:
        register_system_tools(registry)
    
    return registry


__all__ = [
    # Core
    'ToolRegistry',
    'ToolCategory',
    'ToolDefinition',
    'ToolResult',
    'get_registry',
    'reset_registry',
    
    # Tool registration
    'register_browser_tools',
    'register_local_tools',
    'register_cursor_tools',
    'register_window_tools',
    'register_system_tools',
    'create_full_registry',
    
    # Phase 4 tools
    'WindowTools',
    'WindowLostError',
    'SystemTools',
    'TaskStatus',
    
    # Windows compatibility (Phase 4.5)
    'WindowInputController',
    'HwndManager',
    'CoordinateTransformer',
    'DPIHandler',
    'UIPIChecker',
    'WindowStateChecker',
    'MultiMonitorManager',
    'Windows11Compatibility',
    
    # Convenience functions
    'scale_coordinates',
    'can_control_window',
    'is_window_operable',
    'is_windows_11',
    'get_hwnd_manager',
    'get_dpi_handler',
    'get_monitor_manager',
    
    # Availability flags
    'DESKTOP_TOOLS_AVAILABLE',
    'VISION_TOOLS_AVAILABLE',
    'WINDOW_TOOLS_AVAILABLE',
    'SYSTEM_TOOLS_AVAILABLE',
    'WINDOWS_COMPAT_AVAILABLE',
]
