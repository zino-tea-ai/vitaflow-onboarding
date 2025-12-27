# -*- coding: utf-8 -*-
"""
Quick Test - Verify NogicOS installation
"""

import asyncio
import os
import sys

# Ensure UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# Load API keys
try:
    from api_keys import setup_env
    setup_env()
except ImportError:
    print("[Warning] api_keys.py not found")


async def main():
    print("=" * 60)
    print("NogicOS Quick Test")
    print("=" * 60)
    
    # Test 1: Import all modules
    print("\n[1] Testing imports...")
    try:
        from engine.hive.graph import create_agent, HiveAgent
        from engine.hive.state import AgentState, create_initial_state
        from engine.browser.session import BrowserSession, create_browser
        from engine.browser.cdp import CDPBrowser
        from engine.browser.recorder import Recorder, RecordedTrajectory
        from engine.knowledge.store import KnowledgeStore
        from engine.learning.passive import PassiveLearningSystem, SmartRouter
        from engine.server.websocket import StatusServer, get_server
        # Removed: engine.router (replaced by SmartRouter)
        from engine.contracts import AgentInput, BrowserInput
        from engine.observability import setup_logging, get_logger
        from engine.health import HealthChecker
        print("    [OK] All imports successful")
    except ImportError as e:
        print(f"    [FAIL] Import error: {e}")
        return False
    
    # Test 2: Health check
    print("\n[2] Running health checks...")
    try:
        from engine.health import check_all
        results = await check_all()
        
        overall = results["overall"]
        print(f"    Overall: {overall}")
        
        for module, data in results["modules"].items():
            status = data["status"]
            icon = "OK" if status == "healthy" else "WARN" if status == "degraded" else "FAIL"
            print(f"    [{icon}] {module}: {status}")
            if data.get("error"):
                print(f"         Error: {data['error']}")
    except Exception as e:
        print(f"    [FAIL] Health check error: {e}")
        return False
    
    # Test 3: Knowledge store
    print("\n[3] Testing knowledge store...")
    try:
        store = KnowledgeStore()
        result = await store.search("test task")
        print(f"    [OK] Knowledge store working (count: {store.count()})")
    except Exception as e:
        print(f"    [FAIL] Knowledge store error: {e}")
        return False
    
    # Test 4: SmartRouter (replaced old Router)
    print("\n[4] Testing SmartRouter...")
    try:
        store = KnowledgeStore()
        smart_router = SmartRouter(store)
        result = await smart_router.route("Search for AI", "https://example.com")
        print(f"    [OK] SmartRouter working (path: {result.path})")
    except Exception as e:
        print(f"    [FAIL] SmartRouter error: {e}")
        return False
    
    # Test 5: Agent graph
    print("\n[5] Testing agent graph...")
    try:
        agent = create_agent()
        nodes = list(agent.graph.nodes.keys())
        print(f"    [OK] Agent graph compiled (nodes: {nodes})")
    except Exception as e:
        print(f"    [FAIL] Agent error: {e}")
        return False
    
    # Test 6: Passive learning
    print("\n[6] Testing passive learning...")
    try:
        from engine.learning.passive import SmartRouter
        from engine.knowledge.store import KnowledgeStore
        
        store = KnowledgeStore()
        router = SmartRouter(store)
        result = await router.route("test task", "https://example.com")
        print(f"    [OK] SmartRouter working (path: {result['path']})")
    except Exception as e:
        print(f"    [FAIL] Passive learning error: {e}")
        return False
    
    # Test 7: WebSocket server
    print("\n[7] Testing WebSocket server...")
    try:
        from engine.server.websocket import StatusServer, WEBSOCKETS_AVAILABLE
        
        if WEBSOCKETS_AVAILABLE:
            server = StatusServer(port=18888)
            await server.start()
            server.update_agent(state="idle", task="Quick test")
            await server.stop()
            print(f"    [OK] WebSocket server working")
        else:
            print(f"    [WARN] websockets not installed, skipping")
    except Exception as e:
        print(f"    [FAIL] WebSocket server error: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("All tests passed! NogicOS is ready.")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run: python -m engine.health")
    print("  2. Run: python tests/test_agent_basic.py")
    print("  3. Run: python tests/test_passive_learning.py")
    print()
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
