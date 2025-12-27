# -*- coding: utf-8 -*-
"""
NogicOS Hive Server - HTTP + WebSocket API

Provides HTTP endpoints for task execution and WebSocket for real-time status updates.

Architecture:
    HTTP (8080)          WebSocket (8765)
        |                     |
        v                     v
    /execute  ─────────►  broadcast status
    /stats                    |
                              v
                         Electron UI

Usage:
    python hive_server.py
    
    # Then in another terminal:
    curl -X POST http://localhost:8080/execute \
         -H "Content-Type: application/json" \
         -d '{"task": "Search for AI", "url": "https://news.ycombinator.com"}'
"""

import warnings
import asyncio
import os
import sys
import json
import time
import logging
from typing import Optional
from contextlib import asynccontextmanager

# Filter known deprecation warnings that don't affect functionality
# These are from dependencies and will be fixed in future versions
warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality isn't compatible")
warnings.filterwarnings("ignore", message="ForwardRef._evaluate is a private API")
warnings.filterwarnings("ignore", message="websockets.server.WebSocketServerProtocol is deprecated")
warnings.filterwarnings("ignore", message="websockets.legacy is deprecated")

# Ensure UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# Setup logging using observability module
from engine.observability import setup_logging, get_logger
setup_logging(level="INFO")
logger = get_logger("hive_server")

# FastAPI imports
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    logger.error("FastAPI not installed. Run: pip install fastapi uvicorn")
    sys.exit(1)

# NogicOS imports
from engine.knowledge.store import KnowledgeStore, Skill
from engine.learning.passive import SmartRouter, ReplayExecutor, RouteResult
from engine.hive.graph import create_agent
from engine.server.websocket import StatusServer
from engine.skill.executor import SkillExecutor
from engine.skill.synthesizer import SkillSynthesizer
from engine.stream.screenshot import EventDrivenStreamer, StreamConfig
from engine.browser.cdp_session import CDPBrowserSession
from engine.browser.cdp_client import CDPClient


# ============================================================================
# Request/Response Models
# ============================================================================

class ExecuteRequest(BaseModel):
    """Task execution request"""
    task: str
    url: str = "https://news.ycombinator.com"
    max_steps: int = 10
    headless: bool = True  # Default headless for server mode
    use_cdp: bool = False  # Use CDP mode (Electron internal control) instead of Playwright


class ExecuteResponse(BaseModel):
    """Task execution response"""
    success: bool
    result: Optional[str] = None
    path: str  # "skill", "fast", or "normal"
    time_seconds: float
    confidence: float
    steps: int = 0
    error: Optional[str] = None
    skill_name: Optional[str] = None  # Name of skill used (if skill path)


class StatsResponse(BaseModel):
    """Knowledge store statistics"""
    total_trajectories: int
    successful: int
    success_rate: float
    domains: int
    total_skills: int = 0  # Number of learned skills


class StatusResponse(BaseModel):
    """Server status"""
    status: str
    version: str = "0.1.0"
    knowledge_count: int
    websocket_port: int


# ============================================================================
# NogicOS Engine
# ============================================================================

class HiveEngine:
    """
    Core engine that handles task execution
    """
    
    def __init__(self):
        logger.info("Initializing Hive Engine...")
        
        # Shared knowledge store
        self.knowledge_store = KnowledgeStore()
        
        # Smart router with skill support
        self.router = SmartRouter(
            knowledge_store=self.knowledge_store,
            confidence_threshold=0.7,
            prefer_skills=True,  # Enable skill path
        )
        
        # AI Agent (lazy init to avoid API key issues at startup)
        self._agent = None
        
        # Skill synthesizer (lazy init)
        self._synthesizer = None
        
        # Status server for WebSocket
        self.status_server = StatusServer(port=8765)
        
        # Execution state
        self._executing = False
        self._current_task = None
        
        logger.info(f"Engine ready. Knowledge: {self.knowledge_store.count()} trajectories")
    
    @property
    def agent(self):
        """Lazy agent initialization"""
        if self._agent is None:
            self._agent = create_agent(
                verbose=False,
                knowledge_store=self.knowledge_store,
            )
        return self._agent
    
    @property
    def synthesizer(self):
        """Lazy skill synthesizer initialization"""
        if self._synthesizer is None:
            self._synthesizer = SkillSynthesizer(max_retries=2)
        return self._synthesizer
    
    async def start_websocket(self):
        """Start WebSocket server"""
        await self.status_server.start()
        logger.info(f"WebSocket server started on port {self.status_server.port}")
    
    async def stop_websocket(self):
        """Stop WebSocket server"""
        await self.status_server.stop()
    
    async def execute(self, request: ExecuteRequest, timeout: float = 120.0) -> ExecuteResponse:
        """
        Execute a task with automatic fast/normal path routing
        
        Args:
            request: Task request
            timeout: Maximum execution time in seconds (default 120s = 2 minutes)
        """
        if self._executing:
            raise HTTPException(status_code=409, detail="Another task is executing")
        
        self._executing = True
        self._current_task = request.task
        start_time = time.time()
        
        try:
            # Broadcast: starting
            self.status_server.update_agent(
                state="thinking",
                task=request.task,
            )
            
            # Step 1: Route the task
            logger.info(f"Routing task: {request.task[:50]}...")
            route_result = await self.router.route(request.task, request.url)
            logger.info(f"Route: {route_result.path} (confidence: {route_result.confidence:.0%})")
            
            # Broadcast: route decision
            self.status_server.update_agent(
                state="acting" if route_result.is_fast() else "thinking",
                task=request.task,
                progress=0.2,
            )
            
            # Step 2: Execute based on route
            skill_name = None
            if route_result.path == "skill":
                result, skill_name = await self._execute_skill_path(request, route_result)
            elif route_result.path == "fast":
                result = await self._execute_fast_path(request, route_result)
            else:
                result = await self._execute_normal_path(request)
            
            elapsed = time.time() - start_time
            
            # Broadcast: complete
            self.status_server.update_agent(
                state="idle",
                task=None,
                progress=1.0,
            )
            
            # Update knowledge stats
            self.status_server.update_knowledge(
                trajectory_count=self.knowledge_store.count(),
                domain_count=len(self.knowledge_store.get_domains()),
            )
            
            return ExecuteResponse(
                success=result.get("success", False),
                result=str(result.get("result", "")),
                path=route_result.path,
                time_seconds=elapsed,
                confidence=route_result.confidence,
                steps=result.get("steps", 0),
                skill_name=skill_name,
            )
            
        except Exception as e:
            logger.error(f"Execution error: {e}")
            
            # Broadcast: error
            self.status_server.update_agent(
                state="error",
                task=None,
            )
            
            return ExecuteResponse(
                success=False,
                result=None,
                path="error",
                time_seconds=time.time() - start_time,
                confidence=0.0,
                error=str(e),
            )
            
        finally:
            self._executing = False
            self._current_task = None
    
    async def _execute_skill_path(
        self, 
        request: ExecuteRequest, 
        route_result: RouteResult
    ) -> tuple[dict, str]:
        """
        Execute using a learned skill (parameterized function)
        
        This is the fastest path - uses AI-generated code with dynamic parameters.
        
        Returns:
            (result_dict, skill_name)
        """
        skill = route_result.skill
        params = route_result.params or {}
        
        logger.info(f"Executing SKILL PATH: {skill.name}({params})")
        
        # Start browser for skill execution
        from engine.browser.session import BrowserSession
        
        browser = BrowserSession()
        await browser.start(url=request.url, headless=request.headless)
        
        try:
            # Create executor and run skill
            executor = SkillExecutor(browser.page, timeout=30.0)
            exec_result = await executor.execute(
                code=skill.code,
                function_name=skill.name,
                params=params,
            )
            
            # Update skill confidence based on result (ExpeL-style)
            await self.knowledge_store.update_skill_confidence(
                skill.id, 
                success=exec_result.success
            )
            
            if exec_result.success:
                logger.info(f"Skill {skill.name} succeeded in {exec_result.duration_ms:.0f}ms")
                return {
                    "success": True,
                    "result": exec_result.result,
                    "steps": 1,
                }, skill.name
            else:
                # Skill failed - fall back to normal path
                logger.warning(f"Skill {skill.name} failed: {exec_result.error}")
                logger.info("Falling back to NORMAL PATH")
                
                # Close browser and use normal path
                await browser.close()
                result = await self._execute_normal_path(request)
                return result, skill.name
                
        except Exception as e:
            logger.error(f"Skill execution error: {e}")
            await browser.close()
            
            # Fall back to normal path
            result = await self._execute_normal_path(request)
            return result, skill.name
        finally:
            try:
                await browser.close()
            except:
                pass
    
    async def _execute_fast_path(self, request: ExecuteRequest, route_result: RouteResult) -> dict:
        """Execute using cached trajectory"""
        logger.info("Executing FAST PATH (replay)")
        
        # 优先使用缓存的结果（如果有的话）
        if route_result.cached_result:
            logger.info(f"Using cached result directly: {route_result.cached_result[:50]}...")
            return {
                "success": True,
                "result": route_result.cached_result,
                "steps": 0,  # 直接返回缓存，不需要执行
            }
        
        # 否则尝试 replay
        if not route_result.replay_code:
            logger.warning("No replay code and no cached result, falling back to normal path")
            return await self._execute_normal_path(request)
        
        # Start browser for replay
        from engine.browser.session import BrowserSession
        
        browser = BrowserSession()
        await browser.start(url=request.url, headless=request.headless)
        
        try:
            executor = ReplayExecutor(browser.page)
            result = await executor.execute(route_result.replay_code)
            
            return {
                "success": result.get("success", False),
                "result": result.get("result", "Replay completed"),
                "steps": 1,  # Replay is always 1 step
            }
        finally:
            await browser.close()
    
    async def _execute_normal_path(self, request: ExecuteRequest, max_retries: int = 2) -> dict:
        """
        Execute using AI agent with retry and error recovery.
        
        方案 B: Playwright 控制浏览器（headless），截图流同步到前端。
        方案 A: CDP 控制 Electron 内部浏览器（use_cdp=True）。
        
        Args:
            request: Task request
            max_retries: Max retry attempts (default 2, total 3 attempts)
        """
        # 方案 A: CDP 模式 - 使用 Electron 内部控制
        if request.use_cdp:
            return await self._execute_cdp_mode(request, max_retries)
        
        # 方案 B: Playwright 模式（默认）
        logger.info("Executing NORMAL PATH (Playwright mode) with screenshot streaming")
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}/{max_retries}")
            
            # Broadcast: progress
            self.status_server.update_agent(
                state="thinking",
                task=request.task,
                progress=0.3,
            )
            
            # Start browser (always visible for screenshot streaming)
            from engine.browser.session import BrowserSession
            
            browser = BrowserSession()
            streamer = None
            
            try:
                # 方案 B: 使用 headless 模式（Playwright 在 headless 也能截图）
                # 不会打开可见的 Chrome 窗口，截图流同步到 Electron
                await browser.start(url=request.url, headless=True)
                
                # 初始化截图流
                streamer = EventDrivenStreamer(
                    page=browser.active_page,
                    config=StreamConfig(fps=10, quality=70),
                )
                
                # 设置截图回调 - 广播到 WebSocket
                async def on_frame(frame):
                    await self.status_server.broadcast_frame(
                        image_base64=frame.image_base64,
                        action=frame.action,
                        step=frame.step,
                        total_steps=frame.total_steps,
                    )
                
                streamer.on_frame(on_frame)
                await streamer.start()
                
                # 发送初始截图
                await streamer.capture_action(
                    action="Loading page...",
                    step=0,
                    total_steps=request.max_steps,
                )
                
                # Run agent with screenshot integration
                result = await self._run_agent_with_streaming(
                    request=request,
                    browser=browser,
                    streamer=streamer,
                )
                
                # Check if successful
                if result.get("success"):
                    # 发送完成截图
                    await streamer.capture_action(
                        action="Task completed!",
                        step=result.get("steps", 1),
                        total_steps=result.get("steps", 1),
                    )
                    
                    # Try to synthesize a skill from the successful trajectory
                    asyncio.create_task(
                        self._synthesize_skill_from_result(request, result)
                    )
                    return result
                
                # Task failed but no exception - might be recoverable
                last_error = result.get("result", "Task failed")
                logger.warning(f"Task failed (attempt {attempt+1}): {last_error}")
                
            except asyncio.TimeoutError:
                last_error = "Task timed out"
                logger.warning(f"Timeout (attempt {attempt+1})")
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Error (attempt {attempt+1}): {e}")
                
            finally:
                # 停止截图流
                if streamer:
                    await streamer.stop()
                
                try:
                    await browser.close()
                except:
                    pass
            
            # Wait before retry (exponential backoff)
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
        
        # All retries exhausted
        return {
            "success": False,
            "result": f"Failed after {max_retries + 1} attempts: {last_error}",
            "steps": 0,
        }
    
    async def _execute_cdp_mode(self, request: ExecuteRequest, max_retries: int = 2) -> dict:
        """
        Execute using AI agent with CDP internal browser control (方案 A).
        
        使用 Electron 内部的 CDP 控制，而非 Playwright。
        AI 操作直接在 NogicOS 窗口内执行。
        
        Args:
            request: Task request
            max_retries: Max retry attempts
        """
        logger.info("Executing NORMAL PATH (CDP mode) - Electron internal control")
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}/{max_retries}")
            
            # Broadcast: progress
            self.status_server.update_agent(
                state="thinking",
                task=request.task,
                progress=0.3,
            )
            
            # 创建 CDP 浏览器会话（使用 StatusServer 进行双向通信）
            browser = CDPBrowserSession(self.status_server)
            
            try:
                # 导航到目标 URL
                await browser.start(url=request.url)
                
                # 广播初始状态
                await self.status_server.broadcast_frame(
                    image_base64="",  # 初始无截图
                    action="Navigating to page...",
                    step=0,
                    total_steps=request.max_steps,
                )
                
                # 运行 AI Agent（使用 CDP 浏览器）
                result = await self._run_agent_cdp(
                    request=request,
                    browser=browser,
                )
                
                # 成功则返回
                if result.get("success"):
                    # 尝试合成技能
                    asyncio.create_task(
                        self._synthesize_skill_from_result(request, result)
                    )
                    return result
                
                # 失败但可恢复
                last_error = result.get("result", "Task failed")
                logger.warning(f"Task failed (attempt {attempt+1}): {last_error}")
                
            except asyncio.TimeoutError:
                last_error = "Task timed out"
                logger.warning(f"Timeout (attempt {attempt+1})")
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Error (attempt {attempt+1}): {e}")
                
            finally:
                try:
                    await browser.close()
                except:
                    pass
            
            # 重试前等待
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
        
        # 重试耗尽
        return {
            "success": False,
            "result": f"Failed after {max_retries + 1} attempts: {last_error}",
            "steps": 0,
        }
    
    async def _run_agent_cdp(self, request: ExecuteRequest, browser: CDPBrowserSession) -> dict:
        """
        Run AI agent with CDP browser session.
        
        简化版 agent 运行，使用 CDP 控制。
        """
        step_count = 0
        
        try:
            # 使用 agent 的 stream 方法
            async for event in self.agent.stream(
                task=request.task,
                browser_session=browser,
                max_steps=request.max_steps,
            ):
                for node_name, state_update in event.items():
                    if node_name == "observe":
                        step_count += 1
                        # 截图并广播
                        try:
                            screenshot = await browser.get_screenshot_base64("jpeg", 70)
                            await self.status_server.broadcast_frame(
                                image_base64=screenshot,
                                action="Observing page...",
                                step=step_count,
                                total_steps=request.max_steps,
                            )
                        except Exception as e:
                            logger.warning(f"Screenshot failed: {e}")
                        
                    elif node_name == "think":
                        action = state_update.get("next_action", {})
                        if isinstance(action, dict):
                            action_desc = f"{action.get('action_type', 'unknown')}: {action.get('target', '')}"
                        else:
                            action_desc = "Thinking..."
                        
                        self.status_server.update_agent(
                            last_action=action_desc,
                            step=step_count,
                            progress=step_count / request.max_steps,
                        )
                        
                    elif node_name == "act":
                        # 执行后截图
                        try:
                            screenshot = await browser.get_screenshot_base64("jpeg", 70)
                            await self.status_server.broadcast_frame(
                                image_base64=screenshot,
                                action=f"Step {step_count}: Action executed",
                                step=step_count,
                                total_steps=request.max_steps,
                            )
                        except Exception as e:
                            logger.warning(f"Screenshot failed: {e}")
                        
                    elif node_name == "__end__":
                        # Agent 完成
                        final_state = state_update
                        if isinstance(final_state, dict):
                            result_text = final_state.get("result", "Task completed")
                            success = final_state.get("success", True)
                        else:
                            result_text = str(final_state)
                            success = True
                        
                        # 最终截图
                        try:
                            screenshot = await browser.get_screenshot_base64("jpeg", 70)
                            await self.status_server.broadcast_frame(
                                image_base64=screenshot,
                                action="Task completed!",
                                step=step_count,
                                total_steps=step_count,
                            )
                        except:
                            pass
                        
                        return {
                            "success": success,
                            "result": result_text,
                            "steps": step_count,
                        }
            
            # Stream 结束但没有 __end__ 事件
            return {
                "success": True,
                "result": "Agent completed",
                "steps": step_count,
            }
            
        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            return {
                "success": False,
                "result": str(e),
                "steps": step_count,
            }
    
    async def _run_agent_with_streaming(
        self,
        request: ExecuteRequest,
        browser,
        streamer: EventDrivenStreamer,
    ) -> dict:
        """
        Run AI agent with screenshot streaming integration.
        
        Uses agent.stream() to capture screenshots at each step.
        """
        step_count = 0
        final_state = None
        last_action = ""
        
        try:
            # Use stream to get real-time updates
            async for event in self.agent.stream(
                task=request.task,
                browser_session=browser,
                max_steps=request.max_steps,
            ):
                # event is a dict with node name as key
                for node_name, state_update in event.items():
                    # Capture screenshot on significant events
                    if node_name == "observe":
                        # 观察阶段：截图当前页面
                        step_count += 1
                        await streamer.capture_action(
                            action="Observing page...",
                            step=step_count,
                            total_steps=request.max_steps,
                        )
                        
                    elif node_name == "think":
                        # 思考阶段：更新状态
                        action = state_update.get("next_action", {})
                        if isinstance(action, dict):
                            last_action = action.get("step_by_step_reasoning", "Thinking...")[:100]
                        await streamer.capture_action(
                            action=f"Thinking: {last_action}",
                            step=step_count,
                            total_steps=request.max_steps,
                        )
                        
                    elif node_name == "act":
                        # 执行阶段：截图动作结果
                        await streamer.capture_action(
                            action="Executing action...",
                            step=step_count,
                            total_steps=request.max_steps,
                            delay_after=0.5,  # 多等一会看到结果
                        )
                        
                    elif node_name == "terminate":
                        final_state = state_update
                        
                    # 更新广播状态
                    self.status_server.update_agent(
                        state="acting" if node_name == "act" else "thinking",
                        step=step_count,
                        max_steps=request.max_steps,
                        last_action=last_action[:50] if last_action else None,
                    )
            
            # 构建结果
            if final_state:
                return {
                    "success": final_state.get("status") == "completed",
                    "result": final_state.get("result"),
                    "steps": step_count,
                    "actions": final_state.get("actions", []),
                }
            else:
                return {
                    "success": False,
                    "result": "Agent stream ended without termination",
                    "steps": step_count,
                }
                
        except Exception as e:
            logger.error(f"Agent stream error: {e}")
            return {
                "success": False,
                "result": str(e),
                "steps": step_count,
            }
    
    async def _synthesize_skill_from_result(self, request: ExecuteRequest, result: dict):
        """
        Synthesize a skill from a successful agent execution
        
        Runs in background to avoid blocking the response.
        """
        try:
            # Get trajectory from result
            trajectory = result.get("trajectory", [])
            if not trajectory or len(trajectory) < 2:
                logger.debug("Trajectory too short for skill synthesis")
                return
            
            # Extract domain from URL
            from urllib.parse import urlparse
            domain = urlparse(request.url).netloc
            
            logger.info(f"Synthesizing skill for: {request.task[:50]}...")
            
            # Call synthesizer
            synth_result = await self.synthesizer.synthesize(
                task=request.task,
                trajectory=trajectory,
                domain=domain,
            )
            
            if synth_result.success:
                # Save skill to knowledge store
                from engine.knowledge.store import SkillParameter
                
                params = [
                    SkillParameter(
                        name=p["name"],
                        param_type=p.get("type", "str"),
                    )
                    for p in (synth_result.parameters or [])
                ]
                
                skill = await self.knowledge_store.save_skill(
                    name=synth_result.function_name,
                    description=request.task,
                    code=synth_result.code,
                    domain=domain,
                    parameters=params,
                )
                
                logger.info(f"Skill synthesized: {skill.name} ({skill.id})")
                
                # Update status with new skill count
                self.status_server.update_knowledge(
                    trajectory_count=self.knowledge_store.count(),
                    domain_count=len(self.knowledge_store.get_domains()),
                )
            else:
                logger.warning(f"Skill synthesis failed: {synth_result.error}")
                
        except Exception as e:
            logger.error(f"Skill synthesis error: {e}")
    
    def get_stats(self) -> StatsResponse:
        """Get knowledge store statistics"""
        stats = self.knowledge_store.get_stats()
        return StatsResponse(
            total_trajectories=stats["total_trajectories"],
            successful=stats["successful"],
            success_rate=stats["success_rate"],
            domains=stats["domains"],
            total_skills=stats.get("total_skills", 0),
        )


# ============================================================================
# FastAPI Application
# ============================================================================

# Global engine instance
engine: Optional[HiveEngine] = None
server_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global engine, server_start_time
    
    # Record startup time
    server_start_time = time.time()
    
    # Startup
    logger.info("=" * 50)
    logger.info("NogicOS Hive Server Starting...")
    logger.info("=" * 50)
    
    engine = HiveEngine()
    await engine.start_websocket()
    
    logger.info("")
    logger.info("Server ready!")
    logger.info(f"  HTTP:      http://localhost:8080")
    logger.info(f"  WebSocket: ws://localhost:8765")
    logger.info(f"  Knowledge: {engine.knowledge_store.count()} trajectories")
    logger.info("")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await engine.stop_websocket()


app = FastAPI(
    title="NogicOS Hive Server",
    description="AI Browser Engine API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Electron
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_model=StatusResponse)
async def root():
    """Server status"""
    return StatusResponse(
        status="running",
        knowledge_count=engine.knowledge_store.count() if engine else 0,
        websocket_port=8765,
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get knowledge store statistics"""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    return engine.get_stats()


@app.post("/execute", response_model=ExecuteResponse)
async def execute_task(request: ExecuteRequest):
    """
    Execute a task
    
    The server will automatically choose:
    - FAST PATH: If similar task found in knowledge (2-3 seconds)
    - NORMAL PATH: AI agent execution (10-15 seconds)
    
    Successful executions are saved to knowledge for future fast path.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    # Global timeout: 2 minutes max for any task
    GLOBAL_TIMEOUT = 120.0
    
    try:
        result = await asyncio.wait_for(
            engine.execute(request),
            timeout=GLOBAL_TIMEOUT
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"Task timed out after {GLOBAL_TIMEOUT}s: {request.task[:50]}")
        return ExecuteResponse(
            success=False,
            result=f"Task timed out after {GLOBAL_TIMEOUT} seconds",
            path="timeout",
            time_seconds=GLOBAL_TIMEOUT,
            confidence=0.0,
            steps=0,
            error="Global timeout exceeded"
        )
    except Exception as e:
        raise


@app.get("/health")
async def health():
    """
    Enhanced health check endpoint
    
    Returns:
        - status: "healthy" | "degraded" | "unhealthy"
        - engine: bool
        - executing: bool (is a task currently running)
        - uptime_seconds: float
        - memory_mb: float (current process memory usage)
    """
    import psutil
    
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    uptime = time.time() - server_start_time if 'server_start_time' in globals() else 0
    
    # Determine health status
    status = "healthy"
    if engine is None:
        status = "unhealthy"
    elif engine._executing:
        status = "busy"
    elif memory_mb > 1024:  # Warning if > 1GB memory
        status = "degraded"
    
    return {
        "status": status,
        "engine": engine is not None,
        "executing": engine._executing if engine else False,
        "current_task": engine._current_task[:50] if engine and engine._current_task else None,
        "uptime_seconds": round(uptime, 1),
        "memory_mb": round(memory_mb, 1),
    }


@app.get("/health/detailed")
async def health_detailed():
    """
    Detailed health check with module-level status
    
    Checks:
        - hive: LangGraph agent and API key
        - browser: Playwright session availability
        - knowledge: Knowledge store connectivity
    """
    from engine.health import check_all
    
    # Get basic health
    import psutil
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    uptime = time.time() - server_start_time if 'server_start_time' in globals() else 0
    
    # Get module health
    module_health = await check_all()
    
    return {
        "overall": module_health["overall"],
        "server": {
            "engine": engine is not None,
            "executing": engine._executing if engine else False,
            "uptime_seconds": round(uptime, 1),
            "memory_mb": round(memory_mb, 1),
        },
        "modules": module_health["modules"],
    }


# ============================================================================
# Main Entry
# ============================================================================

if __name__ == "__main__":
    # Load API keys
    try:
        from api_keys import setup_env
        setup_env()
        logger.info("API keys loaded from api_keys.py")
    except ImportError:
        logger.info("Using environment variables for API keys")
    
    # Run server
    uvicorn.run(
        "hive_server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )

