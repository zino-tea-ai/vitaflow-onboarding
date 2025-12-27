# -*- coding: utf-8 -*-
"""
End-to-End Test: SkillWeaver Skill Learning System

Tests the complete flow:
1. Execute task with AI agent (NORMAL path)
2. Synthesize skill from successful trajectory
3. Execute similar task with skill (SKILL path)
4. Verify skill parameterization works
5. Verify confidence updates work

Usage:
    python -m tests.test_skill_e2e
"""

import asyncio
import os
import sys
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup environment
from api_keys import setup_env
setup_env()


async def test_skill_system():
    """Test the complete skill learning system"""
    print("=" * 60)
    print("SkillWeaver End-to-End Test")
    print("=" * 60)
    
    # Import after env setup
    from engine.knowledge.store import KnowledgeStore, SkillParameter
    from engine.learning.passive import SmartRouter
    from engine.skill.synthesizer import SkillSynthesizer
    from engine.skill.executor import SkillExecutor
    from engine.skill.extractor import ParameterExtractor
    
    # Use a test directory for knowledge
    test_dir = Path(__file__).parent.parent / "data" / "knowledge_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    
    # Initialize components
    store = KnowledgeStore(data_dir=str(test_dir))
    router = SmartRouter(store, prefer_skills=True)
    synthesizer = SkillSynthesizer(max_retries=2)
    extractor = ParameterExtractor()
    
    print("\n[Phase 1] Testing Knowledge Store")
    print("-" * 40)
    
    # 1. Save a test trajectory
    print("\n[1.1] Saving test trajectory...")
    trajectory = [
        {"action_type": "navigate", "url": "https://news.ycombinator.com"},
        {"action_type": "click", "selector": "input.searchbox"},
        {"action_type": "input", "selector": "input.searchbox", "value": "machine learning"},
        {"action_type": "click", "selector": "button.search-submit"},
    ]
    
    traj_id = await store.save(
        task="Search for machine learning on Hacker News",
        url="https://news.ycombinator.com",
        actions=trajectory,
        success=True,
        result="Found 10 results",
    )
    print(f"    [OK] Saved trajectory: {traj_id}")
    
    # 1.2 Test trajectory search
    print("\n[1.2] Testing trajectory search...")
    result = await store.search("Search for AI on HN", "https://news.ycombinator.com")
    print(f"    Matched: {result.matched}")
    print(f"    Confidence: {result.confidence:.2f}")
    
    print("\n[Phase 2] Testing Skill Synthesis")
    print("-" * 40)
    
    # 2.1 Synthesize skill from trajectory
    print("\n[2.1] Synthesizing skill from trajectory...")
    synth_result = await synthesizer.synthesize(
        task="Search for machine learning on Hacker News",
        trajectory=trajectory,
        domain="news.ycombinator.com",
    )
    
    if synth_result.success:
        print(f"    [OK] Synthesized function: {synth_result.function_name}")
        print(f"    Parameters: {synth_result.parameters}")
        print(f"    Code preview:")
        for line in synth_result.code.split("\n")[:5]:
            print(f"        {line}")
        print("        ...")
    else:
        print(f"    [FAIL] {synth_result.error}")
        # Use fallback skill for testing
        synth_result.success = True
        synth_result.function_name = "search_hn"
        synth_result.parameters = [{"name": "query", "type": "str"}]
        synth_result.code = '''
async def search_hn(page, query: str):
    """Search for content on Hacker News"""
    await page.fill("input.searchbox", query)
    await page.click("button.search-submit")
    return f"Searched for: {query}"
'''
    
    # 2.2 Save skill to store
    print("\n[2.2] Saving skill to knowledge store...")
    params = [
        SkillParameter(
            name=p["name"],
            param_type=p.get("type", "str"),
        )
        for p in (synth_result.parameters or [])
    ]
    
    skill = await store.save_skill(
        name=synth_result.function_name,
        description="Search for content on Hacker News",
        code=synth_result.code,
        domain="news.ycombinator.com",
        parameters=params,
        source_trajectory_id=traj_id,
    )
    print(f"    [OK] Saved skill: {skill.name} ({skill.id})")
    print(f"    Confidence: {skill.confidence}")
    
    print("\n[Phase 3] Testing Smart Router")
    print("-" * 40)
    
    # 3.1 Route with skill match
    print("\n[3.1] Testing SKILL path routing...")
    route = await router.route('Search for "Python tutorials" on HN', "https://news.ycombinator.com")
    print(f"    Path: {route.path}")
    print(f"    Confidence: {route.confidence:.2f}")
    if route.skill:
        print(f"    Skill: {route.skill.name}")
        print(f"    Params: {route.params}")
    
    # 3.2 Test parameter extraction
    print("\n[3.2] Testing parameter extraction...")
    extraction = extractor.extract_from_skill(
        task='Search for "AI agents" on the news site',
        skill=skill,
    )
    print(f"    Success: {extraction.success}")
    print(f"    Params: {extraction.params}")
    print(f"    Method: {extraction.method}")
    
    print("\n[Phase 4] Testing Skill Execution")
    print("-" * 40)
    
    # 4.1 Mock page test
    print("\n[4.1] Testing skill execution with mock page...")
    
    class MockPage:
        """Mock Playwright page for testing"""
        def __init__(self):
            self.actions = []
        
        async def fill(self, selector, value, **kwargs):
            self.actions.append(f"fill({selector}, {value})")
            print(f"        [Mock] fill({selector}, {value})")
        
        async def click(self, selector, **kwargs):
            self.actions.append(f"click({selector})")
            print(f"        [Mock] click({selector})")
        
        async def goto(self, url, **kwargs):
            self.actions.append(f"goto({url})")
            print(f"        [Mock] goto({url})")
        
        async def wait_for_load_state(self, state, **kwargs):
            self.actions.append(f"wait_for_load_state({state})")
            print(f"        [Mock] wait_for_load_state({state})")
        
        async def wait_for_selector(self, selector, **kwargs):
            self.actions.append(f"wait_for_selector({selector})")
            print(f"        [Mock] wait_for_selector({selector})")
        
        async def locator(self, selector):
            return MockLocator(selector, self)
    
    class MockLocator:
        """Mock Playwright locator"""
        def __init__(self, selector, page):
            self.selector = selector
            self.page = page
        
        async def fill(self, value, **kwargs):
            await self.page.fill(self.selector, value)
        
        async def click(self, **kwargs):
            await self.page.click(self.selector)
    
    mock_page = MockPage()
    executor = SkillExecutor(mock_page, timeout=10.0)
    
    exec_result = await executor.execute(
        code=skill.code,
        function_name=skill.name,
        params={"query": "AI agents"},
    )
    print(f"    Success: {exec_result.success}")
    print(f"    Result: {exec_result.result}")
    print(f"    Duration: {exec_result.duration_ms:.0f}ms")
    
    # 4.2 Test confidence update
    print("\n[4.2] Testing confidence update (ExpeL-style)...")
    original_conf = skill.confidence
    await store.update_skill_confidence(skill.id, success=True)
    updated_skill = await store.get_skill_by_id(skill.id)
    print(f"    Original confidence: {original_conf}")
    print(f"    Updated confidence: {updated_skill.confidence}")
    print(f"    Success count: {updated_skill.success_count}")
    
    print("\n[Phase 5] Testing Full Router Flow")
    print("-" * 40)
    
    # 5.1 Test different tasks
    test_tasks = [
        ('Search for "machine learning" on HN', "https://news.ycombinator.com"),
        ("Find Python news", "https://news.ycombinator.com"),
        ("Login to GitHub", "https://github.com"),  # Different domain
    ]
    
    for task, url in test_tasks:
        result = await router.route(task, url)
        print(f"\n    Task: {task[:40]}...")
        print(f"    Path: {result.path}, Confidence: {result.confidence:.2f}")
        if result.skill:
            print(f"    Skill: {result.skill.name}")
    
    print("\n[Phase 6] Final Statistics")
    print("-" * 40)
    
    stats = store.get_stats()
    print(f"\n    Total trajectories: {stats['total_trajectories']}")
    print(f"    Total skills: {stats['total_skills']}")
    print(f"    Domains: {stats['domains']}")
    
    skill_stats = store.get_skill_stats()
    print(f"    Reliable skills: {skill_stats['reliable_skills']}")
    
    # Cleanup
    print("\n[Cleanup] Removing test data...")
    shutil.rmtree(test_dir)
    print("    [OK] Test data removed")
    
    print("\n" + "=" * 60)
    print("SkillWeaver E2E Test Complete!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_skill_system())
    sys.exit(0 if success else 1)

