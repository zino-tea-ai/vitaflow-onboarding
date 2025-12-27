# -*- coding: utf-8 -*-
"""
NogicOS Contracts - Pydantic models for module interfaces
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from enum import Enum


# ============== Agent Contracts ==============

class ActionType(str, Enum):
    CODE = "code"
    TERMINATE = "terminate"


class AgentInput(BaseModel):
    """Input to agent"""
    task: str
    page_state: dict
    previous_actions: List[dict] = []


class AgentOutput(BaseModel):
    """Output from agent"""
    action_type: ActionType
    reasoning: str
    python_code: Optional[str] = None
    result: Optional[str] = None


# ============== Browser Contracts ==============

class BrowserInput(BaseModel):
    """Input for browser operations"""
    url: Optional[str] = None
    action: str = "observe"


class BrowserOutput(BaseModel):
    """Output from browser"""
    success: bool
    url: Optional[str] = None
    title: Optional[str] = None
    axtree: Optional[str] = None
    error: Optional[str] = None


# ============== Knowledge Contracts ==============

class TrajectoryStep(BaseModel):
    """Single step in a trajectory"""
    action_type: str
    selector: Optional[str] = None
    value: Optional[str] = None


class KnowledgeSearchResult(BaseModel):
    """Result from knowledge search"""
    matched: bool
    confidence: float = 0.0
    trajectory: Optional[List[TrajectoryStep]] = None
    source_task: Optional[str] = None


# ============== Router Contracts ==============
# Note: SmartRouter in engine/learning/passive.py uses RouteResult dataclass
# These are kept for reference and potential future use

class RoutePath(str, Enum):
    """Route decision path"""
    FAST = "fast"
    SKILL = "skill"
    NORMAL = "normal"


class RouteInput(BaseModel):
    """Input for routing decision"""
    task: str
    url: str = ""


class RouteOutput(BaseModel):
    """Output from routing decision"""
    path: RoutePath
    confidence: float
    source_task: Optional[str] = None

