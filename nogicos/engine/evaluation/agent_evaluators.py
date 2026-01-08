# -*- coding: utf-8 -*-
"""
NogicOS Agent 架构评估器 - Phase 8.1

专门用于评估新的 Agent 架构（HostAgent + AppAgent）的评估器：
1. agent_handoff_evaluator - 评估 HostAgent → AppAgent 任务传递
2. window_isolation_evaluator - 评估窗口隔离是否正确
3. set_task_status_evaluator - 评估 set_task_status 使用情况
4. multi_agent_efficiency_evaluator - 评估多 Agent 协作效率

Usage:
    from engine.evaluation.agent_evaluators import (
        agent_handoff_evaluator,
        window_isolation_evaluator,
        set_task_status_evaluator,
        multi_agent_efficiency_evaluator,
        get_agent_evaluators,
    )
"""

from typing import Dict, Any, List, Callable

from engine.observability import get_logger

logger = get_logger("agent_evaluators")

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
    logger.warning("[Agent Evaluators] LangSmith not available")


# ===========================================
# 窗口工具列表（用于检测窗口隔离）
# ===========================================

WINDOW_TOOLS = [
    "window_click",
    "window_type", 
    "window_screenshot",
    "window_scroll",
    "window_move",
    "window_resize",
    "window_focus",
    "window_close",
    "window_key",
    "window_drag",
]

# AppAgent 相关的工具名称模式
APP_AGENT_PATTERNS = [
    "app_agent_",
    "dispatch_to_app_agent",
    "execute_app_agent",
]


# ===========================================
# Agent 架构评估器
# ===========================================

@run_evaluator
def agent_handoff_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    评估 HostAgent → AppAgent 任务传递是否正确
    
    检查：
    - 任务是否传递到正确的 AppAgent
    - hwnd 参数是否正确绑定
    - 子任务结果是否正确返回
    
    评分标准：
    - 1.0: 所有 handoff 都正确（hwnd 绑定、有结果返回）
    - 0.7: handoff 正确但部分缺失 hwnd 或结果
    - 0.5: 有 AppAgent 调用但存在问题
    - 0.3: 应该有 handoff 但没有
    - 0.0: 完全没有 handoff 且任务需要
    """
    try:
        outputs = run.outputs or {}
        inputs = run.inputs or {}
        
        tool_calls = outputs.get("tool_calls", []) or []
        target_hwnds = inputs.get("target_hwnds", []) or []
        
        # 查找 AppAgent 调用
        agent_calls = []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            tool_name = tc.get("name", "")
            # 检查是否是 AppAgent 相关调用
            if any(pattern in tool_name for pattern in APP_AGENT_PATTERNS):
                agent_calls.append(tc)
        
        # 如果没有目标窗口，不需要 AppAgent
        if not target_hwnds:
            if not agent_calls:
                return {
                    "key": "agent_handoff", 
                    "score": 1.0, 
                    "comment": "No target windows, no handoff needed"
                }
            else:
                return {
                    "key": "agent_handoff",
                    "score": 0.8,
                    "comment": f"No target windows but {len(agent_calls)} agent calls made"
                }
        
        # 有目标窗口但没有 AppAgent 调用
        if not agent_calls:
            # 检查是否应该有 handoff
            task = inputs.get("task", "")
            needs_window_ops = any(kw in task.lower() for kw in [
                "窗口", "点击", "输入", "截图", "滚动", "window", "click", "type", "screenshot"
            ])
            
            if needs_window_ops:
                return {
                    "key": "agent_handoff",
                    "score": 0.3,
                    "comment": f"Task needs window ops but no AppAgent calls (targets: {len(target_hwnds)})"
                }
            return {
                "key": "agent_handoff",
                "score": 0.5,
                "comment": f"No AppAgent calls for {len(target_hwnds)} target windows"
            }
        
        # 检查 hwnd 绑定
        calls_with_hwnd = 0
        calls_with_result = 0
        
        for tc in agent_calls:
            args = tc.get("args", {}) or tc.get("arguments", {}) or {}
            result = tc.get("result") or tc.get("output")
            
            if args.get("hwnd") or args.get("window_handle"):
                calls_with_hwnd += 1
            if result is not None:
                calls_with_result += 1
        
        total_calls = len(agent_calls)
        hwnd_rate = calls_with_hwnd / total_calls if total_calls > 0 else 0
        result_rate = calls_with_result / total_calls if total_calls > 0 else 0
        
        # 综合评分
        if hwnd_rate == 1.0 and result_rate >= 0.8:
            score = 1.0
            rating = "excellent"
        elif hwnd_rate >= 0.8 and result_rate >= 0.5:
            score = 0.8
            rating = "good"
        elif hwnd_rate >= 0.5:
            score = 0.6
            rating = "acceptable"
        else:
            score = 0.4
            rating = "needs improvement"
        
        return {
            "key": "agent_handoff",
            "score": score,
            "comment": f"{total_calls} handoffs, {hwnd_rate:.0%} with hwnd, {result_rate:.0%} with results ({rating})"
        }
        
    except Exception as e:
        logger.error(f"[agent_handoff_evaluator] Error: {e}")
        return {"key": "agent_handoff", "score": 0.5, "comment": f"Error: {str(e)[:100]}"}


@run_evaluator
def window_isolation_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    评估窗口隔离是否正确
    
    检查：
    - 所有窗口工具调用是否包含 hwnd
    - hwnd 是否与目标窗口匹配
    - 是否有跨窗口污染（同一任务中操作了多个不相关窗口）
    
    评分标准：
    - 1.0: 所有窗口工具调用都有正确的 hwnd
    - 0.7: 大部分调用有 hwnd，少量缺失
    - 0.5: 约半数调用缺失 hwnd
    - 0.3: 大量调用缺失 hwnd
    - 0.0: 所有调用都缺失 hwnd 或有跨窗口污染
    """
    try:
        outputs = run.outputs or {}
        inputs = run.inputs or {}
        
        tool_calls = outputs.get("tool_calls", []) or []
        target_hwnds = set(inputs.get("target_hwnds", []) or [])
        
        # 筛选窗口工具调用
        window_calls = []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            tool_name = tc.get("name", "")
            if tool_name in WINDOW_TOOLS or tool_name.startswith("window_"):
                window_calls.append(tc)
        
        # 没有窗口工具调用
        if not window_calls:
            return {
                "key": "window_isolation",
                "score": 1.0,
                "comment": "No window tools used"
            }
        
        # 检查 hwnd 参数
        calls_with_hwnd = []
        calls_missing_hwnd = []
        used_hwnds = set()
        
        for tc in window_calls:
            args = tc.get("args", {}) or tc.get("arguments", {}) or {}
            hwnd = args.get("hwnd") or args.get("window_handle")
            
            if hwnd:
                calls_with_hwnd.append(tc)
                used_hwnds.add(hwnd)
            else:
                calls_missing_hwnd.append(tc)
        
        total_calls = len(window_calls)
        missing_count = len(calls_missing_hwnd)
        hwnd_rate = len(calls_with_hwnd) / total_calls if total_calls > 0 else 0
        
        # 检查跨窗口污染
        cross_window_violation = False
        if target_hwnds and used_hwnds:
            # 如果使用了不在目标列表中的 hwnd，可能是跨窗口污染
            unexpected_hwnds = used_hwnds - target_hwnds
            if unexpected_hwnds:
                cross_window_violation = True
        
        # 评分
        if cross_window_violation:
            return {
                "key": "window_isolation",
                "score": 0.0,
                "comment": f"Cross-window violation detected: used {len(used_hwnds)} windows, expected {len(target_hwnds)}"
            }
        
        if missing_count == 0:
            score = 1.0
            rating = "perfect isolation"
        elif hwnd_rate >= 0.8:
            score = 0.7
            rating = "good isolation"
        elif hwnd_rate >= 0.5:
            score = 0.5
            rating = "partial isolation"
        elif hwnd_rate > 0:
            score = 0.3
            rating = "poor isolation"
        else:
            score = 0.0
            rating = "no isolation"
        
        return {
            "key": "window_isolation",
            "score": score,
            "comment": f"{missing_count}/{total_calls} calls missing hwnd ({rating})"
        }
        
    except Exception as e:
        logger.error(f"[window_isolation_evaluator] Error: {e}")
        return {"key": "window_isolation", "score": 0.5, "comment": f"Error: {str(e)[:100]}"}


@run_evaluator
def set_task_status_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    评估 Agent 是否正确使用 set_task_status 终止循环
    
    检查：
    - 是否调用了 set_task_status
    - status 是否合理（completed/needs_help/failed）
    - description 是否有意义（长度和内容）
    
    评分标准：
    - 1.0: 正确调用 set_task_status，status 为 completed，description 有意义
    - 0.8: 正确调用，status 为 needs_help 且有合理说明
    - 0.6: 调用了但 description 过短或无意义
    - 0.4: 任务成功但没有调用 set_task_status
    - 0.2: 任务失败且没有正确的 status
    - 0.0: 完全没有调用且任务失败
    """
    try:
        outputs = run.outputs or {}
        tool_calls = outputs.get("tool_calls", []) or []
        
        # 查找 set_task_status 调用
        status_calls = []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            if tc.get("name") == "set_task_status":
                status_calls.append(tc)
        
        task_success = outputs.get("success", False)
        task_error = outputs.get("error", "")
        
        # 没有 set_task_status 调用
        if not status_calls:
            if task_success:
                return {
                    "key": "set_task_status",
                    "score": 0.4,
                    "comment": "Task succeeded but no set_task_status call"
                }
            elif task_error:
                return {
                    "key": "set_task_status",
                    "score": 0.0,
                    "comment": f"Task failed without proper status: {task_error[:50]}"
                }
            else:
                return {
                    "key": "set_task_status",
                    "score": 0.2,
                    "comment": "No set_task_status call and unclear task result"
                }
        
        # 分析最后一次 set_task_status 调用
        last_status_call = status_calls[-1]
        args = last_status_call.get("args", {}) or last_status_call.get("arguments", {}) or {}
        
        status = args.get("status", "")
        description = args.get("description", "") or args.get("message", "")
        
        # 检查 description 质量
        desc_len = len(description)
        has_meaningful_desc = desc_len >= 10 and not description.isspace()
        
        # 评分逻辑
        if status == "completed":
            if has_meaningful_desc:
                return {
                    "key": "set_task_status",
                    "score": 1.0,
                    "comment": f"Properly completed: {description[:50]}..."
                }
            else:
                return {
                    "key": "set_task_status",
                    "score": 0.6,
                    "comment": f"Completed but description too short ({desc_len} chars)"
                }
        
        elif status == "needs_help":
            if has_meaningful_desc:
                return {
                    "key": "set_task_status",
                    "score": 0.8,
                    "comment": f"Needs help: {description[:50]}..."
                }
            else:
                return {
                    "key": "set_task_status",
                    "score": 0.5,
                    "comment": f"Needs help but unclear why ({desc_len} chars)"
                }
        
        elif status == "failed":
            if has_meaningful_desc:
                return {
                    "key": "set_task_status",
                    "score": 0.6,
                    "comment": f"Failed with explanation: {description[:50]}..."
                }
            else:
                return {
                    "key": "set_task_status",
                    "score": 0.3,
                    "comment": f"Failed without clear explanation"
                }
        
        else:
            return {
                "key": "set_task_status",
                "score": 0.4,
                "comment": f"Unknown status: {status}"
            }
        
    except Exception as e:
        logger.error(f"[set_task_status_evaluator] Error: {e}")
        return {"key": "set_task_status", "score": 0.5, "comment": f"Error: {str(e)[:100]}"}


@run_evaluator
def multi_agent_efficiency_evaluator(run: Run, example: Example) -> Dict[str, Any]:
    """
    评估多 Agent 协作效率
    
    检查：
    - 总迭代次数是否合理
    - 是否有重复操作
    - AppAgent 调用是否高效
    - 工具调用的收敛性
    
    评分标准：
    - 1.0: ≤3 次迭代，<10% 重复率（efficient）
    - 0.8: ≤5 次迭代，<20% 重复率（good）
    - 0.6: ≤10 次迭代，<30% 重复率（acceptable）
    - 0.4: ≤15 次迭代或高重复率（inefficient）
    - 0.2: >15 次迭代或非常高重复率（very inefficient）
    """
    try:
        outputs = run.outputs or {}
        
        iterations = outputs.get("iterations", 0) or outputs.get("loop_count", 0)
        tool_calls = outputs.get("tool_calls", []) or []
        
        if not tool_calls:
            # 没有工具调用，检查是否完成了任务
            if outputs.get("success"):
                return {
                    "key": "multi_agent_efficiency",
                    "score": 1.0,
                    "comment": "Task completed without tool calls (efficient)"
                }
            return {
                "key": "multi_agent_efficiency",
                "score": 0.5,
                "comment": "No tool calls to evaluate"
            }
        
        # 生成工具调用签名（用于检测重复）
        tool_signatures = []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            name = tc.get("name", "unknown")
            args = tc.get("args", {}) or tc.get("arguments", {})
            
            # 创建签名（不包含时间戳等易变参数）
            stable_args = {k: v for k, v in args.items() if k not in ["timestamp", "request_id"]}
            signature = f"{name}:{str(sorted(stable_args.items()))}"
            tool_signatures.append(signature)
        
        # 计算重复率
        total_calls = len(tool_signatures)
        unique_calls = len(set(tool_signatures))
        duplicate_count = total_calls - unique_calls
        duplicate_rate = duplicate_count / total_calls if total_calls > 0 else 0
        
        # 如果没有记录迭代次数，根据工具调用数估算
        if iterations == 0:
            # 假设平均每次迭代 2-3 个工具调用
            iterations = max(1, total_calls // 3)
        
        # 评分逻辑
        if iterations <= 3 and duplicate_rate < 0.1:
            score = 1.0
            rating = "efficient"
        elif iterations <= 5 and duplicate_rate < 0.2:
            score = 0.8
            rating = "good"
        elif iterations <= 10 and duplicate_rate < 0.3:
            score = 0.6
            rating = "acceptable"
        elif iterations <= 15 or duplicate_rate < 0.4:
            score = 0.4
            rating = "inefficient"
        else:
            score = 0.2
            rating = "very inefficient"
        
        return {
            "key": "multi_agent_efficiency",
            "score": score,
            "comment": f"{iterations} iterations, {duplicate_count}/{total_calls} duplicates ({duplicate_rate:.0%}) - {rating}"
        }
        
    except Exception as e:
        logger.error(f"[multi_agent_efficiency_evaluator] Error: {e}")
        return {"key": "multi_agent_efficiency", "score": 0.5, "comment": f"Error: {str(e)[:100]}"}


# ===========================================
# 评估器集合函数
# ===========================================

def get_agent_evaluators() -> List[Callable]:
    """
    获取所有 Agent 架构评估器
    
    包含：
    - agent_handoff: HostAgent → AppAgent 任务传递
    - window_isolation: 窗口隔离检查
    - set_task_status: 任务状态设置
    - multi_agent_efficiency: 多 Agent 协作效率
    """
    return [
        agent_handoff_evaluator,
        window_isolation_evaluator,
        set_task_status_evaluator,
        multi_agent_efficiency_evaluator,
    ]


def get_agent_core_evaluators() -> List[Callable]:
    """
    获取核心 Agent 评估器（快速评估）
    
    包含：
    - agent_handoff: 任务传递
    - window_isolation: 窗口隔离
    """
    return [
        agent_handoff_evaluator,
        window_isolation_evaluator,
    ]


def get_agent_quality_evaluators() -> List[Callable]:
    """
    获取 Agent 质量评估器
    
    包含：
    - set_task_status: 任务状态
    - multi_agent_efficiency: 协作效率
    """
    return [
        set_task_status_evaluator,
        multi_agent_efficiency_evaluator,
    ]
