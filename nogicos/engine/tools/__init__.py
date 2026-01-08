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

# UFO tools (Microsoft UFO) - AI-powered desktop automation
try:
    from .ufo_executor import register_ufo_tools, UFOExecutor, execute_desktop_task
    UFO_TOOLS_AVAILABLE = True
except ImportError:
    UFO_TOOLS_AVAILABLE = False
    register_ufo_tools = None
    UFOExecutor = None
    execute_desktop_task = None

# Browser Executor (Browser Use) - AI vision-powered browser automation
try:
    from .browser_executor import (
        register_browser_executor_tools, 
        NogicBrowserExecutor, 
        get_browser_executor
    )
    BROWSER_EXECUTOR_AVAILABLE = True
except ImportError:
    BROWSER_EXECUTOR_AVAILABLE = False
    register_browser_executor_tools = None
    NogicBrowserExecutor = None
    get_browser_executor = None

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
    
    工具精简策略（2026-01-09）：
    - 移除低级桌面工具（desktop_tools, window_tools），让 UFO 处理所有桌面自动化
    - UFO 是 AI 驱动的桌面自动化，能自动理解 UI 并执行完整任务（如发送消息）
    - 这样减少工具数量，避免 Agent 选择低级工具导致任务不完整
    """
    registry = ToolRegistry()
    
    # Core tools (always available)
    register_browser_tools(registry)    # CDP 浏览器
    register_local_tools(registry)      # 文件系统
    register_cursor_tools(registry)     # Cursor IDE
    
    # [已移除] Desktop tools (Phase C) - pyautogui based
    # 原因: UFO 提供更完整的桌面自动化，低级工具容易导致任务不完整
    # if DESKTOP_TOOLS_AVAILABLE and register_desktop_tools:
    #     register_desktop_tools(registry)
    
    # [已移除] Vision tools (Phase C4) - Claude Vision
    # 原因: desktop_analyze_screen, desktop_find_element, desktop_click_element 和 UFO 重叠
    # 但不能完整执行任务（如发送消息），让 UFO 统一处理
    # if VISION_TOOLS_AVAILABLE and register_vision_tools:
    #     register_vision_tools(registry)
    
    # [已移除] Window tools (Phase 4) - PostMessage based, window isolation
    # 原因: UFO 可以处理窗口操作，低级工具容易导致只输入不发送等问题
    # if WINDOW_TOOLS_AVAILABLE and register_window_tools:
    #     register_window_tools(registry)
    
    # System tools (Phase 4) - Task control (保留 list_windows 等系统信息工具)
    if SYSTEM_TOOLS_AVAILABLE and register_system_tools:
        register_system_tools(registry)
    
    # UFO tools - Microsoft UFO AI-powered desktop automation (主力桌面自动化)
    if UFO_TOOLS_AVAILABLE and register_ufo_tools:
        register_ufo_tools(registry)
    
    # Browser Executor - Browser Use AI vision-powered browser automation
    if BROWSER_EXECUTOR_AVAILABLE and register_browser_executor_tools:
        register_browser_executor_tools(registry)
    
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
    
    # UFO tools
    'register_ufo_tools',
    'UFOExecutor',
    'execute_desktop_task',
    
    # Browser Executor (Browser Use)
    'register_browser_executor_tools',
    'NogicBrowserExecutor',
    'get_browser_executor',
    
    # Availability flags
    'DESKTOP_TOOLS_AVAILABLE',
    'VISION_TOOLS_AVAILABLE',
    'WINDOW_TOOLS_AVAILABLE',
    'SYSTEM_TOOLS_AVAILABLE',
    'WINDOWS_COMPAT_AVAILABLE',
    'UFO_TOOLS_AVAILABLE',
    'BROWSER_EXECUTOR_AVAILABLE',
]
