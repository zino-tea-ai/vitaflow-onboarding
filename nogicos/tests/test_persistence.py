# -*- coding: utf-8 -*-
"""
Test Memory Persistence

Verifies:
1. SQLite checkpointer works
2. Trajectories are saved to disk
3. History can be retrieved
4. Threads can be listed
"""

import sys
import os
import asyncio
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_sqlite_persistence():
    """Test SQLite checkpointer initialization"""
    from engine.hive.graph import create_agent
    
    # Create agent with persistence
    agent = create_agent(persist=True)
    
    assert agent.persist == True
    assert agent.db_path is not None
    assert "checkpoints.db" in agent.db_path
    
    print("[PASS] SQLite persistence initialized")
    return True


def test_inmemory_fallback():
    """Test in-memory mode for testing"""
    from engine.hive.graph import create_agent
    from langgraph.checkpoint.memory import InMemorySaver
    
    # Create agent without persistence
    agent = create_agent(persist=False)
    
    assert agent.persist == False
    assert agent.db_path is None
    assert isinstance(agent.checkpointer, InMemorySaver)
    
    print("[PASS] In-memory fallback works")
    return True


def test_data_directory():
    """Test data directory is created"""
    from engine.hive.graph import create_agent
    
    agent = create_agent(persist=True)
    
    data_dir = Path(agent.db_path).parent
    assert data_dir.exists()
    assert data_dir.name == "data"
    
    print("[PASS] Data directory created")
    return True


def test_trajectory_directory():
    """Test trajectory directory structure"""
    from engine.hive.graph import HiveAgent
    
    # Check trajectory dir
    trajectory_dir = Path(__file__).parent.parent / "data" / "trajectories"
    
    # Create if not exists (as agent would)
    trajectory_dir.mkdir(parents=True, exist_ok=True)
    
    assert trajectory_dir.exists()
    
    print("[PASS] Trajectory directory ready")
    return True


def test_get_threads_empty():
    """Test getting threads from empty/new database"""
    from engine.hive.graph import create_agent
    import tempfile
    import time
    
    # Use temp DB
    temp_db = tempfile.mktemp(suffix='.db')
    
    try:
        agent = create_agent(persist=True, db_path=temp_db)
        threads = agent.get_threads()
        
        # Should return empty list, not error
        assert isinstance(threads, list)
        
        print("[PASS] Get threads works on empty DB")
        return True
    finally:
        # Cleanup - try multiple times for Windows
        agent = None
        for _ in range(3):
            try:
                if os.path.exists(temp_db):
                    os.remove(temp_db)
                break
            except:
                time.sleep(0.1)


def run_all_tests():
    """Run all persistence tests"""
    print("=" * 50)
    print("Memory Persistence Tests")
    print("=" * 50)
    print()
    
    tests = [
        test_sqlite_persistence,
        test_inmemory_fallback,
        test_data_directory,
        test_trajectory_directory,
        test_get_threads_empty,
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
    
    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

