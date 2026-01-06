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
        
        # 注册内置工具
        self._register_builtin_tools()
        
        self._initialized = True
        logger.info("HostAgent initialized with Phase 3 components")
    
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
                current_tokens=0,  # TODO: 实现 token 计数
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
        """检查目标窗口是否存在"""
        if not self._target_hwnds:
            return True
        # TODO: 实现实际的窗口存在检查
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
                verified = await self._success_verifier.verify(
                    task=task_text,
                    final_screenshot=final_screenshot,
                    tool_history=self._tool_history,
                    llm_client=None,  # TODO: 传入 LLM 客户端
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
            
            # 5. 执行工具调用
            tool_results = []
            for tool_call in llm_response.tool_calls:
                result = await self._execute_tool(tool_call)
                tool_results.append(result)
                
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
    
    async def _call_llm(self) -> LLMResponse:
        """
        调用 LLM
        
        TODO: 在 Phase 5 实现实际的 Claude API 调用
        """
        # 占位实现
        from .types import StopReason
        return LLMResponse(
            content="Thinking about the task...",
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
    ) -> bool:
        """
        请求用户确认敏感操作
        
        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            
        Returns:
            用户是否批准
        """
        action_id = str(uuid.uuid4())
        
        # 发布确认请求事件
        await self._publish_event(EventType.USER_CONFIRM_REQUIRED, {
            "action_id": action_id,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "risk_level": "high",
        })
        
        self.state = HostAgentState.WAITING_CONFIRM
        
        # TODO: 实现等待用户响应的机制
        # 暂时默认拒绝
        logger.warning(f"Sensitive operation '{tool_name}' requires confirmation")
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
    
    # ========== 上下文管理 ==========
    
    async def _should_compress_context(self) -> bool:
        """检查是否需要压缩上下文"""
        # TODO: 实现 token 计数
        return False
    
    async def _compress_context(self):
        """压缩上下文"""
        # TODO: 在 Phase 5b 实现
        pass
    
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
    
    async def resume(self, task_id: str):
        """恢复任务"""
        # TODO: 实现任务恢复
        pass
    
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
    
    def __repr__(self) -> str:
        return (
            f"HostAgent(state={self.state.value}, "
            f"task={self.current_task_id}, "
            f"agents={len(self._app_agents)})"
        )
