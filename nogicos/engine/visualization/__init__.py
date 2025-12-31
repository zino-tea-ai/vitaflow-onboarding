# -*- coding: utf-8 -*-
"""
Visualization module for NogicOS Agent

Provides visual feedback for AI operations via WebSocket events.
"""

from .tool_mapper import (
    visualize_tool_start,
    visualize_tool_end,
    visualize_task_start,
    visualize_task_complete,
    visualize_task_error,
)

__all__ = [
    'visualize_tool_start',
    'visualize_tool_end',
    'visualize_task_start',
    'visualize_task_complete',
    'visualize_task_error',
]






