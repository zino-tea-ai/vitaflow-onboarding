"""
NogicOS AppAgent - 应用代理
============================

负责特定窗口/应用的操作执行。

参考:
- UFO AppAgent (app_agent.py)
- LangGraph Worker Agent
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable, Awaitable, TYPE_CHECKING
from enum import Enum
from abc import ABC, abstractmethod
import asyncio
import logging
import time

from .types import ToolResult, ToolCall, ToolDefinition, HWND
from .blackboard import Blackboard, RequestStatus
from .errors import ToolExecutionError, WindowLostError, ToolTimeoutError

if TYPE_CHECKING:
    from .host_agent import HostAgent

logger = logging.getLogger(__name__)


class AppType(Enum):
    """应用类型"""
    BROWSER = "browser"
    DESKTOP = "desktop"
    IDE = "ide"
    OFFICE = "office"
    TERMINAL = "terminal"
    CUSTOM = "custom"


class AppAgentState(Enum):
    """AppAgent 状态"""
    IDLE = "idle"
    EXECUTING = "executing"
    WAITING = "waiting"
    ERROR = "error"


@dataclass
class AppAgentConfig:
    """AppAgent 配置"""
    # 超时配置
    tool_timeout_ms: int = 30000
    screenshot_delay_ms: int = 750
    
    # 重试配置
    max_tool_retries: int = 2
    
    # 验证配置
    verify_after_action: bool = True
    
    # 坐标缩放
    coordinate_scale: float = 1.0


class AppAgent(ABC):
    """
    应用代理 - 负责特定窗口的操作
    
    每个 AppAgent 绑定到一个窗口，提供该窗口类型的专用工具。
    
    架构：
    - AppAgent 被 HostAgent 作为工具调用
    - 每个 AppAgent 拥有自己的工具集
    - 工具执行绑定到特定 hwnd
    
    子类需要实现：
    - _get_tools(): 返回应用专用工具
    - _get_window_state(): 获取窗口当前状态
    """
    
    def __init__(
        self,
        hwnd: HWND,
        app_type: AppType,
        host: Optional["HostAgent"] = None,
        config: Optional[AppAgentConfig] = None,
    ):
        """
        初始化 AppAgent
        
        Args:
            hwnd: 窗口句柄
            app_type: 应用类型
            host: 父级 HostAgent
            config: 配置
        """
        self.hwnd = hwnd
        self.app_type = app_type
        self.host = host
        self.config = config or AppAgentConfig()
        
        # 状态
        self.state = AppAgentState.IDLE
        self.is_active = True
        
        # 工具注册
        self._tools: Dict[str, Callable] = {}
        self._tool_definitions: List[ToolDefinition] = []
        
        # 初始化工具
        self._register_tools()
        
        logger.info(f"AppAgent created: hwnd={hwnd}, type={app_type.value}")
    
    def _register_tools(self):
        """注册工具 - 由子类调用 _get_tools()"""
        for tool_def, tool_fn in self._get_tools():
            self._tools[tool_def.name] = tool_fn
            self._tool_definitions.append(tool_def)
    
    @abstractmethod
    def _get_tools(self) -> List[tuple]:
        """
        获取应用专用工具
        
        Returns:
            List of (ToolDefinition, callable) tuples
        """
        pass
    
    @abstractmethod
    async def _get_window_state(self) -> Dict[str, Any]:
        """
        获取窗口当前状态
        
        Returns:
            窗口状态字典
        """
        pass
    
    async def execute(self, task: str) -> ToolResult:
        """
        执行任务 - HostAgent 调用入口
        
        这是 LangGraph Supervisor 调用 Worker 的接口
        
        Args:
            task: 任务描述
            
        Returns:
            执行结果
        """
        if not self.is_active:
            return ToolResult.failure(f"AppAgent for hwnd={self.hwnd} is not active")
        
        self.state = AppAgentState.EXECUTING
        start_time = time.time()
        
        try:
            # 1. 检查窗口是否存在
            if not await self._check_window_exists():
                self.is_active = False
                raise WindowLostError(self.hwnd)
            
            # 2. 获取窗口状态
            window_state = await self._get_window_state()
            
            # 3. 执行任务 (TODO: 实际实现需要解析任务并调用工具)
            result = await self._execute_task(task, window_state)
            
            # 4. 验证执行结果
            if self.config.verify_after_action:
                await asyncio.sleep(self.config.screenshot_delay_ms / 1000)
                # 截图验证 (TODO)
            
            duration_ms = (time.time() - start_time) * 1000
            self.state = AppAgentState.IDLE
            
            return ToolResult.success(
                output=result,
                hwnd=self.hwnd,
                duration_ms=duration_ms,
            )
            
        except WindowLostError:
            self.state = AppAgentState.ERROR
            raise
            
        except Exception as e:
            self.state = AppAgentState.ERROR
            logger.error(f"AppAgent execute error: {e}")
            return ToolResult.failure(
                error=str(e),
                hwnd=self.hwnd,
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    async def _execute_task(self, task: str, window_state: Dict[str, Any]) -> str:
        """
        执行具体任务
        
        Args:
            task: 任务描述
            window_state: 窗口状态
            
        Returns:
            执行结果描述
        """
        # 基础实现：直接返回状态
        # 子类可以覆盖实现更复杂的逻辑
        return f"Task '{task}' executed on {self.app_type.value} window"
    
    async def call_tool(
        self, 
        tool_name: str, 
        **kwargs,
    ) -> ToolResult:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            工具结果
        """
        tool_fn = self._tools.get(tool_name)
        if not tool_fn:
            return ToolResult.failure(f"Tool '{tool_name}' not found in {self.app_type.value} agent")
        
        start_time = time.time()
        
        try:
            # 添加超时控制
            result = await asyncio.wait_for(
                tool_fn(**kwargs),
                timeout=self.config.tool_timeout_ms / 1000,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            if isinstance(result, ToolResult):
                return result
            else:
                return ToolResult.success(
                    output=str(result),
                    hwnd=self.hwnd,
                    duration_ms=duration_ms,
                )
                
        except asyncio.TimeoutError:
            raise ToolTimeoutError(tool_name, self.config.tool_timeout_ms)
            
        except Exception as e:
            raise ToolExecutionError(
                message=str(e),
                tool_name=tool_name,
                tool_args=kwargs,
            )
    
    async def _check_window_exists(self) -> bool:
        """
        检查窗口是否存在
        
        TODO: 实现实际的窗口检查
        """
        # 占位实现
        return True
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """获取工具定义（Claude API 格式）"""
        return [td.to_claude_schema() for td in self._tool_definitions]
    
    def __repr__(self) -> str:
        return f"AppAgent(hwnd={self.hwnd}, type={self.app_type.value}, state={self.state.value})"


# ========== 具体实现 ==========

class BrowserAppAgent(AppAgent):
    """
    浏览器 AppAgent
    
    提供浏览器特定的工具：
    - 导航
    - 点击元素
    - 输入文本
    - 滚动
    - 截图
    """
    
    def __init__(self, hwnd: HWND, host: Optional["HostAgent"] = None, **kwargs):
        super().__init__(hwnd, AppType.BROWSER, host, **kwargs)
    
    def _get_tools(self) -> List[tuple]:
        """获取浏览器工具"""
        from .types import ToolParameter
        
        tools = []
        
        # navigate 工具
        navigate_def = ToolDefinition(
            name="navigate",
            description="Navigate to a URL in the browser",
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="The URL to navigate to",
                    required=True,
                )
            ],
            supports_hwnd=True,
            category="browser",
        )
        tools.append((navigate_def, self._tool_navigate))
        
        # click 工具
        click_def = ToolDefinition(
            name="click",
            description="Click on an element at the specified coordinates",
            parameters=[
                ToolParameter(name="x", type="integer", description="X coordinate", required=True),
                ToolParameter(name="y", type="integer", description="Y coordinate", required=True),
            ],
            supports_hwnd=True,
            category="browser",
        )
        tools.append((click_def, self._tool_click))
        
        # type_text 工具
        type_def = ToolDefinition(
            name="type_text",
            description="Type text at the current cursor position",
            parameters=[
                ToolParameter(
                    name="text",
                    type="string",
                    description="The text to type",
                    required=True,
                )
            ],
            supports_hwnd=True,
            category="browser",
        )
        tools.append((type_def, self._tool_type))
        
        # scroll 工具
        scroll_def = ToolDefinition(
            name="scroll",
            description="Scroll the page",
            parameters=[
                ToolParameter(
                    name="direction",
                    type="string",
                    description="Scroll direction: up, down, left, right",
                    required=True,
                    enum=["up", "down", "left", "right"],
                ),
                ToolParameter(
                    name="amount",
                    type="integer",
                    description="Scroll amount in pixels",
                    required=False,
                    default=300,
                ),
            ],
            supports_hwnd=True,
            category="browser",
        )
        tools.append((scroll_def, self._tool_scroll))
        
        return tools
    
    async def _get_window_state(self) -> Dict[str, Any]:
        """获取浏览器窗口状态"""
        return {
            "hwnd": self.hwnd,
            "type": "browser",
            "url": "",  # TODO: 获取当前 URL
            "title": "",  # TODO: 获取窗口标题
        }
    
    async def _tool_navigate(self, url: str) -> ToolResult:
        """
        导航到 URL
        
        浏览器导航需要：
        1. 聚焦地址栏 (Ctrl+L)
        2. 清空并输入 URL
        3. 按回车
        """
        from ..tools.window_tools import WindowTools
        
        tools = WindowTools()
        
        try:
            # 1. 聚焦地址栏
            hotkey_result = await tools.window_hotkey(self.hwnd, "ctrl+l")
            if not hotkey_result.success:
                return ToolResult.failure(f"Failed to focus address bar: {hotkey_result.error}", hwnd=self.hwnd)
            
            await asyncio.sleep(0.2)
            
            # 2. 输入 URL
            type_result = await tools.window_type(self.hwnd, url)
            if not type_result.success:
                return ToolResult.failure(f"Failed to type URL: {type_result.error}", hwnd=self.hwnd)
            
            await asyncio.sleep(0.1)
            
            # 3. 按回车
            enter_result = await tools.window_key_press(self.hwnd, "enter")
            if not enter_result.success:
                return ToolResult.failure(f"Failed to press Enter: {enter_result.error}", hwnd=self.hwnd)
            
            # 4. 等待页面加载
            await asyncio.sleep(1.0)
            
            # 5. 截图确认
            screenshot_result = await tools.window_screenshot(self.hwnd)
            
            return ToolResult(
                output=f"Navigated to {url}",
                error=None,
                base64_image=screenshot_result.base64_image,
                hwnd=self.hwnd,
            )
            
        except Exception as e:
            logger.error(f"Navigate failed: {e}")
            return ToolResult.failure(str(e), hwnd=self.hwnd)
    
    async def _tool_click(self, x: int, y: int) -> ToolResult:
        """
        点击坐标 - 使用 PostMessage (窗口隔离)
        
        坐标是相对于 1280x800 截图的，会自动转换为客户区坐标
        """
        from ..tools.window_tools import WindowTools
        
        tools = WindowTools()
        
        try:
            result = await tools.window_click(x, y, self.hwnd, capture_screenshot=True)
            
            if result.success:
                return ToolResult(
                    output=f"Clicked at ({x}, {y})",
                    error=None,
                    base64_image=result.base64_image,
                    hwnd=self.hwnd,
                )
            else:
                return ToolResult.failure(result.error or "Click failed", hwnd=self.hwnd)
                
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return ToolResult.failure(str(e), hwnd=self.hwnd)
    
    async def _tool_type(self, text: str) -> ToolResult:
        """
        输入文本 - 使用 PostMessage (窗口隔离)
        
        支持中英文混合输入
        """
        from ..tools.window_tools import WindowTools
        
        tools = WindowTools()
        
        try:
            result = await tools.window_type(text, self.hwnd, capture_screenshot=True)
            
            if result.success:
                return ToolResult(
                    output=f"Typed {len(text)} characters",
                    error=None,
                    base64_image=result.base64_image,
                    hwnd=self.hwnd,
                )
            else:
                return ToolResult.failure(result.error or "Type failed", hwnd=self.hwnd)
                
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return ToolResult.failure(str(e), hwnd=self.hwnd)
    
    async def _tool_scroll(self, direction: str, amount: int = 300) -> ToolResult:
        """
        滚动页面 - 使用 PostMessage (窗口隔离)
        """
        from ..tools.window_tools import WindowTools
        
        tools = WindowTools()
        
        try:
            result = await tools.window_scroll(self.hwnd, direction, amount, capture_screenshot=True)
            
            if result.success:
                return ToolResult(
                    output=f"Scrolled {direction} by {amount}px",
                    error=None,
                    base64_image=result.base64_image,
                    hwnd=self.hwnd,
                )
            else:
                return ToolResult.failure(result.error or "Scroll failed", hwnd=self.hwnd)
                
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return ToolResult.failure(str(e), hwnd=self.hwnd)


class DesktopAppAgent(AppAgent):
    """
    桌面应用 AppAgent
    
    提供通用桌面操作工具：
    - 鼠标点击
    - 键盘输入
    - 快捷键
    - 窗口操作
    """
    
    def __init__(self, hwnd: HWND, host: Optional["HostAgent"] = None, **kwargs):
        super().__init__(hwnd, AppType.DESKTOP, host, **kwargs)
    
    def _get_tools(self) -> List[tuple]:
        """获取桌面工具"""
        from .types import ToolParameter
        
        tools = []
        
        # mouse_click 工具
        click_def = ToolDefinition(
            name="mouse_click",
            description="Click at specified screen coordinates",
            parameters=[
                ToolParameter(name="x", type="integer", description="X coordinate", required=True),
                ToolParameter(name="y", type="integer", description="Y coordinate", required=True),
                ToolParameter(
                    name="button",
                    type="string",
                    description="Mouse button: left, right, middle",
                    required=False,
                    enum=["left", "right", "middle"],
                    default="left",
                ),
                ToolParameter(
                    name="clicks",
                    type="integer",
                    description="Number of clicks (1 for single, 2 for double)",
                    required=False,
                    default=1,
                ),
            ],
            supports_hwnd=True,
            category="desktop",
        )
        tools.append((click_def, self._tool_mouse_click))
        
        # keyboard_type 工具
        type_def = ToolDefinition(
            name="keyboard_type",
            description="Type text using keyboard",
            parameters=[
                ToolParameter(
                    name="text",
                    type="string",
                    description="Text to type",
                    required=True,
                ),
            ],
            supports_hwnd=True,
            category="desktop",
        )
        tools.append((type_def, self._tool_keyboard_type))
        
        # hotkey 工具
        hotkey_def = ToolDefinition(
            name="hotkey",
            description="Press a keyboard shortcut",
            parameters=[
                ToolParameter(
                    name="keys",
                    type="string",
                    description="Keys to press, e.g., 'ctrl+c', 'alt+tab'",
                    required=True,
                ),
            ],
            supports_hwnd=True,
            category="desktop",
        )
        tools.append((hotkey_def, self._tool_hotkey))
        
        # window_focus 工具
        focus_def = ToolDefinition(
            name="window_focus",
            description="Bring the window to foreground",
            parameters=[],
            supports_hwnd=True,
            category="desktop",
        )
        tools.append((focus_def, self._tool_window_focus))
        
        return tools
    
    async def _get_window_state(self) -> Dict[str, Any]:
        """获取桌面窗口状态"""
        return {
            "hwnd": self.hwnd,
            "type": "desktop",
            "title": "",  # TODO: 获取窗口标题
            "bounds": {},  # TODO: 获取窗口边界
        }
    
    async def _tool_mouse_click(
        self, 
        x: int, 
        y: int, 
        button: str = "left",
        clicks: int = 1,
    ) -> ToolResult:
        """
        鼠标点击 - 使用 PostMessage (窗口隔离)
        
        坐标是相对于 1280x800 截图的，会自动转换
        """
        from ..tools.window_tools import WindowTools
        
        tools = WindowTools()
        
        try:
            if clicks == 2:
                # 双击
                result = await tools.window_double_click(x, y, self.hwnd, capture_screenshot=True)
            else:
                # 单击
                result = await tools.window_click(x, y, self.hwnd, button=button, capture_screenshot=True)
            
            if result.success:
                click_type = "double" if clicks == 2 else button
                return ToolResult(
                    output=f"Mouse {click_type} clicked at ({x}, {y})",
                    error=None,
                    base64_image=result.base64_image,
                    hwnd=self.hwnd,
                )
            else:
                return ToolResult.failure(result.error or "Click failed", hwnd=self.hwnd)
                
        except Exception as e:
            logger.error(f"Mouse click failed: {e}")
            return ToolResult.failure(str(e), hwnd=self.hwnd)
    
    async def _tool_keyboard_type(self, text: str) -> ToolResult:
        """
        键盘输入 - 使用 PostMessage (窗口隔离)
        
        支持中英文混合输入（非 ASCII 使用剪贴板）
        """
        from ..tools.window_tools import WindowTools
        
        tools = WindowTools()
        
        try:
            result = await tools.window_type(text, self.hwnd, capture_screenshot=True)
            
            if result.success:
                return ToolResult(
                    output=f"Typed {len(text)} characters",
                    error=None,
                    base64_image=result.base64_image,
                    hwnd=self.hwnd,
                )
            else:
                return ToolResult.failure(result.error or "Type failed", hwnd=self.hwnd)
                
        except Exception as e:
            logger.error(f"Keyboard type failed: {e}")
            return ToolResult.failure(str(e), hwnd=self.hwnd)
    
    async def _tool_hotkey(self, keys: str) -> ToolResult:
        """
        快捷键 - 使用 PostMessage (窗口隔离)
        
        格式: "ctrl+c", "alt+tab", "ctrl+shift+s"
        """
        from ..tools.window_tools import WindowTools
        
        tools = WindowTools()
        
        try:
            result = await tools.window_hotkey(self.hwnd, keys, capture_screenshot=True)
            
            if result.success:
                return ToolResult(
                    output=f"Pressed hotkey: {keys}",
                    error=None,
                    base64_image=result.base64_image,
                    hwnd=self.hwnd,
                )
            else:
                return ToolResult.failure(result.error or "Hotkey failed", hwnd=self.hwnd)
                
        except Exception as e:
            logger.error(f"Hotkey failed: {e}")
            return ToolResult.failure(str(e), hwnd=self.hwnd)
    
    async def _tool_window_focus(self) -> ToolResult:
        """
        窗口聚焦 - 将窗口置于前台
        """
        from ..tools.window_state import get_state_checker
        from ..tools.window_tools import WindowTools
        
        tools = WindowTools()
        state_checker = get_state_checker()
        
        try:
            # 恢复窗口（如果最小化）并置于前台
            success = state_checker.bring_to_foreground(self.hwnd)
            
            if success:
                await asyncio.sleep(0.2)  # 等待窗口激活
                
                # 截图确认
                screenshot_result = await tools.window_screenshot(self.hwnd)
                
                return ToolResult(
                    output=f"Window {self.hwnd} focused",
                    error=None,
                    base64_image=screenshot_result.base64_image,
                    hwnd=self.hwnd,
                )
            else:
                return ToolResult.failure(f"Failed to focus window {self.hwnd}", hwnd=self.hwnd)
                
        except Exception as e:
            logger.error(f"Window focus failed: {e}")
            return ToolResult.failure(str(e), hwnd=self.hwnd)


class IDEAppAgent(AppAgent):
    """
    IDE AppAgent
    
    提供 IDE 特定的工具：
    - 文件操作
    - 代码编辑
    - 终端命令
    """
    
    def __init__(self, hwnd: HWND, host: Optional["HostAgent"] = None, **kwargs):
        super().__init__(hwnd, AppType.IDE, host, **kwargs)
    
    def _get_tools(self) -> List[tuple]:
        """获取 IDE 工具"""
        from .types import ToolParameter
        
        tools = []
        
        # open_file 工具
        open_def = ToolDefinition(
            name="open_file",
            description="Open a file in the IDE",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="File path to open",
                    required=True,
                ),
            ],
            supports_hwnd=True,
            category="ide",
        )
        tools.append((open_def, self._tool_open_file))
        
        # goto_line 工具
        goto_def = ToolDefinition(
            name="goto_line",
            description="Go to a specific line in the current file",
            parameters=[
                ToolParameter(
                    name="line",
                    type="integer",
                    description="Line number",
                    required=True,
                ),
            ],
            supports_hwnd=True,
            category="ide",
        )
        tools.append((goto_def, self._tool_goto_line))
        
        # run_command 工具
        cmd_def = ToolDefinition(
            name="run_terminal_command",
            description="Run a command in the IDE's integrated terminal",
            parameters=[
                ToolParameter(
                    name="command",
                    type="string",
                    description="Command to run",
                    required=True,
                ),
            ],
            supports_hwnd=True,
            is_sensitive=True,  # 敏感操作
            category="ide",
        )
        tools.append((cmd_def, self._tool_run_command))
        
        return tools
    
    async def _get_window_state(self) -> Dict[str, Any]:
        """获取 IDE 窗口状态"""
        return {
            "hwnd": self.hwnd,
            "type": "ide",
            "current_file": "",  # TODO
            "cursor_line": 0,  # TODO
        }
    
    async def _tool_open_file(self, path: str) -> ToolResult:
        """打开文件"""
        logger.info(f"Open file: {path}")
        return ToolResult.success(f"Opened file: {path}", hwnd=self.hwnd)
    
    async def _tool_goto_line(self, line: int) -> ToolResult:
        """跳转到行"""
        logger.info(f"Goto line: {line}")
        return ToolResult.success(f"Jumped to line {line}", hwnd=self.hwnd)
    
    async def _tool_run_command(self, command: str) -> ToolResult:
        """运行终端命令"""
        logger.info(f"Run command: {command}")
        return ToolResult.success(f"Executed: {command}", hwnd=self.hwnd)
