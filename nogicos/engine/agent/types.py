"""
NogicOS 核心数据类型
====================

定义 Agent 系统的核心数据结构。

类型:
- TaskStatus: 任务状态（参考 ByteBot）
- AgentStatus: Agent 状态（参考 UFO）
- ToolResult: 工具执行结果（参考 Anthropic）
- ToolCall: 工具调用请求
- Message: 消息格式

参考:
- Anthropic Computer Use ToolResult
- ByteBot TaskStatus
- LangGraph Message
- UFO Agent Status
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import json


# ========== 状态枚举（统一定义位置）==========

class TaskStatus(Enum):
    """
    任务状态 - 参考 ByteBot
    
    状态流转:
    PENDING -> RUNNING -> COMPLETED/FAILED/NEEDS_HELP
    RUNNING -> PAUSED -> RUNNING
    RUNNING -> INTERRUPTED -> RUNNING/CANCELLED
    """
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    NEEDS_HELP = "needs_help"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


class AgentStatus(Enum):
    """
    Agent 状态 - 参考 UFO
    
    IDLE: 空闲，等待任务
    ACTIVE: 正在执行
    PAUSED: 暂停中
    CONFIRM: 等待用户确认
    """
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    CONFIRM = "confirm"


# ========== 工具相关类型 ==========

@dataclass(frozen=True)
class ToolResult:
    """
    工具执行结果 - 参考 Anthropic
    
    不可变数据类，确保结果不会被意外修改
    
    属性:
        output: 成功时的输出文本
        error: 错误时的错误信息
        base64_image: 截图数据 (base64 编码)
        hwnd: 来源窗口句柄 (NogicOS 独有)
        duration_ms: 执行时间 (毫秒)
    """
    output: Optional[str] = None
    error: Optional[str] = None
    base64_image: Optional[str] = None
    hwnd: Optional[int] = None  # NogicOS 独有
    duration_ms: float = 0.0
    
    @property
    def is_error(self) -> bool:
        """是否为错误结果"""
        return self.error is not None
    
    @property
    def is_success(self) -> bool:
        """是否成功"""
        return self.error is None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        if self.output is not None:
            result["output"] = self.output
        if self.error is not None:
            result["error"] = self.error
        if self.base64_image is not None:
            result["base64_image"] = self.base64_image
        if self.hwnd is not None:
            result["hwnd"] = self.hwnd
        if self.duration_ms > 0:
            result["duration_ms"] = self.duration_ms
        return result
    
    @classmethod
    def success(
        cls, 
        output: str, 
        base64_image: Optional[str] = None,
        hwnd: Optional[int] = None,
        duration_ms: float = 0.0,
    ) -> "ToolResult":
        """创建成功结果"""
        return cls(
            output=output,
            base64_image=base64_image,
            hwnd=hwnd,
            duration_ms=duration_ms,
        )
    
    @classmethod
    def failure(
        cls, 
        error: str,
        hwnd: Optional[int] = None,
        duration_ms: float = 0.0,
    ) -> "ToolResult":
        """创建失败结果"""
        return cls(
            error=error,
            hwnd=hwnd,
            duration_ms=duration_ms,
        )


@dataclass
class ToolCall:
    """
    工具调用请求
    
    从 LLM 响应中解析出的工具调用
    """
    id: str                          # 调用 ID
    name: str                        # 工具名称
    arguments: Dict[str, Any]        # 参数字典
    hwnd: Optional[int] = None       # 目标窗口 (可选)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "hwnd": self.hwnd,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCall":
        """从字典创建"""
        return cls(
            id=data["id"],
            name=data["name"],
            arguments=data.get("arguments", {}),
            hwnd=data.get("hwnd"),
        )


# ========== 消息类型 ==========

class MessageRole(Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class Message:
    """
    消息格式 - 对齐 LangGraph
    
    支持文本、图片、工具调用、工具结果等内容类型
    """
    role: MessageRole
    content: Union[str, List[Dict[str, Any]]]
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None  # 工具结果关联的调用 ID
    name: Optional[str] = None          # 工具名称（role=tool 时）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为 Claude API 格式"""
        result = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.name:
            result["name"] = self.name
        return result
    
    @classmethod
    def user(cls, content: str) -> "Message":
        """创建用户消息"""
        return cls(role=MessageRole.USER, content=content)
    
    @classmethod
    def assistant(
        cls, 
        content: str, 
        tool_calls: Optional[List[ToolCall]] = None,
    ) -> "Message":
        """创建助手消息"""
        return cls(role=MessageRole.ASSISTANT, content=content, tool_calls=tool_calls)
    
    @classmethod
    def tool(cls, tool_call_id: str, name: str, content: str) -> "Message":
        """创建工具结果消息"""
        return cls(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        )
    
    @classmethod
    def system(cls, content: str) -> "Message":
        """创建系统消息"""
        return cls(role=MessageRole.SYSTEM, content=content)


# ========== 上下文类型 ==========

@dataclass
class WindowContext:
    """
    窗口上下文 - NogicOS 独有
    
    描述目标窗口的当前状态
    """
    hwnd: int
    title: str
    app_type: str  # "browser", "desktop", "ide"
    bounds: Dict[str, int]  # x, y, width, height
    is_foreground: bool
    screenshot_id: Optional[str] = None
    ocr_text: Optional[str] = None
    ui_elements: Optional[List[Dict[str, Any]]] = None


@dataclass
class AgentContext:
    """
    Agent 上下文
    
    包含执行任务所需的所有上下文信息
    """
    task_id: str
    task_text: str
    windows: List[WindowContext]
    messages: List[Message]
    iteration: int = 0
    current_hwnd: Optional[int] = None
    
    def get_current_window(self) -> Optional[WindowContext]:
        """获取当前窗口上下文"""
        if self.current_hwnd is None:
            return None
        for w in self.windows:
            if w.hwnd == self.current_hwnd:
                return w
        return None


# ========== 工具定义类型 ==========

@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # "string", "integer", "number", "boolean", "array", "object"
    description: str
    required: bool = False
    enum: Optional[List[str]] = None
    default: Optional[Any] = None


@dataclass
class ToolDefinition:
    """
    工具定义 - 用于生成 Claude API 格式
    
    参考 Anthropic tool schema
    """
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    supports_hwnd: bool = False      # 是否支持窗口隔离
    is_sensitive: bool = False       # 是否为敏感操作
    category: str = "general"        # 工具分类
    
    def to_claude_schema(self) -> Dict[str, Any]:
        """转换为 Claude API 工具定义格式"""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        }


# ========== 响应类型 ==========

class StopReason(Enum):
    """停止原因"""
    END_TURN = "end_turn"       # 正常结束
    TOOL_USE = "tool_use"       # 需要执行工具
    MAX_TOKENS = "max_tokens"   # 达到 token 限制
    STOP_SEQUENCE = "stop_sequence"  # 遇到停止序列


@dataclass
class LLMResponse:
    """
    LLM 响应
    
    封装 Claude API 响应
    """
    content: str
    stop_reason: StopReason
    tool_calls: List[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    
    @property
    def needs_tool_execution(self) -> bool:
        """是否需要执行工具"""
        return self.stop_reason == StopReason.TOOL_USE and len(self.tool_calls) > 0
    
    @property
    def is_final(self) -> bool:
        """是否为最终响应"""
        return self.stop_reason == StopReason.END_TURN


# ========== 类型别名 ==========

# 消息历史
MessageHistory = List[Message]

# 工具结果映射
ToolResultMap = Dict[str, ToolResult]

# 窗口句柄
HWND = int
