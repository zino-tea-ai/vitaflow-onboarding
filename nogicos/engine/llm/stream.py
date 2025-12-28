# -*- coding: utf-8 -*-
"""
NogicOS LLM Stream - Real-time AI Response Streaming

Provides streaming LLM calls that output directly to WebSocket for real-time UI updates.

Architecture:
    User Input → LLM API (streaming) → StreamChunks → WebSocket → Frontend

Features:
    - Token-by-token streaming for thinking/content
    - Automatic chunking for smooth UI updates
    - Tool call detection and streaming
    - Error handling with graceful fallback
"""

import os
import asyncio
import json
import time
from typing import Optional, AsyncGenerator, Dict, Any, List
from dataclasses import dataclass

# Try importing Anthropic
try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Try importing OpenAI
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class StreamConfig:
    """Configuration for LLM streaming"""
    model: str = "claude-opus-4-5-20251101"  # Opus 4.5 - most powerful model
    max_tokens: int = 4096
    temperature: float = 0.7
    thinking_enabled: bool = True  # Enable extended thinking
    chunk_delay_ms: int = 30  # Delay between chunks for smooth UI


class LLMStream:
    """
    Streaming LLM wrapper with WebSocket integration.
    
    Usage:
        llm = LLMStream(status_server, message_id)
        
        # Stream thinking
        async for chunk in llm.think("Analyze this task..."):
            pass  # Automatically broadcast to WebSocket
        
        # Stream content
        async for chunk in llm.respond("Based on my analysis..."):
            pass
    """
    
    def __init__(
        self,
        status_server,
        message_id: str,
        config: Optional[StreamConfig] = None,
    ):
        self.status_server = status_server
        self.message_id = message_id
        self.config = config or StreamConfig()
        
        # Initialize clients
        self._anthropic_client = None
        self._openai_client = None
        
        # State
        self._thinking_buffer = ""
        self._content_buffer = ""
    
    @property
    def anthropic(self):
        """Lazy AsyncAnthropic client initialization"""
        if self._anthropic_client is None and ANTHROPIC_AVAILABLE:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self._anthropic_client = AsyncAnthropic(api_key=api_key)
        return self._anthropic_client
    
    @property
    def openai(self):
        """Lazy OpenAI client initialization"""
        if self._openai_client is None and OPENAI_AVAILABLE:
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                self._openai_client = openai.OpenAI(api_key=api_key)
        return self._openai_client
    
    async def think(
        self,
        prompt: str,
        context: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """
        Stream AI thinking/reasoning process.
        
        Uses Claude's extended thinking feature for Chain-of-Thought.
        Broadcasts thinking chunks to WebSocket in real-time.
        
        Args:
            prompt: The prompt to think about
            context: Optional context to include
            max_tokens: Maximum thinking tokens
            
        Yields:
            Thinking text chunks
        """
        if not self.anthropic:
            # Fallback: simulate thinking
            yield "Analyzing the request...\n"
            await asyncio.sleep(0.5)
            yield f"Processing: {prompt[:100]}...\n"
            return
        
        # Build system prompt for thinking
        system = """You are a thoughtful AI assistant. When given a task, think through it step by step.
Express your reasoning process clearly, showing how you analyze the problem and arrive at conclusions.
Be specific and analytical."""
        
        messages = []
        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
            messages.append({"role": "assistant", "content": "I understand the context. Please provide the task."})
        messages.append({"role": "user", "content": prompt})
        
        try:
            # Use streaming API
            with self.anthropic.messages.stream(
                model=self.config.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                temperature=0.7,
            ) as stream:
                buffer = ""
                for text in stream.text_stream:
                    buffer += text
                    self._thinking_buffer += text
                    
                    # Broadcast to WebSocket
                    await self.status_server.stream_thinking(
                        self.message_id,
                        text,
                        is_complete=False,
                    )
                    
                    yield text
                    
                    # Small delay for smooth UI
                    if self.config.chunk_delay_ms > 0:
                        await asyncio.sleep(self.config.chunk_delay_ms / 1000)
            
            # Mark thinking complete
            await self.status_server.stream_thinking(
                self.message_id,
                "",
                is_complete=True,
            )
            
        except Exception as e:
            error_msg = f"\n[Thinking error: {str(e)}]"
            yield error_msg
            await self.status_server.stream_thinking(
                self.message_id,
                error_msg,
                is_complete=True,
            )
    
    async def respond(
        self,
        prompt: str,
        context: Optional[str] = None,
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """
        Stream AI response content.
        
        Broadcasts content chunks to WebSocket in real-time.
        
        Args:
            prompt: The prompt to respond to
            context: Optional context
            system: Optional system prompt
            max_tokens: Maximum response tokens
            
        Yields:
            Response text chunks
        """
        if not self.anthropic:
            # Fallback
            yield "Processing your request...\n"
            return
        
        system_prompt = system or "You are a helpful AI assistant. Be concise and informative."
        
        messages = []
        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
            messages.append({"role": "assistant", "content": "I understand. What would you like me to do?"})
        messages.append({"role": "user", "content": prompt})
        
        try:
            with self.anthropic.messages.stream(
                model=self.config.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
                temperature=self.config.temperature,
            ) as stream:
                for text in stream.text_stream:
                    self._content_buffer += text
                    
                    # Broadcast to WebSocket
                    await self.status_server.stream_content(
                        self.message_id,
                        text,
                    )
                    
                    yield text
                    
                    if self.config.chunk_delay_ms > 0:
                        await asyncio.sleep(self.config.chunk_delay_ms / 1000)
                        
        except Exception as e:
            error_msg = f"[Response error: {str(e)}]"
            yield error_msg
            await self.status_server.stream_content(self.message_id, error_msg)
    
    async def analyze(
        self,
        data: Any,
        analysis_type: str = "general",
        instructions: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream AI analysis of data.
        
        Specialized for data analysis tasks.
        
        Args:
            data: Data to analyze (will be JSON serialized)
            analysis_type: Type of analysis (general, patterns, insights, recommendations)
            instructions: Additional instructions
            
        Yields:
            Analysis text chunks
        """
        # Serialize data
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, indent=2, ensure_ascii=False)[:10000]  # Limit size
        else:
            data_str = str(data)[:10000]
        
        analysis_prompts = {
            "general": "Analyze the following data and provide insights:",
            "patterns": "Find patterns and trends in this data:",
            "insights": "Extract key insights from this data:",
            "recommendations": "Based on this data, provide actionable recommendations:",
        }
        
        prompt = f"""{analysis_prompts.get(analysis_type, analysis_prompts['general'])}

{data_str}

{instructions or ''}

Provide a structured analysis with clear sections."""

        async for chunk in self.respond(
            prompt,
            system="You are a data analyst. Provide clear, actionable insights from data. Use markdown formatting for structure.",
            max_tokens=2048,
        ):
            yield chunk
    
    async def generate_plan(
        self,
        task: str,
        constraints: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """
        Generate an execution plan for a task.
        
        Returns a structured plan with steps.
        
        Args:
            task: Task description
            constraints: Optional constraints
            
        Returns:
            List of plan steps with title and description
        """
        constraint_str = ""
        if constraints:
            constraint_str = "\n\nConstraints:\n" + "\n".join(f"- {c}" for c in constraints)
        
        prompt = f"""Create a detailed execution plan for the following task:

Task: {task}
{constraint_str}

Respond with a JSON array of steps. Each step should have:
- "title": Short step title
- "description": What this step does

Example format:
[
  {{"title": "Step 1", "description": "Do this first"}},
  {{"title": "Step 2", "description": "Then do this"}}
]

Only output the JSON array, no other text."""

        if not self.anthropic:
            # Fallback plan
            return [
                {"title": "Initialize", "description": "Set up the environment"},
                {"title": "Execute", "description": "Perform the main task"},
                {"title": "Complete", "description": "Finalize and report results"},
            ]
        
        try:
            response = await self.anthropic.messages.create(
                model=self.config.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Lower temperature for structured output
            )
            
            # Parse JSON from response
            text = response.content[0].text.strip()
            
            # Extract JSON array
            if "[" in text:
                start = text.index("[")
                end = text.rindex("]") + 1
                json_str = text[start:end]
                return json.loads(json_str)
            
            return [{"title": "Execute Task", "description": task}]
            
        except Exception as e:
            return [
                {"title": "Error", "description": f"Plan generation failed: {str(e)}"},
            ]
    
    def get_thinking(self) -> str:
        """Get accumulated thinking text"""
        return self._thinking_buffer
    
    def get_content(self) -> str:
        """Get accumulated content text"""
        return self._content_buffer
    
    def clear_buffers(self):
        """Clear accumulated text buffers"""
        self._thinking_buffer = ""
        self._content_buffer = ""


# Convenience functions

async def stream_thinking(
    status_server,
    message_id: str,
    prompt: str,
    context: Optional[str] = None,
) -> str:
    """
    Stream thinking and return full text.
    
    Convenience function for simple use cases.
    """
    llm = LLMStream(status_server, message_id)
    result = ""
    async for chunk in llm.think(prompt, context):
        result += chunk
    return result


async def stream_analysis(
    status_server,
    message_id: str,
    data: Any,
    analysis_type: str = "insights",
) -> str:
    """
    Stream analysis and return full text.
    """
    llm = LLMStream(status_server, message_id)
    result = ""
    async for chunk in llm.analyze(data, analysis_type):
        result += chunk
    return result


async def stream_response(
    status_server,
    message_id: str,
    prompt: str,
    system: Optional[str] = None,
) -> str:
    """
    Stream response and return full text.
    """
    llm = LLMStream(status_server, message_id)
    result = ""
    async for chunk in llm.respond(prompt, system=system):
        result += chunk
    return result


# Test
if __name__ == "__main__":
    async def test():
        print("Testing LLM Stream...")
        
        # Mock status server
        class MockServer:
            async def stream_thinking(self, msg_id, text, is_complete=False):
                print(f"[THINK] {text}", end="", flush=True)
            async def stream_content(self, msg_id, text):
                print(f"[CONTENT] {text}", end="", flush=True)
        
        llm = LLMStream(MockServer(), "test-123")
        
        # Test thinking
        print("\n=== Testing Think ===")
        async for chunk in llm.think("What is 2 + 2? Explain step by step."):
            pass
        
        print("\n\n=== Testing Respond ===")
        async for chunk in llm.respond("What is the capital of France?"):
            pass
        
        print("\n\n=== Testing Plan ===")
        plan = await llm.generate_plan("Analyze YC companies and find patterns")
        print(f"\nPlan: {json.dumps(plan, indent=2)}")
    
    asyncio.run(test())

