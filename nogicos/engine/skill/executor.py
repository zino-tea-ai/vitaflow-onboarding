# -*- coding: utf-8 -*-
"""
Skill Executor - Execute parameterized skills with dynamic parameters

Flow:
    1. Receive skill code + parameters
    2. Create execution namespace with page and utilities
    3. Execute skill function with parameters
    4. Handle errors and timeouts
    5. Return result

Reference: SkillWeaver paper (arXiv:2504.07079)
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger("nogicos.skill.executor")


@dataclass
class ExecutionResult:
    """Result of skill execution"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class SkillExecutor:
    """
    Execute parameterized skills
    
    Usage:
        executor = SkillExecutor(page)
        result = await executor.execute(
            code=skill.code,
            function_name=skill.name,
            params={"query": "AI news"},
        )
    """
    
    def __init__(
        self,
        page,
        timeout: float = 60.0,
    ):
        """
        Initialize executor
        
        Args:
            page: Playwright Page object
            timeout: Execution timeout in seconds
        """
        self.page = page
        self.timeout = timeout
    
    async def execute(
        self,
        code: str,
        function_name: str,
        params: Dict[str, Any] = None,
    ) -> ExecutionResult:
        """
        Execute a skill with parameters
        
        Args:
            code: Python code containing the skill function
            function_name: Name of the function to call
            params: Dictionary of parameters to pass
        
        Returns:
            ExecutionResult with success status and result/error
        """
        import time
        start_time = time.time()
        
        params = params or {}
        
        try:
            # Create execution namespace
            namespace = self._create_namespace()
            
            # Execute the code to define the function
            exec(code, namespace)
            
            # Check if function exists
            if function_name not in namespace:
                return ExecutionResult(
                    success=False,
                    error=f"Function '{function_name}' not found in code",
                    duration_ms=(time.time() - start_time) * 1000,
                )
            
            func = namespace[function_name]
            
            # Check if it's callable
            if not callable(func):
                return ExecutionResult(
                    success=False,
                    error=f"'{function_name}' is not callable",
                    duration_ms=(time.time() - start_time) * 1000,
                )
            
            # Execute with timeout
            logger.info(f"[Executor] Running {function_name} with params: {params}")
            
            result = await asyncio.wait_for(
                func(self.page, **params),
                timeout=self.timeout,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"[Executor] Success in {duration_ms:.0f}ms")
            
            return ExecutionResult(
                success=True,
                result=result,
                duration_ms=duration_ms,
            )
            
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[Executor] Timeout after {duration_ms:.0f}ms")
            return ExecutionResult(
                success=False,
                error=f"Execution timed out after {self.timeout}s",
                duration_ms=duration_ms,
            )
            
        except TypeError as e:
            # Usually parameter mismatch
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[Executor] Parameter error: {e}")
            return ExecutionResult(
                success=False,
                error=f"Parameter error: {e}",
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[Executor] Error: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
    
    def _create_namespace(self) -> Dict[str, Any]:
        """
        Create execution namespace with utilities
        
        Provides:
            - page: Playwright Page object
            - asyncio: For async utilities
            - Common imports
        """
        return {
            "page": self.page,
            "asyncio": asyncio,
            # Add common utilities that skills might need
            "__builtins__": __builtins__,
        }
    
    async def execute_skill(
        self,
        skill: "Skill",
        params: Dict[str, Any] = None,
    ) -> ExecutionResult:
        """
        Execute a Skill object directly
        
        Args:
            skill: Skill object from knowledge store
            params: Parameters to pass to the skill
        
        Returns:
            ExecutionResult
        """
        # Import here to avoid circular imports
        from engine.knowledge.store import Skill
        
        if not isinstance(skill, Skill):
            return ExecutionResult(
                success=False,
                error="Invalid skill object",
            )
        
        return await self.execute(
            code=skill.code,
            function_name=skill.name,
            params=params,
        )


class SkillExecutorWithFallback(SkillExecutor):
    """
    Skill executor with fallback to AI agent on failure
    
    If skill execution fails, can optionally fall back to AI execution.
    """
    
    def __init__(
        self,
        page,
        timeout: float = 60.0,
        fallback_enabled: bool = True,
    ):
        super().__init__(page, timeout)
        self.fallback_enabled = fallback_enabled
    
    async def execute_with_fallback(
        self,
        skill: "Skill",
        params: Dict[str, Any],
        fallback_callback=None,
    ) -> ExecutionResult:
        """
        Execute skill with optional fallback
        
        Args:
            skill: Skill to execute
            params: Parameters
            fallback_callback: Async function to call on failure
        
        Returns:
            ExecutionResult
        """
        # Try skill execution first
        result = await self.execute_skill(skill, params)
        
        if result.success:
            return result
        
        # Skill failed - consider fallback
        if self.fallback_enabled and fallback_callback:
            logger.warning(f"[Executor] Skill failed, falling back to AI: {result.error}")
            try:
                fallback_result = await fallback_callback()
                return ExecutionResult(
                    success=True,
                    result=fallback_result,
                    error=f"Fallback used (skill error: {result.error})",
                    duration_ms=result.duration_ms,
                )
            except Exception as e:
                logger.error(f"[Executor] Fallback also failed: {e}")
                return ExecutionResult(
                    success=False,
                    error=f"Both skill and fallback failed: {result.error}; {e}",
                    duration_ms=result.duration_ms,
                )
        
        return result


# =============================================================================
# Quick Test
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test_executor():
        print("=" * 50)
        print("Skill Executor Test")
        print("=" * 50)
        
        # Create a mock page object for testing
        class MockPage:
            async def fill(self, selector, value):
                print(f"    [Mock] fill({selector}, {value})")
            
            async def click(self, selector):
                print(f"    [Mock] click({selector})")
            
            async def wait_for_load_state(self, state):
                print(f"    [Mock] wait_for_load_state({state})")
        
        mock_page = MockPage()
        executor = SkillExecutor(mock_page)
        
        # Test 1: Execute simple skill
        print("\n[1] Testing simple skill execution...")
        code = '''
async def search_hn(page, query: str):
    """Search on Hacker News"""
    await page.fill("input.search", query)
    await page.click("button[type=submit]")
    return f"Searched for: {query}"
'''
        result = await executor.execute(
            code=code,
            function_name="search_hn",
            params={"query": "AI news"},
        )
        print(f"    Success: {result.success}")
        print(f"    Result: {result.result}")
        print(f"    Duration: {result.duration_ms:.0f}ms")
        
        # Test 2: Missing function
        print("\n[2] Testing missing function...")
        result = await executor.execute(
            code="async def other_func(page): pass",
            function_name="nonexistent",
            params={},
        )
        print(f"    Success: {result.success}")
        print(f"    Error: {result.error}")
        
        # Test 3: Parameter error
        print("\n[3] Testing parameter error...")
        code = '''
async def requires_params(page, required_param: str):
    """Requires a parameter"""
    return required_param
'''
        result = await executor.execute(
            code=code,
            function_name="requires_params",
            params={},  # Missing required_param
        )
        print(f"    Success: {result.success}")
        print(f"    Error: {result.error}")
        
        # Test 4: Skill with default params
        print("\n[4] Testing skill with defaults...")
        code = '''
async def with_defaults(page, query: str = "default"):
    """Has default parameter"""
    return f"Query: {query}"
'''
        result = await executor.execute(
            code=code,
            function_name="with_defaults",
            params={},  # Uses default
        )
        print(f"    Success: {result.success}")
        print(f"    Result: {result.result}")
        
        print("\n" + "=" * 50)
        print("Executor Test Complete!")
        print("=" * 50)
    
    asyncio.run(test_executor())

