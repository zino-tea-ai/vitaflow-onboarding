# -*- coding: utf-8 -*-
"""
Windows 11 Compatibility - Windows 11 特有问题处理

Windows 11 特性影响:
- 圆角窗口: GetWindowRect 返回的矩形包含圆角外的透明区域
- Snap Layouts: 窗口位置可能被系统自动调整
- Mica/Acrylic: 截图可能包含模糊效果
- 新的任务栏行为

使用 DwmGetWindowAttribute 获取实际可见区域
"""

import ctypes
from ctypes import wintypes
import logging
from typing import Tuple, Optional

logger = logging.getLogger("nogicos.tools.win11_compat")


class Windows11Compatibility:
    """Windows 11 特有问题处理"""
    
    # Windows 11 build 号起始值
    WIN11_BUILD_START = 22000
    
    # DWM 属性常量
    DWMWA_EXTENDED_FRAME_BOUNDS = 9
    DWMWA_WINDOW_CORNER_PREFERENCE = 33
    DWMWA_BORDER_COLOR = 34
    DWMWA_CAPTION_COLOR = 35
    DWMWA_TEXT_COLOR = 36
    DWMWA_VISIBLE_FRAME_BORDER_THICKNESS = 37
    DWMWA_SYSTEMBACKDROP_TYPE = 38
    
    # 圆角偏好
    DWMWCP_DEFAULT = 0       # 系统默认
    DWMWCP_DONOTROUND = 1    # 不使用圆角
    DWMWCP_ROUND = 2         # 圆角
    DWMWCP_ROUNDSMALL = 3    # 小圆角
    
    # 背景类型 (Mica, Acrylic)
    DWMSBT_AUTO = 0
    DWMSBT_NONE = 1
    DWMSBT_MAINWINDOW = 2    # Mica
    DWMSBT_TRANSIENTWINDOW = 3  # Acrylic
    DWMSBT_TABBEDWINDOW = 4  # Mica Alt
    
    def __init__(self):
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.dwmapi = ctypes.WinDLL('dwmapi', use_last_error=True)
        self.ntdll = ctypes.WinDLL('ntdll', use_last_error=True)
        self._is_win11: Optional[bool] = None
        self._build_number: Optional[int] = None
    
    def is_windows_11(self) -> bool:
        """检测是否是 Windows 11"""
        if self._is_win11 is not None:
            return self._is_win11
        
        self._is_win11 = self._get_build_number() >= self.WIN11_BUILD_START
        return self._is_win11
    
    def _get_build_number(self) -> int:
        """获取 Windows build 号"""
        if self._build_number is not None:
            return self._build_number
        
        try:
            # 使用 RtlGetVersion 获取真实版本
            class OSVERSIONINFOW(ctypes.Structure):
                _fields_ = [
                    ("dwOSVersionInfoSize", wintypes.DWORD),
                    ("dwMajorVersion", wintypes.DWORD),
                    ("dwMinorVersion", wintypes.DWORD),
                    ("dwBuildNumber", wintypes.DWORD),
                    ("dwPlatformId", wintypes.DWORD),
                    ("szCSDVersion", wintypes.WCHAR * 128)
                ]
            
            version_info = OSVERSIONINFOW()
            version_info.dwOSVersionInfoSize = ctypes.sizeof(OSVERSIONINFOW)
            
            self.ntdll.RtlGetVersion(ctypes.byref(version_info))
            self._build_number = version_info.dwBuildNumber
            
            logger.debug(
                f"Windows version: {version_info.dwMajorVersion}."
                f"{version_info.dwMinorVersion} Build {version_info.dwBuildNumber}"
            )
            
            return self._build_number
            
        except Exception as e:
            logger.warning(f"Failed to get Windows version: {e}")
            self._build_number = 0
            return 0
    
    def get_actual_window_rect(self, hwnd: int) -> Tuple[int, int, int, int]:
        """
        获取实际窗口矩形 (排除圆角透明区域)
        
        Windows 11 的圆角窗口导致 GetWindowRect 返回的矩形
        比实际可见区域大
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            (left, top, right, bottom) 实际可见区域
        """
        # 使用 DwmGetWindowAttribute 获取扩展帧边界
        try:
            rect = wintypes.RECT()
            result = self.dwmapi.DwmGetWindowAttribute(
                hwnd, self.DWMWA_EXTENDED_FRAME_BOUNDS,
                ctypes.byref(rect), ctypes.sizeof(rect)
            )
            if result == 0:  # S_OK
                return (rect.left, rect.top, rect.right, rect.bottom)
        except Exception as e:
            logger.debug(f"DwmGetWindowAttribute failed: {e}")
        
        # Fallback: 使用标准 GetWindowRect
        rect = wintypes.RECT()
        self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return (rect.left, rect.top, rect.right, rect.bottom)
    
    def set_window_corner_preference(self, hwnd: int, preference: str = "round") -> bool:
        """
        设置窗口圆角偏好
        
        Args:
            hwnd: 窗口句柄
            preference: "default", "round", "round_small", "square"
            
        Returns:
            是否设置成功
        """
        preferences = {
            "default": self.DWMWCP_DEFAULT,
            "square": self.DWMWCP_DONOTROUND,
            "round": self.DWMWCP_ROUND,
            "round_small": self.DWMWCP_ROUNDSMALL,
        }
        
        value = ctypes.c_int(preferences.get(preference, self.DWMWCP_ROUND))
        
        try:
            result = self.dwmapi.DwmSetWindowAttribute(
                hwnd, self.DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(value), ctypes.sizeof(value)
            )
            return result == 0
        except Exception as e:
            logger.debug(f"Failed to set corner preference: {e}")
            return False
    
    def set_window_backdrop(self, hwnd: int, backdrop: str = "mica") -> bool:
        """
        设置窗口背景效果 (Windows 11 only)
        
        Args:
            hwnd: 窗口句柄
            backdrop: "none", "mica", "acrylic", "tabbed"
            
        Returns:
            是否设置成功
        """
        if not self.is_windows_11():
            return False
        
        backdrops = {
            "auto": self.DWMSBT_AUTO,
            "none": self.DWMSBT_NONE,
            "mica": self.DWMSBT_MAINWINDOW,
            "acrylic": self.DWMSBT_TRANSIENTWINDOW,
            "tabbed": self.DWMSBT_TABBEDWINDOW,
        }
        
        value = ctypes.c_int(backdrops.get(backdrop, self.DWMSBT_AUTO))
        
        try:
            result = self.dwmapi.DwmSetWindowAttribute(
                hwnd, self.DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(value), ctypes.sizeof(value)
            )
            return result == 0
        except Exception as e:
            logger.debug(f"Failed to set backdrop: {e}")
            return False
    
    def get_visible_frame_thickness(self, hwnd: int) -> int:
        """
        获取可见帧边框厚度
        
        Returns:
            边框厚度 (像素)
        """
        try:
            thickness = ctypes.c_uint()
            result = self.dwmapi.DwmGetWindowAttribute(
                hwnd, self.DWMWA_VISIBLE_FRAME_BORDER_THICKNESS,
                ctypes.byref(thickness), ctypes.sizeof(thickness)
            )
            if result == 0:
                return thickness.value
        except Exception:
            pass
        
        return 0
    
    def adjust_coordinates_for_rounded_corners(
        self, x: int, y: int, hwnd: int
    ) -> Tuple[int, int]:
        """
        调整坐标以补偿圆角边框
        
        如果点击位置接近窗口角落，可能需要调整
        """
        if not self.is_windows_11():
            return x, y
        
        # 获取标准窗口矩形和实际可见区域
        standard_rect = wintypes.RECT()
        self.user32.GetWindowRect(hwnd, ctypes.byref(standard_rect))
        
        actual_rect = self.get_actual_window_rect(hwnd)
        
        # 计算偏移
        offset_left = actual_rect[0] - standard_rect.left
        offset_top = actual_rect[1] - standard_rect.top
        
        # 应用偏移
        adjusted_x = x + offset_left
        adjusted_y = y + offset_top
        
        return adjusted_x, adjusted_y
    
    def is_snap_layout_active(self, hwnd: int) -> bool:
        """
        检测窗口是否处于 Snap Layout 状态
        
        (简化实现 - 检查窗口是否占据屏幕特定比例)
        """
        if not self.is_windows_11():
            return False
        
        # 获取窗口和屏幕尺寸
        rect = self.get_actual_window_rect(hwnd)
        win_width = rect[2] - rect[0]
        win_height = rect[3] - rect[1]
        
        # 获取主显示器尺寸
        screen_width = self.user32.GetSystemMetrics(0)  # SM_CXSCREEN
        screen_height = self.user32.GetSystemMetrics(1)  # SM_CYSCREEN
        
        # 检查常见的 Snap 比例 (50%, 33%, 25%)
        snap_ratios = [0.5, 0.33, 0.25, 0.67, 0.75]
        
        for ratio in snap_ratios:
            if abs(win_width / screen_width - ratio) < 0.05:
                return True
            if abs(win_height / screen_height - ratio) < 0.05:
                return True
        
        return False


# 全局单例
_global_win11_compat: Optional[Windows11Compatibility] = None


def get_win11_compat() -> Windows11Compatibility:
    """获取全局 Windows 11 兼容性处理器"""
    global _global_win11_compat
    if _global_win11_compat is None:
        _global_win11_compat = Windows11Compatibility()
    return _global_win11_compat


# 便捷函数
def is_windows_11() -> bool:
    """检测是否是 Windows 11"""
    return get_win11_compat().is_windows_11()


def get_actual_window_rect(hwnd: int) -> Tuple[int, int, int, int]:
    """获取实际窗口矩形"""
    return get_win11_compat().get_actual_window_rect(hwnd)


# 导出
__all__ = [
    'Windows11Compatibility',
    'get_win11_compat',
    'is_windows_11',
    'get_actual_window_rect',
]
