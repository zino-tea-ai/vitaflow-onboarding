# -*- coding: utf-8 -*-
"""
Window Tools - 窗口隔离工具

整合所有 Windows 兼容性处理:
- PostMessage 点击 (非侵入式)
- 坐标转换 (截图坐标 ↔ 客户区坐标)
- DPI 处理
- UIPI 权限检查
- 窗口状态检测
- HWND 生命周期管理

参考:
- Anthropic Computer Use: 坐标缩放
- ByteBot: 750ms 等待时间
"""

import asyncio
import base64
import logging
from typing import Optional, Tuple
from io import BytesIO
from dataclasses import dataclass

# 导入兼容性模块
from .windows_compat import WindowInputController, InputResult, InputMethod
from .hwnd_manager import HwndManager, WindowLostError, get_hwnd_manager
from .coordinate_system import CoordinateTransformer, scale_coordinates, get_transformer
from .dpi_handler import DPIHandler, get_dpi_handler
from .uipi_checker import UIPIChecker, get_uipi_checker
from .window_state import WindowStateChecker, get_state_checker
from .win11_compat import get_win11_compat

logger = logging.getLogger("nogicos.tools.window_tools")


@dataclass
class WindowToolResult:
    """窗口工具执行结果"""
    success: bool
    output: str
    base64_image: Optional[str] = None
    error: Optional[str] = None
    input_method: Optional[InputMethod] = None
    fallback_count: int = 0


class WindowTools:
    """
    窗口工具 - 整合所有兼容性处理
    
    提供高层 API 用于窗口自动化操作
    """
    
    # 操作后等待时间 (参考 ByteBot)
    POST_ACTION_DELAY_MS = 750
    
    def __init__(self):
        self.input_controller = WindowInputController()
        self.hwnd_manager = get_hwnd_manager()
        self.coord_transformer = get_transformer()
        self.dpi_handler = get_dpi_handler()
        self.uipi_checker = get_uipi_checker()
        self.state_checker = get_state_checker()
        self.win11_compat = get_win11_compat()
    
    async def window_click(
        self, 
        x: int, 
        y: int, 
        hwnd: int,
        button: str = "left",
        capture_screenshot: bool = True
    ) -> WindowToolResult:
        """
        点击窗口 - 完整版本
        
        包含: 坐标转换、DPI 处理、Fallback 策略、状态检查
        
        Args:
            x: 截图坐标 X (相对于 1280x800)
            y: 截图坐标 Y (相对于 1280x800)
            hwnd: 目标窗口句柄
            button: "left", "right", "middle"
            capture_screenshot: 是否在操作后截图
            
        Returns:
            WindowToolResult
        """
        # 1. 检查窗口可操作性
        operable, reason = self.state_checker.is_operable(hwnd)
        if not operable:
            return WindowToolResult(
                success=False,
                output="",
                error=f"窗口无法操作: {reason}"
            )
        
        # 2. 检查 UIPI 权限
        accessibility = self.uipi_checker.check_window_accessibility(hwnd)
        if not accessibility.accessible:
            return WindowToolResult(
                success=False,
                output="",
                error=f"权限不足: {accessibility.reason}\n建议: {accessibility.suggestion}"
            )
        
        # 3. 坐标转换 (截图坐标 → 客户区坐标)
        client_x, client_y = scale_coordinates("api", x, y, hwnd)
        
        # 4. Windows 11 圆角补偿
        if self.win11_compat.is_windows_11():
            client_x, client_y = self.win11_compat.adjust_coordinates_for_rounded_corners(
                client_x, client_y, hwnd
            )
        
        # 5. 执行点击 (自动 Fallback)
        result = await self.input_controller.click(hwnd, client_x, client_y, button)
        
        # 6. 等待 UI 响应
        await asyncio.sleep(self.POST_ACTION_DELAY_MS / 1000)
        
        # 7. 截图验证
        screenshot_b64 = None
        if capture_screenshot:
            screenshot_b64 = await self._capture_window(hwnd)
        
        # 8. 构建返回结果
        output = f"点击 ({x}, {y}) -> 客户区 ({client_x}, {client_y})"
        if result.fallback_count > 0:
            output += f" [使用 Fallback: {result.method_used.value}]"
        
        return WindowToolResult(
            success=result.success,
            output=output,
            base64_image=screenshot_b64,
            error=result.error if not result.success else None,
            input_method=result.method_used,
            fallback_count=result.fallback_count
        )
    
    async def window_double_click(
        self, 
        x: int, 
        y: int, 
        hwnd: int,
        capture_screenshot: bool = True
    ) -> WindowToolResult:
        """双击窗口"""
        # 检查
        operable, reason = self.state_checker.is_operable(hwnd)
        if not operable:
            return WindowToolResult(success=False, output="", error=f"窗口无法操作: {reason}")
        
        # 坐标转换
        client_x, client_y = scale_coordinates("api", x, y, hwnd)
        
        # 执行双击
        result = await self.input_controller.double_click(hwnd, client_x, client_y)
        
        # 等待
        await asyncio.sleep(self.POST_ACTION_DELAY_MS / 1000)
        
        # 截图
        screenshot_b64 = None
        if capture_screenshot:
            screenshot_b64 = await self._capture_window(hwnd)
        
        return WindowToolResult(
            success=result.success,
            output=f"双击 ({x}, {y}) -> 客户区 ({client_x}, {client_y})",
            base64_image=screenshot_b64,
            error=result.error,
            input_method=result.method_used,
            fallback_count=result.fallback_count
        )
    
    async def window_type(
        self, 
        text: str, 
        hwnd: int,
        capture_screenshot: bool = True
    ) -> WindowToolResult:
        """在窗口中输入文字"""
        # 检查
        operable, reason = self.state_checker.is_operable(hwnd)
        if not operable:
            return WindowToolResult(success=False, output="", error=f"窗口无法操作: {reason}")
        
        # 执行输入
        result = await self.input_controller.type_text(hwnd, text)
        
        # 等待
        await asyncio.sleep(self.POST_ACTION_DELAY_MS / 1000)
        
        # 截图
        screenshot_b64 = None
        if capture_screenshot:
            screenshot_b64 = await self._capture_window(hwnd)
        
        return WindowToolResult(
            success=result.success,
            output=f"输入: {text[:50]}{'...' if len(text) > 50 else ''}",
            base64_image=screenshot_b64,
            error=result.error,
            input_method=result.method_used
        )
    
    async def window_drag(
        self, 
        from_x: int, from_y: int,
        to_x: int, to_y: int,
        hwnd: int,
        capture_screenshot: bool = True
    ) -> WindowToolResult:
        """在窗口中拖拽"""
        # 检查
        operable, reason = self.state_checker.is_operable(hwnd)
        if not operable:
            return WindowToolResult(success=False, output="", error=f"窗口无法操作: {reason}")
        
        # 坐标转换
        from_client_x, from_client_y = scale_coordinates("api", from_x, from_y, hwnd)
        to_client_x, to_client_y = scale_coordinates("api", to_x, to_y, hwnd)
        
        # 执行拖拽
        result = await self.input_controller.drag(
            hwnd, from_client_x, from_client_y, to_client_x, to_client_y
        )
        
        # 等待
        await asyncio.sleep(self.POST_ACTION_DELAY_MS / 1000)
        
        # 截图
        screenshot_b64 = None
        if capture_screenshot:
            screenshot_b64 = await self._capture_window(hwnd)
        
        return WindowToolResult(
            success=result.success,
            output=f"拖拽 ({from_x},{from_y}) -> ({to_x},{to_y})",
            base64_image=screenshot_b64,
            error=result.error,
            input_method=result.method_used
        )
    
    async def window_screenshot(self, hwnd: int) -> WindowToolResult:
        """截取窗口截图"""
        # 检查窗口是否存在
        state = self.state_checker.get_window_state(hwnd)
        if not state.exists:
            return WindowToolResult(
                success=False,
                output="",
                error="窗口不存在"
            )
        
        # 截图
        screenshot_b64 = await self._capture_window(hwnd)
        
        if screenshot_b64:
            return WindowToolResult(
                success=True,
                output="截图成功",
                base64_image=screenshot_b64
            )
        else:
            return WindowToolResult(
                success=False,
                output="",
                error="截图失败"
            )
    
    async def window_scroll(
        self,
        hwnd: int,
        direction: str,
        amount: int = 3,
        capture_screenshot: bool = True
    ) -> WindowToolResult:
        """
        滚动窗口
        
        Args:
            hwnd: 窗口句柄
            direction: "up", "down", "left", "right"
            amount: 滚动行数
            capture_screenshot: 是否截图
        """
        # 检查
        operable, reason = self.state_checker.is_operable(hwnd)
        if not operable:
            return WindowToolResult(success=False, output="", error=f"窗口无法操作: {reason}")
        
        # 执行滚动
        result = await self.input_controller.scroll(hwnd, direction, amount)
        
        # 等待
        await asyncio.sleep(self.POST_ACTION_DELAY_MS / 1000)
        
        # 截图
        screenshot_b64 = None
        if capture_screenshot:
            screenshot_b64 = await self._capture_window(hwnd)
        
        return WindowToolResult(
            success=result.success,
            output=f"滚动 {direction} {amount} 行",
            base64_image=screenshot_b64,
            error=result.error,
            input_method=result.method_used
        )
    
    async def window_hotkey(
        self,
        hwnd: int,
        keys: str,
        capture_screenshot: bool = True
    ) -> WindowToolResult:
        """
        发送快捷键
        
        Args:
            hwnd: 窗口句柄
            keys: 快捷键字符串, 如 "ctrl+c", "alt+tab"
            capture_screenshot: 是否截图
        """
        # 检查
        operable, reason = self.state_checker.is_operable(hwnd)
        if not operable:
            return WindowToolResult(success=False, output="", error=f"窗口无法操作: {reason}")
        
        # 执行快捷键
        result = await self.input_controller.hotkey(hwnd, keys)
        
        # 等待
        await asyncio.sleep(self.POST_ACTION_DELAY_MS / 1000)
        
        # 截图
        screenshot_b64 = None
        if capture_screenshot:
            screenshot_b64 = await self._capture_window(hwnd)
        
        return WindowToolResult(
            success=result.success,
            output=f"快捷键 {keys}",
            base64_image=screenshot_b64,
            error=result.error,
            input_method=result.method_used
        )
    
    async def window_key_press(
        self,
        hwnd: int,
        key: str,
        capture_screenshot: bool = False
    ) -> WindowToolResult:
        """
        按下单个按键
        
        Args:
            hwnd: 窗口句柄
            key: 按键名称, 如 "enter", "tab", "escape"
            capture_screenshot: 是否截图
        """
        # 检查
        operable, reason = self.state_checker.is_operable(hwnd)
        if not operable:
            return WindowToolResult(success=False, output="", error=f"窗口无法操作: {reason}")
        
        # 执行按键
        result = await self.input_controller.key_press_by_name(hwnd, key)
        
        # 短暂等待
        await asyncio.sleep(0.1)
        
        # 截图
        screenshot_b64 = None
        if capture_screenshot:
            screenshot_b64 = await self._capture_window(hwnd)
        
        return WindowToolResult(
            success=result.success,
            output=f"按键 {key}",
            base64_image=screenshot_b64,
            error=result.error,
            input_method=result.method_used
        )
    
    async def _capture_window(self, hwnd: int) -> Optional[str]:
        """
        截取窗口并返回 base64 编码的图片
        
        使用 PrintWindow API 截取指定窗口（即使被遮挡也能截取）
        缩放到 1280x800
        """
        try:
            from PIL import Image
            import ctypes
            from ctypes import wintypes
            
            # 先尝试 PrintWindow（不受遮挡影响）
            screenshot = await self._capture_with_printwindow(hwnd)
            
            if screenshot is None:
                # Fallback: 使用 ImageGrab（简单但受遮挡影响）
                screenshot = await self._capture_with_imagegrab(hwnd)
            
            if screenshot is None:
                return None
            
            # 缩放到目标尺寸
            target_size = (self.coord_transformer.TARGET_WIDTH, 
                          self.coord_transformer.TARGET_HEIGHT)
            screenshot = screenshot.resize(target_size, Image.Resampling.LANCZOS)
            
            # 转换为 base64
            buffer = BytesIO()
            screenshot.save(buffer, format='PNG', optimize=True)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return b64
            
        except ImportError:
            logger.error("PIL not available for screenshot")
            return None
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None
    
    async def _capture_with_printwindow(self, hwnd: int) -> Optional["Image.Image"]:
        """
        使用 PrintWindow API 截取窗口
        
        优点：即使窗口被遮挡也能截取
        缺点：某些应用可能不支持（如部分 DirectX 应用）
        """
        try:
            from PIL import Image
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
            
            # 获取窗口客户区尺寸
            rect = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            
            if width <= 0 or height <= 0:
                logger.warning(f"Invalid window size: {width}x{height}")
                return None
            
            # 创建兼容 DC 和位图
            hwnd_dc = user32.GetDC(hwnd)
            if not hwnd_dc:
                return None
            
            try:
                mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
                if not mem_dc:
                    return None
                
                try:
                    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
                    if not bitmap:
                        return None
                    
                    try:
                        old_bitmap = gdi32.SelectObject(mem_dc, bitmap)
                        
                        # PrintWindow - PW_RENDERFULLCONTENT = 2 (Windows 8.1+)
                        # 这个标志可以捕获 DirectComposition 内容
                        PW_RENDERFULLCONTENT = 2
                        result = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
                        
                        if not result:
                            # Fallback: 尝试不带标志
                            result = user32.PrintWindow(hwnd, mem_dc, 0)
                        
                        if not result:
                            logger.debug("PrintWindow failed")
                            return None
                        
                        # 准备 BITMAPINFO
                        class BITMAPINFOHEADER(ctypes.Structure):
                            _fields_ = [
                                ('biSize', wintypes.DWORD),
                                ('biWidth', wintypes.LONG),
                                ('biHeight', wintypes.LONG),
                                ('biPlanes', wintypes.WORD),
                                ('biBitCount', wintypes.WORD),
                                ('biCompression', wintypes.DWORD),
                                ('biSizeImage', wintypes.DWORD),
                                ('biXPelsPerMeter', wintypes.LONG),
                                ('biYPelsPerMeter', wintypes.LONG),
                                ('biClrUsed', wintypes.DWORD),
                                ('biClrImportant', wintypes.DWORD),
                            ]
                        
                        bi = BITMAPINFOHEADER()
                        bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                        bi.biWidth = width
                        bi.biHeight = -height  # 负值 = 自上而下
                        bi.biPlanes = 1
                        bi.biBitCount = 32
                        bi.biCompression = 0  # BI_RGB
                        
                        # 获取位图数据
                        buffer_size = width * height * 4
                        buffer = ctypes.create_string_buffer(buffer_size)
                        
                        gdi32.GetDIBits(
                            mem_dc, bitmap, 0, height,
                            buffer, ctypes.byref(bi), 0  # DIB_RGB_COLORS
                        )
                        
                        # 转换为 PIL Image (BGRA -> RGBA)
                        img = Image.frombuffer('RGBA', (width, height), buffer, 'raw', 'BGRA', 0, 1)
                        
                        # 转换为 RGB（去掉 Alpha）
                        img = img.convert('RGB')
                        
                        return img
                        
                    finally:
                        gdi32.SelectObject(mem_dc, old_bitmap)
                        gdi32.DeleteObject(bitmap)
                finally:
                    gdi32.DeleteDC(mem_dc)
            finally:
                user32.ReleaseDC(hwnd, hwnd_dc)
                
        except Exception as e:
            logger.debug(f"PrintWindow capture failed: {e}")
            return None
    
    async def _capture_with_imagegrab(self, hwnd: int) -> Optional["Image.Image"]:
        """
        使用 ImageGrab 截取窗口（Fallback）
        
        注意：如果窗口被遮挡，会截取到遮挡窗口的内容
        """
        try:
            from PIL import ImageGrab
            
            # 获取窗口实际可见区域 (Windows 11 兼容)
            rect = self.win11_compat.get_actual_window_rect(hwnd)
            
            # 使用 PIL 截图
            screenshot = ImageGrab.grab(bbox=rect)
            return screenshot
            
        except Exception as e:
            logger.debug(f"ImageGrab capture failed: {e}")
            return None
    
    def get_window_info(self, hwnd: int) -> dict:
        """获取窗口信息"""
        state = self.state_checker.get_window_state(hwnd)
        coords = self.coord_transformer.get_window_coordinates(hwnd)
        dpi_scale = self.dpi_handler.get_window_dpi(hwnd)
        
        return {
            "hwnd": hwnd,
            "title": self.hwnd_manager.get_window_title(hwnd),
            "state": {
                "exists": state.exists,
                "visible": state.visible,
                "minimized": state.minimized,
                "maximized": state.maximized,
                "foreground": state.foreground,
                "enabled": state.enabled,
                "hung": state.hung,
            },
            "coordinates": {
                "window_rect": coords.window_rect,
                "client_rect": coords.client_rect,
                "client_size": (coords.client_width, coords.client_height),
            },
            "dpi_scale": dpi_scale,
            "is_windows_11": self.win11_compat.is_windows_11(),
        }


def register_window_tools(registry):
    """注册窗口工具到 Registry"""
    from .base import ToolCategory
    from typing import Dict, Any
    
    # 创建单例
    window_tools = WindowTools()
    
    @registry.action(
        description="""点击窗口中的指定位置。

参数:
- x: 截图上的 X 坐标 (0-1280)
- y: 截图上的 Y 坐标 (0-800)  
- hwnd: 目标窗口句柄
- button: 鼠标按键 ("left", "right", "middle")

功能:
- 自动将截图坐标转换为窗口客户区坐标
- 使用 PostMessage 非侵入式点击 (不抢焦点)
- 自动处理 DPI 缩放和 Windows 11 圆角
- 点击后自动截图验证

返回: 包含截图的结构化数据，用于验证点击效果""",
        category=ToolCategory.LOCAL,
    )
    async def window_click(
        x: int, 
        y: int, 
        hwnd: int,
        button: str = "left"
    ) -> Dict[str, Any]:
        """点击窗口 - 返回结构化数据含截图"""
        result = await window_tools.window_click(x, y, hwnd, button)
        return {
            "type": "window_action",
            "action": "click",
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "image_base64": result.base64_image,
            "input_method": result.input_method.value if result.input_method else None,
            "fallback_count": result.fallback_count,
        }
    
    @registry.action(
        description="""双击窗口中的指定位置。

参数:
- x: 截图上的 X 坐标 (0-1280)
- y: 截图上的 Y 坐标 (0-800)
- hwnd: 目标窗口句柄

返回: 包含截图的结构化数据""",
        category=ToolCategory.LOCAL,
    )
    async def window_double_click(
        x: int, 
        y: int, 
        hwnd: int
    ) -> Dict[str, Any]:
        """双击窗口 - 返回结构化数据含截图"""
        result = await window_tools.window_double_click(x, y, hwnd)
        return {
            "type": "window_action",
            "action": "double_click",
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "image_base64": result.base64_image,
            "input_method": result.input_method.value if result.input_method else None,
            "fallback_count": result.fallback_count,
        }
    
    @registry.action(
        description="""在窗口中输入文字。

参数:
- text: 要输入的文字
- hwnd: 目标窗口句柄

功能:
- ASCII 字符使用 PostMessage WM_CHAR
- 中文等非 ASCII 字符使用剪贴板粘贴

返回: 包含截图的结构化数据""",
        category=ToolCategory.LOCAL,
    )
    async def window_type(
        text: str, 
        hwnd: int
    ) -> Dict[str, Any]:
        """输入文字 - 返回结构化数据含截图"""
        result = await window_tools.window_type(text, hwnd)
        return {
            "type": "window_action",
            "action": "type",
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "image_base64": result.base64_image,
            "input_method": result.input_method.value if result.input_method else None,
        }
    
    @registry.action(
        description="""在窗口中拖拽。

参数:
- from_x, from_y: 起始位置 (截图坐标)
- to_x, to_y: 终止位置 (截图坐标)
- hwnd: 目标窗口句柄

返回: 包含截图的结构化数据""",
        category=ToolCategory.LOCAL,
    )
    async def window_drag(
        from_x: int, from_y: int,
        to_x: int, to_y: int,
        hwnd: int
    ) -> Dict[str, Any]:
        """拖拽 - 返回结构化数据含截图"""
        result = await window_tools.window_drag(from_x, from_y, to_x, to_y, hwnd)
        return {
            "type": "window_action",
            "action": "drag",
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "image_base64": result.base64_image,
            "input_method": result.input_method.value if result.input_method else None,
        }
    
    @registry.action(
        description="""截取窗口截图。

参数:
- hwnd: 目标窗口句柄

返回: 1280x800 的窗口截图 (base64 编码)""",
        category=ToolCategory.LOCAL,
    )
    async def window_screenshot(hwnd: int) -> Dict[str, Any]:
        """截取窗口截图 - 返回结构化数据含截图"""
        result = await window_tools.window_screenshot(hwnd)
        window_info = window_tools.get_window_info(hwnd)
        return {
            "type": "window_screenshot",
            "success": result.success,
            "image_base64": result.base64_image,
            "error": result.error,
            "window_title": window_info.get("title", ""),
            "window_size": window_info.get("coordinates", {}).get("client_size", [0, 0]),
        }
    
    @registry.action(
        description="""获取窗口信息。

参数:
- hwnd: 目标窗口句柄

返回: 窗口标题、状态、尺寸、DPI 等信息""",
        category=ToolCategory.LOCAL,
    )
    async def get_window_info(hwnd: int) -> Dict[str, Any]:
        """获取窗口信息"""
        info = window_tools.get_window_info(hwnd)
        return {
            "type": "window_info",
            **info
        }
    
    logger.info("[WindowTools] All window tools registered")


# 导出
__all__ = [
    'WindowToolResult',
    'WindowTools',
    'register_window_tools',
    'WindowLostError',
]
