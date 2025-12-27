# -*- coding: utf-8 -*-
"""
Passive Learning Recorder

Records user actions via CDP events for later replay.

Architecture:
    Browser Events → Recorder → Action Sequence → KnowledgeStore
    
Events Captured:
    - Navigation (page load, URL change)
    - Clicks (element, coordinates)
    - Input (text entry, form fills)
    - Keyboard (key presses)

Usage:
    recorder = Recorder(page)
    recorder.start()
    # ... user interacts with page ...
    trajectory = recorder.stop()
    await knowledge_store.save(task, url, trajectory)
"""

import asyncio
import logging
import time
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from playwright.async_api import Page, Request, Response

logger = logging.getLogger("nogicos.recorder")


@dataclass
class RecordedAction:
    """A single recorded user action"""
    timestamp: float
    action_type: str  # click, input, navigate, keypress
    url: str
    selector: Optional[str] = None
    value: Optional[str] = None
    coordinates: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def to_playwright_code(self) -> str:
        """Generate Playwright code for this action"""
        if self.action_type == "navigate":
            return f'await page.goto("{self.url}")'
        elif self.action_type == "click":
            if self.selector:
                return f'await page.click("{self.selector}", timeout=15000)'
            elif self.coordinates:
                return f'await page.mouse.click({self.coordinates["x"]}, {self.coordinates["y"]})'
        elif self.action_type == "input":
            if self.selector and self.value:
                return f'await page.fill("{self.selector}", "{self.value}", timeout=15000)'
        elif self.action_type == "keypress":
            if self.value:
                return f'await page.keyboard.press("{self.value}")'
        return f"# Unknown action: {self.action_type}"


@dataclass 
class RecordedTrajectory:
    """A sequence of recorded actions"""
    task: str
    start_url: str
    end_url: str
    actions: List[RecordedAction]
    start_time: float
    end_time: float
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            "task": self.task,
            "start_url": self.start_url,
            "end_url": self.end_url,
            "actions": [a.to_dict() for a in self.actions],
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.end_time - self.start_time,
            "action_count": len(self.actions),
            "success": self.success,
            "metadata": self.metadata,
            "recorded_at": datetime.now().isoformat(),
        }
    
    def to_playwright_script(self) -> str:
        """Generate executable Playwright script"""
        lines = [
            "async def replay(page):",
            '    """Auto-generated replay script"""',
        ]
        for action in self.actions:
            code = action.to_playwright_code()
            lines.append(f"    {code}")
        return "\n".join(lines)


class Recorder:
    """
    Passive action recorder
    
    Captures user interactions via Playwright page events.
    """
    
    def __init__(
        self, 
        page: Page,
        capture_navigation: bool = True,
        capture_clicks: bool = True,
        capture_inputs: bool = True,
        capture_keys: bool = False,  # Can be noisy
    ):
        self.page = page
        self.capture_navigation = capture_navigation
        self.capture_clicks = capture_clicks
        self.capture_inputs = capture_inputs
        self.capture_keys = capture_keys
        
        self._recording = False
        self._actions: List[RecordedAction] = []
        self._start_time: float = 0
        self._start_url: str = ""
        self._listeners: List[Callable] = []
        
        # CDP session for advanced events
        self._cdp_session = None
    
    @property
    def is_recording(self) -> bool:
        return self._recording
    
    @property
    def action_count(self) -> int:
        return len(self._actions)
    
    async def start(self, task: str = ""):
        """Start recording"""
        if self._recording:
            logger.warning("[Recorder] Already recording")
            return
        
        self._recording = True
        self._actions = []
        self._start_time = time.time()
        self._start_url = self.page.url
        self._task = task
        
        # Set up event listeners
        await self._setup_listeners()
        
        logger.info(f"[Recorder] Started recording at {self._start_url}")
    
    async def stop(self) -> RecordedTrajectory:
        """Stop recording and return trajectory"""
        if not self._recording:
            logger.warning("[Recorder] Not recording")
            return None
        
        self._recording = False
        end_time = time.time()
        
        # Remove listeners
        await self._remove_listeners()
        
        trajectory = RecordedTrajectory(
            task=self._task,
            start_url=self._start_url,
            end_url=self.page.url,
            actions=self._actions.copy(),
            start_time=self._start_time,
            end_time=end_time,
            success=True,
        )
        
        logger.info(f"[Recorder] Stopped. Recorded {len(self._actions)} actions in {end_time - self._start_time:.1f}s")
        
        return trajectory
    
    async def _setup_listeners(self):
        """Set up page event listeners"""
        
        # Navigation events
        if self.capture_navigation:
            def on_navigate(response):
                if response.ok and response.request.resource_type == "document":
                    self._record_action(RecordedAction(
                        timestamp=time.time(),
                        action_type="navigate",
                        url=response.url,
                        metadata={"status": response.status},
                    ))
            
            self.page.on("response", on_navigate)
            self._listeners.append(("response", on_navigate))
        
        # Set up CDP for click/input events
        try:
            context = self.page.context
            self._cdp_session = await context.new_cdp_session(self.page)
            
            # Enable DOM events
            await self._cdp_session.send("DOM.enable")
            await self._cdp_session.send("Overlay.enable")
            
            if self.capture_clicks:
                # Listen for click via Input domain
                await self._cdp_session.send("Input.setInterceptDrags", {"enabled": False})
            
        except Exception as e:
            logger.warning(f"[Recorder] CDP setup partial: {e}")
        
        # Use page evaluate to inject click/input listeners
        if self.capture_clicks or self.capture_inputs:
            await self._inject_event_listeners()
    
    async def _inject_event_listeners(self):
        """Inject JavaScript event listeners into page"""
        js_code = """
        () => {
            window.__nogicos_events = window.__nogicos_events || [];
            
            // Click listener
            document.addEventListener('click', (e) => {
                const target = e.target;
                const selector = target.id ? '#' + target.id :
                                 target.className ? '.' + target.className.split(' ')[0] :
                                 target.tagName.toLowerCase();
                window.__nogicos_events.push({
                    type: 'click',
                    timestamp: Date.now(),
                    selector: selector,
                    tagName: target.tagName,
                    text: target.innerText?.substring(0, 50) || '',
                    x: e.clientX,
                    y: e.clientY,
                });
            }, true);
            
            // Input listener (with debounce)
            let inputTimeout = null;
            document.addEventListener('input', (e) => {
                const target = e.target;
                if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
                    clearTimeout(inputTimeout);
                    inputTimeout = setTimeout(() => {
                        const selector = target.id ? '#' + target.id :
                                         target.name ? '[name="' + target.name + '"]' :
                                         target.tagName.toLowerCase();
                        window.__nogicos_events.push({
                            type: 'input',
                            timestamp: Date.now(),
                            selector: selector,
                            value: target.value,
                            inputType: target.type || 'text',
                        });
                    }, 500);  // Debounce 500ms
                }
            }, true);
            
            // Form submit listener
            document.addEventListener('submit', (e) => {
                const form = e.target;
                window.__nogicos_events.push({
                    type: 'submit',
                    timestamp: Date.now(),
                    selector: form.id ? '#' + form.id : 'form',
                    action: form.action,
                });
            }, true);
            
            return true;
        }
        """
        try:
            await self.page.evaluate(js_code)
            logger.debug("[Recorder] Event listeners injected")
        except Exception as e:
            logger.warning(f"[Recorder] Failed to inject listeners: {e}")
    
    async def collect_events(self) -> List[RecordedAction]:
        """Collect events from injected JavaScript"""
        try:
            events = await self.page.evaluate("() => window.__nogicos_events || []")
            
            # Clear collected events
            await self.page.evaluate("() => { window.__nogicos_events = []; }")
            
            for event in events:
                action = RecordedAction(
                    timestamp=event.get("timestamp", time.time() * 1000) / 1000,
                    action_type=event.get("type", "unknown"),
                    url=self.page.url,
                    selector=event.get("selector"),
                    value=event.get("value"),
                    coordinates={"x": event.get("x", 0), "y": event.get("y", 0)} if event.get("x") else None,
                    metadata={
                        "tagName": event.get("tagName"),
                        "text": event.get("text"),
                        "inputType": event.get("inputType"),
                    }
                )
                self._record_action(action)
            
            return self._actions
            
        except Exception as e:
            logger.warning(f"[Recorder] Failed to collect events: {e}")
            return []
    
    def _record_action(self, action: RecordedAction):
        """Add action to recording"""
        if self._recording:
            self._actions.append(action)
            logger.debug(f"[Recorder] {action.action_type}: {action.selector or action.url}")
    
    async def _remove_listeners(self):
        """Remove page event listeners"""
        for event_name, handler in self._listeners:
            try:
                self.page.remove_listener(event_name, handler)
            except:
                pass
        self._listeners = []
        
        # Clean up CDP session
        if self._cdp_session:
            try:
                await self._cdp_session.detach()
            except:
                pass
            self._cdp_session = None


class AutoRecorder:
    """
    Automatic passive recorder that runs continuously
    
    Starts/stops recording based on heuristics:
    - Significant user activity
    - Task completion patterns
    """
    
    def __init__(
        self,
        page: Page,
        min_actions: int = 3,
        idle_timeout: float = 5.0,
        on_trajectory: Callable[[RecordedTrajectory], None] = None,
    ):
        self.page = page
        self.min_actions = min_actions
        self.idle_timeout = idle_timeout
        self.on_trajectory = on_trajectory
        
        self._recorder = Recorder(page)
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._last_action_time: float = 0
    
    async def start(self):
        """Start automatic recording"""
        if self._running:
            return
        
        self._running = True
        await self._recorder.start(task="auto-recorded")
        
        # Start polling for events
        self._poll_task = asyncio.create_task(self._poll_loop())
        
        logger.info("[AutoRecorder] Started")
    
    async def stop(self):
        """Stop automatic recording"""
        if not self._running:
            return
        
        self._running = False
        
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        
        # Save final trajectory if meaningful
        trajectory = await self._recorder.stop()
        if trajectory and len(trajectory.actions) >= self.min_actions:
            await self._save_trajectory(trajectory)
        
        logger.info("[AutoRecorder] Stopped")
    
    async def _poll_loop(self):
        """Poll for events periodically"""
        while self._running:
            await asyncio.sleep(1.0)  # Poll every second
            
            try:
                await self._recorder.collect_events()
                
                if self._recorder.action_count > 0:
                    self._last_action_time = time.time()
                
                # Check for idle timeout → save trajectory
                if (self._recorder.action_count >= self.min_actions and 
                    time.time() - self._last_action_time > self.idle_timeout):
                    await self._finalize_trajectory()
                    
            except Exception as e:
                logger.warning(f"[AutoRecorder] Poll error: {e}")
    
    async def _finalize_trajectory(self):
        """Save current trajectory and reset"""
        trajectory = await self._recorder.stop()
        
        if trajectory and len(trajectory.actions) >= self.min_actions:
            await self._save_trajectory(trajectory)
        
        # Restart recording
        await self._recorder.start(task="auto-recorded")
        self._last_action_time = time.time()
    
    async def _save_trajectory(self, trajectory: RecordedTrajectory):
        """Save trajectory via callback"""
        logger.info(f"[AutoRecorder] Saving trajectory: {len(trajectory.actions)} actions")
        
        if self.on_trajectory:
            try:
                self.on_trajectory(trajectory)
            except Exception as e:
                logger.error(f"[AutoRecorder] Save callback error: {e}")


# Quick test
if __name__ == "__main__":
    import sys
    
    async def test_recorder():
        from playwright.async_api import async_playwright
        
        print("=" * 50)
        print("Recorder Test")
        print("=" * 50)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            await page.goto("https://news.ycombinator.com")
            
            recorder = Recorder(page)
            await recorder.start(task="Test recording")
            
            print("\n[Test] Recording started. Interact with the page...")
            print("[Test] Will record for 10 seconds...")
            
            # Poll for events
            for i in range(10):
                await asyncio.sleep(1)
                await recorder.collect_events()
                print(f"  Actions recorded: {recorder.action_count}")
            
            trajectory = await recorder.stop()
            
            print(f"\n[OK] Recording complete!")
            print(f"     Actions: {len(trajectory.actions)}")
            print(f"     Duration: {trajectory.end_time - trajectory.start_time:.1f}s")
            
            if trajectory.actions:
                print("\n[Actions]")
                for i, action in enumerate(trajectory.actions[:5]):
                    print(f"  {i+1}. {action.action_type}: {action.selector or action.url}")
                
                print("\n[Generated Script]")
                print(trajectory.to_playwright_script())
            
            await browser.close()
    
    asyncio.run(test_recorder())

