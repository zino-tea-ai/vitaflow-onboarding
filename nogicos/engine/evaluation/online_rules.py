# -*- coding: utf-8 -*-
"""
NogicOS Online Monitoring Rules - Phase 8.4

LangSmith Online Evaluation Rules 配置，用于实时监控 Agent 运行质量。

这些规则会在 LangSmith Dashboard 中配置，实现：
- 实时告警 (Alerts)
- 人工审核标记 (Review Flags)
- 自动评估触发 (Auto Evaluation)

Usage:
    from engine.evaluation.online_rules import (
        ONLINE_RULES,
        get_alert_rules,
        get_review_rules,
        get_critical_rules,
    )

配置方式：
    在 LangSmith Dashboard → Project → Rules 中手动配置，
    或使用 LangSmith API 自动化配置。

Reference:
    https://docs.smith.langchain.com/evaluation/how_to_guides/online_evaluation

================================================================================
字段依赖说明（IMPORTANT）
================================================================================

本文件中的规则条件依赖以下字段，需确保评估流水线正确写入：

1. run.outputs.* 字段（由 HostAgent 写入）:
   - run.outputs.iterations: 迭代次数
   - run.outputs.success: 任务是否成功
   - run.outputs.tool_calls: 工具调用列表
   
   写入位置: HostAgent._get_task_result() 返回值

2. feedback.* 字段（由评估器写入）:
   - feedback.latency         <- latency_evaluator (key="latency")
   - feedback.error_rate      <- error_rate_evaluator (key="error_rate")
   - feedback.token_count     <- token_count_evaluator (key="token_count")
   - feedback.ttft            <- ttft_evaluator (key="ttft")
   - feedback.hallucination   <- hallucination_evaluator (key="hallucination")
   - feedback.task_completion_llm <- task_completion_llm_evaluator (key="task_completion_llm")
   - feedback.content_richness <- content_richness_evaluator (key="content_richness")
   - feedback.window_isolation <- window_isolation_evaluator (key="window_isolation")
   - feedback.agent_handoff   <- agent_handoff_evaluator (key="agent_handoff")
   - feedback.multi_agent_efficiency <- multi_agent_efficiency_evaluator (key="multi_agent_efficiency")
   - feedback.set_task_status <- set_task_status_evaluator (key="set_task_status")
   
   写入方式: 评估器返回 {"key": "xxx", "score": 0.x, "comment": "..."} 
             LangSmith 自动将其写入 feedback.{key}

3. 验证规则是否生效:
   - 在 LangSmith Dashboard 查看 Runs，确认 feedback 字段已写入
   - 使用 run_evaluation.py 触发评估，检查 feedback 是否正确
   
================================================================================
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from engine.observability import get_logger

logger = get_logger("online_rules")


class RuleType(Enum):
    """规则类型"""
    ALERT = "alert"           # 告警规则（触发通知）
    REVIEW = "review"         # 审核规则（标记人工审核）
    EVALUATION = "evaluation" # 评估规则（触发自动评估）


class Severity(Enum):
    """严重程度"""
    CRITICAL = "critical"  # 严重 - 立即通知
    HIGH = "high"          # 高 - 尽快处理
    MEDIUM = "medium"      # 中 - 需要关注
    LOW = "low"            # 低 - 信息记录


@dataclass
class OnlineRule:
    """
    在线监控规则定义
    
    Attributes:
        name: 规则名称
        description: 规则描述
        rule_type: 规则类型
        severity: 严重程度
        condition: 触发条件（LangSmith 表达式）
        action: 触发时的动作
        evaluator: 关联的评估器（如果是评估规则）
        notification_channels: 通知渠道列表
        enabled: 是否启用
    """
    name: str
    description: str
    rule_type: RuleType
    severity: Severity
    condition: str
    action: str
    evaluator: Optional[str] = None
    notification_channels: List[str] = field(default_factory=list)
    enabled: bool = True
    
    def to_langsmith_config(self) -> Dict[str, Any]:
        """转换为 LangSmith API 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.rule_type.value,
            "severity": self.severity.value,
            "condition": self.condition,
            "action": self.action,
            "evaluator": self.evaluator,
            "notification_channels": self.notification_channels,
            "enabled": self.enabled,
        }


# ===========================================
# 告警规则 (Alerts) - 性能和错误监控
# ===========================================
# NOTE: 条件使用 LangSmith 实际支持的字段路径
# - run.outputs.* : Agent 输出的字段（由 HostAgent 写入）
# - run.inputs.* : 任务输入
# - run.error : 运行错误
# - feedback.* : 评估器反馈（由 evaluator 写入）

LATENCY_ALERT = OnlineRule(
    name="high_latency_alert",
    description="检测高延迟任务（> 30s），触发告警",
    rule_type=RuleType.ALERT,
    severity=Severity.HIGH,
    # 使用 feedback.latency 由 latency_evaluator 写入
    condition="feedback.latency < 0.2",  # score < 0.2 表示 > 30s
    action="Send notification to Slack channel #agent-alerts",
    evaluator="latency_evaluator",
    notification_channels=["slack:agent-alerts", "email:oncall"],
    enabled=True,
)

ERROR_RATE_ALERT = OnlineRule(
    name="error_rate_alert",
    description="检测高错误率（> 30%），触发告警",
    rule_type=RuleType.ALERT,
    severity=Severity.CRITICAL,
    # 使用 feedback.error_rate 由 error_rate_evaluator 写入
    condition="feedback.error_rate < 0.5",  # score < 0.5 表示有显著错误
    action="Send immediate notification + create incident",
    evaluator="error_rate_evaluator",
    notification_channels=["slack:agent-alerts", "pagerduty"],
    enabled=True,
)

ITERATION_LIMIT_ALERT = OnlineRule(
    name="iteration_limit_alert",
    description="检测接近迭代上限（> 40/50），预警",
    rule_type=RuleType.ALERT,
    severity=Severity.MEDIUM,
    # 使用 run.outputs.iterations 由 HostAgent 写入
    condition="run.outputs.iterations > 40",
    action="Send warning notification",
    notification_channels=["slack:agent-monitoring"],
    enabled=True,
)

TOKEN_OVERUSE_ALERT = OnlineRule(
    name="token_overuse_alert",
    description="检测 token 使用过量（> 100k），成本预警",
    rule_type=RuleType.ALERT,
    severity=Severity.MEDIUM,
    # 使用 feedback.token_count 由 token_count_evaluator 写入
    condition="feedback.token_count < 0.4",  # score < 0.4 表示 > 5000 tokens
    action="Send cost warning notification",
    evaluator="token_count_evaluator",
    notification_channels=["email:billing"],
    enabled=True,
)


# ===========================================
# 审核规则 (Review Flags) - 质量审核标记
# ===========================================

HALLUCINATION_REVIEW = OnlineRule(
    name="hallucination_review",
    description="幻觉检测评分低时标记人工审核",
    rule_type=RuleType.REVIEW,
    severity=Severity.HIGH,
    condition="feedback.hallucination < 0.5",
    action="Flag for human review",
    evaluator="hallucination_evaluator",
    enabled=True,
)

LOW_COMPLETION_REVIEW = OnlineRule(
    name="low_completion_review",
    description="任务完成度低时标记审核",
    rule_type=RuleType.REVIEW,
    severity=Severity.MEDIUM,
    condition="feedback.task_completion_llm < 0.5",
    action="Flag for review with context",
    evaluator="task_completion_llm_evaluator",
    enabled=True,
)

NEEDS_HELP_REVIEW = OnlineRule(
    name="needs_help_review",
    description="Agent 请求帮助时标记审核",
    rule_type=RuleType.REVIEW,
    severity=Severity.LOW,
    # set_task_status 评估器会检测 needs_help 状态，分数 0.8 表示 needs_help
    condition="feedback.set_task_status >= 0.7 AND feedback.set_task_status <= 0.85",
    action="Flag for review - check if help request is valid",
    evaluator="set_task_status_evaluator",
    enabled=True,
)


# ===========================================
# Agent 架构专用规则 (Phase 8)
# ===========================================

WINDOW_ISOLATION_CRITICAL = OnlineRule(
    name="window_isolation_critical",
    description="窗口隔离违规（跨窗口污染），严重告警",
    rule_type=RuleType.ALERT,
    severity=Severity.CRITICAL,
    condition="feedback.window_isolation < 0.3",
    action="Immediate alert - potential data leakage between windows",
    evaluator="window_isolation_evaluator",
    notification_channels=["slack:agent-alerts", "pagerduty"],
    enabled=True,
)

HANDOFF_FAILURE_ALERT = OnlineRule(
    name="handoff_failure_alert",
    description="Agent handoff 失败率高，告警",
    rule_type=RuleType.ALERT,
    severity=Severity.HIGH,
    condition="feedback.agent_handoff < 0.5",
    action="Alert - AppAgent scheduling issues",
    evaluator="agent_handoff_evaluator",
    notification_channels=["slack:agent-monitoring"],
    enabled=True,
)

INEFFICIENT_EXECUTION_REVIEW = OnlineRule(
    name="inefficient_execution_review",
    description="多 Agent 协作效率低时标记审核",
    rule_type=RuleType.REVIEW,
    severity=Severity.MEDIUM,
    condition="feedback.multi_agent_efficiency < 0.5",
    action="Flag for optimization review",
    evaluator="multi_agent_efficiency_evaluator",
    enabled=True,
)

TASK_STATUS_MISSING_ALERT = OnlineRule(
    name="task_status_missing_alert",
    description="任务未正确设置状态，可能是 bug",
    rule_type=RuleType.ALERT,
    severity=Severity.MEDIUM,
    condition="feedback.set_task_status < 0.3",
    action="Alert - task termination issue",
    evaluator="set_task_status_evaluator",
    notification_channels=["slack:agent-monitoring"],
    enabled=True,
)


# ===========================================
# UX 相关规则
# ===========================================

SLOW_TTFT_REVIEW = OnlineRule(
    name="slow_ttft_review",
    description="首 Token 时间过长（> 3s），影响用户体验",
    rule_type=RuleType.REVIEW,
    severity=Severity.MEDIUM,
    # 使用 feedback.ttft 由 ttft_evaluator 写入，score < 0.5 表示 > 2s
    condition="feedback.ttft < 0.5",
    action="Flag for UX optimization review",
    evaluator="ttft_evaluator",
    enabled=True,
)

LOW_CONTENT_RICHNESS_REVIEW = OnlineRule(
    name="low_content_richness_review",
    description="响应内容不够丰富，可能需要改进 prompt",
    rule_type=RuleType.REVIEW,
    severity=Severity.LOW,
    # 修复：添加括号确保 OR 逻辑正确
    condition="feedback.content_richness < 0.5 AND (run.inputs.task CONTAINS '写' OR run.inputs.task CONTAINS 'code')",
    action="Flag for prompt improvement review",
    evaluator="content_richness_evaluator",
    enabled=True,
)


# ===========================================
# 规则集合
# ===========================================

ONLINE_RULES: Dict[str, OnlineRule] = {
    # 告警规则
    "latency_alert": LATENCY_ALERT,
    "error_rate_alert": ERROR_RATE_ALERT,
    "iteration_limit_alert": ITERATION_LIMIT_ALERT,
    "token_overuse_alert": TOKEN_OVERUSE_ALERT,
    
    # 审核规则
    "hallucination_review": HALLUCINATION_REVIEW,
    "low_completion_review": LOW_COMPLETION_REVIEW,
    "needs_help_review": NEEDS_HELP_REVIEW,
    
    # Agent 架构规则 (Phase 8)
    "window_isolation_critical": WINDOW_ISOLATION_CRITICAL,
    "handoff_failure_alert": HANDOFF_FAILURE_ALERT,
    "inefficient_execution_review": INEFFICIENT_EXECUTION_REVIEW,
    "task_status_missing_alert": TASK_STATUS_MISSING_ALERT,
    
    # UX 规则
    "slow_ttft_review": SLOW_TTFT_REVIEW,
    "low_content_richness_review": LOW_CONTENT_RICHNESS_REVIEW,
}


# ===========================================
# 辅助函数
# ===========================================

def get_alert_rules() -> List[OnlineRule]:
    """获取所有告警规则"""
    return [rule for rule in ONLINE_RULES.values() if rule.rule_type == RuleType.ALERT]


def get_review_rules() -> List[OnlineRule]:
    """获取所有审核规则"""
    return [rule for rule in ONLINE_RULES.values() if rule.rule_type == RuleType.REVIEW]


def get_critical_rules() -> List[OnlineRule]:
    """获取所有严重级别规则"""
    return [rule for rule in ONLINE_RULES.values() if rule.severity == Severity.CRITICAL]


def get_agent_architecture_rules() -> List[OnlineRule]:
    """获取 Agent 架构相关规则 (Phase 8)"""
    agent_rules = [
        "window_isolation_critical",
        "handoff_failure_alert",
        "inefficient_execution_review",
        "task_status_missing_alert",
    ]
    return [ONLINE_RULES[name] for name in agent_rules if name in ONLINE_RULES]


def get_rules_by_evaluator(evaluator_name: str) -> List[OnlineRule]:
    """根据评估器名称获取关联规则"""
    return [
        rule for rule in ONLINE_RULES.values()
        if rule.evaluator and evaluator_name in rule.evaluator
    ]


def export_rules_for_langsmith() -> List[Dict[str, Any]]:
    """导出所有规则为 LangSmith API 格式"""
    return [rule.to_langsmith_config() for rule in ONLINE_RULES.values() if rule.enabled]


def get_notification_summary() -> Dict[str, List[str]]:
    """获取通知渠道汇总"""
    summary: Dict[str, List[str]] = {}
    for rule in ONLINE_RULES.values():
        for channel in rule.notification_channels:
            if channel not in summary:
                summary[channel] = []
            summary[channel].append(rule.name)
    return summary


# ===========================================
# 规则配置验证
# ===========================================

def validate_rules() -> List[str]:
    """
    验证规则配置是否完整
    
    Returns:
        验证错误列表，空列表表示全部通过
    """
    errors = []
    
    for name, rule in ONLINE_RULES.items():
        # 检查必填字段
        if not rule.name:
            errors.append(f"Rule '{name}' missing name")
        if not rule.condition:
            errors.append(f"Rule '{name}' missing condition")
        if not rule.action:
            errors.append(f"Rule '{name}' missing action")
        
        # 检查评估规则是否有关联评估器
        if rule.rule_type == RuleType.EVALUATION and not rule.evaluator:
            errors.append(f"Evaluation rule '{name}' missing evaluator")
        
        # 检查严重告警是否有通知渠道
        if rule.severity == Severity.CRITICAL and not rule.notification_channels:
            errors.append(f"Critical rule '{name}' has no notification channels")
    
    if errors:
        for error in errors:
            logger.warning(f"[OnlineRules] Validation: {error}")
    else:
        logger.info(f"[OnlineRules] All {len(ONLINE_RULES)} rules validated successfully")
    
    return errors


# 模块加载时验证
_validation_errors = validate_rules()
