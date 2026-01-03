# -*- coding: utf-8 -*-
"""
NogicOS Smart Search - Cursor 风格的智能搜索
实现 2次 LLM 调用的高效搜索流程
"""

import os
import json
import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

import aiohttp
import anthropic

from engine.observability import get_logger

logger = get_logger("smart_search")


class SmartSearch:
    """
    Cursor 风格的智能搜索
    
    流程:
    0. Intent Detection - 判断是否需要搜索 (可选，快速判断)
    1. Query Optimization - LLM 优化用户输入为搜索 query
    2. Tavily Search - 调用 API 获取结果
    3. Result Synthesis - LLM 整合结果并生成回答
    
    调用精确度：
    - 需要搜索: 时效性问题、事实查询、最新信息
    - 不需要搜索: 代码问题、数学计算、通用知识、闲聊
    """
    
    # 强制不搜索的模式 (最高优先级)
    FORCE_NO_SEARCH = [
        "这段代码", "这个文件", "这个函数", "这个类",
        "帮我写", "帮我实现", "帮我修", "帮我debug",
    ]
    
    # 需要搜索的模式 (高优先级)
    SEARCH_PATTERNS = [
        # 时效性
        "最新", "2025", "2024", "今天", "最近", "现在",
        # 事实查询 (通用概念)
        "是什么意思", "有哪些", "区别", "对比", "怎么用",
        # 明确搜索
        "搜索", "查一下", "找一下", "看看",
        # 产品/公司/概念
        "YC", "Cursor", "OpenAI", "Anthropic", "Google",
        "量子", "AI", "人工智能", "机器学习", "区块链",
    ]
    
    # 不需要搜索的模式 (低优先级)
    NO_SEARCH_PATTERNS = [
        # 代码相关
        "写代码", "写一个", "实现一个", "函数", "class ", "def ", "import ",
        "debug", "修复", "报错", "error", "bug", "代码",
        # 数学计算
        "计算一下", "等于多少", "加减乘除",
        # 闲聊
        "你好", "谢谢", "再见", "帮帮我", "可以吗",
    ]
    
    def __init__(self):
        # 获取 API keys
        self.tavily_api_key = os.environ.get("TAVILY_API_KEY")
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        
        if not self.tavily_api_key:
            try:
                from api_keys import TAVILY_API_KEY
                self.tavily_api_key = TAVILY_API_KEY
            except ImportError:
                pass
        
        if not self.anthropic_api_key:
            try:
                from api_keys import ANTHROPIC_API_KEY
                self.anthropic_api_key = ANTHROPIC_API_KEY
            except ImportError:
                pass
        
        # 与 Cursor 保持一致，使用 Opus 4.5 保证质量
        self.optimizer_model = "claude-opus-4-5-20250514"  # 质量优先
        self.client = anthropic.AsyncAnthropic(api_key=self.anthropic_api_key) if self.anthropic_api_key else None
    
    def should_search(self, user_input: str) -> tuple[bool, str]:
        """
        快速判断是否需要搜索（无 LLM 调用，基于规则）
        
        优先级：强制不搜索 > 搜索模式 > 不搜索模式 > 默认规则
        
        返回: (是否搜索, 原因)
        """
        input_lower = user_input.lower()
        
        # 0. 最高优先级：强制不搜索（代码上下文相关）
        for pattern in self.FORCE_NO_SEARCH:
            if pattern.lower() in input_lower:
                return False, f"代码上下文: {pattern}"
        
        # 1. 检查是否明确需要搜索
        for pattern in self.SEARCH_PATTERNS:
            if pattern.lower() in input_lower:
                return True, f"匹配搜索模式: {pattern}"
        
        # 2. 检查是否明确不需要搜索
        for pattern in self.NO_SEARCH_PATTERNS:
            if pattern.lower() in input_lower:
                return False, f"匹配不搜索模式: {pattern}"
        
        # 3. 默认规则：问句或短文本 -> 搜索
        if "?" in user_input or "？" in user_input:
            return True, "疑问句，默认搜索"
        
        if len(user_input) < 30:
            return True, "短查询，默认搜索"
        
        return False, "长文本且无搜索关键词，默认不搜索"
        
    async def optimize_query(self, user_input: str) -> str:
        """
        Step 1: 用 LLM 将用户输入优化为搜索 query
        
        目标:
        - 提取关键词
        - 添加时间限定 (如 2025)
        - 扩展同义词
        - 移除无效词
        
        耗时目标: < 1秒
        """
        if not self.client:
            logger.warning("No Anthropic client, returning original query")
            return user_input
        
        # 极简 prompt 加速生成
        prompt = f"""Convert to search query. Output ONLY the query, no explanation.
If time-sensitive, add "2025". Use English keywords if helpful.

Input: {user_input}
Query:"""

        try:
            start = time.time()
            response = await self.client.messages.create(
                model=self.optimizer_model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            optimized = response.content[0].text.strip()
            logger.info(f"[QueryOptimize] {time.time()-start:.2f}s: '{user_input}' → '{optimized}'")
            return optimized
        except Exception as e:
            logger.error(f"Query optimization failed: {e}")
            return user_input
    
    async def tavily_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Step 2: 调用 Tavily API 搜索
        
        特性:
        - auto_parameters: 自动优化搜索参数
        - include_answer: 获取 AI 生成的答案
        
        耗时目标: 0.5-1.5秒
        """
        if not self.tavily_api_key:
            return {"error": "TAVILY_API_KEY not configured"}
        
        try:
            start = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "max_results": max_results,
                        "include_answer": True,
                        "include_raw_content": False,
                        "search_depth": "basic",  # basic 更快
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    logger.info(f"[TavilySearch] {time.time()-start:.2f}s: {len(data.get('results', []))} results")
                    return data
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return {"error": str(e)}
    
    async def synthesize_results(
        self, 
        user_input: str, 
        search_results: Dict[str, Any]
    ) -> str:
        """
        Step 3: 用 LLM 整合搜索结果
        
        目标:
        - 简洁回答用户问题
        - 提供来源引用
        - 突出关键信息
        
        耗时目标: 1-2秒
        """
        if not self.client:
            # 无 LLM 时返回原始结果
            answer = search_results.get("answer", "")
            results = search_results.get("results", [])
            
            output = answer + "\n\n**来源:**\n"
            for i, r in enumerate(results[:3], 1):
                output += f"{i}. [{r.get('title', 'Link')}]({r.get('url', '')})\n"
            return output
        
        # 构建精简上下文
        tavily_answer = search_results.get("answer", "")
        results = search_results.get("results", [])
        
        # 只取前3个结果，每个只取100字符
        context_parts = [f"AI摘要: {tavily_answer}"]
        for i, r in enumerate(results[:3], 1):
            context_parts.append(f"{i}. {r.get('title', '')} - {r.get('content', '')[:100]}")
        context = "\n".join(context_parts)
        
        # 极简 prompt - 强制中文
        prompt = f"""根据搜索结果用中文简洁回答。末尾附来源链接。

问题: {user_input}
{context}
回答:"""

        try:
            start = time.time()
            response = await self.client.messages.create(
                model=self.optimizer_model,
                max_tokens=300,  # 限制输出长度加速
                messages=[{"role": "user", "content": prompt}]
            )
            synthesized = response.content[0].text.strip()
            logger.info(f"[Synthesize] {time.time()-start:.2f}s")
            return synthesized
        except Exception as e:
            logger.error(f"Result synthesis failed: {e}")
            # Fallback to raw answer
            return search_results.get("answer", f"搜索完成，但整合失败: {e}")
    
    async def search(
        self, 
        user_input: str, 
        max_results: int = 5,
        force_search: bool = False  # 强制搜索，跳过判断
    ) -> Dict[str, Any]:
        """
        完整的智能搜索流程
        
        返回:
        {
            "success": bool,
            "should_search": bool,  # 是否执行了搜索
            "skip_reason": str,     # 如果跳过，原因是什么
            "answer": str,          # 整合后的回答
            "sources": list,        # 来源列表
            "timing": {...}
        }
        """
        total_start = time.time()
        timing = {}
        
        # Step 0: 判断是否需要搜索
        if not force_search:
            should, reason = self.should_search(user_input)
            if not should:
                timing["total_ms"] = (time.time() - total_start) * 1000
                return {
                    "success": True,
                    "should_search": False,
                    "skip_reason": reason,
                    "answer": None,
                    "sources": [],
                    "timing": timing
                }
        
        try:
            # Step 1: 优化 Query
            step1_start = time.time()
            optimized_query = await self.optimize_query(user_input)
            timing["optimize_query_ms"] = (time.time() - step1_start) * 1000
            
            # Step 2: Tavily 搜索
            step2_start = time.time()
            search_results = await self.tavily_search(optimized_query, max_results)
            timing["search_ms"] = (time.time() - step2_start) * 1000
            
            if "error" in search_results:
                return {
                    "success": False,
                    "error": search_results["error"],
                    "timing": timing
                }
            
            # Step 3: 整合结果
            step3_start = time.time()
            final_answer = await self.synthesize_results(user_input, search_results)
            timing["synthesize_ms"] = (time.time() - step3_start) * 1000
            
            timing["total_ms"] = (time.time() - total_start) * 1000
            
            # 提取来源
            sources = []
            for r in search_results.get("results", [])[:5]:
                sources.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:150]
                })
            
            return {
                "success": True,
                "should_search": True,
                "query": user_input,
                "optimized_query": optimized_query,
                "answer": final_answer,
                "tavily_answer": search_results.get("answer", ""),
                "sources": sources,
                "timing": timing
            }
            
        except Exception as e:
            timing["total_ms"] = (time.time() - total_start) * 1000
            logger.error(f"Smart search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "timing": timing
            }


# Singleton instance
_smart_search: Optional[SmartSearch] = None

def get_smart_search() -> SmartSearch:
    global _smart_search
    if _smart_search is None:
        _smart_search = SmartSearch()
    return _smart_search


async def smart_search(query: str, max_results: int = 5, force_search: bool = False) -> Dict[str, Any]:
    """Convenience function for smart search"""
    return await get_smart_search().search(query, max_results, force_search)


# CLI for testing
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from api_keys import setup_env
    setup_env()
    
    async def test():
        searcher = SmartSearch()
        
        test_queries = [
            "AI 最新进展",
            "Cursor IDE 怎么用",
            "今天天气",
        ]
        
        for q in test_queries:
            print(f"\n{'='*60}")
            print(f"Query: {q}")
            print('='*60)
            
            result = await searcher.search(q)
            
            if result["success"]:
                print(f"\n📝 优化后 Query: {result['optimized_query']}")
                print(f"\n📊 回答:\n{result['answer']}")
                print(f"\n⏱️ 耗时:")
                for k, v in result["timing"].items():
                    print(f"   {k}: {v:.0f}ms")
            else:
                print(f"❌ 失败: {result.get('error')}")
    
    asyncio.run(test())

