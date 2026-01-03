# -*- coding: utf-8 -*-
"""
NogicOS Evaluators for LangSmith - 最佳实践版本

评估器设计原则：
1. 规则评估器只用于客观可量化的指标（延迟、Token数、工具调用次数、错误率）
2. 语义判断交给 LLM 评估器（任务完成度、工具选择合理性、正确性、幻觉、简洁性）

Usage:
    from engine.evaluation.evaluators import (
        # 规则评估器（客观指标）
        latency_evaluator,
        token_count_evaluator,
        tool_call_count_evaluator,
        error_rate_evaluator,
        
        # LLM 评估器（语义理解）
        task_completion_llm_evaluator,
        tool_selection_llm_evaluator,
        correctness_evaluator,
        hallucination_evaluator,
        conciseness_evaluator,
        
        # 评估器列表
        get_rule_evaluators,
        get_llm_evaluators,
        get_all_evaluators,
    )
"""

import re
import time
from typing import Dict, Any, Optional, List, Callable

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

# Try to import openevals for LLM-as-judge
try:
    from openevals.llm import create_llm_as_judge
    from openevals.prompts import (
        CORRECTNESS_PROMPT,
        HALLUCINATION_PROMPT,
        CONCISENESS_PROMPT,
    )
    OPENEVALS_AVAILABLE = True
    logger.info("[Evaluators] openevals available - LLM-as-judge enabled")
except ImportError:
    OPENEVALS_AVAILABLE = False
    logger.warning("[Evaluators] openevals not available - install with: pip install openevals")


# ===========================================
# 规则评估器 - 客观可量化指标
# ===========================================

@run_evaluator
def latency_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    延迟评估器 - 客观指标
    
    评分标准：
    - 1.0: < 3s (excellent)
    - 0.8: 3-5s (good)
    - 0.6: 5-10s (acceptable)
    - 0.4: 10-20s (slow)
    - 0.2: 20-30s (very slow)
    - 0.0: > 30s (timeout)
    """
    try:
        outputs = run.outputs or {}
        latency_ms = None
        
        # 从 run 元数据获取
        if run.end_time and run.start_time:
            latency_ms = (run.end_time - run.start_time).total_seconds() * 1000
        
        # 从 outputs 获取
        if latency_ms is None and outputs:
            latency_ms = outputs.get("total_time_ms")
        
        if latency_ms is None:
            return {"key": "latency", "score": 0.5, "comment": "Latency data not available"}
        
        latency_s = latency_ms / 1000
        
        if latency_s < 3:
            score, rating = 1.0, "excellent"
        elif latency_s < 5:
            score, rating = 0.8, "good"
        elif latency_s < 10:
            score, rating = 0.6, "acceptable"
        elif latency_s < 20:
            score, rating = 0.4, "slow"
        elif latency_s < 30:
            score, rating = 0.2, "very slow"
        else:
            score, rating = 0.0, "timeout"
        
        return {"key": "latency", "score": score, "comment": f"{latency_s:.1f}s ({rating})"}
        
    except Exception as e:
        logger.error(f"[latency_evaluator] Error: {e}")
        return {"key": "latency", "score": 0.5, "comment": f"Error: {str(e)[:100]}"}


@run_evaluator
def token_count_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    Token 使用量评估器 - 客观指标
    
    评分标准（基于单次任务）：
    - 1.0: < 1000 tokens (efficient)
    - 0.8: 1000-3000 tokens (good)
    - 0.6: 3000-5000 tokens (acceptable)
    - 0.4: 5000-10000 tokens (high)
    - 0.2: > 10000 tokens (very high)
    """
    try:
        outputs = run.outputs or {}
        
        # 尝试从不同来源获取 token 数
        total_tokens = None
        
        # 从 outputs 获取
        if outputs:
            total_tokens = outputs.get("total_tokens") or outputs.get("token_count")
        
        # 从 run 的 feedback 或其他元数据获取
        if total_tokens is None and hasattr(run, 'extra') and run.extra:
            total_tokens = run.extra.get("total_tokens")
        
        if total_tokens is None:
            return {"key": "token_count", "score": 0.5, "comment": "Token count not available"}
        
        if total_tokens < 1000:
            score, rating = 1.0, "efficient"
        elif total_tokens < 3000:
            score, rating = 0.8, "good"
        elif total_tokens < 5000:
            score, rating = 0.6, "acceptable"
        elif total_tokens < 10000:
            score, rating = 0.4, "high"
        else:
            score, rating = 0.2, "very high"
        
        return {"key": "token_count", "score": score, "comment": f"{total_tokens} tokens ({rating})"}
        
    except Exception as e:
        logger.error(f"[token_count_evaluator] Error: {e}")
        return {"key": "token_count", "score": 0.5, "comment": f"Error: {str(e)[:100]}"}


@run_evaluator
def tool_call_count_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    工具调用次数评估器 - 客观指标
    
    评分标准：
    - 1.0: 0-2 calls (efficient)
    - 0.8: 3-4 calls (good)
    - 0.6: 5-6 calls (acceptable)
    - 0.4: 7-10 calls (many)
    - 0.2: > 10 calls (excessive)
    
    注意：简单对话任务 0 次调用也是 1.0 分
    """
    try:
        outputs = run.outputs or {}
        inputs = run.inputs or {}
        
        tool_calls = outputs.get("tool_calls", []) or []
        num_calls = len(tool_calls)
        
        # 简单对话不需要工具
        task = inputs.get("task", "") or ""
        is_simple_chat = not any(kw in task.lower() for kw in [
            "文件", "目录", "打开", "创建", "删除", "浏览器", "搜索",
            "file", "directory", "open", "create", "delete", "browser", "search",
            "桌面", "窗口", "截图", "desktop", "window", "screenshot",
        ])
        
        if is_simple_chat and num_calls == 0:
            return {"key": "tool_call_count", "score": 1.0, "comment": "Simple chat, no tools needed"}
        
        if num_calls <= 2:
            score, rating = 1.0, "efficient"
        elif num_calls <= 4:
            score, rating = 0.8, "good"
        elif num_calls <= 6:
            score, rating = 0.6, "acceptable"
        elif num_calls <= 10:
            score, rating = 0.4, "many"
        else:
            score, rating = 0.2, "excessive"
        
        return {"key": "tool_call_count", "score": score, "comment": f"{num_calls} calls ({rating})"}
        
    except Exception as e:
        logger.error(f"[tool_call_count_evaluator] Error: {e}")
        return {"key": "tool_call_count", "score": 0.5, "comment": f"Error: {str(e)[:100]}"}


@run_evaluator
def error_rate_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    错误率评估器 - 客观指标
    
    检查工具执行是否有错误，以及最终结果是否成功
    
    评分标准：
    - 1.0: 无错误
    - 0.7: 有小错误但最终成功
    - 0.3: 有错误且影响结果
    - 0.0: 完全失败
    """
    try:
        outputs = run.outputs or {}
        
        success = outputs.get("success", False)
        error = outputs.get("error", "") or ""
        tool_calls = outputs.get("tool_calls", []) or []
        
        # 统计工具错误
        tool_errors = 0
        for tc in tool_calls:
            if isinstance(tc, dict):
                if not tc.get("success", True) or tc.get("error"):
                    tool_errors += 1
        
        tool_error_rate = tool_errors / len(tool_calls) if tool_calls else 0
        
        # 综合评分
        if success and tool_error_rate == 0:
            score = 1.0
            comment = "No errors"
        elif success and tool_error_rate < 0.3:
            score = 0.7
            comment = f"Success with {tool_errors} tool errors"
        elif success:
            score = 0.5
            comment = f"Success but high error rate: {tool_error_rate:.0%}"
        elif error:
            score = 0.0
            comment = f"Failed: {error[:100]}"
        else:
            score = 0.3
            comment = "Partial failure"
        
        return {"key": "error_rate", "score": score, "comment": comment}
        
    except Exception as e:
        logger.error(f"[error_rate_evaluator] Error: {e}")
        return {"key": "error_rate", "score": 0.5, "comment": f"Error: {str(e)[:100]}"}


# ===========================================
# LLM 评估器 - 语义理解
# ===========================================

# 自定义 prompt 用于任务完成度评估
TASK_COMPLETION_PROMPT = """You are evaluating whether an AI agent successfully completed a user's task.

User's Task: {question}

Agent's Response: {answer}

Evaluate based on:
1. Did the agent understand the task correctly?
2. Did the agent provide a relevant and helpful response?
3. If the task required actions (file operations, web browsing, etc.), were they completed?

Score:
- 1.0: Task fully completed with correct and helpful response
- 0.7: Task mostly completed, minor issues
- 0.5: Task partially completed
- 0.3: Task poorly completed, significant issues
- 0.0: Task not completed or completely wrong

Respond with a JSON object: {{"score": <number>, "reasoning": "<explanation>"}}"""


# 自定义 prompt 用于工具选择评估
TOOL_SELECTION_PROMPT = """You are evaluating whether an AI agent selected appropriate tools for a task.

User's Task: {question}

Tools Used: {tools_used}

Evaluate based on:
1. Were the tools appropriate for the task?
2. Was the number of tools reasonable (not excessive)?
3. Were there any unnecessary tool calls?
4. Were there any missing tool calls that should have been made?

Score:
- 1.0: Optimal tool selection
- 0.7: Good selection with minor inefficiencies
- 0.5: Acceptable but not optimal
- 0.3: Poor selection, wrong or excessive tools
- 0.0: No tools used when needed, or completely wrong tools

Respond with a JSON object: {{"score": <number>, "reasoning": "<explanation>"}}"""


# Evaluator 模型配置
# 可选: 
#   - "anthropic:claude-opus-4-5-20251101" (Claude Opus 4.5 - 最新最强)
#   - "anthropic:claude-3-5-sonnet-20241022" (Claude 3.5 Sonnet - 性价比)
#   - "openai:gpt-4o-mini" (GPT-4o-mini - 最便宜)
EVALUATOR_MODEL = "anthropic:claude-opus-4-5-20251101"  # Claude Opus 4.5 (2025年11月)


def _create_llm_evaluators():
    """创建 LLM-as-judge 评估器（使用 Claude Opus 4.5）"""
    if not OPENEVALS_AVAILABLE:
        logger.warning("[Evaluators] openevals not available, LLM evaluators disabled")
        return {}
    
    try:
        evaluators = {}
        model = EVALUATOR_MODEL
        logger.info(f"[Evaluators] Using model: {model}")
        
        # 正确性评估器
        evaluators['correctness'] = create_llm_as_judge(
            prompt=CORRECTNESS_PROMPT,
            model=model,
            feedback_key="correctness",
        )
        
        # 幻觉检测评估器
        evaluators['hallucination'] = create_llm_as_judge(
            prompt=HALLUCINATION_PROMPT,
            model=model,
            feedback_key="hallucination",
        )
        
        # 简洁性评估器
        evaluators['conciseness'] = create_llm_as_judge(
            prompt=CONCISENESS_PROMPT,
            model=model,
            feedback_key="conciseness",
        )
        
        # 任务完成度评估器
        evaluators['task_completion'] = create_llm_as_judge(
            prompt=TASK_COMPLETION_PROMPT,
            model=model,
            feedback_key="task_completion_llm",
        )
        
        # 工具选择评估器
        evaluators['tool_selection'] = create_llm_as_judge(
            prompt=TOOL_SELECTION_PROMPT,
            model=model,
            feedback_key="tool_selection_llm",
        )
        
        logger.info("[Evaluators] LLM-as-judge evaluators created successfully (Claude Opus 4.5)")
        return evaluators
        
    except Exception as e:
        logger.error(f"[Evaluators] Failed to create LLM evaluators: {e}")
        return {}


# 创建 LLM 评估器实例
_llm_evaluators = _create_llm_evaluators()


def _wrap_llm_evaluator(evaluator_key: str, feedback_key: str):
    """
    包装 LLM 评估器，处理字段转换和错误
    
    返回一个使用 @run_evaluator 装饰器格式的评估器函数，
    这样 LangSmith 可以正确调用它。
    """
    
    @run_evaluator
    def evaluator_fn(run: Run, example: Example) -> Dict[str, Any]:
        llm_eval = _llm_evaluators.get(evaluator_key)
        if llm_eval is None:
            return {"key": feedback_key, "score": 0.5, "comment": "LLM evaluator not available"}
        
        try:
            # 从 run 获取 inputs 和 outputs
            inputs = run.inputs or {}
            outputs = run.outputs or {}
            
            # 转换字段名 - openevals 期望 question/answer 格式
            eval_inputs = {"question": inputs.get("task", "")}
            eval_outputs = {"answer": outputs.get("response", "")}
            
            # 对于工具选择评估器，添加工具信息
            if evaluator_key == "tool_selection":
                tool_calls = outputs.get("tool_calls", [])
                tools_str = ", ".join(
                    tc.get("name", "unknown") for tc in tool_calls if isinstance(tc, dict)
                ) if tool_calls else "None"
                eval_inputs["tools_used"] = tools_str
            
            # 对于幻觉检测，需要提供 context
            # context 可以是 reference 输出或者 agent 响应本身
            if evaluator_key == "hallucination":
                # 使用 agent 响应作为 context（检测响应内部一致性）
                eval_outputs["context"] = outputs.get("response", "")
            
            # 获取 reference outputs（如果有）
            reference_outputs = {}
            if example and hasattr(example, 'outputs') and example.outputs:
                reference_outputs = example.outputs
            
            result = llm_eval(
                inputs=eval_inputs,
                outputs=eval_outputs,
                reference_outputs=reference_outputs,
            )
            
            score = result.score if hasattr(result, 'score') else 0.5
            comment = result.comment if hasattr(result, 'comment') else "LLM evaluation completed"
            
            return {"key": feedback_key, "score": score, "comment": comment}
            
        except Exception as e:
            logger.error(f"[{feedback_key}] Error: {e}")
            return {"key": feedback_key, "score": 0.5, "comment": f"Error: {str(e)[:100]}"}
    
    return evaluator_fn


# 创建 LLM 评估器函数
correctness_evaluator = _wrap_llm_evaluator("correctness", "correctness")
hallucination_evaluator = _wrap_llm_evaluator("hallucination", "hallucination")
conciseness_evaluator = _wrap_llm_evaluator("conciseness", "conciseness")
task_completion_llm_evaluator = _wrap_llm_evaluator("task_completion", "task_completion_llm")
tool_selection_llm_evaluator = _wrap_llm_evaluator("tool_selection", "tool_selection_llm")


# ===========================================
# 评估器集合函数
# ===========================================

def get_rule_evaluators() -> List[Callable]:
    """
    获取规则评估器列表（客观指标，快速、免费）
    
    包含：
    - latency: 延迟
    - token_count: Token 使用量
    - tool_call_count: 工具调用次数
    - error_rate: 错误率
    """
    return [
        latency_evaluator,
        token_count_evaluator,
        tool_call_count_evaluator,
        error_rate_evaluator,
    ]


def get_llm_evaluators() -> List[Callable]:
    """
    获取 LLM-as-judge 评估器列表（语义理解，准确但收费）
    
    包含：
    - task_completion_llm: 任务完成度
    - tool_selection_llm: 工具选择合理性
    - correctness: 正确性
    - hallucination: 幻觉检测
    - conciseness: 简洁性
    
    注意：需要 OpenAI API Key
    """
    if not OPENEVALS_AVAILABLE:
        logger.warning("[Evaluators] LLM evaluators not available")
        return []
    
    return [
        task_completion_llm_evaluator,
        tool_selection_llm_evaluator,
        correctness_evaluator,
        hallucination_evaluator,
        conciseness_evaluator,
    ]


def get_all_evaluators() -> List[Callable]:
    """
    获取所有评估器（规则 + LLM）
    
    推荐用于全面评估
    """
    return get_rule_evaluators() + get_llm_evaluators()


def get_fast_evaluators() -> List[Callable]:
    """
    获取快速评估器（只有规则评估器）
    
    推荐用于快速迭代测试
    """
    return get_rule_evaluators()


def get_quality_evaluators() -> List[Callable]:
    """
    获取质量评估器（规则 + 幻觉检测 + 任务完成度）
    
    平衡成本和质量检测
    """
    evaluators = get_rule_evaluators()
    
    if OPENEVALS_AVAILABLE:
        evaluators.extend([
            task_completion_llm_evaluator,
            hallucination_evaluator,
        ])
    
    return evaluators


def get_essential_evaluators() -> List[Callable]:
    """
    获取核心评估器（最重要的指标）
    
    包含：延迟、错误率、任务完成度、幻觉检测
    """
    evaluators = [
        latency_evaluator,
        error_rate_evaluator,
    ]
    
    if OPENEVALS_AVAILABLE:
        evaluators.extend([
            task_completion_llm_evaluator,
            hallucination_evaluator,
        ])
    
    return evaluators


# ===========================================
# 兼容性别名（保持向后兼容）
# ===========================================

# 旧的评估器名称指向新的实现
task_completion_evaluator = task_completion_llm_evaluator
tool_selection_evaluator = tool_selection_llm_evaluator
response_quality_evaluator = conciseness_evaluator  # response_quality 被 conciseness 替代
