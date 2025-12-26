"""
SkillFlow 增强版探索学习
带有 WebSocket 实时状态广播
"""
import asyncio
import os
import time
from typing import Optional
from urllib.parse import urlparse

import typer
from aioconsole import aprint
from playwright.async_api import async_playwright

from skillweaver.environment import make_browsers
from skillweaver.environment.patches import apply_patches
from skillweaver.knowledge_base.knowledge_base import KnowledgeBase, load_knowledge_base
from skillweaver.lm import LM
from skillweaver.explore import (
    _choose_test_task,
    _choose_explore_task,
    _successfully_executes_function_without_errors,
)
from skillweaver.attempt_task import attempt_task
from skillweaver.agent import codegen_trajectory_to_string

# 导入 WebSocket 广播功能
from skillweaver.websocket_server import (
    start_server,
    broadcast_learn_start,
    broadcast_learn_progress,
    broadcast_skill_discovered,
    broadcast_learn_complete,
    broadcast_kb_loaded,
)


def _get_untested_functions(knowledge_base: KnowledgeBase):
    """获取未测试的函数列表"""
    untested = []
    for func in knowledge_base.get_functions():
        if func.get("test_count", 0) == 0:
            untested.append(func)
    return untested


async def explore_with_ws(
    start_urls: list[str],
    lm: LM,
    knowledge_base: KnowledgeBase,
    output_dir: str,
    iterations: int = 10,
    force_test_probability: float = 0.3,
    allow_recovery: bool = True,
    headless: bool = False,
):
    """探索学习并通过 WebSocket 广播状态"""
    start_time = time.time()
    total_skills_learned = 0
    
    # 广播学习开始
    broadcast_learn_start(start_urls[0] if start_urls else "unknown", iterations)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 保存初始知识库
    knowledge_base.save(output_dir)
    
    async with async_playwright() as p:
        browsers = await make_browsers(
            p,
            start_urls,
            headless=headless,
        )
        
        browser = browsers[0]
        
        for iteration in range(iterations):
            iter_start = time.time()
            iter_dir = os.path.join(output_dir, f"iter_{iteration}")
            
            if not os.path.exists(iter_dir):
                os.makedirs(iter_dir)
            
            await aprint(f"\n{'='*50}")
            await aprint(f"Iteration {iteration + 1}/{iterations}")
            await aprint(f"{'='*50}")
            
            # 广播学习进度
            broadcast_learn_progress(
                iteration + 1, 
                iterations,
                f"开始第 {iteration + 1} 轮探索..."
            )
            
            try:
                # 获取当前状态
                state = await browser.observe()
                
                # 决定是测试还是探索
                untested = _get_untested_functions(knowledge_base)
                
                import random
                should_test = (
                    len(untested) > 0 and 
                    random.random() < force_test_probability
                )
                
                if should_test:
                    await aprint(f"📝 Testing existing skill...")
                    broadcast_learn_progress(
                        iteration + 1,
                        iterations,
                        f"测试已有技能: {untested[0]['name'] if untested else 'unknown'}"
                    )
                    meta, task = await _choose_test_task(lm, state, knowledge_base, untested)
                else:
                    await aprint(f"🔍 Exploring for new skills...")
                    broadcast_learn_progress(
                        iteration + 1,
                        iterations,
                        "探索新技能..."
                    )
                    
                    is_live = not any(
                        url.startswith("http://localhost") or 
                        url.startswith("http://127.0.0.1")
                        for url in start_urls
                    )
                    meta, task = await _choose_explore_task(lm, state, knowledge_base, is_live)
                
                # 执行任务
                states, actions = await attempt_task(
                    browser,
                    lm,
                    task,
                    max_steps=10,
                    knowledge_base=knowledge_base,
                    store_dir=iter_dir,
                    allow_recovery=allow_recovery,
                )
                
                # 处理结果
                if len(actions) > 0:
                    last_action = actions[-1]
                    
                    # 检查是否成功
                    if task["type"] == "test":
                        if _successfully_executes_function_without_errors(task, last_action):
                            knowledge_base.record_test(
                                task["function_name"],
                                task["function_args"],
                                True
                            )
                            await aprint(f"✅ Test passed for {task['function_name']}")
                            broadcast_learn_progress(
                                iteration + 1,
                                iterations,
                                f"✅ 技能测试通过: {task['function_name']}"
                            )
                    elif task["type"] == "explore":
                        # 从探索中提取新技能
                        if "formatted_code" in last_action and last_action.get("result", {}).get("exception") is None:
                            skill_name = f"skill_iter_{iteration}"
                            await aprint(f"🆕 Discovered potential skill from exploration")
                            broadcast_skill_discovered(
                                skill_name,
                                task.get("task", "Discovered skill")[:100]
                            )
                            total_skills_learned += 1
                
                # 保存知识库
                knowledge_base.save(output_dir)
                
            except Exception as e:
                await aprint(f"❌ Error in iteration {iteration}: {e}")
                broadcast_learn_progress(
                    iteration + 1,
                    iterations,
                    f"❌ 迭代出错: {str(e)[:50]}"
                )
            
            # 重置浏览器到起始页
            try:
                await browser.active_page.goto(start_urls[0])
                await browser.active_page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass
            
            iter_duration = time.time() - iter_start
            await aprint(f"⏱️ Iteration {iteration + 1} completed in {iter_duration:.1f}s")
        
        # 关闭浏览器
        for b in browsers:
            await b.close()
    
    # 广播学习完成
    total_duration = time.time() - start_time
    broadcast_learn_complete(
        start_urls[0] if start_urls else "unknown",
        total_skills_learned,
        total_duration
    )
    
    await aprint(f"\n🎉 Exploration complete!")
    await aprint(f"📊 Total skills learned: {total_skills_learned}")
    await aprint(f"⏱️ Total time: {total_duration:.1f}s")
    
    return knowledge_base


def cli(
    start_url: str,
    output_dir: str,
    agent_lm_name: str = "claude-opus-4-5-20251124",
    iterations: int = 10,
    headless: bool = False,
    knowledge_base_path: Optional[str] = None,
):
    """命令行入口"""
    apply_patches()
    
    # 启动 WebSocket 服务器
    print("[SkillFlow] Starting WebSocket server...")
    start_server()
    
    import time
    time.sleep(1)
    
    lm = LM(agent_lm_name)
    
    if knowledge_base_path and os.path.exists(knowledge_base_path):
        knowledge_base = load_knowledge_base(knowledge_base_path)
        broadcast_kb_loaded(knowledge_base_path, len(knowledge_base.functions))
    else:
        knowledge_base = KnowledgeBase()
    
    asyncio.run(explore_with_ws(
        start_urls=[start_url],
        lm=lm,
        knowledge_base=knowledge_base,
        output_dir=output_dir,
        iterations=iterations,
        headless=headless,
    ))


if __name__ == "__main__":
    typer.run(cli)
