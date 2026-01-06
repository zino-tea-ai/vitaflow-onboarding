"""
NogicOS 增量检查点
==================

减少序列化开销，优化状态持久化性能。

策略:
1. 计算状态差异，只保存变化部分
2. 定期做全量检查点
3. 恢复时合并增量

参考:
- LangGraph Checkpointer
- Git 增量提交
"""

import json
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CheckpointDelta:
    """检查点增量"""
    iteration: int
    new_messages: List[dict] = field(default_factory=list)
    status_change: Optional[str] = None
    last_tool_result: Optional[dict] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        result = {"iteration": self.iteration}
        if self.new_messages:
            result["new_messages"] = self.new_messages
        if self.status_change:
            result["status_change"] = self.status_change
        if self.last_tool_result:
            result["last_tool_result"] = self.last_tool_result
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class IncrementalCheckpointer:
    """
    增量检查点管理器
    
    减少序列化和存储开销:
    - 每次只保存变化的消息
    - 每 N 次增量后做一次全量
    - 恢复时自动合并
    
    使用示例:
    ```python
    checkpointer = IncrementalCheckpointer(task_store)
    
    # 保存检查点（自动选择增量/全量）
    await checkpointer.save(task_id, current_state)
    
    # 恢复检查点
    state = await checkpointer.restore(task_id)
    ```
    """
    
    # 每 10 次增量后做全量
    FULL_CHECKPOINT_INTERVAL = 10
    
    def __init__(self, task_store):
        """
        初始化增量检查点管理器
        
        Args:
            task_store: 任务存储实例 (AsyncTaskStore)
        """
        self.task_store = task_store
        self._last_state: Dict[str, dict] = {}  # task_id -> last_state
        self._delta_count: Dict[str, int] = {}  # task_id -> delta_count
    
    async def save(self, task_id: str, state: dict) -> bool:
        """
        保存检查点（自动选择增量/全量）
        
        Args:
            task_id: 任务 ID
            state: 当前状态
            
        Returns:
            是否保存成功
        """
        last_state = self._last_state.get(task_id, {})
        delta_count = self._delta_count.get(task_id, 0)
        
        # 判断是否需要全量
        needs_full = (
            delta_count >= self.FULL_CHECKPOINT_INTERVAL or
            task_id not in self._last_state
        )
        
        if needs_full:
            # 全量保存
            await self.task_store.save_checkpoint(
                task_id,
                state.get("iteration", 0),
                state,
                is_full=True
            )
            self._last_state[task_id] = self._deep_copy(state)
            self._delta_count[task_id] = 0
            logger.debug(f"Full checkpoint saved for task {task_id}")
        else:
            # 计算并保存增量
            delta = self._compute_delta(last_state, state)
            
            if delta:
                await self.task_store.save_checkpoint(
                    task_id,
                    state.get("iteration", 0),
                    delta,
                    is_full=False
                )
                # 更新本地缓存
                self._apply_delta(self._last_state[task_id], delta)
                self._delta_count[task_id] = delta_count + 1
                logger.debug(f"Incremental checkpoint saved for task {task_id} (delta #{delta_count + 1})")
            else:
                logger.debug(f"No changes to checkpoint for task {task_id}")
        
        return True
    
    def _compute_delta(self, old_state: dict, new_state: dict) -> Optional[dict]:
        """
        计算状态差异
        
        Args:
            old_state: 旧状态
            new_state: 新状态
            
        Returns:
            差异字典，如果无变化则返回 None
        """
        delta = {}
        
        # 检查消息增量
        old_messages = old_state.get("messages", [])
        new_messages = new_state.get("messages", [])
        
        if len(new_messages) > len(old_messages):
            delta["new_messages"] = new_messages[len(old_messages):]
        
        # 检查状态变化
        for key in ["status", "iteration", "last_tool_result", "current_hwnd"]:
            old_val = old_state.get(key)
            new_val = new_state.get(key)
            if new_val != old_val:
                delta[key] = new_val
        
        # 检查 agent_status 变化
        old_agent_status = old_state.get("agent_status")
        new_agent_status = new_state.get("agent_status")
        if new_agent_status != old_agent_status:
            delta["agent_status"] = new_agent_status
        
        return delta if delta else None
    
    def _apply_delta(self, state: dict, delta: dict):
        """
        将增量应用到状态
        
        Args:
            state: 要更新的状态（原地修改）
            delta: 增量数据
        """
        if "new_messages" in delta:
            if "messages" not in state:
                state["messages"] = []
            state["messages"].extend(delta["new_messages"])
        
        for key in ["status", "iteration", "last_tool_result", "current_hwnd", "agent_status"]:
            if key in delta:
                state[key] = delta[key]
    
    def _deep_copy(self, obj: Any) -> Any:
        """深拷贝（使用 JSON 序列化）"""
        return json.loads(json.dumps(obj))
    
    async def restore(self, task_id: str) -> Optional[dict]:
        """
        恢复检查点（合并全量 + 增量）
        
        Args:
            task_id: 任务 ID
            
        Returns:
            恢复的状态，如果没有检查点则返回 None
        """
        checkpoints = await self.task_store.get_all_checkpoints(task_id)
        
        if not checkpoints:
            return None
        
        # 找到最近的全量检查点
        full_checkpoint = None
        deltas = []
        
        for cp in reversed(checkpoints):
            if cp.get("is_full"):
                full_checkpoint = cp.get("state")
                break
            else:
                deltas.insert(0, cp.get("state"))
        
        if not full_checkpoint:
            # 没有全量检查点，尝试使用第一个增量
            if deltas:
                logger.warning(f"No full checkpoint found for task {task_id}, using first delta")
                full_checkpoint = deltas[0]
                deltas = deltas[1:]
            else:
                return None
        
        # 应用所有增量
        state = self._deep_copy(full_checkpoint)
        for delta in deltas:
            self._apply_delta(state, delta)
        
        # 更新本地缓存
        self._last_state[task_id] = state
        self._delta_count[task_id] = len(deltas)
        
        logger.info(f"Restored checkpoint for task {task_id} (full + {len(deltas)} deltas)")
        return state
    
    def clear_cache(self, task_id: str = None):
        """
        清除本地缓存
        
        Args:
            task_id: 指定任务 ID，或 None 清除所有
        """
        if task_id:
            self._last_state.pop(task_id, None)
            self._delta_count.pop(task_id, None)
        else:
            self._last_state.clear()
            self._delta_count.clear()
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "cached_tasks": len(self._last_state),
            "delta_counts": dict(self._delta_count),
        }


# ========== 工厂函数 ==========

def create_checkpointer(task_store) -> IncrementalCheckpointer:
    """创建增量检查点管理器"""
    return IncrementalCheckpointer(task_store)
