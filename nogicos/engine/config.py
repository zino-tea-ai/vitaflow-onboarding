"""
NogicOS 配置管理
================

集中管理所有配置参数，支持环境变量覆盖。

包含:
- AgentConfig: Agent 执行参数
- PerformanceSLO: 性能服务水平目标
- SecurityConfig: 安全相关配置

参考:
- 12-Factor App 配置管理
- ByteBot 执行参数
"""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


# ========== 性能 SLO ==========

@dataclass
class PerformanceSLO:
    """
    性能服务水平目标 (Service Level Objectives)
    
    定义系统性能的量化指标，用于监控和告警
    """
    
    # ========== 延迟 SLO ==========
    tool_execution_p50_ms: int = 200       # 工具执行 P50 延迟
    tool_execution_p99_ms: int = 2000      # 工具执行 P99 延迟
    llm_response_p50_ms: int = 3000        # LLM 响应 P50 延迟
    llm_response_p99_ms: int = 15000       # LLM 响应 P99 延迟
    screenshot_capture_ms: int = 500       # 截图捕获延迟
    
    # ========== 吞吐量 SLO ==========
    max_concurrent_tasks: int = 3          # 最大并发任务数
    tool_calls_per_minute: int = 60        # 每分钟工具调用数
    iterations_per_task: int = 20          # 每任务最大迭代数
    
    # ========== 资源 SLO ==========
    max_memory_mb: int = 500               # 最大内存使用
    max_cpu_percent: int = 30              # 最大 CPU 使用率
    max_screenshot_cache_mb: int = 50      # 截图缓存上限
    
    # ========== 可靠性 SLO ==========
    task_success_rate: float = 0.85        # 任务成功率 >= 85%
    tool_retry_rate: float = 0.10          # 工具重试率 <= 10%
    event_drop_rate: float = 0.01          # 事件丢弃率 <= 1%


# ========== 安全配置 ==========

@dataclass
class SecurityConfig:
    """安全相关配置"""
    
    # 敏感工具列表（需要用户确认）
    sensitive_tools: List[str] = field(default_factory=lambda: [
        "delete_file",
        "send_message", 
        "window_type",
        "execute_command",
        "modify_system_settings",
    ])
    
    # 是否强制确认敏感操作
    require_confirm_for_sensitive: bool = True
    
    # Prompt 注入检测
    enable_prompt_injection_detection: bool = True
    
    # 敏感数据模式（正则表达式）
    sensitive_data_patterns: List[str] = field(default_factory=lambda: [
        r"\b\d{16}\b",                    # 信用卡号
        r"\b\d{3}-\d{2}-\d{4}\b",         # SSN
        r"password\s*[:=]\s*\S+",         # 密码
        r"api[_-]?key\s*[:=]\s*\S+",      # API Key
    ])
    
    # 最大允许的工具参数长度
    max_tool_param_length: int = 10000


# ========== Agent 配置 ==========

@dataclass
class AgentConfig:
    """
    Agent 配置 - 支持环境变量覆盖
    
    使用示例:
    ```python
    # 从环境变量加载
    config = AgentConfig.from_env()
    
    # 验证配置
    errors = config.validate()
    if errors:
        raise ValueError(f"Config errors: {errors}")
    ```
    """
    
    # ========== 执行参数 ==========
    screenshot_delay_ms: int = 750
    context_compression_threshold: float = 0.75
    max_iterations: int = 20
    iteration_timeout_s: int = 120
    
    # ========== API 参数 ==========
    claude_model: str = "claude-sonnet-4-20250514"
    claude_timeout_s: int = 60
    max_retries: int = 3
    retry_delay_s: float = 1.0
    
    # ========== 并发参数 ==========
    max_concurrent_tasks: int = 3
    max_api_concurrency: int = 2
    
    # ========== 持久化 ==========
    db_path: str = "nogicos_tasks.db"
    checkpoint_interval: int = 5  # 每 N 次迭代保存检查点
    
    # ========== 性能 ==========
    slo: PerformanceSLO = field(default_factory=PerformanceSLO)
    enable_performance_monitoring: bool = True
    metrics_export_interval_s: int = 60
    
    # ========== 安全 ==========
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # ========== 功能开关 (Feature Flags) ==========
    enable_dual_agent: bool = False       # 启用双层 Agent
    enable_incremental_checkpoint: bool = True  # 启用增量检查点
    enable_backpressure_bus: bool = False  # 启用背压事件总线
    enable_prompt_caching: bool = True    # 启用 Prompt Caching
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """
        从环境变量加载配置
        
        环境变量命名规则: NOGICOS_<FIELD_NAME>
        """
        return cls(
            # 执行参数
            screenshot_delay_ms=int(os.getenv("NOGICOS_SCREENSHOT_DELAY", 750)),
            context_compression_threshold=float(os.getenv("NOGICOS_COMPRESSION_THRESHOLD", 0.75)),
            max_iterations=int(os.getenv("NOGICOS_MAX_ITERATIONS", 20)),
            iteration_timeout_s=int(os.getenv("NOGICOS_ITERATION_TIMEOUT", 120)),
            
            # API 参数
            claude_model=os.getenv("NOGICOS_MODEL", "claude-sonnet-4-20250514"),
            claude_timeout_s=int(os.getenv("NOGICOS_CLAUDE_TIMEOUT", 60)),
            max_retries=int(os.getenv("NOGICOS_MAX_RETRIES", 3)),
            
            # 并发参数
            max_concurrent_tasks=int(os.getenv("NOGICOS_MAX_TASKS", 3)),
            max_api_concurrency=int(os.getenv("NOGICOS_MAX_API_CONCURRENCY", 2)),
            
            # 持久化
            db_path=os.getenv("NOGICOS_DB_PATH", "nogicos_tasks.db"),
            checkpoint_interval=int(os.getenv("NOGICOS_CHECKPOINT_INTERVAL", 5)),
            
            # 性能
            enable_performance_monitoring=os.getenv("NOGICOS_ENABLE_METRICS", "true").lower() == "true",
            
            # 功能开关
            enable_dual_agent=os.getenv("NOGICOS_DUAL_AGENT", "false").lower() == "true",
            enable_incremental_checkpoint=os.getenv("NOGICOS_INCREMENTAL_CHECKPOINT", "true").lower() == "true",
            enable_backpressure_bus=os.getenv("NOGICOS_BACKPRESSURE_BUS", "false").lower() == "true",
            enable_prompt_caching=os.getenv("NOGICOS_PROMPT_CACHING", "true").lower() == "true",
        )
    
    def validate(self) -> List[str]:
        """
        验证配置合法性
        
        Returns:
            错误消息列表，空列表表示验证通过
        """
        errors = []
        
        if self.max_iterations < 1:
            errors.append("max_iterations must be >= 1")
        
        if not (0 < self.context_compression_threshold < 1):
            errors.append("context_compression_threshold must be in (0, 1)")
        
        if self.max_concurrent_tasks < 1:
            errors.append("max_concurrent_tasks must be >= 1")
        
        if self.screenshot_delay_ms < 0:
            errors.append("screenshot_delay_ms must be >= 0")
        
        if self.claude_timeout_s < 1:
            errors.append("claude_timeout_s must be >= 1")
        
        if self.checkpoint_interval < 1:
            errors.append("checkpoint_interval must be >= 1")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "screenshot_delay_ms": self.screenshot_delay_ms,
            "context_compression_threshold": self.context_compression_threshold,
            "max_iterations": self.max_iterations,
            "iteration_timeout_s": self.iteration_timeout_s,
            "claude_model": self.claude_model,
            "claude_timeout_s": self.claude_timeout_s,
            "max_retries": self.max_retries,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "max_api_concurrency": self.max_api_concurrency,
            "db_path": self.db_path,
            "checkpoint_interval": self.checkpoint_interval,
            "enable_performance_monitoring": self.enable_performance_monitoring,
            "enable_dual_agent": self.enable_dual_agent,
            "enable_incremental_checkpoint": self.enable_incremental_checkpoint,
            "enable_backpressure_bus": self.enable_backpressure_bus,
            "enable_prompt_caching": self.enable_prompt_caching,
        }


# ========== 单例模式 ==========

_default_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    """获取默认配置（单例）"""
    global _default_config
    if _default_config is None:
        _default_config = AgentConfig.from_env()
        
        # 验证配置
        errors = _default_config.validate()
        if errors:
            logger.warning(f"Config validation warnings: {errors}")
    
    return _default_config


def set_config(config: AgentConfig):
    """设置默认配置（用于测试）"""
    global _default_config
    _default_config = config


def reload_config():
    """重新加载配置"""
    global _default_config
    _default_config = AgentConfig.from_env()
    logger.info("Config reloaded from environment")
