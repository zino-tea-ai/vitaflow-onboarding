# -*- coding: utf-8 -*-
"""
Knowledge Module Contract Tests

Verifies the knowledge store follows its defined contract.
"""

import asyncio
import os
import sys
import tempfile
import pytest

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from contracts.knowledge_contract import (
    KnowledgeSearchInput,
    KnowledgeSearchOutput,
    KnowledgeSaveInput,
    TrajectoryStep,
)
from knowledge.store import KnowledgeStore


class TestKnowledgeContract:
    """Test knowledge store contract compliance"""
    
    @pytest.fixture
    def temp_store(self):
        """Create a temporary knowledge store"""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(data_dir=tmpdir)
            yield store
    
    @pytest.mark.asyncio
    async def test_search_returns_valid_output(self, temp_store):
        """Search should return valid KnowledgeSearchOutput"""
        input = KnowledgeSearchInput(
            task="Search for AI on Hacker News",
            threshold=0.8
        )
        
        result = await temp_store.search(input)
        
        # Validate output matches contract
        assert isinstance(result, KnowledgeSearchOutput)
        assert isinstance(result.matched, bool)
        assert 0.0 <= result.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_save_creates_trajectory(self, temp_store):
        """Save should store trajectory and return ID"""
        steps = [
            TrajectoryStep(
                action_type="click",
                selector="[data-test='search']",
                value=None,
            ),
            TrajectoryStep(
                action_type="fill",
                selector="input[name='q']",
                value="AI",
            ),
        ]
        
        input = KnowledgeSaveInput(
            task="Search for AI",
            url="https://news.ycombinator.com",
            trajectory=steps,
            success=True,
            duration_ms=5000.0,
        )
        
        trajectory_id = await temp_store.save(input)
        
        assert isinstance(trajectory_id, str)
        assert len(trajectory_id) > 0
        assert temp_store.count() == 1
    
    @pytest.mark.asyncio
    async def test_search_finds_saved_trajectory(self, temp_store):
        """Search should find previously saved trajectory"""
        # Save a trajectory
        steps = [
            TrajectoryStep(
                action_type="click",
                selector="button",
                value=None,
            ),
        ]
        
        save_input = KnowledgeSaveInput(
            task="Search for AI on Hacker News",
            url="https://news.ycombinator.com",
            trajectory=steps,
            success=True,
            duration_ms=3000.0,
        )
        
        await temp_store.save(save_input)
        
        # Search for similar task
        search_input = KnowledgeSearchInput(
            task="Search for AI on Hacker News",
            threshold=0.5,  # Lower threshold for testing
        )
        
        result = await temp_store.search(search_input)
        
        assert result.matched is True
        assert result.confidence > 0.5
        assert result.trajectory is not None
        assert len(result.trajectory) == 1
    
    @pytest.mark.asyncio
    async def test_ping_returns_bool(self, temp_store):
        """Ping should return boolean"""
        result = await temp_store.ping()
        assert isinstance(result, bool)
        assert result is True


def run_tests():
    """Run contract tests"""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_tests()

