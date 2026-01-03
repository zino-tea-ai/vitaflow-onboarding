#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NogicOS Evaluation Runner

Run automated evaluations against the NogicOS agent.

Usage:
    # Create golden dataset
    python -m engine.evaluation.run_evaluation --create-golden
    
    # Run evaluation
    python -m engine.evaluation.run_evaluation --evaluate nogicos_golden
    
    # Create dataset from recent runs
    python -m engine.evaluation.run_evaluation --create-from-runs --limit 20
"""

import os
import sys
import asyncio
import argparse
from typing import Optional, List, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from engine.observability import get_logger, setup_logging
logger = get_logger("evaluation_runner")

# LangSmith evaluation
try:
    from langsmith.evaluation import evaluate
    LANGSMITH_EVAL_AVAILABLE = True
except ImportError:
    LANGSMITH_EVAL_AVAILABLE = False
    logger.warning("[Evaluation] LangSmith evaluation not available")

# Local imports
from engine.evaluation.evaluators import (
    task_completion_evaluator,
    tool_selection_evaluator,
    response_quality_evaluator,
    latency_evaluator,
    aggregate_evaluator,
)
from engine.evaluation.dataset_manager import (
    DatasetManager,
    create_golden_dataset,
    create_dataset_from_runs,
)


def get_agent_function():
    """
    Get the NogicOS agent function for evaluation.
    
    Returns a callable that takes inputs dict and returns outputs dict.
    """
    from engine.agent.react_agent import ReActAgent
    
    agent = ReActAgent()
    
    def agent_fn(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for sync evaluation."""
        task = inputs.get("task", "")
        session_id = inputs.get("session_id", "evaluation")
        
        # Run async agent in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                agent.run(task=task, session_id=session_id)
            )
            return {
                "success": result.success,
                "response": result.response,
                "error": result.error,
                "iterations": result.iterations,
                "tool_calls": result.tool_calls,
            }
        finally:
            loop.close()
    
    return agent_fn


async def get_async_agent_function():
    """
    Get async agent function for evaluation.
    """
    from engine.agent.react_agent import ReActAgent
    
    agent = ReActAgent()
    
    async def agent_fn(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Async wrapper."""
        task = inputs.get("task", "")
        session_id = inputs.get("session_id", "evaluation")
        
        result = await agent.run(task=task, session_id=session_id)
        
        return {
            "success": result.success,
            "response": result.response,
            "error": result.error,
            "iterations": result.iterations,
            "tool_calls": result.tool_calls,
        }
    
    return agent_fn


def run_evaluation(
    dataset_name: str,
    experiment_prefix: str = "nogicos_eval",
    evaluators: Optional[List] = None,
    max_concurrency: int = 2,
) -> Dict[str, Any]:
    """
    Run evaluation against a dataset.
    
    Args:
        dataset_name: Name of the dataset to evaluate against
        experiment_prefix: Prefix for the experiment name
        evaluators: List of evaluator functions (uses defaults if not provided)
        max_concurrency: Maximum concurrent evaluations
        
    Returns:
        Evaluation results summary
    """
    if not LANGSMITH_EVAL_AVAILABLE:
        raise ImportError("LangSmith evaluation not available")
    
    # Default evaluators
    if evaluators is None:
        evaluators = [
            task_completion_evaluator,
            tool_selection_evaluator,
            response_quality_evaluator,
            latency_evaluator,
        ]
    
    logger.info(f"Starting evaluation on dataset '{dataset_name}'...")
    logger.info(f"Using {len(evaluators)} evaluators")
    
    # Get agent function
    agent_fn = get_agent_function()
    
    # Run evaluation
    results = evaluate(
        agent_fn,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
        metadata={
            "agent": "NogicOS ReActAgent",
            "version": "2.0",
        },
    )
    
    # Process results - iterate directly over ExperimentResults
    summary = {
        "experiment_name": results.experiment_name,
        "total_examples": 0,
        "scores": {},
    }
    
    # ExperimentResults is iterable
    for row in results:
        summary["total_examples"] += 1
        # Each row has 'run', 'example', and 'evaluation_results'
        eval_results = row.get("evaluation_results", {})
        if isinstance(eval_results, dict):
            for key, value in eval_results.items():
                if key not in summary["scores"]:
                    summary["scores"][key] = []
                # Handle both dict and direct score values
                if isinstance(value, dict):
                    score = value.get("score", 0)
                else:
                    score = value if isinstance(value, (int, float)) else 0
                summary["scores"][key].append(score)
    
    # Calculate averages
    for key, scores in list(summary["scores"].items()):
        if scores:
            summary["scores"][key] = {
                "avg": sum(scores) / len(scores),
                "min": min(scores),
                "max": max(scores),
                "count": len(scores),
            }
    
    logger.info(f"Evaluation complete: {summary['experiment_name']}")
    logger.info(f"Results: {summary['scores']}")
    
    return summary


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="NogicOS Evaluation Runner")
    
    parser.add_argument(
        "--create-golden",
        action="store_true",
        help="Create golden test dataset",
    )
    parser.add_argument(
        "--create-from-runs",
        action="store_true",
        help="Create dataset from recent runs",
    )
    parser.add_argument(
        "--evaluate",
        type=str,
        metavar="DATASET",
        help="Run evaluation on specified dataset",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="nogicos_from_runs",
        help="Dataset name for --create-from-runs",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of runs to include (for --create-from-runs)",
    )
    parser.add_argument(
        "--list-datasets",
        action="store_true",
        help="List all datasets",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Max concurrent evaluations",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging("INFO")
    
    try:
        if args.create_golden:
            logger.info("Creating golden dataset...")
            info = create_golden_dataset()
            print(f"[OK] Created: {info.name} ({info.example_count} examples)")
            print(f"     ID: {info.id}")
        
        elif args.create_from_runs:
            logger.info(f"Creating dataset from recent runs (limit={args.limit})...")
            info = create_dataset_from_runs(
                dataset_name=args.dataset_name,
                limit=args.limit,
            )
            print(f"[OK] Created: {info.name} ({info.example_count} examples)")
            print(f"     ID: {info.id}")
        
        elif args.evaluate:
            logger.info(f"Running evaluation on '{args.evaluate}'...")
            results = run_evaluation(
                dataset_name=args.evaluate,
                max_concurrency=args.concurrency,
            )
            print("\n" + "="*50)
            print(f"[RESULTS] {results['experiment_name']}")
            print("="*50)
            print(f"Total examples: {results['total_examples']}")
            print("\nScores:")
            for key, stats in results["scores"].items():
                print(f"  {key}: avg={stats['avg']:.2f}, min={stats['min']:.2f}, max={stats['max']:.2f}")
        
        elif args.list_datasets:
            manager = DatasetManager()
            datasets = manager.list_datasets()
            print(f"\n[DATASETS] ({len(datasets)}):")
            for ds in datasets:
                print(f"  - {ds.name}: {ds.example_count} examples")
        
        else:
            parser.print_help()
    
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

