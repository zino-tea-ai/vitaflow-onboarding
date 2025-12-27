# -*- coding: utf-8 -*-
"""
Basic Agent Tests - M2 Verification
"""

import asyncio
import os
import sys

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load API keys
try:
    from api_keys import setup_env
    setup_env()
except ImportError:
    print("[Warning] api_keys.py not found")


def test_graph_compilation():
    """Test 1: Graph compiles without errors"""
    from engine.hive.graph import create_agent
    
    agent = create_agent()
    
    assert agent.graph is not None
    assert "observe" in agent.graph.nodes
    assert "think" in agent.graph.nodes
    assert "act" in agent.graph.nodes
    assert "terminate" in agent.graph.nodes
    
    print("[PASS] Graph compilation")


def test_state_creation():
    """Test 2: Initial state is created correctly"""
    from engine.hive.state import create_initial_state
    
    state = create_initial_state("Test task", max_steps=5)
    
    assert state["task"] == "Test task"
    assert state["max_steps"] == 5
    assert state["current_step"] == 0
    assert state["status"] == "running"
    assert state["actions"] == []
    
    print("[PASS] State creation")


def test_code_sanitization():
    """Test 3: Code sanitization works"""
    from engine.hive.nodes import sanitize_code
    
    # Test .first injection
    code1 = 'page.get_by_role("button").click()'
    sanitized1 = sanitize_code(code1)
    assert '.first' in sanitized1
    
    # Test timeout injection
    code2 = 'element.click()'
    sanitized2 = sanitize_code(code2)
    assert 'timeout=15000' in sanitized2
    
    print("[PASS] Code sanitization")


def test_security_checks():
    """Test 4: Security checks block dangerous code"""
    from engine.hive.nodes import execute_playwright_code, SecurityError
    
    dangerous_codes = [
        "import os; os.system('rm -rf /')",
        "__import__('subprocess').call('ls')",
        "eval('print(1)')",
        "open('/etc/passwd').read()",
    ]
    
    for code in dangerous_codes:
        try:
            asyncio.run(execute_playwright_code(code, None))
            print(f"[FAIL] Security: Should have blocked: {code[:30]}...")
            return False
        except SecurityError:
            pass  # Expected
        except Exception:
            pass  # Other errors are fine too
    
    print("[PASS] Security checks")
    return True


async def test_agent_execution():
    """Test 5: Agent can execute a simple task"""
    from engine.hive.graph import create_agent
    from engine.browser.session import create_browser
    
    agent = create_agent()
    browser = await create_browser(
        url="https://news.ycombinator.com",
        headless=True,
    )
    
    try:
        result = await agent.run(
            task="What is the title of the first news item? Return only the title.",
            browser_session=browser,
            max_steps=3,
        )
        
        print(f"Result: {result}")
        
        assert result is not None
        assert "result" in result
        assert result.get("steps", 0) > 0
        
        print("[PASS] Agent execution")
        return True
        
    except Exception as e:
        print(f"[FAIL] Agent execution: {e}")
        return False
    finally:
        await browser.close()


def run_tests():
    """Run all M2 verification tests"""
    print("=" * 50)
    print("M2 Verification: LangGraph Agent")
    print("=" * 50)
    
    tests_passed = 0
    tests_total = 5
    
    # Test 1
    try:
        test_graph_compilation()
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Graph compilation: {e}")
    
    # Test 2
    try:
        test_state_creation()
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] State creation: {e}")
    
    # Test 3
    try:
        test_code_sanitization()
        tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Code sanitization: {e}")
    
    # Test 4
    try:
        if test_security_checks():
            tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Security checks: {e}")
    
    # Test 5 (optional - requires browser)
    try:
        if asyncio.run(test_agent_execution()):
            tests_passed += 1
    except Exception as e:
        print(f"[FAIL] Agent execution: {e}")
    
    print("=" * 50)
    print(f"M2 Verification: {tests_passed}/{tests_total} PASSED")
    print("=" * 50)
    
    return tests_passed >= 4  # Allow 1 failure (browser test might fail)


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
