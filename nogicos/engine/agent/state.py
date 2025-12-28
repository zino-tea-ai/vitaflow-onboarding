# -*- coding: utf-8 -*-
"""
Agent State - State definition for LangGraph agent

Reference: LangGraph MessagesState pattern
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional, Sequence
from dataclasses import dataclass, field

# Try to import LangGraph types
try:
    from langgraph.graph.message import add_messages
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    # Fallback definitions
    def add_messages(left: list, right: list) -> list:
        return left + right
    BaseMessage = dict
    HumanMessage = dict
    AIMessage = dict
    ToolMessage = dict


@dataclass
class TodoItem:
    """A todo item for task planning"""
    id: str
    content: str
    status: str = "pending"  # pending, in_progress, completed, cancelled
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "content": self.content,
            "status": self.status
        }


@dataclass
class FileEntry:
    """A virtual file entry"""
    path: str
    content: str
    created_at: float = 0.0
    modified_at: float = 0.0


class AgentState(TypedDict):
    """
    State for the NogicOS Agent.
    
    This follows the LangGraph pattern with message accumulation
    and additional state for files and todos.
    """
    # Core messages - uses add_messages reducer for accumulation
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Virtual filesystem for agent-created files
    files: Dict[str, str]
    
    # Todo list for planning
    todos: List[Dict[str, str]]
    
    # Current execution step
    current_step: int
    
    # Session metadata
    session_id: str
    
    # Streaming state
    is_streaming: bool
    
    # Error tracking
    last_error: Optional[str]


def create_initial_state(session_id: str = "default") -> AgentState:
    """Create an initial agent state"""
    import time
    return AgentState(
        messages=[],
        files={},
        todos=[],
        current_step=0,
        session_id=session_id,
        is_streaming=False,
        last_error=None
    )


def add_user_message(state: AgentState, content: str) -> AgentState:
    """Add a user message to the state"""
    if LANGGRAPH_AVAILABLE:
        msg = HumanMessage(content=content)
    else:
        msg = {"role": "user", "content": content}
    
    return {
        **state,
        "messages": list(state["messages"]) + [msg]
    }


def add_ai_message(state: AgentState, content: str) -> AgentState:
    """Add an AI message to the state"""
    if LANGGRAPH_AVAILABLE:
        msg = AIMessage(content=content)
    else:
        msg = {"role": "assistant", "content": content}
    
    return {
        **state,
        "messages": list(state["messages"]) + [msg]
    }


def add_tool_message(state: AgentState, tool_call_id: str, content: str) -> AgentState:
    """Add a tool message to the state"""
    if LANGGRAPH_AVAILABLE:
        msg = ToolMessage(content=content, tool_call_id=tool_call_id)
    else:
        msg = {"role": "tool", "content": content, "tool_call_id": tool_call_id}
    
    return {
        **state,
        "messages": list(state["messages"]) + [msg]
    }


def add_file(state: AgentState, path: str, content: str) -> AgentState:
    """Add or update a file in the virtual filesystem"""
    new_files = dict(state["files"])
    new_files[path] = content
    return {
        **state,
        "files": new_files
    }


def add_todo(state: AgentState, todo_id: str, content: str) -> AgentState:
    """Add a todo item"""
    new_todos = list(state["todos"])
    new_todos.append({
        "id": todo_id,
        "content": content,
        "status": "pending"
    })
    return {
        **state,
        "todos": new_todos
    }


def update_todo_status(state: AgentState, todo_id: str, status: str) -> AgentState:
    """Update a todo item's status"""
    new_todos = []
    for todo in state["todos"]:
        if todo["id"] == todo_id:
            new_todos.append({**todo, "status": status})
        else:
            new_todos.append(todo)
    return {
        **state,
        "todos": new_todos
    }


def increment_step(state: AgentState) -> AgentState:
    """Increment the current step"""
    return {
        **state,
        "current_step": state["current_step"] + 1
    }


