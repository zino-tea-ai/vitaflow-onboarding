# -*- coding: utf-8 -*-
"""
NogicOS Optimization Loop - 闭环优化系统（整合 LangSmith）

完整流程：
1. 评估当前性能 (baseline) - 使用 LangSmith + 新评估器
2. DSPy 优化
3. 评估优化后性能
4. A/B 对比
5. 如果更好则保存，否则回滚

用法：
    # 完整优化循环（使用 LangSmith 数据集）
    python -m engine.evaluation.optimization_loop --full-cycle
    
    # 只运行评估（不优化）
    python -m engine.evaluation.optimization_loop --evaluate-only
    
    # 查看历史
    python -m engine.evaluation.optimization_loop --history
    
    # 使用快速模式（只用规则评估器）
    python -m engine.evaluation.optimization_loop --full-cycle --mode fast
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

# Fix encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Add parent path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from engine.observability import get_logger, setup_logging
setup_logging()
logger = get_logger("optimization_loop")


class OptimizationLoop:
    """
    闭环优化系统（整合 LangSmith）
    
    核心原则：优化必须可验证，否则不部署
    
    支持两种评估模式：
    1. LangSmith 模式（推荐）：使用 LangSmith 数据集和新的评估器体系
    2. Legacy 模式：使用原来的 auto_data_collector 生成任务
    """
    
    DEFAULT_DATASET = "nogicos_comprehensive"
    
    def __init__(self, output_dir: str = "data/optimization_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 记录每次优化的结果
        self.history_file = self.output_dir / "optimization_history.json"
        self.history = self._load_history()
    
    def _load_history(self) -> List[Dict]:
        if self.history_file.exists():
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def _save_history(self):
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def run_langsmith_evaluation(
        self,
        label: str,
        dataset_name: str = None,
        evaluator_mode: str = "essential",
        max_concurrency: int = 2,
    ) -> Dict[str, Any]:
        """
        使用 LangSmith 运行评估（推荐）
        
        Args:
            label: 评估标签 (baseline/optimized)
            dataset_name: 数据集名称
            evaluator_mode: 评估器模式 (all/fast/quality/essential)
            max_concurrency: 并发数
            
        Returns:
            评估结果
        """
        from engine.evaluation.run_evaluation import run_evaluation
        
        dataset_name = dataset_name or self.DEFAULT_DATASET
        
        logger.info(f"[{label}] 使用 LangSmith 评估...")
        logger.info(f"  数据集: {dataset_name}")
        logger.info(f"  模式: {evaluator_mode}")
        
        try:
            results = run_evaluation(
                dataset_name=dataset_name,
                experiment_prefix=f"opt_{label}",
                evaluator_mode=evaluator_mode,
                max_concurrency=max_concurrency,
            )
            
            # 提取核心指标
            scores = results.get("scores", {})
            
            # 计算综合得分
            composite_score = self._calculate_composite_score(scores)
            
            eval_result = {
                "label": label,
                "timestamp": datetime.now().isoformat(),
                "dataset": dataset_name,
                "evaluator_mode": evaluator_mode,
                "experiment_name": results.get("experiment_name", ""),
                "total_examples": results.get("total_examples", 0),
                "scores": scores,
                "composite_score": composite_score,
            }
            
            logger.info(f"[{label}] LangSmith 评估完成:")
            logger.info(f"  总样本数: {eval_result['total_examples']}")
            logger.info(f"  综合得分: {composite_score:.3f}")
            for key, stat in scores.items():
                if isinstance(stat, dict):
                    logger.info(f"  {key}: {stat.get('avg', 0):.3f}")
            
            return eval_result
            
        except Exception as e:
            logger.error(f"[{label}] LangSmith 评估失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "label": label,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "composite_score": 0.0,
            }
    
    def _calculate_composite_score(self, scores: Dict[str, Any]) -> float:
        """
        计算综合得分
        
        权重分配（基于最佳实践）：
        - task_completion_llm: 0.30 (任务完成是最重要的)
        - hallucination: 0.20 (幻觉检测)
        - error_rate: 0.15 (错误率)
        - latency: 0.15 (延迟)
        - correctness: 0.10 (正确性)
        - conciseness: 0.05 (简洁性)
        - tool_selection_llm: 0.05 (工具选择)
        """
        weights = {
            "task_completion_llm": 0.30,
            "hallucination": 0.20,
            "error_rate": 0.15,
            "latency": 0.15,
            "correctness": 0.10,
            "conciseness": 0.05,
            "tool_selection_llm": 0.05,
        }
        
        total_weight = 0
        total_score = 0
        
        for key, weight in weights.items():
            if key in scores:
                stat = scores[key]
                avg = stat.get("avg", 0) if isinstance(stat, dict) else stat
                total_score += avg * weight
                total_weight += weight
        
        if total_weight > 0:
            return total_score / total_weight
        
        # Fallback: 使用所有可用的分数
        all_avgs = []
        for key, stat in scores.items():
            if isinstance(stat, dict):
                all_avgs.append(stat.get("avg", 0))
        
        return sum(all_avgs) / len(all_avgs) if all_avgs else 0.5
    
    async def run_legacy_evaluation(self, label: str, test_count: int = 20) -> Dict[str, Any]:
        """
        使用原来的方式运行评估（Legacy 模式）
        
        保留此方法以支持向后兼容
        """
        from engine.evaluation.auto_data_collector import (
            generate_tasks,
            quick_quality_check,
            run_task_and_collect,
        )
        from engine.agent.react_agent import ReActAgent
        
        logger.info(f"[{label}] 使用 Legacy 评估方式...")
        
        agent = ReActAgent()
        
        results = {
            "label": label,
            "timestamp": datetime.now().isoformat(),
            "test_count": test_count,
            "success_count": 0,
            "high_quality_count": 0,
            "total_latency_ms": 0,
            "errors": [],
        }
        
        tasks = generate_tasks(test_count)
        
        for i, task in enumerate(tasks):
            logger.info(f"  [{i+1}/{test_count}] {task[:40]}...")
            
            result = await run_task_and_collect(agent, task, f"eval_{label}_{i}")
            
            if result.get("success"):
                results["success_count"] += 1
                results["total_latency_ms"] += result.get("duration_ms", 0)
                
                is_quality, reason = quick_quality_check(result)
                if is_quality:
                    results["high_quality_count"] += 1
            else:
                results["errors"].append({
                    "task": task[:50],
                    "error": str(result.get("error", "unknown"))[:100]
                })
        
        # 计算指标
        results["success_rate"] = results["success_count"] / test_count
        results["quality_rate"] = results["high_quality_count"] / test_count
        results["avg_latency_ms"] = (
            results["total_latency_ms"] / results["success_count"]
            if results["success_count"] > 0 else 0
        )
        
        # 综合得分
        results["composite_score"] = (
            results["success_rate"] * 0.4 +
            results["quality_rate"] * 0.4 +
            min(1.0, 10000 / max(results["avg_latency_ms"], 1)) * 0.2
        )
        
        logger.info(f"[{label}] Legacy 评估完成:")
        logger.info(f"  成功率: {results['success_rate']:.1%}")
        logger.info(f"  质量率: {results['quality_rate']:.1%}")
        logger.info(f"  综合得分: {results['composite_score']:.2f}")
        
        return results
    
    async def run_dspy_optimization(self) -> bool:
        """
        运行 DSPy 优化
        """
        try:
            from engine.agent.dspy_optimizer import (
                DSPyClassifier,
                optimize_classifier,
                DSPY_AVAILABLE,
            )
            
            if not DSPY_AVAILABLE:
                logger.error("DSPy 不可用，请安装: pip install dspy-ai")
                return False
            
            logger.info("[DSPy] 开始优化...")
            
            # 创建分类器实例
            classifier = DSPyClassifier()
            
            # 运行优化
            optimized = optimize_classifier(classifier, auto="light")
            
            # 保存优化后的分类器
            if optimized:
                save_path = Path("data/dspy_cache/optimized_classifier.json")
                save_path.parent.mkdir(parents=True, exist_ok=True)
                optimized.save(str(save_path))
                logger.info(f"[DSPy] 优化完成，已保存到: {save_path}")
                return True
            
            return False
        except ImportError as e:
            logger.error(f"[DSPy] 模块导入失败: {e}")
            logger.error("请确保已安装 dspy-ai: pip install dspy-ai")
            return False
        except Exception as e:
            logger.error(f"[DSPy] 优化失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def full_cycle(
        self,
        use_langsmith: bool = True,
        dataset_name: str = None,
        evaluator_mode: str = "essential",
        test_count: int = 20,
        min_improvement: float = 0.05,
        max_concurrency: int = 2,
    ) -> Dict[str, Any]:
        """
        完整优化循环
        
        Args:
            use_langsmith: 使用 LangSmith 评估（推荐）
            dataset_name: 数据集名称（LangSmith 模式）
            evaluator_mode: 评估器模式
            test_count: 测试数量（Legacy 模式）
            min_improvement: 最小提升阈值
            max_concurrency: 并发数
            
        Returns:
            循环结果
        """
        cycle_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info("=" * 60)
        logger.info(f"优化循环开始: {cycle_id}")
        logger.info(f"模式: {'LangSmith' if use_langsmith else 'Legacy'}")
        logger.info("=" * 60)
        
        cycle_result = {
            "cycle_id": cycle_id,
            "timestamp": datetime.now().isoformat(),
            "mode": "langsmith" if use_langsmith else "legacy",
            "evaluator_mode": evaluator_mode,
            "min_improvement": min_improvement,
        }
        
        # Step 1: Baseline 评估
        logger.info("\n[Step 1/4] 评估当前性能 (Baseline)...")
        if use_langsmith:
            baseline = self.run_langsmith_evaluation(
                "baseline",
                dataset_name=dataset_name,
                evaluator_mode=evaluator_mode,
                max_concurrency=max_concurrency,
            )
        else:
            baseline = await self.run_legacy_evaluation("baseline", test_count)
        
        cycle_result["baseline"] = baseline
        
        if baseline.get("error"):
            cycle_result["decision"] = "SKIP"
            cycle_result["reason"] = f"Baseline 评估失败: {baseline.get('error')}"
            self.history.append(cycle_result)
            self._save_history()
            return cycle_result
        
        # Step 2: DSPy 优化
        logger.info("\n[Step 2/4] 运行 DSPy 优化...")
        optimization_success = await self.run_dspy_optimization()
        cycle_result["optimization_success"] = optimization_success
        
        if not optimization_success:
            cycle_result["decision"] = "SKIP"
            cycle_result["reason"] = "DSPy 优化失败"
            self.history.append(cycle_result)
            self._save_history()
            return cycle_result
        
        # Step 3: 优化后评估
        logger.info("\n[Step 3/4] 评估优化后性能...")
        if use_langsmith:
            optimized = self.run_langsmith_evaluation(
                "optimized",
                dataset_name=dataset_name,
                evaluator_mode=evaluator_mode,
                max_concurrency=max_concurrency,
            )
        else:
            optimized = await self.run_legacy_evaluation("optimized", test_count)
        
        cycle_result["optimized"] = optimized
        
        if optimized.get("error"):
            cycle_result["decision"] = "SKIP"
            cycle_result["reason"] = f"优化后评估失败: {optimized.get('error')}"
            self.history.append(cycle_result)
            self._save_history()
            return cycle_result
        
        # Step 4: 比较 & 决策
        logger.info("\n[Step 4/4] 比较结果...")
        baseline_score = baseline.get("composite_score", 0)
        optimized_score = optimized.get("composite_score", 0)
        improvement = optimized_score - baseline_score
        improvement_pct = improvement / max(baseline_score, 0.01)
        
        cycle_result["improvement"] = improvement
        cycle_result["improvement_pct"] = improvement_pct
        
        logger.info("\n" + "=" * 60)
        logger.info("优化结果对比")
        logger.info("=" * 60)
        logger.info(f"  Baseline 得分:  {baseline_score:.3f}")
        logger.info(f"  Optimized 得分: {optimized_score:.3f}")
        logger.info(f"  提升: {improvement:+.3f} ({improvement_pct:+.1%})")
        
        if improvement >= min_improvement:
            cycle_result["decision"] = "DEPLOY"
            cycle_result["reason"] = f"提升 {improvement_pct:.1%} >= {min_improvement:.0%}"
            logger.info(f"\n[OK] 决策: DEPLOY - 优化有效，保存新配置")
        else:
            cycle_result["decision"] = "ROLLBACK"
            cycle_result["reason"] = f"提升 {improvement_pct:.1%} < {min_improvement:.0%}"
            logger.info(f"\n[SKIP] 决策: ROLLBACK - 提升不足，保持原配置")
        
        # 保存历史
        self.history.append(cycle_result)
        self._save_history()
        
        # 保存本次详细结果
        result_file = self.output_dir / f"cycle_{cycle_id}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(cycle_result, f, ensure_ascii=False, indent=2)
        logger.info(f"\n详细结果已保存: {result_file}")
        
        return cycle_result
    
    def show_history(self):
        """显示优化历史"""
        if not self.history:
            print("没有优化历史记录")
            return
        
        print("\n" + "=" * 80)
        print("优化历史")
        print("=" * 80)
        print(f"{'时间':<20} {'模式':<10} {'Baseline':<10} {'Optimized':<10} {'提升':<10} {'决策':<10}")
        print("-" * 80)
        
        for h in self.history[-10:]:  # 最近 10 条
            timestamp = h.get("timestamp", "")[:16]
            mode = h.get("mode", "legacy")[:8]
            baseline_score = h.get("baseline", {}).get("composite_score", 0)
            optimized_score = h.get("optimized", {}).get("composite_score", 0)
            improvement = h.get("improvement_pct", 0)
            decision = h.get("decision", "N/A")
            
            print(f"{timestamp:<20} {mode:<10} {baseline_score:<10.3f} {optimized_score:<10.3f} {improvement:+.1%}     {decision:<10}")
        
        print("=" * 80)


async def main():
    # 加载 API Keys
    try:
        import api_keys
        api_keys.setup_env()
    except ImportError:
        logger.warning("[Optimization] api_keys.py not found")
    
    parser = argparse.ArgumentParser(description="NogicOS 闭环优化系统（整合 LangSmith）")
    
    # 主要命令
    parser.add_argument("--full-cycle", action="store_true", help="运行完整优化循环")
    parser.add_argument("--evaluate-only", action="store_true", help="只运行评估（不优化）")
    parser.add_argument("--history", action="store_true", help="显示优化历史")
    
    # 评估配置
    parser.add_argument("--dataset", type=str, default="nogicos_comprehensive", help="数据集名称")
    parser.add_argument("--mode", type=str, default="essential", 
                       choices=["all", "fast", "quality", "essential", "llm", "rule"],
                       help="评估器模式")
    parser.add_argument("--concurrency", type=int, default=2, help="并发数")
    parser.add_argument("--min-improvement", type=float, default=0.05, help="最小提升阈值")
    
    # Legacy 模式
    parser.add_argument("--legacy", action="store_true", help="使用 Legacy 评估模式")
    parser.add_argument("--test-count", type=int, default=20, help="测试数量（Legacy 模式）")
    
    args = parser.parse_args()
    
    loop = OptimizationLoop()
    
    if args.history:
        loop.show_history()
    
    elif args.evaluate_only:
        logger.info("运行单次评估（不优化）...")
        if args.legacy:
            result = await loop.run_legacy_evaluation("evaluate", args.test_count)
        else:
            result = loop.run_langsmith_evaluation(
                "evaluate",
                dataset_name=args.dataset,
                evaluator_mode=args.mode,
                max_concurrency=args.concurrency,
            )
        
        print("\n" + "=" * 50)
        print("[RESULT] 评估完成")
        print("=" * 50)
        print(f"综合得分: {result.get('composite_score', 0):.3f}")
        if "scores" in result:
            print("\n详细分数:")
            for key, stat in result["scores"].items():
                if isinstance(stat, dict):
                    print(f"  {key}: {stat.get('avg', 0):.3f}")
    
    elif args.full_cycle:
        await loop.full_cycle(
            use_langsmith=not args.legacy,
            dataset_name=args.dataset,
            evaluator_mode=args.mode,
            test_count=args.test_count,
            min_improvement=args.min_improvement,
            max_concurrency=args.concurrency,
        )
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
