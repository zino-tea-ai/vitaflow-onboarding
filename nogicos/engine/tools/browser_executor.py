# -*- coding: utf-8 -*-
"""
NogicOS Browser Executor - 基于 Browser Use 的浏览器自动化

集成 Browser Use 到 NogicOS，禁用所有第三方品牌标识
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class BrowserTaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class BrowserTaskResult:
    status: BrowserTaskStatus
    message: str
    extracted_content: Optional[str] = None
    duration: float = 0.0
    steps_count: int = 0


class NogicBrowserExecutor:
    """
    NogicOS 浏览器执行器 - 封装 Browser Use，移除所有品牌标识
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._agent = None
        self._browser_session = None
        self._initialized = False
        self._branding_disabled = False
    
    def _disable_branding(self):
        """禁用 Browser Use 的所有品牌标识和动画"""
        if self._branding_disabled:
            return
            
        try:
            # 禁用 about:blank 页面的 DVD screensaver 动画
            from browser_use.browser.watchdogs import aboutblank_watchdog
            
            # 替换动画注入方法为空操作
            async def _noop_animation(*args, **kwargs):
                pass
            
            aboutblank_watchdog.AboutBlankWatchdog._show_dvd_screensaver_loading_animation_cdp = _noop_animation
            aboutblank_watchdog.AboutBlankWatchdog._show_dvd_screensaver_on_about_blank_tabs = _noop_animation
            
            logger.info("[NogicBrowser] Disabled Browser Use branding (DVD screensaver)")
            self._branding_disabled = True
            
        except Exception as e:
            logger.warning(f"[NogicBrowser] Could not disable branding: {e}")
        
    async def _ensure_initialized(self):
        """懒加载初始化"""
        if self._initialized:
            return
            
        try:
            # 导入 Browser Use 组件
            from browser_use import Agent, ChatAnthropic
            from browser_use.browser import BrowserProfile, BrowserSession
            
            # === 禁用 Browser Use 的品牌标识 ===
            self._disable_branding()
            
            # 设置 API Key
            if self.api_key:
                os.environ["ANTHROPIC_API_KEY"] = self.api_key
            
            # 创建干净的 BrowserProfile - 禁用所有视觉效果
            self._profile = BrowserProfile(
                headless=False,
                # 禁用元素高亮（hover 动画）
                highlight_elements=False,
                dom_highlight_elements=False,
                # 禁用 demo 模式
                demo_mode=False,
                # 其他设置
                disable_security=True,
            )
            
            # 创建 LLM
            self._llm = ChatAnthropic(
                model='claude-sonnet-4-20250514',
                temperature=0.0
            )
            
            self._initialized = True
            logger.info("[NogicBrowser] Browser executor initialized (clean mode)")
            
        except ImportError as e:
            logger.error(f"[NogicBrowser] Failed to import browser-use: {e}")
            raise RuntimeError("browser-use not installed. Run: pip install browser-use")
    
    async def execute(
        self, 
        task: str, 
        start_url: Optional[str] = None,
        timeout: int = 120
    ) -> BrowserTaskResult:
        """
        执行浏览器任务
        
        Args:
            task: 任务描述
            start_url: 起始 URL（避免显示 about:blank 动画）
            timeout: 超时时间（秒）
        """
        import time
        start_time = time.time()
        
        try:
            await self._ensure_initialized()
            
            from browser_use import Agent
            from browser_use.browser import BrowserSession
            
            # 创建新的 BrowserSession
            browser_session = BrowserSession(browser_profile=self._profile)
            
            # 如果有起始 URL，修改任务让它先导航
            full_task = task
            if start_url:
                full_task = f"First navigate to {start_url}, then: {task}"
            
            # 创建 Agent
            agent = Agent(
                task=full_task,
                llm=self._llm,
                browser_session=browser_session,
            )
            
            logger.info(f"[NogicBrowser] Executing task: {task[:50]}...")
            
            # 执行任务
            result = await asyncio.wait_for(
                agent.run(),
                timeout=timeout
            )
            
            duration = time.time() - start_time
            
            # 解析结果 (Browser Use 0.11.x API)
            success = result.is_successful() if hasattr(result, 'is_successful') else True
            extracted = result.extracted_content() if hasattr(result, 'extracted_content') else ""
            final = result.final_result() if hasattr(result, 'final_result') else None
            steps = result.number_of_steps() if hasattr(result, 'number_of_steps') else 0
            
            message = final or extracted or "Task completed"
            if isinstance(message, str) and len(message) > 500:
                message = message[:500] + "..."
            
            return BrowserTaskResult(
                status=BrowserTaskStatus.SUCCESS if success else BrowserTaskStatus.FAILED,
                message=str(message),
                extracted_content=str(extracted) if extracted else None,
                duration=duration,
                steps_count=steps
            )
            
        except asyncio.TimeoutError:
            return BrowserTaskResult(
                status=BrowserTaskStatus.TIMEOUT,
                message=f"Task timed out after {timeout}s",
                duration=timeout
            )
        except Exception as e:
            logger.error(f"[NogicBrowser] Task failed: {e}")
            return BrowserTaskResult(
                status=BrowserTaskStatus.FAILED,
                message=str(e),
                duration=time.time() - start_time
            )
        finally:
            # 清理浏览器会话
            if browser_session:
                try:
                    await browser_session.close()
                except:
                    pass


# 全局单例
_executor: Optional[NogicBrowserExecutor] = None


def get_browser_executor(api_key: Optional[str] = None) -> NogicBrowserExecutor:
    """获取浏览器执行器单例"""
    global _executor
    if _executor is None:
        _executor = NogicBrowserExecutor(api_key)
    return _executor


def register_browser_executor_tools(registry):
    """
    注册 Browser Use 浏览器自动化工具到 NogicOS Registry
    （AI 视觉驱动，用于复杂网页操作）
    """
    from .base import ToolCategory
    
    @registry.action(
        description="""Execute a browser automation task using AI vision.
        
Use this for:
- Navigating websites and filling forms
- Clicking buttons and links
- Extracting information from web pages
- Any task requiring browser interaction

Args:
    task: Natural language description of what to do in the browser
    url: Optional starting URL (if the page isn't already open)
    
Returns:
    Result with success status, extracted content, and execution details""",
        category=ToolCategory.LOCAL,
    )
    async def browser_task(task: str, url: str = "") -> Dict[str, Any]:
        """Execute a browser task using AI vision."""
        logger.info(f"[Browser Tool] Executing: {task}")
        
        try:
            executor = get_browser_executor()
            result = await executor.execute(
                task=task,
                start_url=url if url else None
            )
            
            return {
                "success": result.status == BrowserTaskStatus.SUCCESS,
                "status": result.status.value,
                "message": result.message,
                "extracted_content": result.extracted_content,
                "steps_count": result.steps_count,
                "duration_seconds": round(result.duration, 1),
            }
        except Exception as e:
            logger.error(f"[Browser Tool] Error: {e}")
            return {
                "success": False,
                "status": "error",
                "message": str(e),
            }
    
    logger.info("[NogicBrowser] Browser tools registered")


# 测试函数
async def test_browser():
    """快速测试浏览器执行器"""
    import sys
    sys.path.insert(0, r"C:\Users\WIN\Desktop\Cursor Project\nogicos")
    from api_keys import ANTHROPIC_API_KEY
    
    executor = NogicBrowserExecutor(api_key=ANTHROPIC_API_KEY)
    result = await executor.execute(
        task="Search for 'NogicOS' on Google",
        start_url="https://google.com"
    )
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(test_browser())
