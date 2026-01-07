"""
NogicOS Context Manager - 上下文压缩策略
========================================

智能管理 LLM 上下文，支持：
1. Token 预算管理
2. 历史消息压缩（使用 Haiku）
3. 截图管理（保留最近 N 张）
4. 重要信息保留策略

参考:
- Claude Context Window Management
- LangGraph Message History Compression

Phase 5b 实现
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING
import logging
import base64
import json

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    tiktoken = None

from .types import Message, MessageRole

if TYPE_CHECKING:
    from .llm_client import LLMClient

logger = logging.getLogger(__name__)


# ========== Token 预算 ==========

@dataclass
class TokenBudget:
    """
    Token 预算配置
    
    管理输入/输出 token 限制和成本估算
    """
    # Token 限制
    max_input_tokens: int = 180000      # Claude 最大输入
    max_output_tokens: int = 8192       # 输出限制
    
    # 阈值
    warning_threshold: float = 0.75      # 75% 时警告
    compression_threshold: float = 0.80  # 80% 时触发压缩
    emergency_threshold: float = 0.95    # 95% 时紧急处理
    
    # 截图管理
    max_screenshots: int = 3             # 保留最近 N 张截图
    # 截图 Token 预算估算（用于预留空间）
    # 实际计数时使用动态估算：(width * height) / 750 * 1.2
    # 此值用于预留空间计算，应略高于平均值
    screenshot_tokens_estimate: int = 3500  # 1920x1080 实际约 3000-3500
    
    # 保留空间
    system_prompt_reserve: int = 5000    # 系统提示词保留
    tool_definitions_reserve: int = 3000 # 工具定义保留
    response_reserve: int = 4096         # 响应保留空间
    
    @property
    def available_for_history(self) -> int:
        """可用于历史消息的 token 数"""
        return (
            self.max_input_tokens 
            - self.system_prompt_reserve 
            - self.tool_definitions_reserve 
            - self.response_reserve
            - (self.max_screenshots * self.screenshot_tokens_estimate)
        )
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        估算 API 调用成本（美元）
        
        基于 Claude 3.5 Sonnet 定价:
        - Input: $3 / 1M tokens
        - Output: $15 / 1M tokens
        """
        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0
        return input_cost + output_cost


# ========== Token 计数器 ==========

class TokenCounter:
    """
    Token 计数器
    
    使用 tiktoken 进行准确计数，回退到估算
    """
    
    def __init__(self):
        self._encoder = None
        if HAS_TIKTOKEN:
            try:
                # Claude 使用 cl100k_base 编码（与 GPT-4 类似）
                self._encoder = tiktoken.get_encoding("cl100k_base")
            except Exception:
                pass
    
    def count(self, text: str) -> int:
        """计算文本的 token 数"""
        if self._encoder:
            return len(self._encoder.encode(text))
        else:
            # 无 tiktoken 时使用改进的估算
            return self._estimate_tokens(text)
    
    def _estimate_tokens(self, text: str) -> int:
        """
        改进的 token 估算（无 tiktoken 时使用）
        
        规则：
        - 英文/数字/标点: ~4 字符/token
        - 中文/日文/韩文: ~1.5 字符/token（CJK 字符占更多 token）
        - 混合文本按比例加权
        """
        if not text:
            return 0
        
        # 统计 CJK 字符数量
        cjk_count = 0
        for char in text:
            # CJK 统一汉字范围
            if '\u4e00' <= char <= '\u9fff':  # 中文
                cjk_count += 1
            elif '\u3040' <= char <= '\u30ff':  # 日文平假名/片假名
                cjk_count += 1
            elif '\uac00' <= char <= '\ud7af':  # 韩文
                cjk_count += 1
        
        non_cjk_count = len(text) - cjk_count
        
        # CJK 字符约 1.5 字符/token，非 CJK 约 4 字符/token
        cjk_tokens = cjk_count / 1.5
        non_cjk_tokens = non_cjk_count / 4
        
        # 加 10% 安全边际
        return int((cjk_tokens + non_cjk_tokens) * 1.1)
    
    def count_message(self, message: Message) -> int:
        """计算消息的 token 数"""
        tokens = 4  # 消息开销
        
        if isinstance(message.content, str):
            tokens += self.count(message.content)
        elif isinstance(message.content, list):
            tokens += self._count_content_list(message.content)
        
        if message.tool_calls:
            for tc in message.tool_calls:
                tokens += self.count(tc.name)
                tokens += self.count(json.dumps(tc.arguments))
        
        return tokens
    
    def _count_content_list(self, content_list: List[Any]) -> int:
        """
        递归计算内容列表的 token 数
        
        处理 text、image、tool_result 等类型，支持嵌套内容
        """
        tokens = 0
        
        for item in content_list:
            if isinstance(item, str):
                tokens += self.count(item)
            elif isinstance(item, dict):
                item_type = item.get("type", "")
                
                if item_type == "text":
                    tokens += self.count(item.get("text", ""))
                    
                elif item_type == "image":
                    tokens += self._estimate_image_tokens(item)
                    
                elif item_type == "tool_result":
                    # tool_result 的 content 可能是字符串或列表（含图片）
                    content = item.get("content", "")
                    if isinstance(content, str):
                        tokens += self.count(content)
                    elif isinstance(content, list):
                        # 递归处理嵌套内容（可能包含图片）
                        tokens += self._count_content_list(content)
                    elif isinstance(content, dict):
                        # 单个内容块
                        tokens += self._count_content_list([content])
                        
                elif item_type == "tool_use":
                    tokens += self.count(item.get("name", ""))
                    tokens += self.count(json.dumps(item.get("input", {})))
                    
                else:
                    # 未知类型，使用 JSON 估算
                    tokens += self.count(json.dumps(item))
        
        return tokens
    
    def count_messages(self, messages: List[Message]) -> int:
        """计算消息列表的总 token 数"""
        return sum(self.count_message(m) for m in messages)
    
    def _estimate_image_tokens(self, image_item: Dict[str, Any]) -> int:
        """
        动态估算图片 token 数
        
        根据 Anthropic 文档：
        - 基础估算：(width * height) / 750
        - 最小值：约 1000 tokens
        - 1920x1080 ≈ 2765 tokens，但实际可能更高
        
        Args:
            image_item: 图片内容字典，可能包含尺寸信息
            
        Returns:
            估算的 token 数
        """
        # 尝试从图片数据中提取尺寸
        width, height = 1920, 1080  # 默认 Full HD
        
        # 检查是否有尺寸信息
        source = image_item.get("source", {})
        if isinstance(source, dict):
            # 检查是否有明确的尺寸
            if "width" in source and "height" in source:
                width = source.get("width", width)
                height = source.get("height", height)
            
            # 尝试从 base64 数据推断尺寸
            data = source.get("data", "")
            if data and len(data) > 100:
                # 根据 base64 数据大小粗略估算
                # PNG/JPEG 压缩率不同，使用保守估算
                data_size = len(data) * 3 / 4  # base64 解码后大小
                
                # 假设 8-bit 颜色深度，3 通道，50% 压缩率
                # pixels ≈ data_size / (3 * 0.5) = data_size * 0.67
                estimated_pixels = data_size * 0.67
                
                # 假设宽高比 16:9
                estimated_height = int((estimated_pixels / (16/9)) ** 0.5)
                estimated_width = int(estimated_height * 16 / 9)
                
                if estimated_width > 100 and estimated_height > 100:
                    width = min(estimated_width, 4096)  # 限制最大尺寸
                    height = min(estimated_height, 4096)
        
        # 计算 token 数
        # Anthropic 公式：(width * height) / 750
        # 添加 20% 安全边际
        raw_tokens = (width * height) / 750
        tokens_with_margin = int(raw_tokens * 1.2)
        
        # 最小 1500 tokens（保守估算）
        return max(tokens_with_margin, 1500)


# ========== 上下文压缩器 ==========

@dataclass
class CompressionResult:
    """压缩结果"""
    messages: List[Message]
    original_tokens: int
    compressed_tokens: int
    removed_count: int
    summary_added: bool
    
    @property
    def compression_ratio(self) -> float:
        """压缩比"""
        if self.original_tokens == 0:
            return 0.0
        return 1 - (self.compressed_tokens / self.original_tokens)


class ContextCompressor:
    """
    上下文压缩器
    
    策略：
    1. 保留系统消息
    2. 保留最近 N 条消息
    3. 使用 Haiku 总结历史消息
    4. 保留包含截图的关键消息
    """
    
    # 【P1 修复】类级别的 Haiku 客户端，避免重复创建
    _haiku_client: Optional["LLMClient"] = None
    _haiku_initialized: bool = False
    
    def __init__(
        self,
        llm_client: Optional["LLMClient"] = None,
        use_haiku_summary: bool = True,
    ):
        """
        初始化压缩器
        
        Args:
            llm_client: LLM 客户端（用于生成摘要）
            use_haiku_summary: 是否使用 Haiku 生成摘要
        """
        self._llm_client = llm_client
        self._use_haiku_summary = use_haiku_summary
        self._counter = TokenCounter()
    
    async def compress(
        self,
        messages: List[Message],
        budget: TokenBudget,
        preserve_recent: int = 6,
    ) -> CompressionResult:
        """
        压缩消息历史
        
        Args:
            messages: 消息列表
            budget: Token 预算
            preserve_recent: 保留最近 N 条消息
            
        Returns:
            CompressionResult
        """
        original_tokens = self._counter.count_messages(messages)
        
        # 检查是否需要压缩
        if original_tokens <= budget.available_for_history:
            return CompressionResult(
                messages=messages,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                removed_count=0,
                summary_added=False,
            )
        
        logger.info(f"Compressing context: {original_tokens} tokens -> target {budget.available_for_history}")
        
        # 分离消息
        recent_messages = messages[-preserve_recent:] if len(messages) > preserve_recent else messages
        old_messages = messages[:-preserve_recent] if len(messages) > preserve_recent else []
        
        # 如果没有旧消息，直接返回
        if not old_messages:
            return CompressionResult(
                messages=recent_messages,
                original_tokens=original_tokens,
                compressed_tokens=self._counter.count_messages(recent_messages),
                removed_count=0,
                summary_added=False,
            )
        
        # 生成摘要
        summary = await self._summarize_history(old_messages)
        
        # 构建新消息列表
        compressed_messages = []
        
        # 添加摘要消息
        if summary:
            summary_msg = Message.system(f"[Previous conversation summary]\n{summary}")
            compressed_messages.append(summary_msg)
        
        # 添加最近消息
        compressed_messages.extend(recent_messages)
        
        compressed_tokens = self._counter.count_messages(compressed_messages)
        
        return CompressionResult(
            messages=compressed_messages,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            removed_count=len(old_messages),
            summary_added=bool(summary),
        )
    
    async def _summarize_history(self, messages: List[Message]) -> str:
        """
        使用 Haiku 总结历史消息 - P1 修复：复用客户端
        
        Args:
            messages: 要总结的消息
            
        Returns:
            摘要文本
        """
        if not self._use_haiku_summary:
            return self._extract_key_info(messages)
        
        # 构建总结提示
        history_text = self._format_messages_for_summary(messages)
        
        summary_prompt = f"""Summarize this conversation history concisely, preserving:
1. Key actions taken and their results
2. Important information discovered
3. Current progress towards the goal
4. Any errors or issues encountered

Keep the summary under 500 words.

Conversation history:
{history_text}"""
        
        try:
            # 【P1 修复】复用 Haiku 客户端
            haiku_client = await self._get_haiku_client()
            if not haiku_client:
                return self._extract_key_info(messages)
            
            response = await haiku_client.generate(
                messages=[Message.user(summary_prompt)],
                system_prompt="You are a concise summarizer. Extract key information only.",
            )
            
            return response.content
            
        except Exception as e:
            logger.warning(f"Failed to generate summary with Haiku: {e}")
            return self._extract_key_info(messages)
    
    @classmethod
    async def _get_haiku_client(cls) -> Optional["LLMClient"]:
        """
        获取或创建 Haiku 客户端单例 - P1 修复
        
        复用客户端避免资源泄漏
        """
        if cls._haiku_initialized:
            return cls._haiku_client
        
        try:
            from .llm_client import LLMClient, LLMConfig
            
            haiku_config = LLMConfig(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                enable_prompt_caching=False,  # 摘要不需要缓存
                enable_streaming=False,  # 摘要不需要流式
            )
            cls._haiku_client = LLMClient(haiku_config)
            await cls._haiku_client.initialize()
            cls._haiku_initialized = True
            
            logger.info("Haiku client initialized for context compression")
            return cls._haiku_client
            
        except Exception as e:
            logger.warning(f"Failed to initialize Haiku client: {e}")
            cls._haiku_initialized = True  # 标记已尝试，避免重复尝试
            return None
    
    def _format_messages_for_summary(self, messages: List[Message]) -> str:
        """格式化消息用于总结"""
        lines = []
        for msg in messages:
            role = msg.role.value.upper()
            if isinstance(msg.content, str):
                # 截断过长内容
                content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
                lines.append(f"[{role}]: {content}")
            elif isinstance(msg.content, list):
                # 处理复杂内容
                for item in msg.content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        content = item.get("text", "")[:500]
                        lines.append(f"[{role}]: {content}")
        
        return "\n".join(lines)
    
    def _extract_key_info(self, messages: List[Message]) -> str:
        """
        从消息中提取关键信息（不使用 LLM）
        
        Args:
            messages: 消息列表
            
        Returns:
            关键信息摘要
        """
        key_info = []
        
        for msg in messages:
            # 提取工具调用结果
            if msg.role == MessageRole.TOOL:
                if isinstance(msg.content, str):
                    # 只保留成功/失败状态
                    if "error" in msg.content.lower():
                        key_info.append(f"Tool error: {msg.content[:100]}")
                    elif "success" in msg.content.lower():
                        key_info.append(f"Tool success: {msg.name}")
            
            # 提取 assistant 的关键动作
            elif msg.role == MessageRole.ASSISTANT and msg.tool_calls:
                for tc in msg.tool_calls:
                    key_info.append(f"Action: {tc.name}")
        
        if not key_info:
            return "Previous actions taken but details summarized for brevity."
        
        return "Previous actions: " + "; ".join(key_info[:10])


# ========== 上下文管理器 ==========

class ContextManager:
    """
    上下文管理器
    
    综合管理 LLM 上下文：
    - Token 预算监控
    - 自动压缩触发
    - 截图管理
    - 状态报告
    """
    
    def __init__(
        self,
        budget: Optional[TokenBudget] = None,
        llm_client: Optional["LLMClient"] = None,
    ):
        """
        初始化上下文管理器
        
        Args:
            budget: Token 预算配置
            llm_client: LLM 客户端（用于压缩）
        """
        self.budget = budget or TokenBudget()
        self._counter = TokenCounter()
        self._compressor = ContextCompressor(llm_client)
        
        # 截图追踪
        self._screenshot_count = 0
    
    def count_tokens(self, messages: List[Message]) -> int:
        """计算消息的 token 数"""
        return self._counter.count_messages(messages)
    
    def get_usage_ratio(self, messages: List[Message]) -> float:
        """获取 token 使用率"""
        tokens = self.count_tokens(messages)
        return tokens / self.budget.available_for_history
    
    def should_warn(self, messages: List[Message]) -> bool:
        """是否应该警告"""
        return self.get_usage_ratio(messages) >= self.budget.warning_threshold
    
    def should_compress(self, messages: List[Message]) -> bool:
        """是否应该压缩"""
        return self.get_usage_ratio(messages) >= self.budget.compression_threshold
    
    def is_emergency(self, messages: List[Message]) -> bool:
        """是否紧急状态"""
        return self.get_usage_ratio(messages) >= self.budget.emergency_threshold
    
    async def maybe_compress(
        self,
        messages: List[Message],
        force: bool = False,
    ) -> List[Message]:
        """
        按需压缩消息
        
        Args:
            messages: 消息列表
            force: 强制压缩
            
        Returns:
            可能压缩后的消息列表
        """
        if not force and not self.should_compress(messages):
            return messages
        
        result = await self._compressor.compress(messages, self.budget)
        
        if result.compression_ratio > 0:
            logger.info(
                f"Compressed context: {result.original_tokens} -> {result.compressed_tokens} tokens "
                f"({result.compression_ratio:.1%} reduction, {result.removed_count} messages removed)"
            )
        
        return result.messages
    
    def manage_screenshots(
        self,
        messages: List[Message],
    ) -> List[Message]:
        """
        管理截图数量
        
        保留最近 N 张截图，移除旧截图
        
        Args:
            messages: 消息列表
            
        Returns:
            处理后的消息列表
        """
        max_screenshots = self.budget.max_screenshots
        screenshot_indices = []
        
        # 找出所有包含截图的消息位置
        for i, msg in enumerate(messages):
            if self._has_screenshot(msg):
                screenshot_indices.append(i)
        
        # 如果截图数量超限，移除旧截图
        if len(screenshot_indices) > max_screenshots:
            indices_to_remove = screenshot_indices[:-max_screenshots]
            
            # 创建新消息列表，替换旧截图
            new_messages = []
            for i, msg in enumerate(messages):
                if i in indices_to_remove:
                    # 用占位消息替换
                    new_messages.append(
                        Message(
                            role=msg.role,
                            content="[Screenshot removed to save context space]",
                        )
                    )
                else:
                    new_messages.append(msg)
            
            logger.debug(f"Removed {len(indices_to_remove)} old screenshots")
            return new_messages
        
        return messages
    
    def _has_screenshot(self, message: Message) -> bool:
        """检查消息是否包含截图"""
        if isinstance(message.content, list):
            for item in message.content:
                if isinstance(item, dict):
                    if item.get("type") == "image":
                        return True
                    if item.get("type") == "tool_result" and item.get("content", {}).get("type") == "image":
                        return True
        return False
    
    def get_status(self, messages: List[Message]) -> Dict[str, Any]:
        """
        获取上下文状态报告
        
        Returns:
            状态信息字典
        """
        tokens = self.count_tokens(messages)
        usage_ratio = self.get_usage_ratio(messages)
        
        return {
            "current_tokens": tokens,
            "max_tokens": self.budget.available_for_history,
            "usage_ratio": usage_ratio,
            "usage_percent": f"{usage_ratio:.1%}",
            "status": (
                "emergency" if self.is_emergency(messages)
                else "warning" if self.should_warn(messages)
                else "normal"
            ),
            "should_compress": self.should_compress(messages),
            "message_count": len(messages),
            "estimated_cost": self.budget.estimate_cost(tokens, 0),
        }


# ========== 便捷函数 ==========

_default_manager: Optional[ContextManager] = None


def get_context_manager(budget: Optional[TokenBudget] = None) -> ContextManager:
    """获取全局上下文管理器"""
    global _default_manager
    
    if _default_manager is None:
        _default_manager = ContextManager(budget)
    
    return _default_manager
