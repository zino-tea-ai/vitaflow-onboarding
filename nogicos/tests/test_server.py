# -*- coding: utf-8 -*-
"""
Test WebSocket Server

Tests:
1. Server startup
2. Status broadcasting
3. Client connection handling
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_status_dataclasses():
    """Test status dataclasses"""
    from engine.server.websocket import (
        AgentStatus, LearningStatus, KnowledgeStats, FullStatus
    )
    
    # AgentStatus
    agent = AgentStatus(state="thinking", task="Test", step=1)
    assert agent.state == "thinking"
    assert agent.task == "Test"
    
    # LearningStatus
    learning = LearningStatus(state="recording", action_count=5)
    assert learning.state == "recording"
    assert learning.action_count == 5
    
    # KnowledgeStats
    knowledge = KnowledgeStats(trajectory_count=10, domain_count=3)
    assert knowledge.trajectory_count == 10
    
    # FullStatus
    status = FullStatus(agent=agent, learning=learning, knowledge=knowledge)
    d = status.to_dict()
    assert d["type"] == "status"
    assert d["data"]["agent"]["state"] == "thinking"
    
    print("[PASS] Status dataclasses")
    return True


def test_server_instantiation():
    """Test server can be instantiated"""
    from engine.server.websocket import StatusServer, WEBSOCKETS_AVAILABLE
    
    if not WEBSOCKETS_AVAILABLE:
        print("[SKIP] websockets not installed")
        return True
    
    server = StatusServer(host="localhost", port=8765)
    assert server.host == "localhost"
    assert server.port == 8765
    assert server.client_count == 0
    assert not server.is_running
    
    print("[PASS] Server instantiation")
    return True


def test_status_updates():
    """Test status update methods"""
    from engine.server.websocket import StatusServer, WEBSOCKETS_AVAILABLE
    
    if not WEBSOCKETS_AVAILABLE:
        print("[SKIP] websockets not installed")
        return True
    
    server = StatusServer()
    
    # Update agent (max_steps first, then step for correct progress calculation)
    server.update_agent(state="thinking", task="Test task", max_steps=5)
    server.update_agent(step=2)
    assert server._agent_status.state == "thinking"
    assert server._agent_status.task == "Test task"
    assert server._agent_status.step == 2
    assert abs(server._agent_status.progress - 0.4) < 0.01  # Float comparison
    
    # Update learning
    server.update_learning(state="recording", action_count=10)
    assert server._learning_status.state == "recording"
    assert server._learning_status.action_count == 10
    
    # Update knowledge
    server.update_knowledge(trajectory_count=5, domains=["google.com"])
    assert server._knowledge_stats.trajectory_count == 5
    assert "google.com" in server._knowledge_stats.domains
    
    print("[PASS] Status updates")
    return True


async def test_server_lifecycle():
    """Test server start/stop"""
    from engine.server.websocket import StatusServer, WEBSOCKETS_AVAILABLE
    
    if not WEBSOCKETS_AVAILABLE:
        print("[SKIP] websockets not installed")
        return True
    
    server = StatusServer(host="localhost", port=18765)  # Use different port
    
    # Start
    success = await server.start()
    assert success == True
    assert server.is_running == True
    
    # Stop
    await server.stop()
    assert server.is_running == False
    
    print("[PASS] Server lifecycle")
    return True


async def test_client_connection():
    """Test client can connect and receive status"""
    from engine.server.websocket import StatusServer, WEBSOCKETS_AVAILABLE
    
    if not WEBSOCKETS_AVAILABLE:
        print("[SKIP] websockets not installed")
        return True
    
    import websockets
    
    server = StatusServer(host="localhost", port=18766)
    await server.start()
    
    try:
        # Connect client
        async with websockets.connect("ws://localhost:18766") as ws:
            # Should receive initial status
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            import json
            data = json.loads(msg)
            
            assert data["type"] == "status"
            assert "agent" in data["data"]
            assert "learning" in data["data"]
            assert "knowledge" in data["data"]
            
            # Test ping/pong
            await ws.send(json.dumps({"type": "ping"}))
            pong = await asyncio.wait_for(ws.recv(), timeout=2.0)
            assert json.loads(pong)["type"] == "pong"
        
        print("[PASS] Client connection")
        return True
        
    finally:
        await server.stop()


async def test_broadcast():
    """Test broadcasting to multiple clients"""
    from engine.server.websocket import StatusServer, WEBSOCKETS_AVAILABLE
    
    if not WEBSOCKETS_AVAILABLE:
        print("[SKIP] websockets not installed")
        return True
    
    import websockets
    import json
    
    server = StatusServer(host="localhost", port=18767)
    await server.start()
    
    try:
        # Connect two clients
        async with websockets.connect("ws://localhost:18767") as ws1:
            async with websockets.connect("ws://localhost:18767") as ws2:
                # Consume initial status messages
                await ws1.recv()
                await ws2.recv()
                
                # Update and broadcast
                server.update_agent(state="acting", task="Broadcast test")
                await server.broadcast_status()
                
                # Both should receive
                msg1 = await asyncio.wait_for(ws1.recv(), timeout=2.0)
                msg2 = await asyncio.wait_for(ws2.recv(), timeout=2.0)
                
                data1 = json.loads(msg1)
                data2 = json.loads(msg2)
                
                assert data1["data"]["agent"]["state"] == "acting"
                assert data2["data"]["agent"]["state"] == "acting"
        
        print("[PASS] Broadcast")
        return True
        
    finally:
        await server.stop()


def run_all_tests():
    """Run all server tests"""
    print("=" * 50)
    print("WebSocket Server Tests")
    print("=" * 50)
    print()
    
    # Sync tests
    sync_tests = [
        test_status_dataclasses,
        test_server_instantiation,
        test_status_updates,
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
            test_server_lifecycle,
            test_client_connection,
            test_broadcast,
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

