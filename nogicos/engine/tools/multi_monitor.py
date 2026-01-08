# -*- coding: utf-8 -*-
"""
Multi Monitor Manager - 多显示器支持

功能:
- 获取所有显示器信息
- 检测窗口所在显示器
- 检测窗口是否跨越多个显示器
- 多显示器 DPI 差异处理
"""

import ctypes
from ctypes import wintypes
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger("nogicos.tools.multi_monitor")


@dataclass
class MonitorInfo:
    """显示器信息"""
    handle: int
    rect: Tuple[int, int, int, int]  # 显示器矩形 (left, top, right, bottom)
    work_rect: Tuple[int, int, int, int]  # 工作区域 (排除任务栏)
    is_primary: bool
    dpi_scale: float
    name: str
    
    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]
    
    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]
    
    @property
    def work_width(self) -> int:
        return self.work_rect[2] - self.work_rect[0]
    
    @property
    def work_height(self) -> int:
        return self.work_rect[3] - self.work_rect[1]


class MultiMonitorManager:
    """多显示器管理器"""
    
    def __init__(self):
        self._monitors: List[MonitorInfo] = []
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self._setup_functions()
        self._refresh_monitors()
    
    def _setup_functions(self):
        """设置 Windows API 函数签名"""
        # EnumDisplayMonitors
        self.MONITORENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
            ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
        )
        self.user32.EnumDisplayMonitors.argtypes = [
            wintypes.HDC, ctypes.POINTER(wintypes.RECT),
            self.MONITORENUMPROC, wintypes.LPARAM
        ]
        self.user32.EnumDisplayMonitors.restype = wintypes.BOOL
        
        # MonitorFromWindow
        self.user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        self.user32.MonitorFromWindow.restype = wintypes.HMONITOR
        
        # GetWindowRect
        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetWindowRect.restype = wintypes.BOOL
    
    def _refresh_monitors(self):
        """刷新显示器列表"""
        self._monitors.clear()
        
        def callback(monitor, hdc, rect, data):
            info = self._get_monitor_info(monitor)
            if info:
                self._monitors.append(info)
            return True
        
        try:
            # 【Segfault 修复】必须保持回调实例的引用，否则会被 GC 导致崩溃
            callback_instance = self.MONITORENUMPROC(callback)
            self.user32.EnumDisplayMonitors(
                None, None, callback_instance, 0
            )
        except Exception as e:
            logger.error(f"Failed to enumerate monitors: {e}")
        
        logger.info(f"Found {len(self._monitors)} monitor(s)")
    
    def _get_monitor_info(self, monitor_handle) -> Optional[MonitorInfo]:
        """获取显示器详细信息"""
        try:
            class MONITORINFOEXW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32)
                ]
            
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            
            if not self.user32.GetMonitorInfoW(monitor_handle, ctypes.byref(info)):
                return None
            
            # 获取 DPI
            dpi_scale = self._get_monitor_dpi_scale(monitor_handle)
            
            return MonitorInfo(
                handle=monitor_handle,
                rect=(
                    info.rcMonitor.left, info.rcMonitor.top,
                    info.rcMonitor.right, info.rcMonitor.bottom
                ),
                work_rect=(
                    info.rcWork.left, info.rcWork.top,
                    info.rcWork.right, info.rcWork.bottom
                ),
                is_primary=bool(info.dwFlags & 1),
                dpi_scale=dpi_scale,
                name=info.szDevice
            )
            
        except Exception as e:
            logger.error(f"Failed to get monitor info: {e}")
            return None
    
    def _get_monitor_dpi_scale(self, monitor_handle) -> float:
        """获取显示器 DPI 缩放"""
        try:
            shcore = ctypes.WinDLL('shcore')
            MDT_EFFECTIVE_DPI = 0
            dpi_x = ctypes.c_uint()
            dpi_y = ctypes.c_uint()
            result = shcore.GetDpiForMonitor(
                monitor_handle, MDT_EFFECTIVE_DPI,
                ctypes.byref(dpi_x), ctypes.byref(dpi_y)
            )
            if result == 0 and dpi_x.value > 0:
                return dpi_x.value / 96.0
        except Exception:
            pass
        
        return 1.0
    
    def get_window_monitor(self, hwnd: int) -> Optional[MonitorInfo]:
        """获取窗口所在的显示器"""
        MONITOR_DEFAULTTONEAREST = 2
        monitor = self.user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        
        for m in self._monitors:
            if m.handle == monitor:
                return m
        
        # 如果缓存中没有，尝试获取
        return self._get_monitor_info(monitor)
    
    def get_all_monitors(self) -> List[MonitorInfo]:
        """获取所有显示器"""
        return self._monitors.copy()
    
    def get_primary_monitor(self) -> Optional[MonitorInfo]:
        """获取主显示器"""
        for m in self._monitors:
            if m.is_primary:
                return m
        return self._monitors[0] if self._monitors else None
    
    def is_window_spanning_monitors(self, hwnd: int) -> bool:
        """检查窗口是否跨越多个显示器"""
        rect = wintypes.RECT()
        if not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        
        monitors_touched = 0
        for m in self._monitors:
            # 检查是否有交集
            if (rect.left < m.rect[2] and rect.right > m.rect[0] and
                rect.top < m.rect[3] and rect.bottom > m.rect[1]):
                monitors_touched += 1
        
        return monitors_touched > 1
    
    def get_virtual_screen_bounds(self) -> Tuple[int, int, int, int]:
        """获取虚拟屏幕边界 (所有显示器组成的矩形)"""
        if not self._monitors:
            return (0, 0, 1920, 1080)  # 默认值
        
        left = min(m.rect[0] for m in self._monitors)
        top = min(m.rect[1] for m in self._monitors)
        right = max(m.rect[2] for m in self._monitors)
        bottom = max(m.rect[3] for m in self._monitors)
        
        return (left, top, right, bottom)
    
    def point_to_monitor(self, x: int, y: int) -> Optional[MonitorInfo]:
        """获取坐标点所在的显示器"""
        for m in self._monitors:
            if (m.rect[0] <= x < m.rect[2] and 
                m.rect[1] <= y < m.rect[3]):
                return m
        return None
    
    def refresh(self):
        """刷新显示器信息"""
        self._refresh_monitors()
    
    @property
    def monitor_count(self) -> int:
        """显示器数量"""
        return len(self._monitors)


# 全局单例
_global_monitor_manager: Optional[MultiMonitorManager] = None


def get_monitor_manager() -> MultiMonitorManager:
    """获取全局多显示器管理器"""
    global _global_monitor_manager
    if _global_monitor_manager is None:
        _global_monitor_manager = MultiMonitorManager()
    return _global_monitor_manager


# 导出
__all__ = [
    'MonitorInfo',
    'MultiMonitorManager',
    'get_monitor_manager',
]
