"""
数据质量过滤器 - 自动过滤垃圾数据，只保留高质量样本

策略：
1. 规则过滤 - 快速剔除明显的垃圾（空响应、超时、错误）
2. LLM 评分 - AI 判断数据质量（0-10分）
3. 自动标签 - 根据分数自动打标签

用法:
    python -m engine.evaluation.data_quality_filter --project nogicos --threshold 6
"""

import os
import sys
import logging
import argparse
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from langsmith import Client
from anthropic import Anthropic

# 加载 API keys
try:
    from api_keys import setup_env
    setup_env()
except ImportError as e:
    logger.debug(f"api_keys 模块未找到: {e}")

logger = logging.getLogger(__name__)

# 质量规则（更宽松，适配 LangSmith 数据格式）
QUALITY_RULES = {
    # 自动拒绝（分数=0）- 只拒绝明显的垃圾
    "auto_reject": [
        lambda r: r.error is not None and "error" in str(r.error).lower(),  # 有明确错误
        lambda r: r.outputs and "traceback" in str(r.outputs).lower(),  # Traceback 泄露
    ],
    # 自动降分（分数-2）
    "auto_penalize": [
        lambda r: r.end_time and r.start_time and (r.end_time - r.start_time).total_seconds() > 60,  # 超时 >60s
        lambda r: not r.outputs,  # 无输出
        lambda r: r.outputs and len(str(r.outputs)) < 20,  # 输出太短
    ],
    # 自动加分（分数+2）
    "auto_bonus": [
        lambda r: r.outputs and len(str(r.outputs)) > 100,  # 有实质输出
        lambda r: r.end_time and r.start_time and (r.end_time - r.start_time).total_seconds() < 10,  # 快速完成
    ],
}


def apply_rule_filters(run) -> Tuple[float, List[str]]:
    """应用规则过滤，返回基础分数和原因"""
    base_score = 6.0  # 基础分（默认中等质量）
    reasons = []
    
    # 检查自动拒绝
    for rule in QUALITY_RULES["auto_reject"]:
        try:
            if rule(run):
                return 0.0, ["auto_rejected"]
        except Exception:
            pass
    
    # 检查降分
    for rule in QUALITY_RULES["auto_penalize"]:
        try:
            if rule(run):
                base_score -= 2
                reasons.append("penalized")
        except Exception:
            pass
    
    # 检查加分
    for rule in QUALITY_RULES["auto_bonus"]:
        try:
            if rule(run):
                base_score += 2
                reasons.append("bonus")
        except Exception:
            pass
    
    return max(1, min(10, base_score)), reasons  # 最低 1 分（除非被拒绝）


def llm_score_quality(task: str, response: str, client: Anthropic) -> Tuple[float, str]:
    """用 LLM 评估数据质量"""
    # 如果输入太短，直接返回低分
    if not task or len(str(task)) < 5:
        return 3.0, "任务描述太短"
    if not response or len(str(response)) < 10:
        return 2.0, "响应太短"
    
    prompt = f"""评估这条 AI Agent 执行数据的质量（用于训练/评估）。

任务: {str(task)[:200]}
响应: {str(response)[:500]}

评分标准（0-10）:
- 10: 完美执行，响应准确完整
- 7-9: 执行成功，响应合理
- 4-6: 部分成功，有改进空间
- 1-3: 执行有问题，但有学习价值
- 0: 垃圾数据，无价值

请回复格式:
分数: X
原因: 一句话解释

只回复上面的格式，不要其他内容。"""

    try:
        llm_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = llm_response.content[0].text
        # 解析分数
        score_lines = [l for l in text.split("\n") if "分数" in l]
        if not score_lines:
            return 5.0, "无法解析分数"
        score = float(score_lines[0].split(":")[1].strip().split()[0])
        
        # 解析原因
        reason_lines = [l for l in text.split("\n") if "原因" in l]
        reason = reason_lines[0].split(":", 1)[1].strip() if reason_lines else "无原因"
        
        return min(10, max(0, score)), reason
    except Exception as e:
        logger.warning(f"LLM 评分失败: {e}")
        return 5.0, f"评分失败: {str(e)[:30]}"


def filter_and_score_runs(
    project_name: str = "nogicos",
    hours: int = 24,
    threshold: float = 6.0,
    use_llm: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    过滤和评分最近的 runs
    
    Args:
        project_name: LangSmith 项目名
        hours: 查看最近多少小时的数据
        threshold: 质量阈值（低于此分数的标记为低质量）
        use_llm: 是否使用 LLM 评分（更准确但更慢）
        dry_run: 只分析不打标签
    
    Returns:
        统计信息
    """
    ls_client = Client()
    anthropic_client = Anthropic() if use_llm else None
    
    # 获取最近的 runs
    start_time = datetime.now() - timedelta(hours=hours)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"NogicOS 数据质量过滤器")
    logger.info(f"{'='*60}")
    logger.info(f"项目: {project_name}")
    logger.info(f"时间范围: 最近 {hours} 小时")
    logger.info(f"质量阈值: {threshold}")
    logger.info(f"LLM 评分: {'是' if use_llm else '否'}")
    logger.info(f"{'='*60}\n")
    
    runs = list(ls_client.list_runs(
        project_name=project_name,
        execution_order=1,  # 只看 root runs
        start_time=start_time,
    ))
    
    logger.info(f"找到 {len(runs)} 条记录\n")
    
    stats = {
        "total": len(runs),
        "high_quality": 0,
        "medium_quality": 0,
        "low_quality": 0,
        "rejected": 0,
        "scores": [],
    }
    
    for i, run in enumerate(runs, 1):
        # 尝试多种可能的输入格式
        task = ""
        if run.inputs:
            task = run.inputs.get("task", "") or run.inputs.get("input", "") or run.inputs.get("query", "") or str(run.inputs)[:200]
        
        # 尝试多种可能的输出格式
        response = ""
        if run.outputs:
            response = run.outputs.get("response", "") or run.outputs.get("output", "") or run.outputs.get("result", "") or str(run.outputs)[:500]
        
        # 1. 规则过滤
        rule_score, rule_reasons = apply_rule_filters(run)
        
        if rule_score == 0:
            final_score = 0
            reason = "规则拒绝"
            stats["rejected"] += 1
        else:
            # 2. LLM 评分（可选）
            if use_llm and rule_score >= 3:
                llm_score, llm_reason = llm_score_quality(task, response, anthropic_client)
                final_score = (rule_score + llm_score) / 2  # 平均
                reason = llm_reason
            else:
                final_score = rule_score
                reason = "规则评分"
            
            # 统计
            if final_score >= 8:
                stats["high_quality"] += 1
            elif final_score >= threshold:
                stats["medium_quality"] += 1
            else:
                stats["low_quality"] += 1
        
        stats["scores"].append(final_score)
        
        # 打印进度
        quality_tag = "高" if final_score >= 8 else ("中" if final_score >= threshold else "低")
        logger.info(f"[{i}/{len(runs)}] 分数: {final_score:.1f} ({quality_tag}) - {task[:40]}...")
        
        # 3. 打标签
        if not dry_run:
            try:
                ls_client.create_feedback(
                    run.id,
                    key="quality_score",
                    score=final_score / 10,  # LangSmith 用 0-1
                    comment=reason,
                )
                
                # 质量标签
                quality_label = "high" if final_score >= 8 else ("medium" if final_score >= threshold else "low")
                ls_client.create_feedback(
                    run.id,
                    key="quality_label",
                    value=quality_label,
                )
            except Exception as e:
                logger.warning(f"打标签失败: {e}")
    
    # 打印统计
    avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
    total = stats["total"] if stats["total"] > 0 else 1  # 防止除零
    
    logger.info(f"\n{'='*60}")
    logger.info("统计结果")
    logger.info(f"{'='*60}")
    logger.info(f"总数: {stats['total']}")
    if stats['total'] > 0:
        logger.info(f"高质量 (>=8): {stats['high_quality']} ({stats['high_quality']/total*100:.1f}%)")
        logger.info(f"中等质量 ({threshold}-8): {stats['medium_quality']} ({stats['medium_quality']/total*100:.1f}%)")
        logger.info(f"低质量 (<{threshold}): {stats['low_quality']} ({stats['low_quality']/total*100:.1f}%)")
        logger.info(f"被拒绝: {stats['rejected']} ({stats['rejected']/total*100:.1f}%)")
        logger.info(f"平均分: {avg_score:.1f}")
    else:
        logger.info("没有找到数据，请扩大时间范围 (--hours)")
    logger.info(f"{'='*60}")
    
    return stats


def create_quality_dataset(
    project_name: str = "nogicos",
    dataset_name: str = "nogicos_quality",
    min_score: float = 7.0,
    limit: int = 100,
) -> None:
    """从高质量数据创建数据集"""
    ls_client = Client()
    
    logger.info(f"\n创建高质量数据集: {dataset_name}")
    logger.info(f"最低分数: {min_score}")
    
    # 查询高分数据
    runs = list(ls_client.list_runs(
        project_name=project_name,
        execution_order=1,
        filter=f'gte(feedback_score, {min_score/10})',  # 0-1 scale
        limit=limit,
    ))
    
    if not runs:
        logger.info("未找到高质量数据，尝试查询所有成功的 runs...")
        runs = list(ls_client.list_runs(
            project_name=project_name,
            execution_order=1,
            error=False,
            limit=limit,
        ))
    
    logger.info(f"找到 {len(runs)} 条符合条件的数据")
    
    # 创建数据集
    try:
        dataset = ls_client.create_dataset(
            dataset_name=dataset_name,
            description=f"高质量数据集（分数>={min_score}）"
        )
    except Exception:
        dataset = ls_client.read_dataset(dataset_name=dataset_name)
    
    # 添加示例
    added = 0
    for run in runs:
        if run.inputs and run.outputs:
            task = run.inputs.get("task")
            response = run.outputs.get("response")
            
            if task and response:
                try:
                    ls_client.create_example(
                        inputs={"task": task},
                        outputs={
                            "expected_response": response,
                            "expected_tools": [tc.get("name") for tc in run.outputs.get("tool_calls", []) if tc.get("name")],
                        },
                        dataset_id=dataset.id,
                        metadata={"source_run_id": str(run.id)}
                    )
                    added += 1
                except Exception as e:
                    logger.warning(f"添加示例失败: {e}")
    
    logger.info(f"成功添加 {added} 条高质量数据到 {dataset_name}")


def main():
    parser = argparse.ArgumentParser(description="NogicOS 数据质量过滤器")
    parser.add_argument("--project", type=str, default="nogicos", help="LangSmith 项目名")
    parser.add_argument("--hours", type=int, default=24, help="查看最近多少小时")
    parser.add_argument("--threshold", type=float, default=6.0, help="质量阈值")
    parser.add_argument("--no-llm", action="store_true", help="不使用 LLM 评分（更快）")
    parser.add_argument("--dry-run", action="store_true", help="只分析不打标签")
    parser.add_argument("--create-dataset", type=str, help="创建高质量数据集")
    parser.add_argument("--min-score", type=float, default=7.0, help="数据集最低分数")
    
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    
    if args.create_dataset:
        create_quality_dataset(
            project_name=args.project,
            dataset_name=args.create_dataset,
            min_score=args.min_score,
        )
    else:
        filter_and_score_runs(
            project_name=args.project,
            hours=args.hours,
            threshold=args.threshold,
            use_llm=not args.no_llm,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()

