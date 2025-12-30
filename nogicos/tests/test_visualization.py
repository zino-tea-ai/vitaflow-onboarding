#!/usr/bin/env python3
"""
测试可视化面板的动画效果
运行：python test_visualization.py
确保前端开发服务器已运行
"""

import asyncio
import random
from engine.server.websocket import get_server, start_server


async def demo_cursor_animation():
    """演示光标移动动画"""
    server = get_server()
    
    print("[Demo] 光标移动动画")
    
    # 移动到几个随机位置
    positions = [
        (60, 80),    # 左上区域
        (200, 150),  # 中间
        (150, 280),  # 底部按钮区域
        (280, 100),  # 右侧
    ]
    
    for x, y in positions:
        await server.viz_cursor_move(x, y, duration=0.6)
        await asyncio.sleep(0.8)
    
    print("[Demo] 光标移动完成")


async def demo_click_animation():
    """演示点击动画"""
    server = get_server()
    
    print("[Demo] 点击动画")
    
    # 移动到目标并点击
    await server.viz_cursor_move(160, 320, duration=0.5)
    await asyncio.sleep(0.6)
    await server.viz_cursor_click()
    await asyncio.sleep(0.5)
    
    print("[Demo] 点击完成")


async def demo_typing_animation():
    """演示输入动画"""
    server = get_server()
    
    print("[Demo] 输入动画")
    
    # 移动到输入框并开始输入
    await server.viz_cursor_move(200, 200, duration=0.5)
    await asyncio.sleep(0.6)
    await server.viz_cursor_click()
    await asyncio.sleep(0.3)
    await server.viz_cursor_type()
    await asyncio.sleep(3)  # 模拟输入 3 秒
    await server.viz_cursor_stop_type()
    
    print("[Demo] 输入完成")


async def demo_highlight_animation():
    """演示元素高亮"""
    server = get_server()
    
    print("[Demo] 元素高亮")
    
    # 高亮一个模拟按钮
    await server.viz_highlight(138, 310, 85, 40, label="提交按钮")
    await asyncio.sleep(2)
    await server.viz_highlight_hide()
    
    print("[Demo] 高亮完成")


async def demo_glow_states():
    """演示屏幕光效状态"""
    server = get_server()
    
    print("[Demo] 屏幕光效")
    
    states = ["low", "medium", "high", "success", "error", "off"]
    
    for state in states:
        print(f"  光效: {state}")
        await server.viz_screen_glow(state)
        await asyncio.sleep(1)
    
    await server.viz_screen_glow_stop()
    print("[Demo] 光效完成")


async def demo_task_flow():
    """演示完整任务流程"""
    server = get_server()
    
    print("[Demo] 完整任务流程")
    
    # 1. 任务开始
    print("  [1/6] 任务开始")
    await server.viz_task_start(max_steps=4, url="https://nogicos.ai/demo")
    await asyncio.sleep(0.5)
    
    # 2. 步骤 1：移动光标
    print("  [2/6] 步骤 1 开始")
    await server.viz_step_start(0)
    await server.viz_screen_glow("medium")
    await server.viz_cursor_move(80, 120, duration=0.5)
    await asyncio.sleep(0.7)
    await server.viz_highlight(60, 100, 100, 50, label="目标元素")
    await asyncio.sleep(0.5)
    await server.viz_step_complete(0, success=True)
    
    # 3. 步骤 2：点击
    print("  [3/6] 步骤 2 开始")
    await server.viz_step_start(1)
    await server.viz_cursor_move(110, 125, duration=0.4)
    await asyncio.sleep(0.5)
    await server.viz_cursor_click()
    await asyncio.sleep(0.5)
    await server.viz_highlight_hide()
    await server.viz_step_complete(1, success=True)
    
    # 4. 步骤 3：输入
    print("  [4/6] 步骤 3 开始")
    await server.viz_step_start(2)
    await server.viz_cursor_move(180, 220, duration=0.5)
    await asyncio.sleep(0.6)
    await server.viz_highlight(130, 200, 150, 40, label="输入框")
    await asyncio.sleep(0.3)
    await server.viz_cursor_click()
    await asyncio.sleep(0.3)
    await server.viz_cursor_type()
    await asyncio.sleep(2)
    await server.viz_cursor_stop_type()
    await server.viz_highlight_hide()
    await server.viz_step_complete(2, success=True)
    
    # 5. 步骤 4：完成
    print("  [5/6] 步骤 4 开始")
    await server.viz_step_start(3)
    await server.viz_cursor_move(160, 320, duration=0.5)
    await asyncio.sleep(0.6)
    await server.viz_highlight(135, 305, 85, 35, label="确认")
    await asyncio.sleep(0.3)
    await server.viz_cursor_click()
    await asyncio.sleep(0.5)
    await server.viz_highlight_hide()
    await server.viz_step_complete(3, success=True)
    
    # 6. 任务完成
    print("  [6/6] 任务完成")
    await server.viz_task_complete()
    await asyncio.sleep(2)
    await server.viz_screen_glow_stop()
    
    print("[Demo] 任务流程完成")


async def main():
    """主函数：启动服务器并运行演示"""
    print("=" * 50)
    print("NogicOS 可视化面板测试")
    print("=" * 50)
    print()
    print("确保前端开发服务器已运行:")
    print("  cd nogicos/nogicos-ui && npm run dev")
    print()
    print("然后访问前端页面观看动画效果")
    print()
    
    # 启动 WebSocket 服务器
    server = await start_server()
    print(f"WebSocket 服务器运行在 ws://{server.host}:{server.port}")
    
    # 等待客户端连接
    print("\n等待前端连接...")
    
    for i in range(30):  # 最多等待 30 秒
        await asyncio.sleep(1)
        if server.client_count > 0:
            print(f"已连接 {server.client_count} 个客户端")
            break
    else:
        print("没有客户端连接，退出")
        await server.stop()
        return
    
    # 运行演示
    print("\n" + "=" * 50)
    print("开始演示")
    print("=" * 50)
    
    demos = [
        ("光标移动", demo_cursor_animation),
        ("点击效果", demo_click_animation),
        ("输入效果", demo_typing_animation),
        ("元素高亮", demo_highlight_animation),
        ("屏幕光效", demo_glow_states),
        ("完整流程", demo_task_flow),
    ]
    
    for i, (name, demo_fn) in enumerate(demos, 1):
        print(f"\n--- 演示 {i}/{len(demos)}: {name} ---")
        await demo_fn()
        await asyncio.sleep(1)
    
    print("\n" + "=" * 50)
    print("所有演示完成!")
    print("=" * 50)
    
    # 保持服务器运行
    print("\n按 Ctrl+C 退出...")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n正在关闭...")
    finally:
        await server.stop()
        print("完成")


if __name__ == "__main__":
    asyncio.run(main())

