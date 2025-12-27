# -*- coding: utf-8 -*-
"""
Hive Agent State Definition

Defines the state schema for the LangGraph agent.
"""

from typing import TypedDict, Annotated, Optional, List, Any
from langgraph.graph.message import add_messages


class PageState(TypedDict):
    """Current browser page state"""
    url: str
    title: str
    axtree: str  # Accessibility tree
    screenshot_base64: Optional[str]


class ActionResult(TypedDict):
    """Result of executing an action"""
    success: bool
    output: Optional[Any]
    error: Optional[str]
    stdout: str


class AgentState(TypedDict):
    """
    Main agent state - flows through the graph
    
    Attributes:
        task: The task to accomplish
        messages: Conversation history (auto-accumulated)
        page_state: Current browser state
        actions: List of actions taken
        current_step: Current step number
        max_steps: Maximum steps allowed
        result: Final result when done
        status: running | completed | failed
    """
    # Task info
    task: str
    
    # Conversation (auto-accumulated by add_messages)
    messages: Annotated[list, add_messages]
    
    # Browser state
    page_state: Optional[PageState]
    
    # Execution tracking
    actions: List[dict]
    current_step: int
    max_steps: int
    
    # Result
    result: Optional[str]
    status: str  # running, completed, failed


def create_initial_state(task: str, max_steps: int = 10) -> AgentState:
    """Create initial state for a new task"""
    return {
        "task": task,
        "messages": [],
        "page_state": None,
        "actions": [],
        "current_step": 0,
        "max_steps": max_steps,
        "result": None,
        "status": "running",
    }

