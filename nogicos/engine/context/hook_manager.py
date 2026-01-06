# -*- coding: utf-8 -*-
"""
Hook Manager - Hook 管理器

管理所有 Hook 的生命周期：
- 连接/断开
- 状态同步到 Context Store
- WebSocket 事件推送
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .store import (
    ContextStore, 
    get_context_store,
    HookType, 
    HookStatus, 
    HookState,
    BrowserContext,
    DesktopContext,
    FileContext,
    AppContext,
    AppType,
)
from .hooks import BaseHook, HookConfig, BrowserHook, DesktopHook, FileHook
from .hooks.desktop_hook import get_all_windows, BROWSER_PROCESSES

logger = logging.getLogger(__name__)


@dataclass
class ConnectionTarget:
    """连接目标"""
    type: str           # browser, desktop, file
    target: str = ""    # 具体目标（如 chrome, 目录路径）
    config: Optional[HookConfig] = None


class HookManager:
    """
    Hook 管理器
    
    统一管理所有 Hook 的生命周期
    """
    
    # Hook 类型到类的映射
    HOOK_CLASSES = {
        "browser": BrowserHook,
        "desktop": DesktopHook,
        "file": FileHook,
    }
    
    def __init__(self, context_store: Optional[ContextStore] = None):
        """
        初始化 Hook Manager
        
        Args:
            context_store: Context Store 实例，None 则使用单例
        """
        self._store = context_store or get_context_store()
        self._hooks: Dict[str, BaseHook] = {}
        self._lock = asyncio.Lock()
        
        # 事件回调（用于 WebSocket 推送）
        self._on_state_change: Optional[Callable[[str, Dict], None]] = None
        
        logger.info("[HookManager] Initialized")
    
    def set_state_change_callback(self, callback: Callable[[str, Dict], None]):
        """
        设置状态变更回调
        
        用于 WebSocket 推送状态变更到前端
        
        Args:
            callback: 回调函数 (hook_id, state_dict) -> None
        """
        self._on_state_change = callback
    
    async def connect(self, target: ConnectionTarget) -> bool:
        """
        连接到目标
        
        Args:
            target: 连接目标配置
            
        Returns:
            是否成功连接
        """
        async with self._lock:
            hook_id = f"{target.type}_{target.target}" if target.target else target.type
            
            # 检查是否已连接
            if hook_id in self._hooks:
                existing_hook = self._hooks[hook_id]
                if existing_hook.is_running:
                    logger.warning(f"[HookManager] Hook already connected: {hook_id}")
                    return True
            
            # 创建 Hook 实例
            hook_class = self.HOOK_CLASSES.get(target.type)
            if not hook_class:
                logger.error(f"[HookManager] Unknown hook type: {target.type}")
                return False
            
            hook = hook_class(
                hook_id=hook_id,
                config=target.config or HookConfig(),
            )
            
            # 设置回调
            hook.set_callbacks(
                on_state_change=lambda state: self._handle_state_change(hook_id, state),
                on_context_update=lambda ctx: self._handle_context_update(hook_id, ctx),
            )
            
            # 启动 Hook
            success = await hook.start(target.target)
            
            if success:
                self._hooks[hook_id] = hook
                logger.info(f"[HookManager] Connected: {hook_id}")
                return True
            else:
                logger.error(f"[HookManager] Failed to connect: {hook_id}")
                return False
    
    async def disconnect(self, hook_id: str) -> bool:
        """
        断开连接
        
        Args:
            hook_id: Hook ID
            
        Returns:
            是否成功断开
        """
        async with self._lock:
            if hook_id not in self._hooks:
                logger.warning(f"[HookManager] Hook not found: {hook_id}")
                return True
            
            hook = self._hooks[hook_id]
            success = await hook.stop()
            
            if success:
                del self._hooks[hook_id]
                self._store.remove_hook(hook_id)
                logger.info(f"[HookManager] Disconnected: {hook_id}")
            
            return success
    
    async def disconnect_all(self) -> bool:
        """断开所有连接"""
        async with self._lock:
            results = []
            for hook_id in list(self._hooks.keys()):
                hook = self._hooks[hook_id]
                success = await hook.stop()
                results.append(success)
                if success:
                    del self._hooks[hook_id]
                    self._store.remove_hook(hook_id)
            
            logger.info(f"[HookManager] Disconnected all hooks")
            return all(results)
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取所有 Hook 状态
        
        Returns:
            状态字典
        """
        status = {
            "hooks": {},
            "available_types": list(self.HOOK_CLASSES.keys()),
        }
        
        for hook_id, hook in self._hooks.items():
            status["hooks"][hook_id] = {
                "type": hook.hook_type.value,
                "status": hook.state.status.value,
                "target": hook.state.target,
                "connected_at": hook.state.connected_at,
                "context": hook.state.context.__dict__ if hook.state.context else None,
            }
        
        return status
    
    def get_hook(self, hook_id: str) -> Optional[BaseHook]:
        """获取 Hook 实例"""
        return self._hooks.get(hook_id)
    
    def is_connected(self, hook_type: str) -> bool:
        """检查某类型的 Hook 是否已连接"""
        # 【修复 #15】不需要加锁因为只是读取，但要确保遍历安全
        for hook_id, hook in list(self._hooks.items()):
            if hook.hook_type.value == hook_type and hook.is_running:
                return True
        return False
    
    def _handle_state_change(self, hook_id: str, state: HookState):
        """处理状态变更"""
        # 同步到 Context Store
        self._store.set_hook_state(hook_id, state)

        # 【修复 #16】回调异常不阻塞主流程
        if self._on_state_change:
            try:
                self._on_state_change(hook_id, state.to_dict())
            except Exception as e:
                logger.error(f"[HookManager] State change callback error: {e}")
                # 继续执行，不阻塞
    
    def _handle_context_update(self, hook_id: str, context: Any):
        """处理上下文更新"""
        # 同步到 Context Store
        self._store.update_context(hook_id, context)
        
        # 触发回调（WebSocket 推送）
        if self._on_state_change:
            try:
                hook = self._hooks.get(hook_id)
                if hook:
                    self._on_state_change(hook_id, hook.state.to_dict())
            except Exception as e:
                logger.error(f"[HookManager] Context update callback error: {e}")
    
    # ============== 便捷方法 ==============
    
    async def connect_browser(self, browser: Optional[str] = None, config: Optional[HookConfig] = None) -> bool:
        """
        连接浏览器
        
        Args:
            browser: 浏览器类型（chrome, firefox, edge），None 自动检测
            config: Hook 配置
        """
        return await self.connect(ConnectionTarget(
            type="browser",
            target=browser or "",
            config=config,
        ))
    
    async def connect_desktop(self, config: Optional[HookConfig] = None) -> bool:
        """连接桌面感知"""
        return await self.connect(ConnectionTarget(
            type="desktop",
            target="",
            config=config,
        ))
    
    async def connect_file(self, directories: Optional[str] = None, config: Optional[HookConfig] = None) -> bool:
        """
        连接文件监听
        
        Args:
            directories: 要监听的目录，多个用分号分隔
            config: Hook 配置
        """
        return await self.connect(ConnectionTarget(
            type="file",
            target=directories or "",
            config=config,
        ))
    
    async def get_browser_context(self) -> Optional[BrowserContext]:
        """获取浏览器上下文"""
        for hook_id, hook in self._hooks.items():
            if hook.hook_type == HookType.BROWSER and hook.state.context:
                return hook.state.context
        return None
    
    async def get_desktop_context(self) -> Optional[DesktopContext]:
        """获取桌面上下文"""
        for hook_id, hook in self._hooks.items():
            if hook.hook_type == HookType.DESKTOP and hook.state.context:
                return hook.state.context
        return None
    
    async def get_file_context(self) -> Optional[FileContext]:
        """获取文件上下文"""
        for hook_id, hook in self._hooks.items():
            if hook.hook_type == HookType.FILE and hook.state.context:
                return hook.state.context
        return None
    
    # ============== 通用应用连接（新版接口） ==============
    
    async def connect_to_window(self, hwnd: int, window_title: str = "") -> Optional[AppContext]:
        """
        连接到指定窗口（通用应用连接器）
        
        这是新版的统一接口，可以连接任意应用窗口。
        根据应用类型自动选择合适的 Hook 策略。
        
        Args:
            hwnd: 窗口句柄
            window_title: 窗口标题（可选，用于显示）
            
        Returns:
            AppContext 或 None
        """
        # 从窗口列表中查找窗口信息
        windows = get_all_windows()
        target_window = None
        for w in windows:
            if w.hwnd == hwnd:
                target_window = w
                break
        
        if not target_window:
            logger.warning(f"[HookManager] Window not found: HWND={hwnd}")
            return None
        
        # 确定应用类型
        app_name_lower = target_window.app_name.lower()
        if app_name_lower in BROWSER_PROCESSES:
            app_type = AppType.BROWSER.value
            hook_type = "browser"
        elif app_name_lower in ["code.exe", "cursor.exe"]:
            app_type = AppType.IDE.value
            hook_type = "desktop"
        elif app_name_lower in ["figma.exe", "sketch.exe"]:
            app_type = AppType.DESIGN.value
            hook_type = "desktop"
        else:
            app_type = AppType.OTHER.value
            hook_type = "desktop"
        
        # 连接对应的 Hook
        success = await self.connect(ConnectionTarget(
            type=hook_type,
            target=target_window.app_name,
        ))
        
        if not success:
            return None
        
        # 创建通用 AppContext
        app_context = AppContext(
            hwnd=target_window.hwnd,
            title=target_window.title,
            app_name=target_window.app_name,
            app_display_name=target_window.app_display_name,
            app_type=app_type,
            x=target_window.x,
            y=target_window.y,
            width=target_window.width,
            height=target_window.height,
        )
        
        # 如果是浏览器，尝试获取更多信息
        if app_type == AppType.BROWSER.value:
            browser_hook = self.get_hook(hook_type)
            if browser_hook and browser_hook.state.context:
                browser_ctx = browser_hook.state.context
                if hasattr(browser_ctx, 'url'):
                    app_context.url = browser_ctx.url
                if hasattr(browser_ctx, 'tab_count'):
                    app_context.tab_count = browser_ctx.tab_count
        
        logger.info(f"[HookManager] Connected to window: {target_window.title} ({app_type})")
        return app_context
    
    def get_connected_windows(self) -> List[AppContext]:
        """
        获取所有已连接的窗口（通用接口）
        
        Returns:
            AppContext 列表
        """
        result = []
        
        for hook_id, hook in self._hooks.items():
            if hook.is_running and hook.state.context:
                ctx = hook.state.context
                
                # 转换为 AppContext
                if isinstance(ctx, BrowserContext):
                    result.append(AppContext(
                        hwnd=ctx.hwnd if hasattr(ctx, 'hwnd') else 0,
                        title=ctx.title,
                        app_name=ctx.app,
                        app_display_name=ctx.app,
                        app_type=AppType.BROWSER.value,
                        url=ctx.url,
                        tab_count=ctx.tab_count,
                    ))
                elif isinstance(ctx, DesktopContext):
                    result.append(AppContext(
                        hwnd=0,
                        title=ctx.active_window,
                        app_name=ctx.active_app,
                        app_display_name=ctx.active_app,
                        app_type=AppType.OTHER.value,
                    ))
        
        return result


# 全局单例
_hook_manager: Optional[HookManager] = None
_manager_lock: Optional[asyncio.Lock] = None


def _get_manager_lock() -> asyncio.Lock:
    """延迟创建 Lock，确保在事件循环中创建"""
    global _manager_lock
    if _manager_lock is None:
        _manager_lock = asyncio.Lock()
    return _manager_lock


async def get_hook_manager() -> HookManager:
    """获取 Hook Manager 单例"""
    global _hook_manager
    lock = _get_manager_lock()
    async with lock:
        if _hook_manager is None:
            _hook_manager = HookManager()
        return _hook_manager

