# -*- coding: utf-8 -*-
"""
WebSocket Server - Real-time status broadcast to Electron client

Architecture:
    Python Engine → WebSocket Server → Electron Client
    
Message Types:
    - status: Agent state, learning state, knowledge stats
    - action: Current action being executed
    - result: Task completion result
    - error: Error notification

Usage:
    server = StatusServer()
    await server.start()
    await server.broadcast_status({"agent": "thinking"})
"""

import asyncio
import json
import logging
from typing import Set, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger("nogicos.server")

# Try to import websockets, gracefully handle if not installed
try:
    import websockets
    # Use TYPE_CHECKING to avoid deprecation warning at runtime
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("[Server] websockets not installed. Run: pip install websockets")


@dataclass
class AgentStatus:
    """Current agent status"""
    state: str = "idle"  # idle, thinking, acting, done, error
    task: str = ""
    step: int = 0
    max_steps: int = 10
    progress: float = 0.0
    last_action: str = ""
    error: Optional[str] = None


@dataclass
class LearningStatus:
    """Passive learning status"""
    state: str = "idle"  # idle, recording, saved
    action_count: int = 0
    last_saved: Optional[str] = None


@dataclass
class KnowledgeStats:
    """Knowledge store statistics"""
    trajectory_count: int = 0
    domain_count: int = 0
    domains: list = None
    
    def __post_init__(self):
        if self.domains is None:
            self.domains = []


@dataclass
class FullStatus:
    """Complete status for broadcast"""
    agent: AgentStatus
    learning: LearningStatus
    knowledge: KnowledgeStats
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return {
            "type": "status",
            "data": {
                "agent": asdict(self.agent),
                "learning": asdict(self.learning),
                "knowledge": asdict(self.knowledge),
                "timestamp": self.timestamp,
            }
        }


class StatusServer:
    """
    WebSocket server for broadcasting status to Electron client
    """
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self._clients: Set = set()
        self._server = None
        self._running = False
        
        # Current status
        self._agent_status = AgentStatus()
        self._learning_status = LearningStatus()
        self._knowledge_stats = KnowledgeStats()
        
        # CDP 响应回调（用于 Python → Electron → Python 的双向通信）
        self._cdp_response_handlers: Dict[str, Any] = {}
    
    @property
    def client_count(self) -> int:
        return len(self._clients)
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    async def start(self):
        """Start WebSocket server"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("[Server] Cannot start: websockets not installed")
            return False
        
        if self._running:
            logger.warning("[Server] Already running")
            return True
        
        try:
            self._server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port,
            )
            self._running = True
            logger.info(f"[Server] WebSocket server started at ws://{self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"[Server] Failed to start: {e}")
            return False
    
    async def stop(self):
        """Stop WebSocket server"""
        if not self._running:
            return
        
        self._running = False
        
        # Close all client connections
        if self._clients:
            await asyncio.gather(
                *[client.close() for client in self._clients],
                return_exceptions=True
            )
            self._clients.clear()
        
        # Close server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        
        logger.info("[Server] WebSocket server stopped")
    
    async def _handle_client(self, websocket):
        """Handle new client connection"""
        self._clients.add(websocket)
        client_id = id(websocket)
        logger.info(f"[Server] Client connected: {client_id} (total: {len(self._clients)})")
        
        try:
            # Send current status on connect
            await self._send_full_status(websocket)
            
            # Handle incoming messages
            async for message in websocket:
                await self._handle_message(websocket, message)
                
        except websockets.ConnectionClosed:
            logger.info(f"[Server] Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"[Server] Client error: {e}")
        finally:
            self._clients.discard(websocket)
            logger.info(f"[Server] Client removed: {client_id} (remaining: {len(self._clients)})")
    
    async def _handle_message(self, websocket, message: str):
        """Handle incoming message from client"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")
            
            if msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong"}))
            
            elif msg_type == "get_status":
                await self._send_full_status(websocket)
            
            elif msg_type == "command":
                # Handle commands from client (future use)
                cmd = data.get("command", "")
                logger.info(f"[Server] Received command: {cmd}")
            
            # CDP 命令转发（方案 A）
            elif msg_type == "cdp_command":
                # 转发 CDP 命令到所有其他客户端（主要是 Electron）
                await self._forward_cdp_message(websocket, data)
            
            elif msg_type == "cdp_response":
                # 转发 CDP 响应到所有其他客户端
                await self._forward_cdp_message(websocket, data)
            
            elif msg_type == "cdp_ready":
                # 转发 CDP 就绪状态
                await self._forward_cdp_message(websocket, data)
            
        except json.JSONDecodeError:
            logger.warning(f"[Server] Invalid JSON: {message}")
    
    async def _forward_cdp_message(self, sender, data: dict):
        """Forward CDP messages to all other clients"""
        msg_str = json.dumps(data)
        
        # 发送给除发送者以外的所有客户端
        for client in self._clients:
            if client != sender:
                try:
                    await client.send(msg_str)
                except Exception as e:
                    logger.error(f"[Server] CDP forward error: {e}")
        
        # 如果是 cdp_response，同时通知内部处理器
        msg_type = data.get("type")
        if msg_type == "cdp_response":
            request_id = data.get("requestId")
            if request_id and request_id in self._cdp_response_handlers:
                handler = self._cdp_response_handlers[request_id]
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"[Server] CDP response handler error: {e}")
    
    async def send_cdp_command(self, method: str, params: dict = None, timeout: float = 30.0) -> dict:
        """
        发送 CDP 命令并等待响应（用于 Python 内部调用）
        
        Args:
            method: CDP 命令方法名
            params: 命令参数
            timeout: 超时时间（秒）
            
        Returns:
            CDP 命令响应
        """
        import uuid
        request_id = str(uuid.uuid4())
        
        # 创建 Future 来等待响应
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        
        def on_response(data):
            if not future.done():
                error = data.get("error")
                if error:
                    future.set_exception(Exception(error))
                else:
                    future.set_result(data.get("result"))
        
        # 注册响应处理器
        self._cdp_response_handlers[request_id] = on_response
        
        try:
            # 发送命令到所有客户端（Electron 会处理 cdp_command）
            await self.broadcast({
                "type": "cdp_command",
                "data": {
                    "requestId": request_id,
                    "method": method,
                    "params": params or {},
                }
            })
            
            # 等待响应
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            raise Exception(f"CDP command timeout: {method}")
        finally:
            # 清理处理器
            self._cdp_response_handlers.pop(request_id, None)
    
    async def _send_full_status(self, websocket):
        """Send full status to a specific client"""
        status = FullStatus(
            agent=self._agent_status,
            learning=self._learning_status,
            knowledge=self._knowledge_stats,
        )
        await websocket.send(json.dumps(status.to_dict()))
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        if not self._clients:
            return
        
        msg_str = json.dumps(message)
        await asyncio.gather(
            *[client.send(msg_str) for client in self._clients],
            return_exceptions=True
        )
    
    async def broadcast_status(self):
        """Broadcast current status to all clients"""
        status = FullStatus(
            agent=self._agent_status,
            learning=self._learning_status,
            knowledge=self._knowledge_stats,
        )
        await self.broadcast(status.to_dict())
    
    # Status update methods
    
    def update_agent(
        self,
        state: str = None,
        task: str = None,
        step: int = None,
        max_steps: int = None,
        last_action: str = None,
        error: str = None,
        progress: float = None,
    ):
        """Update agent status"""
        if state is not None:
            self._agent_status.state = state
        if task is not None:
            self._agent_status.task = task
        if step is not None:
            self._agent_status.step = step
            if self._agent_status.max_steps > 0:
                self._agent_status.progress = step / self._agent_status.max_steps
        if max_steps is not None:
            self._agent_status.max_steps = max_steps
        if last_action is not None:
            self._agent_status.last_action = last_action
        if error is not None:
            self._agent_status.error = error
        if progress is not None:
            self._agent_status.progress = progress
    
    def update_learning(
        self,
        state: str = None,
        action_count: int = None,
    ):
        """Update learning status"""
        if state is not None:
            self._learning_status.state = state
            if state == "saved":
                self._learning_status.last_saved = datetime.now().isoformat()
        if action_count is not None:
            self._learning_status.action_count = action_count
    
    def update_knowledge(
        self,
        trajectory_count: int = None,
        domain_count: int = None,
        domains: list = None,
    ):
        """Update knowledge stats"""
        if trajectory_count is not None:
            self._knowledge_stats.trajectory_count = trajectory_count
        if domain_count is not None:
            self._knowledge_stats.domain_count = domain_count
        if domains is not None:
            self._knowledge_stats.domains = domains
    
    async def broadcast_frame(
        self,
        image_base64: str,
        action: str = None,
        step: int = 0,
        total_steps: int = 0,
    ):
        """
        Broadcast screenshot frame to all clients.
        
        Used by screenshot streamer to send real-time browser visuals.
        
        Args:
            image_base64: JPEG image as base64 string
            action: Current action description
            step: Current step number
            total_steps: Total steps in task
        """
        if not self._clients:
            return
        
        message = {
            "type": "frame",
            "data": {
                "image": image_base64,
                "action": action,
                "step": step,
                "total_steps": total_steps,
            }
        }
        
        msg_str = json.dumps(message)
        await asyncio.gather(
            *[client.send(msg_str) for client in self._clients],
            return_exceptions=True
        )
    
    async def broadcast_action(self, action: str, step: int = 0, total_steps: int = 0):
        """Broadcast action update (without frame)"""
        message = {
            "type": "action",
            "data": {
                "action": action,
                "step": step,
                "total_steps": total_steps,
            }
        }
        await self.broadcast(message)


# Global server instance
_server: Optional[StatusServer] = None


def get_server() -> StatusServer:
    """Get or create global server instance"""
    global _server
    if _server is None:
        _server = StatusServer()
    return _server


async def start_server(host: str = "localhost", port: int = 8765) -> StatusServer:
    """Start global server"""
    global _server
    _server = StatusServer(host, port)
    await _server.start()
    return _server


# Quick test
if __name__ == "__main__":
    async def test_server():
        print("=" * 50)
        print("WebSocket Server Test")
        print("=" * 50)
        
        if not WEBSOCKETS_AVAILABLE:
            print("[ERROR] websockets not installed!")
            print("Run: pip install websockets")
            return
        
        server = StatusServer()
        await server.start()
        
        print(f"\n[Server] Running at ws://{server.host}:{server.port}")
        print("[Server] Connect with a WebSocket client to test")
        print("[Server] Press Ctrl+C to stop\n")
        
        # Simulate status updates
        try:
            for i in range(100):
                await asyncio.sleep(2)
                
                # Update agent status
                server.update_agent(
                    state="thinking" if i % 2 == 0 else "acting",
                    step=i % 5,
                    task="Demo task",
                )
                
                # Broadcast
                await server.broadcast_status()
                print(f"[Server] Broadcast #{i+1} (clients: {server.client_count})")
                
        except KeyboardInterrupt:
            print("\n[Server] Stopping...")
        
        await server.stop()
        print("[Server] Done")
    
    asyncio.run(test_server())

