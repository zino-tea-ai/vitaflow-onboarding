# -*- coding: utf-8 -*-
"""
Hive Agent Nodes

Each node is a function that takes state and returns state updates.

Nodes:
- observe: Get current browser state
- think: Decide what action to take
- act: Execute the action
- terminate: Return final result
"""

import json
import re
import logging
import asyncio
from typing import Literal, Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from anthropic import APIConnectionError, RateLimitError, APIStatusError

from engine.hive.state import AgentState, PageState
from engine.browser.visual import visual_feedback

# Configure logging
logger = logging.getLogger("nogicos.hive")

# Token estimation (rough: 1 token ~ 4 chars for English)
MAX_CONTEXT_TOKENS = 100000  # Claude Opus context
RESERVED_TOKENS = 8000  # For system prompt + response
MAX_AXTREE_TOKENS = MAX_CONTEXT_TOKENS - RESERVED_TOKENS

# Prompt templates
SYSTEM_PROMPT = """You are an AI browser agent. You interact with websites via Playwright.

RULES:
1. ALWAYS add .first after get_by_role() to avoid strict mode errors
2. ALWAYS use timeout=15000 for click(), fill(), press()
3. NEVER use non-ASCII characters in code
4. When task is complete, set terminate_with_result to the answer

You will receive:
- Current page state (URL, title, accessibility tree)
- Previous actions taken

Respond with JSON:
{
    "reasoning": "step by step thinking",
    "action_type": "code" | "terminate",
    "python_code": "async def act(page): ...",  // if action_type is "code"
    "result": "final answer"  // if action_type is "terminate"
}
"""

OBSERVE_PROMPT = """Current page state:
URL: {url}
Title: {title}

Accessibility Tree:
{axtree}

Task: {task}
Step: {step}/{max_steps}

Previous actions:
{previous_actions}

What should you do next?"""


async def observe_node(state: AgentState, browser_session) -> dict:
    """
    Observe node - Get current browser state
    
    Args:
        state: Current agent state
        browser_session: Browser session instance
    
    Returns:
        State update with page_state
    """
    # Get page state from browser
    page_state = await browser_session.observe()
    
    return {
        "page_state": {
            "url": page_state.url,
            "title": page_state.title,
            "axtree": page_state.get_axtree_string(),
            "screenshot_base64": None,  # Can add if needed
        }
    }


def estimate_tokens(text: str) -> int:
    """Estimate token count (rough: 1 token ~ 4 chars)"""
    return len(text) // 4


def truncate_axtree(axtree: str, max_tokens: int = MAX_AXTREE_TOKENS) -> str:
    """
    Smart truncation of accessibility tree
    
    Preserves structure by keeping:
    1. First N lines (top of page)
    2. Interactive elements (buttons, links, inputs)
    """
    if estimate_tokens(axtree) <= max_tokens:
        return axtree
    
    lines = axtree.split('\n')
    
    # Keep first 200 lines (top of page)
    kept_lines = lines[:200]
    
    # Add interactive elements from rest
    interactive_keywords = ['button', 'link', 'textbox', 'input', 'checkbox', 'radio']
    for line in lines[200:]:
        line_lower = line.lower()
        if any(kw in line_lower for kw in interactive_keywords):
            kept_lines.append(line)
        
        if estimate_tokens('\n'.join(kept_lines)) > max_tokens:
            break
    
    result = '\n'.join(kept_lines)
    if len(result) < len(axtree):
        result += f"\n\n[Truncated: {len(lines) - len(kept_lines)} lines omitted]"
    
    return result


async def think_node(
    state: AgentState, 
    llm: ChatAnthropic,
    max_retries: int = 3,
    verbose: bool = False,
) -> dict:
    """
    Think node - Decide what action to take
    
    Uses Claude to analyze page state and decide next action.
    
    Error handling:
    - APIConnectionError: Retry with exponential backoff
    - RateLimitError: Wait and retry
    - APIStatusError: Log and fail gracefully
    """
    page = state.get("page_state", {})
    
    # Format previous actions with more detail
    prev_actions = []
    for i, action in enumerate(state.get("actions", [])):
        action_type = action.get("action_type", "unknown")
        if action_type == "code":
            exec_result = action.get("execution_result", {})
            status = "OK" if exec_result.get("success") else "FAILED"
            error = exec_result.get("error", "")
            prev_actions.append(f"Step {i+1}: Executed code [{status}]" + (f" - {error}" if error else ""))
        elif action_type == "terminate":
            prev_actions.append(f"Step {i+1}: Terminated with result")
    
    prev_actions_str = "\n".join(prev_actions) if prev_actions else "None yet"
    
    # Smart truncation of axtree
    raw_axtree = page.get("axtree", "No accessibility tree")
    truncated_axtree = truncate_axtree(raw_axtree)
    
    # Create prompt
    user_prompt = OBSERVE_PROMPT.format(
        url=page.get("url", "unknown"),
        title=page.get("title", "unknown"),
        axtree=truncated_axtree,
        task=state["task"],
        step=state["current_step"] + 1,
        max_steps=state["max_steps"],
        previous_actions=prev_actions_str,
    )
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]
    
    if verbose:
        logger.info(f"[Think] Step {state['current_step'] + 1}/{state['max_steps']}")
        logger.debug(f"[Think] Prompt length: {len(user_prompt)} chars (~{estimate_tokens(user_prompt)} tokens)")
    
    # Call LLM with retry logic
    content = None
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(messages)
            content = response.content
            
            if verbose:
                logger.info(f"[Think] LLM responded ({len(content)} chars)")
            break
            
        except APIConnectionError as e:
            last_error = e
            wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
            logger.warning(f"[Think] Connection error, retry {attempt+1}/{max_retries} in {wait_time}s: {e}")
            await asyncio.sleep(wait_time)
            
        except RateLimitError as e:
            last_error = e
            wait_time = 30  # Rate limit: wait longer
            logger.warning(f"[Think] Rate limited, waiting {wait_time}s: {e}")
            await asyncio.sleep(wait_time)
            
        except APIStatusError as e:
            last_error = e
            logger.error(f"[Think] API error (status {e.status_code}): {e.message}")
            # Don't retry on 4xx errors (client errors)
            if 400 <= e.status_code < 500:
                break
            await asyncio.sleep(2 ** attempt)
    
    # If all retries failed
    if content is None:
        logger.error(f"[Think] All retries failed: {last_error}")
        return {
            "actions": state.get("actions", []) + [{
                "step": state["current_step"],
                "reasoning": f"LLM error after {max_retries} retries: {last_error}",
                "action_type": "terminate",
                "result": f"Error: {last_error}",
            }],
            "current_step": state["current_step"] + 1,
            "status": "failed",
        }
    
    # Parse JSON response
    try:
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            decision = json.loads(json_match.group())
        else:
            decision = {
                "reasoning": content,
                "action_type": "terminate",
                "result": "Could not parse response",
            }
    except json.JSONDecodeError as e:
        logger.warning(f"[Think] JSON parse error: {e}")
        decision = {
            "reasoning": content,
            "action_type": "terminate",
            "result": "JSON parse error",
        }
    
    # Create action record
    action = {
        "step": state["current_step"],
        "reasoning": decision.get("reasoning", ""),
        "action_type": decision.get("action_type", "terminate"),
        "python_code": decision.get("python_code"),
        "result": decision.get("result"),
    }
    
    if verbose:
        logger.info(f"[Think] Decision: {action['action_type']}")
        if action.get("reasoning"):
            logger.debug(f"[Think] Reasoning: {action['reasoning'][:200]}...")
    
    # Update messages
    new_messages = [
        HumanMessage(content=user_prompt),
        AIMessage(content=content),
    ]
    
    return {
        "messages": new_messages,
        "actions": state.get("actions", []) + [action],
        "current_step": state["current_step"] + 1,
    }


async def act_node(state: AgentState, browser_session) -> dict:
    """
    Act node - Execute the generated code
    
    Runs the Playwright code against the browser.
    Now includes visual feedback for each action!
    """
    actions = state.get("actions", [])
    if not actions:
        return {"status": "failed", "result": "No action to execute"}
    
    current_action = actions[-1]
    
    if current_action.get("action_type") != "code":
        # Not a code action, skip
        return {}
    
    code = current_action.get("python_code", "")
    if not code:
        return {}
    
    # Sanitize code
    code = sanitize_code(code)
    
    page = browser_session.active_page
    
    # === Visual Feedback: Before Execution ===
    try:
        # Parse code to extract target element and action type
        visual_info = _extract_visual_info(code)
        
        if visual_info:
            action_type = visual_info.get("action_type")
            selector = visual_info.get("selector")
            coords = visual_info.get("coords")
            text = visual_info.get("text")
            
            # Show element highlight
            if selector:
                await visual_feedback.highlight_element(page, selector)
                await asyncio.sleep(0.3)  # Brief pause for visual effect
            elif coords:
                await visual_feedback.highlight_by_coordinates(
                    page, coords[0], coords[1], 100, 40
                )
                await asyncio.sleep(0.2)
            
            # Show typing indicator for fill actions
            if action_type == "fill" and selector and text:
                await visual_feedback.show_typing(page, selector, text)
                
    except Exception as e:
        # Visual feedback errors should not block execution
        logger.debug(f"[Visual] Pre-action feedback error: {e}")
    
    # Execute code
    try:
        result = await execute_playwright_code(code, page)
        
        # === Visual Feedback: After Execution (Click) ===
        try:
            if visual_info and visual_info.get("action_type") == "click":
                coords = visual_info.get("coords")
                if coords:
                    await visual_feedback.show_click(page, coords[0], coords[1])
                else:
                    # Try to get element center for click effect
                    selector = visual_info.get("selector")
                    if selector:
                        center = await _get_element_center(page, selector)
                        if center:
                            await visual_feedback.show_click(page, center[0], center[1])
        except Exception as e:
            logger.debug(f"[Visual] Post-action feedback error: {e}")
        
        # Update action with result
        current_action["execution_result"] = {
            "success": True,
            "output": str(result) if result else None,
            "error": None,
        }
        
        return {"actions": actions}
        
    except Exception as e:
        current_action["execution_result"] = {
            "success": False,
            "output": None,
            "error": str(e),
        }
        return {"actions": actions}


def _extract_visual_info(code: str) -> dict:
    """
    Extract visual feedback info from generated code
    
    Parses code to find:
    - Selector (CSS or role-based)
    - Action type (click, fill, press)
    - Coordinates (for coordinate-based actions)
    - Text (for fill actions)
    """
    info = {}
    
    # Detect action type
    if '.click(' in code:
        info["action_type"] = "click"
    elif '.fill(' in code:
        info["action_type"] = "fill"
    elif '.press(' in code:
        info["action_type"] = "press"
    elif '.type(' in code:
        info["action_type"] = "type"
    elif '.hover(' in code:
        info["action_type"] = "hover"
    
    # Extract selector - role-based
    role_match = re.search(r'get_by_role\(["\'](\w+)["\'](?:,\s*name=["\']([^"\']+)["\'])?\)', code)
    if role_match:
        role = role_match.group(1)
        name = role_match.group(2) or ""
        # Construct CSS-like selector for highlight
        info["selector"] = f'[role="{role}"]' if name == "" else f'[role="{role}"][name*="{name}"]'
    
    # Extract selector - CSS selector
    locator_match = re.search(r'locator\(["\']([^"\']+)["\']\)', code)
    if locator_match:
        info["selector"] = locator_match.group(1)
    
    # Extract selector - get_by_text
    text_match = re.search(r'get_by_text\(["\']([^"\']+)["\']\)', code)
    if text_match:
        text = text_match.group(1)
        info["selector"] = f'//*[contains(text(), "{text}")]'
    
    # Extract selector - get_by_placeholder
    placeholder_match = re.search(r'get_by_placeholder\(["\']([^"\']+)["\']\)', code)
    if placeholder_match:
        placeholder = placeholder_match.group(1)
        info["selector"] = f'[placeholder*="{placeholder}"]'
    
    # Extract selector - get_by_label
    label_match = re.search(r'get_by_label\(["\']([^"\']+)["\']\)', code)
    if label_match:
        label = label_match.group(1)
        info["selector"] = f'label:has-text("{label}") + input, [aria-label*="{label}"]'
    
    # Extract coordinates for mouse.click(x, y)
    coord_match = re.search(r'mouse\.click\((\d+(?:\.\d+)?),\s*(\d+(?:\.\d+)?)\)', code)
    if coord_match:
        info["coords"] = (float(coord_match.group(1)), float(coord_match.group(2)))
    
    # Extract fill text
    fill_match = re.search(r'\.fill\(["\']([^"\']*)["\']', code)
    if fill_match:
        info["text"] = fill_match.group(1)
    
    return info if info.get("action_type") else None


async def _get_element_center(page, selector: str) -> tuple:
    """Get center coordinates of an element"""
    try:
        result = await page.evaluate(f"""
            (selector) => {{
                const el = document.querySelector(selector);
                if (!el) return null;
                const rect = el.getBoundingClientRect();
                return [rect.x + rect.width / 2, rect.y + rect.height / 2];
            }}
        """, selector)
        return tuple(result) if result else None
    except:
        return None


def terminate_node(state: AgentState) -> dict:
    """
    Terminate node - Return final result
    """
    actions = state.get("actions", [])
    
    if actions:
        last_action = actions[-1]
        if last_action.get("action_type") == "terminate":
            return {
                "status": "completed",
                "result": last_action.get("result", "Task completed"),
            }
    
    # Check if max steps reached
    if state["current_step"] >= state["max_steps"]:
        return {
            "status": "failed",
            "result": "Max steps reached",
        }
    
    return {}


def sanitize_code(code: str) -> str:
    """Clean up generated code"""
    # Remove non-ASCII
    code = code.encode('ascii', 'ignore').decode('ascii')
    
    # Add .first to selectors
    pattern = r'(\.get_by_role\([^)]+\))(\.(click|fill|press)\()'
    def add_first(match):
        selector = match.group(1)
        action = match.group(2)
        if '.first' not in selector:
            return selector + '.first' + action
        return match.group(0)
    code = re.sub(pattern, add_first, code)
    
    # Add timeout if missing
    for action in ['click', 'fill', 'press']:
        pattern = rf'\.{action}\(\)'
        code = re.sub(pattern, f'.{action}(timeout=15000)', code)
    
    return code


async def execute_playwright_code(code: str, page) -> any:
    """
    Execute Playwright code with safety checks
    
    Safety measures:
    1. Whitelist allowed modules
    2. Block dangerous operations
    3. Timeout execution
    """
    import asyncio
    
    # Safety check: block dangerous patterns
    BLOCKED_PATTERNS = [
        'import os',
        'import sys',
        'import subprocess',
        '__import__',
        'eval(',
        'exec(',
        'open(',
        'file(',
        'input(',
        'raw_input(',
        'compile(',
        'globals(',
        'locals(',
        'vars(',
        'dir(',
        'getattr(',
        'setattr(',
        'delattr(',
        '__builtins__',
        '__class__',
        '__bases__',
        '__subclasses__',
    ]
    
    code_lower = code.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in code_lower:
            raise SecurityError(f"Blocked pattern detected: {pattern}")
    
    # Wrap code if needed
    if 'async def act(page):' not in code:
        lines = code.strip().split('\n')
        indented = '\n'.join('    ' + line for line in lines)
        code = f"async def act(page):\n{indented}"
    
    # Create restricted namespace (only page and asyncio)
    namespace = {
        'page': page,
        'asyncio': asyncio,
        '__builtins__': {
            'print': print,
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'map': map,
            'filter': filter,
            'sorted': sorted,
            'min': min,
            'max': max,
            'sum': sum,
            'any': any,
            'all': all,
            'isinstance': isinstance,
            'hasattr': hasattr,
            'None': None,
            'True': True,
            'False': False,
        }
    }
    
    # Execute with timeout
    exec(code, namespace)
    
    if 'act' in namespace:
        try:
            return await asyncio.wait_for(
                namespace['act'](page),
                timeout=30.0  # 30 second timeout
            )
        except asyncio.TimeoutError:
            raise TimeoutError("Code execution timed out (30s)")
    
    return None


class SecurityError(Exception):
    """Raised when unsafe code is detected"""
    pass


def should_continue(state: AgentState) -> Literal["act", "terminate", "observe"]:
    """
    Router function - decides next node
    """
    # Check if done
    if state.get("status") in ["completed", "failed"]:
        return "terminate"
    
    # Check max steps
    if state["current_step"] >= state["max_steps"]:
        return "terminate"
    
    # Check last action type
    actions = state.get("actions", [])
    if actions:
        last_action = actions[-1]
        if last_action.get("action_type") == "terminate":
            return "terminate"
        if last_action.get("action_type") == "code":
            return "act"
    
    # Default: observe then think
    return "observe"

