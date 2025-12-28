# -*- coding: utf-8 -*-
"""
Smart Router - Decides between conversation and task execution

Uses Claude with tool_choice='auto' to let the LLM decide whether
to respond conversationally or execute a task with tools.

Best Practice from Anthropic Cookbook:
- Simple questions/greetings → Direct response (no tools)
- Task requests → Execute with planning and tools
"""

import os
import uuid
import asyncio
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class ResponseType(Enum):
    """Type of response needed"""
    CONVERSATION = "conversation"  # Simple chat, just respond
    TASK = "task"                  # Needs planning and execution


@dataclass
class RouterResult:
    """Result of smart routing decision"""
    response_type: ResponseType
    direct_response: Optional[str] = None  # For conversation type
    task_description: Optional[str] = None  # Refined task for execution
    confidence: float = 1.0


# Tools that indicate a task (not conversation)
TASK_TOOLS = [
    {
        "name": "execute_task",
        "description": "Execute a task that requires multiple steps, web browsing, file operations, data analysis, or code generation. Use this when the user wants you to DO something, not just EXPLAIN something.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "Clear description of what needs to be done"
                },
                "requires_browser": {
                    "type": "boolean",
                    "description": "Whether this task needs web browsing"
                },
                "requires_files": {
                    "type": "boolean",
                    "description": "Whether this task needs file operations"
                }
            },
            "required": ["task_description"]
        }
    }
]


ROUTER_SYSTEM_PROMPT = """You are NogicOS, a friendly AI assistant.

IMPORTANT: Only use the execute_task tool for ACTUAL tasks that require actions like:
- Browsing websites
- Creating/editing files
- Searching the web
- Analyzing data

For simple messages like:
- "hi", "hello", greetings → Just reply "Hello! How can I help you today?" (DO NOT use any tool)
- Questions about concepts → Answer directly (DO NOT use any tool)
- Casual chat → Respond naturally (DO NOT use any tool)

Keep responses SHORT. Match the user's language.
If unsure, just respond with text - don't use tools."""


class SmartRouter:
    """
    Smart router that decides between conversation and task execution.
    
    Uses Claude's tool_choice='auto' to let the model naturally decide
    whether the user wants to chat or wants a task executed.
    """
    
    def __init__(
        self,
        status_server=None,
        model: str = "claude-3-5-haiku-20241022",  # Haiku - fast response
    ):
        self.status_server = status_server
        self.model = model
        self._client = None
    
    @property
    def client(self):
        """Lazy AsyncAnthropic client initialization"""
        if self._client is None and ANTHROPIC_AVAILABLE:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self._client = AsyncAnthropic(api_key=api_key)
        return self._client
    
    async def route(
        self,
        user_input: str,
        context: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> RouterResult:
        """
        Route user input to either conversation or task execution.
        
        Args:
            user_input: The user's message
            context: Optional context (current page, etc.)
            message_id: Optional message ID for streaming
            
        Returns:
            RouterResult indicating conversation or task
        """
        message_id = message_id or str(uuid.uuid4())[:8]
        
        if not self.client:
            # Fallback: assume task if no client
            return RouterResult(
                response_type=ResponseType.TASK,
                task_description=user_input,
            )
        
        # Build messages
        messages = [{"role": "user", "content": user_input}]
        
        if context:
            messages[0]["content"] = f"{user_input}\n\n[Context: {context}]"
        
        try:
            # Let Claude decide with tool_choice='auto'
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=ROUTER_SYSTEM_PROMPT,
                tools=TASK_TOOLS,
                tool_choice={"type": "auto"},  # KEY: Let Claude decide!
                messages=messages,
            )
            
            # Analyze response
            last_block = response.content[-1] if response.content else None
            
            if not last_block:
                return RouterResult(
                    response_type=ResponseType.TASK,
                    task_description=user_input,
                )
            
            # Check what Claude decided
            if last_block.type == "text":
                # Claude chose to respond directly - it's a conversation!
                return RouterResult(
                    response_type=ResponseType.CONVERSATION,
                    direct_response=last_block.text,
                    confidence=0.95,
                )
            
            elif last_block.type == "tool_use":
                # Claude wants to execute a task
                tool_input = last_block.input
                task_desc = tool_input.get("task_description", user_input)
                
                return RouterResult(
                    response_type=ResponseType.TASK,
                    task_description=task_desc,
                    confidence=0.95,
                )
            
            else:
                # Unknown, default to task
                return RouterResult(
                    response_type=ResponseType.TASK,
                    task_description=user_input,
                )
                
        except Exception as e:
            print(f"[Router] Error: {e}")
            # On error, default to task execution
            return RouterResult(
                response_type=ResponseType.TASK,
                task_description=user_input,
            )
    
    async def route_and_stream(
        self,
        user_input: str,
        context: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> RouterResult:
        """
        Route with streaming support for the response.
        
        If it's a conversation, streams the response directly.
        If it's a task, returns immediately for TaskExecutor to handle.
        """
        message_id = message_id or str(uuid.uuid4())[:8]
        
        if not self.client:
            return RouterResult(
                response_type=ResponseType.TASK,
                task_description=user_input,
            )
        
        messages = [{"role": "user", "content": user_input}]
        
        if context:
            messages[0]["content"] = f"{user_input}\n\n[Context: {context}]"
        
        try:
            # Stream the response
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=1024,
                system=ROUTER_SYSTEM_PROMPT,
                tools=TASK_TOOLS,
                tool_choice={"type": "auto"},
                messages=messages,
            ) as stream:
                response_text = ""
                tool_use_detected = False
                tool_input = {}
                
                async for event in stream:
                    if event.type == "content_block_start":
                        if hasattr(event, 'content_block'):
                            if event.content_block.type == "tool_use":
                                tool_use_detected = True
                                tool_input = {"name": event.content_block.name}
                    
                    elif event.type == "content_block_delta":
                        if hasattr(event, 'delta'):
                            if hasattr(event.delta, 'text'):
                                # Text response - it's conversation
                                response_text += event.delta.text
                                # Stream to frontend
                                if self.status_server and not tool_use_detected:
                                    await self.status_server.stream_content(
                                        message_id,
                                        event.delta.text
                                    )
                                    await asyncio.sleep(0.02)
                            
                            elif hasattr(event.delta, 'partial_json'):
                                # Tool arguments being built
                                pass
                
                # Final decision
                if tool_use_detected:
                    # Get final message for tool details
                    final_msg = await stream.get_final_message()
                    for block in final_msg.content:
                        if block.type == "tool_use":
                            tool_input = block.input
                            break
                    
                    print(f"[Router] Tool detected → TASK: {tool_input}")
                    return RouterResult(
                        response_type=ResponseType.TASK,
                        task_description=tool_input.get("task_description", user_input),
                    )
                else:
                    # Mark complete if we streamed conversation
                    print(f"[Router] No tool → CONVERSATION: {response_text[:50]}...")
                    if self.status_server:
                        await self.status_server.stream_complete(
                            message_id,
                            summary="Conversation response"
                        )
                    
                    return RouterResult(
                        response_type=ResponseType.CONVERSATION,
                        direct_response=response_text,
                    )
                    
        except Exception as e:
            print(f"[Router] Streaming error: {e}")
            return RouterResult(
                response_type=ResponseType.TASK,
                task_description=user_input,
            )


# Convenience function
async def smart_route(
    user_input: str,
    status_server=None,
    context: Optional[str] = None,
) -> RouterResult:
    """
    Quickly route user input.
    
    Returns RouterResult with response_type indicating
    whether to respond directly or execute a task.
    """
    router = SmartRouter(status_server)
    return await router.route(user_input, context)

