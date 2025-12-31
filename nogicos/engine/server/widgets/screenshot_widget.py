"""
Screenshot Widget - 截图显示

显示操作后页面截图的 Widget，支持：
- Base64 或 URL 图片
- 标题和描述
- 高亮区域标记
"""

from __future__ import annotations
from typing import Optional, Dict, Any


def build_screenshot_widget(
    image_data: str,
    title: str = "操作完成",
    description: str = "",
    highlight: Optional[Dict[str, int]] = None,
    is_base64: bool = True,
) -> dict:
    """
    构建截图 Widget。
    
    Args:
        image_data: 图片数据（Base64 或 URL）
        title: 标题
        description: 描述文本
        highlight: 高亮区域 {"x": int, "y": int, "width": int, "height": int}
        is_base64: 是否为 Base64 编码
        
    Returns:
        Widget 数据结构
    """
    # 构建图片 URL
    if is_base64:
        image_url = f"data:image/png;base64,{image_data}"
    else:
        image_url = image_data
    
    widget_data = {
        "type": "nogicos_screenshot",
        "data": {
            "image_url": image_url,
            "title": title,
            "description": description,
        }
    }
    
    # 添加高亮区域
    if highlight:
        widget_data["data"]["highlight"] = highlight
    
    return widget_data


def format_screenshot_markdown(
    image_url: str,
    title: str = "截图",
    description: str = "",
) -> str:
    """
    格式化截图为 Markdown（用于纯文本响应）。
    
    Note: Base64 图片在 Markdown 中显示效果较差，
    建议使用 URL 或 Widget 渲染。
    """
    lines = [f"**{title}**"]
    
    if description:
        lines.append(description)
    
    # 如果不是 base64，可以显示图片链接
    if not image_url.startswith("data:"):
        lines.append(f"![{title}]({image_url})")
    else:
        lines.append("_(截图已附加)_")
    
    return "\n".join(lines)


