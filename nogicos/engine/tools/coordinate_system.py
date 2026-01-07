# -*- coding: utf-8 -*-
"""
Coordinate System - 坐标系统转换

坐标系统关系图:
┌─────────────────────────────────────────┐
│ Screen Coordinates (0,0 = 左上角)        │
│  ┌───────────────────────────────┐      │
│  │ Window (GetWindowRect)         │      │
│  │  ┌─────────────────────────┐  │      │
│  │  │ Client Area             │  │      │
│  │  │ (GetClientRect)         │  │      │
│  │  │                         │  │      │
│  │  │ ← PostMessage 需要的坐标 │  │      │
│  │  └─────────────────────────┘  │      │
│  │  ↑ 标题栏、边框             │      │
│  └───────────────────────────────┘      │
└─────────────────────────────────────────┘

关键区分:
- GetWindowRect: 包含边框和标题栏的完整窗口矩形
- GetClientRect: 客户区 (可绘制区域) 矩形
- ClientToScreen: 客户区坐标 → 屏幕坐标
- PostMessage: 需要客户区坐标
"""

import ctypes
from ctypes import wintypes
import logging
from dataclasses import dataclass
from typing import Tuple

logger = logging.getLogger("nogicos.tools.coordinate_system")


@dataclass
class WindowCoordinates:
    """窗口坐标信息"""
    # 窗口矩形 (屏幕坐标，包含边框)
    window_rect: Tuple[int, int, int, int]  # (left, top, right, bottom)
    # 客户区矩形 (相对于窗口，不包含边框)
    client_rect: Tuple[int, int, int, int]  # (0, 0, width, height)
    # 客户区在屏幕上的位置
    client_origin: Tuple[int, int]  # (x, y)
    # DPI 缩放因子
    dpi_scale: float
    
    @property
    def client_width(self) -> int:
        return self.client_rect[2] - self.client_rect[0]
    
    @property
    def client_height(self) -> int:
        return self.client_rect[3] - self.client_rect[1]
    
    @property
    def window_width(self) -> int:
        return self.window_rect[2] - self.window_rect[0]
    
    @property
    def window_height(self) -> int:
        return self.window_rect[3] - self.window_rect[1]


class CoordinateTransformer:
    """坐标转换器 - 处理所有坐标系统转换"""
    
    # 截图目标尺寸 (Anthropic 参考)
    TARGET_WIDTH = 1280
    TARGET_HEIGHT = 800
    
    def __init__(self, target_size: Tuple[int, int] = None):
        self.target_size = target_size or (self.TARGET_WIDTH, self.TARGET_HEIGHT)
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self._setup_functions()
    
    def _setup_functions(self):
        """设置 Windows API 函数签名"""
        # GetWindowRect
        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetWindowRect.restype = wintypes.BOOL
        
        # GetClientRect
        self.user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetClientRect.restype = wintypes.BOOL
        
        # ClientToScreen
        self.user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        self.user32.ClientToScreen.restype = wintypes.BOOL
        
        # GetDpiForWindow (Windows 10 1607+)
        try:
            self.user32.GetDpiForWindow.argtypes = [wintypes.HWND]
            self.user32.GetDpiForWindow.restype = wintypes.UINT
            self._has_per_window_dpi = True
        except AttributeError:
            self._has_per_window_dpi = False
    
    def get_window_coordinates(self, hwnd: int) -> WindowCoordinates:
        """获取窗口的完整坐标信息"""
        # 1. 获取窗口矩形 (屏幕坐标)
        window_rect = wintypes.RECT()
        self.user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
        
        # 2. 获取客户区矩形 (相对坐标)
        client_rect = wintypes.RECT()
        self.user32.GetClientRect(hwnd, ctypes.byref(client_rect))
        
        # 3. 获取客户区原点在屏幕上的位置
        point = wintypes.POINT(0, 0)
        self.user32.ClientToScreen(hwnd, ctypes.byref(point))
        
        # 4. 获取 DPI 缩放
        dpi_scale = self._get_dpi_scale(hwnd)
        
        return WindowCoordinates(
            window_rect=(window_rect.left, window_rect.top, window_rect.right, window_rect.bottom),
            client_rect=(client_rect.left, client_rect.top, client_rect.right, client_rect.bottom),
            client_origin=(point.x, point.y),
            dpi_scale=dpi_scale
        )
    
    def screenshot_to_client(self, x: int, y: int, hwnd: int) -> Tuple[int, int]:
        """
        将截图坐标转换为客户区坐标
        
        截图是 1280x800，需要转换到实际客户区尺寸
        
        Args:
            x, y: 截图上的坐标 (相对于 1280x800)
            hwnd: 目标窗口句柄
            
        Returns:
            客户区坐标 (x, y)
        """
        coords = self.get_window_coordinates(hwnd)
        
        # 计算缩放因子
        scale_x = coords.client_width / self.target_size[0]
        scale_y = coords.client_height / self.target_size[1]
        
        # 应用缩放 (不需要再乘 DPI，因为截图已经是实际像素)
        client_x = int(x * scale_x)
        client_y = int(y * scale_y)
        
        logger.debug(
            f"screenshot_to_client: ({x}, {y}) -> ({client_x}, {client_y}) "
            f"[scale: {scale_x:.2f}x{scale_y:.2f}, client: {coords.client_width}x{coords.client_height}]"
        )
        
        return client_x, client_y
    
    def client_to_screenshot(self, x: int, y: int, hwnd: int) -> Tuple[int, int]:
        """
        将客户区坐标转换为截图坐标
        
        Args:
            x, y: 客户区坐标
            hwnd: 目标窗口句柄
            
        Returns:
            截图坐标 (x, y) (相对于 1280x800)
        """
        coords = self.get_window_coordinates(hwnd)
        
        # 计算缩放因子
        scale_x = self.target_size[0] / coords.client_width
        scale_y = self.target_size[1] / coords.client_height
        
        screenshot_x = int(x * scale_x)
        screenshot_y = int(y * scale_y)
        
        return screenshot_x, screenshot_y
    
    def client_to_screen(self, x: int, y: int, hwnd: int) -> Tuple[int, int]:
        """将客户区坐标转换为屏幕坐标"""
        point = wintypes.POINT(x, y)
        self.user32.ClientToScreen(hwnd, ctypes.byref(point))
        return point.x, point.y
    
    def get_postmessage_lparam(self, hwnd: int, client_x: int, client_y: int) -> int:
        """
        获取 PostMessage 需要的 lParam
        
        验证坐标在客户区内，并打包为 lParam
        """
        coords = self.get_window_coordinates(hwnd)
        
        # 验证坐标在客户区内
        if not (0 <= client_x < coords.client_width and 0 <= client_y < coords.client_height):
            logger.warning(
                f"Coordinates ({client_x}, {client_y}) outside client area "
                f"(0,0)-({coords.client_width},{coords.client_height})"
            )
        
        # 打包为 lParam: x in low word, y in high word
        lparam = (client_y << 16) | (client_x & 0xFFFF)
        return lparam
    
    def _get_dpi_scale(self, hwnd: int) -> float:
        """获取窗口 DPI 缩放比例"""
        if self._has_per_window_dpi:
            try:
                dpi = self.user32.GetDpiForWindow(hwnd)
                if dpi > 0:
                    return dpi / 96.0
            except Exception:
                pass
        
        # Fallback: 获取显示器 DPI
        try:
            shcore = ctypes.WinDLL('shcore', use_last_error=True)
            MDT_EFFECTIVE_DPI = 0
            monitor = self.user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
            dpi_x = ctypes.c_uint()
            dpi_y = ctypes.c_uint()
            shcore.GetDpiForMonitor(
                monitor, MDT_EFFECTIVE_DPI, 
                ctypes.byref(dpi_x), ctypes.byref(dpi_y)
            )
            if dpi_x.value > 0:
                return dpi_x.value / 96.0
        except Exception:
            pass
        
        return 1.0  # 默认 100%


def scale_coordinates(source: str, x: int, y: int, hwnd: int) -> Tuple[int, int]:
    """
    坐标缩放 - 便捷函数
    
    Args:
        source: "api" (从截图坐标转窗口) 或 "window" (从窗口坐标转截图)
        x, y: 输入坐标
        hwnd: 目标窗口句柄
    
    Returns:
        转换后的坐标
    """
    transformer = CoordinateTransformer()
    
    if source == "api":
        # 从截图坐标 (1280x800) 转换为客户区坐标
        return transformer.screenshot_to_client(x, y, hwnd)
    else:
        # 从客户区坐标转换为截图坐标
        return transformer.client_to_screenshot(x, y, hwnd)


# 全局单例
_global_transformer: CoordinateTransformer = None


def get_transformer() -> CoordinateTransformer:
    """获取全局坐标转换器"""
    global _global_transformer
    if _global_transformer is None:
        _global_transformer = CoordinateTransformer()
    return _global_transformer


# 导出
__all__ = [
    'WindowCoordinates',
    'CoordinateTransformer',
    'scale_coordinates',
    'get_transformer',
]
