# -*- coding: utf-8 -*-
"""
Universal Task Executor - Main execution engine

Implements the Plan-and-Execute pattern with streaming feedback.
Handles any task through AI-driven planning and tool execution.
"""

import os
import json
import uuid
import asyncio
import time
from typing import Dict, Any, Optional, List, AsyncGenerator
from dataclasses import dataclass, asdict

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from .planner import TaskPlanner, ExecutionPlan, PlanStep, StepType
from .tool_router import ToolRouter, ToolResult, ToolCategory


@dataclass
class ExecutionResult:
    """Final result of task execution"""
    success: bool
    task: str
    summary: str
    steps_completed: int
    total_steps: int
    artifacts: List[str]  # File paths or artifact IDs
    duration_ms: int
    error: Optional[str] = None


EXECUTOR_SYSTEM_PROMPT = """You are an AI assistant executing tasks step by step.

For each step, you will:
1. Think about what needs to be done
2. Decide which tool to use (if any)
3. Execute the tool
4. Observe the result
5. Decide next action

When you need to use a tool, respond with a tool call.
When a step is complete, summarize what was accomplished.
When all steps are done, provide a final summary.

Be concise but thorough. Show your reasoning."""


class TaskExecutor:
    """
    Universal Task Executor
    
    Executes any task through:
    1. AI-driven planning
    2. Step-by-step execution with streaming
    3. Tool routing and dispatch
    4. Real-time WebSocket updates
    
    Usage:
        executor = TaskExecutor(status_server)
        result = await executor.execute("Analyze YC companies and generate a report")
    """
    
    def __init__(
        self,
        status_server=None,
        model: str = "claude-opus-4-5-20251101",  # Opus 4.5
    ):
        self.status_server = status_server
        self.model = model
        self.planner = TaskPlanner(model=model)
        self.tool_router = ToolRouter(status_server)
        self._client = None
        
        # Execution state
        self._current_plan: Optional[ExecutionPlan] = None
        self._message_id: str = ""
        self._artifacts: List[str] = []
    
    @property
    def client(self):
        """Lazy AsyncAnthropic client initialization"""
        if self._client is None and ANTHROPIC_AVAILABLE:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self._client = AsyncAnthropic(api_key=api_key)
        return self._client
    
    async def execute(
        self,
        task: str,
        context: Optional[str] = None,
        browser_session=None,
    ) -> ExecutionResult:
        """
        Execute a task with full streaming feedback.
        
        Args:
            task: Task description
            context: Optional context (current page, files, etc.)
            browser_session: Optional browser session for web tasks
            
        Returns:
            ExecutionResult with outcome
        """
        start_time = time.time()
        self._message_id = str(uuid.uuid4())[:8]
        self._artifacts = []
        
        try:
            # Phase 1: Think about the task
            await self._stream_thinking(task, context)
            
            # Phase 2: Create execution plan
            plan = await self._create_and_stream_plan(task, context)
            self._current_plan = plan
            
            # Phase 3: Execute steps
            steps_completed = 0
            for i, step in enumerate(plan.steps):
                success = await self._execute_step(step, i, len(plan.steps), context)
                if success:
                    steps_completed += 1
                else:
                    # Stop on failure (could add retry logic here)
                    break
            
            # Phase 4: Summarize results
            summary = await self._generate_summary(plan, steps_completed)
            
            # Mark complete
            if self.status_server:
                await self.status_server.stream_complete(
                    self._message_id,
                    summary=summary
                )
            
            return ExecutionResult(
                success=steps_completed == len(plan.steps),
                task=task,
                summary=summary,
                steps_completed=steps_completed,
                total_steps=len(plan.steps),
                artifacts=self._artifacts,
                duration_ms=int((time.time() - start_time) * 1000),
            )
            
        except Exception as e:
            error_msg = str(e)
            if self.status_server:
                await self.status_server.stream_error(self._message_id, error_msg)
            
            return ExecutionResult(
                success=False,
                task=task,
                summary=f"Execution failed: {error_msg}",
                steps_completed=0,
                total_steps=0,
                artifacts=[],
                duration_ms=int((time.time() - start_time) * 1000),
                error=error_msg,
            )
    
    async def _stream_thinking(self, task: str, context: Optional[str]):
        """Stream AI thinking about the task"""
        if not self.client or not self.status_server:
            return
        
        thinking_prompt = f"""Analyze this task and think about how to approach it:

Task: {task}

Think about:
1. What is the user trying to accomplish?
2. What steps are needed?
3. What tools might be useful?
4. What are potential challenges?

Keep your thinking concise but thorough."""

        if context:
            thinking_prompt += f"\n\nContext:\n{context}"
        
        try:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": thinking_prompt}],
                temperature=0.7,
            ) as stream:
                async for text in stream.text_stream:
                    await self.status_server.stream_thinking(
                        self._message_id,
                        text,
                        is_complete=False
                    )
                    await asyncio.sleep(0.02)  # Smooth streaming
            
            await self.status_server.stream_thinking(
                self._message_id,
                "",
                is_complete=True
            )
            
        except Exception as e:
            print(f"[Executor] Thinking error: {e}")
    
    async def _create_and_stream_plan(
        self,
        task: str,
        context: Optional[str],
    ) -> ExecutionPlan:
        """Create plan and stream it to frontend"""
        plan = await self.planner.create_plan(task, context)
        
        if self.status_server:
            # Stream the plan
            await self.status_server.stream_plan(
                self._message_id,
                plan.id,
                plan.title,
                [{"title": s.title, "description": s.description} for s in plan.steps]
            )
        
        return plan
    
    async def _execute_step(
        self,
        step: PlanStep,
        step_index: int,
        total_steps: int,
        context: Optional[str],
    ) -> bool:
        """
        Execute a single step with streaming feedback.
        
        Returns True if step succeeded, False otherwise.
        """
        # Debug log: Show step details
        import json as _json
        _log_path = r"c:\Users\WIN\Desktop\Cursor Project\.cursor\debug.log"
        try:
            with open(_log_path, 'a', encoding='utf-8') as _f:
                _f.write(_json.dumps({"location":"task_executor:_execute_step","message":"Executing step","data":{"step_index":step_index,"title":step.title,"step_type":step.step_type.value,"tool_name":step.tool_name,"tool_args":step.tool_args},"timestamp":__import__('time').time()*1000,"hypothesisId":"F"}) + '\n')
        except: pass
        
        # Mark step as in progress
        step.status = "in_progress"
        if self.status_server:
            await self.status_server.stream_plan_step_update(
                self._message_id,
                self._current_plan.id,
                step_index,
                "in_progress",
                0.0
            )
        
        try:
            # Execute based on step type
            if step.step_type == StepType.REASONING:
                result = await self._execute_reasoning_step(step, context)
            elif step.step_type in (StepType.BROWSER, StepType.FILE, StepType.SEARCH):
                result = await self._execute_tool_step(step)
            elif step.step_type == StepType.ANALYSIS:
                result = await self._execute_analysis_step(step, context)
            elif step.step_type == StepType.CODE:
                result = await self._execute_code_step(step)
            else:
                result = await self._execute_reasoning_step(step, context)
            
            # Mark step as completed
            step.status = "completed"
            step.progress = 1.0
            step.result = str(result)[:200] if result else "Completed"
            
            if self.status_server:
                await self.status_server.stream_plan_step_update(
                    self._message_id,
                    self._current_plan.id,
                    step_index,
                    "completed",
                    1.0,
                    step.result
                )
            
            return True
            
        except Exception as e:
            step.status = "failed"
            step.result = str(e)
            
            if self.status_server:
                await self.status_server.stream_plan_step_update(
                    self._message_id,
                    self._current_plan.id,
                    step_index,
                    "failed",
                    step.progress,
                    f"Error: {str(e)}"
                )
            
            return False
    
    async def _execute_reasoning_step(
        self,
        step: PlanStep,
        context: Optional[str],
    ) -> str:
        """Execute a reasoning step - may call tools if needed (agentic mode)"""
        if not self.client:
            return "Reasoning completed (no LLM available)"
        
        # Check if this step might need file operations
        step_lower = f"{step.title} {step.description}".lower()
        needs_tools = any(kw in step_lower for kw in ["移动", "归类", "整理", "move", "organize", "categorize", "sort", "分类"])
        
        # Debug log
        import json as _json
        _log_path = r"c:\Users\WIN\Desktop\Cursor Project\.cursor\debug.log"
        try:
            with open(_log_path, 'a', encoding='utf-8') as _f:
                _f.write(_json.dumps({"location":"task_executor:_execute_reasoning_step","message":"Reasoning step","data":{"step_title":step.title,"needs_tools":needs_tools,"has_context":bool(context)},"timestamp":__import__('time').time()*1000,"hypothesisId":"I"}) + '\n')
        except: pass
        
        if needs_tools:
            # Use agentic mode with tools for file operations
            return await self._execute_agentic_step(step, context)
        
        # Pure reasoning without tools
        prompt = f"""Execute this step:

Step: {step.title}
Description: {step.description}

{f'Context: {context}' if context else ''}

Provide a clear, concise response that completes this step."""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            return response.content[0].text
                
        except Exception as e:
            return f"Reasoning error: {e}"
    
    async def _execute_agentic_step(
        self,
        step: PlanStep,
        context: Optional[str],
    ) -> str:
        """Execute a step in agentic mode - LLM can call tools"""
        # Define file tools for the LLM
        tools = [
            {
                "name": "move_file",
                "description": "Move a file from source to destination",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Full path of file to move"},
                        "destination": {"type": "string", "description": "Full destination path including filename"}
                    },
                    "required": ["source", "destination"]
                }
            },
            {
                "name": "task_complete",
                "description": "Call this when all file operations are done",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "Summary of what was done"}
                    },
                    "required": ["summary"]
                }
            }
        ]
        
        prompt = f"""You are organizing files on a desktop. Execute this step:

Step: {step.title}
Description: {step.description}

Context (files scanned and folders created):
{context or 'No context available'}

IMPORTANT:
- Use move_file tool to move files to appropriate folders
- Desktop path: C:\\Users\\WIN\\Desktop
- Available folders: 文档, 图片, 视频, 压缩包, 其他
- Move .doc/.docx/.pdf/.txt to 文档
- Move .jpg/.png/.gif/.bmp to 图片
- Move .mp4/.avi/.mkv to 视频
- Move .zip/.rar/.7z to 压缩包
- Skip directories (folders), only move files
- Call task_complete when done

Execute the file moves now."""

        messages = [{"role": "user", "content": prompt}]
        results = []
        max_iterations = 20  # Safety limit
        
        # Debug log
        import json as _json
        _log_path = r"c:\Users\WIN\Desktop\Cursor Project\.cursor\debug.log"
        try:
            with open(_log_path, 'a', encoding='utf-8') as _f:
                _f.write(_json.dumps({"location":"task_executor:_execute_agentic_step:start","message":"Starting agentic loop","data":{"step_title":step.title},"timestamp":__import__('time').time()*1000,"hypothesisId":"I"}) + '\n')
        except: pass
        
        for iteration in range(max_iterations):
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    tools=tools,
                    messages=messages,
                    temperature=0.3,
                )
                
                # Check for tool use
                tool_used = False
                for block in response.content:
                    if block.type == "tool_use":
                        tool_used = True
                        tool_name = block.name
                        tool_input = block.input
                        tool_id = block.id
                        
                        # Debug log
                        try:
                            with open(_log_path, 'a', encoding='utf-8') as _f:
                                _f.write(_json.dumps({"location":"task_executor:_execute_agentic_step:tool_call","message":"Tool called","data":{"tool_name":tool_name,"tool_input":tool_input,"iteration":iteration},"timestamp":__import__('time').time()*1000,"hypothesisId":"I"}) + '\n')
                        except: pass
                        
                        if tool_name == "task_complete":
                            results.append(f"✅ Task complete: {tool_input.get('summary', 'Done')}")
                            return "\n".join(results)
                        
                        elif tool_name == "move_file":
                            # Execute the actual move
                            source = tool_input.get("source", "")
                            destination = tool_input.get("destination", "")
                            
                            move_result = await self.tool_router.execute("move_file", {
                                "source": source,
                                "destination": destination
                            })
                            
                            if move_result.success:
                                result_text = f"✅ Moved: {source} → {destination}"
                            else:
                                result_text = f"❌ Failed: {move_result.error}"
                            
                            results.append(result_text)
                            
                            # Add tool result to conversation
                            messages.append({"role": "assistant", "content": response.content})
                            messages.append({
                                "role": "user",
                                "content": [{
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": result_text
                                }]
                            })
                    
                    elif block.type == "text" and not tool_used:
                        # No tool call, LLM is done
                        return block.text if not results else "\n".join(results) + f"\n\n{block.text}"
                
                if not tool_used:
                    break
                    
            except Exception as e:
                results.append(f"Error: {str(e)}")
                break
        
        return "\n".join(results) if results else "Agentic step completed"
    
    async def _execute_tool_step(self, step: PlanStep) -> Any:
        """Execute a tool-based step"""
        tool_name = step.tool_name
        tool_args = step.tool_args
        
        # Debug log: Tool step entry
        import json as _json
        _log_path = r"c:\Users\WIN\Desktop\Cursor Project\.cursor\debug.log"
        try:
            with open(_log_path, 'a', encoding='utf-8') as _f:
                _f.write(_json.dumps({"location":"task_executor:_execute_tool_step:entry","message":"Tool step entry","data":{"original_tool_name":tool_name,"original_tool_args":tool_args,"step_title":step.title},"timestamp":__import__('time').time()*1000,"hypothesisId":"G"}) + '\n')
        except: pass
        
        if not tool_name:
            # Try to infer tool from step type
            tool_name = self._infer_tool(step)
            # Debug log: Inferred tool
            try:
                with open(_log_path, 'a', encoding='utf-8') as _f:
                    _f.write(_json.dumps({"location":"task_executor:_execute_tool_step:inferred","message":"Inferred tool name","data":{"inferred_tool_name":tool_name,"step_description":step.description},"timestamp":__import__('time').time()*1000,"hypothesisId":"G"}) + '\n')
            except: pass
        
        if not tool_name:
            return "No tool specified"
        
        # Stream tool start
        tool_id = str(uuid.uuid4())[:8]
        if self.status_server:
            await self.status_server.stream_tool_start(
                self._message_id,
                tool_id,
                tool_name
            )
            
            # Stream args
            args_str = json.dumps(tool_args, indent=2)
            for i in range(0, len(args_str), 10):
                chunk = args_str[i:i+10]
                await self.status_server.stream_tool_args(
                    self._message_id,
                    tool_id,
                    chunk,
                    is_complete=(i + 10 >= len(args_str))
                )
                await asyncio.sleep(0.03)
        
        # Execute tool
        result = await self.tool_router.execute(tool_name, tool_args)
        
        # Stream result
        if self.status_server:
            await self.status_server.stream_tool_result(
                self._message_id,
                tool_id,
                result=result.result if result.success else None,
                error=result.error,
                duration_ms=result.duration_ms
            )
        
        # Track artifacts
        if result.success and tool_name == "write_file":
            filepath = tool_args.get("filepath", "")
            if filepath:
                self._artifacts.append(filepath)
                
                # Stream artifact
                if self.status_server:
                    content = tool_args.get("content", "")[:2000]
                    await self.status_server.stream_artifact(
                        self._message_id,
                        str(uuid.uuid4())[:8],
                        os.path.basename(filepath),
                        content,
                        artifact_type=self._get_artifact_type(filepath),
                        file_path=filepath
                    )
        
        return result.result if result.success else result.error
    
    async def _execute_analysis_step(
        self,
        step: PlanStep,
        context: Optional[str],
    ) -> str:
        """Execute an analysis step using LLM"""
        if not self.client:
            return "Analysis completed (no LLM available)"
        
        # Get data to analyze
        data = step.tool_args.get("data", context or "")
        analysis_type = step.tool_args.get("analysis_type", "general")
        
        prompt = f"""Analyze the following data:

{data[:5000]}

Analysis type: {analysis_type}
Task context: {step.description}

Provide:
1. Key findings
2. Patterns identified
3. Insights and recommendations

Be specific and actionable."""

        try:
            # Non-streaming - analysis results go to step.result
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            return response.content[0].text
                
        except Exception as e:
            return f"Analysis error: {e}"
    
    async def _execute_code_step(self, step: PlanStep) -> str:
        """Execute a code generation step"""
        # For now, just use reasoning
        # Future: could integrate with code execution
        return await self._execute_reasoning_step(step, None)
    
    def _infer_tool(self, step: PlanStep) -> Optional[str]:
        """Infer tool name from step type and description"""
        desc_lower = step.description.lower()
        title_lower = step.title.lower()
        combined = f"{desc_lower} {title_lower}"
        
        if step.step_type == StepType.BROWSER:
            if "navigate" in combined or "go to" in combined or "open" in combined:
                return "browser_navigate"
            elif "click" in combined:
                return "browser_click"
            elif "type" in combined or "enter" in combined or "input" in combined:
                return "browser_type"
            elif "extract" in combined or "get" in combined or "scrape" in combined:
                return "browser_extract"
            elif "screenshot" in combined:
                return "browser_screenshot"
        
        elif step.step_type == StepType.FILE:
            # Check for list/scan first (most common for desktop org)
            if "list" in combined or "scan" in combined or "see" in combined or "view" in combined:
                return "list_directory"
            # Move/organize operations
            elif "move" in combined or "organize" in combined or "relocate" in combined:
                return "move_file"
            # Copy operations
            elif "copy" in combined or "duplicate" in combined:
                return "copy_file"
            # Delete operations
            elif "delete" in combined or "remove" in combined or "clean" in combined:
                return "delete_file"
            # Write/create file
            elif "write" in combined or "save" in combined or "create file" in combined:
                return "write_file"
            # Read file
            elif "read" in combined:
                return "read_file"
            # Create directory
            elif "directory" in combined or "folder" in combined or "mkdir" in combined:
                return "create_dir"
            # Shell command
            elif "shell" in combined or "command" in combined or "execute" in combined:
                return "shell_execute"
        
        elif step.step_type == StepType.SEARCH:
            return "web_search"
        
        return None
    
    def _get_artifact_type(self, filepath: str) -> str:
        """Get artifact type from file extension"""
        ext = os.path.splitext(filepath)[1].lower()
        type_map = {
            ".json": "json",
            ".md": "markdown",
            ".py": "code",
            ".js": "code",
            ".ts": "code",
            ".html": "code",
            ".css": "code",
            ".txt": "text",
        }
        return type_map.get(ext, "file")
    
    async def _generate_summary(
        self,
        plan: ExecutionPlan,
        steps_completed: int,
    ) -> str:
        """Generate execution summary with streaming"""
        if not self.client:
            summary = f"Completed {steps_completed}/{len(plan.steps)} steps."
            if self.status_server:
                await self.status_server.stream_content(self._message_id, summary)
            return summary
        
        # Gather step results
        step_summaries = []
        for step in plan.steps:
            status_emoji = "✅" if step.status == "completed" else "❌" if step.status == "failed" else "⏭️"
            step_summaries.append(f"{status_emoji} {step.title}: {step.result or 'No result'}")
        
        prompt = f"""Summarize the execution of this task:

Task: {plan.task}

Steps completed:
{chr(10).join(step_summaries)}

Artifacts created: {len(self._artifacts)}

Provide a brief, clear summary (2-3 sentences) of what was accomplished."""

        try:
            # Stream the final summary to main content area
            if self.status_server:
                async with self.client.messages.stream(
                    model=self.model,
                    max_tokens=256,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                ) as stream:
                    full_summary = ""
                    async for text in stream.text_stream:
                        full_summary += text
                        await self.status_server.stream_content(self._message_id, text)
                        await asyncio.sleep(0.02)
                    return full_summary
            else:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=256,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                return response.content[0].text
        except:
            return f"Completed {steps_completed}/{len(plan.steps)} steps. Created {len(self._artifacts)} artifacts."


# Convenience function
async def execute_task(
    task: str,
    status_server=None,
    context: Optional[str] = None,
) -> ExecutionResult:
    """
    Execute a task with default settings.
    
    Args:
        task: Task description
        status_server: Optional StatusServer for streaming
        context: Optional context
        
    Returns:
        ExecutionResult
    """
    executor = TaskExecutor(status_server)
    return await executor.execute(task, context)

