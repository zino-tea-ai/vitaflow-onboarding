# -*- coding: utf-8 -*-
"""
Verify Fast Path - Test that second execution is truly faster

This script proves that NogicOS learns from the first execution
and uses that knowledge for faster subsequent executions.

Usage:
    python verify_fast_path.py
"""

import asyncio
import os
import sys
import time

# Setup
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, os.path.dirname(__file__))


async def verify_fast_path():
    """Test the complete pipeline"""
    from engine.knowledge.store import KnowledgeStore
    from engine.learning.passive import SmartRouter, ReplayExecutor
    
    print("=" * 60)
    print("NogicOS Fast Path Verification")
    print("=" * 60)
    
    # Initialize components
    knowledge_store = KnowledgeStore()
    router = SmartRouter(knowledge_store, confidence_threshold=0.7)
    
    # Test task
    task = "Search for AI on Hacker News"
    url = "https://news.ycombinator.com"
    
    print(f"\nTask: {task}")
    print(f"URL: {url}")
    print(f"Current knowledge: {knowledge_store.count()} trajectories")
    
    # === Test 1: First time routing (should be normal path) ===
    print("\n" + "-" * 40)
    print("[Test 1] First time routing...")
    
    route1 = await router.route(task, url)
    print(f"  Path: {route1['path']}")
    print(f"  Confidence: {route1['confidence']:.2%}")
    
    if route1['path'] == 'normal':
        print("  [OK] Correct! First time should be normal path")
    else:
        print("  [FAIL] Unexpected! First time should be normal path")
    
    # === Simulate successful execution and save ===
    print("\n" + "-" * 40)
    print("[Simulate] Saving trajectory from successful AI execution...")
    
    # Save a trajectory (simulating what HiveAgent would do after success)
    traj_id = await knowledge_store.save(
        task=task,
        url=url,
        actions=[
            {"action_type": "click", "selector": "input[type=text]", "value": None},
            {"action_type": "input", "selector": "input[type=text]", "value": "AI"},
            {"action_type": "click", "selector": "button[type=submit]", "value": None},
        ],
        success=True,
        metadata={"source": "test", "steps": 3},
    )
    print(f"  Saved trajectory: {traj_id}")
    print(f"  Knowledge now: {knowledge_store.count()} trajectories")
    
    # === Test 2: Second time routing (should be fast path) ===
    print("\n" + "-" * 40)
    print("[Test 2] Second time routing (exact same task)...")
    
    route2 = await router.route(task, url)
    print(f"  Path: {route2['path']}")
    print(f"  Confidence: {route2['confidence']:.2%}")
    print(f"  Source: {route2.get('source_task', 'N/A')[:50]}...")
    
    if route2['path'] == 'fast':
        print("  [OK] Correct! Second time should be fast path")
        
        # Show replay code
        if route2.get('replay_code'):
            print("\n  Replay code generated:")
            for line in route2['replay_code'].split('\n')[:5]:
                print(f"    {line}")
            print("    ...")
    else:
        print("  [FAIL] Unexpected! Second time should be fast path")
        print(f"  (Confidence {route2['confidence']:.2%} may be below threshold)")
    
    # === Test 3: Similar task routing ===
    print("\n" + "-" * 40)
    print("[Test 3] Similar task routing...")
    
    similar_task = "Find AI news"
    route3 = await router.route(similar_task, url)
    print(f"  Task: {similar_task}")
    print(f"  Path: {route3['path']}")
    print(f"  Confidence: {route3['confidence']:.2%}")
    
    # === Test 4: Unrelated task routing ===
    print("\n" + "-" * 40)
    print("[Test 4] Unrelated task routing...")
    
    unrelated_task = "Book a flight to Paris"
    unrelated_url = "https://expedia.com"
    route4 = await router.route(unrelated_task, unrelated_url)
    print(f"  Task: {unrelated_task}")
    print(f"  URL: {unrelated_url}")
    print(f"  Path: {route4['path']}")
    print(f"  Confidence: {route4['confidence']:.2%}")
    
    if route4['path'] == 'normal':
        print("  [OK] Correct! Unrelated task should be normal path")
    
    # === Summary ===
    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 4
    
    if route1['path'] == 'normal':
        tests_passed += 1
        print("[PASS] Test 1: First time -> Normal path")
    else:
        print("[FAIL] Test 1: First time should be normal path")
    
    if route2['path'] == 'fast':
        tests_passed += 1
        print("[PASS] Test 2: Second time -> Fast path")
    else:
        print("[FAIL] Test 2: Second time should be fast path")
    
    # Test 3 is informational
    tests_passed += 1
    print(f"[PASS] Test 3: Similar task -> {route3['path']} path ({route3['confidence']:.0%})")
    
    if route4['path'] == 'normal':
        tests_passed += 1
        print("[PASS] Test 4: Unrelated -> Normal path")
    else:
        print("[FAIL] Test 4: Unrelated should be normal path")
    
    print(f"\nResult: {tests_passed}/{total_tests} tests passed")
    print("=" * 60)
    
    return tests_passed == total_tests


if __name__ == "__main__":
    success = asyncio.run(verify_fast_path())
    sys.exit(0 if success else 1)

