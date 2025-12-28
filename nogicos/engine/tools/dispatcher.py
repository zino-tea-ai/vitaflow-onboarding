# Tool Dispatcher
# Routes tool calls to the appropriate handler (Electron IPC or local Python)

import json
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum


class ToolExecutionLocation(Enum):
    """Where the tool should be executed"""
    ELECTRON = "electron"  # File system, terminal - via IPC
    PYTHON = "python"      # Local Python execution
    BROWSER = "browser"    # Browser control - via CDP


@dataclass
class ToolResult:
    """Result of a tool execution"""
    success: bool
    data: Any
    error: Optional[str] = None


# Map tool names to execution locations
TOOL_LOCATIONS: Dict[str, ToolExecutionLocation] = {
    "read_file": ToolExecutionLocation.ELECTRON,
    "write_file": ToolExecutionLocation.ELECTRON,
    "list_dir": ToolExecutionLocation.ELECTRON,
    "run_command": ToolExecutionLocation.ELECTRON,
    "create_dir": ToolExecutionLocation.ELECTRON,
    # Browser tools use existing CDP
    "navigate": ToolExecutionLocation.BROWSER,
    "click": ToolExecutionLocation.BROWSER,
    "type_text": ToolExecutionLocation.BROWSER,
    "screenshot": ToolExecutionLocation.BROWSER,
}


class ToolDispatcher:
    """
    Dispatches tool calls to the appropriate execution environment.
    
    For Electron tools: Sends via WebSocket to Electron main process
    For Python tools: Executes locally
    For Browser tools: Uses existing CDP bridge
    """
    
    def __init__(self, websocket_sender: Optional[Callable[[str, Dict], Awaitable[Any]]] = None):
        self.websocket_sender = websocket_sender
    
    def set_websocket_sender(self, sender: Callable[[str, Dict], Awaitable[Any]]):
        """Set the WebSocket sender function for Electron communication"""
        self.websocket_sender = sender
    
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool and return the result.
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments for the tool
            
        Returns:
            ToolResult with success status and data/error
        """
        location = TOOL_LOCATIONS.get(tool_name, ToolExecutionLocation.PYTHON)
        
        try:
            if location == ToolExecutionLocation.ELECTRON:
                return await self._call_electron_tool(tool_name, args)
            elif location == ToolExecutionLocation.BROWSER:
                return await self._call_browser_tool(tool_name, args)
            else:
                return await self._call_python_tool(tool_name, args)
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    async def _call_electron_tool(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Call a tool that executes in Electron (file system, terminal)"""
        if not self.websocket_sender:
            return ToolResult(
                success=False,
                data=None,
                error="WebSocket sender not configured for Electron tools"
            )
        
        try:
            # Use the StatusServer's send_tool_call which handles call_id and waiting
            # The websocket_sender wrapper calls server.send_tool_call() and returns the result
            result = await self.websocket_sender("tool_call", {
                "tool_name": tool_name,
                "args": args
            })
            return ToolResult(success=True, data=result)
            
        except asyncio.TimeoutError:
            return ToolResult(success=False, data=None, error="Tool call timed out")
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    # Note: Tool responses are handled by StatusServer.send_tool_call()
    # which waits for the response and returns directly
    
    async def _call_browser_tool(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Call a browser tool via CDP (handled by existing CDP bridge)"""
        # Browser tools are handled by the existing CDP system
        # This is a placeholder - actual implementation uses cdp_session
        return ToolResult(
            success=False,
            data=None,
            error="Browser tools should be called via CDPBrowserSession"
        )
    
    async def _call_python_tool(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Call a tool that executes locally in Python"""
        # Python-only tools (if any)
        return ToolResult(
            success=False,
            data=None,
            error=f"Unknown Python tool: {tool_name}"
        )


# Global dispatcher instance
_dispatcher: Optional[ToolDispatcher] = None


def get_dispatcher() -> ToolDispatcher:
    """Get the global tool dispatcher instance"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = ToolDispatcher()
    return _dispatcher


async def init_dispatcher_with_server(status_server=None):
    """
    Initialize dispatcher with WebSocket server connection
    
    Args:
        status_server: Optional StatusServer instance to use. 
                       If not provided, uses the global get_server() instance.
    """
    from ..server.websocket import get_server
    
    dispatcher = get_dispatcher()
    server = status_server if status_server else get_server()
    
    # Create wrapper that uses server's send_tool_call
    async def send_tool(msg_type: str, data: Dict) -> Any:
        if msg_type == "tool_call":
            return await server.send_tool_call(
                data["tool_name"],
                data["args"]
            )
        return None
    
    dispatcher.set_websocket_sender(send_tool)
    return dispatcher

