# -*- coding: utf-8 -*-
"""
NogicOS Infinite AI Tester with Auto-Fix
无限循环测试 + 自动修复，直到 AI 认为产品稳定

核心流程:
1. AI 生成测试用例
2. 执行测试
3. AI 分析结果
4. 如果有问题:
   a. AI 定位问题代码
   b. AI 生成修复方案
   c. 安全应用修复（带备份）
   d. 验证修复是否有效
5. 连续 N 轮无问题 = 产品稳定

Usage:
    python -m tests.infinite_ai_tester
    python -m tests.infinite_ai_tester --max-rounds 100
    python -m tests.infinite_ai_tester --stability-threshold 5
    python -m tests.infinite_ai_tester --no-fix  # 只测试不修复
"""

import sys
import os
import asyncio
import argparse
import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    TIMEOUT = "timeout"
    CRASH = "crash"


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Issue:
    """发现的问题"""
    type: str
    severity: Severity
    description: str
    test_prompt: str = ""
    traceback: str = ""
    suggestion: str = ""
    file_path: str = ""  # 问题所在文件
    line_number: int = 0  # 问题所在行号


@dataclass
class CodeFix:
    """代码修复方案"""
    issue_type: str
    file_path: str
    old_code: str
    new_code: str
    explanation: str
    confidence: float = 0.0  # AI 的置信度 0-1
    backup_path: str = ""
    applied: bool = False
    verified: bool = False


@dataclass
class TestResult:
    """单次测试结果"""
    id: int
    round: int
    timestamp: str
    prompt: str
    category: str
    status: TestStatus
    response: str = ""
    error: str = ""
    issues: List[Issue] = field(default_factory=list)
    execution_time: float = 0.0


@dataclass
class RoundSummary:
    """单轮测试总结"""
    round: int
    total_tests: int
    passed: int
    failed: int
    issues_found: List[Issue]
    is_stable: bool
    ai_analysis: str = ""


class InfiniteAITester:
    """AI 驱动的无限测试循环（带自动修复）"""
    
    def __init__(
        self,
        output_dir: str = "tests/infinite_test_results",
        stability_threshold: int = 3,  # 连续 N 轮无问题 = 稳定
        tests_per_round: int = 10,
        timeout_per_test: int = 60,
        auto_fix: bool = True,  # 是否自动修复
        max_fix_attempts: int = 3,  # 每个问题最大修复尝试次数
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.stability_threshold = stability_threshold
        self.tests_per_round = tests_per_round
        self.timeout_per_test = timeout_per_test
        self.auto_fix = auto_fix
        self.max_fix_attempts = max_fix_attempts
        
        self.agent = None
        self.llm_client = None
        self.model_name = "claude-sonnet-4-20250514"
        
        # Stats
        self.total_rounds = 0
        self.total_tests = 0
        self.total_issues = 0
        self.consecutive_stable_rounds = 0
        self.all_issues: List[Issue] = []
        self.round_summaries: List[RoundSummary] = []
        
        # 修复追踪
        self.fixes_applied: List[CodeFix] = []
        self.fixes_failed: List[CodeFix] = []
        self.fix_attempts: Dict[str, int] = {}  # issue_type -> 尝试次数
        
        # 项目根目录（用于定位代码文件）
        self.project_root = Path(__file__).parent.parent
        
        # Session tracking
        self.session_id = f"infinite_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_time = time.time()
        
    def init_llm(self):
        """初始化 LLM 客户端"""
        if self.llm_client is not None:
            return self.llm_client
            
        try:
            import anthropic
            
            # Load API key
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
            print(f"[✓] LLM client initialized ({self.model_name})")
            return self.llm_client
            
        except Exception as e:
            print(f"[✗] Failed to init LLM: {e}")
            raise
    
    async def init_agent(self):
        """初始化测试 Agent"""
        if self.agent is not None:
            return self.agent
            
        try:
            from engine.agent.react_agent import ReActAgent
            self.agent = ReActAgent()
            print("[✓] Test agent initialized")
            return self.agent
        except Exception as e:
            print(f"[✗] Failed to init agent: {e}")
            raise
    
    def call_llm(self, prompt: str, system: str = "", max_tokens: int = 4000) -> str:
        """调用 LLM"""
        client = self.init_llm()
        
        response = client.messages.create(
            model=self.model_name,
            max_tokens=max_tokens,
            system=system if system else "你是 NogicOS 的 QA 测试专家。",
            messages=[{"role": "user", "content": prompt}],
        )
        
        # 提取文本响应
        for block in response.content:
            # 检查是否是 TextBlock 类型
            if hasattr(block, "type") and getattr(block, "type", None) == "text":
                return getattr(block, "text", "")
        return ""
    
    def read_file_content(self, file_path: str) -> Optional[str]:
        """安全读取文件内容"""
        try:
            full_path = self.project_root / file_path
            if not full_path.exists():
                # 尝试直接路径
                full_path = Path(file_path)
            if full_path.exists():
                return full_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"      [!] Cannot read {file_path}: {e}")
        return None
    
    def locate_issue_in_code(self, issue: Issue, test_result: TestResult) -> Optional[Dict]:
        """使用 AI 定位问题代码位置"""
        
        # 从 traceback 提取文件信息
        traceback_text = issue.traceback or test_result.error or ""
        
        # 构建代码上下文
        relevant_files = []
        if "engine/" in traceback_text:
            # 提取涉及的文件
            import re
            file_matches = re.findall(r'File "([^"]+)"', traceback_text)
            for f in file_matches:
                if "engine" in f or "nogicos" in f:
                    relevant_files.append(f)
        
        # 默认可能的问题文件
        if not relevant_files:
            relevant_files = [
                "engine/agent/react_agent.py",
                "engine/tools/browser.py",
                "engine/tools/local.py",
            ]
        
        # 读取相关文件内容
        file_contents = {}
        for f in relevant_files[:3]:  # 最多 3 个文件
            content = self.read_file_content(f)
            if content:
                # 限制长度
                if len(content) > 5000:
                    content = content[:5000] + "\n... (truncated)"
                file_contents[f] = content
        
        if not file_contents:
            return None
        
        prompt = f"""分析以下错误并精确定位问题代码位置。

## 错误信息
类型: {issue.type}
描述: {issue.description}
触发输入: {issue.test_prompt}

## Traceback
```
{traceback_text[:2000]}
```

## 相关代码文件
"""
        for filepath, content in file_contents.items():
            prompt += f"\n### {filepath}\n```python\n{content}\n```\n"
        
        prompt += """
## 请定位问题
以 JSON 格式返回:
```json
{
  "file_path": "具体文件路径",
  "line_start": 起始行号,
  "line_end": 结束行号,
  "problematic_code": "有问题的代码片段",
  "root_cause": "问题根本原因",
  "confidence": 0.0-1.0 的置信度
}
```
"""
        
        try:
            response = self.call_llm(prompt, system="你是代码调试专家，擅长从错误日志定位问题。")
            
            # 提取 JSON
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                json_str = response
            
            return json.loads(json_str)
            
        except Exception as e:
            print(f"      [!] Failed to locate issue: {e}")
            return None
    
    def generate_fix(self, issue: Issue, location: Dict) -> Optional[CodeFix]:
        """使用 AI 生成修复代码"""
        
        file_path = location.get("file_path", "")
        if not file_path:
            return None
        
        # 读取完整文件内容
        file_content = self.read_file_content(file_path)
        if not file_content:
            return None
        
        prompt = f"""根据以下问题分析，生成修复代码。

## 问题
类型: {issue.type}
描述: {issue.description}
根因: {location.get('root_cause', 'Unknown')}

## 问题代码位置
文件: {file_path}
行号: {location.get('line_start', '?')} - {location.get('line_end', '?')}
问题代码:
```python
{location.get('problematic_code', '')}
```

## 完整文件内容
```python
{file_content[:8000]}
```

## 修复要求
1. 只修改必要的部分
2. 保持代码风格一致
3. 添加必要的错误处理
4. 不要破坏现有功能

## 返回格式
以 JSON 格式返回修复方案:
```json
{{
  "old_code": "需要被替换的原代码（完整匹配）",
  "new_code": "替换后的新代码",
  "explanation": "修复说明",
  "confidence": 0.0-1.0
}}
```

注意: old_code 必须完全匹配文件中的代码，包括缩进和空格。
"""
        
        try:
            response = self.call_llm(
                prompt, 
                system="你是 Python 专家，擅长修复代码 bug。生成的代码必须可以直接应用。",
                max_tokens=6000
            )
            
            # 提取 JSON
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                json_str = response
            
            fix_data = json.loads(json_str)
            
            return CodeFix(
                issue_type=issue.type,
                file_path=file_path,
                old_code=fix_data.get("old_code", ""),
                new_code=fix_data.get("new_code", ""),
                explanation=fix_data.get("explanation", ""),
                confidence=float(fix_data.get("confidence", 0.5)),
            )
            
        except Exception as e:
            print(f"      [!] Failed to generate fix: {e}")
            return None
    
    def apply_fix_safely(self, fix: CodeFix) -> bool:
        """安全应用修复（带备份）"""
        
        if not fix.old_code or not fix.new_code:
            print("      [!] Empty fix code")
            return False
        
        try:
            file_path = self.project_root / fix.file_path
            if not file_path.exists():
                file_path = Path(fix.file_path)
            
            if not file_path.exists():
                print(f"      [!] File not found: {fix.file_path}")
                return False
            
            # 读取原文件
            original_content = file_path.read_text(encoding="utf-8")
            
            # 检查 old_code 是否存在
            if fix.old_code not in original_content:
                print(f"      [!] Old code not found in file")
                # 尝试模糊匹配（去除空白差异）
                normalized_old = " ".join(fix.old_code.split())
                normalized_content = " ".join(original_content.split())
                if normalized_old not in normalized_content:
                    return False
                print(f"      [*] Trying fuzzy match...")
            
            # 创建备份
            backup_dir = self.output_dir / "backups"
            backup_dir.mkdir(exist_ok=True)
            backup_name = f"{file_path.stem}_{datetime.now().strftime('%H%M%S')}{file_path.suffix}.bak"
            backup_path = backup_dir / backup_name
            backup_path.write_text(original_content, encoding="utf-8")
            fix.backup_path = str(backup_path)
            
            # 应用修复
            new_content = original_content.replace(fix.old_code, fix.new_code, 1)
            
            if new_content == original_content:
                print(f"      [!] No changes made")
                return False
            
            # 写入修复
            file_path.write_text(new_content, encoding="utf-8")
            fix.applied = True
            
            print(f"      [✓] Fix applied to {fix.file_path}")
            print(f"          Backup: {backup_path}")
            
            return True
            
        except Exception as e:
            print(f"      [!] Failed to apply fix: {e}")
            return False
    
    def rollback_fix(self, fix: CodeFix) -> bool:
        """回滚修复"""
        if not fix.backup_path or not fix.applied:
            return False
        
        try:
            backup_path = Path(fix.backup_path)
            if not backup_path.exists():
                print(f"      [!] Backup not found: {fix.backup_path}")
                return False
            
            file_path = self.project_root / fix.file_path
            if not file_path.exists():
                file_path = Path(fix.file_path)
            
            # 恢复备份
            backup_content = backup_path.read_text(encoding="utf-8")
            file_path.write_text(backup_content, encoding="utf-8")
            
            fix.applied = False
            print(f"      [↩] Rolled back {fix.file_path}")
            return True
            
        except Exception as e:
            print(f"      [!] Rollback failed: {e}")
            return False
    
    async def verify_fix(self, fix: CodeFix, original_test: Dict) -> bool:
        """验证修复是否有效"""
        print(f"      [*] Verifying fix...")
        
        # 重新运行原来失败的测试
        result = await self.run_single_test(
            original_test, 
            test_id=9999,  # 验证测试 ID
            round_num=0,
        )
        
        # 检查是否还有相同类型的问题
        same_issues = [i for i in result.issues if i.type == fix.issue_type]
        
        if not same_issues and result.status == TestStatus.PASS:
            fix.verified = True
            print(f"      [✓] Fix verified - test now passes!")
            return True
        else:
            print(f"      [✗] Fix did not resolve the issue")
            return False
    
    async def try_fix_issue(self, issue: Issue, test_result: TestResult, test_case: Dict) -> bool:
        """尝试修复单个问题"""
        
        # 检查尝试次数
        issue_key = f"{issue.type}:{issue.description[:50]}"
        attempts = self.fix_attempts.get(issue_key, 0)
        
        if attempts >= self.max_fix_attempts:
            print(f"      [!] Max fix attempts ({self.max_fix_attempts}) reached for this issue")
            return False
        
        self.fix_attempts[issue_key] = attempts + 1
        
        print(f"      [1/4] Locating issue in code...")
        location = self.locate_issue_in_code(issue, test_result)
        
        if not location:
            print(f"      [!] Could not locate issue")
            return False
        
        print(f"            Found: {location.get('file_path', '?')} line {location.get('line_start', '?')}")
        
        print(f"      [2/4] Generating fix...")
        fix = self.generate_fix(issue, location)
        
        if not fix:
            print(f"      [!] Could not generate fix")
            return False
        
        print(f"            Confidence: {fix.confidence:.0%}")
        
        # 低置信度警告
        if fix.confidence < 0.5:
            print(f"      [!] Low confidence fix - proceeding with caution")
        
        print(f"      [3/4] Applying fix...")
        if not self.apply_fix_safely(fix):
            self.fixes_failed.append(fix)
            return False
        
        print(f"      [4/4] Verifying fix...")
        # 重新初始化 agent 以加载修复后的代码
        self.agent = None
        
        if await self.verify_fix(fix, test_case):
            self.fixes_applied.append(fix)
            return True
        else:
            # 回滚
            print(f"      [!] Fix failed verification - rolling back")
            self.rollback_fix(fix)
            self.fixes_failed.append(fix)
            # 重新初始化 agent
            self.agent = None
            return False
    
    def generate_test_cases(self, round_num: int, previous_issues: Optional[List[Issue]] = None) -> List[Dict]:
        """使用 AI 生成测试用例"""
        
        # 构建 prompt
        context = f"""
## NogicOS 简介
NogicOS 是一个 AI 工作助手，核心能力：
- 浏览网页、提取数据
- 文件操作（读、写、搜索、整理）
- 执行 Shell 命令
- 智能任务规划

## 可用工具
- navigate: 导航到 URL
- click: 点击元素
- type: 输入文本
- screenshot: 截图
- read_file: 读取文件
- write_file: 写入文件
- list_directory: 列出目录
- shell_execute: 执行命令
- grep_search: 搜索文件内容
- glob_search: 按模式搜索文件

## 当前测试轮次: {round_num}
"""
        
        if previous_issues:
            context += "\n## 上一轮发现的问题:\n"
            for issue in previous_issues[:5]:
                context += f"- [{issue.severity.value}] {issue.type}: {issue.description}\n"
            context += "\n请生成能够验证这些问题是否已修复的测试用例。\n"
        
        prompt = f"""{context}

请生成 {self.tests_per_round} 个测试用例，覆盖以下类别：
1. 文件操作 (file) - 读写、搜索、整理
2. Shell 命令 (shell) - 执行命令、查看结果
3. 中文处理 (chinese) - 自然语言理解
4. 错误处理 (error) - 边缘情况、异常输入
5. 复杂任务 (complex) - 多步骤任务

以 JSON 格式返回，每个测试包含:
- prompt: 用户输入
- category: 测试类别
- expected_behavior: 期望行为
- risk_level: 风险等级 (low/medium/high)

返回格式:
```json
[
  {{"prompt": "...", "category": "file", "expected_behavior": "...", "risk_level": "low"}},
  ...
]
```
"""
        
        try:
            response = self.call_llm(prompt)
            
            # 提取 JSON
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            elif "[" in response:
                start = response.find("[")
                end = response.rfind("]") + 1
                json_str = response[start:end]
            else:
                json_str = response
            
            test_cases = json.loads(json_str)
            return test_cases
            
        except Exception as e:
            print(f"[!] Failed to generate test cases: {e}")
            # 返回默认测试用例
            return self._get_default_test_cases()
    
    def _get_default_test_cases(self) -> List[Dict]:
        """默认测试用例（AI 生成失败时的后备）"""
        return [
            {"prompt": "读取 requirements.txt", "category": "file", "expected_behavior": "读取文件内容", "risk_level": "low"},
            {"prompt": "当前目录有什么文件", "category": "file", "expected_behavior": "列出目录", "risk_level": "low"},
            {"prompt": "运行 python --version", "category": "shell", "expected_behavior": "显示 Python 版本", "risk_level": "low"},
            {"prompt": "搜索包含 import 的 python 文件", "category": "file", "expected_behavior": "搜索文件", "risk_level": "low"},
            {"prompt": "帮我看看项目结构", "category": "chinese", "expected_behavior": "分析项目", "risk_level": "medium"},
            {"prompt": "读取一个不存在的文件", "category": "error", "expected_behavior": "优雅处理错误", "risk_level": "low"},
            {"prompt": "", "category": "error", "expected_behavior": "处理空输入", "risk_level": "low"},
            {"prompt": "你好", "category": "chinese", "expected_behavior": "自然回复", "risk_level": "low"},
            {"prompt": "分析 README.md 的内容", "category": "complex", "expected_behavior": "总结文件", "risk_level": "medium"},
            {"prompt": "git status", "category": "shell", "expected_behavior": "显示 git 状态", "risk_level": "low"},
        ]
    
    async def run_single_test(self, test_case: Dict, test_id: int, round_num: int) -> TestResult:
        """执行单个测试"""
        agent = await self.init_agent()
        
        result = TestResult(
            id=test_id,
            round=round_num,
            timestamp=datetime.now().isoformat(),
            prompt=test_case.get("prompt", ""),
            category=test_case.get("category", "unknown"),
            status=TestStatus.PASS,
        )
        
        start_time = time.time()
        
        try:
            # 处理空输入
            task = test_case.get("prompt", "").strip()
            if not task:
                task = "(empty input)"
            
            # 执行测试
            agent_result = await asyncio.wait_for(
                agent.run(
                    task=task,
                    session_id=f"{self.session_id}_test_{test_id}",
                ),
                timeout=self.timeout_per_test,
            )
            
            result.response = agent_result.response[:2000] if agent_result.response else ""
            result.execution_time = time.time() - start_time
            
            # 分析响应中的问题
            issues = self._detect_issues(test_case, agent_result)
            result.issues = issues
            
            if issues:
                # 判断最严重的问题等级
                severities = [i.severity for i in issues]
                if Severity.CRITICAL in severities:
                    result.status = TestStatus.CRASH
                elif Severity.HIGH in severities:
                    result.status = TestStatus.FAIL
                else:
                    result.status = TestStatus.FAIL
            else:
                result.status = TestStatus.PASS
                
        except asyncio.TimeoutError:
            result.status = TestStatus.TIMEOUT
            result.error = f"Timeout after {self.timeout_per_test}s"
            result.execution_time = self.timeout_per_test
            result.issues.append(Issue(
                type="timeout",
                severity=Severity.HIGH,
                description=f"Test timed out after {self.timeout_per_test} seconds",
                test_prompt=test_case.get("prompt", ""),
            ))
            
        except Exception as e:
            result.status = TestStatus.CRASH
            result.error = str(e)
            result.execution_time = time.time() - start_time
            tb = traceback.format_exc()
            result.issues.append(Issue(
                type="crash",
                severity=Severity.CRITICAL,
                description=f"Agent crashed: {str(e)[:200]}",
                test_prompt=test_case.get("prompt", ""),
                traceback=tb[:1000],
            ))
        
        return result
    
    def _detect_issues(self, test_case: Dict, agent_result) -> List[Issue]:
        """检测响应中的问题"""
        issues = []
        response = agent_result.response or ""
        prompt = test_case.get("prompt", "")
        
        # 1. Python traceback 泄露
        if "Traceback (most recent call last)" in response:
            issues.append(Issue(
                type="traceback_leaked",
                severity=Severity.HIGH,
                description="Python traceback leaked to user response",
                test_prompt=prompt,
            ))
        
        # 2. 空响应（非空输入时）
        if not response.strip() and prompt.strip():
            issues.append(Issue(
                type="empty_response",
                severity=Severity.MEDIUM,
                description="Empty response for non-empty input",
                test_prompt=prompt,
            ))
        
        # 3. 编码问题
        encoding_markers = ["\\x", "锟斤拷", "烫烫烫", "\\u0000"]
        for marker in encoding_markers:
            if marker in response:
                issues.append(Issue(
                    type="encoding_error",
                    severity=Severity.MEDIUM,
                    description=f"Encoding issue detected: {marker}",
                    test_prompt=prompt,
                ))
                break
        
        # 4. 未处理的异常
        error_patterns = [
            ("KeyError:", Severity.MEDIUM),
            ("AttributeError:", Severity.MEDIUM),
            ("TypeError:", Severity.MEDIUM),
            ("IndexError:", Severity.MEDIUM),
            ("FileNotFoundError:", Severity.LOW),
            ("ConnectionError:", Severity.MEDIUM),
            ("JSONDecodeError:", Severity.MEDIUM),
        ]
        
        for pattern, severity in error_patterns:
            if pattern in response and "sorry" not in response.lower() and "抱歉" not in response:
                issues.append(Issue(
                    type="unhandled_exception",
                    severity=severity,
                    description=f"Unhandled {pattern} in response",
                    test_prompt=prompt,
                ))
        
        # 5. 工具调用格式错误
        if ("<tool_call>" in response or "<function_calls>" in response):
            if response.count("<") != response.count(">"):
                issues.append(Issue(
                    type="malformed_tool_call",
                    severity=Severity.HIGH,
                    description="Malformed XML in tool calls",
                    test_prompt=prompt,
                ))
        
        # 6. 安全风险
        dangerous_patterns = ["rm -rf", "del /f /q", "format c:", "shutdown", ":(){:|:&};:"]
        for pattern in dangerous_patterns:
            if pattern.lower() in response.lower():
                issues.append(Issue(
                    type="safety_risk",
                    severity=Severity.CRITICAL,
                    description=f"Dangerous pattern detected: {pattern}",
                    test_prompt=prompt,
                ))
        
        return issues
    
    def analyze_round_with_ai(self, round_num: int, results: List[TestResult]) -> RoundSummary:
        """使用 AI 分析一轮测试结果"""
        
        # 收集数据
        passed = sum(1 for r in results if r.status == TestStatus.PASS)
        failed = len(results) - passed
        all_issues = []
        for r in results:
            all_issues.extend(r.issues)
        
        # 构建分析 prompt
        issues_text = ""
        if all_issues:
            issues_text = "\n发现的问题:\n"
            for i, issue in enumerate(all_issues[:10], 1):
                issues_text += f"{i}. [{issue.severity.value}] {issue.type}: {issue.description}\n"
                if issue.test_prompt:
                    issues_text += f"   触发输入: {issue.test_prompt[:50]}...\n"
        
        prompt = f"""
分析第 {round_num} 轮测试结果:

## 统计
- 总测试数: {len(results)}
- 通过: {passed}
- 失败: {failed}
- 通过率: {passed/len(results)*100:.1f}%

{issues_text}

## 请回答
1. 这轮测试是否暴露了严重问题？
2. 产品是否可以认为稳定？（连续 {self.stability_threshold} 轮无高危问题 = 稳定）
3. 下一轮应该重点测试什么？

以 JSON 格式返回:
```json
{{
  "is_stable": true/false,
  "stability_reason": "判断理由",
  "critical_issues": ["关键问题1", "..."],
  "next_focus": ["下轮重点1", "..."],
  "overall_assessment": "整体评估"
}}
```
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
            
            analysis = json.loads(json_str)
            is_stable = analysis.get("is_stable", False) and not any(
                i.severity in [Severity.CRITICAL, Severity.HIGH] for i in all_issues
            )
            
            return RoundSummary(
                round=round_num,
                total_tests=len(results),
                passed=passed,
                failed=failed,
                issues_found=all_issues,
                is_stable=is_stable,
                ai_analysis=analysis.get("overall_assessment", ""),
            )
            
        except Exception as e:
            print(f"[!] AI analysis failed: {e}")
            # 基于规则判断
            is_stable = not any(
                i.severity in [Severity.CRITICAL, Severity.HIGH] for i in all_issues
            )
            
            return RoundSummary(
                round=round_num,
                total_tests=len(results),
                passed=passed,
                failed=failed,
                issues_found=all_issues,
                is_stable=is_stable,
                ai_analysis=f"Rule-based: {passed}/{len(results)} passed",
            )
    
    async def run_round(self, round_num: int) -> RoundSummary:
        """执行一轮测试"""
        print(f"\n{'='*60}")
        print(f"ROUND {round_num}")
        print(f"{'='*60}")
        
        # 1. 生成测试用例
        print("\n[1/4] Generating test cases with AI...")
        previous_issues = self.all_issues[-20:] if self.all_issues else None
        test_cases = self.generate_test_cases(round_num, previous_issues)
        print(f"      Generated {len(test_cases)} test cases")
        
        # 2. 执行测试
        print(f"\n[2/4] Running tests...")
        results: List[TestResult] = []
        issues_to_fix: List[tuple] = []  # (issue, test_result, test_case)
        
        for i, test_case in enumerate(test_cases):
            prompt_preview = test_case.get("prompt", "")[:40]
            print(f"  [{i+1}/{len(test_cases)}] {test_case.get('category', '?')}: {prompt_preview}...")
            
            result = await self.run_single_test(test_case, i, round_num)
            results.append(result)
            
            # 显示结果
            status_icon = {
                TestStatus.PASS: "✓",
                TestStatus.FAIL: "✗",
                TestStatus.ERROR: "!",
                TestStatus.TIMEOUT: "⏱",
                TestStatus.CRASH: "💥",
            }.get(result.status, "?")
            
            try:
                print(f"       {status_icon} {result.status.value.upper()} ({result.execution_time:.1f}s)")
            except UnicodeEncodeError:
                print(f"       [{result.status.value.upper()}] ({result.execution_time:.1f}s)")
            
            if result.issues:
                for issue in result.issues[:2]:
                    print(f"         - [{issue.severity.value}] {issue.type}")
                    # 收集需要修复的高危问题
                    if self.auto_fix and issue.severity in [Severity.CRITICAL, Severity.HIGH]:
                        issues_to_fix.append((issue, result, test_case))
        
        # 3. 自动修复（如果启用）
        fixes_this_round = 0
        if self.auto_fix and issues_to_fix:
            print(f"\n[3/4] Auto-fixing {len(issues_to_fix)} high-severity issues...")
            
            for issue, test_result, test_case in issues_to_fix:
                print(f"\n  Fixing: [{issue.severity.value}] {issue.type}")
                print(f"          {issue.description[:60]}...")
                
                if await self.try_fix_issue(issue, test_result, test_case):
                    fixes_this_round += 1
                    print(f"          ✓ Fixed successfully!")
                else:
                    print(f"          ✗ Could not fix automatically")
            
            print(f"\n      Fixed {fixes_this_round}/{len(issues_to_fix)} issues this round")
        else:
            print(f"\n[3/4] No auto-fix needed (no high-severity issues or auto-fix disabled)")
        
        # 4. AI 分析
        print(f"\n[4/4] AI analyzing results...")
        summary = self.analyze_round_with_ai(round_num, results)
        
        # 更新统计
        self.total_rounds += 1
        self.total_tests += len(results)
        self.all_issues.extend(summary.issues_found)
        self.total_issues += len(summary.issues_found)
        self.round_summaries.append(summary)
        
        # 更新连续稳定轮数
        if summary.is_stable:
            self.consecutive_stable_rounds += 1
        else:
            self.consecutive_stable_rounds = 0
        
        # 显示轮次总结
        print(f"\n--- Round {round_num} Summary ---")
        print(f"Passed: {summary.passed}/{summary.total_tests}")
        print(f"Issues: {len(summary.issues_found)}")
        if self.auto_fix:
            print(f"Fixes applied this round: {fixes_this_round}")
            print(f"Total fixes applied: {len(self.fixes_applied)}")
        print(f"Stable: {'Yes' if summary.is_stable else 'No'}")
        print(f"Consecutive stable rounds: {self.consecutive_stable_rounds}/{self.stability_threshold}")
        if summary.ai_analysis:
            print(f"AI Assessment: {summary.ai_analysis[:100]}...")
        
        # 保存结果
        self._save_round_results(round_num, results, summary)
        
        return summary
    
    def _save_round_results(self, round_num: int, results: List[TestResult], summary: RoundSummary):
        """保存单轮结果"""
        output_file = self.output_dir / f"round_{round_num:04d}.json"
        
        data = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": summary.total_tests,
                "passed": summary.passed,
                "failed": summary.failed,
                "is_stable": summary.is_stable,
                "ai_analysis": summary.ai_analysis,
            },
            "results": [
                {
                    "id": r.id,
                    "prompt": r.prompt,
                    "category": r.category,
                    "status": r.status.value,
                    "execution_time": r.execution_time,
                    "error": r.error,
                    "issues": [
                        {
                            "type": i.type,
                            "severity": i.severity.value,
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
        
        report = f"""
{'='*60}
NogicOS INFINITE AI TESTER - FINAL REPORT
{'='*60}

Session: {self.session_id}
Duration: {elapsed/60:.1f} minutes
Auto-Fix: {'Enabled' if self.auto_fix else 'Disabled'}

## Summary
- Total Rounds: {self.total_rounds}
- Total Tests: {self.total_tests}
- Total Issues Found: {self.total_issues}
- Fixes Applied: {len(self.fixes_applied)}
- Fixes Failed: {len(self.fixes_failed)}
- Consecutive Stable Rounds: {self.consecutive_stable_rounds}
- Final Status: {'✓ STABLE' if self.consecutive_stable_rounds >= self.stability_threshold else '✗ UNSTABLE'}

## Rounds Overview
"""
        
        for summary in self.round_summaries:
            status = "✓" if summary.is_stable else "✗"
            report += f"  Round {summary.round}: {summary.passed}/{summary.total_tests} passed, {len(summary.issues_found)} issues {status}\n"
        
        # 按类型统计问题
        if self.all_issues:
            report += "\n## Issues by Type\n"
            issue_types: Dict[str, int] = {}
            for issue in self.all_issues:
                issue_types[issue.type] = issue_types.get(issue.type, 0) + 1
            
            for issue_type, count in sorted(issue_types.items(), key=lambda x: -x[1]):
                report += f"  {issue_type}: {count}\n"
        
        # 修复详情
        if self.fixes_applied:
            report += "\n## Fixes Applied\n"
            for i, fix in enumerate(self.fixes_applied, 1):
                report += f"  {i}. [{fix.issue_type}] {fix.file_path}\n"
                report += f"     {fix.explanation[:80]}...\n"
                report += f"     Verified: {'Yes' if fix.verified else 'No'}\n"
        
        if self.fixes_failed:
            report += "\n## Fixes Failed\n"
            for i, fix in enumerate(self.fixes_failed, 1):
                report += f"  {i}. [{fix.issue_type}] {fix.file_path}\n"
                report += f"     {fix.explanation[:80]}...\n" if fix.explanation else ""
        
        report += f"""
## Conclusion
{'Product is STABLE! ✓' if self.consecutive_stable_rounds >= self.stability_threshold else 'Product needs more work.'}

Results saved to: {self.output_dir}
{'='*60}
"""
        
        return report
    
    async def run(self, max_rounds: int = 100) -> bool:
        """
        运行无限测试循环
        
        Returns:
            True if product reached stability, False otherwise
        """
        print("\n" + "="*60)
        print("NogicOS INFINITE AI TESTER" + (" + AUTO-FIX" if self.auto_fix else ""))
        print("="*60)
        print(f"Stability threshold: {self.stability_threshold} consecutive stable rounds")
        print(f"Tests per round: {self.tests_per_round}")
        print(f"Max rounds: {max_rounds}")
        print(f"Auto-fix: {'Enabled (max {0} attempts per issue)'.format(self.max_fix_attempts) if self.auto_fix else 'Disabled'}")
        print(f"Output: {self.output_dir}")
        print("="*60)
        
        # 初始化
        self.init_llm()
        await self.init_agent()
        
        round_num = 0
        
        try:
            while round_num < max_rounds:
                round_num += 1
                
                # 执行一轮测试
                summary = await self.run_round(round_num)
                
                # 检查是否达到稳定
                if self.consecutive_stable_rounds >= self.stability_threshold:
                    print(f"\n{'='*60}")
                    print(f"🎉 PRODUCT IS STABLE!")
                    print(f"   {self.consecutive_stable_rounds} consecutive stable rounds achieved")
                    print(f"{'='*60}")
                    break
                
                # 短暂休息（避免 API 限流）
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n[!] Test loop interrupted by user")
        
        except Exception as e:
            print(f"\n\n[!] Test loop failed: {e}")
            traceback.print_exc()
        
        finally:
            # 生成最终报告
            report = self.generate_final_report()
            print(report)
            
            # 保存最终报告
            report_file = self.output_dir / "final_report.txt"
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report)
            
            # 保存完整数据
            full_data_file = self.output_dir / "full_results.json"
            with open(full_data_file, "w", encoding="utf-8") as f:
                json.dump({
                    "session_id": self.session_id,
                    "total_rounds": self.total_rounds,
                    "total_tests": self.total_tests,
                    "total_issues": self.total_issues,
                    "consecutive_stable_rounds": self.consecutive_stable_rounds,
                    "is_stable": self.consecutive_stable_rounds >= self.stability_threshold,
                    "auto_fix_enabled": self.auto_fix,
                    "fixes_applied": [
                        {
                            "issue_type": f.issue_type,
                            "file_path": f.file_path,
                            "explanation": f.explanation,
                            "verified": f.verified,
                            "backup_path": f.backup_path,
                        }
                        for f in self.fixes_applied
                    ],
                    "fixes_failed": [
                        {
                            "issue_type": f.issue_type,
                            "file_path": f.file_path,
                            "explanation": f.explanation,
                        }
                        for f in self.fixes_failed
                    ],
                    "all_issues": [
                        {
                            "type": i.type,
                            "severity": i.severity.value,
                            "description": i.description,
                            "test_prompt": i.test_prompt,
                        }
                        for i in self.all_issues
                    ],
                }, f, ensure_ascii=False, indent=2)
        
        return self.consecutive_stable_rounds >= self.stability_threshold


async def main():
    parser = argparse.ArgumentParser(description="NogicOS Infinite AI Tester with Auto-Fix")
    parser.add_argument("--max-rounds", type=int, default=100, help="Maximum number of test rounds")
    parser.add_argument("--stability-threshold", type=int, default=3, help="Consecutive stable rounds needed")
    parser.add_argument("--tests-per-round", type=int, default=10, help="Number of tests per round")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout per test in seconds")
    parser.add_argument("--output", type=str, default="tests/infinite_test_results", help="Output directory")
    parser.add_argument("--no-fix", action="store_true", help="Disable auto-fix (test only)")
    parser.add_argument("--max-fix-attempts", type=int, default=3, help="Max fix attempts per issue type")
    args = parser.parse_args()
    
    tester = InfiniteAITester(
        output_dir=args.output,
        stability_threshold=args.stability_threshold,
        tests_per_round=args.tests_per_round,
        timeout_per_test=args.timeout,
        auto_fix=not args.no_fix,
        max_fix_attempts=args.max_fix_attempts,
    )
    
    is_stable = await tester.run(max_rounds=args.max_rounds)
    
    # Exit code: 0 if stable, 1 if not
    sys.exit(0 if is_stable else 1)


if __name__ == "__main__":
    asyncio.run(main())

