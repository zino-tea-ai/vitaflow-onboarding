# -*- coding: utf-8 -*-
"""
Task Planner - AI-driven task decomposition and planning

Uses Claude to analyze tasks and generate execution plans.
Implements the "Plan-and-Execute" pattern from LangGraph.
"""

import os
import json
import uuid
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class StepType(str, Enum):
    """Types of execution steps"""
    BROWSER = "browser"      # Web browsing/scraping
    ANALYSIS = "analysis"    # Data analysis with AI
    FILE = "file"            # File operations
    SEARCH = "search"        # Information search
    CODE = "code"            # Code generation/execution
    REASONING = "reasoning"  # Pure AI reasoning
    USER_INPUT = "user_input"  # Requires user input


@dataclass
class PlanStep:
    """A single step in the execution plan"""
    id: str
    index: int
    title: str
    description: str
    step_type: StepType
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed, skipped
    progress: float = 0.0
    result: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "index": self.index,
            "title": self.title,
            "description": self.description,
            "stepType": self.step_type.value,
            "toolName": self.tool_name,
            "toolArgs": self.tool_args,
            "dependsOn": self.depends_on,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
        }


@dataclass
class ExecutionPlan:
    """Complete execution plan for a task"""
    id: str
    title: str
    task: str
    steps: List[PlanStep]
    created_at: str = ""
    estimated_duration_ms: int = 0
    
    @property
    def current_step(self) -> int:
        for i, step in enumerate(self.steps):
            if step.status == "in_progress":
                return i
            if step.status == "pending":
                return i
        return len(self.steps)
    
    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == "completed")
        return completed / len(self.steps)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "task": self.task,
            "steps": [s.to_dict() for s in self.steps],
            "currentStep": self.current_step,
            "progress": self.progress,
            "estimatedDurationMs": self.estimated_duration_ms,
        }


PLANNER_SYSTEM_PROMPT = """You are a task planning AI. Given a user's task, create a detailed execution plan.

## Available Tools

### File Operations (step_type: "file")
- list_directory: List files in a directory
  - args: {"path": "/path/to/directory"}
- read_file: Read file content
  - args: {"filepath": "/path/to/file"}
- write_file: Write content to file
  - args: {"filepath": "/path/to/file", "content": "file content"}
- move_file: Move/rename a file
  - args: {"source": "/from/path", "destination": "/to/path"}
- copy_file: Copy a file
  - args: {"source": "/from/path", "destination": "/to/path"}
- delete_file: Delete a file
  - args: {"path": "/path/to/file", "recursive": false}
- create_dir: Create a directory
  - args: {"dirpath": "/path/to/new/dir"}

### Browser Operations (step_type: "browser")
- browser_navigate: Go to a URL
  - args: {"url": "https://..."}
- browser_click: Click an element
  - args: {"selector": "css selector or text"}
- browser_type: Type text into input
  - args: {"selector": "input selector", "text": "text to type"}
- browser_extract: Extract page content
  - args: {"selector": "optional css selector"}
- browser_screenshot: Take screenshot
  - args: {}

### Shell Commands (step_type: "file")
- shell_execute: Run shell command
  - args: {"command": "ls -la", "timeout": 30}

## IMPORTANT for Desktop Operations
- User's Desktop path on Windows: C:\\Users\\WIN\\Desktop
- Always use full absolute paths!
- For "organize desktop" tasks, you MUST:
  1. First use list_directory to scan files
  2. Create category folders with create_dir
  3. **CRITICAL: Generate move_file steps for EACH file** that needs to be moved!
  4. Example: If you see "report.docx" on desktop, add a step: move_file(source="C:\\Users\\WIN\\Desktop\\report.docx", destination="C:\\Users\\WIN\\Desktop\\文档\\report.docx")
  
- DO NOT use "reasoning" steps to "analyze" files - use actual move_file tool calls!
- Each file must have its own move_file step with specific source and destination paths

## Response Format
Respond with a JSON object:
{
  "title": "Plan title",
  "steps": [
    {
      "title": "Step title",
      "description": "What this step does",
      "step_type": "file|browser|reasoning",
      "tool_name": "list_directory",
      "tool_args": {"path": "C:\\\\Users\\\\WIN\\\\Desktop"}
    }
  ]
}

Keep plans focused and efficient. 3-7 steps max.
ALWAYS specify tool_name and tool_args for file/browser steps!"""


class TaskPlanner:
    """
    AI-driven task planner using Claude.
    
    Analyzes user tasks and generates structured execution plans.
    """
    
    def __init__(self, model: str = "claude-opus-4-5-20251101"):  # Opus 4.5
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
    
    async def create_plan(
        self,
        task: str,
        context: Optional[str] = None,
        constraints: Optional[List[str]] = None,
    ) -> ExecutionPlan:
        """
        Create an execution plan for a task.
        
        Args:
            task: User's task description
            context: Optional context (current page, files, etc.)
            constraints: Optional constraints to follow
            
        Returns:
            ExecutionPlan with steps
        """
        if not self.client:
            return self._fallback_plan(task)
        
        # Build prompt
        prompt = f"Task: {task}"
        
        if context:
            prompt += f"\n\nContext:\n{context}"
        
        if constraints:
            prompt += f"\n\nConstraints:\n" + "\n".join(f"- {c}" for c in constraints)
        
        prompt += "\n\nCreate a detailed execution plan."
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=PLANNER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            
            # Parse JSON from response
            text = response.content[0].text.strip()
            plan_data = self._parse_json(text)
            
            # Build ExecutionPlan
            plan_id = str(uuid.uuid4())[:8]
            steps = []
            
            for i, step_data in enumerate(plan_data.get("steps", [])):
                step_type = self._parse_step_type(step_data.get("step_type", "reasoning"))
                
                step = PlanStep(
                    id=f"{plan_id}-{i}",
                    index=i,
                    title=step_data.get("title", f"Step {i+1}"),
                    description=step_data.get("description", ""),
                    step_type=step_type,
                    tool_name=step_data.get("tool_name"),
                    tool_args=step_data.get("tool_args", {}),
                )
                steps.append(step)
            
            # Debug log: Generated plan
            import json as _json
            _log_path = r"c:\Users\WIN\Desktop\Cursor Project\.cursor\debug.log"
            try:
                _steps_data = [{"title":s.title,"step_type":s.step_type.value,"tool_name":s.tool_name,"tool_args":s.tool_args} for s in steps]
                with open(_log_path, 'a', encoding='utf-8') as _f:
                    _f.write(_json.dumps({"location":"planner:create_plan:return","message":"Generated plan","data":{"plan_id":plan_id,"title":plan_data.get("title",""),"steps_count":len(steps),"steps":_steps_data},"timestamp":__import__('time').time()*1000,"hypothesisId":"H"}) + '\n')
            except: pass
            
            return ExecutionPlan(
                id=plan_id,
                title=plan_data.get("title", task[:50]),
                task=task,
                steps=steps,
            )
            
        except Exception as e:
            print(f"[Planner] Error: {e}")
            return self._fallback_plan(task)
    
    def _parse_json(self, text: str) -> dict:
        """Extract and parse JSON from text"""
        # Try to find JSON object
        if "{" in text:
            start = text.index("{")
            # Find matching closing brace
            depth = 0
            end = start
            for i, c in enumerate(text[start:], start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            
            json_str = text[start:end]
            return json.loads(json_str)
        
        return {"title": "Task", "steps": []}
    
    def _parse_step_type(self, type_str: str) -> StepType:
        """Parse step type string to enum"""
        type_map = {
            "browser": StepType.BROWSER,
            "analysis": StepType.ANALYSIS,
            "file": StepType.FILE,
            "search": StepType.SEARCH,
            "code": StepType.CODE,
            "reasoning": StepType.REASONING,
            "user_input": StepType.USER_INPUT,
        }
        return type_map.get(type_str.lower(), StepType.REASONING)
    
    def _fallback_plan(self, task: str) -> ExecutionPlan:
        """Create a basic fallback plan when AI is unavailable"""
        plan_id = str(uuid.uuid4())[:8]
        
        steps = [
            PlanStep(
                id=f"{plan_id}-0",
                index=0,
                title="Analyze Task",
                description=f"Understand and analyze: {task}",
                step_type=StepType.REASONING,
            ),
            PlanStep(
                id=f"{plan_id}-1",
                index=1,
                title="Execute Task",
                description="Perform the main task operations",
                step_type=StepType.REASONING,
            ),
            PlanStep(
                id=f"{plan_id}-2",
                index=2,
                title="Report Results",
                description="Summarize findings and results",
                step_type=StepType.REASONING,
            ),
        ]
        
        return ExecutionPlan(
            id=plan_id,
            title=task[:50],
            task=task,
            steps=steps,
        )
    
    async def refine_step(
        self,
        step: PlanStep,
        context: str,
    ) -> PlanStep:
        """
        Refine a plan step with more details based on context.
        
        Used when a step needs more specific instructions.
        """
        if not self.client:
            return step
        
        prompt = f"""Refine this execution step with more specific details:

Step: {step.title}
Description: {step.description}
Type: {step.step_type.value}

Current Context:
{context}

Provide:
1. More specific tool_name if applicable
2. Detailed tool_args
3. Updated description

Respond with JSON:
{{
  "tool_name": "specific_tool",
  "tool_args": {{"arg": "value"}},
  "description": "refined description"
}}"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            
            data = self._parse_json(response.content[0].text)
            
            if data.get("tool_name"):
                step.tool_name = data["tool_name"]
            if data.get("tool_args"):
                step.tool_args = data["tool_args"]
            if data.get("description"):
                step.description = data["description"]
                
        except Exception as e:
            print(f"[Planner] Refine error: {e}")
        
        return step

