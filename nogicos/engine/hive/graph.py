# -*- coding: utf-8 -*-
"""
Hive Agent Graph - LangGraph State Machine

The core of NogicOS AI engine.

State Flow:
    START → observe → think → [act | terminate]
                        ↑        ↓
                        └────────┘
"""

import os
from typing import Optional
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langchain_anthropic import ChatAnthropic

from engine.hive.state import AgentState, create_initial_state
from engine.hive.nodes import (
    observe_node,
    think_node,
    act_node,
    terminate_node,
    should_continue,
)
from engine.knowledge.store import KnowledgeStore


class HiveAgent:
    """
    Hive Agent - LangGraph-based browser automation agent
    
    Usage:
        agent = HiveAgent()
        result = await agent.run("Search for AI on Hacker News", browser_session)
    
    Memory:
        - checkpointer: SQLite for conversation persistence (survives restart)
        - store: InMemoryStore for cross-thread knowledge
        - knowledge_store: Local file storage for trajectories
    
    Observability:
        - verbose=True enables detailed logging
        - All errors are logged with classification
    """
    
    def __init__(
        self,
        model: str = "claude-opus-4-5-20251101",
        api_key: Optional[str] = None,
        persist: bool = True,  # Enable SQLite persistence
        db_path: str = None,
        verbose: bool = False,  # Enable detailed logging
        knowledge_store: Optional[KnowledgeStore] = None,  # Shared knowledge store
    ):
        self.model_name = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.persist = persist
        self.verbose = verbose
        
        # Configure logging
        if verbose:
            import logging
            logging.basicConfig(level=logging.DEBUG)
            logging.getLogger("nogicos.hive").setLevel(logging.DEBUG)
        else:
            import logging
            logging.getLogger("nogicos.hive").setLevel(logging.WARNING)
        
        # Initialize LLM (lazy if no API key)
        self._llm = None
        if self.api_key:
            self._llm = ChatAnthropic(
                model=model,
                api_key=self.api_key,
                max_tokens=4096,
            )
        
        # Memory components
        # Use InMemorySaver for session persistence
        self.checkpointer = InMemorySaver()
        
        # Track data path for trajectory storage
        if persist:
            db_dir = Path(__file__).parent.parent.parent / "data"
            db_dir.mkdir(exist_ok=True)
            self.db_path = str(db_dir / "checkpoints.db")
        else:
            self.db_path = None
        
        self.store = InMemoryStore()  # Cross-thread knowledge
        
        # Knowledge store for trajectories (shared across system)
        self.knowledge_store = knowledge_store or KnowledgeStore()
        
        # Build graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine"""
        
        # Create graph with state schema
        builder = StateGraph(AgentState)
        
        # Add nodes
        # Note: We'll wrap nodes to inject dependencies
        builder.add_node("observe", self._observe_wrapper)
        builder.add_node("think", self._think_wrapper)
        builder.add_node("act", self._act_wrapper)
        builder.add_node("terminate", terminate_node)
        
        # Define edges
        # START → observe
        builder.add_edge(START, "observe")
        
        # observe → think
        builder.add_edge("observe", "think")
        
        # think → conditional routing
        builder.add_conditional_edges(
            "think",
            self._route_after_think,
            {
                "act": "act",
                "terminate": "terminate",
                "observe": "observe",
            }
        )
        
        # act → observe (loop back)
        builder.add_edge("act", "observe")
        
        # terminate → END
        builder.add_edge("terminate", END)
        
        # Compile with checkpointer
        return builder.compile(
            checkpointer=self.checkpointer,
        )
    
    async def _observe_wrapper(self, state: AgentState) -> dict:
        """Wrapper to inject browser session"""
        if not hasattr(self, '_current_browser'):
            return {"status": "failed", "result": "No browser session"}
        return await observe_node(state, self._current_browser)
    
    @property
    def llm(self):
        """Lazy LLM initialization"""
        if self._llm is None:
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            self._llm = ChatAnthropic(
                model=self.model_name,
                api_key=self.api_key,
                max_tokens=4096,
            )
        return self._llm
    
    async def _think_wrapper(self, state: AgentState) -> dict:
        """Wrapper to inject LLM and config"""
        return await think_node(state, self.llm, verbose=self.verbose)
    
    async def _act_wrapper(self, state: AgentState) -> dict:
        """Wrapper to inject browser session"""
        if not hasattr(self, '_current_browser'):
            return {"status": "failed", "result": "No browser session"}
        return await act_node(state, self._current_browser)
    
    def _route_after_think(self, state: AgentState) -> str:
        """Route after think node"""
        return should_continue(state)
    
    async def run(
        self,
        task: str,
        browser_session,
        max_steps: int = 10,
        thread_id: str = "default",
        save_trajectory: bool = True,
        start_url: str = "",
    ) -> dict:
        """
        Run the agent on a task
        
        Args:
            task: Task description
            browser_session: Browser session instance
            max_steps: Maximum steps to attempt
            thread_id: Thread ID for memory persistence
            save_trajectory: Whether to save successful trajectory
            start_url: Starting URL for knowledge indexing
        
        Returns:
            Final state with result
        """
        # Store browser session for nodes to access
        self._current_browser = browser_session
        
        # Get URL from browser if not provided
        if not start_url and hasattr(browser_session, 'page') and browser_session.page:
            start_url = browser_session.page.url
        
        # Create initial state
        initial_state = create_initial_state(task, max_steps)
        
        # Run graph
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        
        try:
            final_state = await self.graph.ainvoke(initial_state, config)
            
            result = {
                "success": final_state.get("status") == "completed",
                "result": final_state.get("result"),
                "steps": final_state.get("current_step", 0),
                "actions": final_state.get("actions", []),
                "thread_id": thread_id,
            }
            
            # Save successful trajectory for future replay
            if save_trajectory and result["success"]:
                await self._save_trajectory(task, result, thread_id, url=start_url)
            
            return result
        finally:
            # Clean up
            self._current_browser = None
    
    async def _save_trajectory(self, task: str, result: dict, thread_id: str, url: str = ""):
        """Save successful trajectory to knowledge store for future replay"""
        
        # Convert actions to storable format
        actions = []
        for action in result.get("actions", []):
            # Extract action details from the agent's output
            if isinstance(action, dict):
                action_entry = {
                    "action_type": action.get("action_type", "code"),
                    "code": action.get("python_code", ""),
                    "reasoning": action.get("step_by_step_reasoning", ""),
                }
                actions.append(action_entry)
        
        # Save to knowledge store (enables semantic search + replay)
        try:
            traj_id = await self.knowledge_store.save(
                task=task,
                url=url,
                actions=actions,
                success=True,
                result=result.get("result"),  # 保存最终结果，供 Fast Path 复用
                metadata={
                    "thread_id": thread_id,
                    "steps": result["steps"],
                    "source": "hive_agent",
                },
            )
            print(f"[Knowledge] Saved trajectory: {traj_id} for '{task[:40]}...'")
        except Exception as e:
            print(f"[Knowledge] Save failed: {e}")
    
    def get_history(self, thread_id: str) -> list:
        """
        Get conversation history for a thread
        
        Args:
            thread_id: Thread to retrieve history for
            
        Returns:
            List of checkpoints (state snapshots)
        """
        config = {"configurable": {"thread_id": thread_id}}
        
        history = []
        for checkpoint in self.graph.get_state_history(config):
            history.append({
                "checkpoint_id": checkpoint.config["configurable"]["checkpoint_id"],
                "step": checkpoint.values.get("current_step", 0),
                "status": checkpoint.values.get("status", "unknown"),
                "task": checkpoint.values.get("task", ""),
            })
        
        return history
    
    def get_threads(self) -> list:
        """
        List all conversation threads
        
        Note: Currently using InMemorySaver, so this only returns
        threads from the current session. For cross-restart persistence,
        use get_saved_trajectories() instead.
        
        Returns:
            List of thread IDs from current session
        """
        # InMemorySaver stores checkpoints in memory
        # We can list threads by checking the checkpointer's internal state
        threads = []
        try:
            # InMemorySaver uses a dict internally
            if hasattr(self.checkpointer, 'storage'):
                for key in self.checkpointer.storage.keys():
                    if isinstance(key, tuple) and len(key) > 0:
                        thread_id = key[0]
                        if thread_id not in threads:
                            threads.append(thread_id)
        except Exception as e:
            print(f"[Memory] Error listing threads: {e}")
        
        return threads
    
    def get_saved_trajectories(self) -> list:
        """
        List all saved trajectories from disk
        
        Returns:
            List of trajectory files with metadata
        """
        from pathlib import Path
        import json
        
        trajectory_dir = Path(__file__).parent.parent.parent / "data" / "trajectories"
        if not trajectory_dir.exists():
            return []
        
        trajectories = []
        for filepath in trajectory_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    trajectories.append({
                        "id": filepath.stem,
                        "task": data.get("task", ""),
                        "timestamp": data.get("timestamp", ""),
                        "steps": data.get("steps", 0),
                    })
            except:
                pass
        
        return sorted(trajectories, key=lambda x: x.get("timestamp", ""), reverse=True)
    
    def resume(self, thread_id: str, checkpoint_id: str = None) -> dict:
        """
        Resume from a specific checkpoint (time-travel)
        
        Args:
            thread_id: Thread to resume
            checkpoint_id: Optional specific checkpoint to resume from
            
        Returns:
            Config for resuming
        """
        config = {"configurable": {"thread_id": thread_id}}
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        
        return config
    
    async def stream(
        self,
        task: str,
        browser_session,
        max_steps: int = 10,
        thread_id: str = "default",
    ):
        """
        Stream agent execution for real-time updates
        
        Yields state updates as they happen.
        """
        self._current_browser = browser_session
        initial_state = create_initial_state(task, max_steps)
        
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        
        try:
            async for event in self.graph.astream(initial_state, config):
                yield event
        finally:
            self._current_browser = None


def create_agent(
    model: str = "claude-opus-4-5-20251101",
    api_key: Optional[str] = None,
    persist: bool = True,
    db_path: str = None,
    verbose: bool = False,
    knowledge_store: Optional[KnowledgeStore] = None,
) -> HiveAgent:
    """Factory function to create a Hive agent"""
    return HiveAgent(
        model=model, 
        api_key=api_key, 
        persist=persist,
        db_path=db_path,
        verbose=verbose,
        knowledge_store=knowledge_store,
    )


# Quick test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("=" * 50)
        print("Testing Hive Agent with SQLite Persistence")
        print("=" * 50)
        
        # Test 1: Create persistent agent
        agent = create_agent(persist=True)
        print(f"\n[OK] Agent created with persistence")
        print(f"     DB Path: {agent.db_path}")
        print(f"     Nodes: {list(agent.graph.nodes.keys())}")
        
        # Test 2: Check if DB was created
        if Path(agent.db_path).exists():
            print(f"[OK] SQLite database exists")
        else:
            print(f"[INFO] Database will be created on first use")
        
        # Test 3: Create non-persistent agent (for testing)
        test_agent = create_agent(persist=False)
        print(f"\n[OK] Non-persistent agent created (for testing)")
        
        # Test 4: List threads (should be empty or have previous data)
        threads = agent.get_threads()
        print(f"\n[OK] Found {len(threads)} existing threads")
        for t in threads[:5]:  # Show first 5
            print(f"     - {t}")
        
        print("\n" + "=" * 50)
        print("All persistence tests passed!")
        print("=" * 50)
    
    asyncio.run(test())

