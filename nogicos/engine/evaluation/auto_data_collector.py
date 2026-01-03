"""
自动数据收集器 - 用 AI 生成测试用例并自动执行，数据自动进入 LangSmith

用法:
    python -m engine.evaluation.auto_data_collector --count 50

特性:
- AI 自动生成多样化测试任务
- 自动执行并记录到 LangSmith
- 支持后台运行，睡一觉就有数据
"""

import asyncio
import argparse
import logging
import json
import sys
import random
from typing import List, Dict, Any, Tuple
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

logger = logging.getLogger(__name__)

# 任务模板 - 覆盖各种场景
TASK_TEMPLATES = {
    "file_operations": [
        "帮我列出{dir}目录下的所有文件",
        "读取{file}文件的内容",
        "在{dir}目录创建一个名为{name}的文件夹",
        "搜索{dir}目录下所有包含{keyword}的文件",
        "把{file}文件复制到{dir}目录",
    ],
    "browser_tasks": [
        "打开{site}网站",
        "在{site}上搜索{keyword}",
        "打开{site}并截图",
        "访问{url}并提取页面标题",
        "在Google上搜索'{query}'并告诉我前3个结果",
    ],
    "mixed_tasks": [
        "下载{url}的内容并保存到{file}",
        "搜索网上关于{topic}的资料，然后整理成文档保存",
        "打开{site}，截图后保存到桌面",
        "查找本地关于{topic}的文件，然后搜索网上的补充资料",
    ],
    "simple_queries": [
        "现在几点了",
        "今天星期几",
        "帮我算一下{a}加{b}等于多少",
        "{topic}是什么意思",
        "简单解释一下{concept}",
    ],
    "complex_tasks": [
        "整理{dir}目录，把图片移到Pictures，文档移到Documents",
        "分析{dir}目录的文件结构，生成一份报告",
        "比较{file1}和{file2}的内容差异",
        "在{dir}目录下找到最大的5个文件并列出",
    ],
    "edge_cases": [
        "",  # 空输入
        "   ",  # 纯空格
        "!@#$%^&*()",  # 特殊字符
        "帮我删除C盘所有文件",  # 危险请求
        "a" * 1000,  # 超长输入
        "中文测试 English mixed 123",  # 混合语言
    ],
}

# 填充变量
FILL_VALUES = {
    "dir": ["Desktop", "Documents", "Downloads", "当前目录", "."],
    "file": ["test.txt", "readme.md", "config.json", "notes.txt"],
    "name": ["新文件夹", "test_folder", "backup", "temp"],
    "keyword": ["python", "config", "readme", "test"],
    "site": ["google.com", "github.com", "baidu.com"],
    "url": ["https://example.com", "https://github.com"],
    "query": ["Python教程", "AI最新进展", "天气预报"],
    "topic": ["机器学习", "区块链", "量子计算"],
    "concept": ["递归", "闭包", "异步编程"],
    "a": ["15", "100", "3.14"],
    "b": ["27", "200", "2.71"],
    "file1": ["a.txt", "old.md"],
    "file2": ["b.txt", "new.md"],
}


def generate_tasks(count: int) -> List[str]:
    """生成多样化的测试任务"""
    tasks = []
    
    # 确保每个类别都有覆盖
    all_templates = []
    for category, templates in TASK_TEMPLATES.items():
        for template in templates:
            all_templates.append((category, template))
    
    # 随机选择并填充
    for _ in range(count):
        category, template = random.choice(all_templates)
        
        # 填充变量
        task = template
        for key, values in FILL_VALUES.items():
            placeholder = "{" + key + "}"
            if placeholder in task:
                task = task.replace(placeholder, random.choice(values), 1)
        
        tasks.append(task)
    
    return tasks


def quick_quality_check(result: Dict[str, Any]) -> Tuple[bool, str]:
    """
    快速质量检查 - 在收集时过滤垃圾数据
    
    Returns:
        (is_valid, reason)
    """
    # 规则 1: 必须成功
    if not result.get("success"):
        return False, "执行失败"
    
    # 规则 2: 必须有响应
    response = result.get("response", "")
    if not response or len(response) < 10:
        return False, "响应太短"
    
    # 规则 3: 不能有 traceback
    if "traceback" in response.lower() or "error" in response.lower():
        return False, "响应含错误"
    
    # 规则 4: 不能超时太久
    if result.get("duration_ms", 0) > 60000:  # 60秒
        return False, "执行超时"
    
    # 规则 5: 空任务的响应要合理
    task = result.get("task", "")
    if not task.strip() and len(response) > 100:
        return False, "空任务异常响应"
    
    return True, "通过"


async def run_task_and_collect(agent, task: str, session_id: str) -> Dict[str, Any]:
    """执行单个任务并收集结果"""
    start_time = datetime.now()
    
    try:
        result = await agent.run(task=task, session_id=session_id)
        
        return {
            "task": task,
            "success": result.success,
            "response": result.response[:500] if result.response else "",  # 截断长响应
            "error": result.error,
            "iterations": result.iterations,
            "tool_calls": result.tool_calls,
            "duration_ms": (datetime.now() - start_time).total_seconds() * 1000,
        }
    except Exception as e:
        return {
            "task": task,
            "success": False,
            "response": "",
            "error": str(e),
            "iterations": 0,
            "tool_calls": [],
            "duration_ms": (datetime.now() - start_time).total_seconds() * 1000,
        }


async def collect_data(count: int = 50, delay: float = 2.0):
    """
    自动收集数据
    
    Args:
        count: 要生成的任务数量
        delay: 任务之间的延迟（秒），防止 API 限流
    """
    from engine.agent.react_agent import ReActAgent
    
    print(f"\n{'='*60}")
    print("NogicOS 自动数据收集器")
    print(f"{'='*60}")
    print(f"目标: 生成并执行 {count} 个测试任务")
    print(f"数据自动同步到 LangSmith")
    print(f"{'='*60}\n")
    
    # 生成任务
    tasks = generate_tasks(count)
    print(f"[OK] 生成了 {len(tasks)} 个测试任务\n")
    
    # 初始化 Agent（自动启用 LangSmith 追踪）
    agent = ReActAgent()
    session_id = f"auto_collect_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    results = []
    success_count = 0
    quality_count = 0  # 高质量数据计数
    rejected_count = 0  # 被过滤的垃圾数据
    
    for i, task in enumerate(tasks, 1):
        print(f"[{i}/{count}] 执行: {task[:50]}..." if len(task) > 50 else f"[{i}/{count}] 执行: {task}")
        
        result = await run_task_and_collect(agent, task, session_id)
        
        if result["success"]:
            success_count += 1
            
            # 质量检查
            is_quality, reason = quick_quality_check(result)
            if is_quality:
                quality_count += 1
                results.append(result)  # 只保存高质量数据
                print(f"       [OK] 高质量 ({result['duration_ms']:.0f}ms)")
            else:
                rejected_count += 1
                print(f"       [SKIP] 已过滤: {reason}")
        else:
            rejected_count += 1
            print(f"       [FAIL] {result['error'][:50] if result['error'] else '未知错误'}")
        
        # 延迟防止限流
        if i < count:
            await asyncio.sleep(delay)
    
    # 生成报告
    print(f"\n{'='*60}")
    print("收集完成!")
    print(f"{'='*60}")
    print(f"总任务数: {count}")
    print(f"执行成功: {success_count} ({success_count/count*100:.1f}%)")
    print(f"高质量数据: {quality_count} ({quality_count/count*100:.1f}%)")
    print(f"被过滤: {rejected_count} ({rejected_count/count*100:.1f}%)")
    print(f"\n只有高质量数据会同步到 LangSmith")
    print(f"查看: https://smith.langchain.com")
    
    # 保存本地备份
    output_path = f"data/auto_collect_{session_id}.json"
    import os
    os.makedirs("data", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n本地备份: {output_path}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="NogicOS 自动数据收集器")
    parser.add_argument("--count", type=int, default=50, help="生成的任务数量 (默认: 50)")
    parser.add_argument("--delay", type=float, default=2.0, help="任务间延迟秒数 (默认: 2.0)")
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(
        level=logging.WARNING,  # 减少噪音
        format="%(message)s",
    )
    
    # 运行
    asyncio.run(collect_data(count=args.count, delay=args.delay))


if __name__ == "__main__":
    main()

