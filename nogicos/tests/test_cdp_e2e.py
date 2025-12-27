# -*- coding: utf-8 -*-
"""
CDP 模式端到端测试

测试 use_cdp=True 时的任务执行流程

运行方式：
1. 启动 NogicOS: cd nogicos/client && npm start
2. 运行测试: python tests/test_cdp_e2e.py
"""

import asyncio
import sys
import json
import aiohttp
from pathlib import Path

# Windows 控制台 UTF-8 编码支持
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

HTTP_URL = "http://localhost:8080"


async def test_cdp_mode():
    """测试 CDP 模式的任务执行"""
    print("=" * 50)
    print("CDP 模式端到端测试")
    print("=" * 50)
    
    # 检查服务器是否运行
    print("\n[1] 检查服务器状态...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{HTTP_URL}/health", timeout=5) as resp:
                if resp.status != 200:
                    print(f"    ✗ 服务器未响应 (status: {resp.status})")
                    return False
                print("    ✓ 服务器运行中")
        except Exception as e:
            print(f"    ✗ 无法连接服务器: {e}")
            print("\n请确保 NogicOS 已启动：cd nogicos/client && npm start")
            return False
    
    # 测试 CDP 模式执行
    print("\n[2] 执行 CDP 模式任务...")
    
    task_request = {
        "task": "Find the page title",  # 简单任务
        "url": "https://news.ycombinator.com",
        "max_steps": 3,
        "headless": True,
        "use_cdp": True,  # 启用 CDP 模式
    }
    
    print(f"    任务: {task_request['task']}")
    print(f"    URL: {task_request['url']}")
    print(f"    CDP 模式: {task_request['use_cdp']}")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{HTTP_URL}/execute",
                json=task_request,
                timeout=120,  # 2 分钟超时
            ) as resp:
                result = await resp.json()
                
                print(f"\n[3] 执行结果:")
                print(f"    成功: {result.get('success')}")
                print(f"    路径: {result.get('path')}")
                print(f"    步数: {result.get('steps')}")
                print(f"    耗时: {result.get('time_seconds', 0):.2f}s")
                
                if result.get("result"):
                    print(f"    结果: {result.get('result')[:100]}...")
                
                if result.get("error"):
                    print(f"    错误: {result.get('error')}")
                
                return result.get("success", False)
                
        except asyncio.TimeoutError:
            print("    ✗ 请求超时")
            return False
        except Exception as e:
            print(f"    ✗ 请求失败: {e}")
            return False


async def main():
    success = await test_cdp_mode()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ CDP 模式测试通过")
    else:
        print("✗ CDP 模式测试失败")
    print("=" * 50)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())



