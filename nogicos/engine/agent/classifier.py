# -*- coding: utf-8 -*-
"""
Task Classifier - Intelligent Task Routing for NogicOS

Analyzes user tasks and routes them to the appropriate execution path:
- BROWSER: Web automation tasks (navigate, click, search)
- LOCAL: File system and shell tasks (files, code, terminal)
- MIXED: Tasks requiring both browser and local capabilities

Architecture:
    User Task → Classifier → [Browser | Local | Mixed] → Executor
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional, Set

from engine.observability import get_logger

logger = get_logger("classifier")


class TaskType(Enum):
    """Task type classification"""
    BROWSER = "browser"  # Web automation
    LOCAL = "local"      # File/shell operations
    MIXED = "mixed"      # Both browser and local
    UNKNOWN = "unknown"  # Cannot determine


class TaskComplexity(Enum):
    """Task complexity level"""
    SIMPLE = "simple"      # Single action, no planning needed
    MODERATE = "moderate"  # 2-3 steps, light planning
    COMPLEX = "complex"    # 4+ steps, full planning required


@dataclass
class ClassificationResult:
    """Result of task classification"""
    task_type: TaskType
    complexity: TaskComplexity
    confidence: float  # 0.0 - 1.0
    browser_score: float
    local_score: float
    keywords_matched: List[str]
    reasoning: str


class TaskClassifier:
    """
    Intelligent task classifier that determines:
    1. Task type (browser/local/mixed)
    2. Task complexity (simple/moderate/complex)
    3. Confidence score
    
    Based on keyword matching and pattern analysis.
    
    Thread-safe singleton pattern - regex patterns compiled only once.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    # Browser task indicators
    BROWSER_KEYWORDS = {
        # Navigation
        "网页", "网站", "浏览器", "打开网", "访问", "链接",
        "url", "http", "https", "www", "navigate", "browse",
        
        # Interaction
        "点击", "click", "按钮", "button", "输入框", "表单",
        "登录", "login", "注册", "signup", "搜索", "search",
        
        # Content
        "截图", "screenshot", "下载", "download", "页面", "page",
        "滚动", "scroll", "等待", "wait",
        
        # Specific sites
        "google", "baidu", "bing", "youtube", "github",
        "twitter", "facebook", "weibo", "taobao", "amazon",
    }
    
    BROWSER_PATTERNS = [
        r"打开.*网",
        r"访问.*网站",
        r"去.*页面",
        r"在.*搜索",
        r"从.*下载",
        r"登录.*账号",
        r"http[s]?://",
        r"www\.",
    ]
    
    # Local task indicators
    LOCAL_KEYWORDS = {
        # File operations
        "文件", "文件夹", "目录", "folder", "directory", "file",
        "创建", "create", "删除", "delete", "移动", "move",
        "复制", "copy", "重命名", "rename", "读取", "read",
        "写入", "write", "保存", "save",
        
        # Code operations
        "代码", "code", "脚本", "script", "函数", "function",
        "程序", "program", "编译", "compile", "运行", "run",
        "调试", "debug", "修改", "modify", "编辑", "edit",
        
        # Shell operations
        "终端", "terminal", "命令", "command", "shell", "bash",
        "执行", "execute", "pip", "npm", "git",
        
        # Path indicators
        "桌面", "desktop", "文档", "documents", "下载", "downloads",
        "路径", "path", "~", "/", "\\",
    }
    
    LOCAL_PATTERNS = [
        r"创建.*文件",
        r"删除.*文件",
        r"移动.*到",
        r"复制.*到",
        r"读取.*内容",
        r"写入.*内容",
        r"运行.*脚本",
        r"执行.*命令",
        r"安装.*包",
        r"在.*目录",
        r"~/",
        r"[A-Z]:\\",  # Windows path
        r"\.(py|js|ts|html|css|json|txt|md)$",  # File extensions
    ]
    
    # Complexity indicators
    SEQUENCE_WORDS = [
        "和", "并且", "然后", "接着", "最后", "先", "再",
        "之后", "同时", "and", "then", "after", "finally",
        "first", "next", "also", "，然后",
    ]
    
    MULTI_ACTION_VERBS_CN = [
        "整理", "移动", "创建", "删除", "下载", "保存",
        "分析", "总结", "生成", "备份", "复制", "重命名",
        "打开", "关闭", "搜索", "查找", "替换", "提取",
    ]
    
    MULTI_ACTION_VERBS_EN = [
        "organize", "move", "create", "delete", "download", "save",
        "analyze", "summarize", "generate", "backup", "copy", "rename",
        "open", "close", "search", "find", "replace", "extract",
    ]
    
    def __init__(self):
        """Initialize classifier with compiled patterns (only once due to singleton)"""
        if TaskClassifier._initialized:
            return
        
        # Compile patterns once
        self._browser_patterns = [re.compile(p, re.IGNORECASE) for p in self.BROWSER_PATTERNS]
        self._local_patterns = [re.compile(p, re.IGNORECASE) for p in self.LOCAL_PATTERNS]
        
        TaskClassifier._initialized = True
        logger.info("TaskClassifier initialized (singleton)")
    
    def classify(self, task: str) -> ClassificationResult:
        """
        Classify a task into type and complexity.
        
        Args:
            task: User's task description
            
        Returns:
            ClassificationResult with type, complexity, and confidence
        """
        task_lower = task.lower()
        
        # Calculate scores
        browser_score, browser_keywords = self._calculate_browser_score(task, task_lower)
        local_score, local_keywords = self._calculate_local_score(task, task_lower)
        
        # Determine type
        task_type = self._determine_type(browser_score, local_score)
        
        # Determine complexity
        complexity = self._determine_complexity(task, task_lower)
        
        # Calculate confidence
        confidence = self._calculate_confidence(browser_score, local_score, task_type)
        
        # Generate reasoning
        all_keywords = browser_keywords + local_keywords
        reasoning = self._generate_reasoning(task_type, browser_score, local_score, all_keywords)
        
        result = ClassificationResult(
            task_type=task_type,
            complexity=complexity,
            confidence=confidence,
            browser_score=browser_score,
            local_score=local_score,
            keywords_matched=all_keywords,
            reasoning=reasoning,
        )
        
        logger.info(f"Classified task: {task_type.value} ({complexity.value}), confidence={confidence:.2f}")
        logger.debug(f"Keywords: {all_keywords}")
        
        return result
    
    def _calculate_browser_score(self, task: str, task_lower: str) -> Tuple[float, List[str]]:
        """Calculate browser task score"""
        score = 0.0
        matched = []
        
        # Keyword matching
        for keyword in self.BROWSER_KEYWORDS:
            if keyword.lower() in task_lower:
                score += 1.0
                matched.append(keyword)
        
        # Pattern matching (weighted higher)
        for pattern in self._browser_patterns:
            if pattern.search(task):
                score += 2.0
                matched.append(f"pattern:{pattern.pattern}")
        
        # URL detection (strong signal)
        if re.search(r'http[s]?://', task_lower) or re.search(r'www\.', task_lower):
            score += 5.0
        
        return score, matched
    
    def _calculate_local_score(self, task: str, task_lower: str) -> Tuple[float, List[str]]:
        """Calculate local task score"""
        score = 0.0
        matched = []
        
        # Keyword matching
        for keyword in self.LOCAL_KEYWORDS:
            if keyword.lower() in task_lower:
                score += 1.0
                matched.append(keyword)
        
        # Pattern matching (weighted higher)
        for pattern in self._local_patterns:
            if pattern.search(task):
                score += 2.0
                matched.append(f"pattern:{pattern.pattern}")
        
        # File path detection (strong signal)
        if re.search(r'[A-Z]:\\', task) or task.startswith('~') or '/home/' in task_lower:
            score += 5.0
        
        # File extension detection
        if re.search(r'\.\w{2,4}(?:\s|$|,)', task):
            score += 3.0
        
        return score, matched
    
    def _determine_type(self, browser_score: float, local_score: float) -> TaskType:
        """Determine task type based on scores"""
        # Clear winner
        if browser_score > local_score * 2:
            return TaskType.BROWSER
        if local_score > browser_score * 2:
            return TaskType.LOCAL
        
        # Both have significant scores
        if browser_score > 3 and local_score > 3:
            return TaskType.MIXED
        
        # Moderate difference
        if browser_score > local_score + 2:
            return TaskType.BROWSER
        if local_score > browser_score + 2:
            return TaskType.LOCAL
        
        # Very close or both low
        if browser_score < 2 and local_score < 2:
            return TaskType.UNKNOWN
        
        # Default to the higher one
        return TaskType.BROWSER if browser_score > local_score else TaskType.LOCAL
    
    def _determine_complexity(self, task: str, task_lower: str) -> TaskComplexity:
        """Determine task complexity"""
        # Check for sequence indicators
        sequence_count = sum(1 for word in self.SEQUENCE_WORDS if word in task)
        
        # Check for multiple action verbs
        action_count_cn = sum(1 for verb in self.MULTI_ACTION_VERBS_CN if verb in task)
        action_count_en = sum(1 for verb in self.MULTI_ACTION_VERBS_EN if verb in task_lower)
        action_count = action_count_cn + action_count_en
        
        # Simple patterns
        simple_patterns = [
            r"^(list|show|看看|查看|显示)",
            r"^(read|读|读取|打开)",
            r"^(what|what's|什么是|是什么)",
            r"^(help|帮助|怎么)",
        ]
        for pattern in simple_patterns:
            if re.match(pattern, task_lower):
                return TaskComplexity.SIMPLE
        
        # Length-based estimation
        task_length = len(task)
        
        # Complex indicators
        if sequence_count >= 2 or action_count >= 3:
            return TaskComplexity.COMPLEX
        if task_length > 100 and (sequence_count >= 1 or action_count >= 2):
            return TaskComplexity.COMPLEX
        
        # Moderate indicators
        if sequence_count >= 1 or action_count >= 2:
            return TaskComplexity.MODERATE
        if task_length > 50:
            return TaskComplexity.MODERATE
        
        # Default to simple
        return TaskComplexity.SIMPLE
    
    def _calculate_confidence(
        self, 
        browser_score: float, 
        local_score: float, 
        task_type: TaskType
    ) -> float:
        """Calculate classification confidence"""
        total = browser_score + local_score
        
        if total == 0:
            return 0.3  # Unknown, low confidence
        
        if task_type == TaskType.MIXED:
            # Confidence based on both having significant scores
            min_score = min(browser_score, local_score)
            return min(0.8, 0.5 + min_score / 10)
        
        if task_type == TaskType.UNKNOWN:
            return 0.3
        
        # Confidence based on score ratio
        if task_type == TaskType.BROWSER:
            ratio = browser_score / total
        else:  # LOCAL
            ratio = local_score / total
        
        # Map ratio to confidence (0.5 = 0.6, 1.0 = 1.0)
        return min(1.0, 0.6 + ratio * 0.4)
    
    def _generate_reasoning(
        self,
        task_type: TaskType,
        browser_score: float,
        local_score: float,
        keywords: List[str],
    ) -> str:
        """Generate human-readable reasoning"""
        type_map = {
            TaskType.BROWSER: "浏览器任务",
            TaskType.LOCAL: "本地任务",
            TaskType.MIXED: "混合任务",
            TaskType.UNKNOWN: "未知类型",
        }
        
        reasoning_parts = [f"判断为{type_map[task_type]}"]
        
        if browser_score > 0:
            reasoning_parts.append(f"浏览器特征分数={browser_score:.1f}")
        if local_score > 0:
            reasoning_parts.append(f"本地特征分数={local_score:.1f}")
        
        if keywords:
            # Show top 3 keywords
            top_keywords = keywords[:3]
            reasoning_parts.append(f"匹配关键词: {', '.join(top_keywords)}")
        
        return " | ".join(reasoning_parts)
    
    def get_recommended_tools(self, task_type: TaskType) -> Set[str]:
        """
        Get recommended tool categories for a task type.
        
        Args:
            task_type: The classified task type
            
        Returns:
            Set of tool category names to use
        """
        if task_type == TaskType.BROWSER:
            return {"browser", "vision"}
        elif task_type == TaskType.LOCAL:
            return {"local", "desktop"}
        elif task_type == TaskType.MIXED:
            return {"browser", "local", "vision", "desktop"}
        else:
            return {"local"}  # Default to local for unknown


# Singleton getter
def get_classifier() -> TaskClassifier:
    """Get the singleton TaskClassifier instance"""
    return TaskClassifier()


# Convenience function
def classify_task(task: str) -> ClassificationResult:
    """Quick task classification using singleton"""
    return get_classifier().classify(task)


# For testing
if __name__ == "__main__":
    classifier = TaskClassifier()
    
    test_tasks = [
        "打开 google.com 搜索 Python 教程",
        "创建一个新文件 test.py",
        "把桌面上的文件整理到 Documents 文件夹",
        "从 GitHub 下载项目，然后在本地运行",
        "帮我看看当前目录有什么文件",
        "登录网站然后下载报表保存到桌面",
    ]
    
    for task in test_tasks:
        result = classifier.classify(task)
        print(f"\n任务: {task}")
        print(f"  类型: {result.task_type.value}")
        print(f"  复杂度: {result.complexity.value}")
        print(f"  置信度: {result.confidence:.2f}")
        print(f"  推理: {result.reasoning}")

