#!/usr/bin/env python3
"""
通过 WebSocket 客户端发送可视化事件到前端
连接到已运行的 hive_server.py
"""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("请安装 websockets: pip install websockets")
    sys.exit(1)


async def send_event(ws, event_type: str, data: dict = None):
    """发送一个事件"""
    msg = {"type": event_type}
    if data:
        msg["data"] = data
    await ws.send(json.dumps(msg))
    print(f"  → 发送: {event_type}")


async def run_demo():
    uri = "ws://localhost:8765"
    
    print("=" * 50)
    print("NogicOS 可视化演示")
    print("=" * 50)
    print(f"\n连接到 {uri}...")
    
    try:
        async with websockets.connect(uri) as ws:
            print("已连接!\n")
            
            # 等待初始状态消息
            init_msg = await asyncio.wait_for(ws.recv(), timeout=2)
            print(f"收到初始状态: {json.loads(init_msg).get('type', 'unknown')}")
            
            print("\n" + "-" * 40)
            print("开始演示 - 观察右侧可视化面板")
            print("-" * 40 + "\n")
            
            # Demo 1: 任务开始
            print("[1] 任务开始")
            await send_event(ws, "task_start", {"max_steps": 4, "url": "https://nogicos.ai/demo"})
            await asyncio.sleep(1)
            
            # Demo 2: 步骤 1 - 移动光标
            print("[2] 步骤 1: 移动光标")
            await send_event(ws, "step_start", {"step": 0})
            await send_event(ws, "screen_glow", {"intensity": "medium"})
            await send_event(ws, "cursor_move", {"x": 80, "y": 100, "duration": 0.6})
            await asyncio.sleep(0.8)
            await send_event(ws, "highlight", {"rect": {"x": 60, "y": 80, "width": 100, "height": 50}, "label": "目标元素"})
            await asyncio.sleep(1)
            await send_event(ws, "step_complete", {"step": 0, "success": True})
            await asyncio.sleep(0.5)
            
            # Demo 3: 步骤 2 - 点击
            print("[3] 步骤 2: 点击")
            await send_event(ws, "step_start", {"step": 1})
            await send_event(ws, "cursor_move", {"x": 110, "y": 105, "duration": 0.4})
            await asyncio.sleep(0.5)
            await send_event(ws, "cursor_click")
            await asyncio.sleep(0.5)
            await send_event(ws, "highlight_hide")
            await send_event(ws, "step_complete", {"step": 1, "success": True})
            await asyncio.sleep(0.5)
            
            # Demo 4: 步骤 3 - 输入
            print("[4] 步骤 3: 输入")
            await send_event(ws, "step_start", {"step": 2})
            await send_event(ws, "cursor_move", {"x": 180, "y": 180, "duration": 0.5})
            await asyncio.sleep(0.6)
            await send_event(ws, "highlight", {"rect": {"x": 130, "y": 160, "width": 150, "height": 40}, "label": "输入框"})
            await asyncio.sleep(0.3)
            await send_event(ws, "cursor_click")
            await asyncio.sleep(0.3)
            await send_event(ws, "cursor_type")
            await asyncio.sleep(2)
            await send_event(ws, "cursor_stop_type")
            await send_event(ws, "highlight_hide")
            await send_event(ws, "step_complete", {"step": 2, "success": True})
            await asyncio.sleep(0.5)
            
            # Demo 5: 步骤 4 - 确认
            print("[5] 步骤 4: 确认")
            await send_event(ws, "step_start", {"step": 3})
            await send_event(ws, "cursor_move", {"x": 160, "y": 280, "duration": 0.5})
            await asyncio.sleep(0.6)
            await send_event(ws, "highlight", {"rect": {"x": 135, "y": 265, "width": 85, "height": 35}, "label": "确认按钮"})
            await asyncio.sleep(0.3)
            await send_event(ws, "cursor_click")
            await asyncio.sleep(0.5)
            await send_event(ws, "highlight_hide")
            await send_event(ws, "step_complete", {"step": 3, "success": True})
            await asyncio.sleep(0.5)
            
            # Demo 6: 任务完成
            print("[6] 任务完成")
            await send_event(ws, "task_complete")
            await asyncio.sleep(2)
            await send_event(ws, "screen_glow_stop")
            
            print("\n" + "=" * 50)
            print("演示完成!")
            print("=" * 50)
            
    except ConnectionRefusedError:
        print("无法连接到服务器。请确保 hive_server.py 正在运行。")
    except asyncio.TimeoutError:
        print("连接超时")
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    asyncio.run(run_demo())

