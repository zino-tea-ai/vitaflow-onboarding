# -*- coding: utf-8 -*-
"""
Tool Router - Routes tasks to appropriate tools

Manages available tools and dispatches execution requests.
Uses Python backend for local file operations (move, copy, delete).
"""

import os
import json
import shutil
import asyncio
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """Tool categories"""
    BROWSER = "browser"
    FILE = "file"
    SEARCH = "search"
    ANALYSIS = "analysis"
    CODE = "code"
    SYSTEM = "system"


@dataclass
class Tool:
    """Tool definition"""
    name: str
    description: str
    category: ToolCategory
    parameters: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable[..., Awaitable[Any]]] = None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "parameters": self.parameters,
        }
    
    def to_anthropic_tool(self) -> dict:
        """Convert to Anthropic tool format"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": [k for k, v in self.parameters.items() if v.get("required", False)],
            },
        }


@dataclass
class ToolResult:
    """Result of tool execution"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "durationMs": self.duration_ms,
        }


class ToolRouter:
    """
    Routes and executes tool calls.
    
    Maintains a registry of available tools and their handlers.
    Can dispatch to local handlers or forward to Electron frontend.
    """
    
    def __init__(self, status_server=None):
        self.status_server = status_server
        self._tools: Dict[str, Tool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register built-in tools"""
        
        # Browser tools
        self.register(Tool(
            name="browser_navigate",
            description="Navigate to a URL in the browser",
            category=ToolCategory.BROWSER,
            parameters={
                "url": {"type": "string", "description": "URL to navigate to", "required": True},
            },
        ))
        
        self.register(Tool(
            name="browser_click",
            description="Click on an element on the page",
            category=ToolCategory.BROWSER,
            parameters={
                "selector": {"type": "string", "description": "CSS selector or element description"},
                "text": {"type": "string", "description": "Text content to find and click"},
            },
        ))
        
        self.register(Tool(
            name="browser_type",
            description="Type text into an input field",
            category=ToolCategory.BROWSER,
            parameters={
                "selector": {"type": "string", "description": "CSS selector of input"},
                "text": {"type": "string", "description": "Text to type", "required": True},
            },
        ))
        
        self.register(Tool(
            name="browser_extract",
            description="Extract data from the current page",
            category=ToolCategory.BROWSER,
            parameters={
                "selector": {"type": "string", "description": "CSS selector to extract from"},
                "attribute": {"type": "string", "description": "Attribute to extract (default: text)"},
            },
        ))
        
        self.register(Tool(
            name="browser_screenshot",
            description="Take a screenshot of the current page",
            category=ToolCategory.BROWSER,
            parameters={
                "full_page": {"type": "boolean", "description": "Capture full page"},
            },
        ))
        
        # File tools - Now with Python backend handlers
        self.register(Tool(
            name="write_file",
            description="Write content to a file",
            category=ToolCategory.FILE,
            parameters={
                "filepath": {"type": "string", "description": "File path", "required": True},
                "content": {"type": "string", "description": "File content", "required": True},
            },
            handler=self._handle_write_file,
        ))
        
        self.register(Tool(
            name="read_file",
            description="Read content from a file",
            category=ToolCategory.FILE,
            parameters={
                "filepath": {"type": "string", "description": "File path", "required": True},
            },
            handler=self._handle_read_file,
        ))
        
        self.register(Tool(
            name="create_dir",
            description="Create a directory",
            category=ToolCategory.FILE,
            parameters={
                "dirpath": {"type": "string", "description": "Directory path", "required": True},
            },
            handler=self._handle_create_dir,
        ))
        
        self.register(Tool(
            name="move_file",
            description="Move or rename a file/directory",
            category=ToolCategory.FILE,
            parameters={
                "source": {"type": "string", "description": "Source path", "required": True},
                "destination": {"type": "string", "description": "Destination path", "required": True},
            },
            handler=self._handle_move_file,
        ))
        
        self.register(Tool(
            name="copy_file",
            description="Copy a file or directory",
            category=ToolCategory.FILE,
            parameters={
                "source": {"type": "string", "description": "Source path", "required": True},
                "destination": {"type": "string", "description": "Destination path", "required": True},
            },
            handler=self._handle_copy_file,
        ))
        
        self.register(Tool(
            name="delete_file",
            description="Delete a file or directory",
            category=ToolCategory.FILE,
            parameters={
                "path": {"type": "string", "description": "Path to delete", "required": True},
                "recursive": {"type": "boolean", "description": "Delete directories recursively"},
            },
            handler=self._handle_delete_file,
        ))
        
        self.register(Tool(
            name="list_directory",
            description="List files in a directory",
            category=ToolCategory.FILE,
            parameters={
                "path": {"type": "string", "description": "Directory path", "required": True},
            },
            handler=self._handle_list_directory,
        ))
        
        # Search tools
        self.register(Tool(
            name="web_search",
            description="Search the web for information",
            category=ToolCategory.SEARCH,
            parameters={
                "query": {"type": "string", "description": "Search query", "required": True},
                "num_results": {"type": "integer", "description": "Number of results"},
            },
        ))
        
        # Analysis tools
        self.register(Tool(
            name="analyze_data",
            description="Analyze data using AI",
            category=ToolCategory.ANALYSIS,
            parameters={
                "data": {"type": "string", "description": "Data to analyze", "required": True},
                "analysis_type": {"type": "string", "description": "Type: patterns, insights, summary"},
            },
        ))
        
        self.register(Tool(
            name="generate_report",
            description="Generate a report from data",
            category=ToolCategory.ANALYSIS,
            parameters={
                "data": {"type": "string", "description": "Data for report", "required": True},
                "format": {"type": "string", "description": "Format: markdown, json, text"},
                "title": {"type": "string", "description": "Report title"},
            },
        ))
    
    def register(self, tool: Tool):
        """Register a tool"""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def list_tools(self, category: Optional[ToolCategory] = None) -> List[Tool]:
        """List all tools, optionally filtered by category"""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools
    
    def get_anthropic_tools(self, categories: Optional[List[ToolCategory]] = None) -> List[dict]:
        """Get tools in Anthropic format"""
        tools = self.list_tools()
        if categories:
            tools = [t for t in tools if t.category in categories]
        return [t.to_anthropic_tool() for t in tools]
    
    async def execute(
        self,
        tool_name: str,
        args: Dict[str, Any],
        timeout: float = 30.0,
    ) -> ToolResult:
        """
        Execute a tool.
        
        Routes to local handler or Electron frontend.
        
        Args:
            tool_name: Name of tool to execute
            args: Tool arguments
            timeout: Execution timeout
            
        Returns:
            ToolResult with execution outcome
        """
        import time
        start_time = time.time()
        
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}",
            )
        
        try:
            # Check for local handler first
            if tool.handler:
                result = await asyncio.wait_for(
                    tool.handler(**args),
                    timeout=timeout
                )
                return ToolResult(
                    success=True,
                    result=result,
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            
            # Route based on category
            if tool.category == ToolCategory.BROWSER:
                result = await self._execute_browser_tool(tool_name, args, timeout)
            elif tool.category == ToolCategory.FILE:
                result = await self._execute_file_tool(tool_name, args)
            elif tool.category == ToolCategory.ANALYSIS:
                result = await self._execute_analysis_tool(tool_name, args)
            else:
                # Forward to Electron via status_server
                result = await self._forward_to_electron(tool_name, args, timeout)
            
            return ToolResult(
                success=True,
                result=result,
                duration_ms=int((time.time() - start_time) * 1000),
            )
            
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Tool timeout after {timeout}s",
                duration_ms=int(timeout * 1000),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )
    
    async def _execute_browser_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        timeout: float,
    ) -> Any:
        """Execute browser tool via Electron"""
        if self.status_server:
            return await self.status_server.send_tool_call(tool_name, args, timeout)
        raise Exception("No status_server for browser tools")
    
    async def _execute_file_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> Any:
        """Execute file tool using Python backend handlers"""
        tool = self.get_tool(tool_name)
        if tool and tool.handler:
            # Use the registered handler directly
            logger.info(f"[ToolRouter] Executing file tool: {tool_name} with args: {args}")
            return await tool.handler(**args)
        
        # Fallback: forward to Electron (should rarely happen now)
        logger.warning(f"[ToolRouter] No handler for {tool_name}, falling back to Electron")
        if self.status_server:
            return await self.status_server.send_tool_call(tool_name, args, 30.0)
        
        raise Exception(f"No handler for file tool: {tool_name}")
    
    async def _execute_analysis_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> Any:
        """Execute analysis tool using LLM"""
        try:
            from ..llm.stream import LLMStream
        except ImportError:
            return {"error": "LLM not available"}
        
        if tool_name == "analyze_data":
            # Use LLM to analyze
            # Note: This is a simplified implementation
            # In production, would stream to frontend
            return {
                "status": "analyzed",
                "data_length": len(str(args.get("data", ""))),
                "analysis_type": args.get("analysis_type", "general"),
            }
        
        elif tool_name == "generate_report":
            return {
                "status": "generated",
                "format": args.get("format", "markdown"),
                "title": args.get("title", "Report"),
            }
        
        return {"error": f"Unknown analysis tool: {tool_name}"}
    
    async def _forward_to_electron(
        self,
        tool_name: str,
        args: Dict[str, Any],
        timeout: float,
    ) -> Any:
        """Forward tool call to Electron frontend"""
        if not self.status_server:
            raise Exception("No status_server for Electron forwarding")
        
        return await self.status_server.send_tool_call(tool_name, args, timeout)
    
    # ========================================
    # Python Backend File Handlers
    # ========================================
    
    def _is_path_allowed(self, path: str) -> bool:
        """Check if path is within allowed directories"""
        allowed_roots = [
            os.path.expanduser("~"),  # User home
            os.getcwd(),  # Current working directory
        ]
        abs_path = os.path.abspath(path)
        return any(abs_path.startswith(root) for root in allowed_roots)
    
    async def _handle_write_file(self, filepath: str, content: str) -> str:
        """Write content to a file"""
        try:
            if not self._is_path_allowed(filepath):
                return f"Error: Access denied to path: {filepath}"
            
            # Create parent directories if needed
            parent = os.path.dirname(filepath)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"[File] Wrote {len(content)} chars to {filepath}")
            return f"Successfully wrote {len(content)} characters to {filepath}"
            
        except Exception as e:
            logger.error(f"[File] Write failed: {e}")
            return f"Error writing file: {str(e)}"
    
    async def _handle_read_file(self, filepath: str) -> str:
        """Read content from a file"""
        try:
            if not self._is_path_allowed(filepath):
                return f"Error: Access denied to path: {filepath}"
            
            if not os.path.exists(filepath):
                return f"Error: File not found: {filepath}"
            
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Limit output size
            max_size = 50000
            if len(content) > max_size:
                content = content[:max_size] + f"\n... (truncated, total {len(content)} chars)"
            
            logger.info(f"[File] Read {len(content)} chars from {filepath}")
            return content
            
        except Exception as e:
            logger.error(f"[File] Read failed: {e}")
            return f"Error reading file: {str(e)}"
    
    async def _handle_create_dir(self, dirpath: str) -> str:
        """Create a directory"""
        try:
            if not self._is_path_allowed(dirpath):
                return f"Error: Access denied to path: {dirpath}"
            
            os.makedirs(dirpath, exist_ok=True)
            logger.info(f"[File] Created directory: {dirpath}")
            return f"Successfully created directory: {dirpath}"
            
        except Exception as e:
            logger.error(f"[File] Create dir failed: {e}")
            return f"Error creating directory: {str(e)}"
    
    async def _handle_move_file(self, source: str, destination: str) -> str:
        """Move or rename a file/directory"""
        try:
            if not self._is_path_allowed(source):
                return f"Error: Access denied to source path: {source}"
            if not self._is_path_allowed(destination):
                return f"Error: Access denied to destination path: {destination}"
            
            if not os.path.exists(source):
                return f"Error: Source not found: {source}"
            
            # Create destination directory if needed
            dest_dir = os.path.dirname(destination)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            
            shutil.move(source, destination)
            logger.info(f"[File] Moved {source} -> {destination}")
            return f"Successfully moved {source} to {destination}"
            
        except Exception as e:
            logger.error(f"[File] Move failed: {e}")
            return f"Error moving file: {str(e)}"
    
    async def _handle_copy_file(self, source: str, destination: str) -> str:
        """Copy a file or directory"""
        try:
            if not self._is_path_allowed(source):
                return f"Error: Access denied to source path: {source}"
            if not self._is_path_allowed(destination):
                return f"Error: Access denied to destination path: {destination}"
            
            if not os.path.exists(source):
                return f"Error: Source not found: {source}"
            
            # Create destination directory if needed
            dest_dir = os.path.dirname(destination)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            
            if os.path.isdir(source):
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)
            
            logger.info(f"[File] Copied {source} -> {destination}")
            return f"Successfully copied {source} to {destination}"
            
        except Exception as e:
            logger.error(f"[File] Copy failed: {e}")
            return f"Error copying file: {str(e)}"
    
    async def _handle_delete_file(self, path: str, recursive: bool = False) -> str:
        """Delete a file or directory"""
        try:
            if not self._is_path_allowed(path):
                return f"Error: Access denied to path: {path}"
            
            if not os.path.exists(path):
                return f"Error: Path not found: {path}"
            
            # Safety check: don't delete important directories
            danger_paths = [
                os.path.expanduser("~"),
                "C:\\",
                "C:\\Windows",
                "C:\\Program Files",
                "/",
                "/home",
                "/usr",
            ]
            abs_path = os.path.abspath(path)
            if abs_path in danger_paths:
                return f"Error: Refusing to delete protected path: {path}"
            
            if os.path.isdir(path):
                if recursive:
                    shutil.rmtree(path)
                else:
                    os.rmdir(path)  # Only removes empty dirs
            else:
                os.remove(path)
            
            logger.info(f"[File] Deleted: {path}")
            return f"Successfully deleted: {path}"
            
        except Exception as e:
            logger.error(f"[File] Delete failed: {e}")
            return f"Error deleting: {str(e)}"
    
    async def _handle_list_directory(self, path: str) -> str:
        """List directory contents"""
        try:
            if not self._is_path_allowed(path):
                return f"Error: Access denied to path: {path}"
            
            if not os.path.exists(path):
                return f"Error: Path not found: {path}"
            
            if not os.path.isdir(path):
                return f"Error: Not a directory: {path}"
            
            entries = []
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path):
                    entries.append(f"[DIR]  {entry}/")
                else:
                    size = os.path.getsize(full_path)
                    entries.append(f"[FILE] {entry} ({size} bytes)")
            
            if not entries:
                return f"Directory is empty: {path}"
            
            logger.info(f"[File] Listed {len(entries)} items in {path}")
            return f"Contents of {path}:\n" + '\n'.join(sorted(entries))
            
        except Exception as e:
            logger.error(f"[File] List dir failed: {e}")
            return f"Error listing directory: {str(e)}"

