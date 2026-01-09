# -*- coding: utf-8 -*-
"""
Screenshot Utilities - 截图工具

提供窗口截图和屏幕截图功能
"""

# 【修复】确保用户安装的包可以被找到
import sys
import os
_user_site = os.path.expanduser("~\\AppData\\Roaming\\Python\\Python314\\site-packages")
if _user_site not in sys.path:
    sys.path.insert(0, _user_site)

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class WindowRect:
    """窗口矩形"""
    left: int
    top: int
    right: int
    bottom: int
    
    @property
    def width(self) -> int:
        return self.right - self.left
    
    @property
    def height(self) -> int:
        return self.bottom - self.top
    
    @property
    def x(self) -> int:
        return self.left
    
    @property
    def y(self) -> int:
        return self.top


async def capture_screen(region: Optional[Tuple[int, int, int, int]] = None) -> Optional[bytes]:
    """
    截取屏幕
    
    Args:
        region: 可选的区域 (x, y, width, height)，None 表示全屏
    
    Returns:
        PNG 格式的截图数据
    """
    try:
        import mss
        from PIL import Image
        from io import BytesIO
        
        with mss.mss() as sct:
            if region:
                monitor = {
                    "left": region[0],
                    "top": region[1],
                    "width": region[2],
                    "height": region[3],
                }
            else:
                monitor = sct.monitors[1]  # 主显示器
            
            screenshot = sct.grab(monitor)
            
            # 转换为 PNG
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()
            
    except ImportError:
        logger.error("[Screenshot] mss not installed. Run: pip install mss")
        return None
    except Exception as e:
        logger.error(f"[Screenshot] Capture failed: {e}")
        return None


async def capture_window(hwnd: int) -> Optional[bytes]:
    """
    截取指定窗口
    
    Args:
        hwnd: 窗口句柄
    
    Returns:
        PNG 格式的截图数据
    """
    if sys.platform != "win32":
        logger.warning("[Screenshot] Window capture only supported on Windows")
        return None
    
    try:
        import ctypes
        from ctypes import wintypes
        
        user32 = ctypes.windll.user32
        
        # 获取窗口位置
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        
        # 截取区域
        return await capture_screen((
            rect.left,
            rect.top,
            rect.right - rect.left,
            rect.bottom - rect.top,
        ))
        
    except Exception as e:
        logger.error(f"[Screenshot] Window capture failed: {e}")
        return None


async def get_window_rect(hwnd: int) -> Optional[WindowRect]:
    """
    获取窗口位置和大小
    
    Args:
        hwnd: 窗口句柄
    
    Returns:
        WindowRect 或 None
    """
    if sys.platform != "win32":
        return None
    
    try:
        import ctypes
        from ctypes import wintypes
        
        user32 = ctypes.windll.user32
        
        rect = wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return WindowRect(
                left=rect.left,
                top=rect.top,
                right=rect.right,
                bottom=rect.bottom,
            )
        return None
        
    except Exception as e:
        logger.error(f"[Screenshot] Get window rect failed: {e}")
        return None


async def capture_browser_address_bar(hwnd: int) -> Optional[bytes]:
    """
    截取浏览器地址栏区域
    
    浏览器地址栏通常在窗口顶部 50-100 像素
    
    Args:
        hwnd: 浏览器窗口句柄
    
    Returns:
        地址栏区域的截图
    """
    rect = await get_window_rect(hwnd)
    if not rect:
        return None
    
    # 地址栏区域估计：顶部 30-90 像素
    address_bar_region = (
        rect.left + 80,  # 跳过浏览器按钮
        rect.top + 30,   # 跳过标题栏
        rect.width - 200,  # 减去右侧按钮
        60,              # 地址栏高度
    )
    
    return await capture_screen(address_bar_region)


class ScreenshotManager:
    """
    截图管理器
    
    提供高级截图功能
    """
    
    def __init__(self):
        self._cache: dict = {}
    
    async def capture_with_cache(
        self,
        key: str,
        capture_fn,
        cache_seconds: float = 1.0,
    ) -> Optional[bytes]:
        """
        带缓存的截图
        
        避免频繁截图
        """
        import time
        
        now = time.time()
        
        # 检查缓存
        if key in self._cache:
            cached_time, cached_data = self._cache[key]
            if now - cached_time < cache_seconds:
                return cached_data
        
        # 执行截图
        data = await capture_fn()
        
        if data:
            self._cache[key] = (now, data)
        
        return data
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()


# 全局单例
_screenshot_manager: Optional[ScreenshotManager] = None


def get_screenshot_manager() -> ScreenshotManager:
    """获取 ScreenshotManager 单例"""
    global _screenshot_manager
    if _screenshot_manager is None:
        _screenshot_manager = ScreenshotManager()
    return _screenshot_manager

