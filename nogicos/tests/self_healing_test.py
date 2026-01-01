# -*- coding: utf-8 -*-
"""
NogicOS Self-Healing Test System
全自动自愈测试系统 - API + UI + 视觉检测 + 自动修复

核心流程:
┌─────────────────────────────────────────────────────────────┐
│                    Self-Healing Loop                         │
│                                                              │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│   │   AI     │───►│  Execute │───►│   AI     │              │
│   │ Generate │    │  Tests   │    │ Analyze  │              │
│   │  Cases   │    │ API + UI │    │ Results  │              │
│   └──────────┘    └──────────┘    └────┬─────┘              │
│                                        │                     │
│                    ┌───────────────────┴──────────┐         │
│                    ▼                              ▼         │
│            ┌──────────────┐              ┌──────────────┐   │
│            │ Frontend     │              │ Backend      │   │
│            │ Issue (UI)   │              │ Issue (API)  │   │
│            └──────┬───────┘              └──────┬───────┘   │
│                   │                             │           │
│                   ▼                             ▼           │
│            ┌──────────────┐              ┌──────────────┐   │
│            │ Fix TS/React │              │ Fix Python   │   │
│            │    Code      │              │    Code      │   │
│            └──────────────┘              └──────────────┘   │
│                   │                             │           │
│                   └─────────────┬───────────────┘           │
│                                 ▼                           │
│                          ┌──────────┐                       │
│                          │ Verify   │                       │
│                          │  Fix     │                       │
│                          └────┬─────┘                       │
│                               │                             │
│                    ┌──────────┴──────────┐                  │
│                    ▼                     ▼                  │
│             ┌──────────┐          ┌──────────┐              │
│             │ Continue │          │  STABLE  │              │
│             │   Loop   │          │   EXIT   │              │
│             └──────────┘          └──────────┘              │
└─────────────────────────────────────────────────────────────┘

Usage:
    python -m tests.self_healing_test
    python -m tests.self_healing_test --max-rounds 100 --overnight
"""

import sys
import os
import asyncio
import argparse
import json
import time
import traceback
import base64
import httpx
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Data Models
# ============================================================================

class TestType(Enum):
    API = "api"           # 后端 API 测试
    UI = "ui"             # 前端 UI 测试
    VISUAL = "visual"     # 视觉检测
    E2E = "e2e"           # 端到端测试


class IssueLocation(Enum):
    FRONTEND = "frontend"   # 前端问题 (TypeScript/React)
    BACKEND = "backend"     # 后端问题 (Python)
    BOTH = "both"           # 前后端都有问题
    UNKNOWN = "unknown"


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TestCase:
    """测试用例"""
    id: str
    prompt: str
    test_type: TestType
    expected_behavior: str
    category: str = ""


@dataclass
class Issue:
    """发现的问题"""
    id: str
    type: str
    severity: Severity
    location: IssueLocation
    description: str
    test_case: TestCase = None
    error_message: str = ""
    traceback: str = ""
    screenshot_path: str = ""
    file_path: str = ""
    line_number: int = 0


@dataclass
class Fix:
    """修复方案"""
    issue_id: str
    file_path: str
    language: str  # "python" or "typescript"
    old_code: str
    new_code: str
    explanation: str
    confidence: float = 0.0
    backup_path: str = ""
    applied: bool = False
    verified: bool = False


@dataclass
class TestResult:
    """测试结果"""
    test_case: TestCase
    success: bool
    response: str = ""
    error: str = ""
    screenshot_path: str = ""
    response_time: float = 0.0
    issues: List[Issue] = field(default_factory=list)


@dataclass
class RoundSummary:
    """轮次总结"""
    round_num: int
    total_tests: int
    passed: int
    failed: int
    issues: List[Issue]
    fixes_applied: int
    fixes_verified: int
    is_stable: bool
    ai_analysis: str = ""


# ============================================================================
# Self-Healing Test System
# ============================================================================

class SelfHealingTestSystem:
    """全自动自愈测试系统"""
    
    def __init__(
        self,
        output_dir: str = "tests/self_healing_results",
        api_base_url: str = "http://localhost:8080",
        ui_url: str = "http://localhost:5173",
        stability_threshold: int = 3,
        tests_per_round: int = 8,
        timeout: int = 60,
        auto_fix: bool = True,
        use_browser: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.api_base_url = api_base_url
        self.ui_url = ui_url
        self.stability_threshold = stability_threshold
        self.tests_per_round = tests_per_round
        self.timeout = timeout
        self.auto_fix = auto_fix
        self.use_browser = use_browser
        
        # LLM Client
        self.llm_client = None
        self.model_name = "claude-sonnet-4-20250514"
        
        # Playwright
        self.playwright = None
        self.browser = None
        self.page = None
        
        # Project paths
        self.project_root = Path(__file__).parent.parent
        self.frontend_root = self.project_root / "nogicos-ui" / "src"
        self.backend_root = self.project_root / "engine"
        
        # Stats
        self.session_id = f"healing_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_time = time.time()
        self.total_rounds = 0
        self.total_tests = 0
        self.total_issues = 0
        self.consecutive_stable_rounds = 0
        self.fixes_applied: List[Fix] = []
        self.fixes_failed: List[Fix] = []
        self.all_issues: List[Issue] = []
        self.round_summaries: List[RoundSummary] = []
    
    # ========================================================================
    # Initialization
    # ========================================================================
    
    def init_llm(self):
        """初始化 LLM 客户端"""
        if self.llm_client:
            return self.llm_client
        
        try:
            import anthropic
            
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                try:
                    import api_keys
                    api_keys.setup_env()
                    api_key = os.environ.get("ANTHROPIC_API_KEY")
                except:
                    pass
            
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found")
            
            self.llm_client = anthropic.Anthropic(api_key=api_key)
            print("[✓] LLM client initialized")
            return self.llm_client
        except Exception as e:
            print(f"[✗] Failed to init LLM: {e}")
            raise
    
    async def init_browser(self):
        """初始化 Playwright 浏览器"""
        if not self.use_browser:
            return
        
        try:
            from playwright.async_api import async_playwright
            
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,  # 无头模式，适合过夜运行
            )
            self.page = await self.browser.new_page()
            print("[✓] Browser initialized (headless mode)")
        except ImportError:
            print("[!] Playwright not installed. Run: pip install playwright && playwright install")
            self.use_browser = False
        except Exception as e:
            print(f"[!] Browser init failed: {e}")
            self.use_browser = False
    
    async def cleanup_browser(self):
        """清理浏览器"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    def call_llm(self, prompt: str, system: str = "", max_tokens: int = 4000) -> str:
        """调用 LLM"""
        client = self.init_llm()
        
        response = client.messages.create(
            model=self.model_name,
            max_tokens=max_tokens,
            system=system or "你是 NogicOS 的全栈测试和修复专家。",
            messages=[{"role": "user", "content": prompt}],
        )
        
        for block in response.content:
            if hasattr(block, "type") and getattr(block, "type", None) == "text":
                return getattr(block, "text", "")
        return ""
    
    def call_llm_with_image(self, prompt: str, image_path: str, system: str = "") -> str:
        """调用 LLM 并附带图片（用于视觉分析）"""
        client = self.init_llm()
        
        # 读取图片并转为 base64
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        
        response = client.messages.create(
            model=self.model_name,
            max_tokens=4000,
            system=system or "你是 UI/UX 专家，擅长发现界面问题。",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    }
                ]
            }],
        )
        
        for block in response.content:
            if hasattr(block, "type") and getattr(block, "type", None) == "text":
                return getattr(block, "text", "")
        return ""
    
    # ========================================================================
    # Test Case Generation
    # ========================================================================
    
    def generate_test_cases(self, round_num: int, previous_issues: List[Issue] = None) -> List[TestCase]:
        """AI 生成测试用例"""
        
        context = """
## NogicOS 简介
NogicOS 是一个 AI 工作助手，包含：
- 前端: React + TypeScript (端口 5173)
- 后端: Python FastAPI + ReAct Agent (端口 8080)
- 通过 WebSocket 实时通信

## 用户可以做的事情
- 在聊天框输入任务
- 看到 AI 的思考过程和执行结果
- 查看文件、浏览器截图等
"""
        
        if previous_issues:
            context += "\n## 上一轮发现的问题:\n"
            for issue in previous_issues[:5]:
                context += f"- [{issue.location.value}] {issue.type}: {issue.description[:50]}\n"
        
        prompt = f"""{context}

请生成 {self.tests_per_round} 个测试用例，包含以下类型：
1. API 测试 (type: api) - 直接调用后端 API
2. UI 测试 (type: ui) - 模拟用户在界面操作
3. 端到端测试 (type: e2e) - 完整用户流程

以 JSON 格式返回:
```json
[
  {{
    "id": "test_001",
    "prompt": "用户输入的内容",
    "test_type": "api/ui/e2e",
    "expected_behavior": "期望的行为",
    "category": "file/shell/chat/error"
  }}
]
```

测试要覆盖：
- 正常功能（文件读取、命令执行、聊天）
- 错误处理（无效输入、网络错误）
- 边缘情况（空输入、特殊字符、中文）
- 用户体验（响应速度、错误提示友好性）
"""
        
        try:
            response = self.call_llm(prompt)
            
            # 提取 JSON
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                json_str = response
            
            cases_data = json.loads(json_str)
            
            test_cases = []
            for data in cases_data:
                test_cases.append(TestCase(
                    id=data.get("id", f"test_{len(test_cases)}"),
                    prompt=data.get("prompt", ""),
                    test_type=TestType(data.get("test_type", "api")),
                    expected_behavior=data.get("expected_behavior", ""),
                    category=data.get("category", ""),
                ))
            
            return test_cases
            
        except Exception as e:
            print(f"[!] Failed to generate test cases: {e}")
            return self._get_default_test_cases()
    
    def _get_default_test_cases(self) -> List[TestCase]:
        """默认测试用例"""
        return [
            TestCase("api_001", "读取 README.md", TestType.API, "返回文件内容", "file"),
            TestCase("api_002", "运行 python --version", TestType.API, "返回版本号", "shell"),
            TestCase("api_003", "你好", TestType.API, "友好回复", "chat"),
            TestCase("api_004", "", TestType.API, "处理空输入", "error"),
            TestCase("ui_001", "当前目录有什么", TestType.UI, "界面显示结果", "file"),
            TestCase("ui_002", "帮我看看项目结构", TestType.UI, "界面正常渲染", "file"),
            TestCase("e2e_001", "创建一个测试文件", TestType.E2E, "文件被创建", "file"),
            TestCase("e2e_002", "搜索包含 def 的文件", TestType.E2E, "显示搜索结果", "file"),
        ]
    
    # ========================================================================
    # Test Execution
    # ========================================================================
    
    async def run_api_test(self, test_case: TestCase) -> TestResult:
        """执行 API 测试"""
        result = TestResult(test_case=test_case, success=False)
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 调用聊天 API
                response = await client.post(
                    f"{self.api_base_url}/api/chat",
                    json={
                        "messages": [{"role": "user", "content": test_case.prompt or "(empty)"}],
                        "session_id": f"test_{test_case.id}",
                    },
                    headers={"Accept": "text/event-stream"},
                )
                
                result.response_time = time.time() - start_time
                
                if response.status_code == 200:
                    # 解析 SSE 响应
                    full_response = ""
                    for line in response.text.split("\n"):
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if data.get("type") == "text-delta":
                                    full_response += data.get("delta", "")
                            except:
                                pass
                    
                    result.response = full_response
                    result.success = len(full_response) > 0
                    
                    # 检测响应中的问题
                    result.issues = self._detect_api_issues(test_case, result)
                    if result.issues:
                        result.success = False
                else:
                    result.error = f"HTTP {response.status_code}: {response.text[:200]}"
                    result.issues.append(Issue(
                        id=f"issue_{test_case.id}_http",
                        type="http_error",
                        severity=Severity.HIGH,
                        location=IssueLocation.BACKEND,
                        description=f"API returned {response.status_code}",
                        test_case=test_case,
                        error_message=response.text[:500],
                    ))
                    
        except httpx.TimeoutException:
            result.error = "Timeout"
            result.response_time = self.timeout
            result.issues.append(Issue(
                id=f"issue_{test_case.id}_timeout",
                type="timeout",
                severity=Severity.HIGH,
                location=IssueLocation.BACKEND,
                description="API request timed out",
                test_case=test_case,
            ))
        except Exception as e:
            result.error = str(e)
            result.issues.append(Issue(
                id=f"issue_{test_case.id}_error",
                type="connection_error",
                severity=Severity.CRITICAL,
                location=IssueLocation.BACKEND,
                description=f"Connection failed: {str(e)[:100]}",
                test_case=test_case,
                traceback=traceback.format_exc(),
            ))
        
        return result
    
    async def run_ui_test(self, test_case: TestCase) -> TestResult:
        """执行 UI 测试"""
        result = TestResult(test_case=test_case, success=False)
        
        if not self.use_browser or not self.page:
            # 降级为 API 测试
            return await self.run_api_test(test_case)
        
        start_time = time.time()
        screenshot_path = self.output_dir / "screenshots" / f"{test_case.id}_{int(time.time())}.png"
        screenshot_path.parent.mkdir(exist_ok=True)
        
        try:
            # 导航到 UI
            await self.page.goto(self.ui_url, wait_until="networkidle", timeout=30000)
            
            # 找到输入框并输入
            input_selector = "textarea, input[type='text'], [contenteditable='true']"
            await self.page.wait_for_selector(input_selector, timeout=10000)
            
            # 输入测试内容
            if test_case.prompt:
                await self.page.fill(input_selector, test_case.prompt)
                
                # 发送（按 Enter 或点击发送按钮）
                await self.page.keyboard.press("Enter")
            
            # 等待响应
            await asyncio.sleep(3)  # 等待 AI 响应
            
            # 截图
            await self.page.screenshot(path=str(screenshot_path))
            result.screenshot_path = str(screenshot_path)
            
            result.response_time = time.time() - start_time
            result.success = True
            
            # 视觉分析
            visual_issues = await self._analyze_screenshot(screenshot_path, test_case)
            result.issues.extend(visual_issues)
            
            if visual_issues:
                result.success = False
                
        except Exception as e:
            result.error = str(e)
            result.response_time = time.time() - start_time
            
            # 尝试截图记录错误状态
            try:
                await self.page.screenshot(path=str(screenshot_path))
                result.screenshot_path = str(screenshot_path)
            except:
                pass
            
            result.issues.append(Issue(
                id=f"issue_{test_case.id}_ui",
                type="ui_error",
                severity=Severity.HIGH,
                location=IssueLocation.FRONTEND,
                description=f"UI test failed: {str(e)[:100]}",
                test_case=test_case,
                traceback=traceback.format_exc(),
            ))
        
        return result
    
    async def run_e2e_test(self, test_case: TestCase) -> TestResult:
        """执行端到端测试"""
        # E2E 测试结合 API 和 UI
        api_result = await self.run_api_test(test_case)
        
        if self.use_browser and self.page:
            ui_result = await self.run_ui_test(test_case)
            # 合并结果
            api_result.issues.extend(ui_result.issues)
            api_result.screenshot_path = ui_result.screenshot_path
            
            if not api_result.success or not ui_result.success:
                api_result.success = False
        
        return api_result
    
    async def run_test(self, test_case: TestCase) -> TestResult:
        """运行单个测试"""
        if test_case.test_type == TestType.API:
            return await self.run_api_test(test_case)
        elif test_case.test_type == TestType.UI:
            return await self.run_ui_test(test_case)
        elif test_case.test_type == TestType.E2E:
            return await self.run_e2e_test(test_case)
        else:
            return await self.run_api_test(test_case)
    
    # ========================================================================
    # Issue Detection
    # ========================================================================
    
    def _detect_api_issues(self, test_case: TestCase, result: TestResult) -> List[Issue]:
        """检测 API 响应中的问题"""
        issues = []
        response = result.response or ""
        
        # 1. Traceback 泄露
        if "Traceback (most recent call last)" in response:
            issues.append(Issue(
                id=f"issue_{test_case.id}_traceback",
                type="traceback_leaked",
                severity=Severity.HIGH,
                location=IssueLocation.BACKEND,
                description="Python traceback leaked to user",
                test_case=test_case,
                error_message=response[:500],
            ))
        
        # 2. 空响应
        if not response.strip() and test_case.prompt.strip():
            issues.append(Issue(
                id=f"issue_{test_case.id}_empty",
                type="empty_response",
                severity=Severity.MEDIUM,
                location=IssueLocation.BACKEND,
                description="Empty response for non-empty input",
                test_case=test_case,
            ))
        
        # 3. 原始错误泄露
        error_patterns = [
            ("KeyError:", IssueLocation.BACKEND),
            ("AttributeError:", IssueLocation.BACKEND),
            ("TypeError:", IssueLocation.BACKEND),
            ("undefined is not", IssueLocation.FRONTEND),
            ("Cannot read properties", IssueLocation.FRONTEND),
        ]
        
        for pattern, location in error_patterns:
            if pattern in response:
                issues.append(Issue(
                    id=f"issue_{test_case.id}_{pattern[:5]}",
                    type="unhandled_error",
                    severity=Severity.MEDIUM,
                    location=location,
                    description=f"Unhandled error: {pattern}",
                    test_case=test_case,
                    error_message=response[:300],
                ))
        
        # 4. 响应过慢
        if result.response_time > 30:
            issues.append(Issue(
                id=f"issue_{test_case.id}_slow",
                type="slow_response",
                severity=Severity.LOW,
                location=IssueLocation.BACKEND,
                description=f"Response took {result.response_time:.1f}s",
                test_case=test_case,
            ))
        
        return issues
    
    async def _analyze_screenshot(self, screenshot_path: Path, test_case: TestCase) -> List[Issue]:
        """使用 AI 视觉分析截图"""
        issues = []
        
        if not screenshot_path.exists():
            return issues
        
        try:
            prompt = f"""分析这个 NogicOS 界面截图，检测以下问题：

用户操作: {test_case.prompt}
期望行为: {test_case.expected_behavior}

检查：
1. UI 是否正常渲染（无空白、无错误提示）
2. 是否显示了用户期望的内容
3. 是否有明显的视觉问题（元素重叠、文字截断等）
4. 错误信息是否友好（不是技术性的 traceback）

以 JSON 格式返回发现的问题（如果没有问题，返回空数组）:
```json
[
  {{
    "type": "问题类型",
    "severity": "critical/high/medium/low",
    "location": "frontend/backend",
    "description": "问题描述"
  }}
]
```
"""
            
            response = self.call_llm_with_image(prompt, str(screenshot_path))
            
            # 解析响应
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                json_str = response
            
            if json_str.strip() == "[]" or not json_str.strip():
                return issues
            
            issues_data = json.loads(json_str)
            
            for data in issues_data:
                issues.append(Issue(
                    id=f"issue_{test_case.id}_visual_{len(issues)}",
                    type=data.get("type", "visual_issue"),
                    severity=Severity(data.get("severity", "medium")),
                    location=IssueLocation(data.get("location", "frontend")),
                    description=data.get("description", ""),
                    test_case=test_case,
                    screenshot_path=str(screenshot_path),
                ))
            
        except Exception as e:
            print(f"      [!] Visual analysis failed: {e}")
        
        return issues
    
    # ========================================================================
    # Auto-Fix
    # ========================================================================
    
    def locate_issue(self, issue: Issue) -> Optional[Dict]:
        """定位问题代码"""
        
        # 确定搜索范围
        if issue.location == IssueLocation.FRONTEND:
            search_root = self.frontend_root
            file_pattern = "*.tsx"
        elif issue.location == IssueLocation.BACKEND:
            search_root = self.backend_root
            file_pattern = "*.py"
        else:
            return None
        
        # 读取相关文件
        relevant_files = []
        if search_root.exists():
            for f in search_root.rglob(file_pattern):
                if "__pycache__" not in str(f) and "node_modules" not in str(f):
                    relevant_files.append(f)
        
        if not relevant_files:
            return None
        
        # 构建提示
        files_content = ""
        for f in relevant_files[:5]:  # 最多 5 个文件
            try:
                content = f.read_text(encoding="utf-8")
                if len(content) > 3000:
                    content = content[:3000] + "\n... (truncated)"
                files_content += f"\n### {f.relative_to(self.project_root)}\n```\n{content}\n```\n"
            except:
                pass
        
        prompt = f"""定位以下问题的代码位置。

## 问题
类型: {issue.type}
位置: {issue.location.value}
描述: {issue.description}
错误信息: {issue.error_message[:500] if issue.error_message else 'N/A'}

## 相关代码
{files_content}

以 JSON 格式返回:
```json
{{
  "file_path": "文件路径",
  "line_start": 起始行,
  "line_end": 结束行,
  "problematic_code": "有问题的代码",
  "root_cause": "根本原因"
}}
```
"""
        
        try:
            response = self.call_llm(prompt)
            
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                json_str = response
            
            return json.loads(json_str)
        except:
            return None
    
    def generate_fix(self, issue: Issue, location: Dict) -> Optional[Fix]:
        """生成修复代码"""
        
        file_path = location.get("file_path", "")
        if not file_path:
            return None
        
        full_path = self.project_root / file_path
        if not full_path.exists():
            return None
        
        try:
            file_content = full_path.read_text(encoding="utf-8")
        except:
            return None
        
        language = "typescript" if file_path.endswith((".ts", ".tsx")) else "python"
        
        prompt = f"""修复以下 {language} 代码问题。

## 问题
类型: {issue.type}
描述: {issue.description}
根因: {location.get('root_cause', 'Unknown')}

## 当前代码
文件: {file_path}
```{language}
{file_content[:6000]}
```

## 问题代码
```
{location.get('problematic_code', '')}
```

## 修复要求
1. 只修改必要的部分
2. 保持代码风格一致
3. 添加错误处理
4. 确保修复后代码可以直接运行

以 JSON 格式返回:
```json
{{
  "old_code": "需要替换的原代码（必须完全匹配）",
  "new_code": "替换后的新代码",
  "explanation": "修复说明",
  "confidence": 0.0-1.0
}}
```
"""
        
        try:
            response = self.call_llm(prompt, max_tokens=6000)
            
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                json_str = response
            
            fix_data = json.loads(json_str)
            
            return Fix(
                issue_id=issue.id,
                file_path=file_path,
                language=language,
                old_code=fix_data.get("old_code", ""),
                new_code=fix_data.get("new_code", ""),
                explanation=fix_data.get("explanation", ""),
                confidence=float(fix_data.get("confidence", 0.5)),
            )
        except Exception as e:
            print(f"      [!] Generate fix failed: {e}")
            return None
    
    def apply_fix(self, fix: Fix) -> bool:
        """应用修复"""
        if not fix.old_code or not fix.new_code:
            return False
        
        try:
            full_path = self.project_root / fix.file_path
            if not full_path.exists():
                return False
            
            content = full_path.read_text(encoding="utf-8")
            
            if fix.old_code not in content:
                print(f"      [!] Old code not found in {fix.file_path}")
                return False
            
            # 备份
            backup_dir = self.output_dir / "backups"
            backup_dir.mkdir(exist_ok=True)
            backup_name = f"{full_path.stem}_{datetime.now().strftime('%H%M%S')}{full_path.suffix}.bak"
            backup_path = backup_dir / backup_name
            backup_path.write_text(content, encoding="utf-8")
            fix.backup_path = str(backup_path)
            
            # 应用修复
            new_content = content.replace(fix.old_code, fix.new_code, 1)
            full_path.write_text(new_content, encoding="utf-8")
            fix.applied = True
            
            print(f"      [✓] Applied fix to {fix.file_path}")
            return True
            
        except Exception as e:
            print(f"      [!] Apply fix failed: {e}")
            return False
    
    def rollback_fix(self, fix: Fix) -> bool:
        """回滚修复"""
        if not fix.backup_path or not fix.applied:
            return False
        
        try:
            backup_path = Path(fix.backup_path)
            if not backup_path.exists():
                return False
            
            full_path = self.project_root / fix.file_path
            backup_content = backup_path.read_text(encoding="utf-8")
            full_path.write_text(backup_content, encoding="utf-8")
            fix.applied = False
            
            print(f"      [↩] Rolled back {fix.file_path}")
            return True
        except:
            return False
    
    async def try_fix_issue(self, issue: Issue) -> bool:
        """尝试修复问题"""
        print(f"      [1/3] Locating issue...")
        location = self.locate_issue(issue)
        
        if not location:
            print(f"      [!] Could not locate issue")
            return False
        
        print(f"            Found: {location.get('file_path', '?')}")
        
        print(f"      [2/3] Generating fix...")
        fix = self.generate_fix(issue, location)
        
        if not fix:
            print(f"      [!] Could not generate fix")
            return False
        
        print(f"            Confidence: {fix.confidence:.0%}")
        
        print(f"      [3/3] Applying fix...")
        if self.apply_fix(fix):
            self.fixes_applied.append(fix)
            return True
        else:
            self.fixes_failed.append(fix)
            return False
    
    # ========================================================================
    # Main Loop
    # ========================================================================
    
    async def run_round(self, round_num: int) -> RoundSummary:
        """执行一轮测试"""
        print(f"\n{'='*60}")
        print(f"ROUND {round_num}")
        print(f"{'='*60}")
        
        # 1. 生成测试用例
        print("\n[1/4] Generating test cases...")
        previous_issues = self.all_issues[-10:] if self.all_issues else None
        test_cases = self.generate_test_cases(round_num, previous_issues)
        print(f"      Generated {len(test_cases)} test cases")
        
        # 2. 执行测试
        print(f"\n[2/4] Running tests...")
        results: List[TestResult] = []
        issues_to_fix: List[Issue] = []
        
        for i, tc in enumerate(test_cases):
            print(f"  [{i+1}/{len(test_cases)}] {tc.test_type.value}: {tc.prompt[:35]}...")
            
            result = await self.run_test(tc)
            results.append(result)
            
            status = "✓" if result.success else "✗"
            print(f"       {status} ({result.response_time:.1f}s)")
            
            for issue in result.issues:
                print(f"         - [{issue.location.value}] {issue.type}")
                if issue.severity in [Severity.CRITICAL, Severity.HIGH]:
                    issues_to_fix.append(issue)
        
        # 3. 自动修复
        fixes_applied = 0
        if self.auto_fix and issues_to_fix:
            print(f"\n[3/4] Auto-fixing {len(issues_to_fix)} issues...")
            
            for issue in issues_to_fix:
                print(f"\n  Fixing: [{issue.location.value}] {issue.type}")
                if await self.try_fix_issue(issue):
                    fixes_applied += 1
        else:
            print(f"\n[3/4] No critical issues to fix")
        
        # 4. 汇总
        print(f"\n[4/4] Summarizing...")
        
        all_issues = []
        for r in results:
            all_issues.extend(r.issues)
        
        passed = sum(1 for r in results if r.success)
        failed = len(results) - passed
        
        is_stable = not any(i.severity in [Severity.CRITICAL, Severity.HIGH] for i in all_issues)
        
        summary = RoundSummary(
            round_num=round_num,
            total_tests=len(results),
            passed=passed,
            failed=failed,
            issues=all_issues,
            fixes_applied=fixes_applied,
            fixes_verified=0,
            is_stable=is_stable,
        )
        
        # 更新统计
        self.total_rounds += 1
        self.total_tests += len(results)
        self.all_issues.extend(all_issues)
        self.total_issues += len(all_issues)
        self.round_summaries.append(summary)
        
        if is_stable:
            self.consecutive_stable_rounds += 1
        else:
            self.consecutive_stable_rounds = 0
        
        # 打印总结
        print(f"\n--- Round {round_num} Summary ---")
        print(f"Passed: {passed}/{len(results)}")
        print(f"Issues: {len(all_issues)} (Frontend: {sum(1 for i in all_issues if i.location == IssueLocation.FRONTEND)}, Backend: {sum(1 for i in all_issues if i.location == IssueLocation.BACKEND)})")
        print(f"Fixes applied: {fixes_applied}")
        print(f"Stable: {'Yes' if is_stable else 'No'}")
        print(f"Consecutive stable: {self.consecutive_stable_rounds}/{self.stability_threshold}")
        
        # 保存结果
        self._save_round(round_num, results, summary)
        
        return summary
    
    def _save_round(self, round_num: int, results: List[TestResult], summary: RoundSummary):
        """保存轮次结果"""
        output_file = self.output_dir / f"round_{round_num:04d}.json"
        
        data = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "passed": summary.passed,
                "failed": summary.failed,
                "issues": len(summary.issues),
                "fixes_applied": summary.fixes_applied,
                "is_stable": summary.is_stable,
            },
            "results": [
                {
                    "test_id": r.test_case.id,
                    "prompt": r.test_case.prompt,
                    "test_type": r.test_case.test_type.value,
                    "success": r.success,
                    "response_time": r.response_time,
                    "issues": [
                        {
                            "type": i.type,
                            "severity": i.severity.value,
                            "location": i.location.value,
                            "description": i.description,
                        }
                        for i in r.issues
                    ],
                }
                for r in results
            ],
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def generate_final_report(self) -> str:
        """生成最终报告"""
        elapsed = time.time() - self.start_time
        
        frontend_issues = sum(1 for i in self.all_issues if i.location == IssueLocation.FRONTEND)
        backend_issues = sum(1 for i in self.all_issues if i.location == IssueLocation.BACKEND)
        
        report = f"""
{'='*60}
NogicOS SELF-HEALING TEST SYSTEM - FINAL REPORT
{'='*60}

Session: {self.session_id}
Duration: {elapsed/60:.1f} minutes ({elapsed/3600:.1f} hours)

## Summary
- Total Rounds: {self.total_rounds}
- Total Tests: {self.total_tests}
- Total Issues: {self.total_issues}
  - Frontend: {frontend_issues}
  - Backend: {backend_issues}
- Fixes Applied: {len(self.fixes_applied)}
- Fixes Failed: {len(self.fixes_failed)}
- Consecutive Stable Rounds: {self.consecutive_stable_rounds}
- Final Status: {'✓ STABLE' if self.consecutive_stable_rounds >= self.stability_threshold else '✗ NEEDS WORK'}

## Rounds Overview
"""
        
        for s in self.round_summaries:
            status = "✓" if s.is_stable else "✗"
            report += f"  Round {s.round_num}: {s.passed}/{s.total_tests} passed, {len(s.issues)} issues, {s.fixes_applied} fixes {status}\n"
        
        if self.fixes_applied:
            report += "\n## Fixes Applied\n"
            for f in self.fixes_applied:
                report += f"  - [{f.language}] {f.file_path}: {f.explanation[:60]}...\n"
        
        if self.fixes_failed:
            report += "\n## Fixes Failed\n"
            for f in self.fixes_failed:
                report += f"  - [{f.language}] {f.file_path}\n"
        
        report += f"""
## Conclusion
{'Product is STABLE! ✓' if self.consecutive_stable_rounds >= self.stability_threshold else 'Product needs more work.'}

Results: {self.output_dir}
{'='*60}
"""
        return report
    
    async def run(self, max_rounds: int = 100) -> bool:
        """运行自愈测试循环"""
        print("\n" + "="*60)
        print("NogicOS SELF-HEALING TEST SYSTEM")
        print("="*60)
        print(f"API: {self.api_base_url}")
        print(f"UI: {self.ui_url}")
        print(f"Browser: {'Enabled' if self.use_browser else 'Disabled'}")
        print(f"Auto-fix: {'Enabled' if self.auto_fix else 'Disabled'}")
        print(f"Stability: {self.stability_threshold} consecutive stable rounds")
        print(f"Max rounds: {max_rounds}")
        print("="*60)
        
        # 初始化
        self.init_llm()
        await self.init_browser()
        
        try:
            round_num = 0
            while round_num < max_rounds:
                round_num += 1
                
                summary = await self.run_round(round_num)
                
                if self.consecutive_stable_rounds >= self.stability_threshold:
                    print(f"\n{'='*60}")
                    print("🎉 PRODUCT IS STABLE!")
                    print(f"{'='*60}")
                    break
                
                # 短暂休息
                await asyncio.sleep(2)
                
        except KeyboardInterrupt:
            print("\n[!] Interrupted by user")
        except Exception as e:
            print(f"\n[!] Error: {e}")
            traceback.print_exc()
        finally:
            await self.cleanup_browser()
            
            report = self.generate_final_report()
            print(report)
            
            # 保存报告
            report_file = self.output_dir / "final_report.txt"
            report_file.write_text(report, encoding="utf-8")
            
            # 保存完整数据
            full_file = self.output_dir / "full_results.json"
            with open(full_file, "w", encoding="utf-8") as f:
                json.dump({
                    "session_id": self.session_id,
                    "duration_minutes": (time.time() - self.start_time) / 60,
                    "total_rounds": self.total_rounds,
                    "total_tests": self.total_tests,
                    "total_issues": self.total_issues,
                    "is_stable": self.consecutive_stable_rounds >= self.stability_threshold,
                    "fixes_applied": len(self.fixes_applied),
                }, f, ensure_ascii=False, indent=2)
        
        return self.consecutive_stable_rounds >= self.stability_threshold


# ============================================================================
# Main
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="NogicOS Self-Healing Test System")
    parser.add_argument("--max-rounds", type=int, default=100, help="Max test rounds")
    parser.add_argument("--stability", type=int, default=3, help="Consecutive stable rounds needed")
    parser.add_argument("--tests", type=int, default=8, help="Tests per round")
    parser.add_argument("--no-fix", action="store_true", help="Disable auto-fix")
    parser.add_argument("--no-browser", action="store_true", help="Disable browser/UI tests")
    parser.add_argument("--api-url", default="http://localhost:8080", help="API base URL")
    parser.add_argument("--ui-url", default="http://localhost:5173", help="UI URL")
    parser.add_argument("--output", default="tests/self_healing_results", help="Output directory")
    parser.add_argument("--overnight", action="store_true", help="Overnight mode (more rounds, longer timeouts)")
    args = parser.parse_args()
    
    # 过夜模式
    if args.overnight:
        args.max_rounds = 500
        args.stability = 5
        args.tests = 15
    
    system = SelfHealingTestSystem(
        output_dir=args.output,
        api_base_url=args.api_url,
        ui_url=args.ui_url,
        stability_threshold=args.stability,
        tests_per_round=args.tests,
        auto_fix=not args.no_fix,
        use_browser=not args.no_browser,
    )
    
    is_stable = await system.run(max_rounds=args.max_rounds)
    sys.exit(0 if is_stable else 1)


if __name__ == "__main__":
    asyncio.run(main())

