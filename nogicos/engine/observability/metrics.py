"""
NogicOS 性能指标收集
====================

用于 SLO 监控和告警。

指标类型:
1. 延迟分布 (Histogram) - 计算分位数
2. 计数器 (Counter) - 累计统计
3. 仪表盘 (Gauge) - 瞬时值

参考:
- Prometheus 指标模型
- OpenTelemetry Metrics
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from collections import deque
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""
    HISTOGRAM = "histogram"
    COUNTER = "counter"
    GAUGE = "gauge"


@dataclass
class LatencyHistogram:
    """
    延迟直方图 - 计算分位数
    
    使用滑动窗口保存最近 N 个样本
    """
    
    name: str
    window_size: int = 100  # 滑动窗口大小
    _samples: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def __post_init__(self):
        self._samples = deque(maxlen=self.window_size)
    
    def record(self, duration_ms: float):
        """记录一个延迟样本"""
        self._samples.append(duration_ms)
    
    def percentile(self, p: float) -> float:
        """
        计算分位数
        
        Args:
            p: 分位数 (0-100)，如 50 表示 P50
            
        Returns:
            分位数值
        """
        if not self._samples:
            return 0
        sorted_samples = sorted(self._samples)
        idx = int(len(sorted_samples) * p / 100)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def p50(self) -> float:
        """P50 (中位数)"""
        return self.percentile(50)
    
    @property
    def p90(self) -> float:
        """P90"""
        return self.percentile(90)
    
    @property
    def p99(self) -> float:
        """P99"""
        return self.percentile(99)
    
    @property
    def avg(self) -> float:
        """平均值"""
        return sum(self._samples) / len(self._samples) if self._samples else 0
    
    @property
    def min(self) -> float:
        """最小值"""
        return min(self._samples) if self._samples else 0
    
    @property
    def max(self) -> float:
        """最大值"""
        return max(self._samples) if self._samples else 0
    
    @property
    def count(self) -> int:
        """样本数量"""
        return len(self._samples)
    
    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "name": self.name,
            "count": self.count,
            "p50": self.p50,
            "p90": self.p90,
            "p99": self.p99,
            "avg": self.avg,
            "min": self.min,
            "max": self.max,
        }


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


class PerformanceMetrics:
    """
    性能指标收集器
    
    使用示例:
    ```python
    metrics = get_metrics()
    
    # 记录工具调用延迟
    with metrics.measure_latency("tool", "window_click"):
        await execute_tool(...)
    
    # 或者使用异步上下文
    async with metrics.measure_latency("llm", "claude_call"):
        response = await call_claude(...)
    
    # 检查 SLO
    violations = metrics.check_slo(slo_config)
    ```
    """
    
    def __init__(self):
        # 延迟指标
        self._tool_latencies: Dict[str, LatencyHistogram] = {}
        self._llm_latency = LatencyHistogram("llm_response")
        self._screenshot_latency = LatencyHistogram("screenshot")
        
        # 计数器
        self._tool_calls = 0
        self._tool_errors = 0
        self._tool_retries = 0
        self._tasks_completed = 0
        self._tasks_failed = 0
        
        # 事件总线统计
        self._events_processed = 0
        self._events_dropped = 0
        
        # 资源使用
        self._peak_memory_mb = 0
        self._current_memory_mb = 0
        
        # 迭代统计
        self._total_iterations = 0
        
        # SLO 违规回调
        self._slo_violation_callbacks: List[Callable] = []
        
        # 启动时间
        self._start_time = time.time()
    
    def measure_latency(self, category: str, name: str) -> "LatencyMeasurer":
        """
        创建延迟测量上下文管理器
        
        Args:
            category: 分类 ("tool", "llm", "screenshot")
            name: 具体名称
            
        Returns:
            上下文管理器
        """
        return LatencyMeasurer(self, category, name)
    
    def record_tool_call(
        self, 
        tool_name: str, 
        duration_ms: float, 
        success: bool, 
        retried: bool = False
    ):
        """
        记录工具调用
        
        Args:
            tool_name: 工具名称
            duration_ms: 执行时间 (ms)
            success: 是否成功
            retried: 是否重试过
        """
        # 延迟
        if tool_name not in self._tool_latencies:
            self._tool_latencies[tool_name] = LatencyHistogram(f"tool_{tool_name}")
        self._tool_latencies[tool_name].record(duration_ms)
        
        # 计数
        self._tool_calls += 1
        if not success:
            self._tool_errors += 1
        if retried:
            self._tool_retries += 1
    
    def record_llm_call(self, duration_ms: float):
        """记录 LLM 调用"""
        self._llm_latency.record(duration_ms)
    
    def record_screenshot(self, duration_ms: float):
        """记录截图操作"""
        self._screenshot_latency.record(duration_ms)
    
    def record_task_result(self, success: bool):
        """记录任务结果"""
        if success:
            self._tasks_completed += 1
        else:
            self._tasks_failed += 1
    
    def record_iteration(self):
        """记录一次迭代"""
        self._total_iterations += 1
    
    def record_event_stats(self, processed: int, dropped: int):
        """记录事件统计"""
        self._events_processed = processed
        self._events_dropped = dropped
    
    def record_memory_usage(self, memory_mb: float):
        """记录内存使用"""
        self._current_memory_mb = memory_mb
        self._peak_memory_mb = max(self._peak_memory_mb, memory_mb)
    
    def check_slo(self, slo: PerformanceSLO) -> Dict[str, bool]:
        """
        检查 SLO 是否满足
        
        Args:
            slo: SLO 配置
            
        Returns:
            Dict[metric_name, is_passing]
        """
        results = {}
        
        # 延迟 SLO
        for tool_name, hist in self._tool_latencies.items():
            if hist.count > 0:
                results[f"{tool_name}_p50"] = hist.p50 <= slo.tool_execution_p50_ms
                results[f"{tool_name}_p99"] = hist.p99 <= slo.tool_execution_p99_ms
        
        if self._llm_latency.count > 0:
            results["llm_p50"] = self._llm_latency.p50 <= slo.llm_response_p50_ms
            results["llm_p99"] = self._llm_latency.p99 <= slo.llm_response_p99_ms
        
        if self._screenshot_latency.count > 0:
            results["screenshot"] = self._screenshot_latency.p50 <= slo.screenshot_capture_ms
        
        # 可靠性 SLO
        total_tasks = self._tasks_completed + self._tasks_failed
        if total_tasks > 0:
            success_rate = self._tasks_completed / total_tasks
            results["task_success_rate"] = success_rate >= slo.task_success_rate
        
        if self._tool_calls > 0:
            retry_rate = self._tool_retries / self._tool_calls
            results["tool_retry_rate"] = retry_rate <= slo.tool_retry_rate
        
        # 事件丢弃率
        total_events = self._events_processed + self._events_dropped
        if total_events > 0:
            drop_rate = self._events_dropped / total_events
            results["event_drop_rate"] = drop_rate <= slo.event_drop_rate
        
        # 资源 SLO
        results["memory_usage"] = self._current_memory_mb <= slo.max_memory_mb
        
        # 检查违规并回调
        violations = [k for k, v in results.items() if not v]
        if violations:
            for callback in self._slo_violation_callbacks:
                try:
                    callback(violations)
                except Exception as e:
                    logger.error(f"SLO violation callback error: {e}")
        
        return results
    
    def on_slo_violation(self, callback: Callable[[List[str]], None]):
        """注册 SLO 违规回调"""
        self._slo_violation_callbacks.append(callback)
    
    def get_summary(self) -> dict:
        """获取指标摘要"""
        uptime = time.time() - self._start_time
        
        return {
            "uptime_seconds": uptime,
            "tool_calls": self._tool_calls,
            "tool_errors": self._tool_errors,
            "tool_error_rate": self._tool_errors / max(1, self._tool_calls),
            "tool_retries": self._tool_retries,
            "tool_retry_rate": self._tool_retries / max(1, self._tool_calls),
            "tasks_completed": self._tasks_completed,
            "tasks_failed": self._tasks_failed,
            "task_success_rate": self._tasks_completed / max(1, self._tasks_completed + self._tasks_failed),
            "total_iterations": self._total_iterations,
            "llm_latency": self._llm_latency.to_dict(),
            "screenshot_latency": self._screenshot_latency.to_dict(),
            "tool_latencies": {
                name: h.to_dict()
                for name, h in self._tool_latencies.items()
            },
            "events_processed": self._events_processed,
            "events_dropped": self._events_dropped,
            "current_memory_mb": self._current_memory_mb,
            "peak_memory_mb": self._peak_memory_mb,
        }
    
    def reset(self):
        """重置所有指标"""
        self._tool_latencies.clear()
        self._llm_latency = LatencyHistogram("llm_response")
        self._screenshot_latency = LatencyHistogram("screenshot")
        self._tool_calls = 0
        self._tool_errors = 0
        self._tool_retries = 0
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._events_processed = 0
        self._events_dropped = 0
        self._total_iterations = 0
        self._start_time = time.time()


class LatencyMeasurer:
    """
    延迟测量上下文管理器
    
    支持同步和异步使用
    """
    
    def __init__(self, metrics: PerformanceMetrics, category: str, name: str):
        self.metrics = metrics
        self.category = category
        self.name = name
        self.start_time: Optional[float] = None
        self.duration_ms: float = 0
    
    def __enter__(self) -> "LatencyMeasurer":
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        self._record(exc_type is None)
    
    async def __aenter__(self) -> "LatencyMeasurer":
        self.start_time = time.perf_counter()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        self._record(exc_type is None)
    
    def _record(self, success: bool):
        """记录测量结果"""
        if self.category == "tool":
            self.metrics.record_tool_call(self.name, self.duration_ms, success)
        elif self.category == "llm":
            self.metrics.record_llm_call(self.duration_ms)
        elif self.category == "screenshot":
            self.metrics.record_screenshot(self.duration_ms)


# ========== 单例模式 ==========

_metrics_instance: Optional[PerformanceMetrics] = None


def get_metrics() -> PerformanceMetrics:
    """获取全局指标实例（单例）"""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = PerformanceMetrics()
    return _metrics_instance


def set_metrics(metrics: PerformanceMetrics):
    """设置全局指标实例（用于测试）"""
    global _metrics_instance
    _metrics_instance = metrics
