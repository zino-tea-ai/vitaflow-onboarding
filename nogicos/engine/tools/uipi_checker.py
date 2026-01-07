# -*- coding: utf-8 -*-
"""
UIPI Checker - UI 权限隔离检测

Windows Vista+ 有 UI 权限隔离 (User Interface Privilege Isolation):
- 低权限进程无法向高权限进程发送消息
- 例如: 普通应用无法控制以管理员运行的程序

完整性级别:
- UNTRUSTED: 0x0000 (最低)
- LOW: 0x1000 (沙盒应用)
- MEDIUM: 0x2000 (标准用户应用)
- MEDIUM_PLUS: 0x2100
- HIGH: 0x3000 (管理员)
- SYSTEM: 0x4000 (系统服务)
"""

import ctypes
from ctypes import wintypes
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

logger = logging.getLogger("nogicos.tools.uipi_checker")


class IntegrityLevel(IntEnum):
    """Windows 完整性级别"""
    UNTRUSTED = 0x0000
    LOW = 0x1000
    MEDIUM = 0x2000
    MEDIUM_PLUS = 0x2100
    HIGH = 0x3000
    SYSTEM = 0x4000
    
    @classmethod
    def from_rid(cls, rid: int) -> 'IntegrityLevel':
        """从 RID 值获取完整性级别"""
        for level in cls:
            if rid >= level.value and rid < level.value + 0x1000:
                return level
        return cls.MEDIUM


@dataclass
class UIAccessibility:
    """UI 可访问性结果"""
    accessible: bool
    our_level: IntegrityLevel
    target_level: IntegrityLevel
    reason: str
    suggestion: str


class UIPIChecker:
    """UIPI 权限检查器"""
    
    def __init__(self):
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        self.advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
        self._setup_functions()
        
        # 缓存当前进程的完整性级别
        self._our_level: Optional[IntegrityLevel] = None
    
    def _setup_functions(self):
        """设置 Windows API 函数签名"""
        # GetWindowThreadProcessId
        self.user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
        ]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        
        # GetCurrentProcessId
        self.kernel32.GetCurrentProcessId.argtypes = []
        self.kernel32.GetCurrentProcessId.restype = wintypes.DWORD
        
        # OpenProcess
        self.kernel32.OpenProcess.argtypes = [
            wintypes.DWORD, wintypes.BOOL, wintypes.DWORD
        ]
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        
        # CloseHandle
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL
        
        # OpenProcessToken
        self.advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
        ]
        self.advapi32.OpenProcessToken.restype = wintypes.BOOL
        
        # GetTokenInformation
        self.advapi32.GetTokenInformation.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
        ]
        self.advapi32.GetTokenInformation.restype = wintypes.BOOL
    
    def check_window_accessibility(self, hwnd: int) -> UIAccessibility:
        """
        检查窗口是否可被操作
        
        Args:
            hwnd: 目标窗口句柄
            
        Returns:
            UIAccessibility 包含可访问性信息
        """
        # 获取目标窗口的进程 ID
        process_id = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        
        # 获取我们的完整性级别
        our_level = self._get_current_integrity_level()
        
        # 获取目标进程的完整性级别
        target_level = self._get_process_integrity_level(process_id.value)
        
        accessible = our_level >= target_level
        
        if accessible:
            return UIAccessibility(
                accessible=True,
                our_level=our_level,
                target_level=target_level,
                reason="",
                suggestion=""
            )
        else:
            return UIAccessibility(
                accessible=False,
                our_level=our_level,
                target_level=target_level,
                reason=f"UIPI: 我们的级别 ({our_level.name}) 低于目标 ({target_level.name})",
                suggestion="需要以管理员权限运行 NogicOS，或降低目标应用的权限级别"
            )
    
    def _get_current_integrity_level(self) -> IntegrityLevel:
        """获取当前进程的完整性级别"""
        if self._our_level is not None:
            return self._our_level
        
        self._our_level = self._get_process_integrity_level(
            self.kernel32.GetCurrentProcessId()
        )
        return self._our_level
    
    def _get_process_integrity_level(self, process_id: int) -> IntegrityLevel:
        """获取指定进程的完整性级别"""
        PROCESS_QUERY_INFORMATION = 0x0400
        TOKEN_QUERY = 0x0008
        TokenIntegrityLevel = 25
        
        try:
            # 打开进程
            process = self.kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION, False, process_id
            )
            if not process:
                logger.debug(f"Cannot open process {process_id}, assuming MEDIUM")
                return IntegrityLevel.MEDIUM
            
            try:
                # 打开进程令牌
                token = wintypes.HANDLE()
                if not self.advapi32.OpenProcessToken(
                    process, TOKEN_QUERY, ctypes.byref(token)
                ):
                    logger.debug(f"Cannot open token for process {process_id}")
                    return IntegrityLevel.MEDIUM
                
                try:
                    # 获取完整性级别所需的缓冲区大小
                    info_size = wintypes.DWORD()
                    self.advapi32.GetTokenInformation(
                        token, TokenIntegrityLevel, None, 0, ctypes.byref(info_size)
                    )
                    
                    if info_size.value == 0:
                        return IntegrityLevel.MEDIUM
                    
                    # 分配缓冲区并获取信息
                    buffer = ctypes.create_string_buffer(info_size.value)
                    if self.advapi32.GetTokenInformation(
                        token, TokenIntegrityLevel, buffer, 
                        info_size, ctypes.byref(info_size)
                    ):
                        # 解析 TOKEN_MANDATORY_LABEL 结构
                        # 结构的第一个成员是 SID_AND_ATTRIBUTES，其 Sid 指针在偏移 0
                        sid_ptr = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p)).contents
                        
                        if sid_ptr:
                            # 获取 SID 的子权限数量
                            sub_auth_count_ptr = self.advapi32.GetSidSubAuthorityCount(sid_ptr)
                            if sub_auth_count_ptr:
                                count = ctypes.cast(
                                    sub_auth_count_ptr, 
                                    ctypes.POINTER(ctypes.c_ubyte)
                                ).contents.value
                                
                                if count > 0:
                                    # 获取最后一个子权限 (RID)
                                    rid_ptr = self.advapi32.GetSidSubAuthority(
                                        sid_ptr, count - 1
                                    )
                                    if rid_ptr:
                                        rid = ctypes.cast(
                                            rid_ptr, 
                                            ctypes.POINTER(wintypes.DWORD)
                                        ).contents.value
                                        return IntegrityLevel.from_rid(rid)
                    
                    return IntegrityLevel.MEDIUM
                    
                finally:
                    self.kernel32.CloseHandle(token)
            finally:
                self.kernel32.CloseHandle(process)
                
        except Exception as e:
            logger.debug(f"Error getting integrity level for process {process_id}: {e}")
            return IntegrityLevel.MEDIUM
    
    def is_elevated(self) -> bool:
        """检查当前进程是否以管理员权限运行"""
        return self._get_current_integrity_level() >= IntegrityLevel.HIGH
    
    def can_control_window(self, hwnd: int) -> bool:
        """快速检查是否可以控制指定窗口"""
        return self.check_window_accessibility(hwnd).accessible


# 全局单例
_global_uipi_checker: Optional[UIPIChecker] = None


def get_uipi_checker() -> UIPIChecker:
    """获取全局 UIPI 检查器"""
    global _global_uipi_checker
    if _global_uipi_checker is None:
        _global_uipi_checker = UIPIChecker()
    return _global_uipi_checker


# 便捷函数
def can_control_window(hwnd: int) -> bool:
    """快速检查是否可以控制窗口"""
    return get_uipi_checker().can_control_window(hwnd)


# 导出
__all__ = [
    'IntegrityLevel',
    'UIAccessibility',
    'UIPIChecker',
    'get_uipi_checker',
    'can_control_window',
]
