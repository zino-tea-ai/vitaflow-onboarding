# -*- coding: utf-8 -*-
"""
Context Store - 上下文存储系统

存储 Hook 系统捕获的上下文信息：
- 当前状态（内存）：实时的连接状态和上下文
- 历史记录（SQLite）：持久化的事件历史
"""

import asyncio
import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class HookType(Enum):
    """Hook 类型"""
    BROWSER = "browser"
    DESKTOP = "desktop"
    FILE = "file"
    APP = "app"  # 通用应用 Hook（新增）


class AppType(Enum):
    """应用类型（用于通用 App Hook）"""
    BROWSER = "browser"     # 浏览器类应用
    IDE = "ide"             # 开发工具
    DESIGN = "design"       # 设计工具
    COMMUNICATION = "communication"  # 通讯工具
    PRODUCTIVITY = "productivity"    # 办公工具
    MEDIA = "media"         # 媒体工具
    OTHER = "other"         # 其他


class HookStatus(Enum):
    """Hook 连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class BrowserContext:
    """浏览器上下文"""
    app: str = ""                  # Chrome, Firefox, Edge, etc.
    url: str = ""                  # 当前 URL
    title: str = ""                # 页面标题（从窗口标题解析）
    window_title: str = ""         # 完整窗口标题（用于 Overlay 精确匹配）
    hwnd: int = 0                  # 窗口句柄（用于 Overlay）
    tab_count: int = 0             # tab 数量
    tabs: List[Dict[str, str]] = field(default_factory=list)  # [{url, title}, ...]
    page_summary: str = ""         # 页面内容摘要
    screenshot_path: Optional[str] = None  # 最近截图路径
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DesktopContext:
    """桌面上下文"""
    hwnd: int = 0                  # 窗口句柄
    active_app: str = ""           # 当前活跃应用（进程名如 chrome.exe）
    active_window: str = ""        # 当前活跃窗口标题
    window_list: List[Dict[str, str]] = field(default_factory=list)  # 窗口列表
    screenshot_path: Optional[str] = None
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class FileContext:
    """文件上下文"""
    watched_dirs: List[str] = field(default_factory=list)   # 监听的目录
    recent_files: List[str] = field(default_factory=list)   # 最近修改的文件
    clipboard: str = ""            # 剪贴板内容
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AppContext:
    """
    通用应用上下文（新版统一接口）
    
    用于任意应用的连接，根据 app_type 提供不同级别的上下文信息
    """
    # 基本信息（所有应用都有）
    hwnd: int = 0                  # 窗口句柄
    title: str = ""                # 窗口标题
    app_name: str = ""             # 进程名（如 chrome.exe）
    app_display_name: str = ""     # 显示名称（如 Google Chrome）
    app_type: str = "other"        # 应用类型（browser, ide, design, etc.）
    
    # 窗口信息
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    
    # 浏览器特有（app_type == browser）
    url: str = ""                  # 当前 URL
    tab_count: int = 0             # Tab 数量
    
    # IDE 特有（app_type == ide）
    file_path: str = ""            # 当前文件路径
    project_path: str = ""         # 项目路径
    
    # 截图/OCR（通用）
    screenshot_path: Optional[str] = None
    ocr_text: Optional[str] = None
    
    # 元数据
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HookState:
    """单个 Hook 的状态"""
    type: HookType
    status: HookStatus = HookStatus.DISCONNECTED
    target: str = ""               # 目标应用/目录
    context: Optional[Any] = None  # BrowserContext / DesktopContext / FileContext
    error: Optional[str] = None
    connected_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value,
            "status": self.status.value,
            "target": self.target,
            "context": asdict(self.context) if self.context else None,
            "error": self.error,
            "connected_at": self.connected_at,
        }


@dataclass
class ContextEvent:
    """上下文事件（用于历史记录）"""
    id: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    hook_type: str = ""
    event_type: str = ""           # connected, disconnected, updated, error
    data: Dict[str, Any] = field(default_factory=dict)


class ContextStore:
    """
    上下文存储
    
    - 当前状态：内存中的实时状态
    - 历史记录：SQLite 持久化
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化 Context Store
        
        Args:
            db_path: SQLite 数据库路径，None 则使用默认路径
        """
        self._lock = threading.Lock()
        
        # 当前状态（内存）
        self._hooks: Dict[str, HookState] = {}
        
        # 事件监听器
        self._listeners: List[Callable[[str, HookState], None]] = []
        
        # 数据库路径
        if db_path is None:
            db_dir = Path(__file__).parent.parent.parent / "data"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(db_dir / "context_history.db")
        
        self._db_path = db_path
        self._init_db()
        
        logger.info(f"[ContextStore] Initialized, db: {db_path}")
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS context_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    hook_type TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON context_events(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_hook_type 
                ON context_events(hook_type)
            """)
            conn.commit()
    
    # ============== 状态管理 ==============
    
    def get_hook_state(self, hook_id: str) -> Optional[HookState]:
        """获取 Hook 状态"""
        with self._lock:
            return self._hooks.get(hook_id)
    
    def get_all_hooks(self) -> Dict[str, HookState]:
        """获取所有 Hook 状态"""
        with self._lock:
            return dict(self._hooks)
    
    def get_connected_hooks(self) -> Dict[str, HookState]:
        """获取所有已连接的 Hook"""
        with self._lock:
            return {
                k: v for k, v in self._hooks.items() 
                if v.status == HookStatus.CONNECTED
            }
    
    def set_hook_state(self, hook_id: str, state: HookState):
        """设置 Hook 状态"""
        with self._lock:
            old_state = self._hooks.get(hook_id)
            self._hooks[hook_id] = state
        
        # 通知监听器
        self._notify_listeners(hook_id, state)
        
        # 记录事件
        if old_state is None or old_state.status != state.status:
            self.record_event(ContextEvent(
                hook_type=state.type.value,
                event_type=state.status.value,
                data=state.to_dict(),
            ))
    
    def update_context(self, hook_id: str, context: Any):
        """更新 Hook 的上下文"""
        state = None
        with self._lock:
            # 【修复 #17】锁内二次检查，确保状态一致性
            if hook_id in self._hooks:
                self._hooks[hook_id].context = context
                state = self._hooks[hook_id]

        if state is not None:
            self._notify_listeners(hook_id, state)
    
    def remove_hook(self, hook_id: str):
        """移除 Hook"""
        with self._lock:
            if hook_id in self._hooks:
                state = self._hooks.pop(hook_id)
                self.record_event(ContextEvent(
                    hook_type=state.type.value,
                    event_type="removed",
                    data={"hook_id": hook_id},
                ))
    
    # ============== 事件监听 ==============
    
    def add_listener(self, callback: Callable[[str, HookState], None]):
        """添加状态变更监听器"""
        self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[str, HookState], None]):
        """移除监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self, hook_id: str, state: HookState):
        """通知所有监听器"""
        for listener in self._listeners:
            try:
                listener(hook_id, state)
            except Exception as e:
                logger.error(f"[ContextStore] Listener error: {e}")
    
    # ============== 历史记录 ==============
    
    def record_event(self, event: ContextEvent):
        """记录事件到历史"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO context_events (timestamp, hook_type, event_type, data) VALUES (?, ?, ?, ?)",
                    (event.timestamp, event.hook_type, event.event_type, json.dumps(event.data))
                )
                conn.commit()
        except Exception as e:
            logger.error(f"[ContextStore] Failed to record event: {e}")
    
    def get_recent_events(self, minutes: int = 30, hook_type: Optional[str] = None) -> List[ContextEvent]:
        """获取最近 N 分钟的历史事件"""
        try:
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
            
            with sqlite3.connect(self._db_path) as conn:
                if hook_type:
                    cursor = conn.execute(
                        "SELECT id, timestamp, hook_type, event_type, data FROM context_events "
                        "WHERE timestamp > ? AND hook_type = ? ORDER BY timestamp DESC",
                        (cutoff, hook_type)
                    )
                else:
                    cursor = conn.execute(
                        "SELECT id, timestamp, hook_type, event_type, data FROM context_events "
                        "WHERE timestamp > ? ORDER BY timestamp DESC",
                        (cutoff,)
                    )
                
                events = []
                for row in cursor.fetchall():
                    events.append(ContextEvent(
                        id=row[0],
                        timestamp=row[1],
                        hook_type=row[2],
                        event_type=row[3],
                        data=json.loads(row[4]),
                    ))
                return events
        except Exception as e:
            logger.error(f"[ContextStore] Failed to get recent events: {e}")
            return []
    
    # ============== Agent 接口 ==============
    
    def get_context_for_agent(self) -> Dict[str, Any]:
        """
        获取当前上下文（供 Agent 使用）
        
        Returns:
            包含所有已连接 Hook 上下文的字典
        """
        connected = self.get_connected_hooks()
        
        context = {
            "connected_hooks": list(connected.keys()),
            "browser": None,
            "desktop": None,
            "files": None,
            # 新增：支持多窗口
            "connected_windows": [],  # List[AppContext]
        }
        
        for hook_id, state in connected.items():
            if state.type == HookType.BROWSER and state.context:
                context["browser"] = asdict(state.context)
            elif state.type == HookType.DESKTOP and state.context:
                context["desktop"] = asdict(state.context)
            elif state.type == HookType.FILE and state.context:
                context["files"] = asdict(state.context)
            
            # 收集所有带 hwnd 的上下文
            if state.context and hasattr(state.context, 'hwnd') and state.context.hwnd:
                ctx_dict = asdict(state.context) if hasattr(state.context, '__dataclass_fields__') else {}
                if ctx_dict:
                    ctx_dict['hook_id'] = hook_id
                    context["connected_windows"].append(ctx_dict)
        
        return context
    
    def format_context_prompt(self) -> str:
        """
        格式化上下文为 prompt 字符串
        
        Returns:
            可直接注入到 system prompt 的上下文描述
        """
        ctx = self.get_context_for_agent()
        
        if not ctx["connected_hooks"]:
            return ""
        
        lines = ["[CONNECTED TARGETS - You MUST use these windows, do NOT enumerate windows yourself:]"]
        
        # 新增：显示所有连接的窗口
        connected_windows = ctx.get("connected_windows", [])
        if connected_windows:
            lines.append(f"\n## Connected Windows ({len(connected_windows)} total)")
            for i, win in enumerate(connected_windows, 1):
                hwnd = win.get('hwnd', 0)
                title = win.get('title', '') or win.get('active_window', '')
                app = win.get('app_name', '') or win.get('app_display_name', '') or win.get('active_app', '')
                app_type = win.get('app_type', 'unknown')
                
                lines.append(f"\n### Window {i}: {app}")
                lines.append(f"- **HWND: {hwnd}** ← Target window handle")
                lines.append(f"- Title: {title}")
                lines.append(f"- Type: {app_type}")
                
                # 浏览器特有信息
                if win.get('url'):
                    lines.append(f"- URL: {win['url']}")
                if win.get('tab_count'):
                    lines.append(f"- Tabs: {win['tab_count']}")
            
            lines.append(f"\n⚠️ IMPORTANT: User has connected to {len(connected_windows)} specific window(s).")
            lines.append(f"   Do NOT call list_windows or find_window to find other windows.")
            lines.append(f"   Always use the HWND values above for window_screenshot, window_click, etc.")
        
        # 兼容旧格式
        elif ctx["browser"]:
            b = ctx["browser"]
            hwnd = b.get('hwnd', 0)
            lines.append(f"\n## Browser Target ({b['app']})")
            lines.append(f"- **HWND: {hwnd}** ← Use this for all browser operations")
            lines.append(f"- Active URL: {b['url']}")
            lines.append(f"- Page Title: {b['title']}")
            if b.get('tabs'):
                lines.append(f"- Open Tabs ({len(b['tabs'])}):")
                for i, tab in enumerate(b['tabs'][:5]):  # 最多显示 5 个
                    lines.append(f"  {i+1}. {tab.get('title', 'Unknown')} - {tab.get('url', '')}")
                if len(b['tabs']) > 5:
                    lines.append(f"  ... and {len(b['tabs']) - 5} more tabs")
        
        elif ctx["desktop"]:
            d = ctx["desktop"]
            hwnd = d.get('hwnd', 0)
            lines.append(f"\n## Desktop Target")
            lines.append(f"- **HWND: {hwnd}** ← Use this for all desktop operations (click, type, screenshot)")
            lines.append(f"- App: {d['active_app']}")
            lines.append(f"- Window Title: {d['active_window']}")
            lines.append(f"\n⚠️ IMPORTANT: User has connected to this specific window.")
            lines.append(f"   Do NOT call list_windows or find_window to find another window.")
            lines.append(f"   Always use hwnd={hwnd} for window_screenshot, window_click, etc.")
        
        if ctx["files"]:
            f = ctx["files"]
            lines.append(f"\n## Files")
            if f.get('recent_files'):
                lines.append("- Recent Files:")
                for path in f['recent_files'][:5]:
                    lines.append(f"  - {path}")
            if f.get('clipboard'):
                clip = f['clipboard'][:200] + "..." if len(f['clipboard']) > 200 else f['clipboard']
                lines.append(f"- Clipboard: {clip}")
        
        return "\n".join(lines)


# 全局单例
_context_store: Optional[ContextStore] = None
_store_lock = threading.Lock()


def get_context_store() -> ContextStore:
    """获取 Context Store 单例"""
    global _context_store
    with _store_lock:
        if _context_store is None:
            _context_store = ContextStore()
        return _context_store

