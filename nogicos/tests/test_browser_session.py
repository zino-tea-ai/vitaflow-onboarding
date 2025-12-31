# -*- coding: utf-8 -*-
"""
Browser Session Diagnostic Test

Verify:
1. Playwright availability
2. BrowserSession startup
3. Registry context injection
4. Browser Tools session access
"""

import asyncio
import sys
import os

# Fix Windows encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_browser_session():
    print("=" * 60)
    print("Browser Session 诊断测试")
    print("=" * 60)
    
    # Test 1: Playwright 可用性
    print("\n[Test 1] Playwright 可用性")
    try:
        from playwright.async_api import async_playwright
        print("  [OK] Playwright 已安装")
    except ImportError as e:
        print(f"  [FAIL] Playwright 未安装: {e}")
        print("  运行: pip install playwright && playwright install chromium")
        return False
    
    # Test 2: BrowserSession 模块导入
    print("\n[Test 2] BrowserSession 模块导入")
    try:
        from engine.browser import (
            BrowserSession,
            get_browser_session,
            close_browser_session,
            PLAYWRIGHT_AVAILABLE
        )
        print(f"  [OK] 导入成功")
        print(f"  PLAYWRIGHT_AVAILABLE = {PLAYWRIGHT_AVAILABLE}")
    except ImportError as e:
        print(f"  [FAIL] 导入失败: {e}")
        return False
    
    # Test 3: BrowserSession 启动
    print("\n[Test 3] BrowserSession 启动")
    session = BrowserSession(headless=True)
    started = await session.start()
    if started:
        print("  [OK] Session 启动成功")
        print(f"  is_started = {session.is_started}")
    else:
        print("  [FAIL] Session 启动失败")
        return False
    
    # Test 4: 导航测试
    print("\n[Test 4] 导航测试")
    try:
        navigated = await session.navigate("https://example.com", timeout=10.0)
        if navigated:
            title = await session.get_title()
            url = await session.get_current_url()
            print(f"  [OK] 导航成功")
            print(f"  URL: {url}")
            print(f"  Title: {title}")
        else:
            print("  [FAIL] 导航失败")
    except Exception as e:
        print(f"  [FAIL] 导航异常: {e}")
    
    # Test 5: 内容提取
    print("\n[Test 5] 内容提取")
    try:
        content = await session.get_page_content()
        print(f"  [OK] 提取成功")
        print(f"  内容长度: {len(content)} 字符")
        print(f"  前 100 字符: {content[:100]}...")
    except Exception as e:
        print(f"  [FAIL] 提取失败: {e}")
    
    # Test 6: Registry Context 测试
    print("\n[Test 6] Registry Context 注入测试")
    try:
        from engine.tools import create_full_registry
        
        registry = create_full_registry()
        print(f"  创建 Registry, 工具数量: {len(registry.get_all())}")
        
        # 注入 session
        registry.set_context("browser_session", session)
        
        # 验证获取
        ctx_session = registry.get_context("browser_session")
        if ctx_session is session:
            print("  [OK] Context 注入成功")
        else:
            print(f"  [FAIL] Context 注入失败: got {ctx_session}")
    except Exception as e:
        print(f"  [FAIL] Registry 测试失败: {e}")
    
    # Test 7: Browser Tool 调用测试
    print("\n[Test 7] Browser Tool 调用测试")
    try:
        result = await registry.execute("browser_get_url", {})
        if result.success:
            print(f"  [OK] 工具调用成功")
            print(f"  结果: {result.output}")
        else:
            print(f"  [FAIL] 工具调用失败: {result.error}")
    except Exception as e:
        print(f"  [FAIL] 工具调用异常: {e}")
    
    # Cleanup
    print("\n[Cleanup] 关闭 Session")
    await session.stop()
    print("  [OK] Session 已关闭")
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    asyncio.run(test_browser_session())

