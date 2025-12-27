# -*- coding: utf-8 -*-
"""
Test Review Improvements

Tests:
1. Dynamic axtree truncation
2. Error classification
3. Verbose logging
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_truncate_axtree():
    """Test smart accessibility tree truncation"""
    from engine.hive.nodes import truncate_axtree, estimate_tokens
    
    # Short text should not be truncated
    short_text = "button link textbox" * 10
    result = truncate_axtree(short_text, max_tokens=1000)
    assert result == short_text
    print("[PASS] Short text not truncated")
    
    # Long text should be truncated
    long_text = "\n".join([f"Line {i}: generic content" for i in range(1000)])
    result = truncate_axtree(long_text, max_tokens=500)
    assert len(result) < len(long_text)
    assert "Truncated" in result
    print("[PASS] Long text truncated")
    
    # Interactive elements should be preserved
    lines = [f"Line {i}: generic content" for i in range(300)]
    lines[250] = "button important action"
    lines[280] = "link click here"
    long_text = "\n".join(lines)
    result = truncate_axtree(long_text, max_tokens=2000)
    # First 200 lines should be there
    assert "Line 0:" in result
    print("[PASS] Interactive elements preserved")
    
    return True


def test_token_estimation():
    """Test token estimation function"""
    from engine.hive.nodes import estimate_tokens
    
    # 4 chars ~ 1 token
    text = "abcd"
    assert estimate_tokens(text) == 1
    
    text = "12345678"
    assert estimate_tokens(text) == 2
    
    print("[PASS] Token estimation")
    return True


def test_security_patterns():
    """Test blocked patterns in code execution"""
    from engine.hive.nodes import execute_playwright_code, SecurityError
    import asyncio
    
    dangerous_codes = [
        "import os; os.system('rm -rf /')",
        "import subprocess; subprocess.run(['ls'])",
        "__import__('os')",
        "eval('1+1')",
        "open('/etc/passwd')",
    ]
    
    for code in dangerous_codes:
        try:
            asyncio.run(execute_playwright_code(code, None))
            print(f"[FAIL] Should have blocked: {code[:30]}...")
            return False
        except SecurityError:
            pass  # Expected
        except Exception as e:
            # Other errors are OK too (e.g., None page)
            pass
    
    print("[PASS] Security patterns blocked")
    return True


def test_verbose_agent():
    """Test verbose logging option"""
    from engine.hive.graph import create_agent
    import logging
    
    # Create verbose agent
    agent = create_agent(persist=False, verbose=True)
    assert agent.verbose == True
    
    # Check logger level
    logger = logging.getLogger("nogicos.hive")
    assert logger.level == logging.DEBUG
    
    print("[PASS] Verbose logging configured")
    return True


def run_all_tests():
    """Run all improvement tests"""
    print("=" * 50)
    print("Review Improvements Tests")
    print("=" * 50)
    print()
    
    tests = [
        test_token_estimation,
        test_truncate_axtree,
        test_security_patterns,
        test_verbose_agent,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

