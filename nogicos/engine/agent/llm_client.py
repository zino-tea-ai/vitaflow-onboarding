"""
NogicOS LLM Client - Claude API 集成
=====================================

封装 Anthropic Claude API 调用，支持：
1. Prompt Caching - 降低成本，提高延迟
2. 流式输出 - 实时响应
3. Tool Calling - 工具调用

参考:
- Anthropic SDK Python: https://github.com/anthropics/anthropic-sdk-python
- Prompt Caching: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching

Phase 5 实现
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, AsyncIterator, Callable, Awaitable, TypeVar
import logging
import os
import json
import asyncio
import time

try:
    from anthropic import AsyncAnthropic, APIError, RateLimitError, APIConnectionError, APIStatusError
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    AsyncAnthropic = None
    APIError = Exception
    RateLimitError = Exception
    APIConnectionError = Exception
    APIStatusError = Exception

T = TypeVar('T')

from .types import (
    LLMResponse, ToolCall, Message, MessageRole, StopReason,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


# ========== 配置 ==========

@dataclass
class LLMConfig:
    """
    LLM 配置
    
    支持不同模型和参数配置
    """
    # 模型配置
    model: str = "claude-sonnet-4-20250514"  # 默认使用最新 Sonnet
    max_tokens: int = 4096
    temperature: float = 0.0  # 确定性输出，适合 Agent
    
    # API 配置
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: float = 120.0
    
    # 缓存配置
    enable_prompt_caching: bool = True
    cache_system_prompt: bool = True
    cache_tools: bool = True
    
    # 重试配置
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_max_delay: float = 60.0  # 最大退避时间
    retry_exponential_base: float = 2.0  # 指数退避基数
    
    # 流式配置
    enable_streaming: bool = True
    fallback_to_non_streaming: bool = True  # 流式失败时降级为非流式
    
    def __post_init__(self):
        # 从环境变量获取 API key
        if self.api_key is None:
            self.api_key = os.environ.get("ANTHROPIC_API_KEY")


@dataclass
class CacheStats:
    """
    缓存统计
    
    跟踪 Prompt Caching 效果
    """
    total_calls: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    
    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total = self.cache_read_tokens + self.input_tokens
        if total == 0:
            return 0.0
        return self.cache_read_tokens / total
    
    @property
    def estimated_savings(self) -> float:
        """
        估算节省的成本比例
        
        缓存读取成本 = 10% 正常输入成本
        缓存写入成本 = 125% 正常输入成本
        """
        normal_cost = self.input_tokens + self.cache_read_tokens
        cached_cost = self.input_tokens + self.cache_read_tokens * 0.1 + self.cache_write_tokens * 1.25
        if normal_cost == 0:
            return 0.0
        return 1 - (cached_cost / normal_cost)


# ========== 流式事件 ==========

@dataclass
class StreamEvent:
    """流式事件"""
    type: str  # "text", "tool_call", "message_start", "message_end"
    text: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    input_tokens: int = 0
    output_tokens: int = 0


# ========== LLM 客户端 ==========

class LLMClient:
    """
    Claude LLM 客户端
    
    封装 Anthropic API，支持：
    - Prompt Caching（降低 90% 成本）
    - 流式输出
    - Tool Calling
    
    使用示例:
    ```python
    config = LLMConfig()
    client = LLMClient(config)
    await client.initialize()
    
    # 非流式调用
    response = await client.generate(
        messages=[Message.user("Hello")],
        system_prompt="You are an AI assistant.",
        tools=[...]
    )
    
    # 流式调用
    async for event in client.stream(messages, system_prompt, tools):
        if event.type == "text":
            print(event.text, end="")
    ```
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初始化 LLM 客户端
        
        Args:
            config: LLM 配置
        """
        self.config = config or LLMConfig()
        self._client: Optional[AsyncAnthropic] = None
        self._cache_stats = CacheStats()
        
        # 系统提示词缓存（用于 Prompt Caching）
        self._cached_system_prompt: Optional[str] = None
        self._cached_tools: Optional[List[Dict[str, Any]]] = None
        
        self._initialized = False
    
    async def initialize(self):
        """初始化客户端"""
        if self._initialized:
            return
        
        if not HAS_ANTHROPIC:
            raise ImportError(
                "anthropic package not installed. "
                "Please run: pip install anthropic"
            )
        
        if not self.config.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. "
                "Please set the environment variable or pass api_key in config."
            )
        
        self._client = AsyncAnthropic(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )
        
        self._initialized = True
        logger.info(f"LLMClient initialized with model={self.config.model}")
    
    def _prepare_system_content(self, system_prompt: str) -> List[Dict[str, Any]]:
        """
        准备系统提示词内容（支持 Prompt Caching）
        
        Prompt Caching 关键点:
        - 使用 cache_control: {"type": "ephemeral"} 标记可缓存内容
        - 缓存有效期 5 分钟，每次使用自动刷新
        - 缓存读取成本仅为正常的 10%
        """
        if not self.config.enable_prompt_caching or not self.config.cache_system_prompt:
            # 不启用缓存
            return [{"type": "text", "text": system_prompt}]
        
        # 启用缓存
        return [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}  # 标记为可缓存
            }
        ]
    
    def _prepare_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        准备工具定义（支持 Prompt Caching）
        
        工具定义通常较大且稳定，非常适合缓存
        """
        if not tools:
            return []
        
        if not self.config.enable_prompt_caching or not self.config.cache_tools:
            return tools
        
        # 为最后一个工具添加 cache_control（Anthropic 要求缓存边界必须在特定位置）
        cached_tools = [tool.copy() for tool in tools]
        if cached_tools:
            cached_tools[-1]["cache_control"] = {"type": "ephemeral"}
        
        return cached_tools
    
    def _prepare_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """
        准备消息列表 - Phase 5 P0 修复
        
        转换 Message 对象为 Claude API 格式，正确处理：
        - 文本消息
        - 图片消息
        - 工具调用
        - 工具结果（含截图）
        """
        result = []
        
        # 收集相邻的工具结果消息（Claude 需要在一个 user 消息中发送）
        pending_tool_results = []
        
        for i, msg in enumerate(messages):
            # 处理工具结果消息 - 需要收集后合并
            if msg.role == MessageRole.TOOL and msg.tool_call_id:
                tool_result = self._format_tool_result_for_api(msg)
                pending_tool_results.append(tool_result)
                
                # 检查下一条消息是否也是工具结果
                next_is_tool = (
                    i + 1 < len(messages) and 
                    messages[i + 1].role == MessageRole.TOOL
                )
                
                # 如果下一条不是工具结果，将收集的结果打包发送
                if not next_is_tool and pending_tool_results:
                    result.append({
                        "role": "user",
                        "content": pending_tool_results,
                    })
                    pending_tool_results = []
                continue
            
            # 处理 assistant 消息（可能包含工具调用）
            if msg.role == MessageRole.ASSISTANT:
                api_msg = {"role": "assistant", "content": []}
                
                # 添加文本内容
                if msg.content:
                    if isinstance(msg.content, str):
                        api_msg["content"].append({
                            "type": "text",
                            "text": msg.content,
                        })
                    elif isinstance(msg.content, list):
                        api_msg["content"].extend(msg.content)
                
                # 添加工具调用
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        api_msg["content"].append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })
                
                # 确保至少有内容
                if not api_msg["content"]:
                    api_msg["content"] = [{"type": "text", "text": ""}]
                
                result.append(api_msg)
                continue
            
            # 处理 user 消息
            if msg.role == MessageRole.USER:
                api_msg = {"role": "user"}
                
                if isinstance(msg.content, str):
                    # 检查是否包含图片标记
                    if "[SCREENSHOT:" in msg.content:
                        api_msg["content"] = self._parse_content_with_images(msg.content)
                    else:
                        api_msg["content"] = msg.content
                elif isinstance(msg.content, list):
                    api_msg["content"] = msg.content
                else:
                    api_msg["content"] = str(msg.content)
                
                result.append(api_msg)
                continue
            
            # 其他消息类型
            api_msg = {
                "role": msg.role.value if msg.role != MessageRole.SYSTEM else "user",
                "content": msg.content if isinstance(msg.content, str) else str(msg.content),
            }
            result.append(api_msg)
        
        return result
    
    def _format_tool_result_for_api(self, msg: Message) -> Dict[str, Any]:
        """
        格式化工具结果为 API 格式 - Phase 5 P0 修复
        
        处理文本和图片结果
        """
        content = msg.content
        
        # 如果内容是列表（结构化内容，可能包含图片）
        if isinstance(content, list):
            return {
                "type": "tool_result",
                "tool_use_id": msg.tool_call_id,
                "content": content,
            }
        
        # 字符串内容
        if isinstance(content, str):
            # 检查是否包含截图标记（旧格式兼容）
            if "[SCREENSHOT:" in content:
                parts = content.split("[SCREENSHOT:")
                text_part = parts[0].strip()
                return {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": text_part or "Screenshot captured",
                }
            
            return {
                "type": "tool_result",
                "tool_use_id": msg.tool_call_id,
                "content": content,
            }
        
        # 其他类型转为 JSON
        return {
            "type": "tool_result",
            "tool_use_id": msg.tool_call_id,
            "content": json.dumps(content) if content else "Success",
        }
    
    def _parse_content_with_images(self, content: str) -> List[Dict[str, Any]]:
        """
        解析包含图片标记的内容 - Phase 5 P0 修复
        """
        result = []
        parts = content.split("[SCREENSHOT:")
        
        for i, part in enumerate(parts):
            if i == 0:
                # 第一部分是纯文本
                if part.strip():
                    result.append({"type": "text", "text": part.strip()})
            else:
                # 包含截图标记的部分
                if "]" in part:
                    # 截图标记后的文本
                    after_screenshot = part.split("]", 1)
                    if len(after_screenshot) > 1 and after_screenshot[1].strip():
                        result.append({"type": "text", "text": after_screenshot[1].strip()})
        
        return result if result else [{"type": "text", "text": content}]
    
    def _parse_response(self, response) -> LLMResponse:
        """
        解析 API 响应
        
        转换 Anthropic API 响应为 LLMResponse
        """
        content_text = ""
        tool_calls = []
        
        for block in response.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))
        
        # 解析停止原因
        stop_reason_map = {
            "end_turn": StopReason.END_TURN,
            "tool_use": StopReason.TOOL_USE,
            "max_tokens": StopReason.MAX_TOKENS,
            "stop_sequence": StopReason.STOP_SEQUENCE,
        }
        stop_reason = stop_reason_map.get(response.stop_reason, StopReason.END_TURN)
        
        # 更新缓存统计
        self._cache_stats.total_calls += 1
        self._cache_stats.input_tokens += response.usage.input_tokens
        self._cache_stats.output_tokens += response.usage.output_tokens
        
        # Prompt Caching 统计
        if hasattr(response.usage, 'cache_read_input_tokens'):
            self._cache_stats.cache_read_tokens += response.usage.cache_read_input_tokens
        if hasattr(response.usage, 'cache_creation_input_tokens'):
            self._cache_stats.cache_write_tokens += response.usage.cache_creation_input_tokens
        
        return LLMResponse(
            content=content_text,
            stop_reason=stop_reason,
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
    
    def _calculate_retry_delay(self, attempt: int, error: Exception = None) -> float:
        """
        计算重试延迟（指数退避）
        
        Args:
            attempt: 当前重试次数（从 1 开始）
            error: 异常对象（可能包含 retry-after 头）
            
        Returns:
            延迟秒数
        """
        # 检查是否有 retry-after 头
        if hasattr(error, 'response') and error.response:
            retry_after = error.response.headers.get('retry-after')
            if retry_after:
                try:
                    return min(float(retry_after), self.config.retry_max_delay)
                except ValueError:
                    pass
        
        # 指数退避: delay * base^attempt
        delay = self.config.retry_delay * (self.config.retry_exponential_base ** (attempt - 1))
        # 添加抖动避免同时重试
        import random
        jitter = random.uniform(0, delay * 0.1)
        return min(delay + jitter, self.config.retry_max_delay)
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        判断错误是否可重试
        
        Args:
            error: 异常对象
            
        Returns:
            是否可重试
        """
        # RateLimitError (429) - 可重试
        if isinstance(error, RateLimitError):
            return True
        
        # 连接错误 - 可重试
        if HAS_ANTHROPIC and isinstance(error, APIConnectionError):
            return True
        
        # 5xx 服务器错误 - 可重试
        if HAS_ANTHROPIC and isinstance(error, APIStatusError):
            if hasattr(error, 'status_code') and 500 <= error.status_code < 600:
                return True
        
        # 网络超时 - 可重试
        if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return True
        
        return False
    
    async def generate(
        self,
        messages: List[Message],
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """
        生成响应（非流式）- 带重试逻辑
        
        Args:
            messages: 消息历史
            system_prompt: 系统提示词
            tools: 工具定义列表
            
        Returns:
            LLMResponse
        """
        if not self._initialized:
            await self.initialize()
        
        # 准备请求参数
        system_content = self._prepare_system_content(system_prompt)
        api_messages = self._prepare_messages(messages)
        
        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "system": system_content,
            "messages": api_messages,
        }
        
        # 添加工具
        if tools:
            kwargs["tools"] = self._prepare_tools(tools)
        
        logger.debug(f"Calling Claude API: model={self.config.model}, messages={len(messages)}")
        
        last_error = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = await self._client.messages.create(**kwargs)
                return self._parse_response(response)
            
            except (RateLimitError, APIConnectionError, APIStatusError, asyncio.TimeoutError) as e:
                last_error = e
                
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable API error: {e}")
                    raise
                
                if attempt >= self.config.max_retries:
                    logger.error(f"Max retries ({self.config.max_retries}) exceeded: {e}")
                    raise
                
                delay = self._calculate_retry_delay(attempt, e)
                logger.warning(
                    f"API error (attempt {attempt}/{self.config.max_retries}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            
            except APIError as e:
                logger.error(f"API error: {e}")
                raise
        
        # 不应该到达这里，但以防万一
        raise last_error or RuntimeError("Unexpected error in generate")
    
    async def stream(
        self,
        messages: List[Message],
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        on_text: Optional[Callable[[str], Awaitable[None]]] = None,
        on_tool_call: Optional[Callable[[ToolCall], Awaitable[None]]] = None,
    ) -> LLMResponse:
        """
        流式生成响应 - 带重试和降级逻辑
        
        支持实时回调，适合前端展示
        失败时可降级为非流式调用
        
        Args:
            messages: 消息历史
            system_prompt: 系统提示词
            tools: 工具定义列表
            on_text: 文本回调（每个 token）
            on_tool_call: 工具调用回调
            
        Returns:
            最终的 LLMResponse
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.config.enable_streaming:
            # 直接使用非流式
            return await self.generate(messages, system_prompt, tools)
        
        # 准备请求参数
        system_content = self._prepare_system_content(system_prompt)
        api_messages = self._prepare_messages(messages)
        
        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "system": system_content,
            "messages": api_messages,
        }
        
        if tools:
            kwargs["tools"] = self._prepare_tools(tools)
        
        logger.debug(f"Streaming from Claude API: model={self.config.model}")
        
        last_error = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                return await self._do_stream(kwargs, on_text, on_tool_call)
            
            except (RateLimitError, APIConnectionError, APIStatusError, asyncio.TimeoutError) as e:
                last_error = e
                
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable streaming error: {e}")
                    break  # 尝试降级
                
                if attempt >= self.config.max_retries:
                    logger.warning(f"Max streaming retries exceeded: {e}")
                    break  # 尝试降级
                
                delay = self._calculate_retry_delay(attempt, e)
                logger.warning(
                    f"Streaming error (attempt {attempt}/{self.config.max_retries}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            
            except APIError as e:
                logger.error(f"Streaming API error: {e}")
                last_error = e
                break  # 尝试降级
        
        # 流式失败，尝试降级为非流式
        if self.config.fallback_to_non_streaming:
            logger.warning("Streaming failed, falling back to non-streaming mode")
            try:
                return await self.generate(messages, system_prompt, tools)
            except Exception as fallback_error:
                logger.error(f"Fallback to non-streaming also failed: {fallback_error}")
                # 抛出原始流式错误
                raise last_error or fallback_error
        
        # 不降级，直接抛出错误
        raise last_error or RuntimeError("Streaming failed")
    
    async def _do_stream(
        self,
        kwargs: Dict[str, Any],
        on_text: Optional[Callable[[str], Awaitable[None]]] = None,
        on_tool_call: Optional[Callable[[ToolCall], Awaitable[None]]] = None,
    ) -> LLMResponse:
        """
        执行流式调用的内部方法
        
        Args:
            kwargs: API 调用参数
            on_text: 文本回调
            on_tool_call: 工具调用回调
            
        Returns:
            LLMResponse
        """
        # 收集响应内容
        content_text = ""
        tool_calls = []
        current_tool_id = None
        current_tool_name = None
        current_tool_input = ""
        input_tokens = 0
        output_tokens = 0
        stop_reason = StopReason.END_TURN
        
        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "message_start":
                    if hasattr(event.message, 'usage'):
                        input_tokens = event.message.usage.input_tokens
                
                elif event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        current_tool_id = event.content_block.id
                        current_tool_name = event.content_block.name
                        current_tool_input = ""
                
                elif event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        # 文本增量
                        text = event.delta.text
                        content_text += text
                        if on_text:
                            await on_text(text)
                    
                    elif hasattr(event.delta, 'partial_json'):
                        # 工具输入增量
                        current_tool_input += event.delta.partial_json
                
                elif event.type == "content_block_stop":
                    if current_tool_id and current_tool_name:
                        # 完成工具调用
                        try:
                            tool_input = json.loads(current_tool_input) if current_tool_input else {}
                        except json.JSONDecodeError:
                            tool_input = {}
                        
                        tool_call = ToolCall(
                            id=current_tool_id,
                            name=current_tool_name,
                            arguments=tool_input,
                        )
                        tool_calls.append(tool_call)
                        
                        if on_tool_call:
                            await on_tool_call(tool_call)
                        
                        # 重置
                        current_tool_id = None
                        current_tool_name = None
                        current_tool_input = ""
                
                elif event.type == "message_delta":
                    if hasattr(event, 'delta') and hasattr(event.delta, 'stop_reason'):
                        stop_reason_map = {
                            "end_turn": StopReason.END_TURN,
                            "tool_use": StopReason.TOOL_USE,
                            "max_tokens": StopReason.MAX_TOKENS,
                            "stop_sequence": StopReason.STOP_SEQUENCE,
                        }
                        stop_reason = stop_reason_map.get(event.delta.stop_reason, StopReason.END_TURN)
                    
                    if hasattr(event, 'usage'):
                        output_tokens = event.usage.output_tokens
            
            # 获取最终消息以获取完整 usage
            final_message = await stream.get_final_message()
            
            # 更新统计
            self._cache_stats.total_calls += 1
            self._cache_stats.input_tokens += final_message.usage.input_tokens
            self._cache_stats.output_tokens += final_message.usage.output_tokens
            
            if hasattr(final_message.usage, 'cache_read_input_tokens'):
                self._cache_stats.cache_read_tokens += final_message.usage.cache_read_input_tokens
            if hasattr(final_message.usage, 'cache_creation_input_tokens'):
                self._cache_stats.cache_write_tokens += final_message.usage.cache_creation_input_tokens
        
        return LLMResponse(
            content=content_text,
            stop_reason=stop_reason,
            tool_calls=tool_calls,
            input_tokens=final_message.usage.input_tokens,
            output_tokens=final_message.usage.output_tokens,
        )
    
    def get_cache_stats(self) -> CacheStats:
        """获取缓存统计"""
        return self._cache_stats
    
    def reset_cache_stats(self):
        """重置缓存统计"""
        self._cache_stats = CacheStats()
    
    async def count_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量
        
        使用简单估算（实际应使用 tiktoken）
        """
        # 粗略估算：1 token ≈ 4 字符（英文），1 token ≈ 1.5 字符（中文）
        # 这里使用保守估算
        return len(text) // 3
    
    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.close()
            self._client = None
            self._initialized = False


# ========== 便捷函数 ==========

_default_client: Optional[LLMClient] = None


async def get_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """获取全局 LLM 客户端单例"""
    global _default_client
    
    if _default_client is None:
        _default_client = LLMClient(config)
        await _default_client.initialize()
    
    return _default_client


async def generate(
    messages: List[Message],
    system_prompt: str,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> LLMResponse:
    """便捷生成函数"""
    client = await get_llm_client()
    return await client.generate(messages, system_prompt, tools)
