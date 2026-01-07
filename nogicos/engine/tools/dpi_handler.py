# -*- coding: utf-8 -*-
"""
DPI Handler - DPI 缩放处理器

DPI 设置与截图尺寸的关系:
+------------+------------+----------------+-----------+
| DPI 设置   | 截图尺寸   | 实际窗口尺寸   | 坐标偏差  |
+------------+------------+----------------+-----------+
| 100%       | 1280x800   | 1280x800       | 0%        |
| 125%       | 1280x800   | 1600x1000      | 25%       |
| 150%       | 1280x800   | 1920x1200      | 50%       |
+------------+------------+----------------+-----------+

如果不处理 DPI，点击坐标会有 25%-50% 的偏差!
"""

import ctypes
from ctypes import wintypes
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger("nogicos.tools.dpi_handler")


@dataclass
class MonitorDPIInfo:
    """显示器 DPI 信息"""
    monitor_handle: int
    dpi_x: int
    dpi_y: int
    scale_factor: float  # dpi / 96
    monitor_rect: Tuple[int, int, int, int]
    work_rect: Tuple[int, int, int, int]
    is_primary: bool


class DPIHandler:
    """DPI 缩放处理器"""
    
    # 标准 DPI (100%)
    STANDARD_DPI = 96
    
    def __init__(self):
        self._dpi_cache: Dict[int, float] = {}  # hwnd -> scale_factor
        self._setup_api()
    
    def _setup_api(self):
        """设置 Windows API"""
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        
        # 检查可用的 DPI API
        self._api_level = self._detect_api_level()
        logger.debug(f"DPI API level: {self._api_level}")
        
        if self._api_level >= 3:
            # Windows 10 1607+ GetDpiForWindow
            self.user32.GetDpiForWindow.argtypes = [wintypes.HWND]
            self.user32.GetDpiForWindow.restype = wintypes.UINT
        
        # MonitorFromWindow
        self.user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        self.user32.MonitorFromWindow.restype = wintypes.HMONITOR
        
        # GetMonitorInfoW
        self.user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
        self.user32.GetMonitorInfoW.restype = wintypes.BOOL
    
    def _detect_api_level(self) -> int:
        """
        检测可用的 DPI API 级别
        
        Returns:
            3: Windows 10 1607+ (GetDpiForWindow)
            2: Windows 8.1+ (GetDpiForMonitor)
            1: Windows Vista+ (GetDeviceCaps)
        """
        try:
            # 尝试 GetDpiForWindow
            self.user32.GetDpiForWindow
            return 3
        except AttributeError:
            pass
        
        try:
            # 尝试 GetDpiForMonitor
            shcore = ctypes.WinDLL('shcore')
            shcore.GetDpiForMonitor
            return 2
        except:
            pass
        
        return 1
    
    def get_window_dpi(self, hwnd: int) -> float:
        """
        获取窗口 DPI 缩放比例
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            DPI 缩放比例 (1.0 = 100%, 1.25 = 125%, etc.)
        """
        if hwnd in self._dpi_cache:
            return self._dpi_cache[hwnd]
        
        dpi_scale = self._query_dpi(hwnd)
        self._dpi_cache[hwnd] = dpi_scale
        
        logger.debug(f"Window {hwnd} DPI scale: {dpi_scale:.2f} ({int(dpi_scale * 100)}%)")
        return dpi_scale
    
    def _query_dpi(self, hwnd: int) -> float:
        """查询 DPI"""
        # 方法 1: Windows 10 1607+ GetDpiForWindow
        if self._api_level >= 3:
            try:
                dpi = self.user32.GetDpiForWindow(hwnd)
                if dpi > 0:
                    return dpi / self.STANDARD_DPI
            except Exception as e:
                logger.debug(f"GetDpiForWindow failed: {e}")
        
        # 方法 2: GetDpiForMonitor
        if self._api_level >= 2:
            try:
                shcore = ctypes.WinDLL('shcore')
                MDT_EFFECTIVE_DPI = 0
                monitor = self.user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
                dpi_x = ctypes.c_uint()
                dpi_y = ctypes.c_uint()
                shcore.GetDpiForMonitor(
                    monitor, MDT_EFFECTIVE_DPI,
                    ctypes.byref(dpi_x), ctypes.byref(dpi_y)
                )
                if dpi_x.value > 0:
                    return dpi_x.value / self.STANDARD_DPI
            except Exception as e:
                logger.debug(f"GetDpiForMonitor failed: {e}")
        
        # 方法 3: GetDeviceCaps (最后手段)
        try:
            hdc = self.user32.GetDC(hwnd)
            if hdc:
                gdi32 = ctypes.WinDLL('gdi32')
                LOGPIXELSX = 88
                dpi = gdi32.GetDeviceCaps(hdc, LOGPIXELSX)
                self.user32.ReleaseDC(hwnd, hdc)
                if dpi > 0:
                    return dpi / self.STANDARD_DPI
        except Exception as e:
            logger.debug(f"GetDeviceCaps failed: {e}")
        
        return 1.0  # 默认 100%
    
    def invalidate_cache(self, hwnd: Optional[int] = None) -> None:
        """清除 DPI 缓存"""
        if hwnd:
            self._dpi_cache.pop(hwnd, None)
        else:
            self._dpi_cache.clear()
    
    def get_monitor_info(self, hwnd: int) -> Optional[MonitorDPIInfo]:
        """获取窗口所在显示器 DPI 信息"""
        try:
            monitor = self.user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
            
            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)
                ]
            
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            
            if not self.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return None
            
            # 获取 DPI
            dpi_x, dpi_y = self.STANDARD_DPI, self.STANDARD_DPI
            if self._api_level >= 2:
                try:
                    shcore = ctypes.WinDLL('shcore')
                    dx, dy = ctypes.c_uint(), ctypes.c_uint()
                    shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dx), ctypes.byref(dy))
                    dpi_x, dpi_y = dx.value, dy.value
                except:
                    pass
            
            return MonitorDPIInfo(
                monitor_handle=monitor,
                dpi_x=dpi_x,
                dpi_y=dpi_y,
                scale_factor=dpi_x / self.STANDARD_DPI,
                monitor_rect=(
                    info.rcMonitor.left, info.rcMonitor.top,
                    info.rcMonitor.right, info.rcMonitor.bottom
                ),
                work_rect=(
                    info.rcWork.left, info.rcWork.top,
                    info.rcWork.right, info.rcWork.bottom
                ),
                is_primary=bool(info.dwFlags & 1),
            )
            
        except Exception as e:
            logger.error(f"Failed to get monitor info: {e}")
            return None
    
    def scale_for_dpi(self, x: int, y: int, hwnd: int) -> Tuple[int, int]:
        """
        根据 DPI 缩放坐标
        
        用于将逻辑坐标转换为物理像素坐标
        """
        scale = self.get_window_dpi(hwnd)
        return int(x * scale), int(y * scale)
    
    def unscale_for_dpi(self, x: int, y: int, hwnd: int) -> Tuple[int, int]:
        """
        反向 DPI 缩放
        
        用于将物理像素坐标转换为逻辑坐标
        """
        scale = self.get_window_dpi(hwnd)
        if scale == 0:
            return x, y
        return int(x / scale), int(y / scale)


# 全局单例
_global_dpi_handler: Optional[DPIHandler] = None


def get_dpi_handler() -> DPIHandler:
    """获取全局 DPI 处理器"""
    global _global_dpi_handler
    if _global_dpi_handler is None:
        _global_dpi_handler = DPIHandler()
    return _global_dpi_handler


# 导出
__all__ = [
    'MonitorDPIInfo',
    'DPIHandler',
    'get_dpi_handler',
]
