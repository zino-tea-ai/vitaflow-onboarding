# -*- coding: utf-8 -*-
"""
Knowledge Store - Trajectory and Skill storage with semantic search

Based on LangGraph's InMemoryStore pattern for semantic retrieval.
Integrated with SkillWeaver-style skill synthesis and ExpeL-style confidence weighting.

Architecture:
    Task → Embed → Vector Search → Best Match → Skill/Replay

Features:
    - Semantic similarity search (not just keyword match)
    - Domain-based namespacing
    - Trajectory replay generation
    - Skill storage with parameterized code (SkillWeaver)
    - Confidence-based skill weighting (ExpeL)
    - Integration with LangGraph store
"""

import json
import os
import hashlib
import logging
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger("nogicos.knowledge")


@dataclass
class SearchResult:
    """Search result with confidence score"""
    matched: bool
    confidence: float = 0.0
    trajectory: Optional[List[dict]] = None
    source_task: Optional[str] = None
    replay_code: Optional[str] = None
    cached_result: Optional[str] = None  # 缓存的最终答案
    
    def can_replay(self) -> bool:
        """Check if result has enough confidence for replay"""
        return self.matched and self.confidence >= 0.7
    
    def has_cached_result(self) -> bool:
        """Check if we have a cached result to return directly"""
        return self.cached_result is not None and len(self.cached_result) > 0


@dataclass
class TrajectoryEntry:
    """A stored trajectory entry"""
    id: str
    task: str
    domain: str
    url: str
    actions: List[dict]
    success: bool
    created_at: str
    execution_count: int = 0
    success_rate: float = 1.0
    embedding: Optional[List[float]] = None


@dataclass
class SkillParameter:
    """A parameter for a skill function"""
    name: str
    param_type: str = "str"  # str, int, float, bool
    description: str = ""
    required: bool = True
    default: Optional[str] = None


@dataclass
class Skill:
    """
    A learned skill - parameterized Python function for browser automation
    
    Based on SkillWeaver's API format + ExpeL's confidence weighting.
    
    Example:
        Skill(
            id="search_hn_abc123",
            name="search_hn",
            description="Search for content on Hacker News",
            parameters=[SkillParameter(name="query", param_type="str", description="Search query")],
            code='''
async def search_hn(page, query: str):
    await page.fill("input[type=text]", query)
    await page.click("button[type=submit]")
    return True
''',
            domain="news.ycombinator.com",
        )
    """
    id: str
    name: str                                    # Function name, e.g. "search_hn"
    description: str                             # Natural language description
    parameters: List[SkillParameter] = field(default_factory=list)  # Parameter definitions
    code: str = ""                               # Playwright Python code
    domain: str = ""                             # Target domain
    confidence: int = 2                          # ExpeL-style weight (starts at 2)
    success_count: int = 0                       # Successful executions
    fail_count: int = 0                          # Failed executions
    created_at: str = ""                         # Creation timestamp
    updated_at: str = ""                         # Last update timestamp
    source_trajectory_id: Optional[str] = None   # Original trajectory this skill was synthesized from
    embedding: Optional[List[float]] = None      # Embedding for semantic search
    
    def update_confidence(self, success: bool):
        """Update confidence based on execution result (ExpeL-style)"""
        if success:
            self.confidence += 1
            self.success_count += 1
        else:
            self.confidence -= 1
            self.fail_count += 1
        self.updated_at = datetime.now().isoformat()
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 1.0
    
    @property
    def is_reliable(self) -> bool:
        """Check if skill is reliable enough to use"""
        return self.confidence > 0 and self.success_rate >= 0.5
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parameters": [asdict(p) for p in self.parameters],
            "code": self.code,
            "domain": self.domain,
            "confidence": self.confidence,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_trajectory_id": self.source_trajectory_id,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Skill":
        """Create from dictionary"""
        params = [
            SkillParameter(**p) if isinstance(p, dict) else p 
            for p in data.get("parameters", [])
        ]
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            parameters=params,
            code=data.get("code", ""),
            domain=data.get("domain", ""),
            confidence=data.get("confidence", 2),
            success_count=data.get("success_count", 0),
            fail_count=data.get("fail_count", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            source_trajectory_id=data.get("source_trajectory_id"),
        )


@dataclass
class SkillSearchResult:
    """Result from skill search"""
    matched: bool
    skill: Optional[Skill] = None
    confidence: float = 0.0
    
    def can_use(self, threshold: float = 0.7) -> bool:
        """Check if skill is usable"""
        return (
            self.matched 
            and self.skill is not None 
            and self.confidence >= threshold
            and self.skill.is_reliable
        )


class KnowledgeStore:
    """
    Local knowledge store with semantic search
    
    Stores both trajectories (raw action sequences) and skills (parameterized code).
    Uses embeddings for similarity matching when available,
    falls back to keyword matching otherwise.
    
    Directory structure:
        data/knowledge/
        ├── index.json           # Trajectory index
        ├── skills_index.json    # Skill index
        ├── {traj_id}.json       # Individual trajectories
        └── skills/
            └── {skill_id}.json  # Individual skills
    """
    
    def __init__(
        self,
        data_dir: str = None,
        embed_fn: Callable[[str], List[float]] = None,
    ):
        if data_dir is None:
            data_dir = str(Path(__file__).parent.parent.parent / "data" / "knowledge")
        
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        # Skills directory
        self._skills_dir = os.path.join(data_dir, "skills")
        os.makedirs(self._skills_dir, exist_ok=True)
        
        # Trajectory index
        self._index_path = os.path.join(data_dir, "index.json")
        self._index = self._load_index()
        
        # Skills index
        self._skills_index_path = os.path.join(data_dir, "skills_index.json")
        self._skills_index = self._load_skills_index()
        
        # Embedding function (optional)
        self._embed_fn = embed_fn
        self._embeddings_cache: Dict[str, List[float]] = {}
    
    def _load_index(self) -> dict:
        """Load trajectory index from disk"""
        if os.path.exists(self._index_path):
            try:
                with open(self._index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {
            "version": "2.0",
            "trajectories": [],
            "domains": {},
        }
    
    def _load_skills_index(self) -> dict:
        """Load skills index from disk"""
        if os.path.exists(self._skills_index_path):
            try:
                with open(self._skills_index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {
            "version": "1.0",
            "skills": [],
            "domains": {},
        }
    
    def _save_skills_index(self):
        """Save skills index to disk"""
        with open(self._skills_index_path, "w", encoding="utf-8") as f:
            json.dump(self._skills_index, f, indent=2, ensure_ascii=False)
    
    def _save_index(self):
        """Save index to disk"""
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL for namespacing"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc or "unknown"
        except:
            return "unknown"
    
    def _compute_embedding(self, text: str) -> Optional[List[float]]:
        """Compute embedding for text"""
        if not self._embed_fn:
            return None
        
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embeddings_cache:
            return self._embeddings_cache[cache_key]
        
        try:
            embedding = self._embed_fn(text)
            self._embeddings_cache[cache_key] = embedding
            return embedding
        except Exception as e:
            logger.warning(f"[Knowledge] Embedding failed: {e}")
            return None
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors"""
        if not a or not b or len(a) != len(b):
            return 0.0
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    def _extract_key_terms(self, text: str) -> set:
        """
        Extract key terms from task description
        
        Key terms are nouns/verbs that define the task semantics.
        Excludes common stop words and prepositions.
        """
        stop_words = {
            'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'go', 'tell',
            'me', 'you', 'it', 'what', 'how', 'where', 'when', 'why', 'which',
            'this', 'that', 'these', 'those', 'i', 'we', 'they', 'he', 'she',
            'search', 'find', 'get', 'show', 'see', 'look', 'news', 'content',
        }
        
        # Important short terms that should NOT be filtered (domain terms)
        important_short_terms = {'ai', 'ml', 'ux', 'ui', 'js', 'py', 'db', 'api'}
        
        words = set(text.lower().split())
        # Remove stop words and short words (unless important)
        key_terms = {
            w for w in words 
            if w not in stop_words and (len(w) > 2 or w in important_short_terms)
        }
        return key_terms
    
    def _keyword_similarity(self, task1: str, task2: str, url1: str = "", url2: str = "") -> float:
        """
        Improved keyword similarity with key term matching
        
        Requires key terms to match, not just any words.
        """
        words1 = set(task1.lower().split())
        words2 = set(task2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Basic Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        base_score = intersection / union if union > 0 else 0.0
        
        # Extract and compare key terms
        key1 = self._extract_key_terms(task1)
        key2 = self._extract_key_terms(task2)
        
        if key1 and key2:
            key_intersection = len(key1 & key2)
            key_union = len(key1 | key2)
            key_score = key_intersection / key_union if key_union > 0 else 0.0
            
            # If key terms don't match well, heavily penalize
            if key_score < 0.5:
                base_score *= 0.3  # 70% penalty
            elif key_score >= 0.8:
                base_score = min(1.0, base_score * 1.2)  # 20% bonus
        
        # Domain match (reduced bonus)
        domain1 = self._extract_domain(url1)
        domain2 = self._extract_domain(url2)
        if domain1 and domain2 and domain1 == domain2:
            base_score = min(1.0, base_score + 0.05)  # Only 5% bonus (was 15%)
        
        return base_score
    
    async def search(
        self,
        task: str,
        url: str = "",
        limit: int = 5,
    ) -> SearchResult:
        """
        Search for matching trajectory
        
        Uses semantic search if embeddings available,
        falls back to keyword matching.
        """
        if not self._index["trajectories"]:
            return SearchResult(matched=False, confidence=0.0)
        
        domain = self._extract_domain(url)
        
        # Compute query embedding
        query_embedding = self._compute_embedding(task)
        
        # Score all trajectories
        scored = []
        for entry in self._index["trajectories"]:
            # Prefer same domain
            entry_domain = entry.get("domain", "")
            domain_match = entry_domain == domain if domain else True
            
            # Compute similarity
            if query_embedding and entry.get("embedding"):
                score = self._cosine_similarity(query_embedding, entry["embedding"])
            else:
                score = self._keyword_similarity(task, entry["task"], url, entry.get("url", ""))
            
            # Domain bonus
            if domain_match:
                score = min(1.0, score * 1.2)
            
            scored.append((score, entry))
        
        # Sort by score
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Get best match (threshold raised from 0.5 to 0.7 for precision)
        if scored and scored[0][0] >= 0.7:
            best_score, best_entry = scored[0]
            
            # Load full trajectory
            trajectory = await self._load_trajectory(best_entry["id"])
            
            if trajectory:
                # Generate replay code
                replay_code = self._generate_replay_code(trajectory.get("actions", []))
                
                return SearchResult(
                    matched=True,
                    confidence=best_score,
                    trajectory=trajectory.get("actions", []),
                    source_task=best_entry["task"],
                    replay_code=replay_code,
                    cached_result=trajectory.get("result"),  # 返回缓存的结果
                )
        
        return SearchResult(matched=False, confidence=scored[0][0] if scored else 0.0)
    
    async def _load_trajectory(self, traj_id: str) -> Optional[dict]:
        """Load full trajectory from disk"""
        filepath = os.path.join(self.data_dir, f"{traj_id}.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return None
    
    def _generate_replay_code(self, actions: List[dict]) -> str:
        """Generate Playwright code for replay"""
        lines = [
            "async def replay(page):",
            '    """Auto-generated replay from knowledge base"""',
        ]
        
        for action in actions:
            action_type = action.get("action_type", "")
            selector = action.get("selector", "")
            value = action.get("value", "")
            url = action.get("url", "")
            
            if action_type == "navigate" and url:
                lines.append(f'    await page.goto("{url}")')
            elif action_type == "click" and selector:
                lines.append(f'    await page.click("{selector}", timeout=15000)')
            elif action_type == "input" and selector and value:
                # Mask sensitive data
                safe_value = "***" if any(kw in selector.lower() for kw in ["password", "secret", "token"]) else value
                lines.append(f'    await page.fill("{selector}", "{safe_value}", timeout=15000)')
            elif action_type == "submit":
                if selector:
                    lines.append(f'    await page.click("{selector} [type=submit]", timeout=15000)')
        
        lines.append("    return True")
        return "\n".join(lines)
    
    async def save(
        self,
        task: str,
        url: str,
        actions: List[dict],
        success: bool = True,
        result: Optional[str] = None,  # 最终结果/答案
        metadata: dict = None,
    ) -> str:
        """
        Save a trajectory to knowledge store
        
        Args:
            task: Task description
            url: Starting URL
            actions: List of recorded actions
            success: Whether task succeeded
            result: The final result/answer from the task (for Fast Path reuse)
            metadata: Additional metadata
        
        Returns:
            Trajectory ID
        """
        domain = self._extract_domain(url)
        traj_id = hashlib.sha256(f"{task}|{url}|{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        # Compute embedding
        embedding = self._compute_embedding(task)
        
        # Save full trajectory
        data = {
            "id": traj_id,
            "task": task,
            "domain": domain,
            "url": url,
            "actions": actions,
            "success": success,
            "result": result,  # 保存最终结果
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        
        filepath = os.path.join(self.data_dir, f"{traj_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Update index
        index_entry = {
            "id": traj_id,
            "task": task,
            "domain": domain,
            "url": url,
            "action_count": len(actions),
            "success": success,
            "created_at": datetime.now().isoformat(),
        }
        
        if embedding:
            index_entry["embedding"] = embedding
        
        # Check for existing entry with same task+domain
        existing_idx = None
        for i, entry in enumerate(self._index["trajectories"]):
            if entry["task"] == task and entry.get("domain") == domain:
                existing_idx = i
                break
        
        if existing_idx is not None:
            # Update existing
            self._index["trajectories"][existing_idx] = index_entry
        else:
            # Add new
            self._index["trajectories"].append(index_entry)
        
        # Update domain stats
        if domain not in self._index["domains"]:
            self._index["domains"][domain] = {"count": 0, "success_count": 0}
        self._index["domains"][domain]["count"] += 1
        if success:
            self._index["domains"][domain]["success_count"] += 1
        
        self._save_index()
        
        logger.info(f"[Knowledge] Saved trajectory {traj_id} for '{task[:50]}...' on {domain}")
        return traj_id
    
    def count(self) -> int:
        """Get total trajectory count"""
        return len(self._index["trajectories"])
    
    def count_by_domain(self, domain: str) -> int:
        """Get trajectory count for a domain"""
        return self._index["domains"].get(domain, {}).get("count", 0)
    
    def get_domains(self) -> List[str]:
        """List all domains with stored trajectories"""
        return list(self._index["domains"].keys())
    
    def get_stats(self) -> dict:
        """Get knowledge store statistics"""
        total = self.count()
        success = sum(1 for t in self._index["trajectories"] if t.get("success", False))
        
        return {
            "total_trajectories": total,
            "successful": success,
            "success_rate": success / total if total > 0 else 0.0,
            "domains": len(self._index["domains"]),
            "domain_stats": self._index["domains"],
            "total_skills": self.skill_count(),
        }
    
    # ========================================================================
    # Skill Management (SkillWeaver-style)
    # ========================================================================
    
    async def save_skill(
        self,
        name: str,
        description: str,
        code: str,
        domain: str,
        parameters: List[SkillParameter] = None,
        source_trajectory_id: str = None,
    ) -> Skill:
        """
        Save a new skill to the knowledge store
        
        Args:
            name: Function name (e.g., "search_hn")
            description: Natural language description
            code: Playwright Python code
            domain: Target domain
            parameters: List of parameter definitions
            source_trajectory_id: ID of trajectory this skill was synthesized from
        
        Returns:
            Created Skill object
        """
        skill_id = hashlib.sha256(f"{name}|{domain}|{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        skill = Skill(
            id=skill_id,
            name=name,
            description=description,
            parameters=parameters or [],
            code=code,
            domain=domain,
            confidence=2,  # ExpeL: new skills start with confidence 2
            success_count=0,
            fail_count=0,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            source_trajectory_id=source_trajectory_id,
        )
        
        # Compute embedding for semantic search
        embed_text = f"{name} {description}"
        skill.embedding = self._compute_embedding(embed_text)
        
        # Save skill to file
        filepath = os.path.join(self._skills_dir, f"{skill_id}.json")
        skill_data = skill.to_dict()
        if skill.embedding:
            skill_data["embedding"] = skill.embedding
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(skill_data, f, indent=2, ensure_ascii=False)
        
        # Update index
        index_entry = {
            "id": skill_id,
            "name": name,
            "description": description,
            "domain": domain,
            "confidence": skill.confidence,
            "created_at": skill.created_at,
        }
        if skill.embedding:
            index_entry["embedding"] = skill.embedding
        
        # Check for existing skill with same name+domain
        existing_idx = None
        for i, entry in enumerate(self._skills_index["skills"]):
            if entry["name"] == name and entry.get("domain") == domain:
                existing_idx = i
                break
        
        if existing_idx is not None:
            # Update existing (new version of skill)
            self._skills_index["skills"][existing_idx] = index_entry
            logger.info(f"[Knowledge] Updated skill: {name} ({skill_id}) for {domain}")
        else:
            # Add new
            self._skills_index["skills"].append(index_entry)
            logger.info(f"[Knowledge] Saved new skill: {name} ({skill_id}) for {domain}")
        
        # Update domain stats
        if domain not in self._skills_index["domains"]:
            self._skills_index["domains"][domain] = {"count": 0}
        self._skills_index["domains"][domain]["count"] += 1
        
        self._save_skills_index()
        
        return skill
    
    async def find_skill(
        self,
        task: str,
        url: str = "",
        confidence_threshold: float = 0.7,
    ) -> SkillSearchResult:
        """
        Find a matching skill for a task
        
        Uses semantic search to find the best matching skill.
        
        Args:
            task: Task description
            url: Target URL (for domain matching)
            confidence_threshold: Minimum confidence for skill to be usable
        
        Returns:
            SkillSearchResult with matched skill and confidence
        """
        if not self._skills_index["skills"]:
            return SkillSearchResult(matched=False, confidence=0.0)
        
        domain = self._extract_domain(url)
        
        # Compute query embedding
        query_embedding = self._compute_embedding(task)
        
        # Score all skills
        scored = []
        for entry in self._skills_index["skills"]:
            # Skip low-confidence skills
            if entry.get("confidence", 2) <= 0:
                continue
            
            # Prefer same domain
            entry_domain = entry.get("domain", "")
            domain_match = entry_domain == domain if domain else True
            
            # Compute similarity
            if query_embedding and entry.get("embedding"):
                score = self._cosine_similarity(query_embedding, entry["embedding"])
            else:
                # Fallback to keyword matching
                search_text = f"{entry['name']} {entry['description']}"
                score = self._keyword_similarity(task, search_text, url, "")
            
            # Domain bonus
            if domain_match and domain:
                score = min(1.0, score * 1.3)  # Stronger domain bonus for skills
            
            scored.append((score, entry))
        
        # Sort by score
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Get best match (threshold raised from 0.5 to 0.7 for precision)
        if scored and scored[0][0] >= 0.7:
            best_score, best_entry = scored[0]
            
            # Load full skill
            skill = await self._load_skill(best_entry["id"])
            
            if skill and skill.is_reliable:
                return SkillSearchResult(
                    matched=True,
                    skill=skill,
                    confidence=best_score,
                )
        
        return SkillSearchResult(
            matched=False, 
            confidence=scored[0][0] if scored else 0.0
        )
    
    async def _load_skill(self, skill_id: str) -> Optional[Skill]:
        """Load full skill from disk"""
        filepath = os.path.join(self._skills_dir, f"{skill_id}.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return Skill.from_dict(data)
            except Exception as e:
                logger.error(f"[Knowledge] Failed to load skill {skill_id}: {e}")
        return None
    
    async def update_skill_confidence(self, skill_id: str, success: bool) -> Optional[Skill]:
        """
        Update skill confidence based on execution result (ExpeL-style)
        
        Args:
            skill_id: Skill ID
            success: Whether execution succeeded
        
        Returns:
            Updated skill or None if not found
        """
        skill = await self._load_skill(skill_id)
        if not skill:
            return None
        
        # Update confidence
        skill.update_confidence(success)
        
        # Save updated skill
        filepath = os.path.join(self._skills_dir, f"{skill_id}.json")
        skill_data = skill.to_dict()
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(skill_data, f, indent=2, ensure_ascii=False)
        
        # Update index
        for entry in self._skills_index["skills"]:
            if entry["id"] == skill_id:
                entry["confidence"] = skill.confidence
                break
        
        self._save_skills_index()
        
        logger.info(f"[Knowledge] Updated skill {skill_id} confidence: {skill.confidence} (success={success})")
        
        return skill
    
    async def get_skill_by_id(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID"""
        return await self._load_skill(skill_id)
    
    async def get_skills_for_domain(self, domain: str) -> List[Skill]:
        """Get all skills for a domain"""
        skills = []
        for entry in self._skills_index["skills"]:
            if entry.get("domain") == domain:
                skill = await self._load_skill(entry["id"])
                if skill:
                    skills.append(skill)
        return skills
    
    def skill_count(self) -> int:
        """Get total skill count"""
        return len(self._skills_index["skills"])
    
    def get_skill_stats(self) -> dict:
        """Get skill statistics"""
        total = self.skill_count()
        reliable = sum(1 for s in self._skills_index["skills"] if s.get("confidence", 0) > 0)
        
        return {
            "total_skills": total,
            "reliable_skills": reliable,
            "domains": len(self._skills_index["domains"]),
            "domain_stats": self._skills_index["domains"],
        }


# Quick test
if __name__ == "__main__":
    import asyncio
    
    async def test_store():
        print("=" * 50)
        print("Knowledge Store Test")
        print("=" * 50)
        
        store = KnowledgeStore()
        
        # Test save trajectory
        print("\n[1] Testing trajectory save...")
        traj_id = await store.save(
            task="Login to Hacker News",
            url="https://news.ycombinator.com",
            actions=[
                {"action_type": "click", "selector": "a.login"},
                {"action_type": "input", "selector": "#username", "value": "testuser"},
                {"action_type": "input", "selector": "#password", "value": "***"},
                {"action_type": "click", "selector": "button[type=submit]"},
            ],
            success=True,
        )
        print(f"    [OK] Saved trajectory: {traj_id}")
        
        # Test search (exact match)
        print("\n[2] Testing trajectory search (exact)...")
        result = await store.search("Login to Hacker News", "https://news.ycombinator.com")
        print(f"    Matched: {result.matched}")
        print(f"    Confidence: {result.confidence:.2f}")
        print(f"    Can replay: {result.can_replay()}")
        
        # Test search (similar)
        print("\n[3] Testing trajectory search (similar)...")
        result = await store.search("Sign in to HN", "https://news.ycombinator.com")
        print(f"    Matched: {result.matched}")
        print(f"    Confidence: {result.confidence:.2f}")
        
        # =====================================================================
        # Skill Tests
        # =====================================================================
        
        print("\n" + "-" * 50)
        print("Skill Tests")
        print("-" * 50)
        
        # Test save skill
        print("\n[4] Testing skill save...")
        skill = await store.save_skill(
            name="search_hn",
            description="Search for content on Hacker News",
            code='''
async def search_hn(page, query: str):
    """Search for content on Hacker News"""
    await page.fill("input[type=text]", query)
    await page.click("button[type=submit]")
    await page.wait_for_load_state("networkidle")
    return True
''',
            domain="news.ycombinator.com",
            parameters=[
                SkillParameter(name="query", param_type="str", description="Search query"),
            ],
            source_trajectory_id=traj_id,
        )
        print(f"    [OK] Saved skill: {skill.name} ({skill.id})")
        print(f"    Confidence: {skill.confidence}")
        print(f"    Parameters: {[p.name for p in skill.parameters]}")
        
        # Test find skill (exact match)
        print("\n[5] Testing skill search (exact)...")
        result = await store.find_skill("Search for AI on Hacker News", "https://news.ycombinator.com")
        print(f"    Matched: {result.matched}")
        print(f"    Confidence: {result.confidence:.2f}")
        if result.skill:
            print(f"    Skill: {result.skill.name}")
            print(f"    Can use: {result.can_use()}")
        
        # Test find skill (similar)
        print("\n[6] Testing skill search (similar)...")
        result = await store.find_skill("Find Python articles", "https://news.ycombinator.com")
        print(f"    Matched: {result.matched}")
        print(f"    Confidence: {result.confidence:.2f}")
        
        # Test update confidence
        print("\n[7] Testing skill confidence update...")
        updated = await store.update_skill_confidence(skill.id, success=True)
        if updated:
            print(f"    [OK] Updated confidence: {updated.confidence}")
            print(f"    Success count: {updated.success_count}")
        
        # Test stats
        print("\n[8] Testing stats...")
        stats = store.get_stats()
        print(f"    Total trajectories: {stats['total_trajectories']}")
        print(f"    Total skills: {stats['total_skills']}")
        print(f"    Domains: {stats['domains']}")
        
        skill_stats = store.get_skill_stats()
        print(f"    Reliable skills: {skill_stats['reliable_skills']}")
        
        print("\n" + "=" * 50)
        print("Knowledge Store Test Complete!")
        print("=" * 50)
    
    asyncio.run(test_store())
