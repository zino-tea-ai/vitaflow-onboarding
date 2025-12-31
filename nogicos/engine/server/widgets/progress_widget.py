"""
Progress Widget - 任务进度显示

显示任务执行进度的 Widget，支持：
- 当前步骤/总步骤
- 进度百分比
- 状态描述
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

# ChatKit widget imports
try:
    from chatkit.widgets import WidgetRoot
    CHATKIT_WIDGETS_AVAILABLE = True
except ImportError:
    CHATKIT_WIDGETS_AVAILABLE = False
    WidgetRoot = dict  # Fallback


@dataclass
class ProgressState:
    """进度状态"""
    current_step: int
    total_steps: int
    status: str = "active"  # active, completed, error
    description: str = ""
    
    @property
    def percentage(self) -> int:
        """计算进度百分比"""
        if self.total_steps == 0:
            return 0
        return min(100, int((self.current_step / self.total_steps) * 100))
    
    @property
    def progress_bar(self) -> str:
        """生成 ASCII 进度条"""
        filled = int(self.percentage / 10)
        empty = 10 - filled
        return "█" * filled + "░" * empty


def build_progress_widget(state: ProgressState) -> dict:
    """
    构建进度 Widget。
    
    由于 ChatKit Widget 模板系统较复杂，
    这里使用简化的 JSON 结构返回进度信息，
    前端可以根据此结构渲染自定义 UI。
    
    返回格式：
    {
        "type": "nogicos_progress",
        "data": {
            "current": 2,
            "total": 4,
            "percentage": 50,
            "status": "active",
            "description": "正在执行...",
            "progress_bar": "█████░░░░░"
        }
    }
    """
    return {
        "type": "nogicos_progress",
        "data": {
            "current": state.current_step,
            "total": state.total_steps,
            "percentage": state.percentage,
            "status": state.status,
            "description": state.description,
            "progress_bar": state.progress_bar,
        }
    }


def format_progress_text(state: ProgressState) -> str:
    """
    格式化进度文本（用于纯文本响应）。
    
    Example:
        [█████░░░░░] 50% | 步骤 2/4: 正在输入搜索词
    """
    status_icon = {
        "active": "⏳",
        "completed": "✓",
        "error": "✗",
    }.get(state.status, "•")
    
    return (
        f"{status_icon} [{state.progress_bar}] {state.percentage}% | "
        f"步骤 {state.current_step}/{state.total_steps}"
        + (f": {state.description}" if state.description else "")
    )


