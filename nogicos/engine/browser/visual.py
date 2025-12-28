"""
NogicOS Visual Feedback Module

Premium animations using Motion library:
- Spring corner highlight
- Click ripple effects
- Learning notifications

Implemented via Playwright page.evaluate() JavaScript injection
"""

import asyncio
import logging
from typing import Optional, Tuple
from playwright.async_api import Page

logger = logging.getLogger(__name__)


# Motion CDN URL (ESM module)
MOTION_CDN = "https://cdn.jsdelivr.net/npm/motion@12/+esm"

# NogicOS brand colors
BRAND_GREEN = "#22c55e"
BRAND_BLUE = "#3b82f6"


class VisualFeedback:
    """
    AI operation visual feedback
    
    Injects Motion animations into target page to show users each AI action
    """
    
    def __init__(self, color: str = BRAND_GREEN):
        self.color = color
        self._motion_injected = False
    
    async def inject_motion(self, page: Page) -> bool:
        """
        Inject Motion library into page
        
        Returns:
            bool: Whether injection succeeded
        """
        if self._motion_injected:
            return True
            
        try:
            # Check if already injected
            already_injected = await page.evaluate("""
                () => typeof window.__nogicMotion !== 'undefined'
            """)
            
            if already_injected:
                self._motion_injected = True
                return True
            
            # Inject Motion library (via dynamic script creation)
            await page.evaluate(f"""
                () => {{
                    return new Promise((resolve, reject) => {{
                        // Mark as injected
                        window.__nogicMotion = true;
                        
                        // Create script tag
                        const script = document.createElement('script');
                        script.type = 'module';
                        script.textContent = `
                            import {{ animate, spring }} from "{MOTION_CDN}";
                            window.motionAnimate = animate;
                            window.motionSpring = spring;
                            window.__motionReady = true;
                        `;
                        document.head.appendChild(script);
                        
                        // Wait for load completion
                        let attempts = 0;
                        const check = setInterval(() => {{
                            attempts++;
                            if (window.__motionReady) {{
                                clearInterval(check);
                                resolve(true);
                            }} else if (attempts > 50) {{
                                clearInterval(check);
                                // Even if Motion fails to load, provide fallback
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
        Highlight target element - Spring corner animation
        
        4 corners spring in from outside, forming a focus frame
        
        Args:
            page: Playwright Page object
            selector: CSS selector
            duration: Animation duration (seconds)
            color: Highlight color, defaults to brand green
            
        Returns:
            bool: Whether display succeeded
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
                    
                    // Corner dimensions
                    const cornerSize = 20;
                    const cornerThickness = 3;
                    const color = '{color}';
                    const offset = 8; // Offset from element
                    
                    // Create container
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
                    
                    // 4 corner position configs
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
                        
                        // L-shaped corner (using two divs)
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
                    
                    // Execute animation
                    if (window.motionAnimate) {{
                        // Use Motion Spring
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
                        
                        // Remove container
                        setTimeout(() => container.remove(), {int((duration + 0.3) * 1000)});
                    }} else {{
                        // Fallback: CSS animation
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
        Show click ripple effect
        
        3-layer animation overlay:
        1. Center point - scale entrance
        2. Outer ring - expanding fade out
        3. Ripple wave - multiple expansions
        
        Args:
            page: Playwright Page object
            x: Click X coordinate (relative to viewport)
            y: Click Y coordinate (relative to viewport)
            color: Ripple color
            
        Returns:
            bool: Whether display succeeded
        """
        color = color or self.color
        
        try:
            await self.inject_motion(page)
            
            await page.evaluate(f"""
                (x, y) => {{
                    const scrollX = window.scrollX;
                    const scrollY = window.scrollY;
                    const color = '{color}';
                    
                    // Create container
                    const container = document.createElement('div');
                    container.className = 'nogic-click';
                    container.style.cssText = `
                        position: absolute;
                        top: ${{y + scrollY}}px;
                        left: ${{x + scrollX}}px;
                        pointer-events: none;
                        z-index: 2147483647;
                    `;
                    
                    // 1. Center point
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
                    
                    // 2. Outer ring
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
                    
                    // 3. Ripple wave
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
                    
                    // Execute animation
                    if (window.motionAnimate) {{
                        // Center point Spring scale
                        window.motionAnimate(
                            center,
                            {{ transform: ['translate(-50%, -50%) scale(0)', 'translate(-50%, -50%) scale(1.2)', 'translate(-50%, -50%) scale(1)'] }},
                            {{ duration: 0.3, easing: window.motionSpring({{ stiffness: 600, damping: 20 }}) }}
                        );
                        
                        // Outer ring expansion
                        window.motionAnimate(
                            outer,
                            {{ transform: ['translate(-50%, -50%) scale(0.3)', 'translate(-50%, -50%) scale(1.5)'], opacity: [1, 0] }},
                            {{ duration: 0.5, easing: 'ease-out' }}
                        );
                        
                        // Ripple wave
                        window.motionAnimate(
                            ripple,
                            {{ transform: ['translate(-50%, -50%) scale(0.2)', 'translate(-50%, -50%) scale(2)'], opacity: [0.6, 0] }},
                            {{ duration: 0.7, easing: 'ease-out' }}
                        );
                    }} else {{
                        // Fallback: CSS animation
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
                    
                    // Remove container
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
        Show typing indicator
        
        Display text preview next to input field
        
        Args:
            page: Playwright Page object
            selector: Input field selector
            text: Text being typed
            color: Indicator color
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
                    
                    // Remove old indicator
                    const old = document.querySelector('.nogic-typing');
                    if (old) old.remove();
                    
                    // Create indicator
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
                    
                    // Remove after 3 seconds
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
        Show notification (bottom right)
        
        Used for learning complete, skill synthesis events
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
                    // Create notification
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
                    
                    // Entrance animation
                    requestAnimationFrame(() => {{
                        notification.style.transform = 'translateX(0)';
                    }});
                    
                    // Exit after 3 seconds
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
        Highlight area by coordinates (when no selector available)
        """
        color = color or self.color
        
        try:
            await self.inject_motion(page)
            
            await page.evaluate(f"""
                (x, y, width, height) => {{
                    const scrollX = window.scrollX;
                    const scrollY = window.scrollY;
                    const color = '{color}';
                    
                    // Create highlight box
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
        """Reset state (call after page navigation)"""
        self._motion_injected = False


# Singleton instance
visual_feedback = VisualFeedback()
