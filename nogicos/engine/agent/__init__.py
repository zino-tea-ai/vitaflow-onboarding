# -*- coding: utf-8 -*-
"""
NogicOS Agent - Pure ReAct Agent with Plan-Execute capabilities

Components:
- ReActAgent: Core Think-Act-Observe loop
- TaskPlanner: Complex task decomposition and replanning
- TaskClassifier: Intelligent task routing (browser/local/mixed)
- AgentMode: Cursor-style interaction modes (Agent/Ask/Plan)
- Event System: Unified communication via EventBus (Phase 0)
"""

from .react_agent import ReActAgent, AgentResult
from .planner import TaskPlanner, Plan, PlanExecuteState, is_simple_task
from .classifier import TaskClassifier, TaskType, TaskComplexity, ClassificationResult
from .modes import AgentMode, ModeRouter, get_mode_router, ModeConfig
from .imports import get_available_features

# Phase 0: 通信契约层
from .events import (
    EventType, EventPriority, AgentEvent,
    task_started_event, task_completed_event, task_failed_event,
    tool_start_event, tool_end_event, tool_error_event,
    confirm_required_event, llm_chunk_event,
)
from .event_bus import EventBus, get_event_bus, set_event_bus, on_event, on_all_events
from .ws_adapter import (
    WebSocketEventAdapter, get_ws_adapter, set_ws_adapter,
    SecurityError, ValidationError,
)

# Phase 0.25: 性能基础设施
from .async_db import AsyncTaskStore, get_task_store, set_task_store
from .screenshot_manager import ScreenshotManager, get_screenshot_manager, set_screenshot_manager
from .incremental_checkpoint import IncrementalCheckpointer, create_checkpointer

# Phase 0.5: 状态真相源
from .state_manager import (
    TaskStateManager, get_state_manager, set_state_manager,
    TaskStatus, AgentStatus, TaskState,
    InvalidTransitionError, TaskNotFoundError,
)

# Phase 1: 核心数据结构
from .types import (
    ToolResult, ToolCall, ToolDefinition, ToolParameter,
    Message, MessageRole, MessageHistory,
    WindowContext, AgentContext,
    LLMResponse, StopReason,
    HWND,
)
from .validators import (
    ToolCallValidator, SecurityValidator,
    ValidationResult, ValidationError,
)

__all__ = [
    # Core Agent
    'ReActAgent',
    'AgentResult',
    # Planning
    'TaskPlanner',
    'Plan',
    'PlanExecuteState',
    'is_simple_task',
    # Classification
    'TaskClassifier',
    'TaskType',
    'TaskComplexity',
    'ClassificationResult',
    # Modes
    'AgentMode',
    'ModeRouter',
    'ModeConfig',
    'get_mode_router',
    # Utils
    'get_available_features',
    # Event System (Phase 0)
    'EventType',
    'EventPriority',
    'AgentEvent',
    'EventBus',
    'get_event_bus',
    'set_event_bus',
    'on_event',
    'on_all_events',
    'WebSocketEventAdapter',
    'get_ws_adapter',
    'set_ws_adapter',
    'SecurityError',
    'ValidationError',
    # Event Factory Functions
    'task_started_event',
    'task_completed_event',
    'task_failed_event',
    'tool_start_event',
    'tool_end_event',
    'tool_error_event',
    'confirm_required_event',
    'llm_chunk_event',
    # Performance Infrastructure (Phase 0.25)
    'AsyncTaskStore',
    'get_task_store',
    'set_task_store',
    'ScreenshotManager',
    'get_screenshot_manager',
    'set_screenshot_manager',
    'IncrementalCheckpointer',
    'create_checkpointer',
    # State Management (Phase 0.5)
    'TaskStateManager',
    'get_state_manager',
    'set_state_manager',
    'TaskStatus',
    'AgentStatus',
    'TaskState',
    'InvalidTransitionError',
    'TaskNotFoundError',
    # Core Types (Phase 1)
    'ToolResult',
    'ToolCall',
    'ToolDefinition',
    'ToolParameter',
    'Message',
    'MessageRole',
    'MessageHistory',
    'WindowContext',
    'AgentContext',
    'LLMResponse',
    'StopReason',
    'HWND',
    'ToolCallValidator',
    'SecurityValidator',
    'ValidationResult',
]
