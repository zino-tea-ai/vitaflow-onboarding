# -*- coding: utf-8 -*-
"""
Context Module - Automatic context injection for NogicOS Agent

This module provides automatic context collection and injection, similar to Cursor's
approach of enriching each message with relevant information about the user's environment.

Components:
- ContextInjector: Main class for collecting and injecting context
- WorkspaceInfo: Workspace structure and metadata
- TerminalTracker: Recent terminal command history
"""

from .injector import ContextInjector, ContextConfig, get_context_injector
from .workspace import WorkspaceInfo, get_workspace_layout
from .terminal import TerminalTracker

__all__ = [
    "ContextInjector",
    "ContextConfig",
    "get_context_injector",
    "WorkspaceInfo",
    "get_workspace_layout",
    "TerminalTracker",
]

