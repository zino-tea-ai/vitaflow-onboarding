# -*- coding: utf-8 -*-
"""
End-to-End Integration Tests

Tests the complete flow from task input to result output.
"""

import asyncio
import os
import sys
import tempfile
import pytest

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class TestEndToEnd:
    """End-to-end integration tests"""
    
    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Set up API keys"""
        try:
            from api_keys import setup_env
            setup_env()
        except ImportError:
            pytest.skip("api_keys.py not found")
    
    @pytest.mark.asyncio
    async def test_health_check_passes(self):
        """Health check should pass for all modules"""
        from health.checks import check_all
        
        results = await check_all()
        
        assert results["overall"] in ["healthy", "degraded"]
        assert "knowledge" in results["modules"]
        assert "browser" in results["modules"]
        assert "hive" in results["modules"]
    
    @pytest.mark.asyncio
    async def test_router_integration(self):
        """Router should integrate with knowledge store"""
        from router import Router
        from knowledge.store import KnowledgeStore
        from contracts.router_contract import RouterInput, RouteType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(data_dir=tmpdir)
            router = Router(knowledge=store)
            
            # Route a new task (should go to normal path)
            input = RouterInput(
                task="Search for AI on Hacker News",
                url="https://news.ycombinator.com"
            )
            
            result = await router.route(input)
            
            assert result.route_type == RouteType.NORMAL_PATH
            assert result.reasoning is not None
    
    @pytest.mark.asyncio
    async def test_browser_session_lifecycle(self):
        """Browser session should start and stop cleanly"""
        from browser.session import BrowserSession
        
        session = BrowserSession()
        
        try:
            await session.start(
                start_url="https://example.com",
                headless=True,
            )
            
            # Verify session is active
            assert session.active_page is not None
            assert session.playwright_browser is not None
            
            # Observe state
            state = await session.observe()
            assert state.url is not None
            assert state.screenshot is not None
            
        finally:
            await session.stop()
    
    @pytest.mark.asyncio 
    async def test_lm_initialization(self):
        """LM should initialize without errors"""
        from hive.lm import LM
        
        # Should not raise
        lm = LM("claude-opus-4-5-20251101")
        
        assert lm.model == "claude-opus-4-5-20251101"
        assert lm.is_anthropic()
    
    @pytest.mark.asyncio
    async def test_knowledge_save_and_search(self):
        """Knowledge store should save and retrieve trajectories"""
        from knowledge.store import KnowledgeStore
        from contracts.knowledge_contract import (
            KnowledgeSearchInput,
            KnowledgeSaveInput,
            TrajectoryStep,
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(data_dir=tmpdir)
            
            # Save a trajectory
            await store.save(KnowledgeSaveInput(
                task="Click the search button",
                url="https://example.com",
                trajectory=[
                    TrajectoryStep(
                        action_type="click",
                        selector="button.search"
                    )
                ],
                success=True,
                duration_ms=1500.0,
            ))
            
            # Search for it
            result = await store.search(KnowledgeSearchInput(
                task="Click the search button",
                threshold=0.5,
            ))
            
            assert result.matched is True
            assert result.trajectory is not None


def run_tests():
    """Run integration tests"""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_tests()

