"""
NogicOS 终止检查器 + 成功验证器
==============================

定义清晰的任务终止条件，区分 ERROR vs FAIL：

- TerminationChecker: 判断 Agent 循环是否应该终止
- SuccessVerifier: 验证任务是否真正完成（Agent 说完成不一定真完成）

参考:
- ByteBot set_task_status + termination 逻辑
- UFO ERROR vs FAIL 状态区分
- UFO AppAgent 可恢复 FAIL vs HostAgent 终态 ERROR
"""

import logging
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Protocol, TYPE_CHECKING
from enum import Enum
from datetime import datetime

if TYPE_CHECKING:
    from .types import ToolResult

logger = logging.getLogger(__name__)


class TerminationReason(Enum):
    """
    终止原因
    
    区分正常终止和异常终止
    """
    # ===== 正常终止 =====
    COMPLETED = "completed"           # 任务正常完成
    NEEDS_HELP = "needs_help"         # Agent 请求用户帮助
    
    # ===== 资源限制 =====
    MAX_ITERATIONS = "max_iterations" # 达到最大迭代次数
    TIMEOUT = "timeout"               # 任务超时
    TOKEN_LIMIT = "token_limit"       # Token 限制
    
    # ===== 失败终止 =====
    CONSECUTIVE_FAILURES = "consecutive_failures"  # 连续失败过多
    WINDOW_LOST = "window_lost"       # 目标窗口丢失
    CRITICAL_ERROR = "critical_error" # 严重错误
    
    # ===== 用户控制 =====
    USER_CANCELLED = "user_cancelled" # 用户取消
    USER_PAUSED = "user_paused"       # 用户暂停


class TerminationType(Enum):
    """终止类型 - 区分 ERROR vs FAIL"""
    SUCCESS = "success"     # 成功完成
    FAIL = "fail"           # 逻辑失败（可能可重试）
    ERROR = "error"         # 系统错误（不可恢复）
    CANCELLED = "cancelled" # 用户取消


@dataclass
class TerminationResult:
    """
    终止检查结果
    
    包含是否应该终止、原因、类型等信息
    """
    should_terminate: bool
    reason: Optional[TerminationReason] = None
    termination_type: Optional[TerminationType] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def continue_running(cls) -> "TerminationResult":
        """继续运行"""
        return cls(should_terminate=False, message="Continue")
    
    @classmethod
    def completed(cls, message: str = "Task completed") -> "TerminationResult":
        """任务完成"""
        return cls(
            should_terminate=True,
            reason=TerminationReason.COMPLETED,
            termination_type=TerminationType.SUCCESS,
            message=message,
        )
    
    @classmethod
    def failed(
        cls, 
        reason: TerminationReason, 
        message: str,
        details: Optional[Dict] = None,
    ) -> "TerminationResult":
        """任务失败"""
        return cls(
            should_terminate=True,
            reason=reason,
            termination_type=TerminationType.FAIL,
            message=message,
            details=details or {},
        )
    
    @classmethod
    def error(
        cls, 
        reason: TerminationReason, 
        message: str,
        details: Optional[Dict] = None,
    ) -> "TerminationResult":
        """系统错误"""
        return cls(
            should_terminate=True,
            reason=reason,
            termination_type=TerminationType.ERROR,
            message=message,
            details=details or {},
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "should_terminate": self.should_terminate,
            "reason": self.reason.value if self.reason else None,
            "type": self.termination_type.value if self.termination_type else None,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class TerminationConfig:
    """
    终止检查配置
    
    定义各种终止条件的阈值
    """
    # 迭代限制
    max_iterations: int = 50
    
    # 超时（秒）
    task_timeout_s: float = 1800.0  # 30 分钟
    iteration_timeout_s: float = 120.0  # 单次迭代 2 分钟
    
    # 失败容忍度
    max_consecutive_failures: int = 3
    max_total_failures: int = 10
    
    # Token 限制
    max_context_tokens: int = 180000
    
    # 无进展检测
    max_no_progress_iterations: int = 5


class TerminationChecker:
    """
    终止检查器
    
    判断 Agent 循环是否应该终止
    
    检查顺序（优先级）：
    1. set_task_status 被调用（最高）
    2. 用户取消
    3. 窗口丢失
    4. 严重错误
    5. 连续失败
    6. 最大迭代次数
    7. 超时
    8. Token 限制
    
    使用示例:
    ```python
    checker = TerminationChecker(config)
    
    result = checker.check(
        iteration=10,
        tool_results=results,
        set_task_status_called=False,
        window_exists=True,
        elapsed_time_s=60.0,
    )
    
    if result.should_terminate:
        print(f"Terminating: {result.reason.value}")
    ```
    """
    
    def __init__(self, config: Optional[TerminationConfig] = None):
        """
        初始化终止检查器
        
        Args:
            config: 终止配置
        """
        self.config = config or TerminationConfig()
        
        # 失败追踪
        self._consecutive_failures = 0
        self._total_failures = 0
        self._last_success_iteration = 0
        
        # 进度追踪
        self._last_progress_iteration = 0
        self._last_state_hash: Optional[str] = None
        
        # 用户控制
        self._user_cancelled = False
        self._user_paused = False
    
    def check(
        self, 
        iteration: int,
        tool_results: Optional[List["ToolResult"]] = None,
        set_task_status_called: bool = False,
        set_task_status_value: Optional[str] = None,
        window_exists: bool = True,
        elapsed_time_s: float = 0,
        current_tokens: int = 0,
        critical_error: Optional[str] = None,
    ) -> TerminationResult:
        """
        检查是否应该终止
        
        Args:
            iteration: 当前迭代次数
            tool_results: 工具执行结果列表
            set_task_status_called: set_task_status 工具是否被调用
            set_task_status_value: set_task_status 的值 (completed/needs_help)
            window_exists: 目标窗口是否存在
            elapsed_time_s: 已耗时（秒）
            current_tokens: 当前上下文 token 数
            critical_error: 严重错误信息
            
        Returns:
            终止检查结果
        """
        tool_results = tool_results or []
        
        # 1. set_task_status 被调用（最高优先级）
        if set_task_status_called:
            if set_task_status_value == "completed":
                return TerminationResult.completed("Task completed by agent")
            elif set_task_status_value == "needs_help":
                return TerminationResult(
                    should_terminate=True,
                    reason=TerminationReason.NEEDS_HELP,
                    termination_type=TerminationType.FAIL,  # 需要帮助算作失败
                    message="Agent needs user help",
                )
        
        # 2. 用户取消
        if self._user_cancelled:
            return TerminationResult(
                should_terminate=True,
                reason=TerminationReason.USER_CANCELLED,
                termination_type=TerminationType.CANCELLED,
                message="Cancelled by user",
            )
        
        # 3. 用户暂停
        if self._user_paused:
            return TerminationResult(
                should_terminate=True,
                reason=TerminationReason.USER_PAUSED,
                termination_type=TerminationType.CANCELLED,
                message="Paused by user",
            )
        
        # 4. 严重错误
        if critical_error:
            return TerminationResult.error(
                reason=TerminationReason.CRITICAL_ERROR,
                message=f"Critical error: {critical_error}",
                details={"error": critical_error},
            )
        
        # 5. 目标窗口丢失
        if not window_exists:
            return TerminationResult.error(
                reason=TerminationReason.WINDOW_LOST,
                message="Target window no longer exists",
            )
        
        # 6. 更新失败追踪
        self._update_failure_tracking(tool_results, iteration)
        
        # 7. 连续失败检查
        if self._consecutive_failures >= self.config.max_consecutive_failures:
            return TerminationResult.failed(
                reason=TerminationReason.CONSECUTIVE_FAILURES,
                message=f"{self._consecutive_failures} consecutive tool failures",
                details={
                    "consecutive_failures": self._consecutive_failures,
                    "max_allowed": self.config.max_consecutive_failures,
                },
            )
        
        # 8. 总失败次数检查
        if self._total_failures >= self.config.max_total_failures:
            return TerminationResult.failed(
                reason=TerminationReason.CONSECUTIVE_FAILURES,
                message=f"Total failures ({self._total_failures}) exceeded limit",
                details={
                    "total_failures": self._total_failures,
                    "max_allowed": self.config.max_total_failures,
                },
            )
        
        # 9. 最大迭代次数
        if iteration >= self.config.max_iterations:
            return TerminationResult.failed(
                reason=TerminationReason.MAX_ITERATIONS,
                message=f"Reached max iterations ({self.config.max_iterations})",
                details={
                    "iteration": iteration,
                    "max_iterations": self.config.max_iterations,
                },
            )
        
        # 10. 超时检查
        if elapsed_time_s > self.config.task_timeout_s:
            return TerminationResult.failed(
                reason=TerminationReason.TIMEOUT,
                message=f"Task timed out after {elapsed_time_s:.1f}s",
                details={
                    "elapsed_s": elapsed_time_s,
                    "timeout_s": self.config.task_timeout_s,
                },
            )
        
        # 11. Token 限制
        if current_tokens > 0 and current_tokens > self.config.max_context_tokens:
            return TerminationResult.failed(
                reason=TerminationReason.TOKEN_LIMIT,
                message=f"Context exceeds token limit ({current_tokens}/{self.config.max_context_tokens})",
                details={
                    "current_tokens": current_tokens,
                    "max_tokens": self.config.max_context_tokens,
                },
            )
        
        # 继续运行
        return TerminationResult.continue_running()
    
    def _update_failure_tracking(
        self, 
        tool_results: List["ToolResult"],
        iteration: int,
    ):
        """
        更新失败追踪
        
        Args:
            tool_results: 工具结果列表
            iteration: 当前迭代
        """
        has_failure = any(
            getattr(r, 'is_error', False) or getattr(r, 'error', None) 
            for r in tool_results
        )
        
        if has_failure:
            self._consecutive_failures += 1
            self._total_failures += 1
        else:
            # 重置连续失败计数
            self._consecutive_failures = 0
            self._last_success_iteration = iteration
    
    def cancel(self):
        """用户取消"""
        self._user_cancelled = True
    
    def pause(self):
        """用户暂停"""
        self._user_paused = True
    
    def resume(self):
        """恢复运行"""
        self._user_paused = False
    
    def reset(self):
        """重置状态（新任务）"""
        self._consecutive_failures = 0
        self._total_failures = 0
        self._last_success_iteration = 0
        self._last_progress_iteration = 0
        self._last_state_hash = None
        self._user_cancelled = False
        self._user_paused = False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "consecutive_failures": self._consecutive_failures,
            "total_failures": self._total_failures,
            "last_success_iteration": self._last_success_iteration,
            "user_cancelled": self._user_cancelled,
            "user_paused": self._user_paused,
        }


class LLMClientProtocol(Protocol):
    """LLM 客户端协议（用于类型提示）"""
    async def create_message(
        self, 
        model: str,
        max_tokens: int,
        messages: List[Dict[str, Any]],
    ) -> Any: ...


class SuccessVerifier:
    """
    成功验证器
    
    Agent 说 "completed" 不一定真的完成了。
    使用 LLM 验证任务是否真正完成。
    
    验证策略：
    1. 比对任务目标和最终截图
    2. 检查工具调用历史是否合理
    3. 使用 Haiku 模型降低成本
    
    使用示例:
    ```python
    verifier = SuccessVerifier()
    
    verified = await verifier.verify(
        task="在浏览器中搜索 Python 教程",
        final_screenshot=screenshot_base64,
        tool_history=tools_called,
        llm_client=client,
    )
    
    if not verified:
        print("Task not actually completed!")
    ```
    """
    
    VERIFICATION_PROMPT = """You are a task verification assistant. 

Task was: {task}

Agent claims the task is completed.

Tool calls made:
{tool_summary}

Please verify by looking at the final screenshot:
1. Does the screenshot show the expected result?
2. Were all necessary actions performed?
3. Is there any indication that the task failed or is incomplete?

Respond with JSON only:
{{"verified": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}
"""
    
    def __init__(
        self,
        verification_model: str = "claude-3-haiku-20240307",
        min_confidence: float = 0.7,
    ):
        """
        初始化成功验证器
        
        Args:
            verification_model: 用于验证的模型（默认 Haiku 降低成本）
            min_confidence: 最低置信度阈值
        """
        self.verification_model = verification_model
        self.min_confidence = min_confidence
    
    async def verify(
        self, 
        task: str, 
        final_screenshot: Optional[str],
        tool_history: List[Dict[str, Any]],
        llm_client: Optional[Any] = None,
    ) -> bool:
        """
        验证任务是否真正完成
        
        Args:
            task: 原始任务描述
            final_screenshot: 最终截图（base64）
            tool_history: 工具调用历史
            llm_client: LLM 客户端（可选，无则跳过验证）
            
        Returns:
            是否真正完成
        """
        # 无 LLM 客户端，默认通过
        if llm_client is None:
            logger.warning("No LLM client provided, skipping verification")
            return True
        
        # 无截图，无法验证
        if not final_screenshot:
            logger.warning("No screenshot provided, skipping verification")
            return True
        
        try:
            # 构建验证 prompt
            tool_summary = self._summarize_tools(tool_history)
            prompt = self.VERIFICATION_PROMPT.format(
                task=task,
                tool_summary=tool_summary,
            )
            
            # 构建消息
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": final_screenshot,
                        }
                    }
                ]
            }]
            
            # 调用 LLM
            response = await llm_client.messages.create(
                model=self.verification_model,
                max_tokens=200,
                messages=messages,
            )
            
            # 解析响应
            result = self._parse_response(response)
            
            if result is None:
                logger.warning("Failed to parse verification response")
                return True  # 解析失败默认通过
            
            verified = result.get("verified", True)
            confidence = result.get("confidence", 1.0)
            reason = result.get("reason", "")
            
            logger.info(
                f"Verification result: verified={verified}, "
                f"confidence={confidence:.2f}, reason={reason}"
            )
            
            # 置信度不足时也认为未验证
            if confidence < self.min_confidence:
                logger.warning(
                    f"Confidence too low: {confidence:.2f} < {self.min_confidence}"
                )
                return False
            
            return verified
            
        except Exception as e:
            logger.error(f"Verification failed with error: {e}")
            return True  # 验证出错默认通过
    
    def _summarize_tools(self, tool_history: List[Dict[str, Any]]) -> str:
        """
        汇总工具调用历史
        
        Args:
            tool_history: 工具调用列表
            
        Returns:
            汇总文本
        """
        if not tool_history:
            return "No tools were called"
        
        lines = []
        for i, tool in enumerate(tool_history[-10:], 1):  # 最多显示最近 10 个
            name = tool.get("name", "unknown")
            args = tool.get("arguments", {})
            success = not tool.get("error")
            status = "✓" if success else "✗"
            
            # 简化参数显示
            args_str = ", ".join(
                f"{k}={str(v)[:30]}" 
                for k, v in list(args.items())[:3]
            )
            
            lines.append(f"{i}. {status} {name}({args_str})")
        
        if len(tool_history) > 10:
            lines.append(f"... and {len(tool_history) - 10} more tools")
        
        return "\n".join(lines)
    
    def _parse_response(self, response: Any) -> Optional[Dict[str, Any]]:
        """
        解析 LLM 响应
        
        Args:
            response: LLM 响应
            
        Returns:
            解析后的字典，或 None
        """
        try:
            # 获取响应文本
            if hasattr(response, 'content') and response.content:
                text = response.content[0].text
            else:
                return None
            
            # 尝试解析 JSON
            # 处理可能的 markdown 代码块
            text = text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            
            return json.loads(text)
            
        except (json.JSONDecodeError, AttributeError, IndexError) as e:
            logger.debug(f"Failed to parse response: {e}")
            return None


@dataclass
class TaskStatusCall:
    """set_task_status 调用记录"""
    status: str  # "completed" or "needs_help"
    description: str
    timestamp: datetime = field(default_factory=datetime.now)


def detect_set_task_status(tool_calls: List[Dict[str, Any]]) -> Optional[TaskStatusCall]:
    """
    检测 tool_calls 中是否有 set_task_status 调用
    
    Args:
        tool_calls: 工具调用列表
        
    Returns:
        TaskStatusCall 或 None
    """
    for call in tool_calls:
        if call.get("name") == "set_task_status":
            args = call.get("arguments", {})
            return TaskStatusCall(
                status=args.get("status", ""),
                description=args.get("description", ""),
            )
    return None


# ========== 导出 ==========

__all__ = [
    "TerminationReason",
    "TerminationType",
    "TerminationResult",
    "TerminationConfig",
    "TerminationChecker",
    "SuccessVerifier",
    "TaskStatusCall",
    "detect_set_task_status",
]
