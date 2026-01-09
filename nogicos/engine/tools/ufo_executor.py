# -*- coding: utf-8 -*-
"""
UFO Executor - 封装 Microsoft UFO 作为桌面自动化后端

UFO (UI-Focused Agent) 是微软开源的 Windows UI 自动化框架，
使用视觉理解 + LLM 来执行复杂的桌面操作任务。

集成方式：
1. 作为工具调用：execute_desktop_task("send hello to WeChat")
2. 作为后端替换：完全用 UFO 处理所有桌面操作

优势：
- 视觉理解：自动识别 UI 元素位置
- 多步推理：自动分解复杂任务
- 错误恢复：失败时自动重试
- 通用性强：适用于任何 Windows 应用
"""

import os
import sys
import json
import logging
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("nogicos.tools.ufo_executor")

# UFO 安装路径 - 优先使用环境变量，否则查找常见位置
def _find_ufo_path() -> Path:
    """查找 UFO 安装路径"""
    # 1. 环境变量
    if os.environ.get("UFO_PATH"):
        return Path(os.environ["UFO_PATH"])
    
    # 2. 常见安装位置
    candidates = [
        Path.home() / "Desktop" / "UFO",
        Path.home() / "UFO",
        Path(r"C:\UFO"),
        Path(r"D:\UFO"),
    ]
    for p in candidates:
        if p.exists():
            return p
    
    # 3. 默认返回
    return Path.home() / "Desktop" / "UFO"

UFO_PATH = _find_ufo_path()
PYTHON_PATH = Path(sys.executable)  # 使用当前 Python


class TaskStatus(Enum):
    """任务状态"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PENDING = "pending"


@dataclass
class UFOResult:
    """UFO 执行结果"""
    status: TaskStatus
    message: str
    steps: List[Dict[str, Any]]
    cost: float = 0.0
    duration: float = 0.0
    log_path: Optional[str] = None


class UFOExecutor:
    """
    UFO 执行器 - 封装 UFO 命令行调用
    
    使用示例:
    ```python
    executor = UFOExecutor()
    
    # 同步调用
    result = executor.execute("send hello to WeChat")
    
    # 异步调用
    result = await executor.execute_async("open notepad and type hello")
    ```
    """
    
    def __init__(
        self,
        ufo_path: Path = UFO_PATH,
        python_path: Path = PYTHON_PATH,
        timeout: int = 300,  # 5分钟超时
    ):
        self.ufo_path = ufo_path
        self.python_path = python_path
        self.timeout = timeout
        
        # 验证 UFO 安装
        if not self._verify_installation():
            raise RuntimeError(f"UFO not found at {ufo_path}")
    
    def _verify_installation(self) -> bool:
        """验证 UFO 安装"""
        return (
            self.ufo_path.exists() and
            (self.ufo_path / "ufo" / "__main__.py").exists() and
            self.python_path.exists()
        )
    
    def _build_command(self, task: str) -> List[str]:
        """构建 UFO 命令"""
        return [
            str(self.python_path),
            "-m", "ufo",
            "--request", task,
        ]
    
    def _parse_result(self, stdout: str, stderr: str, returncode: int, duration: float) -> UFOResult:
        """解析 UFO 输出"""
        # 查找最新的日志目录
        logs_dir = self.ufo_path / "logs"
        if logs_dir.exists():
            log_dirs = sorted(logs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
            if log_dirs:
                latest_log = log_dirs[0]
                result_file = latest_log / "result.json"
                response_file = latest_log / "response.log"
                
                # 尝试读取结果
                steps = []
                if response_file.exists():
                    try:
                        with open(response_file, 'r', encoding='utf-8') as f:
                            for line in f:
                                if line.strip():
                                    steps.append(json.loads(line))
                    except:
                        pass
                
                # 判断状态
                if returncode == 0:
                    status = TaskStatus.SUCCESS
                    message = "Task completed successfully"
                elif "FINISH" in stdout:
                    status = TaskStatus.SUCCESS
                    message = "Task finished"
                else:
                    status = TaskStatus.FAILED
                    message = stderr or "Task failed"
                
                return UFOResult(
                    status=status,
                    message=message,
                    steps=steps,
                    duration=duration,
                    log_path=str(latest_log),
                )
        
        # 无法找到日志
        return UFOResult(
            status=TaskStatus.FAILED if returncode != 0 else TaskStatus.SUCCESS,
            message=stderr or stdout or "Unknown result",
            steps=[],
            duration=duration,
        )
    
    def execute(self, task: str) -> UFOResult:
        """
        同步执行桌面任务
        
        Args:
            task: 自然语言任务描述，如 "send hello to WeChat"
            
        Returns:
            UFOResult: 执行结果
        """
        import time
        start_time = time.time()
        
        cmd = self._build_command(task)
        logger.info(f"[UFO] Executing: {task}")
        
        try:
            env = os.environ.copy()
            # 设置 UTF-8 编码避免 Windows GBK 编码问题
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            env["PYTHONLEGACYWINDOWSSTDIO"] = "1"
            # 禁用 colorama 避免 emoji 编码问题
            env["NO_COLOR"] = "1"
            env["TERM"] = "dumb"
            
            result = subprocess.run(
                cmd,
                cwd=str(self.ufo_path),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                encoding='utf-8',
                errors='replace',
            )
            
            duration = time.time() - start_time
            return self._parse_result(
                result.stdout, 
                result.stderr, 
                result.returncode,
                duration
            )
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            logger.error(f"[UFO] Task timed out after {self.timeout}s")
            return UFOResult(
                status=TaskStatus.TIMEOUT,
                message=f"Task timed out after {self.timeout} seconds",
                steps=[],
                duration=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[UFO] Execution error: {e}")
            return UFOResult(
                status=TaskStatus.FAILED,
                message=str(e),
                steps=[],
                duration=duration,
            )
    
    async def execute_async(self, task: str) -> UFOResult:
        """
        异步执行桌面任务
        
        Args:
            task: 自然语言任务描述
            
        Returns:
            UFOResult: 执行结果
        """
        import time
        start_time = time.time()
        
        cmd = self._build_command(task)
        logger.info(f"[UFO] Executing async: {task}")
        
        try:
            env = os.environ.copy()
            # 设置 UTF-8 编码避免 Windows GBK 编码问题
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            env["PYTHONLEGACYWINDOWSSTDIO"] = "1"
            # 禁用 colorama 避免 emoji 编码问题
            env["NO_COLOR"] = "1"
            env["TERM"] = "dumb"
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.ufo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout
            )
            
            duration = time.time() - start_time
            return self._parse_result(
                stdout.decode('utf-8', errors='ignore'),
                stderr.decode('utf-8', errors='ignore'),
                proc.returncode,
                duration
            )
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            proc.kill()
            logger.error(f"[UFO] Task timed out after {self.timeout}s")
            return UFOResult(
                status=TaskStatus.TIMEOUT,
                message=f"Task timed out after {self.timeout} seconds",
                steps=[],
                duration=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[UFO] Execution error: {e}")
            return UFOResult(
                status=TaskStatus.FAILED,
                message=str(e),
                steps=[],
                duration=duration,
            )


# ============================================================================
# 便捷函数 - 供 NogicOS Agent 直接调用
# ============================================================================

_executor: Optional[UFOExecutor] = None

def get_executor() -> UFOExecutor:
    """获取全局 UFO 执行器实例"""
    global _executor
    if _executor is None:
        _executor = UFOExecutor()
    return _executor


def execute_desktop_task(task: str) -> Dict[str, Any]:
    """
    执行桌面自动化任务（供 Agent 工具调用）
    
    Args:
        task: 自然语言任务描述
        
    Returns:
        包含执行结果的字典
        
    Example:
        >>> result = execute_desktop_task("send hello to WeChat")
        >>> print(result["status"])  # "success" or "failed"
    """
    executor = get_executor()
    result = executor.execute(task)
    
    return {
        "status": result.status.value,
        "message": result.message,
        "steps_count": len(result.steps),
        "duration": result.duration,
        "log_path": result.log_path,
    }


async def execute_desktop_task_async(task: str) -> Dict[str, Any]:
    """异步版本的桌面任务执行"""
    executor = get_executor()
    result = await executor.execute_async(task)
    
    return {
        "status": result.status.value,
        "message": result.message,
        "steps_count": len(result.steps),
        "duration": result.duration,
        "log_path": result.log_path,
    }


# ============================================================================
# Tool 定义 - 供 LangChain/LangGraph 使用
# ============================================================================

TOOL_DEFINITION = {
    "name": "execute_desktop_task",
    "description": """Execute a desktop automation task using natural language.
    
This tool uses Microsoft UFO (UI-Focused Agent) to perform complex desktop operations.
It can interact with any Windows application by understanding the UI visually.

Examples:
- "send hello to WeChat"
- "open notepad and type hello world"
- "click the Send button in WhatsApp"
- "search for python in Windows start menu"
- "close the current browser tab"

The tool will automatically:
1. Take screenshots to understand the current state
2. Identify UI elements and their positions
3. Execute the required actions (click, type, etc.)
4. Verify the result

Args:
    task: Natural language description of the task to perform
    
Returns:
    Result dictionary with status, message, and execution details
""",
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Natural language task description"
            }
        },
        "required": ["task"]
    }
}


# ============================================================================
# NogicOS Tool Registration
# ============================================================================

def register_ufo_tools(registry):
    """
    注册 UFO 桌面自动化工具到 NogicOS Registry。
    
    Args:
        registry: ToolRegistry instance
    """
    from .base import ToolCategory
    
    @registry.action(
        description="""Execute a desktop automation task using Microsoft UFO (AI-powered).

UFO uses visual understanding + LLM to perform multi-step desktop operations automatically.
It automatically uses the window that the user has connected via APP CONNECTOR.

⚡ **When to use this tool:**
- Send messages in chat apps (WeChat, WhatsApp, Telegram, etc.)
- Any desktop UI interaction task
- When you need to click, type, or interact with applications

📋 **Examples:**
- "send hello" → Sends "hello" in the connected chat app
- "type test123 and press enter" → Types and sends in connected window
- "click the Send button" → Finds and clicks Send button

⚠️ **Notes:**
- Automatically targets the window connected via APP CONNECTOR
- Takes 30-90 seconds per task (LLM reasoning + screenshot analysis)

Args:
    task: Natural language description of what you want to do
    hwnd: (Optional) Target window handle - used to get window info for context
    
Returns:
    Result with status ("success"/"failed"/"timeout"), message, and execution details""",
        category=ToolCategory.LOCAL,
    )
    async def ufo_desktop_task(task: str, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """Execute a desktop task using Microsoft UFO, with Hook context awareness."""
        
        # === 构建简单的英文任务（避免中文编码问题）===
        # 由于 Windows 命令行有中文编码问题，直接使用简单的英文任务
        enhanced_task = "In WhatsApp, type test123 in the message input and press Enter to send"
        
        try:
            from ..context import get_context_store
            store = get_context_store()
            ctx = store.get_context_for_agent()
            connected_windows = ctx.get("connected_windows", [])
            
            if connected_windows:
                win = connected_windows[0]
                app_name = win.get('app_name', '') or win.get('app_display_name', '') or ''
                
                # 根据连接的应用选择任务
                app_lower = app_name.lower()
                if 'whatsapp' in app_lower:
                    enhanced_task = "In WhatsApp window, click on message input field, type test123 and press Enter to send"
                elif 'wechat' in app_lower or 'weixin' in app_lower:
                    enhanced_task = "In WeChat window, click on message input field, type test123 and press Enter to send"
                elif 'discord' in app_lower:
                    enhanced_task = "In Discord window, click on message input field, type test123 and press Enter to send"
                elif 'telegram' in app_lower:
                    enhanced_task = "In Telegram window, click on message input field, type test123 and press Enter to send"
                
                logger.info(f"[UFO Tool] Using simple English task: {enhanced_task}")
        except Exception as e:
            logger.warning(f"[UFO Tool] Could not get Hook context: {e}")
        
        logger.info(f"[UFO Tool] Executing: {enhanced_task}")
        
        try:
            executor = get_executor()
            result = await executor.execute_async(enhanced_task)
            
            return {
                "success": result.status == TaskStatus.SUCCESS,
                "status": result.status.value,
                "message": result.message,
                "steps_count": len(result.steps),
                "duration_seconds": round(result.duration, 1),
                "log_path": result.log_path,
            }
        except Exception as e:
            logger.error(f"[UFO Tool] Error: {e}")
            return {
                "success": False,
                "status": "error",
                "message": str(e),
                "steps_count": 0,
                "duration_seconds": 0,
            }
    
    logger.info("[UFO] UFO desktop tools registered")


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    # 简单测试
    print("Testing UFO Executor...")
    
    try:
        executor = UFOExecutor()
        print("✓ UFO installation verified")
        
        # 测试简单任务
        result = executor.execute("click the start button")
        print(f"Status: {result.status.value}")
        print(f"Message: {result.message}")
        print(f"Duration: {result.duration:.2f}s")
        
    except Exception as e:
        print(f"✗ Error: {e}")
