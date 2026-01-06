# -*- coding: utf-8 -*-
"""
Cursor vs NogicOS 对比测试

测试维度：
1. 响应速度 (Time to First Token)
2. 任务理解准确性
3. 工具调用合理性
4. 回复质量
"""

import asyncio
import httpx
import time
import json
import sys
import os

# 确保UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# 测试用例
TEST_CASES = [
    {
        "id": "simple_chat",
        "category": "简单对话",
        "prompt": "你好，介绍一下你自己",
        "expected_behavior": "简短自我介绍，不需要调用工具"
    },
    {
        "id": "file_list",
        "category": "文件操作",
        "prompt": "列出当前目录有什么文件",
        "expected_behavior": "调用 list_directory 工具，返回文件列表"
    },
    {
        "id": "file_read",
        "category": "文件读取",
        "prompt": "读取 README.md 的内容",
        "expected_behavior": "调用 read_file 工具，返回文件内容"
    },
    {
        "id": "web_search",
        "category": "网络搜索",
        "prompt": "搜索一下 Claude 3.5 的最新消息",
        "expected_behavior": "调用搜索工具，返回相关信息"
    },
    {
        "id": "multi_step",
        "category": "多步骤任务",
        "prompt": "帮我看看桌面有什么文件，然后告诉我最大的那个文件是什么",
        "expected_behavior": "先列出目录，分析文件大小，给出答案"
    },
    {
        "id": "ambiguous",
        "category": "模糊意图",
        "prompt": "帮我整理一下",
        "expected_behavior": "应该询问具体整理什么，或者做出合理假设"
    },
    {
        "id": "code_task",
        "category": "代码任务",
        "prompt": "帮我写一个 Python 函数，计算斐波那契数列",
        "expected_behavior": "直接给出代码，不需要过多解释"
    }
]


async def test_nogicos(prompt: str) -> dict:
    """测试 NogicOS 响应"""
    url = "http://localhost:8080/api/chat"
    
    start_time = time.time()
    first_token_time = None
    full_response = ""
    tool_calls = []
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                url,
                json={"text": prompt},
                headers={"Accept": "text/event-stream"}
            ) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    # 记录首 token 时间
                    if first_token_time is None and line:
                        first_token_time = time.time() - start_time
                    
                    # 解析 SSE 数据
                    if line.startswith("0:"):  # 文本内容
                        try:
                            text = json.loads(line[2:])
                            full_response += text
                        except:
                            pass
                    elif line.startswith("9:"):  # 工具调用
                        try:
                            tool_data = json.loads(line[2:])
                            tool_calls.append(tool_data)
                        except:
                            pass
        
        total_time = time.time() - start_time
        
        return {
            "success": True,
            "ttft": first_token_time,
            "total_time": total_time,
            "response": full_response[:500],  # 截断
            "tool_calls": tool_calls,
            "response_length": len(full_response)
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "ttft": None,
            "total_time": time.time() - start_time
        }


def print_result(test_case: dict, result: dict):
    """打印测试结果"""
    print(f"\n{'='*60}")
    print(f"测试: {test_case['category']} - {test_case['id']}")
    print(f"Prompt: {test_case['prompt']}")
    print(f"期望行为: {test_case['expected_behavior']}")
    print(f"-"*60)
    
    if result["success"]:
        print(f"TTFT: {result['ttft']:.2f}s" if result['ttft'] else "TTFT: N/A")
        print(f"总耗时: {result['total_time']:.2f}s")
        print(f"响应长度: {result['response_length']} 字符")
        
        if result.get("tool_calls"):
            print(f"工具调用: {len(result['tool_calls'])} 次")
            for tc in result["tool_calls"][:3]:  # 只显示前3个
                print(f"  - {tc.get('toolName', 'unknown')}")
        
        print(f"\n响应预览:")
        print(f"{result['response'][:300]}...")
    else:
        print(f"失败: {result.get('error', 'Unknown error')}")


async def run_comparison():
    """运行对比测试"""
    print("=" * 60)
    print("NogicOS 功能测试")
    print("=" * 60)
    
    # 先检查服务是否可用
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:8080/health")
            if resp.status_code != 200:
                print("NogicOS 服务未启动或不健康")
                return
    except:
        print("无法连接 NogicOS 服务 (localhost:8080)")
        print("请先启动: python hive_server.py")
        return
    
    print("NogicOS 服务已连接\n")
    
    results = []
    
    for test_case in TEST_CASES:
        print(f"\n正在测试: {test_case['id']}...")
        result = await test_nogicos(test_case["prompt"])
        results.append({
            "test_case": test_case,
            "result": result
        })
        print_result(test_case, result)
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r["result"]["success"])
    ttft_sum = sum(r["result"]["ttft"] for r in results if r["result"].get("ttft"))
    ttft_count = sum(1 for r in results if r["result"].get("ttft"))
    time_sum = sum(r["result"]["total_time"] for r in results if r["result"]["success"])

    avg_ttft = ttft_sum / ttft_count if ttft_count > 0 else 0
    avg_time = time_sum / success_count if success_count > 0 else 0
    
    print(f"成功率: {success_count}/{len(TEST_CASES)}")
    print(f"平均 TTFT: {avg_ttft:.2f}s")
    print(f"平均总耗时: {avg_time:.2f}s")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_comparison())


