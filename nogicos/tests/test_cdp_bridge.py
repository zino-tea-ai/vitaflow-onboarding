# -*- coding: utf-8 -*-
"""
CDP Bridge 测试脚本

测试 Python → WebSocket → Electron → CDP 控制链路

运行方式：
1. 启动 NogicOS: cd nogicos/client && npm start
2. 运行测试: python tests/test_cdp_bridge.py
"""

import asyncio
import sys
import json
import uuid
import websockets
from pathlib import Path

# Windows 控制台 UTF-8 编码支持
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.browser.cdp_client import CDPClient, CDPError

WS_URL = "ws://localhost:8765"


async def test_cdp_bridge():
    """测试 CDP Bridge 功能"""
    print("=" * 50)
    print("CDP Bridge 测试")
    print("=" * 50)
    
    # 连接 WebSocket
    print("\n[1] 连接 WebSocket...")
    try:
        ws = await asyncio.wait_for(
            websockets.connect(WS_URL),
            timeout=5.0
        )
        print("    ✓ WebSocket 已连接")
    except Exception as e:
        print(f"    ✗ 连接失败: {e}")
        print("\n请确保 NogicOS 已启动：cd nogicos/client && npm start")
        return False
    
    # 创建 CDP 客户端
    cdp_client = CDPClient(
        ws_send=lambda msg: ws.send(json.dumps(msg))
    )
    
    # 等待 CDP Bridge 就绪
    print("\n[2] 等待 CDP Bridge 就绪...")
    
    # 监听消息
    ready_event = asyncio.Event()
    init_check_id = "init-check-" + str(uuid.uuid4())[:8]
    
    async def listen_messages():
        nonlocal init_check_id
        try:
            async for message in ws:
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "cdp_ready":
                    cdp_client.set_ready(True)
                    ready_event.set()
                    print("    ✓ CDP Bridge 已就绪 (收到 cdp_ready)")
                    
                elif msg_type == "cdp_response":
                    request_id = data.get("requestId")
                    
                    # 检查是否是我们的初始化检查响应
                    if request_id == init_check_id and not ready_event.is_set():
                        result = data.get("result")
                        error = data.get("error")
                        if result and not error:
                            cdp_client.set_ready(True)
                            ready_event.set()
                            print(f"    ✓ CDP Bridge 已就绪 (响应: {result})")
                        else:
                            print(f"    [!] 初始检查失败: {error}")
                    else:
                        # 转发给 cdp_client 处理
                        cdp_client.handle_response(data)
                    
                elif msg_type == "status":
                    # 忽略状态更新
                    pass
                    
                else:
                    pass  # 忽略其他消息
        except websockets.exceptions.ConnectionClosed:
            pass
    
    # 先启动消息监听
    listen_task = asyncio.create_task(listen_messages())
    
    # 等待一小段时间让监听器启动
    await asyncio.sleep(0.1)
    
    # 发送请求获取 CDP 状态（因为 cdp_ready 可能在我们连接前就发送了）
    await ws.send(json.dumps({
        "type": "cdp_command",
        "data": {
            "requestId": init_check_id,
            "method": "getURL",  # 尝试执行一个简单命令来验证 CDP 是否就绪
            "params": {},
        }
    }))
    
    # 等待就绪（最多 10 秒）
    try:
        await asyncio.wait_for(ready_event.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        print("    ✗ 超时：CDP Bridge 未就绪")
        print("    提示：请检查 Electron 控制台是否有错误")
        listen_task.cancel()
        await ws.close()
        return False
    
    # 测试 CDP 命令
    print("\n[3] 测试 CDP 命令...")
    
    test_results = []
    
    # 测试 1: 获取当前 URL
    print("\n    测试 3.1: 获取当前 URL")
    try:
        url = await cdp_client.get_url()
        print(f"    ✓ 当前 URL: {url[:50]}...")
        test_results.append(("get_url", True))
    except CDPError as e:
        print(f"    ✗ 失败: {e}")
        test_results.append(("get_url", False))
    
    # 测试 2: 获取页面标题
    print("\n    测试 3.2: 获取页面标题")
    try:
        title = await cdp_client.get_title()
        print(f"    ✓ 页面标题: {title}")
        test_results.append(("get_title", True))
    except CDPError as e:
        print(f"    ✗ 失败: {e}")
        test_results.append(("get_title", False))
    
    # 测试 3: 执行 JavaScript
    print("\n    测试 3.3: 执行 JavaScript")
    try:
        result = await cdp_client.evaluate("1 + 1")
        print(f"    ✓ 1 + 1 = {result}")
        test_results.append(("evaluate", result == 2))
    except CDPError as e:
        print(f"    ✗ 失败: {e}")
        test_results.append(("evaluate", False))
    
    # 测试 4: 截图
    print("\n    测试 3.4: 截取截图")
    try:
        screenshot = await cdp_client.screenshot({"format": "jpeg", "quality": 50})
        print(f"    ✓ 截图大小: {len(screenshot)} 字符 (base64)")
        test_results.append(("screenshot", len(screenshot) > 1000))
    except CDPError as e:
        print(f"    ✗ 失败: {e}")
        test_results.append(("screenshot", False))
    
    # 测试 5: 查询元素
    print("\n    测试 3.5: 查询元素 (body)")
    try:
        node_id = await cdp_client.query_selector("body")
        print(f"    ✓ body 节点 ID: {node_id}")
        test_results.append(("query_selector", node_id is not None))
    except CDPError as e:
        print(f"    ✗ 失败: {e}")
        test_results.append(("query_selector", False))
    
    # 清理
    listen_task.cancel()
    await ws.close()
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    
    passed = sum(1 for _, success in test_results if success)
    total = len(test_results)
    
    for name, success in test_results:
        status = "✓" if success else "✗"
        print(f"  {status} {name}")
    
    print(f"\n通过: {passed}/{total}")
    
    return passed == total


async def main():
    success = await test_cdp_bridge()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

