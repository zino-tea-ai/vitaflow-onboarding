# -*- coding: utf-8 -*-
"""
Test Passive Learning System

Tests:
1. Recorder functionality
2. KnowledgeStore with semantic search
3. SmartRouter decisions
4. Full integration
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_recorded_action():
    """Test RecordedAction dataclass"""
    from engine.browser.recorder import RecordedAction
    import time
    
    action = RecordedAction(
        timestamp=time.time(),
        action_type="click",
        url="https://example.com",
        selector="#button",
        coordinates={"x": 100, "y": 200},
    )
    
    # Test to_dict
    d = action.to_dict()
    assert d["action_type"] == "click"
    assert d["selector"] == "#button"
    
    # Test to_playwright_code
    code = action.to_playwright_code()
    assert 'page.click("#button"' in code
    
    print("[PASS] RecordedAction")
    return True


def test_recorded_trajectory():
    """Test RecordedTrajectory dataclass"""
    from engine.browser.recorder import RecordedAction, RecordedTrajectory
    import time
    
    actions = [
        RecordedAction(time.time(), "navigate", "https://example.com"),
        RecordedAction(time.time(), "click", "https://example.com", selector="#login"),
        RecordedAction(time.time(), "input", "https://example.com", selector="#user", value="test"),
    ]
    
    trajectory = RecordedTrajectory(
        task="Login to site",
        start_url="https://example.com",
        end_url="https://example.com/dashboard",
        actions=actions,
        start_time=time.time() - 10,
        end_time=time.time(),
    )
    
    # Test to_dict
    d = trajectory.to_dict()
    assert d["task"] == "Login to site"
    assert len(d["actions"]) == 3
    
    # Test to_playwright_script
    script = trajectory.to_playwright_script()
    assert "async def replay(page):" in script
    assert 'page.goto("https://example.com")' in script
    
    print("[PASS] RecordedTrajectory")
    return True


async def test_knowledge_store():
    """Test KnowledgeStore save and search"""
    from engine.knowledge.store import KnowledgeStore
    import tempfile
    import shutil
    
    # Use temp directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        store = KnowledgeStore(data_dir=temp_dir)
        
        # Save trajectory
        traj_id = await store.save(
            task="Login to Hacker News",
            url="https://news.ycombinator.com",
            actions=[
                {"action_type": "click", "selector": "a.login"},
                {"action_type": "input", "selector": "#username", "value": "test"},
            ],
            success=True,
        )
        
        assert traj_id is not None
        assert store.count() == 1
        
        # Search exact match
        result = await store.search("Login to Hacker News", "https://news.ycombinator.com")
        assert result.matched == True
        assert result.confidence >= 0.5
        
        # Search similar
        result = await store.search("Sign in to HN", "https://news.ycombinator.com")
        assert result.confidence > 0  # Should have some match
        
        # Search unrelated
        result = await store.search("Book flight", "https://expedia.com")
        assert result.confidence < 0.5
        
        print("[PASS] KnowledgeStore")
        return True
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_smart_router():
    """Test SmartRouter routing decisions"""
    from engine.learning.passive import SmartRouter
    from engine.knowledge.store import KnowledgeStore
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        store = KnowledgeStore(data_dir=temp_dir)
        router = SmartRouter(store, confidence_threshold=0.6)
        
        # Save a high-quality trajectory
        await store.save(
            task="Search for Python tutorials",
            url="https://google.com",
            actions=[
                {"action_type": "input", "selector": "input[name=q]", "value": "Python tutorials"},
                {"action_type": "click", "selector": "button[type=submit]"},
            ],
            success=True,
        )
        
        # Route exact match → should be fast path
        result = await router.route("Search for Python tutorials", "https://google.com")
        assert result["path"] == "fast" or result["confidence"] >= 0.6
        
        # Route different task → should be normal path
        result = await router.route("Check weather forecast", "https://weather.com")
        assert result["path"] == "normal"
        
        print("[PASS] SmartRouter")
        return True
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_replay_executor():
    """Test ReplayExecutor code execution"""
    from engine.learning.passive import ReplayExecutor
    
    # Create mock page
    class MockPage:
        def __init__(self):
            self.actions = []
        
        async def goto(self, url):
            self.actions.append(("goto", url))
        
        async def click(self, selector, timeout=None):
            self.actions.append(("click", selector))
        
        async def fill(self, selector, value, timeout=None):
            self.actions.append(("fill", selector, value))
    
    page = MockPage()
    executor = ReplayExecutor(page)
    
    # Test simple replay
    code = '''
async def replay(page):
    await page.goto("https://example.com")
    await page.click("#button", timeout=15000)
    return True
'''
    
    result = await executor.execute(code)
    assert result["success"] == True
    assert len(page.actions) == 2
    
    print("[PASS] ReplayExecutor")
    return True


def run_all_tests():
    """Run all passive learning tests"""
    print("=" * 50)
    print("Passive Learning Tests")
    print("=" * 50)
    print()
    
    # Sync tests
    sync_tests = [
        test_recorded_action,
        test_recorded_trajectory,
    ]
    
    passed = 0
    failed = 0
    
    for test in sync_tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # Async tests
    async def run_async_tests():
        nonlocal passed, failed
        
        async_tests = [
            test_knowledge_store,
            test_smart_router,
            test_replay_executor,
        ]
        
        for test in async_tests:
            try:
                if await test():
                    passed += 1
            except Exception as e:
                print(f"[FAIL] {test.__name__}: {e}")
                import traceback
                traceback.print_exc()
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

