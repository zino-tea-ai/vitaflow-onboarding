# -*- coding: utf-8 -*-
"""
Tool Registry - Unified tool management for NogicOS Agent

Reference: browser-use/tools/registry/service.py
Pattern: LangGraph ToolNode compatible tools
"""

import json
import asyncio
import logging
import functools
from enum import Enum
from dataclasses import dataclass, field
from typing import (
    Dict, Any, List, Callable, Optional, Union, 
    TypeVar, Generic, Awaitable, get_type_hints
)
from inspect import signature, Parameter, iscoroutinefunction

try:
    from pydantic import BaseModel, Field, create_model
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """Tool categories for routing and filtering"""
    BROWSER = "browser"
    LOCAL = "local"
    PLAN = "plan"
    SYSTEM = "system"


@dataclass
class ToolDefinition:
    """Definition of a tool that can be registered and executed"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    category: ToolCategory
    handler: Callable[..., Awaitable[Any]]
    requires_context: List[str] = field(default_factory=list)  # e.g., ['browser_session', 'file_system']
    
    def to_anthropic_format(self) -> Dict[str, Any]:
        """Convert to Anthropic tool format"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }
    
    def to_langchain_format(self) -> Dict[str, Any]:
        """Convert to LangChain tool format"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema
        }


@dataclass
class ToolResult:
    """Result from tool execution"""
    success: bool
    output: Any
    error: Optional[str] = None
    tool_name: str = ""
    duration_ms: int = 0


class ToolRegistry:
    """
    Unified registry for all NogicOS tools.
    
    Supports:
    - Decorator-based registration (@registry.action)
    - Category-based filtering
    - Context injection (browser_session, file_system, etc.)
    - Anthropic/LangChain format conversion
    """
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._context: Dict[str, Any] = {}
        
    def set_context(self, key: str, value: Any) -> None:
        """Set a context value that will be injected into tools"""
        self._context[key] = value
        
    def get_context(self, key: str) -> Optional[Any]:
        """Get a context value"""
        return self._context.get(key)
    
    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition"""
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name} ({tool.category.value})")
    
    def action(
        self,
        description: str,
        category: ToolCategory = ToolCategory.SYSTEM,
        requires_context: Optional[List[str]] = None,
    ) -> Callable:
        """
        Decorator for registering actions.
        
        Usage:
            @registry.action("Navigate to a URL", category=ToolCategory.BROWSER)
            async def navigate(url: str) -> str:
                ...
        """
        def decorator(func: Callable) -> Callable:
            # Extract function signature for input schema
            sig = signature(func)
            hints = get_type_hints(func) if hasattr(func, '__annotations__') else {}
            
            # Build input schema from function parameters
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'context', 'browser_session', 'file_system'):
                    continue
                    
                param_type = hints.get(param_name, str)
                json_type = self._python_type_to_json(param_type)
                
                properties[param_name] = {
                    "type": json_type,
                    "description": f"Parameter: {param_name}"
                }
                
                if param.default == Parameter.empty:
                    required.append(param_name)
            
            input_schema = {
                "type": "object",
                "properties": properties,
                "required": required
            }
            
            # Create tool definition
            tool_def = ToolDefinition(
                name=func.__name__,
                description=description,
                input_schema=input_schema,
                category=category,
                handler=func,
                requires_context=requires_context or []
            )
            
            self.register(tool_def)
            
            # Return wrapped function
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Inject context if needed
                for ctx_key in tool_def.requires_context:
                    if ctx_key not in kwargs and ctx_key in self._context:
                        kwargs[ctx_key] = self._context[ctx_key]
                
                if iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return await asyncio.to_thread(func, *args, **kwargs)
            
            return wrapper
        
        return decorator
    
    def _python_type_to_json(self, python_type) -> str:
        """Convert Python type to JSON schema type"""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        
        # Handle Optional types
        origin = getattr(python_type, '__origin__', None)
        if origin is Union:
            args = getattr(python_type, '__args__', ())
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                return self._python_type_to_json(non_none[0])
        
        return type_map.get(python_type, "string")
    
    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def get_by_category(self, category: ToolCategory) -> List[ToolDefinition]:
        """Get all tools in a category"""
        return [t for t in self._tools.values() if t.category == category]
    
    def get_all(self) -> List[ToolDefinition]:
        """Get all registered tools"""
        return list(self._tools.values())
    
    def get_names(self) -> List[str]:
        """Get all tool names"""
        return list(self._tools.keys())
    
    def to_anthropic_format(self) -> List[Dict[str, Any]]:
        """Convert all tools to Anthropic format"""
        return [t.to_anthropic_format() for t in self._tools.values()]
    
    def to_langchain_tools(self):
        """Convert to LangChain tool format for use with ToolNode"""
        try:
            from langchain_core.tools import StructuredTool
        except ImportError:
            logger.warning("langchain_core not available, returning empty list")
            return []
        
        tools = []
        for tool_def in self._tools.values():
            # Create async wrapper that handles context injection
            async def _execute(tool_name=tool_def.name, **kwargs):
                return await self.execute(tool_name, kwargs)
            
            # Build args schema from input_schema
            if PYDANTIC_AVAILABLE:
                fields = {}
                for prop_name, prop_def in tool_def.input_schema.get("properties", {}).items():
                    field_type = str  # Default
                    if prop_def.get("type") == "integer":
                        field_type = int
                    elif prop_def.get("type") == "number":
                        field_type = float
                    elif prop_def.get("type") == "boolean":
                        field_type = bool
                    
                    is_required = prop_name in tool_def.input_schema.get("required", [])
                    if is_required:
                        fields[prop_name] = (field_type, ...)
                    else:
                        fields[prop_name] = (Optional[field_type], None)
                
                if fields:
                    ArgsSchema = create_model(f"{tool_def.name}_Args", **fields)
                else:
                    ArgsSchema = None
            else:
                ArgsSchema = None
            
            lc_tool = StructuredTool.from_function(
                func=_execute,
                name=tool_def.name,
                description=tool_def.description,
                args_schema=ArgsSchema,
                coroutine=_execute
            )
            tools.append(lc_tool)
        
        return tools
    
    async def execute(
        self,
        name: str,
        args: Dict[str, Any],
        max_retries: int = 3,
        timeout_seconds: float = 30.0,
    ) -> ToolResult:
        """
        Execute a tool by name with given arguments.
        
        Phase D: Reliability improvements
        - D1.1: Automatic retry (up to max_retries)
        - D1.2: Timeout handling (timeout_seconds)
        - D1.3: Graceful degradation
        - D1.4: User-friendly error messages
        
        Args:
            name: Tool name
            args: Tool arguments
            max_retries: Maximum retry attempts (default: 3)
            timeout_seconds: Execution timeout in seconds (default: 30)
            
        Returns:
            ToolResult with success status and output
        """
        import time
        start_time = time.time()
        
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool '{name}' not found. Available tools: {', '.join(list(self._tools.keys())[:5])}...",
                tool_name=name
            )
        
        last_error = None
        
        # D1.1: Retry logic
        for attempt in range(max_retries):
            try:
                # Inject required context
                call_args = dict(args)
                for ctx_key in tool.requires_context:
                    if ctx_key in self._context:
                        call_args[ctx_key] = self._context[ctx_key]
                
                # D1.2: Timeout handling
                if iscoroutinefunction(tool.handler):
                    result = await asyncio.wait_for(
                        tool.handler(**call_args),
                        timeout=timeout_seconds
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(tool.handler, **call_args),
                        timeout=timeout_seconds
                    )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                return ToolResult(
                    success=True,
                    output=result,
                    tool_name=name,
                    duration_ms=duration_ms
                )
                
            except asyncio.TimeoutError:
                last_error = f"Tool '{name}' timed out after {timeout_seconds}s"
                logger.warning(f"{last_error} (attempt {attempt + 1}/{max_retries})")
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Tool '{name}' failed: {e} (attempt {attempt + 1}/{max_retries})")
            
            # Wait before retry (exponential backoff)
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
        
        # D1.3: Graceful degradation - all retries failed
        duration_ms = int((time.time() - start_time) * 1000)
        
        # D1.4: User-friendly error messages
        friendly_error = self._make_friendly_error(name, last_error)
        
        logger.error(f"Tool '{name}' failed after {max_retries} attempts: {friendly_error}")
        
        return ToolResult(
            success=False,
            output=None,
            error=friendly_error,
            tool_name=name,
            duration_ms=duration_ms
        )
    
    def _make_friendly_error(self, tool_name: str, error: str) -> str:
        """
        D1.4: Convert technical errors to user-friendly messages.
        
        Args:
            tool_name: Name of the tool that failed
            error: Technical error message
            
        Returns:
            User-friendly error message
        """
        # Common error patterns and friendly translations
        if "timed out" in error.lower():
            return f"{tool_name} took too long to respond. Try again or simplify the request."
        
        if "not found" in error.lower() or "no such file" in error.lower():
            return f"Could not find the requested resource. Check if the path or target exists."
        
        if "permission" in error.lower() or "access denied" in error.lower():
            return f"Permission denied. Check if you have access to this resource."
        
        if "connection" in error.lower() or "network" in error.lower():
            return f"Connection issue. Check your network or try again later."
        
        if "api key" in error.lower() or "unauthorized" in error.lower():
            return f"Authentication failed. Check your API key configuration."
        
        # Default: return original error with context
        return f"{tool_name} failed: {error}"


# Global registry instance
_global_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get or create the global tool registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def reset_registry() -> None:
    """Reset the global registry (for testing)"""
    global _global_registry
    _global_registry = None


