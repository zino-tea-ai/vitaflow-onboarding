# -*- coding: utf-8 -*-
"""
NogicOS Evaluation Module

Provides:
- LangSmith dataset management
- Custom evaluators for agent tasks
- Automated evaluation pipeline
"""

from .evaluators import (
    task_completion_evaluator,
    tool_selection_evaluator,
    response_quality_evaluator,
    latency_evaluator,
)

from .dataset_manager import (
    DatasetManager,
    create_dataset_from_runs,
    add_example_to_dataset,
)

__all__ = [
    # Evaluators
    "task_completion_evaluator",
    "tool_selection_evaluator", 
    "response_quality_evaluator",
    "latency_evaluator",
    # Dataset
    "DatasetManager",
    "create_dataset_from_runs",
    "add_example_to_dataset",
]

