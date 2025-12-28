# -*- coding: utf-8 -*-
"""
NogicOS Tools - Unified tool system

This module provides:
- ToolRegistry: Central registry for all tools
- Browser Tools: Web automation capabilities
- Local Tools: File system and shell operations
- Plan Tools: Todo/planning capabilities (via middleware)
"""

from .base import (
    ToolRegistry,
    ToolCategory,
    ToolDefinition,
    ToolResult,
    get_registry,
    reset_registry,
)
from .browser import register_browser_tools
from .local import register_local_tools

# Try to import dispatcher for backwards compatibility
try:
    from .dispatcher import get_dispatcher, init_dispatcher_with_server
except ImportError:
    # Fallback if dispatcher doesn't exist
    def get_dispatcher():
        return get_registry()
    
    async def init_dispatcher_with_server(status_server):
        registry = get_registry()
        registry.set_context("status_server", status_server)
        return registry


def create_full_registry() -> ToolRegistry:
    """
    Create a fully populated tool registry with all tools.
    
    Returns:
        ToolRegistry with browser, local, and plan tools registered.
    """
    registry = ToolRegistry()
    register_browser_tools(registry)
    register_local_tools(registry)
    return registry


__all__ = [
    'ToolRegistry',
    'ToolCategory',
    'ToolDefinition',
    'ToolResult',
    'get_registry',
    'reset_registry',
    'register_browser_tools',
    'register_local_tools',
    'create_full_registry',
    'get_dispatcher',
    'init_dispatcher_with_server',
]
