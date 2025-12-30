# -*- coding: utf-8 -*-
"""
Task Planner - Plan-Execute Architecture for Complex Tasks

Based on LangGraph's plan-and-execute pattern:
- Decompose complex tasks into steps
- Execute steps sequentially
- Replan when errors occur
- Dynamic tool discovery from registry

Architecture:
    User Task → Planner → [Step 1 → Step 2 → ...] → Response
                   ↑              ↓ (on error)
                   └── Replanner ←┘
"""

import os
import json
import re
from typing import List, Dict, Any, Optional, Tuple, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

# Anthropic client
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None

from engine.observability import get_logger
logger = get_logger("planner")

# Type checking imports
if TYPE_CHECKING:
    from engine.tools.base import ToolRegistry, ToolDefinition


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"      # Single tool call (list, read, etc.)
    MODERATE = "moderate"  # 2-3 tool calls
    COMPLEX = "complex"    # 4+ tool calls or multi-stage


@dataclass
class PlanStep:
    """A single step in a plan"""
    description: str
    suggested_tool: Optional[str] = None
    tool_args_hint: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, in_progress, completed, failed


@dataclass
class Plan:
    """Execution plan with steps"""
    steps: List[str]
    complexity: TaskComplexity = TaskComplexity.MODERATE
    estimated_tools: int = 0
    detailed_steps: List[PlanStep] = field(default_factory=list)
    
    def __len__(self):
        return len(self.steps)
    
    def __iter__(self):
        return iter(self.steps)
    
    def pop_first(self) -> Optional[str]:
        """Get and remove first step"""
        if self.steps:
            return self.steps.pop(0)
        return None
    
    @property
    def remaining(self) -> int:
        return len(self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "steps": self.steps,
            "complexity": self.complexity.value,
            "estimated_tools": self.estimated_tools,
        }


@dataclass
class PlanExecuteState:
    """State for plan-execute loop"""
    input: str                                    # Original task
    plan: Plan = field(default_factory=lambda: Plan([]))
    past_steps: List[Tuple[str, str]] = field(default_factory=list)  # (step, result)
    response: Optional[str] = None
    error: Optional[str] = None


# Dynamic planning prompt template
PLANNER_PROMPT_TEMPLATE = """You are a task planner for an AI agent. Your job is to break down complex tasks into simple, executable steps.

## Available Tools
{tools_description}

## Task
{task}

## Instructions
1. Analyze the task carefully
2. Break it into 2-7 simple, executable steps
3. Each step should map to ONE tool call
4. Steps should be in order of execution
5. Do not add unnecessary steps
6. The final step should complete the objective
7. For each step, suggest which tool to use

## Output Format
Return a JSON object:
```json
{{
  "complexity": "simple|moderate|complex",
  "steps": [
    {{"description": "Step 1 description", "tool": "suggested_tool_name"}},
    {{"description": "Step 2 description", "tool": "suggested_tool_name"}}
  ]
}}
```

If the task is simple (single action), return:
```json
{{
  "complexity": "simple",
  "steps": [{{"description": "Execute the action", "tool": "tool_name"}}]
}}
```
"""

# Smart replanning prompt with error analysis
REPLANNER_PROMPT = """You are replanning a task after an error occurred. Analyze the error and choose the best recovery strategy.

## Original Task
{task}

## Available Tools
{tools_description}

## Original Plan
{plan}

## Completed Steps
{past_steps}

## Error on Current Step
Step: {current_step}
Error: {error}

## Error Analysis Guidelines
1. **Permission Error**: Suggest alternative path or ask user for permission
2. **File Not Found**: Use list_directory first to find the file
3. **Network Error**: Retry with exponential backoff or use cached data
4. **Invalid Input**: Correct the input and retry
5. **Tool Not Available**: Find alternative tool or approach
6. **Timeout**: Simplify the step or break it down further

## Instructions
1. Analyze what went wrong (classify the error type)
2. Decide if the task can continue with a different approach
3. If continuing: provide updated steps with specific tool suggestions
4. If complete: summarize results
5. If failed: explain why clearly

## Output Format
```json
{{
  "action": "continue|respond|fail",
  "error_type": "permission|not_found|network|invalid_input|timeout|other",
  "analysis": "Brief analysis of what went wrong",
  "steps": [{{"description": "Step", "tool": "tool_name"}}],
  "response": "Final answer or error message",
  "reason": "Why this action"
}}
```
"""


class TaskPlanner:
    """
    Plan-Execute agent for complex tasks.
    
    Workflow:
    1. Analyze task complexity
    2. If simple: pass directly to ReAct agent
    3. If complex: generate plan, execute step by step
    4. On error: replan with intelligent error analysis
    
    Key Features:
    - Dynamic tool discovery from ToolRegistry
    - Smart error recovery with error type classification
    - Tool suggestion for each step
    """
    
    # Patterns for simple tasks (don't need planning)
    SIMPLE_PATTERNS = [
        r"^(list|show|看看|查看).*文件",  # Just list files
        r"^(read|读|打开).*文件",         # Just read a file
        r"^(go to|打开|访问).*网",        # Just navigate
        r"^(what|what's|什么是)",         # Just questions
        r"^(help|帮助|怎么)",             # Help requests
    ]
    
    def __init__(
        self, 
        model: str = "claude-opus-4-5-20251101",
        registry: Optional["ToolRegistry"] = None
    ):
        """
        Initialize task planner.
        
        Args:
            model: Claude model for planning
            registry: ToolRegistry for dynamic tool discovery
        """
        self.model = model
        self._client = None
        self._registry = registry
        self._tools_cache: Optional[str] = None
    
    def set_registry(self, registry: "ToolRegistry") -> None:
        """Set or update the tool registry"""
        self._registry = registry
        self._tools_cache = None  # Clear cache
    
    def _get_client(self):
        """Lazy-load Anthropic client"""
        if self._client is None and ANTHROPIC_AVAILABLE:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self._client = anthropic.Anthropic(api_key=api_key)
        return self._client
    
    def _build_tools_description(self, category_filter: Optional[str] = None) -> str:
        """
        Build tools description from registry.
        
        Args:
            category_filter: Optional category to filter tools (browser, local, etc.)
            
        Returns:
            Formatted string describing available tools
        """
        if self._registry is None:
            # Fallback to hardcoded list if no registry
            return """- list_directory: List files in a folder
- move_file: Move/rename a file  
- create_directory: Create a folder
- delete_file: Delete a file
- read_file: Read file content
- write_file: Write to a file
- browser_navigate: Go to a URL
- browser_click: Click on page elements
- browser_screenshot: Take a screenshot"""
        
        # Get tools from registry
        tools = self._registry.get_all()
        
        # Filter by category if specified
        if category_filter:
            from engine.tools.base import ToolCategory
            try:
                cat = ToolCategory(category_filter)
                tools = [t for t in tools if t.category == cat]
            except ValueError:
                pass  # Invalid category, use all tools
        
        # Build description with examples
        lines = []
        for tool in tools:
            # Extract parameter info
            params = tool.input_schema.get("properties", {})
            param_str = ", ".join(params.keys()) if params else "none"
            
            lines.append(f"- **{tool.name}**: {tool.description}")
            lines.append(f"  Parameters: {param_str}")
        
        return "\n".join(lines)
    
    def is_simple_task(self, task: str) -> bool:
        """
        Check if task is simple enough to skip planning.
        
        Simple tasks:
        - Single action requests
        - Information queries
        - Direct commands
        """
        task_lower = task.lower().strip()
        
        # Check against simple patterns FIRST
        for pattern in self.SIMPLE_PATTERNS:
            if re.search(pattern, task_lower):
                return True
        
        # Tasks with sequence indicators are COMPLEX (check before length)
        sequence_words = ["和", "并且", "然后", "接着", "最后", "先", "再", "，然后", "之后"]
        if any(word in task for word in sequence_words):
            return False
        
        # Tasks with multiple action verbs are COMPLEX
        action_words = ["整理", "移动", "创建", "删除", "下载", "保存", "分析", "总结", "生成", "备份", "复制", "重命名"]
        action_count = sum(1 for word in action_words if word in task)
        if action_count >= 2:
            return False
        
        # Short tasks are usually simple (check after complexity indicators)
        if len(task) < 20:
            return True
        
        # Medium length with single action is still simple
        if len(task) < 50 and action_count <= 1:
            return True
        
        # Default: longer tasks are complex
        return len(task) < 30
    
    async def plan(
        self, 
        task: str, 
        category_filter: Optional[str] = None
    ) -> Plan:
        """
        Generate execution plan for a task.
        
        Args:
            task: User's task description
            category_filter: Optional tool category to focus on
            
        Returns:
            Plan with steps and tool suggestions
        """
        # Check for simple task
        if self.is_simple_task(task):
            logger.debug(f"Simple task detected, skipping planning: {task[:50]}")
            return Plan(
                steps=[task],  # Single step = original task
                complexity=TaskComplexity.SIMPLE,
                estimated_tools=1,
            )
        
        client = self._get_client()
        if not client:
            logger.warning("No Anthropic client, falling back to simple execution")
            return Plan(steps=[task], complexity=TaskComplexity.SIMPLE)
        
        try:
            # Build dynamic tools description from registry
            tools_description = self._build_tools_description(category_filter)
            
            # Call Claude for planning with dynamic prompt
            prompt = PLANNER_PROMPT_TEMPLATE.format(
                tools_description=tools_description,
                task=task
            )
            
            # Call with timeout protection (30 seconds)
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
                timeout=30.0,  # 30 second timeout for planning
            )
            
            # Parse response
            response_text = response.content[0].text
            plan_data = self._parse_json_response(response_text)
            
            if not plan_data or "steps" not in plan_data:
                logger.warning("Failed to parse plan, using single step")
                return Plan(steps=[task], complexity=TaskComplexity.SIMPLE)
            
            complexity = TaskComplexity(plan_data.get("complexity", "moderate"))
            
            # Parse steps - now with tool suggestions
            steps_data = plan_data["steps"]
            step_descriptions = []
            detailed_steps = []
            
            for step in steps_data:
                if isinstance(step, dict):
                    desc = step.get("description", str(step))
                    tool = step.get("tool")
                    step_descriptions.append(desc)
                    detailed_steps.append(PlanStep(
                        description=desc,
                        suggested_tool=tool
                    ))
                else:
                    step_descriptions.append(str(step))
                    detailed_steps.append(PlanStep(description=str(step)))
            
            logger.info(f"Generated plan with {len(step_descriptions)} steps ({complexity.value})")
            
            return Plan(
                steps=step_descriptions,
                complexity=complexity,
                estimated_tools=len(step_descriptions),
                detailed_steps=detailed_steps,
            )
            
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return Plan(steps=[task], complexity=TaskComplexity.SIMPLE)
    
    async def replan(
        self,
        state: PlanExecuteState,
        current_step: str,
        error: str,
        category_filter: Optional[str] = None,
    ) -> Tuple[str, Union[Plan, str], Optional[str]]:
        """
        Replan after an error with intelligent error analysis.
        
        Args:
            state: Current execution state
            current_step: Step that failed
            error: Error message
            category_filter: Optional tool category filter
            
        Returns:
            Tuple of (action, result, error_type)
            - ("continue", Plan, error_type): Continue with updated plan
            - ("respond", str, error_type): Return response to user
            - ("fail", str, error_type): Abort with error message
        """
        client = self._get_client()
        if not client:
            return ("fail", f"Step failed: {error}", "other")
        
        try:
            # Build dynamic tools description
            tools_description = self._build_tools_description(category_filter)
            
            # Format past steps
            past_steps_str = "\n".join(
                f"- {step}: {result}" for step, result in state.past_steps
            ) or "None"
            
            # Format current plan
            plan_str = "\n".join(f"- {s}" for s in state.plan.steps)
            
            prompt = REPLANNER_PROMPT.format(
                task=state.input,
                tools_description=tools_description,
                plan=plan_str,
                past_steps=past_steps_str,
                current_step=current_step,
                error=error,
            )
            
            # Call with timeout protection (30 seconds)
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
                timeout=30.0,  # 30 second timeout for replanning
            )
            
            response_text = response.content[0].text
            replan_data = self._parse_json_response(response_text)
            
            if not replan_data:
                return ("fail", f"Replanning failed: {error}", "other")
            
            action = replan_data.get("action", "fail")
            error_type = replan_data.get("error_type", "other")
            analysis = replan_data.get("analysis", "")
            
            if analysis:
                logger.info(f"Error analysis: {analysis}")
            
            if action == "continue":
                steps_data = replan_data.get("steps", [])
                if steps_data:
                    # Parse steps with tool suggestions
                    step_descriptions = []
                    detailed_steps = []
                    
                    for step in steps_data:
                        if isinstance(step, dict):
                            desc = step.get("description", str(step))
                            tool = step.get("tool")
                            step_descriptions.append(desc)
                            detailed_steps.append(PlanStep(
                                description=desc,
                                suggested_tool=tool
                            ))
                        else:
                            step_descriptions.append(str(step))
                            detailed_steps.append(PlanStep(description=str(step)))
                    
                    logger.info(f"Replanned with {len(step_descriptions)} steps (error_type={error_type})")
                    new_plan = Plan(
                        steps=step_descriptions,
                        detailed_steps=detailed_steps
                    )
                    return ("continue", new_plan, error_type)
                return ("fail", "No steps to continue", error_type)
            
            elif action == "respond":
                resp = replan_data.get("response", "Task completed with partial results.")
                return ("respond", resp, error_type)
            
            else:  # fail
                reason = replan_data.get("response", error)
                return ("fail", reason, error_type)
                
        except Exception as e:
            logger.error(f"Replanning error: {e}")
            return ("fail", f"Replanning failed: {e}", "other")
    
    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response"""
        try:
            # Try to extract JSON block
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end].strip()
            
            return json.loads(text)
            
        except json.JSONDecodeError:
            # Try to find JSON object in text
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            return None


# Convenience functions
async def create_plan(task: str, registry: Optional["ToolRegistry"] = None) -> Plan:
    """Quick plan creation with optional registry"""
    planner = TaskPlanner(registry=registry)
    return await planner.plan(task)


def is_simple_task(task: str) -> bool:
    """Quick complexity check"""
    planner = TaskPlanner()
    return planner.is_simple_task(task)


# Export all for easy importing
__all__ = [
    "TaskPlanner",
    "Plan",
    "PlanStep",
    "PlanExecuteState",
    "TaskComplexity",
    "create_plan",
    "is_simple_task",
]

