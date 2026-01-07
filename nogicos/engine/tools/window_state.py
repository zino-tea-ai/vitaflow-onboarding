# -*- coding: utf-8 -*-
"""
Window State - 窗口状态全面检测

检测项目:
- exists: 窗口是否存在
- visible: 是否可见
- minimized: 是否最小化
- maximized: 是否最大化
- foreground: 是否前台窗口
- enabled: 是否启用
- hung: 是否无响应
- cloaked: 是否被隐藏 (UWP/Virtual Desktop)
- on_current_desktop: 是否在当前虚拟桌面
"""

import ctypes
from ctypes import wintypes
import logging
from dataclasses import dataclass
from typing import Tuple, Optional

logger = logging.getLogger("nogicos.tools.window_state")


@dataclass
class WindowState:
    """完整的窗口状态"""
    exists: bool           # 窗口是否存在
    visible: bool          # 是否可见
    minimized: bool        # 是否最小化
    maximized: bool        # 是否最大化
    foreground: bool       # 是否前台窗口
    enabled: bool          # 是否启用
    hung: bool             # 是否无响应
    cloaked: bool          # 是否被隐藏 (UWP/Virtual Desktop)
    on_current_desktop: bool  # 是否在当前虚拟桌面
    
    def is_operable(self) -> Tuple[bool, str]:
        """
        检查窗口是否可操作
        
        Returns:
            (可操作, 原因) 元组
        """
        if not self.exists:
            return False, "窗口已关闭"
        if self.minimized:
            return False, "窗口已最小化"
        if self.hung:
            return False, "应用程序无响应"
        if self.cloaked:
            return False, "窗口在其他虚拟桌面或被隐藏"
        if not self.on_current_desktop:
            return False, "窗口不在当前虚拟桌面"
        if not self.enabled:
            return False, "窗口已禁用"
        
        return True, "可以操作"


class WindowStateChecker:
    """全面的窗口状态检测"""
    
    def __init__(self):
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self._setup_functions()
        self._virtual_desktop_manager = None
    
    def _setup_functions(self):
        """设置 Windows API 函数签名"""
        # IsWindow
        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.restype = wintypes.BOOL
        
        # IsWindowVisible
        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.IsWindowVisible.restype = wintypes.BOOL
        
        # IsIconic (minimized)
        self.user32.IsIconic.argtypes = [wintypes.HWND]
        self.user32.IsIconic.restype = wintypes.BOOL
        
        # IsZoomed (maximized)
        self.user32.IsZoomed.argtypes = [wintypes.HWND]
        self.user32.IsZoomed.restype = wintypes.BOOL
        
        # GetForegroundWindow
        self.user32.GetForegroundWindow.argtypes = []
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        
        # IsWindowEnabled
        self.user32.IsWindowEnabled.argtypes = [wintypes.HWND]
        self.user32.IsWindowEnabled.restype = wintypes.BOOL
        
        # IsHungAppWindow
        self.user32.IsHungAppWindow.argtypes = [wintypes.HWND]
        self.user32.IsHungAppWindow.restype = wintypes.BOOL
    
    def get_window_state(self, hwnd: int) -> WindowState:
        """获取完整窗口状态"""
        return WindowState(
            exists=self._is_window(hwnd),
            visible=self._is_visible(hwnd),
            minimized=self._is_minimized(hwnd),
            maximized=self._is_maximized(hwnd),
            foreground=self._is_foreground(hwnd),
            enabled=self._is_enabled(hwnd),
            hung=self._is_hung(hwnd),
            cloaked=self._is_cloaked(hwnd),
            on_current_desktop=self._is_on_current_desktop(hwnd),
        )
    
    def is_operable(self, hwnd: int) -> Tuple[bool, str]:
        """检查窗口是否可操作"""
        state = self.get_window_state(hwnd)
        return state.is_operable()
    
    def _is_window(self, hwnd: int) -> bool:
        """检查窗口是否存在"""
        return bool(self.user32.IsWindow(hwnd))
    
    def _is_visible(self, hwnd: int) -> bool:
        """检查窗口是否可见"""
        return bool(self.user32.IsWindowVisible(hwnd))
    
    def _is_minimized(self, hwnd: int) -> bool:
        """检查窗口是否最小化"""
        return bool(self.user32.IsIconic(hwnd))
    
    def _is_maximized(self, hwnd: int) -> bool:
        """检查窗口是否最大化"""
        return bool(self.user32.IsZoomed(hwnd))
    
    def _is_foreground(self, hwnd: int) -> bool:
        """检查窗口是否为前台窗口"""
        return self.user32.GetForegroundWindow() == hwnd
    
    def _is_enabled(self, hwnd: int) -> bool:
        """检查窗口是否启用"""
        return bool(self.user32.IsWindowEnabled(hwnd))
    
    def _is_hung(self, hwnd: int) -> bool:
        """检查应用是否无响应"""
        return bool(self.user32.IsHungAppWindow(hwnd))
    
    def _is_cloaked(self, hwnd: int) -> bool:
        """
        检查窗口是否被隐藏 (Windows 8+ 特性)
        
        Cloaked 状态用于:
        - UWP 应用暂停时
        - 窗口在其他虚拟桌面
        - DWM 组合效果
        """
        try:
            dwmapi = ctypes.WinDLL('dwmapi')
            DWMWA_CLOAKED = 14
            cloaked = ctypes.c_int()
            result = dwmapi.DwmGetWindowAttribute(
                hwnd, DWMWA_CLOAKED, 
                ctypes.byref(cloaked), ctypes.sizeof(cloaked)
            )
            return result == 0 and cloaked.value != 0
        except Exception:
            return False
    
    def _is_on_current_desktop(self, hwnd: int) -> bool:
        """
        检查窗口是否在当前虚拟桌面 (Windows 10+)
        
        使用 IVirtualDesktopManager COM 接口
        """
        try:
            # 延迟初始化 Virtual Desktop Manager
            if self._virtual_desktop_manager is None:
                self._init_virtual_desktop_manager()
            
            if self._virtual_desktop_manager:
                is_on_current = ctypes.c_bool()
                hr = self._virtual_desktop_manager.IsWindowOnCurrentVirtualDesktop(
                    hwnd, ctypes.byref(is_on_current)
                )
                if hr == 0:  # S_OK
                    return is_on_current.value
        except Exception as e:
            logger.debug(f"Virtual desktop check failed: {e}")
        
        # 无法检测则假设在当前桌面
        return True
    
    def _init_virtual_desktop_manager(self):
        """初始化 Virtual Desktop Manager COM 接口"""
        try:
            import comtypes.client
            CLSID_VirtualDesktopManager = "{AA509086-5CA9-4C25-8F95-589D3C07B48A}"
            self._virtual_desktop_manager = comtypes.client.CreateObject(
                CLSID_VirtualDesktopManager
            )
        except Exception as e:
            logger.debug(f"Cannot initialize VirtualDesktopManager: {e}")
            self._virtual_desktop_manager = None
    
    def restore_window(self, hwnd: int) -> bool:
        """
        恢复窗口 (如果最小化)
        
        Returns:
            是否成功恢复
        """
        if not self._is_window(hwnd):
            return False
        
        if self._is_minimized(hwnd):
            SW_RESTORE = 9
            self.user32.ShowWindow(hwnd, SW_RESTORE)
            return True
        
        return False
    
    def bring_to_foreground(self, hwnd: int) -> bool:
        """
        将窗口置于前台
        
        Returns:
            是否成功
        """
        if not self._is_window(hwnd):
            return False
        
        # 先恢复
        self.restore_window(hwnd)
        
        # 设置前台
        return bool(self.user32.SetForegroundWindow(hwnd))


# 全局单例
_global_state_checker: Optional[WindowStateChecker] = None


def get_state_checker() -> WindowStateChecker:
    """获取全局窗口状态检查器"""
    global _global_state_checker
    if _global_state_checker is None:
        _global_state_checker = WindowStateChecker()
    return _global_state_checker


# 便捷函数
def is_window_operable(hwnd: int) -> Tuple[bool, str]:
    """快速检查窗口是否可操作"""
    return get_state_checker().is_operable(hwnd)


# 导出
__all__ = [
    'WindowState',
    'WindowStateChecker',
    'get_state_checker',
    'is_window_operable',
]
