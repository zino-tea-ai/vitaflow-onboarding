"""
Phase 5 单元测试
================

测试 LLM 集成相关功能
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch


# ========== 导入测试 ==========

class TestImports:
    """测试模块导入"""
    
    def test_llm_client_import(self):
        """测试 LLM 客户端导入"""
        from nogicos.engine.agent.llm_client import (
            LLMClient, LLMConfig, CacheStats,
            get_llm_client, generate,
        )
        assert LLMClient is not None
        assert LLMConfig is not None
        assert CacheStats is not None
    
    def test_prompts_import(self):
        """测试 Prompt 模块导入"""
        from nogicos.engine.agent.prompts import (
            AgentMode, PromptBuilder, build_system_prompt,
            SYSTEM_PROMPT_TEMPLATE, THINKING_TEMPLATES,
        )
        assert AgentMode is not None
        assert PromptBuilder is not None
        assert SYSTEM_PROMPT_TEMPLATE is not None
    
    def test_tool_descriptions_import(self):
        """测试工具描述导入"""
        from nogicos.engine.agent.tool_descriptions import (
            ToolDescription, ToolRegistry,
            get_tool_registry, get_tool_schemas,
            TOOL_DESCRIPTIONS,
        )
        assert ToolDescription is not None
        assert ToolRegistry is not None
        assert TOOL_DESCRIPTIONS is not None
    
    def test_context_manager_import(self):
        """测试上下文管理器导入"""
        from nogicos.engine.agent.context_manager import (
            ContextManager, TokenBudget, TokenCounter,
            ContextCompressor, CompressionResult,
            get_context_manager,
        )
        assert ContextManager is not None
        assert TokenBudget is not None
        assert TokenCounter is not None
    
    def test_vision_import(self):
        """测试视觉模块导入"""
        from nogicos.engine.agent.vision import (
            VisionEnhancer, EnhancedScreenshot, UIElement,
            get_vision_enhancer,
            OCRExtractor, OCRResult, TextRegion,
            get_ocr_extractor,
        )
        assert VisionEnhancer is not None
        assert EnhancedScreenshot is not None
        assert OCRExtractor is not None


# ========== LLM 配置测试 ==========

class TestLLMConfig:
    """测试 LLM 配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        from nogicos.engine.agent.llm_client import LLMConfig
        
        config = LLMConfig()
        assert config.model == "claude-sonnet-4-20250514"
        assert config.max_tokens == 4096
        assert config.temperature == 0.0
        assert config.enable_prompt_caching == True
        assert config.enable_streaming == True
    
    def test_custom_config(self):
        """测试自定义配置"""
        from nogicos.engine.agent.llm_client import LLMConfig
        
        config = LLMConfig(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            temperature=0.5,
            enable_prompt_caching=False,
        )
        assert config.model == "claude-3-haiku-20240307"
        assert config.max_tokens == 1024
        assert config.temperature == 0.5
        assert config.enable_prompt_caching == False


# ========== Token 预算测试 ==========

class TestTokenBudget:
    """测试 Token 预算"""
    
    def test_default_budget(self):
        """测试默认预算"""
        from nogicos.engine.agent.context_manager import TokenBudget
        
        budget = TokenBudget()
        assert budget.max_input_tokens == 180000
        assert budget.max_output_tokens == 8192
        assert budget.warning_threshold == 0.75
        assert budget.compression_threshold == 0.80
    
    def test_available_for_history(self):
        """测试可用历史空间计算"""
        from nogicos.engine.agent.context_manager import TokenBudget
        
        budget = TokenBudget(
            max_input_tokens=100000,
            system_prompt_reserve=5000,
            tool_definitions_reserve=3000,
            response_reserve=4096,
            max_screenshots=3,
            screenshot_tokens_estimate=1500,
        )
        
        # 100000 - 5000 - 3000 - 4096 - (3 * 1500) = 83404
        expected = 100000 - 5000 - 3000 - 4096 - (3 * 1500)
        assert budget.available_for_history == expected
    
    def test_estimate_cost(self):
        """测试成本估算"""
        from nogicos.engine.agent.context_manager import TokenBudget
        
        budget = TokenBudget()
        # 1M input tokens = $3, 1M output tokens = $15
        cost = budget.estimate_cost(1_000_000, 100_000)
        expected = 3.0 + 1.5  # $3 for input + $1.5 for output
        assert cost == expected


# ========== Prompt 构建测试 ==========

class TestPromptBuilder:
    """测试 Prompt 构建"""
    
    def test_build_system_prompt(self):
        """测试系统提示词构建"""
        from nogicos.engine.agent.prompts import build_system_prompt, AgentMode
        
        prompt = build_system_prompt(
            task_description="Search for Python tutorials",
            windows=[{"hwnd": 12345, "title": "Chrome", "app_type": "browser"}],
            mode=AgentMode.BROWSER,
        )
        
        assert "NogicOS" in prompt
        assert "Python tutorials" in prompt
        assert "Chrome" in prompt
        assert "BROWSER-SPECIFIC" in prompt
    
    def test_format_window_context(self):
        """测试窗口上下文格式化"""
        from nogicos.engine.agent.prompts import PromptBuilder
        
        builder = PromptBuilder()
        context = builder.format_window_context([
            {"hwnd": 123, "title": "Notepad", "app_type": "desktop"},
            {"hwnd": 456, "title": "Chrome", "app_type": "browser"},
        ])
        
        assert "Notepad" in context
        assert "Chrome" in context
        assert "DESKTOP" in context
        assert "BROWSER" in context


# ========== 工具描述测试 ==========

class TestToolDescriptions:
    """测试工具描述"""
    
    def test_tool_registry(self):
        """测试工具注册表"""
        from nogicos.engine.agent.tool_descriptions import get_tool_registry
        
        registry = get_tool_registry()
        tools = registry.get_all()
        
        assert len(tools) > 0
        assert any(t.name == "window_screenshot" for t in tools)
        assert any(t.name == "window_click" for t in tools)
        assert any(t.name == "set_task_status" for t in tools)
    
    def test_to_claude_tools(self):
        """测试转换为 Claude 工具格式"""
        from nogicos.engine.agent.tool_descriptions import get_tool_schemas
        
        schemas = get_tool_schemas()
        
        assert len(schemas) > 0
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema
    
    def test_tool_description_content(self):
        """测试工具描述内容"""
        from nogicos.engine.agent.tool_descriptions import get_tool_registry
        
        registry = get_tool_registry()
        click_tool = registry.get("window_click")
        
        assert click_tool is not None
        assert click_tool.name == "window_click"
        assert len(click_tool.when_to_use) > 0
        assert len(click_tool.when_not_to_use) > 0
        assert "x" in click_tool.parameters
        assert "y" in click_tool.parameters


# ========== 缓存统计测试 ==========

class TestCacheStats:
    """测试缓存统计"""
    
    def test_cache_hit_rate(self):
        """测试缓存命中率计算"""
        from nogicos.engine.agent.llm_client import CacheStats
        
        stats = CacheStats(
            total_calls=10,
            cache_read_tokens=8000,
            cache_write_tokens=2000,
            input_tokens=2000,
            output_tokens=1000,
        )
        
        # cache_hit_rate = cache_read / (cache_read + input)
        expected_rate = 8000 / (8000 + 2000)
        assert stats.cache_hit_rate == expected_rate
    
    def test_estimated_savings(self):
        """测试成本节省估算"""
        from nogicos.engine.agent.llm_client import CacheStats
        
        stats = CacheStats(
            total_calls=1,
            cache_read_tokens=10000,
            cache_write_tokens=0,
            input_tokens=0,
            output_tokens=0,
        )
        
        # 纯缓存读取，节省 90%
        assert stats.estimated_savings > 0.8  # 应该接近 0.9


# ========== 上下文管理器测试 ==========

class TestContextManager:
    """测试上下文管理器"""
    
    def test_token_counter(self):
        """测试 Token 计数"""
        from nogicos.engine.agent.context_manager import TokenCounter
        
        counter = TokenCounter()
        tokens = counter.count("Hello, world!")
        
        # 应该返回一个正数
        assert tokens > 0
    
    def test_should_compress(self):
        """测试压缩判断"""
        from nogicos.engine.agent.context_manager import ContextManager, TokenBudget
        from nogicos.engine.agent.types import Message
        
        budget = TokenBudget(
            max_input_tokens=1000,
            compression_threshold=0.5,
        )
        manager = ContextManager(budget)
        
        # 空消息列表不需要压缩
        assert not manager.should_compress([])
    
    def test_get_status(self):
        """测试状态获取"""
        from nogicos.engine.agent.context_manager import ContextManager
        from nogicos.engine.agent.types import Message
        
        manager = ContextManager()
        status = manager.get_status([Message.user("Hello")])
        
        assert "current_tokens" in status
        assert "max_tokens" in status
        assert "usage_ratio" in status
        assert "status" in status


# ========== 视觉增强测试 ==========

class TestVisionEnhancer:
    """测试视觉增强器"""
    
    def test_enhanced_screenshot_methods(self):
        """测试增强截图方法"""
        from nogicos.engine.agent.vision import EnhancedScreenshot, TextRegion
        
        screenshot = EnhancedScreenshot(
            image_b64="",
            width=1920,
            height=1080,
            text_elements=[
                TextRegion(text="Submit", bbox=(100, 100, 200, 150), confidence=0.9),
                TextRegion(text="Cancel", bbox=(300, 100, 400, 150), confidence=0.8),
            ],
            full_text="Submit Cancel",
        )
        
        # 测试 find_text
        results = screenshot.find_text("submit")
        assert len(results) == 1
        assert results[0].text == "Submit"
        
        # 测试 to_context_string
        context = screenshot.to_context_string()
        assert "1920x1080" in context
        assert "Submit" in context or "2 text regions" in context
    
    def test_text_region(self):
        """测试文本区域"""
        from nogicos.engine.agent.vision import TextRegion
        
        region = TextRegion(
            text="Button",
            bbox=(100, 200, 200, 250),
            confidence=0.95,
        )
        
        assert region.center == (150, 225)
        assert region.width == 100
        assert region.height == 50
    
    def test_ui_element(self):
        """测试 UI 元素"""
        from nogicos.engine.agent.vision import UIElement
        
        button = UIElement(
            type="button",
            text="Submit",
            bbox=(100, 100, 200, 150),
            confidence=0.9,
        )
        
        assert button.clickable == True
        assert button.editable == False
        assert button.center == (150, 125)
        
        input_elem = UIElement(
            type="input",
            text="",
            bbox=(100, 200, 400, 230),
        )
        
        assert input_elem.clickable == False
        assert input_elem.editable == True


# ========== 集成测试 ==========

class TestIntegration:
    """集成测试"""
    
    def test_all_modules_from_init(self):
        """测试从 __init__ 导入所有模块"""
        from nogicos.engine.agent import (
            # LLM Client
            LLMClient, LLMConfig, CacheStats,
            # Prompts
            PromptAgentMode, PromptBuilder, build_system_prompt,
            # Tool Descriptions
            ToolDescription, ToolRegistry, get_tool_schemas,
            # Context Manager
            ContextManager, TokenBudget, TokenCounter,
            # Vision
            VisionEnhancer, EnhancedScreenshot, OCRExtractor,
        )
        
        # 验证都能导入
        assert LLMClient is not None
        assert PromptBuilder is not None
        assert ToolDescription is not None
        assert ContextManager is not None
        assert VisionEnhancer is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
