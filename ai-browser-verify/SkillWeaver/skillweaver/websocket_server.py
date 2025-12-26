"""
SkillFlow WebSocket 客户端 (同步版本)
使用 websocket-client 库，避免 asyncio/nest_asyncio 冲突
"""
import json
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import websocket  # websocket-client 库（同步）

# 消息类型
class MessageType(str, Enum):
    # 连接
    CONNECTED = "connected"
    
    # 任务
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_ERROR = "task_error"
    
    # 步骤
    STEP_START = "step_start"
    STEP_THINKING = "step_thinking"
    STEP_ACTION = "step_action"
    STEP_RESULT = "step_result"
    STEP_COMPLETE = "step_complete"
    
    # 技能
    SKILL_MATCHED = "skill_matched"
    SKILL_EXECUTING = "skill_executing"
    SKILL_RESULT = "skill_result"
    
    # 学习
    LEARN_START = "learn_start"
    LEARN_PROGRESS = "learn_progress"
    SKILL_DISCOVERED = "skill_discovered"
    LEARN_COMPLETE = "learn_complete"
    
    # 知识库
    KB_LOADED = "kb_loaded"
    SKILL_LIST = "skill_list"
    
    # AI 可视化动画（NogicOS Atlas 体验）
    CURSOR_MOVE = "cursor_move"
    CURSOR_CLICK = "cursor_click"
    CURSOR_TYPE = "cursor_type"
    CURSOR_STOP_TYPE = "cursor_stop_type"
    HIGHLIGHT = "highlight"
    HIGHLIGHT_HIDE = "highlight_hide"
    SCREEN_GLOW = "screen_glow"
    SCREEN_GLOW_STOP = "screen_glow_stop"
    SCREEN_PULSE = "screen_pulse"


@dataclass
class ExecutionMessage:
    """执行消息"""
    type: MessageType
    data: dict
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value if isinstance(self.type, MessageType) else self.type,
            "data": self.data,
            "timestamp": self.timestamp
        })


class SkillFlowWebSocketClient:
    """同步 WebSocket 客户端 - 连接到 NogicOS 服务器"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}"
        self.ws: Optional[websocket.WebSocket] = None
        self._connected = False
        self._lock = threading.Lock()
    
    def connect(self):
        """连接到服务器（同步）"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.ws = websocket.create_connection(
                    self.uri,
                    timeout=5
                )
                self._connected = True
                print(f"[SkillFlow WS] Connected to {self.uri}")
                return True
            except Exception as e:
                print(f"[SkillFlow WS] Connection attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)
        
        self._connected = False
        return False
    
    def send(self, message: ExecutionMessage):
        """发送消息（同步，线程安全）"""
        if not self._connected or not self.ws:
            # 尝试重连
            if not self.connect():
                print(f"[SkillFlow WS] Cannot send, not connected")
                return False
        
        json_msg = message.to_json()
        
        with self._lock:
            try:
                self.ws.send(json_msg)
                return True
            except Exception as e:
                print(f"[SkillFlow WS] Send error: {e}")
                self._connected = False
                return False
    
    def send_sync(self, message: ExecutionMessage):
        """同步发送（别名，保持 API 兼容性）"""
        return self.send(message)
    
    def start(self):
        """启动客户端（连接）"""
        self.connect()
        return self
    
    def stop(self):
        """停止客户端"""
        self._connected = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass


# 全局客户端实例
_client: Optional[SkillFlowWebSocketClient] = None


def get_client() -> SkillFlowWebSocketClient:
    """获取客户端实例"""
    global _client
    if _client is None:
        _client = SkillFlowWebSocketClient()
    return _client


def start_server():
    """启动客户端（保持 API 兼容性）"""
    print("[SkillFlow] Starting WebSocket client...")
    client = get_client()
    client.start()
    return client


def broadcast_sync(msg_type: MessageType, data: dict):
    """同步发送消息"""
    client = get_client()
    client.send_sync(ExecutionMessage(type=msg_type, data=data))


# 便捷广播函数
def broadcast_task_start(task: str, url: str, has_kb: bool = False):
    broadcast_sync(MessageType.TASK_START, {
        "task": task,
        "url": url,
        "has_knowledge_base": has_kb
    })


def broadcast_task_complete(task: str, success: bool, duration: float, steps: int):
    broadcast_sync(MessageType.TASK_COMPLETE, {
        "task": task,
        "success": success,
        "duration": duration,
        "total_steps": steps
    })


def broadcast_task_error(task: str, error: str):
    broadcast_sync(MessageType.TASK_ERROR, {
        "task": task,
        "error": error
    })


def broadcast_step_start(step: int, max_steps: int):
    broadcast_sync(MessageType.STEP_START, {
        "step": step,
        "max_steps": max_steps
    })


def broadcast_step_thinking(step: int, reasoning: str):
    broadcast_sync(MessageType.STEP_THINKING, {
        "step": step,
        "reasoning": reasoning
    })


def broadcast_step_action(step: int, action_type: str, detail: str, code: str = ""):
    broadcast_sync(MessageType.STEP_ACTION, {
        "step": step,
        "action_type": action_type,
        "detail": detail,
        "code": code
    })


def broadcast_step_result(step: int, success: bool, result: str = None, error: str = None):
    broadcast_sync(MessageType.STEP_RESULT, {
        "step": step,
        "success": success,
        "result": result,
        "error": error
    })


def broadcast_step_complete(step: int, duration: float):
    broadcast_sync(MessageType.STEP_COMPLETE, {
        "step": step,
        "duration": duration
    })


def broadcast_skill_matched(skill_name: str, description: str, confidence: float = 1.0):
    broadcast_sync(MessageType.SKILL_MATCHED, {
        "skill_name": skill_name,
        "description": description,
        "confidence": confidence
    })


def broadcast_skill_executing(skill_name: str, params: dict = None):
    broadcast_sync(MessageType.SKILL_EXECUTING, {
        "skill_name": skill_name,
        "params": params or {}
    })


def broadcast_skill_result(skill_name: str, success: bool, result: str = None):
    broadcast_sync(MessageType.SKILL_RESULT, {
        "skill_name": skill_name,
        "success": success,
        "result": result
    })


def broadcast_learn_start(url: str):
    broadcast_sync(MessageType.LEARN_START, {
        "url": url
    })


def broadcast_learn_progress(message: str, progress: float = None):
    broadcast_sync(MessageType.LEARN_PROGRESS, {
        "message": message,
        "progress": progress
    })


def broadcast_skill_discovered(skill_name: str, description: str, source: str = "exploration"):
    broadcast_sync(MessageType.SKILL_DISCOVERED, {
        "skill_name": skill_name,
        "description": description,
        "source": source
    })


def broadcast_learn_complete(skills_count: int, duration: float):
    broadcast_sync(MessageType.LEARN_COMPLETE, {
        "skills_count": skills_count,
        "duration": duration
    })


def broadcast_kb_loaded(path: str, skills_count: int):
    broadcast_sync(MessageType.KB_LOADED, {
        "path": path,
        "skills_count": skills_count
    })


def broadcast_skill_list(skills: list):
    broadcast_sync(MessageType.SKILL_LIST, {
        "skills": skills
    })


# AI 可视化动画函数
def broadcast_cursor_move(x: int, y: int, duration: float = 0.5):
    broadcast_sync(MessageType.CURSOR_MOVE, {
        "x": x,
        "y": y,
        "duration": duration
    })


def broadcast_cursor_click(x: int, y: int):
    broadcast_sync(MessageType.CURSOR_CLICK, {
        "x": x,
        "y": y
    })


def broadcast_cursor_type(text: str):
    broadcast_sync(MessageType.CURSOR_TYPE, {
        "text": text
    })


def broadcast_cursor_stop_type():
    broadcast_sync(MessageType.CURSOR_STOP_TYPE, {})


def broadcast_highlight(selector: str, label: str = None, color: str = "blue"):
    broadcast_sync(MessageType.HIGHLIGHT, {
        "selector": selector,
        "label": label,
        "color": color
    })


def broadcast_highlight_hide():
    broadcast_sync(MessageType.HIGHLIGHT_HIDE, {})


def broadcast_screen_glow(color: str = "blue", intensity: float = 0.5):
    broadcast_sync(MessageType.SCREEN_GLOW, {
        "color": color,
        "intensity": intensity
    })


def broadcast_screen_glow_stop():
    broadcast_sync(MessageType.SCREEN_GLOW_STOP, {})


def broadcast_screen_pulse(color: str = "green"):
    broadcast_sync(MessageType.SCREEN_PULSE, {
        "color": color
    })
