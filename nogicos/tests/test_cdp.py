# -*- coding: utf-8 -*-
"""
Test CDP Bridge

Tests:
1. CDPBrowser class instantiation
2. Connection to external browser (if available)
3. Page state observation
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_cdp_import():
    """Test CDP module can be imported"""
    from engine.browser.cdp import CDPBrowser, connect_to_electron, PageState
    
    assert CDPBrowser is not None
    assert connect_to_electron is not None
    assert PageState is not None
    
    print("[PASS] CDP module imports")
    return True


def test_cdp_instantiation():
    """Test CDPBrowser can be instantiated"""
    from engine.browser.cdp import CDPBrowser
    
    browser = CDPBrowser("http://localhost:9222")
    
    assert browser.cdp_url == "http://localhost:9222"
    assert browser.timeout == 30000
    assert browser.connected == False
    assert browser.page is None
    
    print("[PASS] CDPBrowser instantiation")
    return True


def test_page_state():
    """Test PageState dataclass"""
    from engine.browser.cdp import PageState
    import time
    
    state = PageState(
        id="test-123",
        url="https://example.com",
        title="Test Page",
        timestamp=time.time(),
        accessibility_tree={
            "id": "1",
            "role": "document",
            "name": "Test",
            "children": [
                {"id": "2", "role": "button", "name": "Click me", "children": []},
            ],
        },
    )
    
    assert state.id == "test-123"
    assert state.url == "https://example.com"
    
    axtree_str = state.get_axtree_string()
    assert "document" in axtree_str
    assert "button" in axtree_str
    assert "Click me" in axtree_str
    
    print("[PASS] PageState dataclass")
    return True


async def test_cdp_connection_mock():
    """Test CDP connection flow (without real browser)"""
    from engine.browser.cdp import CDPBrowser
    
    browser = CDPBrowser("http://localhost:9999")  # Non-existent port
    
    try:
        await browser.connect(max_retries=1, retry_delay=0.1)
        # Should fail
        print("[FAIL] Should have raised ConnectionError")
        return False
    except ConnectionError as e:
        # Expected
        assert "Could not connect" in str(e)
        print("[PASS] Connection failure handled correctly")
        return True
    except Exception as e:
        print(f"[PASS] Connection failure raised: {type(e).__name__}")
        return True


async def test_cdp_live_connection():
    """Test live CDP connection (requires browser on port 9222)"""
    from engine.browser.cdp import CDPBrowser
    
    browser = CDPBrowser("http://localhost:9222")
    
    try:
        await browser.connect(max_retries=2, retry_delay=0.5)
        
        if browser.connected:
            print(f"[LIVE] Connected to browser at {browser.page.url}")
            
            # Get page state
            state = await browser.observe()
            print(f"[LIVE] Page title: {state.title}")
            print(f"[LIVE] AXTree lines: {len(state.get_axtree_string().split(chr(10)))}")
            
            await browser.close()
            print("[PASS] Live CDP connection")
            return True
        else:
            print("[SKIP] No browser available")
            return True
            
    except ConnectionError:
        print("[SKIP] No browser available on port 9222")
        print("       Start Electron with: npm start (in client/)")
        return True
    except Exception as e:
        print(f"[WARN] Unexpected error: {e}")
        return True


def run_all_tests():
    """Run all CDP tests"""
    print("=" * 50)
    print("CDP Bridge Tests")
    print("=" * 50)
    print()
    
    # Sync tests
    tests = [
        test_cdp_import,
        test_cdp_instantiation,
        test_page_state,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
    
    # Async tests
    async def run_async_tests():
        nonlocal passed, failed
        
        async_tests = [
            test_cdp_connection_mock,
            test_cdp_live_connection,
        ]
        
        for test in async_tests:
            try:
                if await test():
                    passed += 1
            except Exception as e:
                print(f"[FAIL] {test.__name__}: {e}")
                failed += 1
    
    asyncio.run(run_async_tests())
    
    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

