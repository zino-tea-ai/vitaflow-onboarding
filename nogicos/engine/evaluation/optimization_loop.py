# -*- coding: utf-8 -*-
"""
NogicOS Optimization Loop - 闭环优化系统

完整流程：
1. 采集数据 (auto_data_collector)
2. 评估当前性能 (baseline)
3. DSPy 优化
4. 评估优化后性能
5. A/B 对比
6. 如果更好则保存，否则回滚

用法：
    python -m engine.evaluation.optimization_loop --full-cycle
    python -m engine.evaluation.optimization_loop --compare
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
    闭环优化系统
    
    核心原则：优化必须可验证，否则不部署
    """
    
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
    
    async def run_evaluation(self, label: str, test_count: int = 20) -> Dict[str, Any]:
        """
        运行评估，返回性能指标
        """
        from engine.evaluation.auto_data_collector import (
            generate_tasks,
            quick_quality_check,
            run_task_and_collect,
        )
        from engine.agent.react_agent import ReActAgent
        
        logger.info(f"[{label}] 开始评估，测试 {test_count} 个任务...")
        
        # 初始化 Agent
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
        
        # 生成任务
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
        
        # 综合得分 (可调整权重)
        results["composite_score"] = (
            results["success_rate"] * 0.4 +
            results["quality_rate"] * 0.4 +
            min(1.0, 10000 / max(results["avg_latency_ms"], 1)) * 0.2  # 延迟越低越好
        )
        
        logger.info(f"[{label}] 评估完成:")
        logger.info(f"  成功率: {results['success_rate']:.1%}")
        logger.info(f"  质量率: {results['quality_rate']:.1%}")
        logger.info(f"  平均延迟: {results['avg_latency_ms']:.0f}ms")
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
                logger.error("DSPy 不可用")
                return False
            
            logger.info("[DSPy] 开始优化...")
            
            # 创建分类器实例
            classifier = DSPyClassifier()
            
            # 运行优化
            optimized = optimize_classifier(classifier, auto="light")
            
            # 保存优化后的分类器
            if optimized:
                optimized.save("data/dspy_cache/optimized_classifier.json")
                logger.info("[DSPy] 优化完成，已保存")
                return True
            
            return False
        except Exception as e:
            logger.error(f"[DSPy] 优化失败: {e}")
            return False
    
    async def full_cycle(
        self,
        test_count: int = 20,
        min_improvement: float = 0.05,  # 至少提升 5% 才部署
    ) -> Dict[str, Any]:
        """
        完整优化循环：
        1. 评估 baseline
        2. DSPy 优化
        3. 评估优化后
        4. 比较 & 决策
        """
        cycle_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"=" * 60)
        logger.info(f"优化循环开始: {cycle_id}")
        logger.info(f"=" * 60)
        
        cycle_result = {
            "cycle_id": cycle_id,
            "timestamp": datetime.now().isoformat(),
            "test_count": test_count,
            "min_improvement": min_improvement,
        }
        
        # Step 1: Baseline 评估
        logger.info("\n[Step 1/4] 评估当前性能 (Baseline)...")
        baseline = await self.run_evaluation("baseline", test_count)
        cycle_result["baseline"] = baseline
        
        # Step 2: DSPy 优化
        logger.info("\n[Step 2/4] 运行 DSPy 优化...")
        optimization_success = await self.run_dspy_optimization()
        cycle_result["optimization_success"] = optimization_success
        
        if not optimization_success:
            cycle_result["decision"] = "SKIP"
            cycle_result["reason"] = "优化失败"
            self.history.append(cycle_result)
            self._save_history()
            return cycle_result
        
        # Step 3: 优化后评估
        logger.info("\n[Step 3/4] 评估优化后性能...")
        optimized = await self.run_evaluation("optimized", test_count)
        cycle_result["optimized"] = optimized
        
        # Step 4: 比较 & 决策
        logger.info("\n[Step 4/4] 比较结果...")
        improvement = optimized["composite_score"] - baseline["composite_score"]
        improvement_pct = improvement / max(baseline["composite_score"], 0.01)
        
        cycle_result["improvement"] = improvement
        cycle_result["improvement_pct"] = improvement_pct
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"优化结果对比")
        logger.info(f"{'=' * 60}")
        logger.info(f"  Baseline 得分:  {baseline['composite_score']:.3f}")
        logger.info(f"  Optimized 得分: {optimized['composite_score']:.3f}")
        logger.info(f"  提升: {improvement:+.3f} ({improvement_pct:+.1%})")
        
        if improvement >= min_improvement:
            cycle_result["decision"] = "DEPLOY"
            cycle_result["reason"] = f"提升 {improvement_pct:.1%} >= {min_improvement:.0%}"
            logger.info(f"\n✅ 决策: DEPLOY - 优化有效，保存新配置")
            # TODO: 实际保存优化后的配置
        else:
            cycle_result["decision"] = "ROLLBACK"
            cycle_result["reason"] = f"提升 {improvement_pct:.1%} < {min_improvement:.0%}"
            logger.info(f"\n❌ 决策: ROLLBACK - 提升不足，保持原配置")
            # TODO: 回滚到原配置
        
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
        
        print(f"\n{'=' * 70}")
        print("优化历史")
        print(f"{'=' * 70}")
        print(f"{'时间':<20} {'Baseline':<10} {'Optimized':<10} {'提升':<10} {'决策':<10}")
        print("-" * 70)
        
        for h in self.history[-10:]:  # 最近 10 条
            timestamp = h.get("timestamp", "")[:16]
            baseline_score = h.get("baseline", {}).get("composite_score", 0)
            optimized_score = h.get("optimized", {}).get("composite_score", 0)
            improvement = h.get("improvement_pct", 0)
            decision = h.get("decision", "N/A")
            
            print(f"{timestamp:<20} {baseline_score:<10.3f} {optimized_score:<10.3f} {improvement:+.1%}     {decision:<10}")
        
        print(f"{'=' * 70}")


async def main():
    parser = argparse.ArgumentParser(description="NogicOS 闭环优化系统")
    parser.add_argument("--full-cycle", action="store_true", help="运行完整优化循环")
    parser.add_argument("--test-count", type=int, default=20, help="每次评估的测试数量")
    parser.add_argument("--min-improvement", type=float, default=0.05, help="最小提升阈值")
    parser.add_argument("--history", action="store_true", help="显示优化历史")
    parser.add_argument("--baseline-only", action="store_true", help="只运行 baseline 评估")
    
    args = parser.parse_args()
    
    loop = OptimizationLoop()
    
    if args.history:
        loop.show_history()
    elif args.baseline_only:
        await loop.run_evaluation("baseline", args.test_count)
    elif args.full_cycle:
        await loop.full_cycle(args.test_count, args.min_improvement)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())

