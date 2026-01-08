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

# ============================================================================
# DPI 感知设置 - 必须在任何 pyautogui/UIA 操作之前设置
# 否则高 DPI 屏幕 (如 1.75x 缩放) 上坐标会错误
# ============================================================================
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    logger.info("DPI awareness set to PROCESS_PER_MONITOR_DPI_AWARE")
except Exception as e:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # 旧版 Windows 回退
        logger.info("DPI awareness set via SetProcessDPIAware (legacy)")
    except Exception:
        logger.warning(f"Failed to set DPI awareness: {e}")

# #region agent log helper (debug mode)
import json as _json
import os as _os
import time as _time
from pathlib import Path as _Path
_DEBUG_LOG_PATH = _Path(r"c:\Users\WIN\Desktop\Cursor Project\.cursor\debug.log")

def _win_compat_dbg_log(hypothesis_id: str, location: str, message: str, data: dict):
    """Write a single NDJSON debug line to debug.log (append-only)."""
    try:
        payload = {
            "sessionId": "debug-session",
            "runId": "pre-fix-1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(_time.time() * 1000),
        }
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(_json.dumps(payload, ensure_ascii=False) + "\n")
            f.flush()
            _os.fsync(f.fileno())
    except Exception:
        pass
# #endregion


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
        
        # AllowSetForegroundWindow - allows background process to set foreground window
        self.user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
        self.user32.AllowSetForegroundWindow.restype = wintypes.BOOL
        
        # AttachThreadInput - attach our thread to another thread's input queue
        self.user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
        self.user32.AttachThreadInput.restype = wintypes.BOOL
        
        # GetForegroundWindow - get the current foreground window
        self.user32.GetForegroundWindow.argtypes = []
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        
        # GetWindowThreadProcessId - get thread ID of window
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        
        # BringWindowToTop - bring window to top of Z-order
        self.user32.BringWindowToTop.argtypes = [wintypes.HWND]
        self.user32.BringWindowToTop.restype = wintypes.BOOL
        
        # ClientToScreen
        self.user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        self.user32.ClientToScreen.restype = wintypes.BOOL
        
        # IsWindow
        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.restype = wintypes.BOOL

        # SetCursorPos / mouse_event for pointer control
        self.user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self.user32.SetCursorPos.restype = wintypes.BOOL

        # Note: dwExtraInfo uses ULONG_PTR in WinAPI; use DWORD for compatibility
        self.user32.mouse_event.argtypes = [
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD
        ]
        self.user32.mouse_event.restype = None
        
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
        点击操作 - 直接使用 pyautogui (最可靠)
        
        对于现代应用 (WhatsApp/Electron 等)，PostMessage 无效
        直接使用 pyautogui 全局点击
        
        Args:
            hwnd: 窗口句柄
            x: 客户区 X 坐标
            y: 客户区 Y 坐标
            button: "left", "right", "middle"
        """
        import pyautogui
        
        # 验证窗口有效性
        if not self.user32.IsWindow(hwnd):
            return InputResult(
                success=False,
                method_used=InputMethod.POST_MESSAGE,
                error="Invalid window handle"
            )
        
        try:
            # 获取窗口屏幕位置
            rect = wintypes.RECT()
            if not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return InputResult(
                    success=False,
                    method_used=InputMethod.SEND_INPUT,
                    error="Failed to get window rect"
                )
            
            # 转换客户区坐标为屏幕坐标
            screen_x = rect.left + x
            screen_y = rect.top + y
            
            # #region agent log J1
            _win_compat_dbg_log("J1", "click:pyautogui", "Using pyautogui click", {
                "hwnd": hwnd, "client_x": x, "client_y": y, 
                "screen_x": screen_x, "screen_y": screen_y,
                "rect": {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom}
            })
            # #endregion
            
            # 使用 pyautogui 点击
            pyautogui.click(screen_x, screen_y, button=button)
            await asyncio.sleep(0.1)
            
            return InputResult(success=True, method_used=InputMethod.SEND_INPUT)
            
        except Exception as e:
            # #region agent log J1
            _win_compat_dbg_log("J1", "click:error", "pyautogui click failed", {"error": str(e)})
            # #endregion
            return InputResult(
                success=False,
                method_used=InputMethod.SEND_INPUT,
                error=f"pyautogui click failed: {str(e)}"
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
            # 0. 验证窗口仍然有效 (防止 TOCTOU)
            if not self.user32.IsWindow(hwnd):
                logger.debug("Window closed before SendInput fallback")
                return False

            # 1. 获取窗口焦点 (会打扰用户!)
            self.user32.SetForegroundWindow(hwnd)
            await asyncio.sleep(0.1)  # 等待窗口激活

            # 再次验证
            if not self.user32.IsWindow(hwnd):
                return False

            # 2. 转换客户区坐标到屏幕坐标
            point = wintypes.POINT(x, y)
            if not self.user32.ClientToScreen(hwnd, ctypes.byref(point)):
                logger.debug("ClientToScreen failed")
                return False

            # 3. 验证坐标合理性
            if point.x < -10000 or point.x > 50000 or point.y < -10000 or point.y > 50000:
                logger.debug(f"Invalid screen coordinates: ({point.x}, {point.y})")
                return False

            # 4. 使用 pyautogui
            try:
                import pyautogui
                pyautogui.click(point.x, point.y, button=button)
                logger.debug(f"SendInput fallback success at screen ({point.x}, {point.y})")
                return True
            except ImportError:
                logger.warning("pyautogui not available for SendInput fallback")
                return False
            except Exception as e:
                # CRITICAL: Log the actual error instead of hiding it
                logger.warning(f"pyautogui.click failed at ({point.x}, {point.y}): {e}")
                return False

        except Exception as e:
            logger.warning(f"SendInput fallback exception: {e}")
            return False
    
    async def _fallback_uia_click(
        self, hwnd: int, x: int, y: int, button: str = "left"
    ) -> bool:
        """
        Fallback: 使用 pywinauto (如果可用)

        pywinauto 对现代应用有更好的支持
        """
        try:
            # 0. 验证窗口仍然有效 (防止 pywinauto 在无效 HWND 上崩溃)
            if not self.user32.IsWindow(hwnd):
                logger.debug("Window closed before pywinauto fallback")
                return False

            # 尝试使用 pywinauto
            from pywinauto import Desktop
            from pywinauto.controls.hwndwrapper import HwndWrapper

            # 包装窗口 (在 try 块内，捕获任何 pywinauto 异常)
            wrapper = HwndWrapper(hwnd)

            # 再次验证窗口有效
            if not self.user32.IsWindow(hwnd):
                return False

            # 获取窗口矩形
            rect = wrapper.rectangle()

            # 验证矩形合理性
            if rect.width() <= 0 or rect.height() <= 0:
                logger.debug(f"Invalid window rect: {rect}")
                return False

            # 验证坐标在窗口范围内 (with tolerance for edge cases)
            tolerance = 10  # Allow 10px outside window bounds
            if x < -tolerance or x > rect.width() + tolerance or y < -tolerance or y > rect.height() + tolerance:
                logger.debug(f"Coordinates ({x}, {y}) far outside window bounds (w={rect.width()}, h={rect.height()})")
                return False

            # Clamp coordinates to valid range (handle edge clicks gracefully)
            clamped_x = max(1, min(x, rect.width() - 1))
            clamped_y = max(1, min(y, rect.height() - 1))
            if clamped_x != x or clamped_y != y:
                logger.debug(f"Coordinates clamped: ({x}, {y}) -> ({clamped_x}, {clamped_y})")
                x, y = clamped_x, clamped_y

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
        输入文字 - 使用 pyautogui (最可靠)
        
        对于现代应用 (Electron/WhatsApp 等)，PostMessage 无效
        直接使用 pyautogui 全局键盘模拟
        """
        return await self._type_via_pyautogui(hwnd, text)
    
    async def _type_via_pyautogui(self, hwnd: int, text: str) -> InputResult:
        """
        最简单直接的方案：pywinauto 直接操作控件 (不依赖任何鼠标坐标)
        """
        import pyperclip
        
        try:
            from pywinauto import Desktop
            from pywinauto.keyboard import send_keys
            
            _win_compat_dbg_log("SIMPLE", "start", "Direct control method", {"hwnd": hwnd})
            
            # 1. 激活窗口
            self.user32.SetForegroundWindow(hwnd)
            await asyncio.sleep(0.2)
            
            # 2. 用 pywinauto 找到窗口和输入控件
            desktop = Desktop(backend='uia')
            target_window = None
            for win in desktop.windows():
                if win.handle == hwnd:
                    target_window = win
                    break
            
            if target_window:
                # 找 Edit 控件
                edits = list(target_window.descendants(control_type='Edit'))
                _win_compat_dbg_log("SIMPLE", "edits", f"Found {len(edits)} Edit controls", {})
                
                if edits:
                    # 用最底部的 Edit
                    bottom_edit = max(edits, key=lambda e: e.rectangle().top)
                    rect = bottom_edit.rectangle()
                    # #region agent log
                    _win_compat_dbg_log("F2", "edit_info", f"Selected Edit control", {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom, "class_name": getattr(bottom_edit, 'class_name', lambda: 'unknown')()})
                    # #endregion
                    
                    # 直接设置焦点到控件（不需要点击）
                    try:
                        bottom_edit.set_focus()
                        await asyncio.sleep(0.1)
                        # #region agent log
                        _win_compat_dbg_log("F2", "focus", "Focus set successfully", {})
                        # #endregion
                    except Exception as focus_err:
                        # #region agent log
                        _win_compat_dbg_log("F2", "focus_fail", str(focus_err), {})
                        # #endregion
                    
                    # ====== 修复：跳过 set_edit_text，直接使用剪贴板（对 Electron 应用更可靠）======
                    # set_edit_text 对 Electron/Chromium 应用（如 WhatsApp）通常无效
                    # #region agent log
                    _win_compat_dbg_log("F2", "strategy", "Using clipboard paste (more reliable for Electron apps)", {})
                    # #endregion
                    
                    # 剪贴板粘贴（对所有应用都可靠）
                    try:
                        original = pyperclip.paste()
                    except:
                        original = ""
                    
                    pyperclip.copy(text)
                    # #region agent log
                    _win_compat_dbg_log("F2", "clipboard", f"Copied to clipboard", {"text_len": len(text), "text_preview": text[:50] if len(text) > 50 else text})
                    # #endregion
                    await asyncio.sleep(0.05)
                    
                    # 确保目标窗口有焦点
                    try:
                        target_window.set_focus()
                        await asyncio.sleep(0.3)  # 增加延迟，让窗口真正激活
                        # #region agent log
                        _win_compat_dbg_log("F2", "window_focus", "Window focus set before paste", {})
                        # #endregion
                    except Exception as wf_err:
                        # #region agent log
                        _win_compat_dbg_log("F2", "window_focus_fail", str(wf_err), {})
                        # #endregion
                    
                    # 点击输入框确保它真正获得焦点（对 Electron 应用关键）
                    try:
                        import pyautogui
                        edit_rect = bottom_edit.rectangle()
                        click_x = (edit_rect.left + edit_rect.right) // 2
                        click_y = (edit_rect.top + edit_rect.bottom) // 2
                        pyautogui.click(click_x, click_y)
                        await asyncio.sleep(0.2)
                        # #region agent log
                        _win_compat_dbg_log("F3", "click_edit", "Clicked edit control to ensure focus", {"x": click_x, "y": click_y})
                        # #endregion
                    except Exception as click_err:
                        # #region agent log
                        _win_compat_dbg_log("F3", "click_fail", str(click_err), {})
                        # #endregion
                    
                    # 使用 pyautogui.hotkey 代替 send_keys（更可靠）
                    import pyautogui
                    pyautogui.hotkey('ctrl', 'v')
                    # #region agent log
                    _win_compat_dbg_log("F3", "paste_sent", "Ctrl+V sent via pyautogui.hotkey", {})
                    # #endregion
                    await asyncio.sleep(0.2)
                    
                    try:
                        pyperclip.copy(original)
                    except:
                        pass
                    
                    # #region agent log
                    _win_compat_dbg_log("F2", "done", "Clipboard paste completed", {"text": text})
                    return InputResult(success=True, method_used=InputMethod.UI_AUTOMATION)
            
            # 回退：直接发送键盘（假设窗口已有焦点）
            _win_compat_dbg_log("SIMPLE", "fallback", "No Edit found, using direct keyboard", {})
            
            try:
                original = pyperclip.paste()
            except:
                original = ""
            
            pyperclip.copy(text)
            await asyncio.sleep(0.05)
            send_keys('^v')
            await asyncio.sleep(0.15)
            
            try:
                pyperclip.copy(original)
            except:
                pass
            
            return InputResult(success=True, method_used=InputMethod.SEND_INPUT)
            
        except Exception as e:
            _win_compat_dbg_log("SIMPLE", "error", str(e), {})
            return InputResult(success=False, method_used=InputMethod.SEND_INPUT, error=str(e))
    
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
            # #region agent log H1
            _win_compat_dbg_log("H1", "send_ctrl_v:focus", "Setting foreground window", {"hwnd": hwnd})
            # #endregion
            
            # Use AttachThreadInput trick to bypass Windows focus stealing prevention
            # This works by temporarily attaching our thread to the foreground window's thread
            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            foreground_hwnd = self.user32.GetForegroundWindow()
            foreground_thread = self.user32.GetWindowThreadProcessId(foreground_hwnd, None)
            target_thread = self.user32.GetWindowThreadProcessId(hwnd, None)
            
            attached = False
            try:
                # Attach to foreground thread to get permission to set foreground window
                if current_thread != foreground_thread:
                    attached = bool(self.user32.AttachThreadInput(current_thread, foreground_thread, True))
                
                # Also attach to target thread
                if current_thread != target_thread:
                    self.user32.AttachThreadInput(current_thread, target_thread, True)
                
                # Now we should be able to set foreground window
                self.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY = -1
                result = self.user32.SetForegroundWindow(hwnd)
                
                # Also try BringWindowToTop for good measure
                self.user32.BringWindowToTop(hwnd)
                
            finally:
                # Detach threads
                if attached and current_thread != foreground_thread:
                    self.user32.AttachThreadInput(current_thread, foreground_thread, False)
                if current_thread != target_thread:
                    self.user32.AttachThreadInput(current_thread, target_thread, False)
            
            # #region agent log H1
            _win_compat_dbg_log("H1", "send_ctrl_v:focus_result", "SetForegroundWindow result", {"success": bool(result), "hwnd": hwnd, "attached": attached})
            # #endregion
            
            if not result:
                logger.warning(f"SetForegroundWindow failed for hwnd {hwnd}")
            
            await asyncio.sleep(0.15)  # 等待窗口激活 (增加到 150ms)
            
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
    
    async def _open_clipboard_with_retry(self, hwnd: int, max_retries: int = 5, delay: float = 0.1) -> bool:
        """
        打开剪贴板，带重试机制防止死锁

        Args:
            hwnd: 窗口句柄 (可以为 0)
            max_retries: 最大重试次数
            delay: 每次重试间隔 (秒)

        Returns:
            是否成功打开
        """
        for attempt in range(max_retries):
            if self.user32.OpenClipboard(hwnd):
                return True
            if hwnd != 0 and self.user32.OpenClipboard(0):
                return True
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
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
        
        # CRITICAL: Must set correct types for 64-bit compatibility
        # Without this, handles (pointers) overflow on 64-bit systems
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HANDLE
        kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
        kernel32.GlobalUnlock.restype = wintypes.BOOL

        try:
            # 1. 打开剪贴板 (带重试)
            if not await self._open_clipboard_with_retry(hwnd):
                return InputResult(
                    success=False,
                    method_used=InputMethod.POST_MESSAGE,
                    error="Failed to open clipboard after retries"
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
    
    async def scroll(self, hwnd: int, direction: str, amount: int = 3) -> InputResult:
        """
        滚动操作 - 使用 WM_MOUSEWHEEL
        
        Args:
            hwnd: 窗口句柄
            direction: "up", "down", "left", "right"
            amount: 滚动行数 (每行 120 单位)
        """
        try:
            WM_MOUSEWHEEL = 0x020A
            WM_MOUSEHWHEEL = 0x020E  # 水平滚动
            
            # 计算滚动量 (每行 120 单位)
            WHEEL_DELTA = 120
            
            if direction in ("up", "down"):
                msg = WM_MOUSEWHEEL
                delta = WHEEL_DELTA * amount if direction == "up" else -WHEEL_DELTA * amount
            elif direction in ("left", "right"):
                msg = WM_MOUSEHWHEEL
                delta = -WHEEL_DELTA * amount if direction == "left" else WHEEL_DELTA * amount
            else:
                return InputResult(
                    success=False,
                    method_used=InputMethod.POST_MESSAGE,
                    error=f"Invalid scroll direction: {direction}"
                )
            
            # wParam: HIWORD = wheel delta, LOWORD = key state
            wparam = (delta & 0xFFFF) << 16
            
            # lParam: 鼠标位置 (窗口中心)
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            self.user32.GetClientRect(hwnd, ctypes.byref(rect))
            center_x = (rect.right - rect.left) // 2
            center_y = (rect.bottom - rect.top) // 2
            lparam = (center_y << 16) | (center_x & 0xFFFF)
            
            result = self.user32.PostMessageW(hwnd, msg, wparam, lparam)
            
            if result:
                return InputResult(success=True, method_used=InputMethod.POST_MESSAGE)
            else:
                return InputResult(
                    success=False,
                    method_used=InputMethod.POST_MESSAGE,
                    error="Failed to send scroll message"
                )
                
        except Exception as e:
            return InputResult(
                success=False,
                method_used=InputMethod.POST_MESSAGE,
                error=str(e)
            )
    
    async def hotkey(self, hwnd: int, keys: str) -> InputResult:
        """
        快捷键操作
        
        Args:
            hwnd: 窗口句柄
            keys: 快捷键字符串, 如 "ctrl+c", "alt+tab", "ctrl+shift+s"
        """
        try:
            # 解析快捷键
            key_names = [k.strip().lower() for k in keys.split("+")]
            
            # 虚拟键码映射
            VK_MAP = {
                "ctrl": 0x11, "control": 0x11,
                "alt": 0x12, "menu": 0x12,
                "shift": 0x10,
                "win": 0x5B, "windows": 0x5B,
                "tab": 0x09,
                "enter": 0x0D, "return": 0x0D,
                "esc": 0x1B, "escape": 0x1B,
                "space": 0x20,
                "backspace": 0x08, "back": 0x08,
                "delete": 0x2E, "del": 0x2E,
                "insert": 0x2D, "ins": 0x2D,
                "home": 0x24,
                "end": 0x23,
                "pageup": 0x21, "pgup": 0x21,
                "pagedown": 0x22, "pgdn": 0x22,
                "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
                "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
                "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
                "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
            }
            
            # 字母和数字
            for c in "abcdefghijklmnopqrstuvwxyz":
                VK_MAP[c] = ord(c.upper())
            for c in "0123456789":
                VK_MAP[c] = ord(c)
            
            # 转换为虚拟键码
            vk_codes = []
            for key in key_names:
                if key in VK_MAP:
                    vk_codes.append(VK_MAP[key])
                else:
                    return InputResult(
                        success=False,
                        method_used=InputMethod.POST_MESSAGE,
                        error=f"Unknown key: {key}"
                    )
            
            # 按下所有键
            for vk in vk_codes:
                self.user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
                await asyncio.sleep(0.02)
            
            # 释放所有键 (逆序)
            for vk in reversed(vk_codes):
                self.user32.PostMessageW(hwnd, WM_KEYUP, vk, 0)
                await asyncio.sleep(0.02)
            
            return InputResult(success=True, method_used=InputMethod.POST_MESSAGE)
            
        except Exception as e:
            return InputResult(
                success=False,
                method_used=InputMethod.POST_MESSAGE,
                error=str(e)
            )
    
    async def key_press_by_name(self, hwnd: int, key_name: str) -> InputResult:
        """
        按键操作 (按名称)
        
        Args:
            hwnd: 窗口句柄
            key_name: 按键名称, 如 "enter", "tab", "escape"
        """
        # 使用 hotkey 方法处理单个按键
        return await self.hotkey(hwnd, key_name)
    
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
