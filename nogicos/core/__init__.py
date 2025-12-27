# -*- coding: utf-8 -*-
"""
NogicOS Core - Unified exports for contracts, config, and utilities

This module provides a single entry point for commonly used types and utilities.
Import from here instead of scattered modules.

Usage:
    from core import TaskRequest, TaskResponse, RoutePath
    from core import setup_env, get_config
"""

# ============== Configuration ==============
# Re-export from api_keys and config
from api_keys import setup_env
from config import (
    DEFAULT_MODEL,
    BROWSER_HEADLESS,
    BROWSER_TIMEOUT,
    KNOWLEDGE_BASE_DIR,
    LOG_LEVEL,
)

# ============== Contracts ==============
# Re-export from engine.contracts
from engine.contracts import (
    # Agent
    ActionType,
    AgentInput,
    AgentOutput,
    # Browser
    BrowserInput,
    BrowserOutput,
    # Knowledge
    TrajectoryStep,
    KnowledgeSearchResult,
    # Router
    RoutePath,
    RouteInput,
    RouteOutput,
)

# ============== Core Types ==============
from typing import Optional
from pydantic import BaseModel


class TaskRequest(BaseModel):
    """Unified task request (matches hive_server.ExecuteRequest)"""
    task: str
    url: Optional[str] = None
    headless: bool = True


class TaskResponse(BaseModel):
    """Unified task response (matches hive_server.ExecuteResponse)"""
    success: bool
    result: str
    path: str  # "fast", "skill", "normal", "timeout"
    time_seconds: float
    confidence: float
    steps: int
    error: Optional[str] = None
    skill_name: Optional[str] = None


class HealthStatus(BaseModel):
    """Health check response"""
    status: str  # "healthy", "degraded", "unhealthy", "busy"
    engine: bool
    executing: bool
    current_task: Optional[str] = None
    uptime_seconds: float
    memory_mb: float


# ============== Exports ==============
__all__ = [
    # Config
    "setup_env",
    "DEFAULT_MODEL",
    "BROWSER_HEADLESS",
    "BROWSER_TIMEOUT",
    "KNOWLEDGE_BASE_DIR",
    "LOG_LEVEL",
    # Contracts
    "ActionType",
    "AgentInput",
    "AgentOutput",
    "BrowserInput",
    "BrowserOutput",
    "TrajectoryStep",
    "KnowledgeSearchResult",
    "RoutePath",
    "RouteInput",
    "RouteOutput",
    # Core Types
    "TaskRequest",
    "TaskResponse",
    "HealthStatus",
]

