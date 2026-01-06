"""
NogicOS Agent 错误分类
======================

定义 Agent 系统的错误层级，区分可恢复和不可恢复错误。

参考:
- UFO ERROR vs FAIL 状态区分
- ByteBot 错误处理策略
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any


class ErrorSeverity(Enum):
    """错误严重级别"""
    WARNING = "warning"      # 警告，不影响执行
    ERROR = "error"          # 错误，可重试/降级
    CRITICAL = "critical"    # 严重错误，需要停止
    FATAL = "fatal"          # 致命错误，紧急停止


class ErrorCategory(Enum):
    """错误分类"""
    LLM = "llm"              # LLM 相关错误
    TOOL = "tool"            # 工具执行错误
    WINDOW = "window"        # 窗口相关错误
    NETWORK = "network"      # 网络错误
    STATE = "state"          # 状态管理错误
    CONCURRENCY = "concurrency"  # 并发控制错误
    SECURITY = "security"    # 安全错误
    VALIDATION = "validation"  # 验证错误
    UNKNOWN = "unknown"      # 未知错误


class AgentError(Exception):
    """
    Agent 错误基类
    
    所有 Agent 相关错误都应继承此类，提供：
    - 是否可恢复标识
    - 错误分类
    - 重试建议
    """
    
    recoverable: bool = True
    category: ErrorCategory = ErrorCategory.UNKNOWN
    severity: ErrorSeverity = ErrorSeverity.ERROR
    
    def __init__(
        self, 
        message: str,
        details: Optional[dict] = None,
        cause: Optional[Exception] = None,
    ):
        """
        初始化错误
        
        Args:
            message: 错误消息
            details: 附加详情
            cause: 原始异常
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "recoverable": self.recoverable,
            "details": self.details,
        }
    
    @property
    def should_retry(self) -> bool:
        """是否应该重试"""
        return self.recoverable and self.severity != ErrorSeverity.FATAL
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r}, recoverable={self.recoverable})"


# ========== LLM 相关错误 ==========

class LLMError(AgentError):
    """LLM 错误基类"""
    category = ErrorCategory.LLM


class ClaudeAPIError(LLMError):
    """
    Claude API 错误（可重试）
    
    包括：
    - 速率限制
    - 服务器错误
    - 超时
    """
    recoverable = True
    severity = ErrorSeverity.ERROR
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.retry_after = retry_after
        self.details["status_code"] = status_code
        self.details["retry_after"] = retry_after


class RateLimitError(ClaudeAPIError):
    """速率限制错误"""
    
    def __init__(self, message: str = "API rate limit exceeded", **kwargs):
        super().__init__(message, **kwargs)


class TokenLimitError(LLMError):
    """Token 限制错误"""
    recoverable = True  # 可通过压缩上下文恢复
    
    def __init__(
        self, 
        message: str = "Context exceeds token limit",
        current_tokens: int = 0,
        max_tokens: int = 0,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.current_tokens = current_tokens
        self.max_tokens = max_tokens
        self.details["current_tokens"] = current_tokens
        self.details["max_tokens"] = max_tokens


class LLMResponseError(LLMError):
    """LLM 响应解析错误"""
    recoverable = True
    
    def __init__(self, message: str, raw_response: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.raw_response = raw_response
        self.details["raw_response"] = raw_response[:500] if raw_response else None


# ========== 工具执行错误 ==========

class ToolError(AgentError):
    """工具错误基类"""
    category = ErrorCategory.TOOL


class ToolExecutionError(ToolError):
    """
    工具执行错误（可降级）
    
    工具执行失败，但可以让 LLM 知道并调整策略
    """
    recoverable = True
    severity = ErrorSeverity.ERROR
    
    def __init__(
        self, 
        message: str, 
        tool_name: str,
        tool_args: Optional[dict] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.details["tool_name"] = tool_name
        self.details["tool_args"] = tool_args


class ToolNotFoundError(ToolError):
    """工具不存在错误"""
    recoverable = True  # 可以告知 LLM 重新选择
    
    def __init__(self, tool_name: str, **kwargs):
        super().__init__(f"Tool '{tool_name}' not found", **kwargs)
        self.tool_name = tool_name
        self.details["tool_name"] = tool_name


class ToolValidationError(ToolError):
    """工具参数验证错误"""
    recoverable = True
    category = ErrorCategory.VALIDATION
    
    def __init__(
        self, 
        message: str,
        tool_name: str,
        validation_errors: Optional[list] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.tool_name = tool_name
        self.validation_errors = validation_errors or []
        self.details["tool_name"] = tool_name
        self.details["validation_errors"] = validation_errors


class ToolTimeoutError(ToolError):
    """工具执行超时"""
    recoverable = True
    
    def __init__(
        self, 
        tool_name: str, 
        timeout_ms: int,
        **kwargs,
    ):
        super().__init__(
            f"Tool '{tool_name}' timed out after {timeout_ms}ms",
            **kwargs,
        )
        self.tool_name = tool_name
        self.timeout_ms = timeout_ms
        self.details["tool_name"] = tool_name
        self.details["timeout_ms"] = timeout_ms


# ========== 窗口相关错误 ==========

class WindowError(AgentError):
    """窗口错误基类"""
    category = ErrorCategory.WINDOW


class WindowLostError(WindowError):
    """
    目标窗口丢失（不可恢复）
    
    窗口已关闭或不可访问，任务无法继续
    """
    recoverable = False
    severity = ErrorSeverity.CRITICAL
    
    def __init__(self, hwnd: int, window_title: Optional[str] = None, **kwargs):
        message = f"Window lost: hwnd={hwnd}"
        if window_title:
            message += f" ('{window_title}')"
        super().__init__(message, **kwargs)
        self.hwnd = hwnd
        self.window_title = window_title
        self.details["hwnd"] = hwnd
        self.details["window_title"] = window_title


class WindowNotFocusableError(WindowError):
    """窗口无法获取焦点"""
    recoverable = True
    
    def __init__(self, hwnd: int, reason: str = "", **kwargs):
        super().__init__(f"Window {hwnd} cannot be focused: {reason}", **kwargs)
        self.hwnd = hwnd
        self.details["hwnd"] = hwnd
        self.details["reason"] = reason


class WindowLockedError(WindowError):
    """窗口被其他任务锁定"""
    recoverable = True  # 可以等待
    
    def __init__(self, hwnd: int, locked_by: str, **kwargs):
        super().__init__(
            f"Window {hwnd} is locked by task '{locked_by}'",
            **kwargs,
        )
        self.hwnd = hwnd
        self.locked_by = locked_by
        self.details["hwnd"] = hwnd
        self.details["locked_by"] = locked_by


# ========== 状态管理错误 ==========

class StateError(AgentError):
    """状态管理错误基类"""
    category = ErrorCategory.STATE


class InvalidStateTransitionError(StateError):
    """非法状态转换"""
    recoverable = False
    
    def __init__(
        self, 
        current_state: str, 
        target_state: str,
        valid_targets: Optional[list] = None,
        **kwargs,
    ):
        super().__init__(
            f"Invalid transition: {current_state} -> {target_state}",
            **kwargs,
        )
        self.current_state = current_state
        self.target_state = target_state
        self.valid_targets = valid_targets or []
        self.details["current_state"] = current_state
        self.details["target_state"] = target_state
        self.details["valid_targets"] = valid_targets


class TaskNotFoundError(StateError):
    """任务不存在"""
    recoverable = False
    
    def __init__(self, task_id: str, **kwargs):
        super().__init__(f"Task '{task_id}' not found", **kwargs)
        self.task_id = task_id
        self.details["task_id"] = task_id


class CheckpointError(StateError):
    """检查点错误"""
    recoverable = True


# ========== 并发控制错误 ==========

class ConcurrencyError(AgentError):
    """并发控制错误基类"""
    category = ErrorCategory.CONCURRENCY


class TooManyTasksError(ConcurrencyError):
    """
    任务过多（等待）
    
    已达到最大并发任务数，需要等待
    """
    recoverable = True
    severity = ErrorSeverity.WARNING
    
    def __init__(
        self, 
        current_count: int, 
        max_count: int,
        **kwargs,
    ):
        super().__init__(
            f"Too many tasks: {current_count}/{max_count}",
            **kwargs,
        )
        self.current_count = current_count
        self.max_count = max_count
        self.details["current_count"] = current_count
        self.details["max_count"] = max_count


class ResourceLockError(ConcurrencyError):
    """资源锁定错误"""
    recoverable = True
    
    def __init__(self, resource: str, **kwargs):
        super().__init__(f"Resource '{resource}' is locked", **kwargs)
        self.resource = resource
        self.details["resource"] = resource


# ========== 安全错误 ==========

class SecurityError(AgentError):
    """安全错误基类"""
    category = ErrorCategory.SECURITY
    recoverable = False
    severity = ErrorSeverity.CRITICAL


class UnauthorizedActionError(SecurityError):
    """未授权操作"""
    
    def __init__(self, action: str, reason: str = "", **kwargs):
        super().__init__(f"Unauthorized action '{action}': {reason}", **kwargs)
        self.action = action
        self.details["action"] = action
        self.details["reason"] = reason


class SensitiveOperationDeniedError(SecurityError):
    """敏感操作被拒绝"""
    
    def __init__(self, operation: str, **kwargs):
        super().__init__(
            f"Sensitive operation '{operation}' requires user confirmation",
            **kwargs,
        )
        self.operation = operation
        self.details["operation"] = operation


class PromptInjectionError(SecurityError):
    """Prompt 注入检测"""
    severity = ErrorSeverity.FATAL
    
    def __init__(self, detected_pattern: str = "", **kwargs):
        super().__init__("Potential prompt injection detected", **kwargs)
        self.detected_pattern = detected_pattern
        self.details["detected_pattern"] = detected_pattern[:100]  # 限制长度


# ========== 严重错误 ==========

class CriticalError(AgentError):
    """
    严重错误（紧急停止）
    
    需要立即停止任务，保存状态
    """
    recoverable = False
    severity = ErrorSeverity.CRITICAL
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)


class FatalError(AgentError):
    """
    致命错误
    
    系统级错误，需要人工介入
    """
    recoverable = False
    severity = ErrorSeverity.FATAL


# ========== 错误恢复策略 ==========

@dataclass
class RecoveryStrategy:
    """错误恢复策略"""
    retry: bool = False           # 是否重试
    max_retries: int = 3          # 最大重试次数
    backoff_base: float = 2.0     # 退避基数（秒）
    fallback: Optional[str] = None  # 降级策略
    notify_user: bool = False     # 是否通知用户


def get_recovery_strategy(error: AgentError) -> RecoveryStrategy:
    """
    根据错误类型获取恢复策略
    
    Args:
        error: Agent 错误
        
    Returns:
        恢复策略
    """
    if isinstance(error, RateLimitError):
        return RecoveryStrategy(
            retry=True,
            max_retries=5,
            backoff_base=error.retry_after or 5.0,
        )
    
    elif isinstance(error, ClaudeAPIError):
        return RecoveryStrategy(
            retry=True,
            max_retries=3,
            backoff_base=2.0,
        )
    
    elif isinstance(error, TokenLimitError):
        return RecoveryStrategy(
            retry=True,
            max_retries=1,
            fallback="compress_context",
        )
    
    elif isinstance(error, ToolExecutionError):
        return RecoveryStrategy(
            retry=True,
            max_retries=2,
            fallback="inform_llm",
        )
    
    elif isinstance(error, WindowLostError):
        return RecoveryStrategy(
            retry=False,
            notify_user=True,
        )
    
    elif isinstance(error, TooManyTasksError):
        return RecoveryStrategy(
            retry=True,
            max_retries=10,
            backoff_base=1.0,
        )
    
    elif isinstance(error, SecurityError):
        return RecoveryStrategy(
            retry=False,
            notify_user=True,
        )
    
    elif error.recoverable:
        return RecoveryStrategy(retry=True, max_retries=2)
    
    else:
        return RecoveryStrategy(retry=False, notify_user=True)
