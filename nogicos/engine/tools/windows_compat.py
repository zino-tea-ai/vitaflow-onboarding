# -*- coding: utf-8 -*-
"""
Windows Compatibility Layer - PostMessage + Fallback Strategy

Reference: Windows 系统工程师 Review 最佳实践

应用类型兼容性:
- 传统 Win32 应用: ✅ PostMessage 有效
- Electron 应用: ⚠️ 部分有效 (Chromium 自己处理输入)
- UWP 应用: ❌ 无效 (不同的消息模型)
- DirectX 游戏: ❌ 无效 (直接读取硬件输入)
"""

import ctypes
from ctypes import wintypes
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("nogicos.tools.windows_compat")


class InputMethod(Enum):
    """输入方式枚举"""
    POST_MESSAGE = "post_message"      # 非侵入式，不抢焦点
    SEND_INPUT = "send_input"          # 需要焦点，更可靠
    UI_AUTOMATION = "ui_automation"    # UIA，适合现代应用


@dataclass
class InputResult:
    """输入操作结果"""
    success: bool
    method_used: InputMethod
    fallback_count: int = 0
    error: Optional[str] = None


# Windows 消息常量
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEMOVE = 0x0200
WM_CHAR = 0x0102
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
MK_MBUTTON = 0x0010


class WindowInputController:
    """
    窗口输入控制器 - 自动 Fallback 策略
    
    优先级:
    1. PostMessage (非侵入式)
    2. SendInput (需要焦点)
    3. UI Automation (现代应用)
    """
    
    CLICK_DELAY_MS = 50      # 点击间隔
    CHAR_DELAY_MS = 20       # 输入字符间隔
    
    def __init__(self):
        # Load user32.dll
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self._setup_functions()
    
    def _setup_functions(self):
        """设置 Windows API 函数签名"""
        # PostMessageW
        self.user32.PostMessageW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        ]
        self.user32.PostMessageW.restype = wintypes.BOOL
        
        # SetForegroundWindow
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL
        
        # ClientToScreen
        self.user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        self.user32.ClientToScreen.restype = wintypes.BOOL
        
        # IsWindow
        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.restype = wintypes.BOOL
        
        # Clipboard APIs
        self.user32.OpenClipboard.argtypes = [wintypes.HWND]
        self.user32.OpenClipboard.restype = wintypes.BOOL
        
        self.user32.CloseClipboard.argtypes = []
        self.user32.CloseClipboard.restype = wintypes.BOOL
        
        self.user32.EmptyClipboard.argtypes = []
        self.user32.EmptyClipboard.restype = wintypes.BOOL
        
        self.user32.GetClipboardData.argtypes = [wintypes.UINT]
        self.user32.GetClipboardData.restype = wintypes.HANDLE
        
        self.user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        self.user32.SetClipboardData.restype = wintypes.HANDLE
        
        self.user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        self.user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
        
        # SendInput (for Ctrl+V)
        self.user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
        self.user32.SendInput.restype = wintypes.UINT
    
    async def click(self, hwnd: int, x: int, y: int, button: str = "left") -> InputResult:
        """
        点击操作 - 自动 Fallback
        
        Args:
            hwnd: 窗口句柄
            x: 客户区 X 坐标
            y: 客户区 Y 坐标
            button: "left", "right", "middle"
        """
        # 验证窗口有效性
        if not self.user32.IsWindow(hwnd):
            return InputResult(
                success=False,
                method_used=InputMethod.POST_MESSAGE,
                error="Invalid window handle"
            )
        
        # 1. 尝试 PostMessage (非侵入式)
        success = await self._try_post_message_click(hwnd, x, y, button)
        if success:
            return InputResult(success=True, method_used=InputMethod.POST_MESSAGE)
        
        # 2. Fallback: SetForegroundWindow + SendInput
        success = await self._fallback_send_input_click(hwnd, x, y, button)
        if success:
            return InputResult(
                success=True, 
                method_used=InputMethod.SEND_INPUT, 
                fallback_count=1
            )
        
        # 3. Fallback: UI Automation (最后手段)
        success = await self._fallback_uia_click(hwnd, x, y, button)
        if success:
            return InputResult(
                success=True, 
                method_used=InputMethod.UI_AUTOMATION, 
                fallback_count=2
            )
        
        return InputResult(
            success=False, 
            method_used=InputMethod.POST_MESSAGE,
            error="All input methods failed"
        )
    
    async def _try_post_message_click(
        self, hwnd: int, x: int, y: int, button: str = "left"
    ) -> bool:
        """尝试 PostMessage 点击"""
        try:
            lparam = self._make_lparam(x, y)
            
            # 根据按钮类型选择消息
            if button == "left":
                down_msg, up_msg, mk = WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON
            elif button == "right":
                down_msg, up_msg, mk = WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON
            else:  # middle
                down_msg, up_msg, mk = WM_MBUTTONDOWN, WM_MBUTTONUP, MK_MBUTTON
            
            # DOWN
            result = self.user32.PostMessageW(hwnd, down_msg, mk, lparam)
            if not result:
                logger.debug(f"PostMessage DOWN failed: {ctypes.get_last_error()}")
                return False
            
            await asyncio.sleep(self.CLICK_DELAY_MS / 1000)
            
            # UP
            result = self.user32.PostMessageW(hwnd, up_msg, 0, lparam)
            if not result:
                logger.debug(f"PostMessage UP failed: {ctypes.get_last_error()}")
                return False
            
            logger.debug(f"PostMessage click success at ({x}, {y})")
            return True
            
        except Exception as e:
            logger.debug(f"PostMessage click exception: {e}")
            return False
    
    async def _fallback_send_input_click(
        self, hwnd: int, x: int, y: int, button: str = "left"
    ) -> bool:
        """Fallback: 使用 SendInput (需要窗口焦点)"""
        try:
            # 1. 获取窗口焦点 (会打扰用户!)
            self.user32.SetForegroundWindow(hwnd)
            await asyncio.sleep(0.1)  # 等待窗口激活
            
            # 2. 转换客户区坐标到屏幕坐标
            point = wintypes.POINT(x, y)
            self.user32.ClientToScreen(hwnd, ctypes.byref(point))
            
            # 3. 使用 pyautogui
            try:
                import pyautogui
                pyautogui.click(point.x, point.y, button=button)
                logger.debug(f"SendInput fallback success at screen ({point.x}, {point.y})")
                return True
            except ImportError:
                logger.warning("pyautogui not available for SendInput fallback")
                return False
            
        except Exception as e:
            logger.debug(f"SendInput fallback exception: {e}")
            return False
    
    async def _fallback_uia_click(
        self, hwnd: int, x: int, y: int, button: str = "left"
    ) -> bool:
        """
        Fallback: 使用 pywinauto (如果可用)
        
        pywinauto 对现代应用有更好的支持
        """
        try:
            # 尝试使用 pywinauto
            from pywinauto import Desktop
            from pywinauto.controls.hwndwrapper import HwndWrapper
            
            # 包装窗口
            wrapper = HwndWrapper(hwnd)
            
            # 获取窗口矩形
            rect = wrapper.rectangle()
            
            # 计算屏幕坐标
            screen_x = rect.left + x
            screen_y = rect.top + y
            
            # 使用 pywinauto 点击
            if button == "left":
                wrapper.click_input(coords=(x, y))
            elif button == "right":
                wrapper.right_click_input(coords=(x, y))
            else:
                wrapper.click_input(coords=(x, y), button='middle')
            
            logger.debug(f"pywinauto click success at ({x}, {y})")
            return True
            
        except ImportError:
            logger.debug("pywinauto not available for UIA fallback")
            return False
        except Exception as e:
            logger.debug(f"pywinauto fallback exception: {e}")
            return False
    
    async def double_click(self, hwnd: int, x: int, y: int, button: str = "left") -> InputResult:
        """双击操作"""
        result1 = await self.click(hwnd, x, y, button)
        if not result1.success:
            return result1
        
        await asyncio.sleep(0.05)  # 50ms 间隔
        result2 = await self.click(hwnd, x, y, button)
        
        return InputResult(
            success=result2.success,
            method_used=result2.method_used,
            fallback_count=max(result1.fallback_count, result2.fallback_count),
            error=result2.error
        )
    
    async def type_text(self, hwnd: int, text: str) -> InputResult:
        """
        输入文字 - 智能选择输入方式
        
        - ASCII 字符: 使用 PostMessage WM_CHAR (更快)
        - 非 ASCII 字符 (中文等): 使用剪贴板 + Ctrl+V (更可靠)
        """
        try:
            # 检查是否包含非 ASCII 字符
            has_non_ascii = any(ord(c) > 127 for c in text)
            
            if has_non_ascii:
                # 使用剪贴板方式输入中文
                return await self._type_via_clipboard(hwnd, text)
            else:
                # ASCII 字符使用 WM_CHAR
                return await self._type_via_wm_char(hwnd, text)
            
        except Exception as e:
            return InputResult(
                success=False,
                method_used=InputMethod.POST_MESSAGE,
                error=str(e)
            )
    
    async def _type_via_wm_char(self, hwnd: int, text: str) -> InputResult:
        """使用 WM_CHAR 输入 ASCII 文字"""
        try:
            for char in text:
                result = self.user32.PostMessageW(hwnd, WM_CHAR, ord(char), 0)
                if not result:
                    return InputResult(
                        success=False,
                        method_used=InputMethod.POST_MESSAGE,
                        error=f"Failed to type character: {char}"
                    )
                await asyncio.sleep(self.CHAR_DELAY_MS / 1000)
            
            return InputResult(success=True, method_used=InputMethod.POST_MESSAGE)
            
        except Exception as e:
            return InputResult(
                success=False,
                method_used=InputMethod.POST_MESSAGE,
                error=str(e)
            )
    
    async def _send_ctrl_v(self, hwnd: int) -> bool:
        """
        发送 Ctrl+V - 使用 SendInput API (更可靠)
        
        SendInput 比 PostMessage 更可靠，因为：
        - 对 Electron/Chromium 应用有效
        - 对 UWP 应用有效
        - 模拟真实键盘输入
        
        缺点：需要窗口有焦点
        """
        import ctypes
        from ctypes import wintypes
        
        # SendInput 结构体
        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        VK_CONTROL = 0x11
        VK_V = 0x56
        
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]
        
        class INPUT(ctypes.Structure):
            class _INPUT_UNION(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT)]
            _anonymous_ = ("_input",)
            _fields_ = [
                ("type", wintypes.DWORD),
                ("_input", _INPUT_UNION),
            ]
        
        try:
            # 1. 激活目标窗口 (SendInput 需要窗口有焦点)
            self.user32.SetForegroundWindow(hwnd)
            await asyncio.sleep(0.05)  # 等待窗口激活
            
            # 2. 构造输入序列: Ctrl↓ V↓ V↑ Ctrl↑
            inputs = (INPUT * 4)()
            
            # Ctrl Down
            inputs[0].type = INPUT_KEYBOARD
            inputs[0].ki.wVk = VK_CONTROL
            inputs[0].ki.dwFlags = 0
            
            # V Down
            inputs[1].type = INPUT_KEYBOARD
            inputs[1].ki.wVk = VK_V
            inputs[1].ki.dwFlags = 0
            
            # V Up
            inputs[2].type = INPUT_KEYBOARD
            inputs[2].ki.wVk = VK_V
            inputs[2].ki.dwFlags = KEYEVENTF_KEYUP
            
            # Ctrl Up
            inputs[3].type = INPUT_KEYBOARD
            inputs[3].ki.wVk = VK_CONTROL
            inputs[3].ki.dwFlags = KEYEVENTF_KEYUP
            
            # 3. 发送输入
            sent = self.user32.SendInput(4, ctypes.byref(inputs), ctypes.sizeof(INPUT))
            
            if sent != 4:
                logger.warning(f"SendInput only sent {sent}/4 inputs")
                return False
            
            await asyncio.sleep(0.05)  # 等待粘贴完成
            return True
            
        except Exception as e:
            logger.error(f"SendInput Ctrl+V failed: {e}")
            # Fallback: 尝试 PostMessage 方式
            try:
                self.user32.PostMessageW(hwnd, WM_KEYDOWN, VK_CONTROL, 0)
                await asyncio.sleep(0.02)
                self.user32.PostMessageW(hwnd, WM_KEYDOWN, VK_V, 0)
                await asyncio.sleep(0.02)
                self.user32.PostMessageW(hwnd, WM_KEYUP, VK_V, 0)
                await asyncio.sleep(0.02)
                self.user32.PostMessageW(hwnd, WM_KEYUP, VK_CONTROL, 0)
                await asyncio.sleep(0.05)
                return True
            except Exception as e2:
                logger.error(f"PostMessage Ctrl+V fallback also failed: {e2}")
                return False
    
    async def _type_via_clipboard(self, hwnd: int, text: str) -> InputResult:
        """
        使用剪贴板 + Ctrl+V 输入文字 (支持中文)
        
        流程:
        1. 保存原剪贴板内容
        2. 设置新文字到剪贴板
        3. 发送 Ctrl+V
        4. 恢复原剪贴板内容
        """
        import ctypes
        from ctypes import wintypes
        
        # 剪贴板 API
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        
        try:
            # 1. 打开剪贴板
            if not self.user32.OpenClipboard(hwnd):
                # 如果无法用 hwnd 打开，尝试用 0
                if not self.user32.OpenClipboard(0):
                    return InputResult(
                        success=False,
                        method_used=InputMethod.POST_MESSAGE,
                        error="Failed to open clipboard"
                    )
            
            try:
                # 2. 保存原剪贴板内容
                original_data = None
                if self.user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                    handle = self.user32.GetClipboardData(CF_UNICODETEXT)
                    if handle:
                        ptr = kernel32.GlobalLock(handle)
                        if ptr:
                            original_data = ctypes.wstring_at(ptr)
                            kernel32.GlobalUnlock(handle)
                
                # 3. 清空并设置新内容
                self.user32.EmptyClipboard()
                
                # 分配内存
                text_bytes = (text + '\0').encode('utf-16-le')
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
                if not h_mem:
                    return InputResult(
                        success=False,
                        method_used=InputMethod.POST_MESSAGE,
                        error="Failed to allocate clipboard memory"
                    )
                
                # 复制数据
                ptr = kernel32.GlobalLock(h_mem)
                ctypes.memmove(ptr, text_bytes, len(text_bytes))
                kernel32.GlobalUnlock(h_mem)
                
                # 设置剪贴板
                self.user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                
            finally:
                self.user32.CloseClipboard()
            
            # 4. 发送 Ctrl+V - 使用 SendInput (更可靠)
            # PostMessage 对 Electron 等应用无效，SendInput 更通用
            await self._send_ctrl_v(hwnd)
            
            # 5. 恢复原剪贴板内容 (可选，避免覆盖用户数据)
            if original_data:
                try:
                    if self.user32.OpenClipboard(0):
                        try:
                            self.user32.EmptyClipboard()
                            orig_bytes = (original_data + '\0').encode('utf-16-le')
                            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(orig_bytes))
                            if h_mem:
                                ptr = kernel32.GlobalLock(h_mem)
                                ctypes.memmove(ptr, orig_bytes, len(orig_bytes))
                                kernel32.GlobalUnlock(h_mem)
                                self.user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                        finally:
                            self.user32.CloseClipboard()
                except:
                    pass  # 恢复失败不影响主流程
            
            return InputResult(success=True, method_used=InputMethod.POST_MESSAGE)
            
        except Exception as e:
            logger.error(f"Clipboard type failed: {e}")
            return InputResult(
                success=False,
                method_used=InputMethod.POST_MESSAGE,
                error=f"Clipboard type failed: {str(e)}"
            )
    
    async def key_press(self, hwnd: int, key_code: int) -> InputResult:
        """按键操作"""
        try:
            # KEY DOWN
            result = self.user32.PostMessageW(hwnd, WM_KEYDOWN, key_code, 0)
            if not result:
                return InputResult(
                    success=False,
                    method_used=InputMethod.POST_MESSAGE,
                    error="Failed to send key down"
                )
            
            await asyncio.sleep(self.CLICK_DELAY_MS / 1000)
            
            # KEY UP
            result = self.user32.PostMessageW(hwnd, WM_KEYUP, key_code, 0)
            if not result:
                return InputResult(
                    success=False,
                    method_used=InputMethod.POST_MESSAGE,
                    error="Failed to send key up"
                )
            
            return InputResult(success=True, method_used=InputMethod.POST_MESSAGE)
            
        except Exception as e:
            return InputResult(
                success=False,
                method_used=InputMethod.POST_MESSAGE,
                error=str(e)
            )
    
    async def drag(
        self, hwnd: int, 
        from_x: int, from_y: int, 
        to_x: int, to_y: int,
        steps: int = 10
    ) -> InputResult:
        """拖拽操作 - DOWN → MOVE → MOVE → UP"""
        try:
            # DOWN
            from_lparam = self._make_lparam(from_x, from_y)
            result = self.user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, from_lparam)
            if not result:
                return InputResult(
                    success=False,
                    method_used=InputMethod.POST_MESSAGE,
                    error="Failed to send mouse down for drag"
                )
            
            # MOVE (插值)
            for i in range(1, steps + 1):
                progress = i / steps
                curr_x = int(from_x + (to_x - from_x) * progress)
                curr_y = int(from_y + (to_y - from_y) * progress)
                move_lparam = self._make_lparam(curr_x, curr_y)
                self.user32.PostMessageW(hwnd, WM_MOUSEMOVE, MK_LBUTTON, move_lparam)
                await asyncio.sleep(0.01)
            
            # UP
            to_lparam = self._make_lparam(to_x, to_y)
            result = self.user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, to_lparam)
            if not result:
                return InputResult(
                    success=False,
                    method_used=InputMethod.POST_MESSAGE,
                    error="Failed to send mouse up for drag"
                )
            
            return InputResult(success=True, method_used=InputMethod.POST_MESSAGE)
            
        except Exception as e:
            return InputResult(
                success=False,
                method_used=InputMethod.POST_MESSAGE,
                error=str(e)
            )
    
    @staticmethod
    def _make_lparam(x: int, y: int) -> int:
        """构造 lParam: x in low word, y in high word"""
        return (y << 16) | (x & 0xFFFF)


class InputSimulator:
    """输入模拟器 - 处理消息时序 (简化版)"""
    
    def __init__(self):
        self.controller = WindowInputController()
    
    async def click(self, hwnd: int, x: int, y: int) -> InputResult:
        """单击"""
        return await self.controller.click(hwnd, x, y)
    
    async def double_click(self, hwnd: int, x: int, y: int) -> InputResult:
        """双击"""
        return await self.controller.double_click(hwnd, x, y)
    
    async def type_text(self, hwnd: int, text: str) -> InputResult:
        """输入文字"""
        return await self.controller.type_text(hwnd, text)
    
    async def drag(
        self, hwnd: int, 
        from_x: int, from_y: int, 
        to_x: int, to_y: int
    ) -> InputResult:
        """拖拽"""
        return await self.controller.drag(hwnd, from_x, from_y, to_x, to_y)


# 导出
__all__ = [
    'InputMethod',
    'InputResult', 
    'WindowInputController',
    'InputSimulator',
]
