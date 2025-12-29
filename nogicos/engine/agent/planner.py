# -*- coding: utf-8 -*-
"""
Task Planner - Plan-Execute Architecture for Complex Tasks

Based on LangGraph's plan-and-execute pattern:
- Decompose complex tasks into steps
- Execute steps sequentially
- Replan when errors occur

Architecture:
    User Task → Planner → [Step 1 → Step 2 → ...] → Response
                   ↑              ↓ (on error)
                   └── Replanner ←┘
"""

import os
import json
import re
from typing import List, Dict, Any, Optional, Tuple, Union
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


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"      # Single tool call (list, read, etc.)
    MODERATE = "moderate"  # 2-3 tool calls
    COMPLEX = "complex"    # 4+ tool calls or multi-stage


@dataclass
class Plan:
    """Execution plan with steps"""
    steps: List[str]
    complexity: TaskComplexity = TaskComplexity.MODERATE
    estimated_tools: int = 0
    
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


@dataclass
class PlanExecuteState:
    """State for plan-execute loop"""
    input: str                                    # Original task
    plan: Plan = field(default_factory=lambda: Plan([]))
    past_steps: List[Tuple[str, str]] = field(default_factory=list)  # (step, result)
    response: Optional[str] = None
    error: Optional[str] = None


# Planning prompt
PLANNER_PROMPT = """You are a task planner for an AI agent that can control browser and files.

## Available Tools
- list_directory: List files in a folder
- move_file: Move/rename a file
- create_directory: Create a folder
- delete_file: Delete a file
- read_file: Read file content
- write_file: Write to a file
- navigate: Go to a URL
- click: Click on page elements
- screenshot: Take a screenshot

## Task
{task}

## Instructions
Break this task into 2-7 simple, executable steps.
Each step should be ONE tool call.
Steps should be in order of execution.
Do not add unnecessary steps.
The final step should complete the objective.

## Output Format
Return a JSON object with this structure:
```json
{
  "complexity": "simple|moderate|complex",
  "steps": ["Step 1 description", "Step 2 description", ...]
}
```

If the task is simple (single action), return:
```json
{
  "complexity": "simple",
  "steps": ["Execute the single action"]
}
```
"""

# Replanning prompt
REPLANNER_PROMPT = """You are replanning a task after an error occurred.

## Original Task
{task}

## Original Plan
{plan}

## Completed Steps
{past_steps}

## Error on Current Step
Step: {current_step}
Error: {error}

## Instructions
1. Analyze what went wrong
2. Decide if the task can continue or needs a different approach
3. If continuing: update the remaining steps
4. If the task is complete: set response
5. If the task cannot be completed: explain why

## Output Format
Return a JSON object:
```json
{
  "action": "continue|respond|fail",
  "steps": ["Remaining step 1", ...],  // if action is "continue"
  "response": "Final answer",           // if action is "respond" or "fail"
  "reason": "Why this action"
}
```
"""


class TaskPlanner:
    """
    Plan-Execute agent for complex tasks.
    
    Workflow:
    1. Analyze task complexity
    2. If simple: pass directly to ReAct agent
    3. If complex: generate plan, execute step by step
    4. On error: replan or abort
    """
    
    # Patterns for simple tasks (don't need planning)
    SIMPLE_PATTERNS = [
        r"^(list|show|看看|查看).*文件",  # Just list files
        r"^(read|读|打开).*文件",         # Just read a file
        r"^(go to|打开|访问).*网",        # Just navigate
        r"^(what|what's|什么是)",         # Just questions
        r"^(help|帮助|怎么)",             # Help requests
    ]
    
    def __init__(self, model: str = "claude-opus-4-5-20251101"):
        """
        Initialize task planner.
        
        Args:
            model: Claude model for planning
        """
        self.model = model
        self._client = None
    
    def _get_client(self):
        """Lazy-load Anthropic client"""
        if self._client is None and ANTHROPIC_AVAILABLE:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self._client = anthropic.Anthropic(api_key=api_key)
        return self._client
    
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
    
    async def plan(self, task: str) -> Plan:
        """
        Generate execution plan for a task.
        
        Args:
            task: User's task description
            
        Returns:
            Plan with steps
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
            # Call Claude for planning
            prompt = PLANNER_PROMPT.format(task=task)
            
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            
            # Parse response
            response_text = response.content[0].text
            plan_data = self._parse_json_response(response_text)
            
            if not plan_data or "steps" not in plan_data:
                logger.warning("Failed to parse plan, using single step")
                return Plan(steps=[task], complexity=TaskComplexity.SIMPLE)
            
            complexity = TaskComplexity(plan_data.get("complexity", "moderate"))
            steps = plan_data["steps"]
            
            logger.info(f"Generated plan with {len(steps)} steps ({complexity.value})")
            
            return Plan(
                steps=steps,
                complexity=complexity,
                estimated_tools=len(steps),
            )
            
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return Plan(steps=[task], complexity=TaskComplexity.SIMPLE)
    
    async def replan(
        self,
        state: PlanExecuteState,
        current_step: str,
        error: str,
    ) -> Tuple[str, Union[Plan, str]]:
        """
        Replan after an error.
        
        Args:
            state: Current execution state
            current_step: Step that failed
            error: Error message
            
        Returns:
            Tuple of (action, result)
            - ("continue", Plan): Continue with updated plan
            - ("respond", str): Return response to user
            - ("fail", str): Abort with error message
        """
        client = self._get_client()
        if not client:
            return ("fail", f"Step failed: {error}")
        
        try:
            # Format past steps
            past_steps_str = "\n".join(
                f"- {step}: {result}" for step, result in state.past_steps
            ) or "None"
            
            # Format current plan
            plan_str = "\n".join(f"- {s}" for s in state.plan.steps)
            
            prompt = REPLANNER_PROMPT.format(
                task=state.input,
                plan=plan_str,
                past_steps=past_steps_str,
                current_step=current_step,
                error=error,
            )
            
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            
            response_text = response.content[0].text
            replan_data = self._parse_json_response(response_text)
            
            if not replan_data:
                return ("fail", f"Replanning failed: {error}")
            
            action = replan_data.get("action", "fail")
            
            if action == "continue":
                new_steps = replan_data.get("steps", [])
                if new_steps:
                    logger.info(f"Replanned with {len(new_steps)} remaining steps")
                    return ("continue", Plan(steps=new_steps))
                return ("fail", "No steps to continue")
            
            elif action == "respond":
                response = replan_data.get("response", "Task completed with partial results.")
                return ("respond", response)
            
            else:  # fail
                reason = replan_data.get("response", error)
                return ("fail", reason)
                
        except Exception as e:
            logger.error(f"Replanning error: {e}")
            return ("fail", f"Replanning failed: {e}")
    
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
async def create_plan(task: str) -> Plan:
    """Quick plan creation"""
    planner = TaskPlanner()
    return await planner.plan(task)


def is_simple_task(task: str) -> bool:
    """Quick complexity check"""
    planner = TaskPlanner()
    return planner.is_simple_task(task)

