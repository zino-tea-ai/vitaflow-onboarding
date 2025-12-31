"""
Tool Card Widget - 工具执行卡片

显示工具执行状态的 Widget，支持：
- 工具名称和参数
- 执行状态（executing, success, error）
- 执行结果或错误信息
- 执行时间
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class ToolCardState:
    """工具卡片状态"""
    tool_id: str
    tool_name: str
    args: Dict[str, Any]
    status: str = "executing"  # executing, success, error
    result: Optional[str] = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration_ms(self) -> Optional[int]:
        """计算执行时长（毫秒）"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() * 1000)
        return None
    
    @property
    def status_icon(self) -> str:
        """状态图标"""
        return {
            "executing": "⏳",
            "success": "✓",
            "error": "✗",
        }.get(self.status, "•")
    
    @property
    def display_name(self) -> str:
        """工具显示名称（中文化）"""
        name_map = {
            "navigate": "导航到网页",
            "click": "点击元素",
            "type_text": "输入文本",
            "screenshot": "截取屏幕",
            "list_directory": "列出目录",
            "move_file": "移动文件",
            "create_directory": "创建文件夹",
            "delete_file": "删除文件",
            "read_file": "读取文件",
            "write_file": "写入文件",
        }
        return name_map.get(self.tool_name, self.tool_name)


def build_tool_card_widget(state: ToolCardState) -> dict:
    """
    构建工具卡片 Widget。
    
    返回格式：
    {
        "type": "nogicos_tool_card",
        "data": {
            "tool_id": "abc123",
            "tool_name": "navigate",
            "display_name": "导航到网页",
            "args": {"url": "https://..."},
            "status": "success",
            "status_icon": "✓",
            "result": "导航成功",
            "error": null,
            "duration_ms": 1234
        }
    }
    """
    return {
        "type": "nogicos_tool_card",
        "data": {
            "tool_id": state.tool_id,
            "tool_name": state.tool_name,
            "display_name": state.display_name,
            "args": state.args,
            "status": state.status,
            "status_icon": state.status_icon,
            "result": state.result,
            "error": state.error,
            "duration_ms": state.duration_ms,
        }
    }


def format_tool_text(state: ToolCardState) -> str:
    """
    格式化工具执行为文本（用于纯文本响应）。
    
    Example:
        ✓ 导航到网页 (234ms)
          url: https://taobao.com
          结果: 导航成功
    """
    lines = []
    
    # 状态行
    duration_str = f" ({state.duration_ms}ms)" if state.duration_ms else ""
    lines.append(f"{state.status_icon} {state.display_name}{duration_str}")
    
    # 参数（简化显示）
    if state.args:
        for key, value in list(state.args.items())[:3]:  # 最多3个参数
            value_str = str(value)[:50]  # 截断长值
            lines.append(f"  {key}: {value_str}")
    
    # 结果或错误
    if state.status == "success" and state.result:
        result_preview = state.result[:100] if len(state.result) > 100 else state.result
        lines.append(f"  结果: {result_preview}")
    elif state.status == "error" and state.error:
        lines.append(f"  错误: {state.error}")
    
    return "\n".join(lines)


