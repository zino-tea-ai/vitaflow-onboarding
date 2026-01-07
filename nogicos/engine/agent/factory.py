"""
NogicOS AgentFactory - 代理工厂
================================

根据应用类型创建对应的 AppAgent。

参考:
- UFO AgentFactory
- 工厂模式
"""

from typing import Optional, Dict, Type, TYPE_CHECKING
import logging

from .app_agent import (
    AppAgent, AppAgentConfig, AppType,
    BrowserAppAgent, DesktopAppAgent, IDEAppAgent,
)
from .types import HWND

if TYPE_CHECKING:
    from .host_agent import HostAgent

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Agent 工厂
    
    负责根据应用类型创建对应的 AppAgent 实例。
    支持：
    1. 内置 Agent 类型
    2. 自定义 Agent 注册
    3. 窗口类型自动检测
    
    使用示例:
    ```python
    factory = AgentFactory()
    
    # 创建浏览器 Agent
    browser_agent = factory.create(hwnd=12345, app_type="browser")
    
    # 注册自定义 Agent
    factory.register("custom_app", MyCustomAgent)
    custom_agent = factory.create(hwnd=67890, app_type="custom_app")
    ```
    """
    
    # 内置 Agent 类型映射
    _BUILTIN_AGENTS: Dict[str, Type[AppAgent]] = {
        "browser": BrowserAppAgent,
        "desktop": DesktopAppAgent,
        "ide": IDEAppAgent,
    }
    
    # 窗口类名 -> 应用类型映射（用于自动检测）
    _WINDOW_CLASS_MAP: Dict[str, str] = {
        # 浏览器
        "Chrome_WidgetWin_1": "browser",
        "MozillaWindowClass": "browser",
        "IEFrame": "browser",
        "ApplicationFrameWindow": "browser",  # Edge
        
        # IDE
        "SunAwtFrame": "ide",  # IntelliJ
        "Notepad++": "ide",
        "VSCodeMainWindow": "ide",  # VS Code (Electron)
        
        # Office
        "OpusApp": "office",  # Word
        "XLMAIN": "office",   # Excel
        
        # 终端
        "ConsoleWindowClass": "terminal",
        "CASCADIA_HOSTING_WINDOW_CLASS": "terminal",  # Windows Terminal
    }
    
    def __init__(self):
        """初始化工厂"""
        self._custom_agents: Dict[str, Type[AppAgent]] = {}
        self._instances: Dict[HWND, AppAgent] = {}  # 实例缓存
    
    def create(
        self,
        hwnd: HWND,
        app_type: Optional[str] = None,
        host: Optional["HostAgent"] = None,
        config: Optional[AppAgentConfig] = None,
        **kwargs,
    ) -> AppAgent:
        """
        创建 AppAgent
        
        Args:
            hwnd: 窗口句柄
            app_type: 应用类型（None 时自动检测）
            host: 父级 HostAgent
            config: Agent 配置
            **kwargs: 额外参数
            
        Returns:
            AppAgent 实例
            
        Raises:
            ValueError: 不支持的应用类型
        """
        # 检查缓存
        if hwnd in self._instances:
            logger.debug(f"Returning cached agent for hwnd={hwnd}")
            return self._instances[hwnd]
        
        # 自动检测应用类型
        if app_type is None:
            app_type = self._detect_app_type(hwnd)
            logger.info(f"Auto-detected app type for hwnd={hwnd}: {app_type}")
        
        # 查找 Agent 类
        agent_class = self._get_agent_class(app_type)
        if agent_class is None:
            raise ValueError(f"Unsupported app type: {app_type}")
        
        # 创建实例
        agent = agent_class(
            hwnd=hwnd,
            host=host,
            config=config,
            **kwargs,
        )
        
        # 缓存
        self._instances[hwnd] = agent
        
        logger.info(f"Created {agent_class.__name__} for hwnd={hwnd}")
        return agent
    
    def create_from_type(
        self,
        hwnd: HWND,
        app_type: AppType,
        host: Optional["HostAgent"] = None,
        config: Optional[AppAgentConfig] = None,
        **kwargs,
    ) -> AppAgent:
        """
        根据 AppType 枚举创建
        
        Args:
            hwnd: 窗口句柄
            app_type: AppType 枚举
            host: 父级 HostAgent
            config: Agent 配置
            
        Returns:
            AppAgent 实例
        """
        return self.create(
            hwnd=hwnd,
            app_type=app_type.value,
            host=host,
            config=config,
            **kwargs,
        )
    
    def register(self, app_type: str, agent_class: Type[AppAgent]):
        """
        注册自定义 Agent 类型
        
        Args:
            app_type: 应用类型名称
            agent_class: Agent 类
        """
        if not issubclass(agent_class, AppAgent):
            raise TypeError(f"{agent_class} must be a subclass of AppAgent")
        
        self._custom_agents[app_type] = agent_class
        logger.info(f"Registered custom agent: {app_type} -> {agent_class.__name__}")
    
    def unregister(self, app_type: str):
        """注销自定义 Agent 类型"""
        self._custom_agents.pop(app_type, None)
    
    def get_cached(self, hwnd: HWND) -> Optional[AppAgent]:
        """获取缓存的 Agent"""
        return self._instances.get(hwnd)
    
    def remove_cached(self, hwnd: HWND):
        """移除缓存的 Agent"""
        self._instances.pop(hwnd, None)
    
    def clear_cache(self):
        """清空缓存"""
        self._instances.clear()
    
    def _get_agent_class(self, app_type: str) -> Optional[Type[AppAgent]]:
        """获取 Agent 类"""
        # 先查自定义
        if app_type in self._custom_agents:
            return self._custom_agents[app_type]
        
        # 再查内置
        if app_type in self._BUILTIN_AGENTS:
            return self._BUILTIN_AGENTS[app_type]
        
        # 默认使用 Desktop
        if app_type in ["custom", "unknown"]:
            return DesktopAppAgent
        
        return None
    
    def _detect_app_type(self, hwnd: HWND) -> str:
        """
        自动检测应用类型
        
        使用 GetClassName 获取窗口类名，然后匹配到应用类型
        """
        import ctypes
        from ctypes import wintypes
        
        try:
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            
            # 获取窗口类名
            class_buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buffer, 256)
            class_name = class_buffer.value
            
            # 获取窗口标题
            title_length = user32.GetWindowTextLengthW(hwnd) + 1
            title_buffer = ctypes.create_unicode_buffer(title_length)
            user32.GetWindowTextW(hwnd, title_buffer, title_length)
            title = title_buffer.value.lower()
            
            logger.debug(f"Window detection: hwnd={hwnd}, class={class_name}, title={title[:50]}")
            
            # 1. 精确类名匹配
            if class_name in self._WINDOW_CLASS_MAP:
                return self._WINDOW_CLASS_MAP[class_name]
            
            # 2. 浏览器检测 (Electron 应用也使用 Chrome_WidgetWin_1)
            browser_classes = [
                "Chrome_WidgetWin_1",  # Chrome, Edge, Electron apps
                "MozillaWindowClass",  # Firefox
                "IEFrame",             # IE
                "ApplicationFrameWindow",  # Edge UWP
            ]
            if class_name in browser_classes:
                return "browser"
            
            # 3. 标题关键词检测
            browser_keywords = ["chrome", "firefox", "edge", "safari", "opera", "brave", "vivaldi"]
            for keyword in browser_keywords:
                if keyword in title:
                    return "browser"
            
            ide_keywords = ["visual studio", "vscode", "code", "pycharm", "intellij", "webstorm", "sublime", "atom", "notepad++"]
            for keyword in ide_keywords:
                if keyword in title:
                    return "ide"
            
            terminal_keywords = ["terminal", "cmd", "powershell", "bash", "命令提示符", "windows terminal"]
            for keyword in terminal_keywords:
                if keyword in title:
                    return "terminal"
            
            # 4. 进程名检测 (可选，更准确但更慢)
            try:
                process_id = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
                
                # 获取进程名需要更多权限，这里简化处理
                # 可以扩展为使用 psutil 或 CreateToolhelp32Snapshot
            except Exception:
                pass
            
            # 5. 默认返回 desktop
            return "desktop"
            
        except Exception as e:
            logger.warning(f"Failed to detect app type for hwnd={hwnd}: {e}")
            return "desktop"
    
    def get_supported_types(self) -> list:
        """获取支持的应用类型"""
        builtin = list(self._BUILTIN_AGENTS.keys())
        custom = list(self._custom_agents.keys())
        return builtin + custom
    
    def __repr__(self) -> str:
        return (
            f"AgentFactory(builtin={len(self._BUILTIN_AGENTS)}, "
            f"custom={len(self._custom_agents)}, "
            f"cached={len(self._instances)})"
        )


# ========== 全局单例 ==========

_default_factory: Optional[AgentFactory] = None


def get_agent_factory() -> AgentFactory:
    """获取全局 Agent 工厂（单例）"""
    global _default_factory
    if _default_factory is None:
        _default_factory = AgentFactory()
    return _default_factory


def set_agent_factory(factory: AgentFactory):
    """设置全局 Agent 工厂（用于测试）"""
    global _default_factory
    _default_factory = factory


# ========== 便捷函数 ==========

def create_app_agent(
    hwnd: HWND,
    app_type: Optional[str] = None,
    host: Optional["HostAgent"] = None,
    **kwargs,
) -> AppAgent:
    """
    便捷函数：创建 AppAgent
    
    Args:
        hwnd: 窗口句柄
        app_type: 应用类型
        host: 父级 HostAgent
        **kwargs: 额外参数
        
    Returns:
        AppAgent 实例
    """
    factory = get_agent_factory()
    return factory.create(hwnd, app_type, host, **kwargs)


def create_browser_agent(hwnd: HWND, host: Optional["HostAgent"] = None, **kwargs) -> BrowserAppAgent:
    """创建浏览器 Agent"""
    return get_agent_factory().create(hwnd, "browser", host, **kwargs)


def create_desktop_agent(hwnd: HWND, host: Optional["HostAgent"] = None, **kwargs) -> DesktopAppAgent:
    """创建桌面 Agent"""
    return get_agent_factory().create(hwnd, "desktop", host, **kwargs)


def create_ide_agent(hwnd: HWND, host: Optional["HostAgent"] = None, **kwargs) -> IDEAppAgent:
    """创建 IDE Agent"""
    return get_agent_factory().create(hwnd, "ide", host, **kwargs)
