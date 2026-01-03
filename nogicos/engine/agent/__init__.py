# -*- coding: utf-8 -*-
"""
NogicOS Agent - Pure ReAct Agent with Plan-Execute capabilities

Components:
- ReActAgent: Core Think-Act-Observe loop
- TaskPlanner: Complex task decomposition and replanning
- TaskClassifier: Intelligent task routing (browser/local/mixed)
- AgentMode: Cursor-style interaction modes (Agent/Ask/Plan)
"""

from .react_agent import ReActAgent, AgentResult
from .planner import TaskPlanner, Plan, PlanExecuteState, is_simple_task
from .classifier import TaskClassifier, TaskType, TaskComplexity, ClassificationResult
from .modes import AgentMode, ModeRouter, get_mode_router, ModeConfig
from .imports import get_available_features

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
]
