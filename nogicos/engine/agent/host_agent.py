"""
NogicOS HostAgent - 主控代理
=============================

实现 Supervisor 模式的主控 Agent，负责：
1. 任务分解和调度
2. AppAgent 管理和调用
3. 全局状态协调
4. 错误恢复和重试

参考:
- UFO HostAgent (host_agent.py)
- LangGraph Supervisor (tool-calling)
- ByteBot runIteration 循环
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable, Awaitable, Set, TYPE_CHECKING
from enum import Enum
import asyncio
import logging
import uuid
import time

from .events import EventType, AgentEvent
from .event_bus import EventBus, get_event_bus
from .blackboard import Blackboard, SubTask, RequestStatus
from .state_manager import TaskStateManager, TaskStatus, AgentStatus, get_state_manager
from .async_db import AsyncTaskStore, get_task_store
from .types import ToolResult, ToolCall, Message, MessageRole, LLMResponse
from .concurrency import ConcurrencyManager, ConcurrencyConfig, get_concurrency_manager
from .termination import (
    TerminationChecker, TerminationConfig, TerminationResult,
    TerminationReason, TerminationType, SuccessVerifier, detect_set_task_status,
)

# Phase 5: LLM 集成
from .llm_client import LLMClient, LLMConfig, get_llm_client
from .prompts import build_system_prompt, AgentMode
from .tool_descriptions import get_tool_schemas, get_tool_registry
from .context_manager import ContextManager, TokenBudget, get_context_manager

if TYPE_CHECKING:
    from .app_agent import AppAgent

logger = logging.getLogger(__name__)


class HostAgentState(Enum):
    """HostAgent 状态"""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_CONFIRM = "waiting_confirm"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class AgentConfig:
    """
    Agent 配置
    
    包含 Agent 运行时的所有配置参数
    """
    # 基础配置
    db_path: str = "nogicos_tasks.db"
    
    # 迭代控制
    max_iterations: int = 50
    iteration_timeout_s: float = 120.0
    screenshot_delay_ms: int = 750
    
    # 重试配置
    max_retries: int = 3
    retry_backoff_base: float = 2.0
    
    # 并发配置
    max_concurrent_tasks: int = 3
    max_api_concurrency: int = 5
    
    # 检查点配置
    checkpoint_interval: int = 5  # 每 N 次迭代保存检查点
    
    # 上下文配置
    max_context_tokens: int = 180000
    context_compress_threshold: float = 0.75
    
    # 终止配置 (Phase 3)
    task_timeout_s: float = 1800.0  # 30 分钟任务超时
    max_consecutive_failures: int = 3  # 连续失败限制
    max_total_failures: int = 10  # 总失败次数限制
    
    # 成功验证配置 (Phase 3)
    verify_success: bool = True  # 是否验证任务完成
    verification_model: str = "claude-3-haiku-20240307"  # 验证模型
    min_verification_confidence: float = 0.7  # 最低验证置信度
    
    # 敏感操作
    sensitive_tools: List[str] = field(default_factory=lambda: [
        "delete_file", "system_command", "send_email",
        "make_payment", "modify_settings"
    ])
    
    # Vision 增强配置 (Phase 5c)
    enable_vision_enhancement: bool = True  # 是否启用 OCR 增强
    vision_ocr_enabled: bool = True         # 是否启用 OCR 文本提取
    vision_enhancement_timeout_ms: int = 5000  # 增强超时（毫秒）
    vision_log_timing: bool = True          # 是否记录增强耗时
    
    def to_termination_config(self) -> TerminationConfig:
        """转换为终止配置"""
        return TerminationConfig(
            max_iterations=self.max_iterations,
            task_timeout_s=self.task_timeout_s,
            iteration_timeout_s=self.iteration_timeout_s,
            max_consecutive_failures=self.max_consecutive_failures,
            max_total_failures=self.max_total_failures,
            max_context_tokens=self.max_context_tokens,
        )
    
    def to_concurrency_config(self) -> ConcurrencyConfig:
        """转换为并发配置"""
        return ConcurrencyConfig(
            max_concurrent_tasks=self.max_concurrent_tasks,
            max_api_concurrency=self.max_api_concurrency,
        )


@dataclass
class IterationResult:
    """单次迭代结果"""
    iteration: int
    tool_calls: List[ToolCall]
    tool_results: List[ToolResult]
    llm_response: Optional[LLMResponse] = None
    thinking: Optional[str] = None
    duration_ms: float = 0.0
    should_continue: bool = True
    error: Optional[str] = None


class HostAgent:
    """
    主控代理 - Supervisor 模式
    
    负责：
    1. 接收用户任务
    2. 分解任务为子任务
    3. 调度 AppAgent 执行
    4. 管理全局状态
    5. 处理错误和恢复
    
    使用示例:
    ```python
    config = AgentConfig()
    host = HostAgent(config)
    await host.initialize()
    
    # 启动任务
    result = await host.process_task(
        task_id="task-123",
        task_text="在浏览器中搜索 Python 教程",
        target_hwnds=[12345]
    )
    ```
    
    架构：
    - HostAgent 作为 Supervisor
    - AppAgent 作为 Worker (tool-calling 模式)
    """
    
    def __init__(
        self, 
        config: Optional[AgentConfig] = None,
        event_bus: Optional[EventBus] = None,
        task_store: Optional[AsyncTaskStore] = None,
        state_manager: Optional[TaskStateManager] = None,
        concurrency_manager: Optional[ConcurrencyManager] = None,
    ):
        """
        初始化 HostAgent
        
        Args:
            config: Agent 配置
            event_bus: 事件总线（默认全局单例）
            task_store: 任务存储（默认全局单例）
            state_manager: 状态管理器（默认全局单例）
            concurrency_manager: 并发管理器（默认全局单例）
        """
        self.config = config or AgentConfig()
        self._event_bus = event_bus
        self._task_store = task_store
        self._state_manager = state_manager
        self._concurrency_manager = concurrency_manager
        
        # Agent 状态
        self.state = HostAgentState.IDLE
        self.is_processing = False
        self.current_task_id: Optional[str] = None
        
        # AppAgent 注册表
        self._app_agents: Dict[int, "AppAgent"] = {}  # hwnd -> AppAgent
        
        # 黑板（任务间共享状态）
        self.blackboard: Optional[Blackboard] = None
        
        # 迭代状态
        self._iteration_count = 0
        self._retry_count = 0
        self._start_time: Optional[float] = None
        
        # 消息历史
        self._messages: List[Message] = []
        
        # 工具注册表（包含 AppAgent 工具）
        self._tools: Dict[str, Callable] = {}
        self._tool_definitions: List[Dict[str, Any]] = []
        
        # Phase 3: 终止检查器和成功验证器
        self._termination_checker: Optional[TerminationChecker] = None
        self._success_verifier: Optional[SuccessVerifier] = None
        
        # 当前任务的目标窗口
        self._target_hwnds: Set[int] = set()
        
        # 工具调用历史（用于验证）
        self._tool_history: List[Dict[str, Any]] = []
        
        # 回调
        self._on_thinking: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_tool_start: Optional[Callable[[str, dict], Awaitable[None]]] = None
        self._on_tool_end: Optional[Callable[[str, ToolResult], Awaitable[None]]] = None
        
        # Phase 5: LLM 客户端（延迟初始化）
        self._llm_client = None
        self._llm_available = False
        self._context_manager = None
        self._vision_enhancer = None
        
        # 初始化标记
        self._initialized = False
        
        logger.info(f"HostAgent created with config: max_iterations={self.config.max_iterations}")
    
    async def initialize(self):
        """初始化 HostAgent（异步）"""
        if self._initialized:
            return
        
        # 获取单例
        self._event_bus = self._event_bus or get_event_bus()
        self._task_store = self._task_store or await get_task_store()
        self._state_manager = self._state_manager or await get_state_manager(self._task_store)
        
        # Phase 3: 初始化并发管理器
        self._concurrency_manager = self._concurrency_manager or get_concurrency_manager(
            self.config.to_concurrency_config()
        )
        
        # Phase 3: 初始化成功验证器
        self._success_verifier = SuccessVerifier(
            verification_model=self.config.verification_model,
            min_confidence=self.config.min_verification_confidence,
        )
        
        # Phase 5: 初始化 LLM 客户端（优雅降级）
        self._llm_client = None
        self._llm_available = False
        try:
            llm_config = LLMConfig(
                model="claude-sonnet-4-20250514",
                max_tokens=self.config.max_context_tokens // 20,
                enable_prompt_caching=True,
                enable_streaming=True,
            )
            self._llm_client = LLMClient(llm_config)
            await self._llm_client.initialize()
            self._llm_available = True
            logger.info("LLM client initialized successfully")
        except ImportError as e:
            logger.warning(
                f"LLM client unavailable (missing dependency): {e}. "
                "Install with: pip install anthropic"
            )
        except ValueError as e:
            logger.warning(
                f"LLM client unavailable (configuration error): {e}. "
                "Set ANTHROPIC_API_KEY environment variable."
            )
        except Exception as e:
            logger.warning(f"LLM client initialization failed: {e}")
        
        # Phase 5b: 初始化上下文管理器
        token_budget = TokenBudget(
            max_input_tokens=self.config.max_context_tokens,
            compression_threshold=self.config.context_compress_threshold,
        )
        self._context_manager = ContextManager(token_budget, self._llm_client)
        
        # Phase 5c: 初始化视觉增强器（优雅降级）
        self._vision_enhancer = None
        if self.config.enable_vision_enhancement:
            try:
                from .vision import VisionEnhancer, get_vision_enhancer
                self._vision_enhancer = get_vision_enhancer(
                    use_ocr=self.config.vision_ocr_enabled,
                    use_ui_detection=False,
                )
                logger.info(f"Vision enhancement enabled: ocr={self.config.vision_ocr_enabled}")
            except ImportError as e:
                logger.warning(
                    f"Vision enhancement unavailable (missing dependency): {e}. "
                    "Install with: pip install pillow easyocr"
                )
            except Exception as e:
                logger.warning(f"Vision enhancement initialization failed: {e}")
        
        # 注册内置工具
        self._register_builtin_tools()
        
        self._initialized = True
        logger.info("HostAgent initialized with Phase 5 LLM + Vision integration")
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        # set_task_status 工具 - 参考 ByteBot
        self._tools["set_task_status"] = self._tool_set_task_status
        self._tool_definitions.append({
            "name": "set_task_status",
            "description": "设置任务状态。当任务完成或需要用户帮助时调用此工具。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["completed", "needs_help"],
                        "description": "任务状态：completed=已完成，needs_help=需要用户帮助"
                    },
                    "description": {
                        "type": "string",
                        "description": "状态描述，说明完成的内容或需要什么帮助"
                    }
                },
                "required": ["status", "description"]
            }
        })
    
    async def _tool_set_task_status(self, status: str, description: str) -> ToolResult:
        """
        set_task_status 工具实现
        
        Args:
            status: 状态 (completed / needs_help)
            description: 状态描述
        """
        if status == "completed":
            await self._complete_task(description)
            return ToolResult.success(f"Task marked as completed: {description}")
        elif status == "needs_help":
            await self._request_help(description)
            return ToolResult.success(f"Help requested: {description}")
        else:
            return ToolResult.failure(f"Invalid status: {status}")
    
    # ========== AppAgent 管理 ==========
    
    def register_app_agent(self, hwnd: int, agent: "AppAgent"):
        """
        注册 AppAgent
        
        Args:
            hwnd: 窗口句柄
            agent: AppAgent 实例
        """
        self._app_agents[hwnd] = agent
        
        # 将 AppAgent 注册为工具（LangGraph Supervisor 模式）
        tool_name = f"app_agent_{hwnd}"
        self._tools[tool_name] = agent.execute
        self._tool_definitions.append({
            "name": tool_name,
            "description": f"Execute task on {agent.app_type} window (hwnd={hwnd})",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task to execute on this window"
                    }
                },
                "required": ["task"]
            }
        })
        
        logger.info(f"Registered AppAgent: hwnd={hwnd}, type={agent.app_type}")
    
    def unregister_app_agent(self, hwnd: int):
        """注销 AppAgent"""
        if hwnd in self._app_agents:
            agent = self._app_agents.pop(hwnd)
            tool_name = f"app_agent_{hwnd}"
            self._tools.pop(tool_name, None)
            self._tool_definitions = [
                t for t in self._tool_definitions 
                if t["name"] != tool_name
            ]
            logger.info(f"Unregistered AppAgent: hwnd={hwnd}")
    
    def get_app_agent(self, hwnd: int) -> Optional["AppAgent"]:
        """获取 AppAgent"""
        return self._app_agents.get(hwnd)
    
    # ========== 任务处理 ==========
    
    async def process_task(
        self, 
        task_id: str, 
        task_text: str,
        target_hwnds: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        处理任务 - 主入口
        
        Phase 3: 增加并发控制
        
        Args:
            task_id: 任务 ID
            task_text: 任务描述
            target_hwnds: 目标窗口列表
            
        Returns:
            任务结果
        """
        if not self._initialized:
            await self.initialize()
        
        if self.is_processing:
            raise RuntimeError(f"Already processing task: {self.current_task_id}")
        
        logger.info(f"Starting task: {task_id}")
        
        # Phase 3: 获取任务槽位
        hwnd_set = set(target_hwnds or [])
        if not await self._concurrency_manager.acquire_task_slot(task_id, hwnd_set):
            from .errors import TooManyTasksError
            raise TooManyTasksError(
                current_count=len(self._concurrency_manager.get_active_tasks()),
                max_count=self.config.max_concurrent_tasks,
            )
        
        # Phase 3: 获取窗口锁
        if hwnd_set and not await self._concurrency_manager.acquire_windows(hwnd_set, task_id):
            self._concurrency_manager.release_task_slot(task_id)
            from .errors import WindowLockedError
            raise WindowLockedError(
                hwnd=list(hwnd_set)[0] if hwnd_set else 0,
                locked_by="another task",
            )
        
        # 初始化任务状态
        self.is_processing = True
        self.current_task_id = task_id
        self.state = HostAgentState.PLANNING
        self._iteration_count = 0
        self._retry_count = 0
        self._start_time = time.time()
        self._messages = []
        self._target_hwnds = hwnd_set
        self._tool_history = []
        
        # Phase 3: 初始化终止检查器
        self._termination_checker = TerminationChecker(self.config.to_termination_config())
        
        # 创建黑板
        self.blackboard = Blackboard(task_id=task_id)
        
        try:
            # 1. 创建任务记录
            await self._state_manager.create_task(task_id, task_text, target_hwnds)
            await self._state_manager.transition(task_id, TaskStatus.RUNNING)
            
            # 2. 发布任务开始事件
            await self._publish_event(EventType.TASK_STARTED, {
                "task_text": task_text,
                "target_hwnds": target_hwnds or [],
            })
            
            # 3. 添加初始消息
            self._messages.append(Message.user(task_text))
            
            # 4. 运行主循环
            result = await self._run_loop(task_id, task_text)
            
            return result
            
        except Exception as e:
            logger.exception(f"Task {task_id} failed with error: {e}")
            await self._fail_task(task_id, str(e))
            raise
            
        finally:
            # Phase 3: 释放资源
            if self._target_hwnds:
                self._concurrency_manager.release_windows(self._target_hwnds)
            self._concurrency_manager.release_task_slot(task_id)
            
            self.is_processing = False
            self.current_task_id = None
            self.state = HostAgentState.IDLE
            self._target_hwnds = set()
    
    async def _run_loop(self, task_id: str, task_text: str = "") -> Dict[str, Any]:
        """
        运行主循环 - Phase 3 升级版
        
        使用 TerminationChecker 进行统一的终止条件检查
        
        迭代执行直到：
        1. 调用 set_task_status
        2. 达到最大迭代次数
        3. 发生不可恢复错误
        4. 连续失败过多
        5. 超时
        """
        self.state = HostAgentState.EXECUTING
        
        # 最终截图（用于验证）
        final_screenshot: Optional[str] = None
        termination_result: Optional[TerminationResult] = None
        
        while self.is_processing:
            elapsed = time.time() - (self._start_time or time.time())
            
            # 运行单次迭代
            result = await self._run_iteration(task_id)
            
            # 记录工具调用历史
            for tc in result.tool_calls:
                self._tool_history.append({
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "error": any(r.is_error for r in result.tool_results) if result.tool_results else False,
                })
            
            # 保存最后的截图
            for tr in result.tool_results:
                if tr.base64_image:
                    final_screenshot = tr.base64_image
            
            # Phase 3: 使用 TerminationChecker 检查终止条件
            set_task_status_call = detect_set_task_status([
                {"name": tc.name, "arguments": tc.arguments}
                for tc in result.tool_calls
            ])
            
            termination_result = self._termination_checker.check(
                iteration=self._iteration_count,
                tool_results=result.tool_results,
                set_task_status_called=set_task_status_call is not None,
                set_task_status_value=set_task_status_call.status if set_task_status_call else None,
                window_exists=await self._check_windows_exist(),
                elapsed_time_s=elapsed,
                current_tokens=self._context_manager.count_tokens(self._messages) if self._context_manager else 0,
            )
            
            if termination_result.should_terminate:
                logger.info(
                    f"Task {task_id} terminating: "
                    f"reason={termination_result.reason.value if termination_result.reason else 'unknown'}, "
                    f"type={termination_result.termination_type.value if termination_result.termination_type else 'unknown'}"
                )
                break
            
            # 定期保存检查点
            if self._iteration_count % self.config.checkpoint_interval == 0:
                await self._save_checkpoint(task_id)
            
            self._iteration_count += 1
            
            # 非阻塞调度下一次迭代
            await asyncio.sleep(0)
        
        # Phase 3: 处理终止结果
        if termination_result:
            await self._handle_termination(task_id, task_text, termination_result, final_screenshot)
        
        # 返回最终结果
        return await self._get_task_result(task_id)
    
    async def _check_windows_exist(self) -> bool:
        """
        检查目标窗口是否存在 - Phase 3 修复
        
        使用 Windows API 检查窗口句柄是否有效
        
        Returns:
            所有目标窗口是否都存在
        """
        if not self._target_hwnds:
            return True
        
        try:
            import ctypes
            from ctypes import wintypes
            
            # Windows API: IsWindow 检查窗口句柄是否有效
            user32 = ctypes.windll.user32
            user32.IsWindow.argtypes = [wintypes.HWND]
            user32.IsWindow.restype = wintypes.BOOL
            
            for hwnd in self._target_hwnds:
                if not user32.IsWindow(hwnd):
                    logger.warning(f"Window {hwnd} no longer exists")
                    return False
            
            return True
            
        except Exception as e:
            # 非 Windows 平台或其他错误，默认返回 True
            logger.debug(f"Window existence check failed: {e}")
            return True
    
    async def _handle_termination(
        self,
        task_id: str,
        task_text: str,
        termination_result: TerminationResult,
        final_screenshot: Optional[str],
    ):
        """
        处理任务终止 - Phase 3
        
        根据终止类型更新状态，并可选地验证成功
        """
        if termination_result.termination_type == TerminationType.SUCCESS:
            # 任务声称完成，可选验证
            if self.config.verify_success and final_screenshot and self._success_verifier:
                # Phase 3 修复: 传入 LLM 客户端进行真正的验证
                verified = await self._success_verifier.verify(
                    task=task_text,
                    final_screenshot=final_screenshot,
                    tool_history=self._tool_history,
                    llm_client=self._llm_client,  # 使用 HostAgent 的 LLM 客户端
                )
                if not verified:
                    logger.warning(f"Task {task_id} verification failed")
                    await self._fail_task(task_id, "Task verification failed")
                    return
            
            await self._complete_task(termination_result.message)
            
        elif termination_result.termination_type == TerminationType.FAIL:
            # 逻辑失败
            if termination_result.reason == TerminationReason.NEEDS_HELP:
                await self._request_help(termination_result.message)
            else:
                await self._fail_task(task_id, termination_result.message)
            
        elif termination_result.termination_type == TerminationType.ERROR:
            # 系统错误
            await self._emergency_stop(task_id, termination_result.message)
            
        elif termination_result.termination_type == TerminationType.CANCELLED:
            # 用户取消
            await self._state_manager.transition(
                task_id,
                TaskStatus.CANCELLED,
                reason=termination_result.message,
            )
            self.is_processing = False
    
    async def _emergency_stop(self, task_id: str, reason: str):
        """
        紧急停止 - Phase 3
        
        保存状态 + 通知用户
        """
        self.is_processing = False
        
        # 保存检查点
        await self._save_checkpoint(task_id)
        
        # 更新状态
        await self._state_manager.transition(
            task_id,
            TaskStatus.INTERRUPTED,
            reason=reason,
        )
        
        # 发布紧急停止事件
        await self._publish_event(EventType.TASK_FAILED, {
            "type": "emergency_stop",
            "reason": reason,
        })
        
        self.state = HostAgentState.ERROR
        logger.error(f"Emergency stop: {reason}")
    
    async def _run_iteration(self, task_id: str) -> IterationResult:
        """
        单次迭代
        
        1. 构建上下文
        2. 调用 LLM
        3. 执行工具
        4. 处理结果
        """
        start_time = time.time()
        
        try:
            # 1. 检查任务状态
            status = await self._state_manager.get_status(task_id)
            if status != TaskStatus.RUNNING:
                return IterationResult(
                    iteration=self._iteration_count,
                    tool_calls=[],
                    tool_results=[],
                    should_continue=False,
                )
            
            # 2. 检查上下文是否需要压缩
            if await self._should_compress_context():
                await self._compress_context()
            
            # 3. 调用 LLM (TODO: 实现实际的 LLM 调用)
            llm_response = await self._call_llm()
            
            # 4. 发布思考事件
            if llm_response.content:
                await self._publish_event(EventType.AGENT_THINKING, {
                    "thinking": llm_response.content,
                    "iteration": self._iteration_count,
                })
                if self._on_thinking:
                    await self._on_thinking(llm_response.content)
            
            # 5. 执行工具调用并将结果添加到消息历史
            tool_results = []
            for tool_call in llm_response.tool_calls:
                result = await self._execute_tool(tool_call)
                
                # 【P2 修复】如果是截图结果，使用 Vision 增强
                if result.base64_image:
                    result = await self._enhance_screenshot_result(result)
                
                tool_results.append(result)
                
                # 【P0 修复】将工具结果添加到消息历史
                # Claude 需要看到工具执行结果才能继续推理
                # 使用结构化内容支持图片
                if result.base64_image:
                    # 包含截图的结果，使用结构化内容
                    tool_result_content = self._build_tool_result_message_content(tool_call, result)
                    self._messages.append(Message(
                        role=MessageRole.TOOL,
                        content=tool_result_content,
                        tool_call_id=tool_call.id,
                        name=tool_call.name,
                    ))
                else:
                    # 纯文本结果
                    tool_result_content = self._format_tool_result_content(tool_call, result)
                    self._messages.append(Message.tool(
                        tool_call_id=tool_call.id,
                        name=tool_call.name,
                        content=tool_result_content,
                    ))
                
                # 截图延迟
                await asyncio.sleep(self.config.screenshot_delay_ms / 1000)
            
            # 6. 检查 set_task_status
            task_status_called = any(
                tc.name == "set_task_status" 
                for tc in llm_response.tool_calls
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            return IterationResult(
                iteration=self._iteration_count,
                tool_calls=llm_response.tool_calls,
                tool_results=tool_results,
                llm_response=llm_response,
                thinking=llm_response.content,
                duration_ms=duration_ms,
                should_continue=not task_status_called and llm_response.needs_tool_execution,
            )
            
        except Exception as e:
            logger.error(f"Iteration {self._iteration_count} error: {e}")
            
            # 错误恢复
            if await self._handle_error(task_id, e):
                # 可恢复，继续
                return IterationResult(
                    iteration=self._iteration_count,
                    tool_calls=[],
                    tool_results=[],
                    should_continue=True,
                    error=str(e),
                )
            else:
                # 不可恢复，停止
                return IterationResult(
                    iteration=self._iteration_count,
                    tool_calls=[],
                    tool_results=[],
                    should_continue=False,
                    error=str(e),
                )
    
    def _determine_prompt_mode(self, windows_info: List[Dict[str, Any]]) -> AgentMode:
        """
        根据窗口类型自动选择 Prompt 模式
        
        策略：
        - 全部是浏览器窗口 → BROWSER 模式
        - 全部是桌面应用窗口 → DESKTOP 模式
        - 混合或未知 → HYBRID 模式
        
        Args:
            windows_info: 窗口信息列表
            
        Returns:
            最佳的 AgentMode
        """
        if not windows_info:
            return AgentMode.HYBRID
        
        app_types = {w.get("app_type", "unknown").lower() for w in windows_info}
        
        # 移除 unknown
        known_types = app_types - {"unknown"}
        
        if not known_types:
            # 全部未知，使用混合模式
            return AgentMode.HYBRID
        
        if known_types == {"browser"}:
            return AgentMode.BROWSER
        
        if known_types <= {"desktop", "ide", "native"}:
            return AgentMode.DESKTOP
        
        # 混合类型
        return AgentMode.HYBRID
    
    async def _call_llm(self) -> LLMResponse:
        """
        调用 LLM - Phase 5 实现

        使用 Claude API 调用，支持：
        - Prompt Caching
        - 流式输出
        - Tool Calling
        - 自动选择 Prompt 模式
        """
        # 检查 LLM 是否可用
        if not self._llm_available or self._llm_client is None:
            from .types import StopReason
            logger.error("LLM client not available, cannot process task")
            return LLMResponse(
                content="Error: LLM client is not available. Please ensure anthropic package is installed and ANTHROPIC_API_KEY is set.",
                stop_reason=StopReason.END_TURN,
                tool_calls=[],
                input_tokens=0,
                output_tokens=0,
            )
        
        # 构建系统提示词
        windows_info = [
            {
                "hwnd": hwnd,
                "title": agent.window_title if hasattr(agent, 'window_title') else f"Window {hwnd}",
                "app_type": agent.app_type if hasattr(agent, 'app_type') else "unknown",
            }
            for hwnd, agent in self._app_agents.items()
        ]
        
        # 如果没有注册的 AppAgent，使用目标窗口
        if not windows_info and self._target_hwnds:
            windows_info = [
                {"hwnd": hwnd, "title": f"Window {hwnd}", "app_type": "unknown"}
                for hwnd in self._target_hwnds
            ]
        
        # 获取任务描述
        task_text = ""
        for msg in self._messages:
            if msg.role == MessageRole.USER and isinstance(msg.content, str):
                task_text = msg.content
                break
        
        # 自动选择最佳 Prompt 模式
        prompt_mode = self._determine_prompt_mode(windows_info)
        logger.debug(f"Selected prompt mode: {prompt_mode.value} based on windows: {[w.get('app_type') for w in windows_info]}")
        
        system_prompt = build_system_prompt(
            task_description=task_text,
            windows=windows_info,
            mode=prompt_mode,
        )
        
        # 获取工具定义（使用增强版描述）
        tool_registry = get_tool_registry()
        
        # 合并内置工具定义和注册表中的工具
        all_tools = self._tool_definitions.copy()
        
        # 添加注册表中的工具（如果没有重复）
        registered_tool_names = {t["name"] for t in all_tools}
        for tool_schema in tool_registry.to_claude_tools():
            if tool_schema["name"] not in registered_tool_names:
                all_tools.append(tool_schema)
        
        # 流式输出回调
        async def on_text(text: str):
            """文本流回调"""
            if self._on_thinking:
                await self._on_thinking(text)
            # 发布思考事件
            await self._publish_event(EventType.AGENT_THINKING, {
                "text": text,
                "iteration": self._iteration_count,
                "streaming": True,
            })
        
        async def on_tool_call(tool_call: ToolCall):
            """工具调用回调"""
            logger.debug(f"Tool call detected: {tool_call.name}")
        
        try:
            # 使用流式调用
            response = await self._llm_client.stream(
                messages=self._messages,
                system_prompt=system_prompt,
                tools=all_tools,
                on_text=on_text,
                on_tool_call=on_tool_call,
            )
            
            # 记录 token 使用
            logger.info(
                f"LLM call complete: input={response.input_tokens}, output={response.output_tokens}, "
                f"tool_calls={len(response.tool_calls)}"
            )
            
            # 添加 assistant 消息到历史
            self._messages.append(Message.assistant(
                content=response.content,
                tool_calls=response.tool_calls,
            ))
            
            return response
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            # 返回错误响应
            from .types import StopReason
            return LLMResponse(
                content=f"Error calling LLM: {e}",
                stop_reason=StopReason.END_TURN,
                tool_calls=[],
                input_tokens=0,
                output_tokens=0,
            )
    
    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        执行工具调用
        
        Args:
            tool_call: 工具调用请求
            
        Returns:
            工具执行结果
        """
        tool_name = tool_call.name
        tool_args = tool_call.arguments
        
        # 发布工具开始事件
        await self._publish_event(EventType.TOOL_START, {
            "tool_name": tool_name,
            "args": tool_args,
        })
        
        if self._on_tool_start:
            await self._on_tool_start(tool_name, tool_args)
        
        start_time = time.time()
        
        try:
            # 查找工具
            tool_fn = self._tools.get(tool_name)
            if not tool_fn:
                result = ToolResult.failure(f"Tool '{tool_name}' not found")
            else:
                # 检查敏感操作
                if tool_name in self.config.sensitive_tools:
                    approved = await self._request_confirmation(tool_name, tool_args)
                    if not approved:
                        result = ToolResult.failure("User denied the operation")
                    else:
                        result = await tool_fn(**tool_args)
                else:
                    result = await tool_fn(**tool_args)
            
            duration_ms = (time.time() - start_time) * 1000
            
            # 发布工具结束事件
            await self._publish_event(EventType.TOOL_END, {
                "tool_name": tool_name,
                "result": result.to_dict(),
                "duration_ms": duration_ms,
            })
            
            if self._on_tool_end:
                await self._on_tool_end(tool_name, result)
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result = ToolResult.failure(str(e), duration_ms=duration_ms)
            
            # 发布工具错误事件
            await self._publish_event(EventType.TOOL_ERROR, {
                "tool_name": tool_name,
                "error": str(e),
                "duration_ms": duration_ms,
            })
            
            return result
    
    def _format_tool_result_content(
        self,
        tool_call: ToolCall,
        result: ToolResult,
    ) -> str:
        """
        格式化工具结果为消息内容 - Phase 5 P0 修复
        
        处理文本结果和截图结果，转换为 Claude API 可接受的格式
        
        Args:
            tool_call: 工具调用
            result: 工具执行结果
            
        Returns:
            格式化的内容字符串或内容列表
        """
        # 如果有错误，返回错误信息
        if result.is_error:
            return f"Error: {result.error}"
        
        # 如果有截图，需要特殊处理
        # 注意：截图会在 _prepare_messages 中转换为图片格式
        if result.base64_image:
            # 返回带有截图标记的内容，后续在 _prepare_messages 中处理
            output_text = result.output or "Screenshot captured"
            return f"{output_text}\n[SCREENSHOT:{result.base64_image[:50]}...]"
        
        # 普通文本结果
        return result.output or "Success"
    
    def _build_tool_result_message_content(
        self,
        tool_call: ToolCall,
        result: ToolResult,
    ) -> list:
        """
        构建包含图片的工具结果消息内容 - Phase 5 P0/P2 修复
        
        用于支持截图工具返回图片，并可选地使用 Vision 增强
        
        Args:
            tool_call: 工具调用
            result: 工具执行结果
            
        Returns:
            Claude API 格式的内容列表
        """
        content = []
        
        # 添加文本结果
        if result.is_error:
            content.append({
                "type": "text",
                "text": f"Error: {result.error}",
            })
        elif result.output:
            content.append({
                "type": "text",
                "text": result.output,
            })
        
        # 添加截图
        if result.base64_image:
            # 确定图片类型
            media_type = "image/png"
            if result.base64_image.startswith("/9j/"):
                media_type = "image/jpeg"
            
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": result.base64_image,
                }
            })
            
            # 【P2 修复】使用 Vision 增强器添加 OCR 文本
            # 这样 LLM 可以更好地理解截图内容
            if hasattr(self, '_vision_enhancer') and self._vision_enhancer:
                try:
                    # 异步增强需要在协程中调用，这里使用同步方式获取 OCR 文本
                    # 实际使用时应在 _execute_tool 后异步调用
                    pass  # OCR 增强在下面单独处理
                except Exception as e:
                    logger.debug(f"Vision enhancement skipped: {e}")
        
        # 如果没有任何内容，返回默认成功消息
        if not content:
            content.append({
                "type": "text",
                "text": "Success",
            })
        
        return content
    
    async def _enhance_screenshot_result(
        self,
        result: ToolResult,
    ) -> ToolResult:
        """
        使用 Vision 增强截图结果 - Phase 5c 带性能监控
        
        为截图添加 OCR 文本描述，帮助 LLM 更好地理解屏幕内容
        支持超时控制和性能日志

        Args:
            result: 原始工具结果

        Returns:
            增强后的工具结果
        """
        if not result.base64_image:
            return result

        # 检查是否启用 Vision 增强
        if not self.config.enable_vision_enhancement:
            return result
        
        if not hasattr(self, '_vision_enhancer') or not self._vision_enhancer:
            return result

        start_time = time.time()
        
        try:
            # 使用超时控制的异步增强
            timeout_s = self.config.vision_enhancement_timeout_ms / 1000.0
            
            enhanced = await asyncio.wait_for(
                self._vision_enhancer.enhance(
                    screenshot_b64=result.base64_image,
                    hwnd=result.hwnd,
                ),
                timeout=timeout_s,
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # 记录时延日志
            if self.config.vision_log_timing:
                logger.info(
                    f"Vision enhancement completed in {elapsed_ms:.1f}ms "
                    f"(ocr_chars={len(enhanced.full_text)}, elements={len(enhanced.text_elements)})"
                )

            # 构建增强的输出文本
            enhanced_output = result.output or "Screenshot captured"

            # 添加 OCR 文本
            if enhanced.full_text:
                ocr_preview = enhanced.full_text[:500]
                if len(enhanced.full_text) > 500:
                    ocr_preview += "..."
                enhanced_output += f"\n\n[OCR Text]: {ocr_preview}"

            # 添加结构化描述
            if enhanced.description:
                enhanced_output += f"\n\n[Description]: {enhanced.description}"

            # 返回增强后的结果
            return ToolResult(
                output=enhanced_output,
                error=result.error,
                base64_image=result.base64_image,
                hwnd=result.hwnd,
                duration_ms=result.duration_ms,
            )
        
        except asyncio.TimeoutError:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.warning(
                f"Vision enhancement timed out after {elapsed_ms:.1f}ms "
                f"(limit={self.config.vision_enhancement_timeout_ms}ms)"
            )
            return result

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.warning(f"Failed to enhance screenshot after {elapsed_ms:.1f}ms: {e}")
            return result
    
    # ========== 状态管理 ==========
    
    async def _complete_task(self, description: str):
        """完成任务"""
        if self.current_task_id:
            await self._state_manager.transition(
                self.current_task_id, 
                TaskStatus.COMPLETED,
                reason=description,
            )
            await self._publish_event(EventType.TASK_COMPLETED, {
                "description": description,
            })
        self.is_processing = False
        self.state = HostAgentState.COMPLETED
        logger.info(f"Task completed: {description}")
    
    async def _fail_task(self, task_id: str, error: str):
        """任务失败"""
        await self._state_manager.transition(
            task_id, 
            TaskStatus.FAILED,
            reason=error,
        )
        await self._publish_event(EventType.TASK_FAILED, {
            "error": error,
        })
        self.is_processing = False
        self.state = HostAgentState.ERROR
        logger.error(f"Task failed: {error}")
    
    async def _request_help(self, description: str):
        """请求用户帮助"""
        if self.current_task_id:
            await self._state_manager.transition(
                self.current_task_id,
                TaskStatus.NEEDS_HELP,
                reason=description,
            )
        self.is_processing = False
        self.state = HostAgentState.WAITING_CONFIRM
        logger.info(f"Help requested: {description}")
    
    # ========== 用户确认 ==========
    
    async def _request_confirmation(
        self, 
        tool_name: str, 
        tool_args: dict,
        timeout_s: float = 60.0,
    ) -> bool:
        """
        请求用户确认敏感操作
        
        工作流程:
        1. 发布 USER_CONFIRM_REQUIRED 事件
        2. 等待用户通过 approve_action() / deny_action() 响应
        3. 超时则默认拒绝
        
        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            timeout_s: 等待超时时间 (秒)
            
        Returns:
            用户是否批准
        """
        action_id = str(uuid.uuid4())
        
        # 存储待确认的操作
        if not hasattr(self, '_pending_confirmations'):
            self._pending_confirmations: Dict[str, asyncio.Event] = {}
            self._confirmation_results: Dict[str, bool] = {}
        
        # 创建等待事件
        confirmation_event = asyncio.Event()
        self._pending_confirmations[action_id] = confirmation_event
        self._confirmation_results[action_id] = False  # 默认拒绝
        
        # 发布确认请求事件
        await self._publish_event(EventType.USER_CONFIRM_REQUIRED, {
            "action_id": action_id,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "risk_level": "high",
            "timeout_s": timeout_s,
        })
        
        self.state = HostAgentState.WAITING_CONFIRM
        
        logger.info(
            f"Waiting for user confirmation: action_id={action_id}, "
            f"tool={tool_name}, timeout={timeout_s}s"
        )
        
        try:
            # 等待用户响应或超时
            await asyncio.wait_for(confirmation_event.wait(), timeout=timeout_s)
            approved = self._confirmation_results.get(action_id, False)
            
        except asyncio.TimeoutError:
            logger.warning(
                f"Confirmation timeout for action {action_id} ({tool_name}), "
                f"defaulting to deny"
            )
            approved = False
            
        finally:
            # 清理
            self._pending_confirmations.pop(action_id, None)
            self._confirmation_results.pop(action_id, None)
            self.state = HostAgentState.EXECUTING
        
        if approved:
            logger.info(f"User approved sensitive operation: {tool_name}")
        else:
            logger.info(f"User denied sensitive operation: {tool_name}")
        
        return approved
    
    async def approve_action(self, action_id: str) -> bool:
        """
        批准敏感操作 - 供前端调用
        
        Args:
            action_id: 操作 ID (从 USER_CONFIRM_REQUIRED 事件获取)
            
        Returns:
            是否成功 (action_id 是否存在)
        """
        if not hasattr(self, '_pending_confirmations'):
            return False
        
        event = self._pending_confirmations.get(action_id)
        if event:
            self._confirmation_results[action_id] = True
            event.set()
            return True
        
        logger.warning(f"Unknown action_id: {action_id}")
        return False
    
    async def deny_action(self, action_id: str) -> bool:
        """
        拒绝敏感操作 - 供前端调用
        
        Args:
            action_id: 操作 ID (从 USER_CONFIRM_REQUIRED 事件获取)
            
        Returns:
            是否成功 (action_id 是否存在)
        """
        if not hasattr(self, '_pending_confirmations'):
            return False
        
        event = self._pending_confirmations.get(action_id)
        if event:
            self._confirmation_results[action_id] = False
            event.set()
            return True
        
        logger.warning(f"Unknown action_id: {action_id}")
        return False
    
    # ========== 错误处理 ==========
    
    async def _handle_error(self, task_id: str, error: Exception) -> bool:
        """
        处理错误
        
        Args:
            task_id: 任务 ID
            error: 异常
            
        Returns:
            是否可恢复
        """
        from .errors import (
            AgentError, ClaudeAPIError, ToolExecutionError,
            WindowLostError, get_recovery_strategy,
        )
        
        # 获取恢复策略
        if isinstance(error, AgentError):
            strategy = get_recovery_strategy(error)
        else:
            # 未知错误，默认不可恢复
            return False
        
        if not strategy.retry:
            return False
        
        # 重试
        if self._retry_count < strategy.max_retries:
            self._retry_count += 1
            wait_time = strategy.backoff_base ** self._retry_count
            logger.info(f"Retrying in {wait_time}s (attempt {self._retry_count})")
            await asyncio.sleep(wait_time)
            return True
        
        return False
    
    # ========== 上下文管理 - Phase 5b 实现 ==========
    
    async def _should_compress_context(self) -> bool:
        """
        检查是否需要压缩上下文 - Phase 5b 实现
        
        使用 ContextManager 检查 token 使用率
        """
        if not hasattr(self, '_context_manager') or self._context_manager is None:
            return False
        
        return self._context_manager.should_compress(self._messages)
    
    async def _compress_context(self):
        """
        压缩上下文 - Phase 5b 实现
        
        使用 ContextManager 进行智能压缩：
        - 保留最近 N 条消息
        - 使用 Haiku 总结历史
        - 管理截图数量
        """
        if not hasattr(self, '_context_manager') or self._context_manager is None:
            return
        
        # 获取压缩前状态
        status_before = self._context_manager.get_status(self._messages)
        logger.info(f"Context before compression: {status_before['usage_percent']} ({status_before['current_tokens']} tokens)")
        
        # 管理截图数量
        self._messages = self._context_manager.manage_screenshots(self._messages)
        
        # 压缩消息历史
        self._messages = await self._context_manager.maybe_compress(self._messages)
        
        # 获取压缩后状态
        status_after = self._context_manager.get_status(self._messages)
        logger.info(f"Context after compression: {status_after['usage_percent']} ({status_after['current_tokens']} tokens)")
        
        # 发布上下文压缩事件
        await self._publish_event(EventType.CHECKPOINT_SAVED, {
            "type": "context_compressed",
            "before_tokens": status_before["current_tokens"],
            "after_tokens": status_after["current_tokens"],
            "compression_ratio": 1 - (status_after["current_tokens"] / max(status_before["current_tokens"], 1)),
        })
    
    def get_context_status(self) -> Dict[str, Any]:
        """
        获取当前上下文状态 - Phase 5b
        
        Returns:
            上下文状态信息
        """
        if not hasattr(self, '_context_manager') or self._context_manager is None:
            return {"status": "not_initialized"}
        
        return self._context_manager.get_status(self._messages)
    
    def get_llm_stats(self) -> Dict[str, Any]:
        """
        获取 LLM 统计信息 - Phase 5
        
        Returns:
            LLM 调用统计（包括缓存命中率）
        """
        if not hasattr(self, '_llm_client') or self._llm_client is None:
            return {"status": "not_initialized"}
        
        cache_stats = self._llm_client.get_cache_stats()
        return {
            "total_calls": cache_stats.total_calls,
            "input_tokens": cache_stats.input_tokens,
            "output_tokens": cache_stats.output_tokens,
            "cache_read_tokens": cache_stats.cache_read_tokens,
            "cache_write_tokens": cache_stats.cache_write_tokens,
            "cache_hit_rate": f"{cache_stats.cache_hit_rate:.1%}",
            "estimated_savings": f"{cache_stats.estimated_savings:.1%}",
        }
    
    # ========== 检查点 ==========
    
    async def _save_checkpoint(self, task_id: str):
        """保存检查点"""
        state = {
            "iteration": self._iteration_count,
            "messages": [m.to_dict() for m in self._messages],
            "blackboard": self.blackboard.to_dict() if self.blackboard else None,
            "app_agents": list(self._app_agents.keys()),
        }
        await self._task_store.save_checkpoint(task_id, self._iteration_count, state)
        
        await self._publish_event(EventType.CHECKPOINT_SAVED, {
            "iteration": self._iteration_count,
        })
        
        logger.debug(f"Checkpoint saved: iteration={self._iteration_count}")
    
    # ========== 辅助方法 ==========
    
    async def _get_task_result(self, task_id: str) -> Dict[str, Any]:
        """获取任务最终结果"""
        state = await self._state_manager.get_state(task_id)
        return {
            "task_id": task_id,
            "status": state["status"].value if state else "unknown",
            "iterations": self._iteration_count,
            "duration_s": time.time() - (self._start_time or time.time()),
            "blackboard": self.blackboard.to_dict() if self.blackboard else None,
        }
    
    async def _publish_event(self, event_type: EventType, payload: Dict[str, Any]):
        """发布事件"""
        if self._event_bus and self.current_task_id:
            event = AgentEvent.create(
                event_type=event_type,
                task_id=self.current_task_id,
                payload=payload,
                source="host_agent",
            )
            await self._event_bus.publish(event)
    
    # ========== 控制方法 ==========
    
    async def stop(self, reason: str = "User requested"):
        """停止当前任务"""
        if self.is_processing and self.current_task_id:
            await self._state_manager.transition(
                self.current_task_id,
                TaskStatus.INTERRUPTED,
                reason=reason,
            )
            self.is_processing = False
            self.state = HostAgentState.IDLE
            logger.info(f"Task stopped: {reason}")
    
    async def pause(self):
        """暂停当前任务"""
        if self.is_processing and self.current_task_id:
            await self._state_manager.transition(
                self.current_task_id,
                TaskStatus.PAUSED,
            )
            await self._save_checkpoint(self.current_task_id)
            logger.info("Task paused")
    
    async def resume(self, task_id: str) -> Dict[str, Any]:
        """
        恢复任务 - 从检查点恢复中断的任务
        
        Args:
            task_id: 要恢复的任务 ID
            
        Returns:
            任务结果
            
        Raises:
            ValueError: 任务不存在或无法恢复
        """
        if not self._initialized:
            await self.initialize()
        
        if self.is_processing:
            raise RuntimeError(f"Already processing task: {self.current_task_id}")
        
        logger.info(f"Resuming task: {task_id}")
        
        # 1. 获取任务信息
        task_info = await self._task_store.get_task(task_id)
        if not task_info:
            raise ValueError(f"Task {task_id} not found")
        
        # 2. 检查任务状态是否可恢复
        resumable_statuses = ["paused", "interrupted", "running"]
        if task_info["status"] not in resumable_statuses:
            raise ValueError(
                f"Task {task_id} is in status '{task_info['status']}', cannot resume. "
                f"Only tasks in {resumable_statuses} can be resumed."
            )
        
        # 3. 恢复检查点
        checkpoint = await self._task_store.restore_checkpoint(task_id)
        if not checkpoint:
            logger.warning(f"No checkpoint found for task {task_id}, starting from scratch")
            # 没有检查点，重新开始
            return await self.process_task(
                task_id=task_id,
                task_text=task_info["task_text"],
                target_hwnds=task_info.get("target_hwnds"),
            )
        
        # 4. 初始化任务状态
        self.is_processing = True
        self.current_task_id = task_id
        self.state = HostAgentState.EXECUTING
        self._start_time = time.time()
        self._target_hwnds = set(task_info.get("target_hwnds") or [])
        self._tool_history = []
        
        # 5. 恢复消息历史
        self._messages = []
        if "messages" in checkpoint:
            for msg_dict in checkpoint["messages"]:
                try:
                    msg = Message.from_dict(msg_dict)
                    self._messages.append(msg)
                except Exception as e:
                    logger.warning(f"Failed to restore message: {e}")
        
        # 6. 恢复迭代计数
        self._iteration_count = checkpoint.get("iteration", 0)
        self._retry_count = 0
        
        # 7. 恢复黑板状态
        if "blackboard" in checkpoint and checkpoint["blackboard"]:
            self.blackboard = Blackboard.from_dict(checkpoint["blackboard"])
        else:
            self.blackboard = Blackboard(task_id=task_id)
        
        # 8. 初始化终止检查器
        self._termination_checker = TerminationChecker(self.config.to_termination_config())
        
        # 9. 获取并发锁
        if self._target_hwnds:
            if not await self._concurrency_manager.acquire_task_slot(task_id, self._target_hwnds):
                self.is_processing = False
                raise RuntimeError("Failed to acquire task slot")
            
            if not await self._concurrency_manager.acquire_windows(self._target_hwnds, task_id):
                self._concurrency_manager.release_task_slot(task_id)
                self.is_processing = False
                raise RuntimeError("Failed to acquire window locks")
        
        try:
            # 10. 更新任务状态
            await self._state_manager.transition(task_id, TaskStatus.RUNNING)
            
            # 11. 发布恢复事件
            await self._publish_event(EventType.TASK_STARTED, {
                "resumed": True,
                "from_iteration": self._iteration_count,
                "task_text": task_info["task_text"],
            })
            
            logger.info(f"Resumed task {task_id} from iteration {self._iteration_count}")
            
            # 12. 继续运行主循环
            result = await self._run_loop(task_id, task_info["task_text"])
            
            return result
            
        except Exception as e:
            logger.exception(f"Resumed task {task_id} failed: {e}")
            await self._fail_task(task_id, str(e))
            raise
            
        finally:
            # 释放资源
            if self._target_hwnds:
                self._concurrency_manager.release_windows(self._target_hwnds)
                self._concurrency_manager.release_task_slot(task_id)
            
            self.is_processing = False
            self.current_task_id = None
            self.state = HostAgentState.IDLE
            self._target_hwnds = set()
    
    # ========== 回调设置 ==========
    
    def on_thinking(self, callback: Callable[[str], Awaitable[None]]):
        """设置思考回调"""
        self._on_thinking = callback
    
    def on_tool_start(self, callback: Callable[[str, dict], Awaitable[None]]):
        """设置工具开始回调"""
        self._on_tool_start = callback
    
    def on_tool_end(self, callback: Callable[[str, ToolResult], Awaitable[None]]):
        """设置工具结束回调"""
        self._on_tool_end = callback
    
    # ========== 资源清理 ==========
    
    async def close(self):
        """
        关闭并清理资源
        
        应在 Agent 不再使用时调用，释放：
        - LLM 客户端连接
        - Haiku 压缩客户端
        - 其他异步资源
        """
        logger.info("Closing HostAgent and releasing resources...")
        
        # 停止当前任务（如果有）
        if self.is_processing:
            await self.stop("Agent closing")
        
        # 关闭 LLM 客户端
        if hasattr(self, '_llm_client') and self._llm_client:
            try:
                await self._llm_client.close()
                logger.debug("LLM client closed")
            except Exception as e:
                logger.warning(f"Error closing LLM client: {e}")
            self._llm_client = None
        
        # 关闭 Haiku 压缩客户端（类级别单例）
        from .context_manager import ContextCompressor
        if ContextCompressor._haiku_client:
            try:
                await ContextCompressor._haiku_client.close()
                ContextCompressor._haiku_client = None
                ContextCompressor._haiku_initialized = False
                logger.debug("Haiku client closed")
            except Exception as e:
                logger.warning(f"Error closing Haiku client: {e}")
        
        # 清理视觉增强器
        self._vision_enhancer = None
        
        # 重置初始化标记
        self._initialized = False
        
        logger.info("HostAgent closed successfully")
    
    async def __aenter__(self):
        """支持 async with 语法"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """支持 async with 语法"""
        await self.close()
        return False
    
    def __repr__(self) -> str:
        return (
            f"HostAgent(state={self.state.value}, "
            f"task={self.current_task_id}, "
            f"agents={len(self._app_agents)})"
        )
