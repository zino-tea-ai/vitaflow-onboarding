# -*- coding: utf-8 -*-
"""
NogicOS Stream Protocol - Streaming Message Types

Defines the streaming message protocol for real-time AI interaction,
inspired by Continue's ToolCallState and LobeChat's Chain of Thought.

Architecture:
    Backend (Python)          Frontend (JavaScript)
         |                          |
    StreamChunk ────WebSocket────► updateMessage()
         |                          |
    thinking/content/tool ─────► ThinkingBubble/ToolCard

Message Types:
    - thinking: AI reasoning process (Chain of Thought)
    - content: Final response text (streaming)
    - tool_start: Tool call initiated
    - tool_args: Tool arguments (streaming)
    - tool_result: Tool execution result
    - artifact: Generated file/output
    - plan_update: Plan progress update
    - confirm: Request user confirmation
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Any, List, Literal
from enum import Enum
import json
import time
import uuid


# ============================================================================
# Enums
# ============================================================================

class ChunkType(str, Enum):
    """Stream chunk types"""
    THINKING = "thinking"           # AI reasoning/CoT
    CONTENT = "content"             # Response text
    TOOL_START = "tool_start"       # Tool call started
    TOOL_ARGS = "tool_args"         # Tool arguments (streaming)
    TOOL_RESULT = "tool_result"     # Tool execution result
    ARTIFACT = "artifact"           # Generated file/output
    PLAN_UPDATE = "plan_update"     # Plan progress
    CONFIRM = "confirm"             # Request confirmation
    ERROR = "error"                 # Error occurred
    COMPLETE = "complete"           # Stream complete


class ToolCallStatus(str, Enum):
    """Tool call lifecycle states (Continue-style)"""
    GENERATING = "generating"       # Generating arguments
    GENERATED = "generated"         # Arguments ready, awaiting execution
    CALLING = "calling"             # Currently executing
    DONE = "done"                   # Completed successfully
    ERRORED = "errored"             # Execution failed
    CANCELED = "canceled"           # Canceled by user


class ArtifactType(str, Enum):
    """Output artifact types"""
    CODE = "code"
    FILE = "file"
    CHART = "chart"
    TABLE = "table"
    MARKDOWN = "markdown"
    JSON = "json"


class PlanStepStatus(str, Enum):
    """Plan step states"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ThinkingContent:
    """AI reasoning/thinking content"""
    text: str
    is_complete: bool = False
    duration_ms: Optional[int] = None  # Thinking duration
    
    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "isComplete": self.is_complete,
            "durationMs": self.duration_ms,
        }


@dataclass
class ToolCallState:
    """Tool call state machine (Continue-style)"""
    id: str
    name: str
    status: ToolCallStatus = ToolCallStatus.GENERATING
    arguments: dict = field(default_factory=dict)
    arguments_text: str = ""  # Streaming arguments as text
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    @property
    def duration_ms(self) -> Optional[int]:
        if self.end_time:
            return int((self.end_time - self.start_time) * 1000)
        return None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "arguments": self.arguments,
            "argumentsText": self.arguments_text,
            "result": self.result,
            "error": self.error,
            "durationMs": self.duration_ms,
        }


@dataclass
class Artifact:
    """Output artifact (file, code, etc.)"""
    id: str
    type: ArtifactType
    title: str
    content: str
    language: Optional[str] = None  # For code artifacts
    preview: bool = True
    file_path: Optional[str] = None  # For file artifacts
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "content": self.content,
            "language": self.language,
            "preview": self.preview,
            "filePath": self.file_path,
        }


@dataclass
class PlanStep:
    """Single step in execution plan"""
    id: str
    index: int
    title: str
    description: str = ""
    status: PlanStepStatus = PlanStepStatus.PENDING
    progress: float = 0.0  # 0-1
    result: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)  # Artifact IDs
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "index": self.index,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "artifacts": self.artifacts,
        }


@dataclass
class Plan:
    """Execution plan with multiple steps"""
    id: str
    title: str
    steps: List[PlanStep] = field(default_factory=list)
    current_step: int = 0
    total_time_ms: Optional[int] = None
    
    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == PlanStepStatus.COMPLETED)
        return completed / len(self.steps)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "steps": [s.to_dict() for s in self.steps],
            "currentStep": self.current_step,
            "progress": self.progress,
            "totalTimeMs": self.total_time_ms,
        }


# ============================================================================
# Stream Chunk
# ============================================================================

@dataclass
class StreamChunk:
    """
    Single chunk in the message stream.
    
    This is the atomic unit sent over WebSocket for real-time updates.
    """
    type: ChunkType
    data: Any
    message_id: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def to_json(self) -> str:
        """Serialize to JSON for WebSocket"""
        payload = {
            "type": self.type.value,
            "messageId": self.message_id,
            "timestamp": self.timestamp,
            "data": self._serialize_data(),
        }
        return json.dumps(payload, ensure_ascii=False)
    
    def _serialize_data(self) -> Any:
        """Serialize data based on type"""
        if hasattr(self.data, "to_dict"):
            return self.data.to_dict()
        elif isinstance(self.data, dict):
            return self.data
        elif isinstance(self.data, list):
            return [
                item.to_dict() if hasattr(item, "to_dict") else item
                for item in self.data
            ]
        else:
            return self.data


# ============================================================================
# Stream Builder
# ============================================================================

class StreamBuilder:
    """
    Builder for creating stream chunks.
    
    Maintains state across a streaming session (message_id, plan state, etc.)
    
    Usage:
        builder = StreamBuilder()
        
        # Send thinking
        yield builder.thinking("Analyzing the request...")
        yield builder.thinking("Found 3 relevant patterns", complete=True)
        
        # Send tool call
        tool_id = builder.start_tool("browser_navigate")
        yield builder.tool_args(tool_id, '{"url": "https://...')
        yield builder.tool_result(tool_id, {"success": True})
        
        # Send content
        yield builder.content("Here are the results...")
        
        # Complete
        yield builder.complete()
    """
    
    def __init__(self, message_id: Optional[str] = None):
        self.message_id = message_id or str(uuid.uuid4())[:8]
        self._thinking_start: Optional[float] = None
        self._tool_calls: dict[str, ToolCallState] = {}
        self._plan: Optional[Plan] = None
        self._artifacts: dict[str, Artifact] = {}
    
    def thinking(
        self,
        text: str,
        complete: bool = False,
    ) -> StreamChunk:
        """Create thinking chunk (Chain of Thought)"""
        if self._thinking_start is None:
            self._thinking_start = time.time()
        
        duration_ms = None
        if complete and self._thinking_start:
            duration_ms = int((time.time() - self._thinking_start) * 1000)
            self._thinking_start = None
        
        return StreamChunk(
            type=ChunkType.THINKING,
            message_id=self.message_id,
            data=ThinkingContent(
                text=text,
                is_complete=complete,
                duration_ms=duration_ms,
            ),
        )
    
    def content(self, text: str) -> StreamChunk:
        """Create content chunk (streaming response text)"""
        return StreamChunk(
            type=ChunkType.CONTENT,
            message_id=self.message_id,
            data={"text": text},
        )
    
    def start_tool(self, name: str, tool_id: Optional[str] = None) -> str:
        """Start a tool call, returns tool_id"""
        tool_id = tool_id or str(uuid.uuid4())[:8]
        self._tool_calls[tool_id] = ToolCallState(
            id=tool_id,
            name=name,
            status=ToolCallStatus.GENERATING,
        )
        return tool_id
    
    def tool_start(self, tool_id: str, name: str) -> StreamChunk:
        """Create tool start chunk"""
        if tool_id not in self._tool_calls:
            self.start_tool(name, tool_id)
        
        return StreamChunk(
            type=ChunkType.TOOL_START,
            message_id=self.message_id,
            data=self._tool_calls[tool_id],
        )
    
    def tool_args(
        self,
        tool_id: str,
        args_text: str,
        is_complete: bool = False,
    ) -> StreamChunk:
        """Create tool arguments chunk (streaming)"""
        if tool_id in self._tool_calls:
            tool = self._tool_calls[tool_id]
            tool.arguments_text += args_text
            
            if is_complete:
                tool.status = ToolCallStatus.GENERATED
                # Try to parse as JSON
                try:
                    tool.arguments = json.loads(tool.arguments_text)
                except:
                    pass
        
        return StreamChunk(
            type=ChunkType.TOOL_ARGS,
            message_id=self.message_id,
            data={
                "toolId": tool_id,
                "argsText": args_text,
                "isComplete": is_complete,
            },
        )
    
    def tool_calling(self, tool_id: str) -> StreamChunk:
        """Mark tool as executing"""
        if tool_id in self._tool_calls:
            self._tool_calls[tool_id].status = ToolCallStatus.CALLING
        
        return StreamChunk(
            type=ChunkType.TOOL_ARGS,
            message_id=self.message_id,
            data={
                "toolId": tool_id,
                "status": ToolCallStatus.CALLING.value,
            },
        )
    
    def tool_result(
        self,
        tool_id: str,
        result: Any = None,
        error: Optional[str] = None,
    ) -> StreamChunk:
        """Create tool result chunk"""
        if tool_id in self._tool_calls:
            tool = self._tool_calls[tool_id]
            tool.end_time = time.time()
            
            if error:
                tool.status = ToolCallStatus.ERRORED
                tool.error = error
            else:
                tool.status = ToolCallStatus.DONE
                tool.result = result
        
        return StreamChunk(
            type=ChunkType.TOOL_RESULT,
            message_id=self.message_id,
            data=self._tool_calls.get(tool_id),
        )
    
    def artifact(
        self,
        title: str,
        content: str,
        artifact_type: ArtifactType = ArtifactType.FILE,
        language: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> StreamChunk:
        """Create artifact chunk"""
        artifact_id = str(uuid.uuid4())[:8]
        artifact = Artifact(
            id=artifact_id,
            type=artifact_type,
            title=title,
            content=content,
            language=language,
            file_path=file_path,
        )
        self._artifacts[artifact_id] = artifact
        
        return StreamChunk(
            type=ChunkType.ARTIFACT,
            message_id=self.message_id,
            data=artifact,
        )
    
    def create_plan(self, title: str, steps: List[dict]) -> StreamChunk:
        """Create execution plan"""
        plan_steps = [
            PlanStep(
                id=str(uuid.uuid4())[:8],
                index=i,
                title=step.get("title", f"Step {i+1}"),
                description=step.get("description", ""),
            )
            for i, step in enumerate(steps)
        ]
        
        self._plan = Plan(
            id=str(uuid.uuid4())[:8],
            title=title,
            steps=plan_steps,
        )
        
        return StreamChunk(
            type=ChunkType.PLAN_UPDATE,
            message_id=self.message_id,
            data=self._plan,
        )
    
    def update_plan_step(
        self,
        step_index: int,
        status: Optional[PlanStepStatus] = None,
        progress: Optional[float] = None,
        result: Optional[str] = None,
    ) -> StreamChunk:
        """Update plan step status"""
        if self._plan and 0 <= step_index < len(self._plan.steps):
            step = self._plan.steps[step_index]
            if status:
                step.status = status
            if progress is not None:
                step.progress = progress
            if result:
                step.result = result
            
            # Update current step
            if status == PlanStepStatus.IN_PROGRESS:
                self._plan.current_step = step_index
        
        return StreamChunk(
            type=ChunkType.PLAN_UPDATE,
            message_id=self.message_id,
            data=self._plan,
        )
    
    def confirm(
        self,
        message: str,
        options: List[str] = None,
        default: str = "continue",
    ) -> StreamChunk:
        """Request user confirmation"""
        return StreamChunk(
            type=ChunkType.CONFIRM,
            message_id=self.message_id,
            data={
                "message": message,
                "options": options or ["continue", "cancel"],
                "default": default,
            },
        )
    
    def error(self, message: str, details: Optional[str] = None) -> StreamChunk:
        """Create error chunk"""
        return StreamChunk(
            type=ChunkType.ERROR,
            message_id=self.message_id,
            data={
                "message": message,
                "details": details,
            },
        )
    
    def complete(self, summary: Optional[str] = None) -> StreamChunk:
        """Create completion chunk"""
        return StreamChunk(
            type=ChunkType.COMPLETE,
            message_id=self.message_id,
            data={
                "summary": summary,
                "artifacts": list(self._artifacts.keys()),
                "toolCalls": list(self._tool_calls.keys()),
            },
        )


# ============================================================================
# Convenience Functions
# ============================================================================

def create_stream_builder(message_id: Optional[str] = None) -> StreamBuilder:
    """Create a new stream builder"""
    return StreamBuilder(message_id)


def parse_stream_chunk(json_str: str) -> Optional[StreamChunk]:
    """Parse JSON string to StreamChunk"""
    try:
        data = json.loads(json_str)
        return StreamChunk(
            type=ChunkType(data["type"]),
            message_id=data.get("messageId", ""),
            timestamp=data.get("timestamp", time.time()),
            data=data.get("data"),
        )
    except Exception:
        return None


