# -*- coding: utf-8 -*-
"""
NogicOS Infinite AI Tester
无限循环测试，直到 AI 认为产品稳定

核心流程:
1. AI 生成测试用例
2. 执行测试
3. AI 分析结果
4. 如果有问题，记录并继续
5. 连续 N 轮无问题 = 产品稳定

Usage:
    python -m tests.infinite_ai_tester
    python -m tests.infinite_ai_tester --max-rounds 100
    python -m tests.infinite_ai_tester --stability-threshold 5
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
    """AI 驱动的无限测试循环"""
    
    def __init__(
        self,
        output_dir: str = "tests/infinite_test_results",
        stability_threshold: int = 3,  # 连续 N 轮无问题 = 稳定
        tests_per_round: int = 10,
        timeout_per_test: int = 60,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.stability_threshold = stability_threshold
        self.tests_per_round = tests_per_round
        self.timeout_per_test = timeout_per_test
        
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
    
    def call_llm(self, prompt: str, system: str = "") -> str:
        """调用 LLM"""
        client = self.init_llm()
        
        messages = [{"role": "user", "content": prompt}]
        
        response = client.messages.create(
            model=self.model_name,
            max_tokens=4000,
            system=system if system else "你是 NogicOS 的 QA 测试专家。",
            messages=messages,
        )
        
        return response.content[0].text
    
    def generate_test_cases(self, round_num: int, previous_issues: List[Issue] = None) -> List[Dict]:
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
        print("\n[1/3] Generating test cases with AI...")
        previous_issues = self.all_issues[-20:] if self.all_issues else None
        test_cases = self.generate_test_cases(round_num, previous_issues)
        print(f"      Generated {len(test_cases)} test cases")
        
        # 2. 执行测试
        print(f"\n[2/3] Running tests...")
        results: List[TestResult] = []
        
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
        
        # 3. AI 分析
        print(f"\n[3/3] AI analyzing results...")
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

## Summary
- Total Rounds: {self.total_rounds}
- Total Tests: {self.total_tests}
- Total Issues: {self.total_issues}
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
        print("NogicOS INFINITE AI TESTER")
        print("="*60)
        print(f"Stability threshold: {self.stability_threshold} consecutive stable rounds")
        print(f"Tests per round: {self.tests_per_round}")
        print(f"Max rounds: {max_rounds}")
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
    parser = argparse.ArgumentParser(description="NogicOS Infinite AI Tester")
    parser.add_argument("--max-rounds", type=int, default=100, help="Maximum number of test rounds")
    parser.add_argument("--stability-threshold", type=int, default=3, help="Consecutive stable rounds needed")
    parser.add_argument("--tests-per-round", type=int, default=10, help="Number of tests per round")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout per test in seconds")
    parser.add_argument("--output", type=str, default="tests/infinite_test_results", help="Output directory")
    args = parser.parse_args()
    
    tester = InfiniteAITester(
        output_dir=args.output,
        stability_threshold=args.stability_threshold,
        tests_per_round=args.tests_per_round,
        timeout_per_test=args.timeout,
    )
    
    is_stable = await tester.run(max_rounds=args.max_rounds)
    
    # Exit code: 0 if stable, 1 if not
    sys.exit(0 if is_stable else 1)


if __name__ == "__main__":
    asyncio.run(main())

