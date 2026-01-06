# -*- coding: utf-8 -*-
"""
Browser Hook - 浏览器感知

通用方式感知用户浏览器状态：
1. Accessibility API - 获取窗口标题
2. Screenshot + Vision - 提取 URL、页面内容
3. OCR - 本地 OCR 提取地址栏文字
"""

import asyncio
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .base_hook import BaseHook, HookConfig
from ..store import HookType, BrowserContext

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
    """窗口信息"""
    hwnd: int = 0
    title: str = ""
    class_name: str = ""
    process_name: str = ""
    rect: Tuple[int, int, int, int] = (0, 0, 0, 0)  # left, top, right, bottom
    
    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]
    
    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]
    
    @property
    def x(self) -> int:
        return self.rect[0]
    
    @property
    def y(self) -> int:
        return self.rect[1]


class BrowserHook(BaseHook):
    """
    浏览器 Hook
    
    感知用户浏览器状态，不需要任何插件
    """
    
    # 支持的浏览器
    SUPPORTED_BROWSERS = {
        "chrome": ["Chrome", "Google Chrome"],
        "firefox": ["Firefox", "Mozilla Firefox"],
        "edge": ["Edge", "Microsoft Edge"],
        "brave": ["Brave"],
        "arc": ["Arc"],
    }
    
    # 浏览器窗口类名（Windows）
    BROWSER_CLASS_NAMES = {
        "Chrome_WidgetWin_1": "chrome",
        "MozillaWindowClass": "firefox",
        "Chrome_WidgetWin_0": "edge",  # Edge 也用 Chromium
    }
    
    def __init__(
        self,
        hook_id: str = "browser",
        config: Optional[HookConfig] = None,
    ):
        super().__init__(hook_id, HookType.BROWSER, config)
        
        self._target_browser: Optional[str] = None  # chrome, firefox, edge, etc.
        self._target_hwnd: Optional[int] = None
        self._last_context: Optional[BrowserContext] = None
    
    async def _connect(self, target: Optional[str] = None) -> bool:
        """
        连接到浏览器
        
        Args:
            target: 浏览器类型（chrome, firefox, edge）或 None（自动检测）
        """
        self._target_browser = target
        
        # 检测浏览器窗口
        window = await self._find_browser_window(target)
        
        if window:
            self._target_hwnd = window.hwnd
            self._target_browser = self._detect_browser_type(window)
            logger.info(f"[BrowserHook] Found {self._target_browser}: {window.title}")
            return True
        else:
            logger.warning("[BrowserHook] No browser window found")
            return False
    
    async def _disconnect(self) -> bool:
        """断开连接"""
        self._target_hwnd = None
        self._target_browser = None
        self._last_context = None
        return True
    
    async def capture(self) -> Optional[BrowserContext]:
        """
        捕获浏览器上下文
        
        Returns:
            BrowserContext 或 None
        """
        try:
            # 获取当前活跃的浏览器窗口
            window = await self._find_browser_window(self._target_browser)
            
            if not window:
                return self._last_context
            
            self._target_hwnd = window.hwnd
            
            # 从窗口标题提取信息
            title, url = self._parse_browser_title(window.title)
            
            # 创建上下文
            context = BrowserContext(
                app=self._target_browser or self._detect_browser_type(window),
                url=url,
                title=title,
                window_title=window.title,  # 完整窗口标题（用于 Overlay 精确匹配）
                hwnd=window.hwnd,  # 窗口句柄，用于 Overlay
                tab_count=1,  # 从标题无法得知 tab 数量
                last_updated=datetime.now().isoformat(),
            )
            
            # 如果启用 OCR，尝试提取更多信息
            if self.config.enable_ocr:
                try:
                    url_from_ocr = await self._ocr_address_bar(window)
                    if url_from_ocr:
                        context.url = url_from_ocr
                except Exception as e:
                    logger.debug(f"[BrowserHook] OCR failed: {e}")
            
            self._last_context = context
            return context
            
        except Exception as e:
            logger.error(f"[BrowserHook] Capture failed: {e}")
            return self._last_context
    
    def _detect_browser_type(self, window: WindowInfo) -> str:
        """从窗口信息检测浏览器类型"""
        # 优先用 class_name
        if window.class_name in self.BROWSER_CLASS_NAMES:
            return self.BROWSER_CLASS_NAMES[window.class_name]
        
        # 从标题检测
        title_lower = window.title.lower()
        for browser_id, names in self.SUPPORTED_BROWSERS.items():
            for name in names:
                if name.lower() in title_lower:
                    return browser_id
        
        return "unknown"
    
    def _parse_browser_title(self, title: str) -> Tuple[str, str]:
        """
        从浏览器标题解析页面标题和可能的 URL
        
        典型格式: "Google - Chrome"
                  "example.com - Page Title - Edge"
        
        Returns:
            (page_title, url_hint)
        """
        if not title:
            return "", ""
        
        # 移除浏览器名称后缀
        for names in self.SUPPORTED_BROWSERS.values():
            for name in names:
                if title.endswith(f" - {name}"):
                    title = title[:-len(f" - {name}")]
                    break
                if title.endswith(f" — {name}"):  # em dash
                    title = title[:-len(f" — {name}")]
                    break
        
        # 尝试提取域名
        url_hint = ""
        # 匹配 domain.com 格式
        domain_match = re.search(r'([a-zA-Z0-9-]+\.[a-zA-Z]{2,})', title)
        if domain_match:
            url_hint = f"https://{domain_match.group(1)}"
        
        return title.strip(), url_hint
    
    async def _find_browser_window(self, target_browser: Optional[str] = None) -> Optional[WindowInfo]:
        """
        查找浏览器窗口
        
        Args:
            target_browser: 指定浏览器，None 则查找任意浏览器
            
        Returns:
            WindowInfo 或 None
        """
        if sys.platform == "win32" and WINDOWS_AVAILABLE:
            return await self._find_browser_window_windows(target_browser)
        else:
            # macOS / Linux 暂未实现
            logger.warning(f"[BrowserHook] Platform {sys.platform} not fully supported")
            return None
    
    async def _find_browser_window_windows(self, target_browser: Optional[str] = None) -> Optional[WindowInfo]:
        """Windows 平台查找浏览器窗口"""
        try:
            user32 = ctypes.windll.user32
            
            # 获取前台窗口
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                window = self._get_window_info_windows(hwnd)
                if window and self._is_browser_window(window, target_browser):
                    return window
            
            # 枚举所有窗口查找浏览器
            windows = []
            
            def enum_callback(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    window = self._get_window_info_windows(hwnd)
                    if window and self._is_browser_window(window, target_browser):
                        windows.append(window)
                return True
            
            # 【修复 #18】缓存 WNDENUMPROC 类型避免重复创建
            if not hasattr(self, '_WNDENUMPROC'):
                self._WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(self._WNDENUMPROC(enum_callback), 0)
            
            if windows:
                return windows[0]
            
            return None
            
        except Exception as e:
            logger.error(f"[BrowserHook] Window enumeration failed: {e}")
            return None
    
    def _get_window_info_windows(self, hwnd: int) -> Optional[WindowInfo]:
        """获取 Windows 窗口信息"""
        try:
            user32 = ctypes.windll.user32
            
            # 获取窗口标题
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return None
            
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
            
            # 获取类名
            class_buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buffer, 256)
            class_name = class_buffer.value
            
            # 获取窗口位置
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            
            return WindowInfo(
                hwnd=hwnd,
                title=title,
                class_name=class_name,
                rect=(rect.left, rect.top, rect.right, rect.bottom),
            )
            
        except Exception as e:
            logger.debug(f"[BrowserHook] Get window info failed: {e}")
            return None
    
    # 要排除的 Electron 应用（它们也用 Chrome_WidgetWin_1 类名）
    EXCLUDED_ELECTRON_APPS = [
        "nogicos", "nogicos-ui", "cursor", "vscode", "visual studio code",
        "electron", "slack", "discord", "notion", "figma",
    ]
    
    def _is_browser_window(self, window: WindowInfo, target_browser: Optional[str] = None) -> bool:
        """
        判断是否是浏览器窗口
        
        【通用方案】优先检查标题中是否包含浏览器名称，
        因为 Chrome_WidgetWin_1 类名被很多 Electron 应用使用。
        """
        title_lower = window.title.lower()
        
        # 【优先】检查标题是否包含浏览器名称
        # 真正的浏览器标题格式: "页面标题 - Google Chrome"
        for browser_id, names in self.SUPPORTED_BROWSERS.items():
            if target_browser and browser_id != target_browser:
                continue
            for name in names:
                if name.lower() in title_lower:
                    return True
        
        # 【备用】如果标题没有浏览器名称，检查类名
        # 但这可能误判 Electron 应用，所以只作为备用
        # if window.class_name in self.BROWSER_CLASS_NAMES:
        #     detected = self.BROWSER_CLASS_NAMES[window.class_name]
        #     if target_browser is None or detected == target_browser:
        #         return True
        
        return False
    
    async def _ocr_address_bar(self, window: WindowInfo) -> Optional[str]:
        """
        OCR 提取地址栏 URL
        
        使用 Windows 内置 OCR 或 Tesseract
        """
        try:
            from .screenshot_utils import capture_screen
            from .ocr_utils import get_screenshot_ocr
            
            # 地址栏区域估计：窗口顶部
            # Chrome/Edge: 标题栏约 30px，tab 栏约 35px，地址栏在 70-130px
            address_bar_region = (
                window.x + 100,       # 跳过浏览器导航按钮
                window.y + 50,        # 跳过标题栏
                window.width - 300,   # 减去右侧按钮
                60,                   # 地址栏高度
            )
            
            # 截取地址栏
            screenshot_data = await capture_screen(address_bar_region)
            if not screenshot_data:
                return None
            
            # OCR 提取 URL
            ocr = get_screenshot_ocr()
            if not ocr.available:
                logger.debug("[BrowserHook] OCR not available")
                return None
            
            url = await ocr.extract_url(screenshot_data)
            if url:
                logger.debug(f"[BrowserHook] OCR extracted URL: {url}")
            return url
            
        except Exception as e:
            logger.debug(f"[BrowserHook] OCR failed: {e}")
            return None
    
    def get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """
        获取当前浏览器窗口位置
        
        供 Overlay 使用
        
        Returns:
            (x, y, width, height) 或 None
        """
        if not self._target_hwnd:
            return None
        
        try:
            if sys.platform == "win32" and WINDOWS_AVAILABLE:
                window = self._get_window_info_windows(self._target_hwnd)
                if window:
                    return (window.x, window.y, window.width, window.height)
        except Exception as e:
            logger.error(f"[BrowserHook] Get window rect failed: {e}")
        
        return None

