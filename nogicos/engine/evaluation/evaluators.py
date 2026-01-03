# -*- coding: utf-8 -*-
"""
NogicOS Custom Evaluators for LangSmith

Provides specialized evaluators for AI Agent performance:
- Task Completion: Did the agent complete the task?
- Tool Selection: Did the agent choose the right tools?
- Response Quality: Is the response helpful and accurate?
- Latency: Is the response time acceptable?

Usage:
    from engine.evaluation.evaluators import (
        task_completion_evaluator,
        tool_selection_evaluator,
    )
    
    results = evaluate(
        agent_function,
        data="nogicos_test_set",
        evaluators=[task_completion_evaluator, tool_selection_evaluator],
    )
"""

import re
from typing import Dict, Any, Optional

from engine.observability import get_logger
logger = get_logger("evaluators")

# Try to import LangSmith
try:
    from langsmith.evaluation.evaluator import run_evaluator
    from langsmith.schemas import Run, Example
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    run_evaluator = lambda f: f
    Run = Any
    Example = Any
    logger.warning("[Evaluators] LangSmith not available")


# ===========================================
# Task Completion Evaluator
# ===========================================

@run_evaluator
def task_completion_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    Evaluate whether the agent successfully completed the task.
    
    Scoring:
    - 1.0: Task fully completed (success=True, has output)
    - 0.5: Partial completion (has output but may have errors)
    - 0.0: Task failed (no output or error)
    
    Args:
        run: The agent run to evaluate
        example: The expected example (may contain expected outputs)
        
    Returns:
        Evaluation result with score and comment
    """
    outputs = run.outputs or {}
    
    # Check success flag
    success = outputs.get("success", False)
    response = outputs.get("response", "")
    error = outputs.get("error", "")
    
    # Scoring logic
    if success and response:
        score = 1.0
        comment = "Task completed successfully"
    elif response and not error:
        score = 0.7
        comment = "Task completed with output, but success flag not set"
    elif response:
        score = 0.5
        comment = f"Partial completion with error: {error[:100]}"
    else:
        score = 0.0
        comment = f"Task failed: {error[:100] if error else 'No output'}"
    
    return {
        "key": "task_completion",
        "score": score,
        "comment": comment,
    }


# ===========================================
# Tool Selection Evaluator
# ===========================================

@run_evaluator
def tool_selection_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    Evaluate whether the agent selected appropriate tools.
    
    Checks:
    - Did the agent use tools at all when needed?
    - Were the tools relevant to the task?
    - Was the number of tool calls reasonable?
    
    Scoring:
    - 1.0: Optimal tool selection
    - 0.7: Good selection with minor inefficiencies
    - 0.5: Tools used but not optimal
    - 0.3: Excessive or wrong tools
    - 0.0: No tools used when needed
    """
    outputs = run.outputs or {}
    inputs = run.inputs or {}
    
    task = inputs.get("task", "")
    tool_calls = outputs.get("tool_calls", [])
    iterations = outputs.get("iterations", 0)
    
    # Expected outputs from example (if available)
    expected = example.outputs or {} if example else {}
    expected_tools = expected.get("expected_tools", [])
    
    # Determine if task requires tools
    task_lower = task.lower()
    needs_tools = any(kw in task_lower for kw in [
        "文件", "目录", "打开", "创建", "删除", "移动", "列出",
        "file", "directory", "open", "create", "delete", "move", "list",
        "browser", "浏览器", "网页", "搜索", "点击",
    ])
    
    # Scoring
    if not needs_tools:
        # Simple chat, no tools needed
        if not tool_calls:
            return {"key": "tool_selection", "score": 1.0, "comment": "No tools needed, none used"}
        else:
            return {"key": "tool_selection", "score": 0.7, "comment": "Tools used but may not be needed"}
    
    # Task needs tools
    if not tool_calls:
        return {"key": "tool_selection", "score": 0.0, "comment": "Tools needed but none used"}
    
    # Check tool count efficiency
    num_tools = len(tool_calls)
    
    if expected_tools:
        # Compare with expected
        used_tools = {tc.get("name") for tc in tool_calls}
        expected_set = set(expected_tools)
        match_rate = len(used_tools & expected_set) / len(expected_set) if expected_set else 0
        score = match_rate
        comment = f"Tool match rate: {match_rate:.0%}"
    else:
        # Heuristic scoring based on efficiency
        if num_tools <= 2 and iterations <= 3:
            score = 1.0
            comment = f"Efficient: {num_tools} tools in {iterations} iterations"
        elif num_tools <= 4 and iterations <= 5:
            score = 0.8
            comment = f"Good: {num_tools} tools in {iterations} iterations"
        elif num_tools <= 6 and iterations <= 8:
            score = 0.6
            comment = f"Acceptable: {num_tools} tools in {iterations} iterations"
        else:
            score = 0.4
            comment = f"Inefficient: {num_tools} tools in {iterations} iterations"
    
    # Check for successful tool executions
    success_rate = sum(1 for tc in tool_calls if tc.get("success", False)) / num_tools if num_tools else 0
    if success_rate < 0.5:
        score = max(0.0, score - 0.3)
        comment += f" | Low tool success rate: {success_rate:.0%}"
    
    return {
        "key": "tool_selection",
        "score": score,
        "comment": comment,
    }


# ===========================================
# Response Quality Evaluator
# ===========================================

@run_evaluator
def response_quality_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    Evaluate the quality of the agent's response.
    
    Checks:
    - Response length (not too short, not too verbose)
    - Contains useful information
    - Matches expected output pattern (if provided)
    
    Scoring:
    - 1.0: High quality response
    - 0.7: Good response with minor issues
    - 0.5: Acceptable response
    - 0.3: Poor quality
    - 0.0: No response or completely wrong
    """
    outputs = run.outputs or {}
    inputs = run.inputs or {}
    
    response = outputs.get("response", "")
    task = inputs.get("task", "")
    
    # Expected output (if available)
    expected = example.outputs or {} if example else {}
    expected_response = expected.get("response", "")
    expected_contains = expected.get("response_contains", [])
    
    if not response:
        return {"key": "response_quality", "score": 0.0, "comment": "No response"}
    
    score = 0.5  # Base score
    issues = []
    
    # Length check
    response_len = len(response)
    if response_len < 10:
        issues.append("Too short")
        score -= 0.2
    elif response_len > 2000:
        issues.append("Too verbose")
        score -= 0.1
    else:
        score += 0.2
    
    # Content check - should contain relevant information
    task_keywords = set(re.findall(r'\w+', task.lower()))
    response_keywords = set(re.findall(r'\w+', response.lower()))
    keyword_overlap = len(task_keywords & response_keywords) / len(task_keywords) if task_keywords else 0
    
    if keyword_overlap > 0.3:
        score += 0.2
    elif keyword_overlap < 0.1:
        issues.append("Low relevance to task")
        score -= 0.1
    
    # Check against expected content
    if expected_contains:
        matches = sum(1 for kw in expected_contains if kw.lower() in response.lower())
        match_rate = matches / len(expected_contains)
        if match_rate >= 0.8:
            score += 0.3
        elif match_rate >= 0.5:
            score += 0.1
        else:
            issues.append(f"Missing expected content ({match_rate:.0%})")
            score -= 0.2
    
    # Clamp score
    score = max(0.0, min(1.0, score))
    
    comment = "Good quality" if not issues else " | ".join(issues)
    
    return {
        "key": "response_quality",
        "score": score,
        "comment": comment,
    }


# ===========================================
# Latency Evaluator
# ===========================================

@run_evaluator
def latency_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    Evaluate response latency.
    
    Scoring based on total execution time:
    - 1.0: < 3s (excellent)
    - 0.8: 3-5s (good)
    - 0.6: 5-10s (acceptable)
    - 0.4: 10-20s (slow)
    - 0.2: 20-30s (very slow)
    - 0.0: > 30s (timeout territory)
    """
    outputs = run.outputs or {}
    
    # Try to get latency from different sources
    latency_ms = None
    
    # From run metadata
    if run.end_time and run.start_time:
        latency_ms = (run.end_time - run.start_time).total_seconds() * 1000
    
    # From outputs
    if latency_ms is None:
        latency_ms = outputs.get("total_time_ms")
    
    if latency_ms is None:
        return {
            "key": "latency",
            "score": 0.5,
            "comment": "Latency data not available",
        }
    
    latency_s = latency_ms / 1000
    
    # Scoring
    if latency_s < 3:
        score = 1.0
        rating = "excellent"
    elif latency_s < 5:
        score = 0.8
        rating = "good"
    elif latency_s < 10:
        score = 0.6
        rating = "acceptable"
    elif latency_s < 20:
        score = 0.4
        rating = "slow"
    elif latency_s < 30:
        score = 0.2
        rating = "very slow"
    else:
        score = 0.0
        rating = "timeout"
    
    return {
        "key": "latency",
        "score": score,
        "comment": f"{latency_s:.1f}s ({rating})",
    }


# ===========================================
# Aggregate Evaluator
# ===========================================

def create_aggregate_evaluator(
    weights: Optional[Dict[str, float]] = None
):
    """
    Create an aggregate evaluator that combines multiple scores.
    
    Args:
        weights: Dict of evaluator_key -> weight (default: equal weights)
        
    Returns:
        Evaluator function
    """
    default_weights = {
        "task_completion": 0.4,
        "tool_selection": 0.2,
        "response_quality": 0.2,
        "latency": 0.2,
    }
    weights = weights or default_weights
    
    @run_evaluator
    def aggregate_evaluator(run: Run, example: Example) -> Dict[str, Any]:
        """Aggregate multiple evaluation scores."""
        scores = {}
        
        # Run individual evaluators
        evaluators = [
            task_completion_evaluator,
            tool_selection_evaluator,
            response_quality_evaluator,
            latency_evaluator,
        ]
        
        for evaluator in evaluators:
            try:
                result = evaluator(run, example)
                key = result["key"]
                scores[key] = result["score"]
            except Exception as e:
                logger.warning(f"Evaluator {evaluator.__name__} failed: {e}")
        
        # Weighted average
        total_weight = sum(weights.get(k, 0) for k in scores)
        if total_weight > 0:
            aggregate_score = sum(
                scores[k] * weights.get(k, 0)
                for k in scores
            ) / total_weight
        else:
            aggregate_score = 0.5
        
        return {
            "key": "aggregate",
            "score": aggregate_score,
            "comment": f"Weighted avg of {len(scores)} metrics",
        }
    
    return aggregate_evaluator


# Default aggregate evaluator
aggregate_evaluator = create_aggregate_evaluator()

