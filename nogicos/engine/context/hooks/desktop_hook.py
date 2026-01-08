# -*- coding: utf-8 -*-
"""
Desktop Hook - 桌面窗口感知

感知当前活跃窗口和窗口列表
提供通用的窗口发现能力（用于 App Connector）
"""

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .base_hook import BaseHook, HookConfig
from ..store import HookType, DesktopContext

logger = logging.getLogger(__name__)

# Windows API
if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes
        WINDOWS_AVAILABLE = True
    except ImportError:
        WINDOWS_AVAILABLE = False
else:
    WINDOWS_AVAILABLE = False


@dataclass
class WindowInfo:
    """窗口信息（用于窗口选择器）"""
    hwnd: int                          # 窗口句柄
    title: str                         # 窗口标题
    app_name: str                      # 应用程序名称（如 chrome.exe）
    app_display_name: str = ""         # 显示名称（如 Google Chrome）
    icon_path: str = ""                # 图标路径（暂未实现）
    is_browser: bool = False           # 是否是浏览器
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "app_name": self.app_name,
            "app_display_name": self.app_display_name or self.app_name,
            "icon_path": self.icon_path,
            "is_browser": self.is_browser,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


# 浏览器进程名映射
BROWSER_PROCESSES = {
    "chrome.exe": "Google Chrome",
    "firefox.exe": "Mozilla Firefox",
    "msedge.exe": "Microsoft Edge",
    "brave.exe": "Brave",
    "opera.exe": "Opera",
    "arc.exe": "Arc",
}

# 常见应用进程名映射
APP_DISPLAY_NAMES = {
    **BROWSER_PROCESSES,
    "code.exe": "VS Code",
    "cursor.exe": "Cursor",
    "figma.exe": "Figma",
    "slack.exe": "Slack",
    "discord.exe": "Discord",
    "notion.exe": "Notion",
    "obsidian.exe": "Obsidian",
    "spotify.exe": "Spotify",
    "explorer.exe": "File Explorer",
    "wps.exe": "WPS Office",
    "excel.exe": "Excel",
    "word.exe": "Word",
    "powerpnt.exe": "PowerPoint",
}


class DesktopHook(BaseHook):
    """
    桌面 Hook
    
    支持两种模式：
    1. 无目标：感知当前活跃窗口（焦点窗口）
    2. 有目标 HWND：锁定监控特定窗口
    """
    
    def __init__(
        self,
        hook_id: str = "desktop",
        config: Optional[HookConfig] = None,
    ):
        super().__init__(hook_id, HookType.DESKTOP, config)
        
        self._last_context: Optional[DesktopContext] = None
        self._target_hwnd: Optional[int] = None  # 目标窗口 HWND（如果指定则锁定）
    
    async def _connect(self, target: Optional[str] = None) -> bool:
        """
        连接到目标窗口
        
        Args:
            target: 目标窗口的 HWND（字符串形式），None 则监控当前活动窗口
        """
        if target:
            try:
                self._target_hwnd = int(target)
                logger.info(f"[DesktopHook] Locked to window HWND: {self._target_hwnd}")
            except ValueError:
                logger.error(f"[DesktopHook] Invalid HWND: {target}")
                return False
        else:
            self._target_hwnd = None
            logger.info("[DesktopHook] Monitoring active (foreground) window")
        return True
    
    async def _disconnect(self) -> bool:
        """断开连接"""
        self._last_context = None
        self._target_hwnd = None
        return True
    
    async def capture(self) -> Optional[DesktopContext]:
        """
        捕获桌面上下文
        
        Returns:
            DesktopContext 或 None
        """
        try:
            if sys.platform == "win32" and WINDOWS_AVAILABLE:
                return await self._capture_windows()
            else:
                logger.warning(f"[DesktopHook] Platform {sys.platform} not fully supported")
                return None
                
        except Exception as e:
            logger.error(f"[DesktopHook] Capture failed: {e}")
            return self._last_context
    
    async def _capture_windows(self) -> Optional[DesktopContext]:
        """Windows 平台捕获"""
        try:
            user32 = ctypes.windll.user32
            
            # 决定监控哪个窗口
            if self._target_hwnd:
                # 锁定模式：使用指定的 HWND
                hwnd = self._target_hwnd
                # 验证窗口是否还存在
                if not user32.IsWindow(hwnd):
                    logger.warning(f"[DesktopHook] Target window {hwnd} no longer exists")
                    hwnd = 0
            else:
                # 活动窗口模式：获取前台窗口
                hwnd = user32.GetForegroundWindow()

            # Early return if no valid hwnd
            if hwnd == 0:
                return self._last_context

            active_app = ""
            active_window = ""

            if hwnd:
                # 获取窗口标题
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    active_window = buffer.value
                
                # 获取进程名
                active_app = self._get_process_name_windows(hwnd)
            
            # 获取窗口列表（仅在非锁定模式下获取，锁定模式下不需要）
            window_list = [] if self._target_hwnd else await self._get_window_list_windows()
            
            context = DesktopContext(
                hwnd=hwnd,  # 添加 hwnd 到上下文
                active_app=active_app,
                active_window=active_window,
                window_list=window_list,
                last_updated=datetime.now().isoformat(),
            )
            
            self._last_context = context
            return context
            
        except Exception as e:
            logger.error(f"[DesktopHook] Windows capture failed: {e}")
            return self._last_context
    
    def _get_process_name_windows(self, hwnd: int) -> str:
        """获取窗口的进程名"""
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            
            # 获取进程 ID
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            
            # 打开进程
            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_VM_READ = 0x0010
            
            process = kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                False,
                pid.value
            )
            
            if process:
                try:
                    # 获取进程名
                    buffer = ctypes.create_unicode_buffer(260)
                    psapi.GetModuleBaseNameW(process, None, buffer, 260)
                    return buffer.value
                finally:
                    kernel32.CloseHandle(process)
            
            return ""
            
        except Exception as e:
            logger.debug(f"[DesktopHook] Get process name failed: {e}")
            return ""
    
    async def _get_window_list_windows(self) -> List[Dict[str, str]]:
        """获取可见窗口列表"""
        try:
            user32 = ctypes.windll.user32
            windows = []
            
            def enum_callback(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buffer, length + 1)
                        title = buffer.value
                        
                        # 过滤系统窗口
                        if title and not self._is_system_window(title):
                            app = self._get_process_name_windows(hwnd)
                            windows.append({
                                "app": app,
                                "title": title,
                            })
                return True
            
            # 【修复 #18 + Segfault 修复】
            # 关键：必须保持回调实例的引用，否则会被 GC 导致 Segfault
            if not hasattr(DesktopHook, '_WNDENUMPROC'):
                DesktopHook._WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            callback_instance = DesktopHook._WNDENUMPROC(enum_callback)
            user32.EnumWindows(callback_instance, 0)

            return windows[:20]  # 最多返回 20 个窗口
            
        except Exception as e:
            logger.error(f"[DesktopHook] Get window list failed: {e}")
            return []
    
    def _is_system_window(self, title: str) -> bool:
        """判断是否是系统窗口（应该忽略）"""
        system_titles = [
            "Program Manager",
            "Windows Input Experience",
            "Microsoft Text Input Application",
            "Settings",
            "Calculator",
        ]
        
        # 完全匹配
        if title in system_titles:
            return True
        
        # 空标题或很短的标题
        if len(title) < 2:
            return True
        
        return False


# ============================================================================
# 独立函数：获取所有窗口（供 API 直接调用）
# ============================================================================

def get_all_windows() -> List[WindowInfo]:
    """
    获取所有可见窗口的详细信息

    供 /api/windows 端点调用，用于窗口选择器 UI

    Returns:
        List[WindowInfo]: 窗口信息列表，按最近活跃排序
    """
    if not WINDOWS_AVAILABLE:
        logger.warning("[DesktopHook] Windows API not available")
        return []
    
    try:
        user32 = ctypes.windll.user32
        windows: List[WindowInfo] = []
        
        def enum_callback(hwnd, _):
            # 只处理可见窗口
            if not user32.IsWindowVisible(hwnd):
                return True
            
            # 获取窗口标题
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
            
            # 获取进程名（先获取，用于过滤）
            app_name = _get_process_name_static(hwnd)
            if not app_name:
                return True
            
            # 过滤系统窗口和自己的应用
            if _is_system_window_static(title, app_name):
                return True
            
            # 获取窗口位置
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            
            # 过滤太小的窗口（可能是隐藏窗口）
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width < 100 or height < 100:
                return True
            
            # 判断是否是浏览器
            app_lower = app_name.lower()
            is_browser = app_lower in BROWSER_PROCESSES
            
            # 获取显示名称
            app_display_name = APP_DISPLAY_NAMES.get(app_lower, app_name.replace(".exe", "").title())
            
            windows.append(WindowInfo(
                hwnd=hwnd,
                title=title,
                app_name=app_name,
                app_display_name=app_display_name,
                is_browser=is_browser,
                x=rect.left,
                y=rect.top,
                width=width,
                height=height,
            ))
            
            return True
        
        # 【修复 #18 + Segfault 修复】
        # 关键：必须保持回调实例的引用，否则会被 GC 导致 Segfault
        global _WNDENUMPROC_CACHED
        if '_WNDENUMPROC_CACHED' not in globals():
            _WNDENUMPROC_CACHED = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        callback_instance = _WNDENUMPROC_CACHED(enum_callback)
        user32.EnumWindows(callback_instance, 0)
        
        # 获取当前前台窗口，放到列表最前面
        foreground_hwnd = user32.GetForegroundWindow()
        windows.sort(key=lambda w: (w.hwnd != foreground_hwnd, w.app_display_name))
        
        logger.debug(f"[DesktopHook] Found {len(windows)} windows")

        return windows[:30]  # 最多返回 30 个窗口

    except Exception as e:
        logger.error(f"[DesktopHook] get_all_windows failed: {e}")
        return []


def _is_system_window_static(title: str, app_name: str = "") -> bool:
    """判断是否是系统窗口或自己的应用"""
    system_titles = [
        "Program Manager",
        "Windows Input Experience",
        "Microsoft Text Input Application",
        "Settings",
        "Calculator",
        "NVIDIA GeForce Overlay",
        "AMD Software",
    ]

    # 过滤自己的进程（NogicOS 的 Electron 进程）
    self_processes = [
        "nogicos.exe",
    ]
    
    # 精确匹配 NogicOS 窗口标题（不要用模糊匹配，否则会过滤掉打开 nogicos 项目的 Cursor）
    nogicos_exact_titles = [
        "NogicOS",
    ]

    if title in system_titles:
        return True
    
    # 精确匹配 NogicOS 窗口（只过滤主窗口，不过滤包含 nogicos 关键字的其他应用）
    if title in nogicos_exact_titles:
        return True

    # 检查是否是自己的进程
    if app_name and app_name.lower() in self_processes:
        return True

    if len(title) < 2:
        return True

    return False


def _get_process_name_static(hwnd: int) -> str:
    """获取窗口的进程名"""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        
        process = kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
            False,
            pid.value
        )
        
        if process:
            try:
                buffer = ctypes.create_unicode_buffer(260)
                psapi.GetModuleBaseNameW(process, None, buffer, 260)
                return buffer.value
            finally:
                kernel32.CloseHandle(process)
        
        return ""
        
    except Exception:
        return ""

