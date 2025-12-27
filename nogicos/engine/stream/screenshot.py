# -*- coding: utf-8 -*-
"""
Screenshot Streamer

Captures browser screenshots and streams them via WebSocket.
Designed for AI operation visualization without external browsers.

Architecture:
    Playwright (headless) ──► Screenshot ──► Base64 ──► WebSocket ──► Electron UI

Features:
    - JPEG compression for minimal bandwidth
    - Configurable FPS (default 10)
    - Action overlay rendering
    - Minimal latency (~50ms per frame)
"""

import asyncio
import base64
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from playwright.async_api import Page

logger = logging.getLogger("nogicos.stream")


@dataclass
class StreamConfig:
    """Screenshot stream configuration"""
    fps: int = 10  # Frames per second
    quality: int = 70  # JPEG quality (0-100)
    scale: str = "css"  # "css" or "device"
    max_width: int = 1280  # Max screenshot width
    max_height: int = 720  # Max screenshot height


@dataclass
class FrameData:
    """Single frame data"""
    image_base64: str
    timestamp: float
    action: Optional[str] = None
    step: int = 0
    total_steps: int = 0


class ScreenshotStreamer:
    """
    Captures and streams browser screenshots in real-time.
    
    Usage:
        streamer = ScreenshotStreamer(page, config)
        streamer.on_frame(callback)  # Register callback for new frames
        
        await streamer.start()
        # ... do browser operations ...
        await streamer.stop()
    """
    
    def __init__(
        self, 
        page: Page, 
        config: Optional[StreamConfig] = None,
        on_frame: Optional[Callable[[FrameData], Any]] = None,
    ):
        self.page = page
        self.config = config or StreamConfig()
        self._on_frame = on_frame
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_action: Optional[str] = None
        self._current_step = 0
        self._total_steps = 0
        
        # Stats
        self._frame_count = 0
        self._start_time = 0.0
        self._last_frame_time = 0.0
        
    def on_frame(self, callback: Callable[[FrameData], Any]):
        """Register callback for new frames"""
        self._on_frame = callback
        
    def set_action(self, action: str, step: int = 0, total_steps: int = 0):
        """Set current action being performed (shown on overlay)"""
        self._current_action = action
        self._current_step = step
        self._total_steps = total_steps
        
    def clear_action(self):
        """Clear action overlay"""
        self._current_action = None
        
    async def start(self):
        """Start continuous screenshot streaming"""
        if self._running:
            return
            
        self._running = True
        self._start_time = time.time()
        self._frame_count = 0
        
        logger.info(f"[Stream] Starting at {self.config.fps} FPS, quality={self.config.quality}")
        
        self._task = asyncio.create_task(self._stream_loop())
        
    async def stop(self):
        """Stop streaming"""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        elapsed = time.time() - self._start_time
        actual_fps = self._frame_count / elapsed if elapsed > 0 else 0
        logger.info(f"[Stream] Stopped. Sent {self._frame_count} frames, actual FPS: {actual_fps:.1f}")
        
    async def capture_frame(self) -> Optional[FrameData]:
        """Capture a single frame"""
        try:
            # Take screenshot as JPEG bytes
            screenshot_bytes = await self.page.screenshot(
                type="jpeg",
                quality=self.config.quality,
                scale=self.config.scale,
            )
            
            # Encode to base64
            image_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            
            frame = FrameData(
                image_base64=image_base64,
                timestamp=time.time(),
                action=self._current_action,
                step=self._current_step,
                total_steps=self._total_steps,
            )
            
            self._frame_count += 1
            self._last_frame_time = time.time()
            
            return frame
            
        except Exception as e:
            logger.warning(f"[Stream] Screenshot failed: {e}")
            return None
            
    async def send_frame(self, frame: Optional[FrameData] = None):
        """Capture and send a single frame (for event-driven streaming)"""
        if frame is None:
            frame = await self.capture_frame()
            
        if frame and self._on_frame:
            try:
                result = self._on_frame(frame)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning(f"[Stream] Frame callback error: {e}")
                
    async def _stream_loop(self):
        """Continuous streaming loop"""
        interval = 1.0 / self.config.fps
        
        while self._running:
            loop_start = time.time()
            
            # Capture and send frame
            frame = await self.capture_frame()
            if frame:
                await self.send_frame(frame)
            
            # Wait for next frame
            elapsed = time.time() - loop_start
            sleep_time = max(0, interval - elapsed)
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                # Frame took too long, skip sleep
                logger.debug(f"[Stream] Frame took {elapsed*1000:.0f}ms, target {interval*1000:.0f}ms")


class EventDrivenStreamer(ScreenshotStreamer):
    """
    Event-driven screenshot streamer.
    
    Instead of continuous FPS-based streaming, captures screenshots
    only when actions occur. Better for bandwidth efficiency.
    
    Usage:
        streamer = EventDrivenStreamer(page)
        streamer.on_frame(callback)
        
        # When action happens:
        await streamer.capture_action("Clicking button", step=1, total=5)
    """
    
    async def start(self):
        """Just mark as running, no continuous loop"""
        self._running = True
        self._start_time = time.time()
        self._frame_count = 0
        logger.info("[Stream] Event-driven streamer ready")
        
    async def stop(self):
        """Mark as stopped"""
        self._running = False
        elapsed = time.time() - self._start_time
        logger.info(f"[Stream] Stopped. Sent {self._frame_count} frames in {elapsed:.1f}s")
        
    async def capture_action(
        self, 
        action: str, 
        step: int = 0, 
        total_steps: int = 0,
        delay_before: float = 0.1,
        delay_after: float = 0.3,
    ):
        """
        Capture screenshot when an action occurs.
        
        Args:
            action: Description of the action
            step: Current step number
            total_steps: Total steps in task
            delay_before: Wait before capturing (to see action starting)
            delay_after: Wait after capturing (to see action result)
        """
        if not self._running:
            return
            
        self.set_action(action, step, total_steps)
        
        # Small delay to let page update
        if delay_before > 0:
            await asyncio.sleep(delay_before)
        
        # Capture and send
        await self.send_frame()
        
        # Post-action delay
        if delay_after > 0:
            await asyncio.sleep(delay_after)
            await self.send_frame()  # Capture result
            
        self.clear_action()

