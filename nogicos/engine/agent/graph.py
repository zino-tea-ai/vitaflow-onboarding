# -*- coding: utf-8 -*-
"""
NogicOS Agent Graph - LangGraph-based agent implementation

Reference: LangGraph StateGraph + ToolNode pattern
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, AsyncGenerator, Literal, Union

from .state import AgentState, create_initial_state

# Import tools
from ..tools.base import ToolRegistry, ToolCategory, get_registry
from ..tools.browser import register_browser_tools
from ..tools.local import register_local_tools

logger = logging.getLogger(__name__)

# Try to import LangGraph
try:
    from langgraph.graph import StateGraph, END, START
    from langgraph.prebuilt import ToolNode
    from langgraph.checkpoint.memory import MemorySaver
    from langchain_core.messages import (
        BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
    )
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not available, using fallback implementation")

# Try to import Anthropic
try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic not available")


AGENT_SYSTEM_PROMPT = """You are NogicOS, an AI assistant that can browse the web and operate the local file system.

You have access to the following tool categories:
1. Browser Tools: Navigate websites, click elements, type text, take screenshots, extract content
2. Local Tools: Read/write files, execute shell commands, search files

When given a task:
1. Think about what steps are needed
2. Use appropriate tools to accomplish each step
3. Observe results and adjust your approach
4. Provide a clear summary when done

Always be helpful, accurate, and efficient. If you encounter errors, try alternative approaches.

IMPORTANT: Match the user's language in your responses."""


class NogicOSAgent:
    """
    NogicOS Agent using LangGraph pattern.
    
    Features:
    - Agent loop with tool calling
    - Browser and local file system tools
    - Streaming support
    - State persistence
    """
    
    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        model: str = "claude-sonnet-4-20250514",
        api_key: Optional[str] = None,
        status_server = None,
    ):
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.status_server = status_server
        
        # Initialize tool registry
        self.registry = registry or get_registry()
        register_browser_tools(self.registry)
        register_local_tools(self.registry)
        
        # Initialize Anthropic client
        self._client = None
        if ANTHROPIC_AVAILABLE and self.api_key:
            self._client = AsyncAnthropic(api_key=self.api_key)
        
        # Build the graph
        self.graph = self._build_graph() if LANGGRAPH_AVAILABLE else None
        
        logger.info(f"NogicOSAgent initialized with {len(self.registry.get_all())} tools")
    
    @property
    def client(self) -> AsyncAnthropic:
        if self._client is None:
            if not ANTHROPIC_AVAILABLE:
                raise RuntimeError("Anthropic not available")
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client
    
    def _build_graph(self):
        """Build the LangGraph agent graph"""
        if not LANGGRAPH_AVAILABLE:
            return None
        
        # Create the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", self._execute_tools)
        
        # Set entry point
        workflow.add_edge(START, "agent")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        
        # Tools -> Agent loop
        workflow.add_edge("tools", "agent")
        
        # Compile with memory saver
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)
    
    def _should_continue(self, state: AgentState) -> Literal["continue", "end"]:
        """Determine if we should continue to tools or end"""
        messages = state.get("messages", [])
        if not messages:
            return "end"
        
        last_message = messages[-1]
        
        # Check if the last message has tool calls
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"
        
        # Also check for additional_kwargs (LangChain format)
        if hasattr(last_message, 'additional_kwargs'):
            tool_calls = last_message.additional_kwargs.get('tool_calls', [])
            if tool_calls:
                return "continue"
        
        return "end"
    
    async def _call_model(self, state: AgentState) -> Dict[str, Any]:
        """Call the LLM with current state"""
        messages = state.get("messages", [])
        
        # Convert to Anthropic format
        anthropic_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                anthropic_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                content = msg.content
                # Handle tool calls in AI message
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    content_blocks = []
                    if content:
                        content_blocks.append({"type": "text", "text": content})
                    for tc in msg.tool_calls:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id", tc.get("name", "")),
                            "name": tc.get("name", ""),
                            "input": tc.get("args", {})
                        })
                    anthropic_messages.append({"role": "assistant", "content": content_blocks})
                else:
                    anthropic_messages.append({"role": "assistant", "content": content})
            elif isinstance(msg, ToolMessage):
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content
                    }]
                })
            elif isinstance(msg, SystemMessage):
                # System messages handled separately
                pass
        
        # Get tools in Anthropic format
        tools = self.registry.to_anthropic_format()
        
        # Generate message ID for this turn
        import uuid
        message_id = str(uuid.uuid4())[:8]
        
        # Stream thinking if status server available
        if self.status_server:
            try:
                await self.status_server.stream_thinking(message_id, "Analyzing the task and deciding next action...")
            except Exception as e:
                logger.debug(f"Stream thinking failed: {e}")
        
        try:
            # Call Claude with streaming
            response_content = ""
            tool_calls = []
            
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=AGENT_SYSTEM_PROMPT,
                messages=anthropic_messages,
                tools=tools if tools else None,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, 'text'):
                            response_content += event.delta.text
                            if self.status_server:
                                try:
                                    await self.status_server.stream_content(message_id, event.delta.text)
                                except Exception:
                                    pass
                        elif hasattr(event.delta, 'partial_json'):
                            pass  # Tool call in progress
                    
                    elif event.type == "content_block_stop":
                        pass
                    
                    elif event.type == "message_delta":
                        pass
            
            # Get final message
            final_message = await stream.get_final_message()
            
            # Extract tool calls from response
            for block in final_message.content:
                if block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "args": block.input
                    })
                    if self.status_server:
                        try:
                            await self.status_server.stream_tool_start(
                                message_id,
                                block.id,
                                block.name,
                            )
                        except Exception:
                            pass
                elif block.type == "text":
                    response_content = block.text
            
            # Create AI message
            ai_message = AIMessage(
                content=response_content,
                tool_calls=tool_calls if tool_calls else []
            )
            
            return {"messages": [ai_message]}
            
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            error_message = AIMessage(content=f"Error: {str(e)}")
            return {"messages": [error_message]}
    
    async def _execute_tools(self, state: AgentState) -> Dict[str, Any]:
        """Execute tool calls from the last AI message"""
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}
        
        last_message = messages[-1]
        tool_calls = getattr(last_message, 'tool_calls', None) or []
        
        tool_messages = []
        
        # Generate message ID for tool execution
        import uuid
        message_id = str(uuid.uuid4())[:8]
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_id = tool_call.get("id", tool_name)
            args = tool_call.get("args", {})
            
            logger.info(f"Executing tool: {tool_name} with args: {args}")
            
            if self.status_server:
                try:
                    await self.status_server.stream_tool_start(message_id, tool_id, tool_name)
                except Exception:
                    pass
            
            # Execute the tool
            result = await self.registry.execute(tool_name, args)
            
            # Stream result
            if self.status_server:
                try:
                    await self.status_server.stream_tool_result(
                        message_id,
                        tool_id,
                        result.output if result.success else None,
                        result.error if not result.success else None,
                        result.duration_ms
                    )
                except Exception:
                    pass
            
            # Create tool message
            content = str(result.output) if result.success else f"Error: {result.error}"
            tool_message = ToolMessage(
                content=content,
                tool_call_id=tool_id
            )
            tool_messages.append(tool_message)
        
        return {"messages": tool_messages}
    
    async def invoke(
        self,
        message: str,
        session_id: str = "default",
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Invoke the agent with a message.
        
        Args:
            message: User message
            session_id: Session ID for state persistence
            config: Additional configuration
            
        Returns:
            Final state after agent execution
        """
        if not LANGGRAPH_AVAILABLE or self.graph is None:
            return await self._invoke_fallback(message, session_id)
        
        # Create initial state with user message
        initial_state = create_initial_state(session_id)
        initial_state["messages"] = [HumanMessage(content=message)]
        
        # Run the graph
        config = config or {}
        config["configurable"] = config.get("configurable", {})
        config["configurable"]["thread_id"] = session_id
        
        result = await self.graph.ainvoke(initial_state, config)
        return result
    
    async def astream(
        self,
        message: str,
        session_id: str = "default",
        config: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream agent execution.
        
        Args:
            message: User message
            session_id: Session ID for state persistence
            config: Additional configuration
            
        Yields:
            State updates during execution
        """
        if not LANGGRAPH_AVAILABLE or self.graph is None:
            result = await self._invoke_fallback(message, session_id)
            yield result
            return
        
        # Create initial state with user message
        initial_state = create_initial_state(session_id)
        initial_state["messages"] = [HumanMessage(content=message)]
        
        # Run the graph with streaming
        config = config or {}
        config["configurable"] = config.get("configurable", {})
        config["configurable"]["thread_id"] = session_id
        
        async for state in self.graph.astream(initial_state, config, stream_mode="values"):
            yield state
    
    async def _invoke_fallback(
        self,
        message: str,
        session_id: str = "default"
    ) -> Dict[str, Any]:
        """Fallback implementation without LangGraph"""
        logger.warning("Using fallback agent implementation")
        
        if not ANTHROPIC_AVAILABLE:
            return {
                "messages": [{"role": "assistant", "content": "Error: Anthropic client not available"}],
                "session_id": session_id
            }
        
        # Simple single-turn response
        tools = self.registry.to_anthropic_format()
        
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=AGENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
            tools=tools if tools else None,
        )
        
        # Extract response
        content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                content += block.text
        
        return {
            "messages": [
                {"role": "user", "content": message},
                {"role": "assistant", "content": content}
            ],
            "session_id": session_id
        }
    
    def get_final_response(self, state: Dict[str, Any]) -> str:
        """Extract the final AI response from state"""
        messages = state.get("messages", [])
        
        # Find the last AI message
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                return msg.content
            elif isinstance(msg, dict) and msg.get("role") == "assistant":
                return msg.get("content", "")
        
        return ""

