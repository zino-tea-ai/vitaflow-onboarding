"""
NogicOS Visual Feedback Module

使用 Motion 库实现顶级动效：
- Spring 边角高亮
- 点击涟漪效果
- 学习通知

通过 Playwright page.evaluate() 注入 JavaScript 实现
"""

import asyncio
import logging
from typing import Optional, Tuple
from playwright.async_api import Page

logger = logging.getLogger(__name__)


# Motion CDN URL (ESM module)
MOTION_CDN = "https://cdn.jsdelivr.net/npm/motion@12/+esm"

# NogicOS 品牌颜色
BRAND_GREEN = "#22c55e"
BRAND_BLUE = "#3b82f6"


class VisualFeedback:
    """
    AI 操作可视化反馈
    
    在目标页面注入 Motion 动效，让用户看到 AI 的每一步操作
    """
    
    def __init__(self, color: str = BRAND_GREEN):
        self.color = color
        self._motion_injected = False
    
    async def inject_motion(self, page: Page) -> bool:
        """
        注入 Motion 库到页面
        
        Returns:
            bool: 是否注入成功
        """
        if self._motion_injected:
            return True
            
        try:
            # 检查是否已经注入
            already_injected = await page.evaluate("""
                () => typeof window.__nogicMotion !== 'undefined'
            """)
            
            if already_injected:
                self._motion_injected = True
                return True
            
            # 注入 Motion 库（通过动态创建 script）
            await page.evaluate(f"""
                () => {{
                    return new Promise((resolve, reject) => {{
                        // 标记已注入
                        window.__nogicMotion = true;
                        
                        // 创建 script 标签
                        const script = document.createElement('script');
                        script.type = 'module';
                        script.textContent = `
                            import {{ animate, spring }} from "{MOTION_CDN}";
                            window.motionAnimate = animate;
                            window.motionSpring = spring;
                            window.__motionReady = true;
                        `;
                        document.head.appendChild(script);
                        
                        // 等待加载完成
                        let attempts = 0;
                        const check = setInterval(() => {{
                            attempts++;
                            if (window.__motionReady) {{
                                clearInterval(check);
                                resolve(true);
                            }} else if (attempts > 50) {{
                                clearInterval(check);
                                // 即使 Motion 加载失败，也提供 fallback
                                window.motionAnimate = null;
                                resolve(false);
                            }}
                        }}, 100);
                    }});
                }}
            """)
            
            self._motion_injected = True
            logger.debug("[Visual] Motion library injected")
            return True
            
        except Exception as e:
            logger.warning(f"[Visual] Failed to inject Motion: {e}")
            return False
    
    async def highlight_element(
        self, 
        page: Page, 
        selector: str,
        duration: float = 0.5,
        color: Optional[str] = None
    ) -> bool:
        """
        高亮目标元素 - Spring 边角动画
        
        4 个边角从外向内 Spring 飞入，形成聚焦框
        
        Args:
            page: Playwright Page 对象
            selector: CSS 选择器
            duration: 动画持续时间（秒）
            color: 高亮颜色，默认品牌绿
            
        Returns:
            bool: 是否成功显示
        """
        color = color or self.color
        
        try:
            await self.inject_motion(page)
            
            result = await page.evaluate(f"""
                (selector) => {{
                    const el = document.querySelector(selector);
                    if (!el) return {{ success: false, reason: 'element not found' }};
                    
                    const rect = el.getBoundingClientRect();
                    const scrollX = window.scrollX;
                    const scrollY = window.scrollY;
                    
                    // 边角尺寸
                    const cornerSize = 20;
                    const cornerThickness = 3;
                    const color = '{color}';
                    const offset = 8; // 距离元素的偏移
                    
                    // 创建容器
                    const container = document.createElement('div');
                    container.className = 'nogic-highlight';
                    container.style.cssText = `
                        position: absolute;
                        top: ${{rect.top + scrollY - offset}}px;
                        left: ${{rect.left + scrollX - offset}}px;
                        width: ${{rect.width + offset * 2}}px;
                        height: ${{rect.height + offset * 2}}px;
                        pointer-events: none;
                        z-index: 2147483647;
                    `;
                    
                    // 4 个边角位置配置
                    const corners = [
                        {{ name: 'top-left', x: 0, y: 0, rotate: 0, fromX: -30, fromY: -30 }},
                        {{ name: 'top-right', x: 'calc(100% - {cornerSize}px)', y: 0, rotate: 90, fromX: 30, fromY: -30 }},
                        {{ name: 'bottom-right', x: 'calc(100% - {cornerSize}px)', y: 'calc(100% - {cornerSize}px)', rotate: 180, fromX: 30, fromY: 30 }},
                        {{ name: 'bottom-left', x: 0, y: 'calc(100% - {cornerSize}px)', rotate: 270, fromX: -30, fromY: 30 }}
                    ];
                    
                    corners.forEach((corner, i) => {{
                        const el = document.createElement('div');
                        el.className = 'nogic-corner nogic-corner-' + corner.name;
                        el.style.cssText = `
                            position: absolute;
                            left: ${{corner.x}};
                            top: ${{corner.y}};
                            width: {cornerSize}px;
                            height: {cornerSize}px;
                            opacity: 0;
                            transform: translate(${{corner.fromX}}px, ${{corner.fromY}}px);
                        `;
                        
                        // L 形边角（使用两个 div）
                        el.innerHTML = `
                            <div style="
                                position: absolute;
                                background: ${{color}};
                                ${{corner.name.includes('left') ? 'left: 0' : 'right: 0'}};
                                ${{corner.name.includes('top') ? 'top: 0' : 'bottom: 0'}};
                                width: {cornerThickness}px;
                                height: {cornerSize}px;
                            "></div>
                            <div style="
                                position: absolute;
                                background: ${{color}};
                                ${{corner.name.includes('left') ? 'left: 0' : 'right: 0'}};
                                ${{corner.name.includes('top') ? 'top: 0' : 'bottom: 0'}};
                                width: {cornerSize}px;
                                height: {cornerThickness}px;
                            "></div>
                        `;
                        
                        container.appendChild(el);
                    }});
                    
                    document.body.appendChild(container);
                    
                    // 执行动画
                    if (window.motionAnimate) {{
                        // 使用 Motion Spring
                        const cornerEls = container.querySelectorAll('.nogic-corner');
                        cornerEls.forEach((el, i) => {{
                            window.motionAnimate(
                                el,
                                {{ 
                                    opacity: [0, 1, 1, 0], 
                                    transform: ['translate(var(--from-x, 0), var(--from-y, 0))', 'translate(0, 0)', 'translate(0, 0)', 'translate(0, 0)']
                                }},
                                {{ 
                                    duration: {duration + 0.3},
                                    easing: window.motionSpring({{ stiffness: 500, damping: 25 }})
                                }}
                            );
                        }});
                        
                        // 移除容器
                        setTimeout(() => container.remove(), {int((duration + 0.3) * 1000)});
                    }} else {{
                        // Fallback: CSS 动画
                        const style = document.createElement('style');
                        style.textContent = `
                            @keyframes nogicCornerIn {{
                                0% {{ opacity: 0; transform: translate(var(--from-x), var(--from-y)); }}
                                30% {{ opacity: 1; transform: translate(0, 0); }}
                                70% {{ opacity: 1; transform: translate(0, 0); }}
                                100% {{ opacity: 0; transform: translate(0, 0); }}
                            }}
                            .nogic-corner {{
                                animation: nogicCornerIn {duration + 0.3}s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
                            }}
                            .nogic-corner-top-left {{ --from-x: -30px; --from-y: -30px; }}
                            .nogic-corner-top-right {{ --from-x: 30px; --from-y: -30px; }}
                            .nogic-corner-bottom-right {{ --from-x: 30px; --from-y: 30px; }}
                            .nogic-corner-bottom-left {{ --from-x: -30px; --from-y: 30px; }}
                        `;
                        document.head.appendChild(style);
                        
                        setTimeout(() => {{
                            container.remove();
                            style.remove();
                        }}, {int((duration + 0.3) * 1000)});
                    }}
                    
                    return {{ success: true, rect: {{ x: rect.x, y: rect.y, width: rect.width, height: rect.height }} }};
                }}
            """, selector)
            
            if result.get('success'):
                logger.debug(f"[Visual] Highlighted element: {selector}")
                return True
            else:
                logger.warning(f"[Visual] Failed to highlight: {result.get('reason')}")
                return False
                
        except Exception as e:
            logger.warning(f"[Visual] Highlight error: {e}")
            return False
    
    async def show_click(
        self, 
        page: Page, 
        x: float, 
        y: float,
        color: Optional[str] = None
    ) -> bool:
        """
        显示点击涟漪效果
        
        3 层动画叠加：
        1. 中心点 - 缩放入场
        2. 外圈 - 扩散淡出
        3. 涟漪波 - 多次扩散
        
        Args:
            page: Playwright Page 对象
            x: 点击 X 坐标（相对视口）
            y: 点击 Y 坐标（相对视口）
            color: 涟漪颜色
            
        Returns:
            bool: 是否成功显示
        """
        color = color or self.color
        
        try:
            await self.inject_motion(page)
            
            await page.evaluate(f"""
                (x, y) => {{
                    const scrollX = window.scrollX;
                    const scrollY = window.scrollY;
                    const color = '{color}';
                    
                    // 创建容器
                    const container = document.createElement('div');
                    container.className = 'nogic-click';
                    container.style.cssText = `
                        position: absolute;
                        top: ${{y + scrollY}}px;
                        left: ${{x + scrollX}}px;
                        pointer-events: none;
                        z-index: 2147483647;
                    `;
                    
                    // 1. 中心点
                    const center = document.createElement('div');
                    center.style.cssText = `
                        position: absolute;
                        width: 12px;
                        height: 12px;
                        background: ${{color}};
                        border-radius: 50%;
                        transform: translate(-50%, -50%) scale(0);
                        box-shadow: 0 0 10px ${{color}};
                    `;
                    container.appendChild(center);
                    
                    // 2. 外圈
                    const outer = document.createElement('div');
                    outer.style.cssText = `
                        position: absolute;
                        width: 40px;
                        height: 40px;
                        border: 2px solid ${{color}};
                        border-radius: 50%;
                        transform: translate(-50%, -50%) scale(0.3);
                        opacity: 1;
                    `;
                    container.appendChild(outer);
                    
                    // 3. 涟漪波
                    const ripple = document.createElement('div');
                    ripple.style.cssText = `
                        position: absolute;
                        width: 80px;
                        height: 80px;
                        border: 1px solid ${{color}};
                        border-radius: 50%;
                        transform: translate(-50%, -50%) scale(0.2);
                        opacity: 0.6;
                    `;
                    container.appendChild(ripple);
                    
                    document.body.appendChild(container);
                    
                    // 执行动画
                    if (window.motionAnimate) {{
                        // 中心点 Spring 缩放
                        window.motionAnimate(
                            center,
                            {{ transform: ['translate(-50%, -50%) scale(0)', 'translate(-50%, -50%) scale(1.2)', 'translate(-50%, -50%) scale(1)'] }},
                            {{ duration: 0.3, easing: window.motionSpring({{ stiffness: 600, damping: 20 }}) }}
                        );
                        
                        // 外圈扩散
                        window.motionAnimate(
                            outer,
                            {{ transform: ['translate(-50%, -50%) scale(0.3)', 'translate(-50%, -50%) scale(1.5)'], opacity: [1, 0] }},
                            {{ duration: 0.5, easing: 'ease-out' }}
                        );
                        
                        // 涟漪波
                        window.motionAnimate(
                            ripple,
                            {{ transform: ['translate(-50%, -50%) scale(0.2)', 'translate(-50%, -50%) scale(2)'], opacity: [0.6, 0] }},
                            {{ duration: 0.7, easing: 'ease-out' }}
                        );
                    }} else {{
                        // Fallback: CSS 动画
                        const style = document.createElement('style');
                        style.textContent = `
                            @keyframes nogicCenterPop {{
                                0% {{ transform: translate(-50%, -50%) scale(0); }}
                                50% {{ transform: translate(-50%, -50%) scale(1.2); }}
                                100% {{ transform: translate(-50%, -50%) scale(1); }}
                            }}
                            @keyframes nogicOuterExpand {{
                                0% {{ transform: translate(-50%, -50%) scale(0.3); opacity: 1; }}
                                100% {{ transform: translate(-50%, -50%) scale(1.5); opacity: 0; }}
                            }}
                            @keyframes nogicRipple {{
                                0% {{ transform: translate(-50%, -50%) scale(0.2); opacity: 0.6; }}
                                100% {{ transform: translate(-50%, -50%) scale(2); opacity: 0; }}
                            }}
                        `;
                        document.head.appendChild(style);
                        
                        center.style.animation = 'nogicCenterPop 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards';
                        outer.style.animation = 'nogicOuterExpand 0.5s ease-out forwards';
                        ripple.style.animation = 'nogicRipple 0.7s ease-out forwards';
                        
                        setTimeout(() => style.remove(), 1000);
                    }}
                    
                    // 移除容器
                    setTimeout(() => container.remove(), 800);
                }}
            """, x, y)
            
            logger.debug(f"[Visual] Click effect at ({x}, {y})")
            return True
            
        except Exception as e:
            logger.warning(f"[Visual] Click effect error: {e}")
            return False
    
    async def show_typing(
        self, 
        page: Page, 
        selector: str,
        text: str,
        color: Optional[str] = None
    ) -> bool:
        """
        显示输入指示器
        
        在输入框旁边显示正在输入的文字预览
        
        Args:
            page: Playwright Page 对象
            selector: 输入框选择器
            text: 正在输入的文字
            color: 指示器颜色
        """
        color = color or BRAND_BLUE
        
        try:
            await page.evaluate(f"""
                (selector, text) => {{
                    const el = document.querySelector(selector);
                    if (!el) return;
                    
                    const rect = el.getBoundingClientRect();
                    const scrollX = window.scrollX;
                    const scrollY = window.scrollY;
                    
                    // 移除旧的指示器
                    const old = document.querySelector('.nogic-typing');
                    if (old) old.remove();
                    
                    // 创建指示器
                    const indicator = document.createElement('div');
                    indicator.className = 'nogic-typing';
                    indicator.style.cssText = `
                        position: absolute;
                        top: ${{rect.bottom + scrollY + 4}}px;
                        left: ${{rect.left + scrollX}}px;
                        background: rgba(0, 0, 0, 0.8);
                        border: 1px solid {color};
                        border-radius: 4px;
                        padding: 4px 8px;
                        font-size: 12px;
                        color: #fff;
                        pointer-events: none;
                        z-index: 2147483647;
                        max-width: 300px;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                    `;
                    indicator.innerHTML = `
                        <span style="color: {color}; margin-right: 4px;">AI:</span>
                        <span>${{text.substring(0, 50)}}${{text.length > 50 ? '...' : ''}}</span>
                    `;
                    
                    document.body.appendChild(indicator);
                    
                    // 3 秒后移除
                    setTimeout(() => indicator.remove(), 3000);
                }}
            """, selector, text)
            
            return True
            
        except Exception as e:
            logger.warning(f"[Visual] Typing indicator error: {e}")
            return False
    
    async def show_notification(
        self,
        page: Page,
        message: str,
        type: str = "success"  # success, info, warning, error
    ) -> bool:
        """
        显示通知（右下角）
        
        用于显示学习完成、技能合成等事件
        """
        colors = {
            "success": BRAND_GREEN,
            "info": BRAND_BLUE,
            "warning": "#eab308",
            "error": "#ef4444"
        }
        color = colors.get(type, BRAND_GREEN)
        
        try:
            await page.evaluate(f"""
                (message, color) => {{
                    // 创建通知
                    const notification = document.createElement('div');
                    notification.className = 'nogic-notification';
                    notification.style.cssText = `
                        position: fixed;
                        bottom: 20px;
                        right: 20px;
                        background: rgba(0, 0, 0, 0.9);
                        border: 1px solid ${{color}};
                        border-radius: 8px;
                        padding: 12px 16px;
                        font-size: 13px;
                        color: #fff;
                        pointer-events: none;
                        z-index: 2147483647;
                        max-width: 300px;
                        transform: translateX(120%);
                        transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
                        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                    `;
                    notification.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div style="width: 8px; height: 8px; background: ${{color}}; border-radius: 50%;"></div>
                            <span>${{message}}</span>
                        </div>
                    `;
                    
                    document.body.appendChild(notification);
                    
                    // 入场动画
                    requestAnimationFrame(() => {{
                        notification.style.transform = 'translateX(0)';
                    }});
                    
                    // 3 秒后退出
                    setTimeout(() => {{
                        notification.style.transform = 'translateX(120%)';
                        setTimeout(() => notification.remove(), 300);
                    }}, 3000);
                }}
            """, message, color)
            
            logger.debug(f"[Visual] Notification: {message}")
            return True
            
        except Exception as e:
            logger.warning(f"[Visual] Notification error: {e}")
            return False
    
    async def highlight_by_coordinates(
        self,
        page: Page,
        x: float,
        y: float,
        width: float = 100,
        height: float = 40,
        color: Optional[str] = None
    ) -> bool:
        """
        通过坐标高亮区域（当没有选择器时）
        """
        color = color or self.color
        
        try:
            await self.inject_motion(page)
            
            await page.evaluate(f"""
                (x, y, width, height) => {{
                    const scrollX = window.scrollX;
                    const scrollY = window.scrollY;
                    const color = '{color}';
                    
                    // 创建高亮框
                    const box = document.createElement('div');
                    box.className = 'nogic-coord-highlight';
                    box.style.cssText = `
                        position: absolute;
                        top: ${{y + scrollY - 4}}px;
                        left: ${{x + scrollX - 4}}px;
                        width: ${{width + 8}}px;
                        height: ${{height + 8}}px;
                        border: 2px solid ${{color}};
                        border-radius: 4px;
                        pointer-events: none;
                        z-index: 2147483647;
                        opacity: 0;
                        transform: scale(1.1);
                    `;
                    
                    document.body.appendChild(box);
                    
                    if (window.motionAnimate) {{
                        window.motionAnimate(
                            box,
                            {{ opacity: [0, 1, 1, 0], transform: ['scale(1.1)', 'scale(1)', 'scale(1)', 'scale(0.95)'] }},
                            {{ duration: 0.8, easing: 'ease-out' }}
                        );
                    }} else {{
                        box.style.transition = 'all 0.3s ease-out';
                        box.style.opacity = '1';
                        box.style.transform = 'scale(1)';
                        setTimeout(() => {{
                            box.style.opacity = '0';
                        }}, 500);
                    }}
                    
                    setTimeout(() => box.remove(), 800);
                }}
            """, x, y, width, height)
            
            return True
            
        except Exception as e:
            logger.warning(f"[Visual] Coordinate highlight error: {e}")
            return False
    
    def reset(self):
        """重置状态（页面导航后调用）"""
        self._motion_injected = False


# 单例实例
visual_feedback = VisualFeedback()

