# -*- coding: utf-8 -*-
"""
Passive Learning System

Automatically learns from user actions and stores them for replay.
Now integrated with SkillWeaver-style skill synthesis and ExpeL-style confidence.

Architecture:
    User Actions → Recorder → KnowledgeStore → Future Replay
    New Task → SmartRouter → Skill Execution (fast) / AI Agent (normal)
    
Flow:
    1. User performs actions in browser
    2. Recorder captures via CDP events
    3. On idle, trajectory is saved to KnowledgeStore
    4. Optionally synthesize skill from trajectory
    5. Future similar tasks can use skill (parameterized) or replay

Usage:
    learning = PassiveLearningSystem(browser, knowledge_store)
    await learning.start()
    # ... user interacts ...
    await learning.stop()
"""

import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from engine.browser.recorder import Recorder, RecordedTrajectory, AutoRecorder
from engine.knowledge.store import KnowledgeStore, SearchResult, Skill, SkillSearchResult

logger = logging.getLogger("nogicos.learning")


@dataclass
class RouteResult:
    """Result of SmartRouter decision"""
    path: str  # "skill", "fast", or "normal"
    skill: Optional[Skill] = None
    params: Optional[Dict[str, Any]] = None
    replay_code: Optional[str] = None
    cached_result: Optional[str] = None
    confidence: float = 0.0
    source_task: Optional[str] = None
    trajectory: Optional[list] = None
    
    def is_fast(self) -> bool:
        """Check if this is a fast path (skill or replay)"""
        return self.path in ("skill", "fast")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "path": self.path,
            "skill": self.skill.to_dict() if self.skill else None,
            "params": self.params,
            "replay_code": self.replay_code,
            "cached_result": self.cached_result,
            "confidence": self.confidence,
            "source_task": self.source_task,
            "trajectory": self.trajectory,
        }


class PassiveLearningSystem:
    """
    Passive learning coordinator
    
    Connects Recorder to KnowledgeStore for automatic learning.
    """
    
    def __init__(
        self,
        page,
        knowledge_store: KnowledgeStore = None,
        auto_save: bool = True,
        min_actions: int = 3,
        idle_timeout: float = 5.0,
        on_learn: Callable[[RecordedTrajectory], None] = None,
    ):
        self.page = page
        self.knowledge_store = knowledge_store or KnowledgeStore()
        self.auto_save = auto_save
        self.min_actions = min_actions
        self.idle_timeout = idle_timeout
        self.on_learn = on_learn
        
        self._recorder: Optional[AutoRecorder] = None
        self._running = False
        self._trajectories_learned = 0
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def trajectories_learned(self) -> int:
        return self._trajectories_learned
    
    async def start(self):
        """Start passive learning"""
        if self._running:
            logger.warning("[PassiveLearning] Already running")
            return
        
        self._running = True
        
        # Create auto recorder with callback
        self._recorder = AutoRecorder(
            page=self.page,
            min_actions=self.min_actions,
            idle_timeout=self.idle_timeout,
            on_trajectory=self._on_trajectory_recorded,
        )
        
        await self._recorder.start()
        
        logger.info("[PassiveLearning] Started")
    
    async def stop(self):
        """Stop passive learning"""
        if not self._running:
            return
        
        self._running = False
        
        if self._recorder:
            await self._recorder.stop()
            self._recorder = None
        
        logger.info(f"[PassiveLearning] Stopped. Learned {self._trajectories_learned} trajectories")
    
    def _on_trajectory_recorded(self, trajectory: RecordedTrajectory):
        """Handle recorded trajectory"""
        if not self.auto_save:
            return
        
        # Run save in background
        asyncio.create_task(self._save_trajectory(trajectory))
    
    async def _save_trajectory(self, trajectory: RecordedTrajectory):
        """Save trajectory to knowledge store"""
        try:
            # Generate task description from actions
            task = self._infer_task(trajectory)
            
            # Convert actions to storable format
            actions = [a.to_dict() for a in trajectory.actions]
            
            # Save to knowledge store
            traj_id = await self.knowledge_store.save(
                task=task,
                url=trajectory.start_url,
                actions=actions,
                success=trajectory.success,
                metadata={
                    "recorded_at": datetime.now().isoformat(),
                    "duration": trajectory.end_time - trajectory.start_time,
                    "source": "passive_learning",
                },
            )
            
            self._trajectories_learned += 1
            
            logger.info(f"[PassiveLearning] Learned: {task[:50]}... ({len(actions)} actions)")
            
            # Callback
            if self.on_learn:
                self.on_learn(trajectory)
                
        except Exception as e:
            logger.error(f"[PassiveLearning] Save failed: {e}")
    
    def _infer_task(self, trajectory: RecordedTrajectory) -> str:
        """Infer task description from trajectory"""
        # Use explicit task if provided
        if trajectory.task and trajectory.task != "auto-recorded":
            return trajectory.task
        
        # Analyze actions to infer task
        actions = trajectory.actions
        
        # Look for key patterns
        has_login = any("login" in str(a.selector or "").lower() or 
                       "signin" in str(a.selector or "").lower() 
                       for a in actions)
        has_search = any("search" in str(a.selector or "").lower() for a in actions)
        has_form = any(a.action_type == "input" for a in actions)
        has_submit = any(a.action_type == "submit" for a in actions)
        
        # Build description
        parts = []
        
        if has_login:
            parts.append("login")
        elif has_search:
            parts.append("search")
        elif has_form:
            parts.append("fill form")
        
        if has_submit:
            parts.append("and submit")
        
        # Add domain context
        from urllib.parse import urlparse
        try:
            domain = urlparse(trajectory.start_url).netloc
            if domain:
                parts.append(f"on {domain}")
        except:
            pass
        
        if parts:
            return " ".join(parts)
        
        return f"actions on {trajectory.start_url}"


class SmartRouter:
    """
    Smart task router with skill support
    
    Decides whether to:
    1. Execute parameterized skill (skill path) - fastest, most flexible
    2. Replay from trajectory (fast path) - fast, but not parameterized
    3. Execute with AI agent (normal path) - slowest, but most capable
    
    Priority order:
    1. Skill with confidence >= threshold → skill path
    2. Trajectory with confidence >= threshold → fast path  
    3. Otherwise → normal path
    """
    
    def __init__(
        self,
        knowledge_store: KnowledgeStore,
        confidence_threshold: float = 0.7,
        prefer_skills: bool = True,
    ):
        self.knowledge_store = knowledge_store
        self.confidence_threshold = confidence_threshold
        self.prefer_skills = prefer_skills
        
        # Lazy-loaded extractor
        self._extractor = None
    
    @property
    def extractor(self):
        """Lazy load parameter extractor"""
        if self._extractor is None:
            from engine.skill.extractor import ParameterExtractor
            self._extractor = ParameterExtractor()
        return self._extractor
    
    async def route(self, task: str, url: str = "") -> RouteResult:
        """
        Route a task to the best execution path
        
        Priority:
        1. Skill path (if skill found with high confidence)
        2. Fast path (trajectory replay)
        3. Normal path (AI agent)
        
        Args:
            task: Task description
            url: Target URL
        
        Returns:
            RouteResult with execution path and resources
        """
        # 1. Try to find a matching skill first (if enabled)
        if self.prefer_skills:
            skill_result = await self.knowledge_store.find_skill(task, url)
            
            if skill_result.can_use(self.confidence_threshold):
                # Extract parameters for the skill
                extraction = self.extractor.extract_from_skill(task, skill_result.skill)
                
                logger.info(
                    f"[Router] SKILL path: {skill_result.skill.name} "
                    f"(conf={skill_result.confidence:.2f}, params={extraction.params})"
                )
                
                return RouteResult(
                    path="skill",
                    skill=skill_result.skill,
                    params=extraction.params,
                    confidence=skill_result.confidence,
                    source_task=skill_result.skill.description,
                )
        
        # 2. Try trajectory search (fast path)
        traj_result = await self.knowledge_store.search(task, url)
        
        if traj_result.matched and traj_result.confidence >= self.confidence_threshold:
            logger.info(
                f"[Router] FAST path: '{traj_result.source_task[:30]}...' "
                f"(conf={traj_result.confidence:.2f})"
            )
            
            return RouteResult(
                path="fast",
                replay_code=traj_result.replay_code,
                cached_result=traj_result.cached_result,
                confidence=traj_result.confidence,
                source_task=traj_result.source_task,
                trajectory=traj_result.trajectory,
            )
        
        # 3. Fall back to normal path (AI agent)
        logger.info(f"[Router] NORMAL path (best conf={traj_result.confidence:.2f})")
        
        return RouteResult(
            path="normal",
            confidence=traj_result.confidence,
        )
    
    async def route_dict(self, task: str, url: str = "") -> Dict[str, Any]:
        """
        Route and return as dictionary (backwards compatibility)
        """
        result = await self.route(task, url)
        return result.to_dict()


class ReplayExecutor:
    """
    Execute replay code from knowledge store
    """
    
    def __init__(self, page):
        self.page = page
    
    async def execute(self, replay_code: str) -> dict:
        """
        Execute replay code
        
        Returns:
            {"success": bool, "error": str | None}
        """
        try:
            # Create namespace with page
            namespace = {
                "page": self.page,
                "asyncio": asyncio,
            }
            
            # Execute the replay function definition
            exec(replay_code, namespace)
            
            # Call the replay function
            if "replay" in namespace:
                result = await asyncio.wait_for(
                    namespace["replay"](self.page),
                    timeout=60.0  # 1 minute timeout
                )
                return {"success": True, "result": result}
            else:
                return {"success": False, "error": "No replay function found"}
                
        except asyncio.TimeoutError:
            return {"success": False, "error": "Replay timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Quick test
if __name__ == "__main__":
    from engine.knowledge.store import SkillParameter
    
    async def test_passive_learning():
        print("=" * 50)
        print("Passive Learning System Test")
        print("=" * 50)
        
        store = KnowledgeStore()
        router = SmartRouter(store)
        
        # Test 1: Save a trajectory
        print("\n[1] Saving test trajectory...")
        await store.save(
            task="Search for AI news on Hacker News",
            url="https://news.ycombinator.com",
            actions=[
                {"action_type": "click", "selector": "input[type=text]"},
                {"action_type": "input", "selector": "input[type=text]", "value": "AI"},
                {"action_type": "click", "selector": "button[type=submit]"},
            ],
            success=True,
        )
        print("    [OK] Trajectory saved")
        
        # Test 2: Save a skill
        print("\n[2] Saving test skill...")
        await store.save_skill(
            name="search_hn",
            description="Search for content on Hacker News",
            code='''
async def search_hn(page, query: str):
    """Search for content on Hacker News"""
    await page.fill("input[type=text]", query)
    await page.click("button[type=submit]")
    return True
''',
            domain="news.ycombinator.com",
            parameters=[
                SkillParameter(name="query", param_type="str", description="Search query"),
            ],
        )
        print("    [OK] Skill saved")
        
        # Test 3: Route with skill match
        print("\n[3] Testing SKILL path (parameterized)...")
        result = await router.route('Search for "Python tutorials" on HN', "https://news.ycombinator.com")
        print(f"    Path: {result.path}")
        print(f"    Confidence: {result.confidence:.2f}")
        if result.skill:
            print(f"    Skill: {result.skill.name}")
            print(f"    Params: {result.params}")
        
        # Test 4: Route exact trajectory match (disable skills)
        print("\n[4] Testing FAST path (trajectory replay)...")
        router_no_skills = SmartRouter(store, prefer_skills=False)
        result = await router_no_skills.route("Search for AI news on Hacker News", "https://news.ycombinator.com")
        print(f"    Path: {result.path}")
        print(f"    Confidence: {result.confidence:.2f}")
        print(f"    Source: {result.source_task}")
        
        # Test 5: Route unrelated task
        print("\n[5] Testing NORMAL path (no match)...")
        result = await router.route("Book a flight to Paris", "https://expedia.com")
        print(f"    Path: {result.path}")
        print(f"    Confidence: {result.confidence:.2f}")
        
        # Test 6: RouteResult helper methods
        print("\n[6] Testing RouteResult helpers...")
        result = await router.route('Search for "ML" on HN', "https://news.ycombinator.com")
        print(f"    is_fast(): {result.is_fast()}")
        print(f"    to_dict() keys: {list(result.to_dict().keys())}")
        
        print("\n" + "=" * 50)
        print("Test Complete!")
        print("=" * 50)
    
    asyncio.run(test_passive_learning())

