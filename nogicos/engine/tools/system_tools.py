# -*- coding: utf-8 -*-
"""
System Tools - 任务控制工具

提供系统级别的任务控制功能:
- set_task_status: 设置任务状态 (参考 ByteBot)
- get_system_info: 获取系统信息
- list_windows: 列出所有窗口
- find_window: 查找窗口
"""

import asyncio
import ctypes
from ctypes import wintypes
import platform
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json as _json
from pathlib import Path as _Path
import time

logger = logging.getLogger("nogicos.tools.system_tools")

# #region agent log helper (debug mode)
_DEBUG_LOG_PATH = _Path(r"c:\Users\WIN\Desktop\Cursor Project\.cursor\debug.log")

def _sys_dbg_log(hypothesis_id: str, location: str, message: str, data: dict):
    try:
        payload = {
            "sessionId": "debug-session",
            "runId": "pre-fix-1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion


@dataclass
class TaskStatus:
    """任务状态"""
    status: str  # "completed" | "needs_help" | "in_progress" | "failed"
    description: str
    progress: float = 0.0  # 0.0 - 1.0


class SystemTools:
    """系统工具"""
    
    def __init__(self):
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self._setup_functions()
        self._current_task_status: Optional[TaskStatus] = None
    
    def _setup_functions(self):
        """设置 Windows API 函数签名"""
        # EnumWindows
        self.WNDENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        self.user32.EnumWindows.argtypes = [self.WNDENUMPROC, wintypes.LPARAM]
        self.user32.EnumWindows.restype = wintypes.BOOL
        
        # GetWindowTextW
        self.user32.GetWindowTextW.argtypes = [
            wintypes.HWND, wintypes.LPWSTR, ctypes.c_int
        ]
        self.user32.GetWindowTextW.restype = ctypes.c_int
        
        # GetWindowTextLengthW
        self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.user32.GetWindowTextLengthW.restype = ctypes.c_int
        
        # IsWindowVisible
        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.IsWindowVisible.restype = wintypes.BOOL
        
        # GetClassName
        self.user32.GetClassNameW.argtypes = [
            wintypes.HWND, wintypes.LPWSTR, ctypes.c_int
        ]
        self.user32.GetClassNameW.restype = ctypes.c_int
        
        # FindWindowW
        self.user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        self.user32.FindWindowW.restype = wintypes.HWND
    
    def set_task_status(
        self, 
        status: str, 
        description: str,
        progress: float = 0.0
    ) -> TaskStatus:
        """
        设置任务状态 - 参考 ByteBot
        
        Args:
            status: "completed" | "needs_help" | "in_progress" | "failed"
            description: 状态描述
            progress: 进度 (0.0 - 1.0)
            
        Returns:
            TaskStatus 对象
        """
        valid_statuses = ["completed", "needs_help", "in_progress", "failed"]
        if status not in valid_statuses:
            status = "in_progress"
        
        self._current_task_status = TaskStatus(
            status=status,
            description=description,
            progress=min(max(progress, 0.0), 1.0)
        )
        
        logger.info(f"Task status: {status} - {description} ({progress*100:.0f}%)")
        return self._current_task_status
    
    def get_task_status(self) -> Optional[TaskStatus]:
        """获取当前任务状态"""
        return self._current_task_status
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        info = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }
        
        # Windows 特定信息
        if platform.system() == "Windows":
            info["windows_edition"] = platform.win32_edition() if hasattr(platform, 'win32_edition') else "N/A"
            
            # 屏幕信息
            info["screen_width"] = self.user32.GetSystemMetrics(0)  # SM_CXSCREEN
            info["screen_height"] = self.user32.GetSystemMetrics(1)  # SM_CYSCREEN
            info["virtual_screen_width"] = self.user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            info["virtual_screen_height"] = self.user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            info["monitor_count"] = self.user32.GetSystemMetrics(80)  # SM_CMONITORS
        
        return info
    
    def list_windows(self, visible_only: bool = True) -> List[Dict[str, Any]]:
        """
        列出所有窗口
        
        Args:
            visible_only: 是否只列出可见窗口
            
        Returns:
            窗口列表
        """
        windows = []
        
        def enum_callback(hwnd, lparam):
            # 检查可见性
            if visible_only and not self.user32.IsWindowVisible(hwnd):
                return True
            
            # 获取标题
            length = self.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True  # 跳过无标题窗口
            
            buffer = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
            
            # 获取类名
            class_buffer = ctypes.create_unicode_buffer(256)
            self.user32.GetClassNameW(hwnd, class_buffer, 256)
            class_name = class_buffer.value
            
            windows.append({
                "hwnd": hwnd,
                "title": title,
                "class_name": class_name,
            })
            
            return True
        
        try:
            # 【Segfault 修复】必须保持回调实例的引用，否则会被 GC 导致崩溃
            callback_instance = self.WNDENUMPROC(enum_callback)
            self.user32.EnumWindows(callback_instance, 0)
        except Exception as e:
            logger.error(f"EnumWindows failed: {e}")
        
        # Debug log: record top few windows
        try:
            top = windows[:5]
            _sys_dbg_log(
                hypothesis_id="H4",
                location="system_tools:list_windows",
                message="Enumerated windows",
                data={
                    "count": len(windows),
                    "top": [{"hwnd": w.get("hwnd"), "title": w.get("title"), "class": w.get("class_name")} for w in top],
                },
            )
        except Exception:
            pass

        return windows
    
    def find_window(
        self, 
        title: Optional[str] = None, 
        class_name: Optional[str] = None,
        partial_match: bool = True
    ) -> List[Dict[str, Any]]:
        """
        查找窗口
        
        Args:
            title: 窗口标题 (支持部分匹配)
            class_name: 窗口类名 (支持部分匹配)
            partial_match: 是否部分匹配
            
        Returns:
            匹配的窗口列表
        """
        # 精确匹配
        if not partial_match and title:
            hwnd = self.user32.FindWindowW(
                class_name if class_name else None,
                title
            )
            if hwnd:
                return [{"hwnd": hwnd, "title": title, "class_name": class_name or ""}]
            return []
        
        # 部分匹配
        all_windows = self.list_windows(visible_only=True)
        results = []
        
        for win in all_windows:
            match = True
            
            if title:
                if partial_match:
                    match = match and title.lower() in win["title"].lower()
                else:
                    match = match and win["title"] == title
            
            if class_name:
                if partial_match:
                    match = match and class_name.lower() in win["class_name"].lower()
                else:
                    match = match and win["class_name"] == class_name
            
            if match:
                results.append(win)
        
        return results
    
    async def wait_for_window(
        self, 
        title: str, 
        timeout: float = 30.0,
        interval: float = 0.5
    ) -> Optional[int]:
        """
        等待窗口出现
        
        Args:
            title: 窗口标题 (部分匹配)
            timeout: 超时时间 (秒)
            interval: 检查间隔 (秒)
            
        Returns:
            窗口句柄，或 None (超时)
        """
        import time
        start = time.time()
        
        while time.time() - start < timeout:
            windows = self.find_window(title=title, partial_match=True)
            if windows:
                return windows[0]["hwnd"]
            await asyncio.sleep(interval)
        
        return None


# 全局单例
_global_system_tools: Optional[SystemTools] = None


def get_system_tools() -> SystemTools:
    """获取全局系统工具"""
    global _global_system_tools
    if _global_system_tools is None:
        _global_system_tools = SystemTools()
    return _global_system_tools


def register_system_tools(registry):
    """注册系统工具到 Registry"""
    from .base import ToolCategory
    
    system_tools = get_system_tools()
    
    @registry.action(
        description="""设置任务状态 - 用于报告任务进度。

参数:
- status: 状态值
  - "completed": 任务完成
  - "needs_help": 需要用户帮助
  - "in_progress": 进行中
  - "failed": 任务失败
- description: 状态描述

示例:
- set_task_status("completed", "成功打开了浏览器并导航到目标网页")
- set_task_status("needs_help", "无法找到登录按钮，请确认页面是否正确")""",
        category=ToolCategory.SYSTEM,
    )
    async def set_task_status(status: str, description: str) -> str:
        result = system_tools.set_task_status(status, description)
        return f"Status set to {result.status}: {result.description}"
    
    @registry.action(
        description="""获取系统信息。

返回: 操作系统、屏幕分辨率、显示器数量等信息""",
        category=ToolCategory.SYSTEM,
    )
    async def get_system_info() -> str:
        import json
        info = system_tools.get_system_info()
        return json.dumps(info, indent=2, ensure_ascii=False)
    
    @registry.action(
        description="""列出所有可见窗口。

返回: 窗口列表，包含 hwnd、标题、类名""",
        category=ToolCategory.SYSTEM,
    )
    async def list_windows() -> str:
        import json
        windows = system_tools.list_windows(visible_only=True)
        # 只返回前 20 个
        if len(windows) > 20:
            windows = windows[:20]
            windows.append({"note": f"... and {len(windows) - 20} more"})
        return json.dumps(windows, indent=2, ensure_ascii=False)
    
    @registry.action(
        description="""查找窗口。

参数:
- title: 窗口标题 (支持部分匹配)
- class_name: 窗口类名 (可选)

返回: 匹配的窗口列表""",
        category=ToolCategory.SYSTEM,
    )
    async def find_window(
        title: str, 
        class_name: Optional[str] = None
    ) -> str:
        import json
        windows = system_tools.find_window(
            title=title, 
            class_name=class_name,
            partial_match=True
        )
        return json.dumps(windows, indent=2, ensure_ascii=False)
    
    @registry.action(
        description="""等待窗口出现。

参数:
- title: 窗口标题 (部分匹配)
- timeout: 超时时间 (秒，默认 30)

返回: 窗口句柄，或超时错误""",
        category=ToolCategory.SYSTEM,
    )
    async def wait_for_window(
        title: str, 
        timeout: float = 30.0
    ) -> str:
        hwnd = await system_tools.wait_for_window(title, timeout)
        if hwnd:
            return f"Found window: hwnd={hwnd}"
        else:
            return f"Timeout: Window '{title}' not found after {timeout}s"
    
    @registry.action(
        description="""Request user confirmation before performing sensitive actions.

IMPORTANT: You MUST call this tool before:
- Filling forms (especially application forms, login forms)
- Sending messages (WhatsApp, email, chat)
- Submitting data
- Making purchases or payments
- Any action that cannot be easily undone

Args:
    action_description: What you're about to do (e.g., "Fill YC application form")
    content_preview: The content you're about to submit (e.g., the answer text)

Returns:
    "confirmed" if user approves, "cancelled" if user declines

Example:
    result = request_confirmation(
        action_description="Fill YC application form",
        content_preview="We're building NogicOS, a desktop AI assistant..."
    )
    if result == "confirmed":
        # proceed with filling
    else:
        # abort and inform user""",
        category=ToolCategory.SYSTEM,
    )
    async def request_confirmation(
        action_description: str,
        content_preview: str
    ) -> str:
        """Request user confirmation via UI dialog."""
        import uuid
        
        # Get the status server from registry context (set by hive_server)
        status_server = registry.get_context("status_server")
        
        if not status_server:
            logger.warning("[Confirmation] No status server available, auto-confirming")
            return "confirmed"
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        
        # Send confirmation request to frontend
        logger.info(f"[Confirmation] Requesting user confirmation: {action_description}")
        
        try:
            # Use the status server's confirmation mechanism
            confirmed = await status_server.stream_confirm(
                request_id=request_id,
                action=action_description,
                content=content_preview,
                timeout=120  # 2 minutes to respond
            )
            
            if confirmed:
                logger.info(f"[Confirmation] User confirmed: {action_description}")
                return "confirmed"
            else:
                logger.info(f"[Confirmation] User cancelled: {action_description}")
                return "cancelled"
                
        except asyncio.TimeoutError:
            logger.warning(f"[Confirmation] Timeout waiting for user response")
            return "cancelled"
        except Exception as e:
            logger.error(f"[Confirmation] Error: {e}")
            return "cancelled"
    
    logger.info("[SystemTools] All system tools registered")


# 导出
__all__ = [
    'TaskStatus',
    'SystemTools',
    'get_system_tools',
    'register_system_tools',
]
