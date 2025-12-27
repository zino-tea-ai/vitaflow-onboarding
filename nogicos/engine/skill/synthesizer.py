# -*- coding: utf-8 -*-
"""
Skill Synthesizer - Generate parameterized Python code from trajectories

Based on SkillWeaver's KnowledgeBase.update() method.

Flow:
    1. Receive trajectory + task description
    2. Build synthesis prompt with context
    3. Call LLM to generate parameterized Python function
    4. Validate generated code
    5. Retry if validation fails (up to max_retries)
    6. Return synthesized skill

Reference: SkillWeaver paper (arXiv:2504.07079)
"""

import ast
import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger("nogicos.skill.synthesizer")


# =============================================================================
# Synthesis Prompt Template (based on SkillWeaver's kb_procedural_update_single_templ)
# =============================================================================

SKILL_SYNTHESIS_PROMPT = '''You are an expert Python programmer specializing in browser automation with Playwright.

Your task is to synthesize a reusable, parameterized Python function from the following task execution trajectory.

## Context

**Task Description:**
{task}

**Target Domain:**
{domain}

**Execution Trajectory (Action History):**
{trajectory}

## Requirements

1. Create a single async Python function that:
   - Takes `page` as the first parameter (Playwright Page object)
   - Extracts variable parts from the trajectory as function parameters
   - Uses descriptive parameter names with type hints
   - Includes a docstring explaining what the function does
   - Returns a meaningful result (e.g., extracted data, success status)

2. Make the function PARAMETERIZED:
   - If the trajectory includes a search query, extract it as a `query: str` parameter
   - If there are form inputs, extract them as parameters
   - Use sensible defaults where appropriate

3. Make the function ROBUST:
   - Use reasonable timeouts (e.g., `timeout=15000`)
   - Handle common failure cases gracefully
   - Use `wait_for_load_state` or `wait_for_selector` where appropriate

4. Code style:
   - Use async/await syntax
   - Use Playwright's async API (e.g., `await page.fill()`, `await page.click()`)
   - Keep the function focused on a single task

## Output Format

Return ONLY the Python function code, no markdown code blocks, no explanations.
The function should be ready to execute with `exec()`.

Example output format:
async def search_website(page, query: str):
    """Search for content on the website"""
    await page.fill("input[type=text]", query)
    await page.click("button[type=submit]")
    await page.wait_for_load_state("networkidle")
    return True

## Your Response (Python code only):
'''


# =============================================================================
# Code Validation
# =============================================================================

@dataclass
class ValidationResult:
    """Result of code validation"""
    valid: bool
    errors: List[str]
    function_name: Optional[str] = None
    parameters: Optional[List[Dict[str, str]]] = None


def validate_skill_code(code: str) -> ValidationResult:
    """
    Validate synthesized skill code
    
    Checks:
    1. Valid Python syntax
    2. Contains exactly one async function
    3. First parameter is 'page'
    4. Has a docstring
    
    Args:
        code: Python code string
    
    Returns:
        ValidationResult with errors if any
    """
    errors = []
    function_name = None
    parameters = []
    
    # Remove markdown code blocks if present
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        # Find end of code block
        end_idx = -1
        for i, line in enumerate(lines[1:], 1):
            if line.strip().startswith("```"):
                end_idx = i
                break
        if end_idx > 0:
            code = "\n".join(lines[1:end_idx])
        else:
            code = "\n".join(lines[1:])
    
    # Check 1: Valid Python syntax
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return ValidationResult(
            valid=False,
            errors=[f"Syntax error: {e}"],
        )
    
    # Check 2: Contains async function
    async_funcs = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
    ]
    
    if len(async_funcs) == 0:
        errors.append("Code must contain an async function")
    elif len(async_funcs) > 1:
        errors.append("Code should contain only one async function")
    else:
        func = async_funcs[0]
        function_name = func.name
        
        # Check 3: First parameter is 'page'
        if not func.args.args or func.args.args[0].arg != "page":
            errors.append("First parameter must be 'page' (Playwright Page)")
        
        # Check 4: Has docstring
        if not (func.body and isinstance(func.body[0], ast.Expr) and 
                isinstance(func.body[0].value, ast.Constant)):
            errors.append("Function should have a docstring")
        
        # Extract parameters (skip 'page')
        for arg in func.args.args[1:]:
            param_info = {
                "name": arg.arg,
                "type": "str",  # Default
            }
            # Try to get type hint
            if arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    param_info["type"] = arg.annotation.id
                elif isinstance(arg.annotation, ast.Constant):
                    param_info["type"] = str(arg.annotation.value)
            parameters.append(param_info)
    
    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        function_name=function_name,
        parameters=parameters,
    )


def extract_function_name(code: str) -> Optional[str]:
    """Extract function name from code"""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                return node.name
    except:
        pass
    return None


def clean_code(code: str) -> str:
    """Clean generated code - remove markdown, extra whitespace"""
    code = code.strip()
    
    # Remove markdown code blocks
    if code.startswith("```"):
        lines = code.split("\n")
        # Skip first line (```python)
        start_idx = 1
        end_idx = len(lines)
        for i, line in enumerate(lines[1:], 1):
            if line.strip().startswith("```"):
                end_idx = i
                break
        code = "\n".join(lines[start_idx:end_idx])
    
    return code.strip()


# =============================================================================
# Trajectory Formatting
# =============================================================================

def format_trajectory(actions: List[Dict[str, Any]]) -> str:
    """
    Format trajectory actions into a readable string for the LLM
    
    Args:
        actions: List of action dictionaries
    
    Returns:
        Formatted string describing the trajectory
    """
    lines = []
    
    for i, action in enumerate(actions, 1):
        action_type = action.get("action_type", "unknown")
        
        if action_type == "navigate":
            url = action.get("url", "")
            lines.append(f"{i}. Navigate to: {url}")
            
        elif action_type == "click":
            selector = action.get("selector", "")
            lines.append(f"{i}. Click on element: {selector}")
            
        elif action_type == "input":
            selector = action.get("selector", "")
            value = action.get("value", "")
            # Mask sensitive values
            if any(kw in selector.lower() for kw in ["password", "secret", "token"]):
                value = "***"
            lines.append(f'{i}. Fill "{selector}" with value: "{value}"')
            
        elif action_type == "submit":
            selector = action.get("selector", "")
            lines.append(f"{i}. Submit form: {selector}")
            
        elif action_type == "code":
            code = action.get("code", "")[:100]  # Truncate
            reasoning = action.get("reasoning", "")[:100]
            lines.append(f"{i}. Execute code: {code}...")
            if reasoning:
                lines.append(f"   Reasoning: {reasoning}...")
        else:
            lines.append(f"{i}. {action_type}: {action}")
    
    return "\n".join(lines)


# =============================================================================
# Skill Synthesizer Class
# =============================================================================

class SkillSynthesizer:
    """
    Synthesize parameterized skills from trajectories
    
    Based on SkillWeaver's KnowledgeBase.update() method.
    
    Usage:
        synthesizer = SkillSynthesizer(llm)
        result = await synthesizer.synthesize(
            task="Search for AI on Hacker News",
            trajectory=actions,
            domain="news.ycombinator.com",
        )
        if result.success:
            print(result.code)
            print(result.function_name)
            print(result.parameters)
    """
    
    def __init__(
        self,
        llm=None,
        max_retries: int = 3,
    ):
        """
        Initialize synthesizer
        
        Args:
            llm: LangChain LLM instance (e.g., ChatAnthropic)
            max_retries: Max retry attempts for synthesis
        """
        self._llm = llm
        self.max_retries = max_retries
    
    @property
    def llm(self):
        """Lazy LLM initialization"""
        if self._llm is None:
            # Import here to avoid circular imports
            from langchain_anthropic import ChatAnthropic
            import os
            
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            
            self._llm = ChatAnthropic(
                model="claude-sonnet-4-20250514",  # Use Sonnet for synthesis (faster, cheaper)
                api_key=api_key,
                max_tokens=2048,
            )
        return self._llm
    
    async def synthesize(
        self,
        task: str,
        trajectory: List[Dict[str, Any]],
        domain: str,
        existing_code: str = "",
    ) -> "SynthesisResult":
        """
        Synthesize a skill from a trajectory
        
        Args:
            task: Task description
            trajectory: List of action dictionaries
            domain: Target domain
            existing_code: Optional existing code for context
        
        Returns:
            SynthesisResult with code, function name, and parameters
        """
        # Format trajectory
        trajectory_str = format_trajectory(trajectory)
        
        # Build prompt
        prompt = SKILL_SYNTHESIS_PROMPT.format(
            task=task,
            domain=domain,
            trajectory=trajectory_str,
        )
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Add feedback from previous attempt if any
                if last_error:
                    prompt_with_feedback = f"{prompt}\n\nPrevious attempt had errors:\n{last_error}\n\nPlease fix these issues:"
                else:
                    prompt_with_feedback = prompt
                
                # Call LLM
                logger.info(f"[Synthesizer] Attempt {attempt + 1}/{self.max_retries}")
                
                response = await self.llm.ainvoke(prompt_with_feedback)
                code = clean_code(response.content)
                
                # Validate code
                validation = validate_skill_code(code)
                
                if validation.valid:
                    logger.info(f"[Synthesizer] Success! Function: {validation.function_name}")
                    return SynthesisResult(
                        success=True,
                        code=code,
                        function_name=validation.function_name,
                        parameters=validation.parameters,
                    )
                else:
                    last_error = "; ".join(validation.errors)
                    logger.warning(f"[Synthesizer] Validation failed: {last_error}")
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"[Synthesizer] Error: {e}")
        
        # All retries failed
        return SynthesisResult(
            success=False,
            error=f"Synthesis failed after {self.max_retries} attempts: {last_error}",
        )
    
    def synthesize_sync(
        self,
        task: str,
        trajectory: List[Dict[str, Any]],
        domain: str,
    ) -> "SynthesisResult":
        """Synchronous wrapper for synthesize"""
        import asyncio
        return asyncio.run(self.synthesize(task, trajectory, domain))


@dataclass
class SynthesisResult:
    """Result of skill synthesis"""
    success: bool
    code: str = ""
    function_name: Optional[str] = None
    parameters: Optional[List[Dict[str, str]]] = None
    error: Optional[str] = None


# =============================================================================
# Quick Test
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test_synthesizer():
        print("=" * 50)
        print("Skill Synthesizer Test")
        print("=" * 50)
        
        # Test trajectory formatting
        print("\n[1] Testing trajectory formatting...")
        actions = [
            {"action_type": "navigate", "url": "https://news.ycombinator.com"},
            {"action_type": "click", "selector": "input.search"},
            {"action_type": "input", "selector": "input.search", "value": "AI news"},
            {"action_type": "click", "selector": "button[type=submit]"},
        ]
        formatted = format_trajectory(actions)
        print(formatted)
        
        # Test code validation
        print("\n[2] Testing code validation...")
        test_code = '''
async def search_hn(page, query: str):
    """Search for content on Hacker News"""
    await page.fill("input.search", query)
    await page.click("button[type=submit]")
    return True
'''
        validation = validate_skill_code(test_code)
        print(f"    Valid: {validation.valid}")
        print(f"    Function: {validation.function_name}")
        print(f"    Parameters: {validation.parameters}")
        print(f"    Errors: {validation.errors}")
        
        # Test invalid code
        print("\n[3] Testing invalid code validation...")
        invalid_code = "def not_async(): pass"
        validation = validate_skill_code(invalid_code)
        print(f"    Valid: {validation.valid}")
        print(f"    Errors: {validation.errors}")
        
        # Test with markdown
        print("\n[4] Testing code cleaning...")
        markdown_code = '''```python
async def test(page):
    """Test"""
    return True
```'''
        cleaned = clean_code(markdown_code)
        print(f"    Cleaned:\n{cleaned}")
        
        print("\n" + "=" * 50)
        print("Synthesizer Test Complete!")
        print("=" * 50)
    
    asyncio.run(test_synthesizer())

