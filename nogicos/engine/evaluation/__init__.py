# -*- coding: utf-8 -*-
"""
NogicOS Evaluation Module

Provides:
- LangSmith dataset management
- Custom evaluators for agent tasks
- Automated evaluation pipeline
- Agent architecture evaluators (Phase 8)
- Online monitoring rules (Phase 8)
"""

# 现有评估器
from .evaluators import (
    # 规则评估器
    latency_evaluator,
    token_count_evaluator,
    tool_call_count_evaluator,
    error_rate_evaluator,
    # UX 评估器
    ttft_evaluator,
    follow_up_evaluator,
    content_richness_evaluator,
    # LLM 评估器
    task_completion_llm_evaluator,
    tool_selection_llm_evaluator,
    correctness_evaluator,
    hallucination_evaluator,
    conciseness_evaluator,
    # 兼容性别名
    task_completion_evaluator,
    tool_selection_evaluator,
    response_quality_evaluator,
    # 评估器组
    get_rule_evaluators,
    get_llm_evaluators,
    get_ux_evaluators,
    get_all_evaluators,
    get_fast_evaluators,
    get_quality_evaluators,
    get_essential_evaluators,
)

# Phase 8: 新增 Agent 架构评估器
from .agent_evaluators import (
    agent_handoff_evaluator,
    window_isolation_evaluator,
    set_task_status_evaluator,
    multi_agent_efficiency_evaluator,
    get_agent_evaluators,
    get_agent_core_evaluators,
    get_agent_quality_evaluators,
)

# Phase 8: 在线监控规则
from .online_rules import (
    ONLINE_RULES,
    OnlineRule,
    RuleType,
    Severity,
    get_alert_rules,
    get_review_rules,
    get_critical_rules,
    get_agent_architecture_rules,
    export_rules_for_langsmith,
)

# 数据集管理
from .dataset_manager import (
    DatasetManager,
    create_dataset_from_runs,
    add_example_to_dataset,
)

__all__ = [
    # === 规则评估器（客观指标） ===
    "latency_evaluator",
    "token_count_evaluator",
    "tool_call_count_evaluator",
    "error_rate_evaluator",
    
    # === UX 评估器 ===
    "ttft_evaluator",
    "follow_up_evaluator",
    "content_richness_evaluator",
    
    # === LLM 评估器（语义理解） ===
    "task_completion_llm_evaluator",
    "tool_selection_llm_evaluator",
    "correctness_evaluator",
    "hallucination_evaluator",
    "conciseness_evaluator",
    
    # === 兼容性别名 ===
    "task_completion_evaluator",
    "tool_selection_evaluator",
    "response_quality_evaluator",
    
    # === 评估器组函数 ===
    "get_rule_evaluators",
    "get_llm_evaluators",
    "get_ux_evaluators",
    "get_all_evaluators",
    "get_fast_evaluators",
    "get_quality_evaluators",
    "get_essential_evaluators",
    
    # === Phase 8: Agent 架构评估器 ===
    "agent_handoff_evaluator",
    "window_isolation_evaluator",
    "set_task_status_evaluator",
    "multi_agent_efficiency_evaluator",
    "get_agent_evaluators",
    "get_agent_core_evaluators",
    "get_agent_quality_evaluators",
    
    # === Phase 8: 在线监控规则 ===
    "ONLINE_RULES",
    "OnlineRule",
    "RuleType",
    "Severity",
    "get_alert_rules",
    "get_review_rules",
    "get_critical_rules",
    "get_agent_architecture_rules",
    "export_rules_for_langsmith",
    
    # === 数据集管理 ===
    "DatasetManager",
    "create_dataset_from_runs",
    "add_example_to_dataset",
]

