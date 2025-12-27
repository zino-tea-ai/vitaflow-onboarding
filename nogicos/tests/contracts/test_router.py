# -*- coding: utf-8 -*-
"""
Router Module Contract Tests

Verifies the router follows its defined contract.
"""

import asyncio
import os
import sys
import tempfile
import pytest

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from contracts.router_contract import RouterInput, RouterOutput, RouteType
from contracts.knowledge_contract import KnowledgeSaveInput, TrajectoryStep
from knowledge.store import KnowledgeStore
from router import Router


class TestRouterContract:
    """Test router contract compliance"""
    
    @pytest.fixture
    def temp_router(self):
        """Create router with temporary knowledge store"""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(data_dir=tmpdir)
            router = Router(knowledge=store)
            yield router, store
    
    @pytest.mark.asyncio
    async def test_route_returns_valid_output(self, temp_router):
        """Route should return valid RouterOutput"""
        router, _ = temp_router
        
        input = RouterInput(
            task="Search for AI",
            url="https://example.com",
        )
        
        result = await router.route(input)
        
        # Validate output matches contract
        assert isinstance(result, RouterOutput)
        assert isinstance(result.route_type, RouteType)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reasoning, str)
    
    @pytest.mark.asyncio
    async def test_route_fast_path_on_high_confidence(self, temp_router):
        """Router should choose fast path for high confidence matches"""
        router, store = temp_router
        
        # Save a trajectory
        steps = [TrajectoryStep(action_type="click", selector="button")]
        await store.save(KnowledgeSaveInput(
            task="Search for AI on Hacker News",
            url="https://news.ycombinator.com",
            trajectory=steps,
            success=True,
            duration_ms=1000.0,
        ))
        
        # Route exact same task
        input = RouterInput(
            task="Search for AI on Hacker News",
            url="https://news.ycombinator.com",
        )
        
        result = await router.route(input)
        
        assert result.route_type == RouteType.FAST_PATH
        assert result.confidence >= 0.85
        assert result.trajectory is not None
    
    @pytest.mark.asyncio
    async def test_route_normal_path_on_no_match(self, temp_router):
        """Router should choose normal path when no match found"""
        router, _ = temp_router
        
        input = RouterInput(
            task="Some completely new task",
            url="https://newsite.com",
        )
        
        result = await router.route(input)
        
        assert result.route_type == RouteType.NORMAL_PATH
        assert result.trajectory is None


def run_tests():
    """Run contract tests"""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_tests()

