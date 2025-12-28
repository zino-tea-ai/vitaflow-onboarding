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
from engine.demo.yc_analyzer import YCAnalyzer, analyze_yc_companies
from engine.tools import get_dispatcher, init_dispatcher_with_server

# Try to import old executor (backwards compatibility)
try:
    from engine.executor import TaskExecutor, execute_task as executor_execute_task
except ImportError:
    TaskExecutor = None
    executor_execute_task = None

# Import new agent (v2 architecture)
try:
    from engine.agent import NogicOSAgent
    from engine.tools import create_full_registry
    from engine.middleware import FilesystemMiddleware, TodoMiddleware
    AGENT_V2_AVAILABLE = True
except ImportError:
    AGENT_V2_AVAILABLE = False
    NogicOSAgent = None


# ============================================================================
# Request/Response Models
# ============================================================================

class ContextConfig(BaseModel):
    """Context configuration for task execution"""
    file: bool = False  # Include file context
    web: bool = False   # Include web page context


class ExecuteRequest(BaseModel):
    """Task execution request"""
    task: str
    url: Optional[str] = None  # No default URL
    max_steps: int = 10
    headless: bool = True  # Default headless for server mode
    use_cdp: bool = False  # Use CDP mode (Electron internal control) instead of Playwright
    mode: str = "agent"   # ask, plan, agent
    context: Optional[ContextConfig] = None  # Context configuration


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
        
        # Use cached result if available (fastest path)
        if route_result.cached_result:
            logger.info(f"Using cached result directly: {route_result.cached_result[:50]}...")
            return {
                "success": True,
                "result": route_result.cached_result,
                "steps": 0,  # Direct return from cache, no execution needed
            }
        
        # Otherwise try replay
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
        
        Option B: Playwright controls browser (headless), screenshot stream syncs to frontend.
        Option A: CDP controls Electron internal browser (use_cdp=True).
        
        Args:
            request: Task request
            max_retries: Max retry attempts (default 2, total 3 attempts)
        """
        # Option A: CDP mode - Use Electron internal control
        if request.use_cdp:
            return await self._execute_cdp_mode(request, max_retries)
        
        # Option B: Playwright mode (default)
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
                # Option B: Use headless mode (Playwright can screenshot in headless too)
                # No visible Chrome window, screenshot stream syncs to Electron
                await browser.start(url=request.url, headless=True)
                
                # Initialize screenshot streamer
                streamer = EventDrivenStreamer(
                    page=browser.active_page,
                    config=StreamConfig(fps=10, quality=70),
                )
                
                # Set screenshot callback - broadcast to WebSocket
                async def on_frame(frame):
                    await self.status_server.broadcast_frame(
                        image_base64=frame.image_base64,
                        action=frame.action,
                        step=frame.step,
                        total_steps=frame.total_steps,
                    )
                
                streamer.on_frame(on_frame)
                await streamer.start()
                
                # Send initial screenshot
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
                    # Send completion screenshot
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
                # Stop screenshot stream
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
        Execute using AI agent with CDP internal browser control (Option A).
        
        Uses Electron internal CDP control instead of Playwright.
        AI operations execute directly within the NogicOS window.
        
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
            
            # Create CDP browser session (using StatusServer for bidirectional communication)
            browser = CDPBrowserSession(self.status_server)
            
            try:
                # Navigate to target URL
                await browser.start(url=request.url)
                
                # Broadcast initial state
                await self.status_server.broadcast_frame(
                    image_base64="",  # No screenshot initially
                    action="Navigating to page...",
                    step=0,
                    total_steps=request.max_steps,
                )
                
                # Run AI Agent (using CDP browser)
                result = await self._run_agent_cdp(
                    request=request,
                    browser=browser,
                )
                
                # Return if successful
                if result.get("success"):
                    # Try to synthesize skill
                    asyncio.create_task(
                        self._synthesize_skill_from_result(request, result)
                    )
                    return result
                
                # Failed but recoverable
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
            
            # Wait before retry
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
    
    async def _run_agent_cdp(self, request: ExecuteRequest, browser: CDPBrowserSession) -> dict:
        """
        Run AI agent with CDP browser session.
        
        Simplified agent run using CDP control.
        """
        step_count = 0
        
        try:
            # Use agent's stream method
            async for event in self.agent.stream(
                task=request.task,
                browser_session=browser,
                max_steps=request.max_steps,
            ):
                for node_name, state_update in event.items():
                    if node_name == "observe":
                        step_count += 1
                        # Screenshot and broadcast
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
                        # Screenshot after execution
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
                        # Agent completed
                        final_state = state_update
                        if isinstance(final_state, dict):
                            result_text = final_state.get("result", "Task completed")
                            success = final_state.get("success", True)
                        else:
                            result_text = str(final_state)
                            success = True
                        
                        # Final screenshot
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
            
            # Stream ended without __end__ event
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
                        # Observe phase: screenshot current page
                        step_count += 1
                        await streamer.capture_action(
                            action="Observing page...",
                            step=step_count,
                            total_steps=request.max_steps,
                        )
                        
                    elif node_name == "think":
                        # Think phase: update status
                        action = state_update.get("next_action", {})
                        if isinstance(action, dict):
                            last_action = action.get("step_by_step_reasoning", "Thinking...")[:100]
                        await streamer.capture_action(
                            action=f"Thinking: {last_action}",
                            step=step_count,
                            total_steps=request.max_steps,
                        )
                        
                    elif node_name == "act":
                        # Act phase: screenshot action result
                        await streamer.capture_action(
                            action="Executing action...",
                            step=step_count,
                            total_steps=request.max_steps,
                            delay_after=0.5,  # Wait a bit to see result
                        )
                        
                    elif node_name == "terminate":
                        final_state = state_update
                        
                    # Update broadcast status
                    self.status_server.update_agent(
                        state="acting" if node_name == "act" else "thinking",
                        step=step_count,
                        max_steps=request.max_steps,
                        last_action=last_action[:50] if last_action else None,
                    )
            
            # Build result
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


def is_yc_demo_task(task: str) -> bool:
    """Check if task is a YC analysis demo task"""
    keywords = ["yc", "y combinator", "ycombinator", "application", "analyze"]
    task_lower = task.lower()
    # Check if at least 2 keywords match
    matches = sum(1 for kw in keywords if kw in task_lower)
    return matches >= 2


@app.post("/execute", response_model=ExecuteResponse)
async def execute_task(request: ExecuteRequest):
    """
    Smart task execution with intelligent routing.
    
    The server will:
    1. Use Smart Router to decide: conversation or task?
    2. For simple chats → respond directly (no planning)
    3. For tasks → generate plan and execute with streaming
    
    This provides a natural experience like talking to Claude/Cursor.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    # Global timeout: 3 minutes max for any task
    GLOBAL_TIMEOUT = 180.0
    start_time = time.time()
    
    # Import smart router
    from engine.executor.router import SmartRouter, ResponseType
    
    # Check for YC Demo scenario (special handling with expanded demo)
    if is_yc_demo_task(request.task):
        logger.info(f"[Demo] Detected YC analysis task: {request.task[:50]}")
        return await execute_yc_demo(request)
    
    # ========================================
    # SMART ROUTING: Let LLM decide conversation vs task
    # ========================================
    logger.info(f"[Router] Analyzing input: {request.task[:50]}...")
    
    router = SmartRouter(status_server=engine.status_server)
    
    try:
        # Route with streaming - if conversation, response is streamed directly
        route_result = await asyncio.wait_for(
            router.route_and_stream(
                user_input=request.task,
                context=request.url if request.url else None,
            ),
            timeout=30.0  # 30s timeout for routing
        )
        
        # If it's just conversation, return directly
        if route_result.response_type == ResponseType.CONVERSATION:
            logger.info(f"[Router] Handled as conversation")
            return ExecuteResponse(
                success=True,
                result=route_result.direct_response,
                path="conversation",
                time_seconds=time.time() - start_time,
                confidence=route_result.confidence,
                steps=0,  # No steps for conversation
                error=None,
            )
        
        # Otherwise, it's a task - proceed with execution
        logger.info(f"[Router] Routing to task executor: {route_result.task_description[:50]}...")
        
    except asyncio.TimeoutError:
        logger.warning(f"[Router] Timeout, defaulting to task execution")
        route_result = None  # Will use original task
    except Exception as e:
        logger.warning(f"[Router] Error: {e}, defaulting to task execution")
        route_result = None
    
    # Use the refined task description if available
    task_to_execute = (
        route_result.task_description 
        if route_result and route_result.task_description 
        else request.task
    )
    
    # Use Universal Task Executor for tasks
    logger.info(f"[Executor] Starting task execution: {task_to_execute[:50]}...")
    
    try:
        # Initialize tool dispatcher
        await init_dispatcher_with_server(engine.status_server)
        
        # Create executor
        executor = TaskExecutor(
            status_server=engine.status_server,
            model="claude-opus-4-5-20251101",  # Opus 4.5
        )
        
        # Build context from request
        context = None
        if request.context:
            context_parts = []
            if request.context.web and request.url:
                context_parts.append(f"Current URL: {request.url}")
            if context_parts:
                context = "\n".join(context_parts)
        
        # Execute with timeout
        result = await asyncio.wait_for(
            executor.execute(
                task=task_to_execute,  # Use refined task from router
                context=context,
            ),
            timeout=GLOBAL_TIMEOUT
        )
        
        elapsed = time.time() - start_time
        
        return ExecuteResponse(
            success=result.success,
            result=result.summary,
            path="universal",
            time_seconds=elapsed,
            confidence=0.9 if result.success else 0.0,
            steps=result.steps_completed,
            error=result.error,
        )
        
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
        logger.error(f"[Executor] Error: {e}")
        return ExecuteResponse(
            success=False,
            result=None,
            path="error",
            time_seconds=time.time() - start_time,
            confidence=0.0,
            steps=0,
            error=str(e)
        )


async def execute_yc_demo(request: ExecuteRequest) -> ExecuteResponse:
    """
    Execute YC Demo scenario with v2.0 streaming protocol.
    
    This is a specialized handler for the YC analysis demo:
    - Crawl YC website
    - Extract AI company data
    - Analyze patterns
    - Generate reports
    
    v2.0: Uses Cursor-style streaming feedback with thinking bubbles,
    plan view, tool call cards, and artifact previews.
    """
    start_time = time.time()
    
    try:
        # Initialize tool dispatcher with the correct status_server instance
        await init_dispatcher_with_server(engine.status_server)
        
        # Create browser session based on mode
        if request.use_cdp:
            # CDP mode - use Electron's BrowserView
            browser_session = CDPBrowserSession(engine.status_server)
        else:
            # For demo, we'll use a mock session that works with the analyzer
            browser_session = MockBrowserSession()
        
        # Create unique message ID for this execution
        import uuid
        message_id = str(uuid.uuid4())[:8]
        
        # Run YC analysis with v2 streaming
        analyzer = YCAnalyzer(output_dir="~/yc_research")
        
        # Try v2 streaming first, fall back to v1 if not available
        try:
            result = await analyzer.run_full_analysis_v2(
                browser_session,
                engine.status_server,
                message_id
            )
        except AttributeError:
            # Fall back to v1 if v2 not available
            logger.info("[Demo] Falling back to v1 analysis (v2 not available)")
            
            # Status callback for real-time updates (v1)
            async def status_callback(message: str, step: int, total_steps: int):
                engine.status_server.update_agent(
                    state="acting",
                    step=step,
                    max_steps=total_steps,
                    last_action=message
                )
                await engine.status_server.broadcast_status()
            
            result = await analyzer.run_full_analysis(browser_session, status_callback)
        
        elapsed = time.time() - start_time
        
        if result["success"]:
            # Format success message
            files_str = ", ".join(os.path.basename(f) for f in result["files_created"])
            insights_preview = result["insights"][:3] if result["insights"] else []
            
            return ExecuteResponse(
                success=True,
                result=f"Analysis complete! Created: {files_str}. Key insights: {'; '.join(insights_preview)}",
                path="demo",
                time_seconds=elapsed,
                confidence=0.95,
                steps=len(result["steps_completed"]),
            )
        else:
            return ExecuteResponse(
                success=False,
                result=None,
                path="demo",
                time_seconds=elapsed,
                confidence=0.0,
                steps=len(result["steps_completed"]),
                error=result["error"]
            )
            
    except Exception as e:
        logger.error(f"[Demo] YC analysis failed: {e}")
        return ExecuteResponse(
            success=False,
            result=None,
            path="demo",
            time_seconds=time.time() - start_time,
            confidence=0.0,
            steps=0,
            error=str(e)
        )


class MockBrowserSession:
    """Mock browser session for demo without real browser"""
    async def navigate(self, url: str):
        logger.info(f"[Mock] Navigate to: {url}")
        await asyncio.sleep(0.5)
    
    async def click(self, selector: str):
        logger.info(f"[Mock] Click: {selector}")
        await asyncio.sleep(0.2)
    
    async def type(self, text: str):
        logger.info(f"[Mock] Type: {text[:20]}...")
        await asyncio.sleep(0.2)


@app.get("/read_file")
async def read_file(path: str):
    """
    Read file content endpoint for preview panel
    
    Args:
        path: File path (supports ~ for home directory)
        
    Returns:
        {"content": "file content", "filename": "name.ext"}
    """
    import os
    
    # Expand ~ to home directory
    if path.startswith("~"):
        path = os.path.expanduser(path)
    
    # Security: only allow reading from yc_research directory
    if "yc_research" not in path:
        raise HTTPException(status_code=403, detail="Access denied: Can only read from yc_research directory")
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content, "filename": os.path.basename(path)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# V2 API - New Agent Architecture
# ============================================================================

class ExecuteV2Request(BaseModel):
    """V2 task execution request"""
    message: str
    session_id: str = "default"
    max_steps: int = 20


class ExecuteV2Response(BaseModel):
    """V2 task execution response"""
    success: bool
    response: str
    session_id: str
    time_seconds: float
    error: Optional[str] = None


@app.post("/v2/execute", response_model=ExecuteV2Response)
async def execute_v2(request: ExecuteV2Request):
    """
    V2 Execute endpoint using new LangGraph-based agent.
    
    Features:
    - Unified tool registry (browser + local + plan)
    - LangGraph agent loop
    - Streaming via WebSocket
    - State persistence
    """
    if not AGENT_V2_AVAILABLE:
        raise HTTPException(
            status_code=501, 
            detail="V2 agent not available. Install: pip install langgraph langchain-core"
        )
    
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    start_time = time.time()
    
    try:
        # Create tool registry with all tools
        registry = create_full_registry()
        
        # Add middleware
        fs_middleware = FilesystemMiddleware(registry=registry)
        todo_middleware = TodoMiddleware(registry=registry)
        
        # Create agent
        agent = NogicOSAgent(
            registry=registry,
            status_server=engine.status_server,
        )
        
        # Execute
        result = await agent.invoke(
            message=request.message,
            session_id=request.session_id,
        )
        
        # Extract final response
        response = agent.get_final_response(result)
        
        elapsed = time.time() - start_time
        
        return ExecuteV2Response(
            success=True,
            response=response,
            session_id=request.session_id,
            time_seconds=elapsed,
        )
        
    except Exception as e:
        logger.error(f"V2 execution error: {e}")
        return ExecuteV2Response(
            success=False,
            response="",
            session_id=request.session_id,
            time_seconds=time.time() - start_time,
            error=str(e),
        )


@app.get("/v2/tools")
async def list_v2_tools():
    """List all available tools in the V2 registry"""
    if not AGENT_V2_AVAILABLE:
        raise HTTPException(status_code=501, detail="V2 agent not available")
    
    registry = create_full_registry()
    tools = registry.to_anthropic_format()
    
    return {
        "count": len(tools),
        "tools": tools,
    }


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

