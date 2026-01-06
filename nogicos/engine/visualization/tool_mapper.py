# -*- coding: utf-8 -*-
"""
Tool Visualization Mapper - Maps tool executions to visual events

This module provides a universal way to visualize AI tool executions.
Each tool type is mapped to appropriate cursor movements, highlights, and effects.

Architecture:
    Tool Execution → Tool Mapper → viz_* methods → WebSocket → Frontend
"""

import random
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("nogicos.visualization")


# =============================================================================
# Tool Category Definitions
# =============================================================================

class ToolVizCategory:
    """Visual categories for tools"""
    FILE_READ = "file_read"       # Reading files/directories
    FILE_WRITE = "file_write"     # Writing/creating files
    FILE_MOVE = "file_move"       # Moving/copying files
    FILE_DELETE = "file_delete"   # Deleting files
    BROWSER_NAV = "browser_nav"   # Browser navigation
    BROWSER_CLICK = "browser_click"  # Browser clicks
    BROWSER_TYPE = "browser_type"    # Browser typing
    DESKTOP_CLICK = "desktop_click"  # Desktop clicks
    DESKTOP_TYPE = "desktop_type"    # Desktop typing
    DESKTOP_WINDOW = "desktop_window"  # Window operations
    SHELL = "shell"              # Shell commands
    SEARCH = "search"            # Search operations
    WAIT = "wait"                # Wait/pause operations


# =============================================================================
# Tool to Category Mapping
# =============================================================================

TOOL_CATEGORY_MAP: Dict[str, str] = {
    # Local Tools - File Read
    "read_file": ToolVizCategory.FILE_READ,
    "list_directory": ToolVizCategory.FILE_READ,
    "glob_search": ToolVizCategory.SEARCH,
    "grep_search": ToolVizCategory.SEARCH,
    "get_cwd": ToolVizCategory.FILE_READ,
    "path_exists": ToolVizCategory.FILE_READ,
    
    # Local Tools - File Write
    "write_file": ToolVizCategory.FILE_WRITE,
    "append_file": ToolVizCategory.FILE_WRITE,
    "create_directory": ToolVizCategory.FILE_WRITE,
    
    # Local Tools - File Move
    "move_file": ToolVizCategory.FILE_MOVE,
    "copy_file": ToolVizCategory.FILE_MOVE,
    
    # Local Tools - File Delete
    "delete_file": ToolVizCategory.FILE_DELETE,
    
    # Local Tools - Shell
    "shell_execute": ToolVizCategory.SHELL,
    
    # Browser Tools
    "browser_navigate": ToolVizCategory.BROWSER_NAV,
    "browser_click": ToolVizCategory.BROWSER_CLICK,
    "browser_type": ToolVizCategory.BROWSER_TYPE,
    "browser_screenshot": ToolVizCategory.FILE_READ,
    "browser_extract": ToolVizCategory.FILE_READ,
    "browser_get_url": ToolVizCategory.FILE_READ,
    "browser_scroll": ToolVizCategory.BROWSER_CLICK,
    "browser_back": ToolVizCategory.BROWSER_NAV,
    "browser_wait": ToolVizCategory.WAIT,
    "browser_send_keys": ToolVizCategory.BROWSER_TYPE,
    
    # Desktop Tools
    "desktop_click": ToolVizCategory.DESKTOP_CLICK,
    "desktop_type": ToolVizCategory.DESKTOP_TYPE,
    "desktop_hotkey": ToolVizCategory.DESKTOP_TYPE,
    "desktop_screenshot": ToolVizCategory.FILE_READ,
    "desktop_get_position": ToolVizCategory.FILE_READ,
    "desktop_get_screen_size": ToolVizCategory.FILE_READ,
    "desktop_move_to": ToolVizCategory.DESKTOP_CLICK,
    "desktop_scroll": ToolVizCategory.DESKTOP_CLICK,
    "desktop_list_windows": ToolVizCategory.DESKTOP_WINDOW,
    "desktop_focus_window": ToolVizCategory.DESKTOP_WINDOW,
    "desktop_get_active_window": ToolVizCategory.DESKTOP_WINDOW,
    "desktop_locate_image": ToolVizCategory.SEARCH,
    "desktop_wait_for_image": ToolVizCategory.SEARCH,
    "desktop_click_image": ToolVizCategory.DESKTOP_CLICK,
}


# =============================================================================
# Simulated Screen Layout (for visualization panel)
# =============================================================================

# The visualization panel simulates a 360x400 screen
SCREEN_WIDTH = 360
SCREEN_HEIGHT = 400

# Regions in the simulated screen (for positioning cursor and highlights)
SCREEN_REGIONS = {
    "file_explorer": {"x": 20, "y": 50, "w": 100, "h": 300},     # Left side
    "main_content": {"x": 130, "y": 50, "w": 200, "h": 250},     # Center
    "url_bar": {"x": 60, "y": 20, "w": 280, "h": 25},            # Top
    "buttons": {"x": 130, "y": 320, "w": 200, "h": 50},          # Bottom
    "search_box": {"x": 130, "y": 160, "w": 150, "h": 35},       # Center search
}


def _get_region_for_category(category: str) -> Dict[str, int]:
    """Get the screen region for a tool category"""
    region_map = {
        ToolVizCategory.FILE_READ: "file_explorer",
        ToolVizCategory.FILE_WRITE: "file_explorer",
        ToolVizCategory.FILE_MOVE: "file_explorer",
        ToolVizCategory.FILE_DELETE: "file_explorer",
        ToolVizCategory.BROWSER_NAV: "url_bar",
        ToolVizCategory.BROWSER_CLICK: "main_content",
        ToolVizCategory.BROWSER_TYPE: "search_box",
        ToolVizCategory.DESKTOP_CLICK: "main_content",
        ToolVizCategory.DESKTOP_TYPE: "search_box",
        ToolVizCategory.DESKTOP_WINDOW: "main_content",
        ToolVizCategory.SHELL: "main_content",
        ToolVizCategory.SEARCH: "search_box",
        ToolVizCategory.WAIT: "main_content",
    }
    region_name = region_map.get(category, "main_content")
    return SCREEN_REGIONS.get(region_name, SCREEN_REGIONS["main_content"])


def _random_point_in_region(region: Dict[str, int], seed: int = None) -> Tuple[int, int]:
    """Get a random point within a region

    Args:
        region: Region dict with x, y, w, h
        seed: Optional seed for reproducible results in tests
    """
    if seed is not None:
        random.seed(seed)
    x = region["x"] + random.randint(10, max(10, region["w"] - 10))
    y = region["y"] + random.randint(10, max(10, region["h"] - 10))
    return x, y


def _get_label_for_tool(tool_name: str, args: Dict[str, Any]) -> str:
    """Generate a human-readable label for the tool action"""
    labels = {
        "read_file": lambda a: f"读取 {_short_path(a.get('path', ''))}",
        "write_file": lambda a: f"写入 {_short_path(a.get('path', ''))}",
        "list_directory": lambda a: f"浏览 {_short_path(a.get('path', '.'))}",
        "move_file": lambda a: f"移动到 {_short_path(a.get('destination', ''))}",
        "copy_file": lambda a: f"复制到 {_short_path(a.get('destination', ''))}",
        "delete_file": lambda a: f"删除 {_short_path(a.get('path', ''))}",
        "create_directory": lambda a: f"创建 {_short_path(a.get('path', ''))}",
        "glob_search": lambda a: f"搜索 {a.get('pattern', '*')}",
        "grep_search": lambda a: f"查找 {a.get('pattern', '')}",
        "shell_execute": lambda a: f"执行 {_short_cmd(a.get('command', ''))}",
        "browser_navigate": lambda a: f"打开 {_short_url(a.get('url', ''))}",
        "browser_click": lambda a: f"点击 {a.get('selector', '')}",
        "browser_type": lambda a: f"输入 {_short_text(a.get('text', ''))}",
        "desktop_click": lambda a: f"点击 ({a.get('x', 0)}, {a.get('y', 0)})",
        "desktop_type": lambda a: f"输入 {_short_text(a.get('text', ''))}",
        "desktop_focus_window": lambda a: f"聚焦 {a.get('title', '')}",
    }
    
    label_fn = labels.get(tool_name)
    if label_fn:
        try:
            return label_fn(args)
        except:
            pass
    return tool_name.replace("_", " ").title()


def _short_path(path: str, max_len: int = 20) -> str:
    """Shorten a path for display"""
    if not path:
        return "..."
    if len(path) <= max_len:
        return path
    # Get filename or last part
    parts = path.replace("\\", "/").split("/")
    return "..." + parts[-1][:max_len-3] if parts else path[:max_len-3] + "..."


def _short_url(url: str, max_len: int = 25) -> str:
    """Shorten a URL for display"""
    if not url:
        return "..."
    # Remove protocol
    url = url.replace("https://", "").replace("http://", "")
    if len(url) <= max_len:
        return url
    return url[:max_len-3] + "..."


def _short_text(text: str, max_len: int = 15) -> str:
    """Shorten text for display"""
    if not text:
        return "..."
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + "..."


def _short_cmd(cmd: str, max_len: int = 20) -> str:
    """Shorten command for display"""
    if not cmd:
        return "..."
    # Get first word
    first_word = cmd.split()[0] if cmd.split() else cmd
    if len(first_word) <= max_len:
        return first_word
    return first_word[:max_len-3] + "..."


# =============================================================================
# Visualization Functions
# =============================================================================

async def visualize_task_start(server, max_steps: int = 10, url: str = None):
    """
    Send visualization events when a task starts.
    
    Args:
        server: StatusServer instance
        max_steps: Maximum number of steps in the task
        url: Optional URL to display in simulated browser
    """
    if server is None:
        return
    
    try:
        await server.viz_task_start(max_steps=max_steps, url=url)
        await server.viz_screen_glow("low")
        logger.debug(f"[Viz] Task started, max_steps={max_steps}")
    except Exception as e:
        logger.warning(f"[Viz] Failed to send task_start: {e}")


async def visualize_task_complete(server):
    """
    Send visualization events when a task completes successfully.
    
    Args:
        server: StatusServer instance
    """
    if server is None:
        return
    
    try:
        await server.viz_task_complete()
        logger.debug("[Viz] Task completed")
    except Exception as e:
        logger.warning(f"[Viz] Failed to send task_complete: {e}")


async def visualize_task_error(server):
    """
    Send visualization events when a task fails.
    
    Args:
        server: StatusServer instance
    """
    if server is None:
        return
    
    try:
        await server.viz_task_error()
        logger.debug("[Viz] Task error")
    except Exception as e:
        logger.warning(f"[Viz] Failed to send task_error: {e}")


async def visualize_tool_start(server, tool_name: str, args: Dict[str, Any], step: int = 0):
    """
    Send visualization events when a tool starts executing.
    
    Args:
        server: StatusServer instance
        tool_name: Name of the tool being executed
        args: Tool arguments
        step: Current step number (0-indexed)
    """
    if server is None:
        return
    
    try:
        # Get tool category
        category = TOOL_CATEGORY_MAP.get(tool_name, ToolVizCategory.FILE_READ)
        
        # Get target region for this tool type
        region = _get_region_for_category(category)
        
        # Get a point in the region
        target_x, target_y = _random_point_in_region(region)
        
        # Get label for highlight
        label = _get_label_for_tool(tool_name, args)
        
        # Send step start
        await server.viz_step_start(step)
        
        # Move cursor to target
        await server.viz_cursor_move(target_x, target_y, duration=0.5)
        
        # Show highlight at target region
        await server.viz_highlight(
            region["x"], region["y"],
            region["w"], region["h"],
            label=label
        )
        
        # Set appropriate glow based on category
        glow_map = {
            ToolVizCategory.FILE_WRITE: "medium",
            ToolVizCategory.FILE_DELETE: "high",
            ToolVizCategory.FILE_MOVE: "medium",
            ToolVizCategory.BROWSER_CLICK: "medium",
            ToolVizCategory.DESKTOP_CLICK: "medium",
            ToolVizCategory.SHELL: "high",
        }
        glow = glow_map.get(category, "low")
        await server.viz_screen_glow(glow)
        
        # Trigger action-specific animations
        if category in [ToolVizCategory.BROWSER_CLICK, ToolVizCategory.DESKTOP_CLICK]:
            await server.viz_cursor_click()
        elif category in [ToolVizCategory.BROWSER_TYPE, ToolVizCategory.DESKTOP_TYPE]:
            await server.viz_cursor_type()
        
        logger.debug(f"[Viz] Tool start: {tool_name} -> category={category}, pos=({target_x}, {target_y})")
        
    except Exception as e:
        logger.warning(f"[Viz] Failed to visualize tool start: {e}")


async def visualize_tool_end(server, tool_name: str, success: bool, step: int = 0):
    """
    Send visualization events when a tool finishes executing.
    
    Args:
        server: StatusServer instance
        tool_name: Name of the tool that finished
        success: Whether the tool execution was successful
        step: Current step number (0-indexed)
    """
    if server is None:
        return
    
    try:
        # Get tool category
        category = TOOL_CATEGORY_MAP.get(tool_name, ToolVizCategory.FILE_READ)
        
        # Stop typing animation if it was a type tool
        if category in [ToolVizCategory.BROWSER_TYPE, ToolVizCategory.DESKTOP_TYPE]:
            await server.viz_cursor_stop_type()
        
        # Hide highlight
        await server.viz_highlight_hide()
        
        # Send step complete
        await server.viz_step_complete(step, success=success)
        
        # Set glow based on success
        if success:
            await server.viz_screen_glow("low")
        else:
            await server.viz_screen_glow("error")
        
        logger.debug(f"[Viz] Tool end: {tool_name} -> success={success}")
        
    except Exception as e:
        logger.warning(f"[Viz] Failed to visualize tool end: {e}")













