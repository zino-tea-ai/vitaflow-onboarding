"""
Phase 3 测试 - Agent 循环 + 错误恢复 + 并发控制 + TerminationChecker
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Phase 3 imports - 使用绝对导入
from nogicos.engine.agent.concurrency import (
    ConcurrencyManager, ConcurrencyConfig,
    get_concurrency_manager, set_concurrency_manager,
)
from nogicos.engine.agent.termination import (
    TerminationChecker, TerminationConfig, TerminationResult,
    TerminationReason, TerminationType, SuccessVerifier,
    detect_set_task_status,
)
from nogicos.engine.agent.host_agent import HostAgent, AgentConfig
from nogicos.engine.agent.types import ToolResult


class TestConcurrencyManager:
    """测试并发管理器"""
    
    @pytest.fixture
    def manager(self):
        """创建测试用并发管理器"""
        config = ConcurrencyConfig(
            max_concurrent_tasks=2,
            max_api_concurrency=3,
        )
        return ConcurrencyManager(config)
    
    @pytest.mark.asyncio
    async def test_acquire_task_slot_success(self, manager):
        """测试成功获取任务槽位"""
        result = await manager.acquire_task_slot("task-1")
        assert result is True
        assert len(manager.get_active_tasks()) == 1
    
    @pytest.mark.asyncio
    async def test_acquire_task_slot_limit(self, manager):
        """测试任务槽位限制"""
        await manager.acquire_task_slot("task-1")
        await manager.acquire_task_slot("task-2")
        
        # 第三个应该失败
        result = await manager.acquire_task_slot("task-3")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_release_task_slot(self, manager):
        """测试释放任务槽位"""
        await manager.acquire_task_slot("task-1")
        manager.release_task_slot("task-1")
        
        assert len(manager.get_active_tasks()) == 0
    
    @pytest.mark.asyncio
    async def test_window_lock_acquire_release(self, manager):
        """测试窗口锁获取和释放"""
        hwnd = 12345
        
        acquired = await manager.acquire_window(hwnd, "task-1", timeout=1.0)
        assert acquired is True
        assert manager.is_window_locked(hwnd) is True
        assert manager.get_window_owner(hwnd) == "task-1"
        
        manager.release_window(hwnd)
        assert manager.is_window_locked(hwnd) is False
    
    @pytest.mark.asyncio
    async def test_window_lock_context_manager(self, manager):
        """测试窗口锁上下文管理器"""
        hwnd = 12345
        
        async with manager.window_lock(hwnd, "task-1"):
            assert manager.is_window_locked(hwnd) is True
        
        assert manager.is_window_locked(hwnd) is False
    
    @pytest.mark.asyncio
    async def test_api_slot_concurrency(self, manager):
        """测试 API 槽位并发限制"""
        results = []
        
        async def api_call(n):
            async with manager.api_slot():
                results.append(f"start-{n}")
                await asyncio.sleep(0.1)
                results.append(f"end-{n}")
        
        # 同时启动 5 个调用，但只有 3 个槽位
        await asyncio.gather(*[api_call(i) for i in range(5)])
        
        # 所有调用都应该完成
        assert len([r for r in results if r.startswith("end")]) == 5
    
    @pytest.mark.asyncio
    async def test_batch_window_acquire(self, manager):
        """测试批量获取窗口锁"""
        hwnds = {111, 222, 333}
        
        result = await manager.acquire_windows(hwnds, "task-1")
        assert result is True
        
        for hwnd in hwnds:
            assert manager.is_window_locked(hwnd) is True
        
        manager.release_windows(hwnds)
        
        for hwnd in hwnds:
            assert manager.is_window_locked(hwnd) is False


class TestTerminationChecker:
    """测试终止检查器"""
    
    @pytest.fixture
    def checker(self):
        """创建测试用终止检查器"""
        config = TerminationConfig(
            max_iterations=10,
            task_timeout_s=60.0,
            max_consecutive_failures=3,
        )
        return TerminationChecker(config)
    
    def test_continue_running(self, checker):
        """测试继续运行"""
        result = checker.check(
            iteration=1,
            tool_results=[],
            set_task_status_called=False,
            window_exists=True,
            elapsed_time_s=10.0,
        )
        
        assert result.should_terminate is False
    
    def test_set_task_status_completed(self, checker):
        """测试 set_task_status(completed)"""
        result = checker.check(
            iteration=1,
            tool_results=[],
            set_task_status_called=True,
            set_task_status_value="completed",
        )
        
        assert result.should_terminate is True
        assert result.reason == TerminationReason.COMPLETED
        assert result.termination_type == TerminationType.SUCCESS
    
    def test_set_task_status_needs_help(self, checker):
        """测试 set_task_status(needs_help)"""
        result = checker.check(
            iteration=1,
            tool_results=[],
            set_task_status_called=True,
            set_task_status_value="needs_help",
        )
        
        assert result.should_terminate is True
        assert result.reason == TerminationReason.NEEDS_HELP
    
    def test_max_iterations(self, checker):
        """测试最大迭代次数"""
        result = checker.check(
            iteration=10,  # 等于 max_iterations
            tool_results=[],
        )
        
        assert result.should_terminate is True
        assert result.reason == TerminationReason.MAX_ITERATIONS
    
    def test_timeout(self, checker):
        """测试超时"""
        result = checker.check(
            iteration=1,
            tool_results=[],
            elapsed_time_s=61.0,  # 超过 60s
        )
        
        assert result.should_terminate is True
        assert result.reason == TerminationReason.TIMEOUT
    
    def test_window_lost(self, checker):
        """测试窗口丢失"""
        result = checker.check(
            iteration=1,
            tool_results=[],
            window_exists=False,
        )
        
        assert result.should_terminate is True
        assert result.reason == TerminationReason.WINDOW_LOST
        assert result.termination_type == TerminationType.ERROR
    
    def test_consecutive_failures(self, checker):
        """测试连续失败"""
        # 创建带错误的 ToolResult
        error_result = ToolResult.failure("test error")
        
        # 连续 3 次失败
        for i in range(3):
            result = checker.check(
                iteration=i,
                tool_results=[error_result],
            )
        
        assert result.should_terminate is True
        assert result.reason == TerminationReason.CONSECUTIVE_FAILURES
    
    def test_user_cancel(self, checker):
        """测试用户取消"""
        checker.cancel()
        
        result = checker.check(iteration=1, tool_results=[])
        
        assert result.should_terminate is True
        assert result.reason == TerminationReason.USER_CANCELLED
        assert result.termination_type == TerminationType.CANCELLED
    
    def test_reset(self, checker):
        """测试重置"""
        checker.cancel()
        checker.reset()
        
        result = checker.check(iteration=1, tool_results=[])
        assert result.should_terminate is False


class TestDetectSetTaskStatus:
    """测试 set_task_status 检测"""
    
    def test_detect_completed(self):
        """检测 completed 状态"""
        tool_calls = [
            {"name": "click", "arguments": {"x": 100, "y": 200}},
            {"name": "set_task_status", "arguments": {"status": "completed", "description": "Done"}},
        ]
        
        result = detect_set_task_status(tool_calls)
        
        assert result is not None
        assert result.status == "completed"
        assert result.description == "Done"
    
    def test_detect_needs_help(self):
        """检测 needs_help 状态"""
        tool_calls = [
            {"name": "set_task_status", "arguments": {"status": "needs_help", "description": "Stuck"}},
        ]
        
        result = detect_set_task_status(tool_calls)
        
        assert result is not None
        assert result.status == "needs_help"
    
    def test_no_set_task_status(self):
        """无 set_task_status 调用"""
        tool_calls = [
            {"name": "click", "arguments": {"x": 100, "y": 200}},
            {"name": "type", "arguments": {"text": "hello"}},
        ]
        
        result = detect_set_task_status(tool_calls)
        
        assert result is None


class TestSuccessVerifier:
    """测试成功验证器"""
    
    @pytest.fixture
    def verifier(self):
        """创建测试用验证器"""
        return SuccessVerifier(min_confidence=0.7)
    
    @pytest.mark.asyncio
    async def test_verify_no_client(self, verifier):
        """无 LLM 客户端时默认通过"""
        result = await verifier.verify(
            task="test task",
            final_screenshot="base64data",
            tool_history=[],
            llm_client=None,
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_verify_no_screenshot(self, verifier):
        """无截图时默认通过"""
        result = await verifier.verify(
            task="test task",
            final_screenshot=None,
            tool_history=[],
            llm_client=MagicMock(),
        )
        
        assert result is True


class TestHostAgentPhase3:
    """测试 HostAgent Phase 3 功能"""
    
    @pytest.fixture
    def config(self):
        """创建测试配置"""
        return AgentConfig(
            max_iterations=5,
            max_concurrent_tasks=2,
            task_timeout_s=30.0,
            verify_success=False,  # 测试时禁用验证
        )
    
    @pytest.mark.asyncio
    async def test_config_conversion(self, config):
        """测试配置转换"""
        term_config = config.to_termination_config()
        assert term_config.max_iterations == 5
        assert term_config.task_timeout_s == 30.0
        
        conc_config = config.to_concurrency_config()
        assert conc_config.max_concurrent_tasks == 2


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
