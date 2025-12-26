/**
 * NogicOS AI Overlay Layer
 * 使用 GSAP 实现 Atlas 级别的动画体验
 */

// GSAP 在 Electron 中通过 script 标签加载
// 如果需要在 Node 环境使用，需要特殊处理

// ========================================
// AI 光标组件 - GSAP 增强版
// ========================================
class AICursor {
    constructor() {
        this.element = null;
        this.labelElement = null;
        this.glowElement = null;
        this.rippleContainer = null;
        this.isVisible = false;
        this.currentX = 100;
        this.currentY = 100;
        this.timeline = null;
        this.init();
    }

    init() {
        // 创建光标容器
        this.element = document.createElement('div');
        this.element.className = 'ai-cursor';
        this.element.innerHTML = `
            <div class="ai-cursor-pointer">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                    <path d="M5.5 3.21V20.79C5.5 21.3 6.0 21.58 6.4 21.28L11.17 17.21L13.8 22.74C14.0 23.18 14.56 23.37 15.0 23.17L17.27 22.13C17.71 21.93 17.9 21.37 17.7 20.93L15.07 15.41L21.5 14.79C22.05 14.73 22.32 14.07 21.96 13.64L6.96 3.36C6.6 3.06 6.0 3.26 5.5 3.71Z" 
                          fill="url(#cursor-gradient)" stroke="rgba(255,255,255,0.8)" stroke-width="1.5"/>
                    <defs>
                        <linearGradient id="cursor-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" stop-color="#818cf8"/>
                            <stop offset="50%" stop-color="#6366f1"/>
                            <stop offset="100%" stop-color="#4f46e5"/>
                        </linearGradient>
                    </defs>
                </svg>
            </div>
            <div class="ai-cursor-glow"></div>
            <div class="ai-cursor-trail"></div>
        `;

        this.glowElement = this.element.querySelector('.ai-cursor-glow');

        // 创建涟漪容器（用于点击效果）
        this.rippleContainer = document.createElement('div');
        this.rippleContainer.className = 'ai-ripple-container';

        // 创建标签
        this.labelElement = document.createElement('div');
        this.labelElement.className = 'ai-cursor-label';
        this.labelElement.innerHTML = `<span class="label-dot"></span><span class="label-text">AI</span>`;

        document.body.appendChild(this.rippleContainer);
        document.body.appendChild(this.element);
        document.body.appendChild(this.labelElement);

        // 初始化 GSAP 动画
        this._initGSAP();
    }

    _initGSAP() {
        // 光晕呼吸动画
        if (typeof gsap !== 'undefined') {
            gsap.to(this.glowElement, {
                scale: 1.3,
                opacity: 0.3,
                duration: 1.5,
                repeat: -1,
                yoyo: true,
                ease: "sine.inOut"
            });
        }
    }

    show() {
        if (this.isVisible) return;
        this.isVisible = true;
        
        if (typeof gsap !== 'undefined') {
            gsap.to(this.element, {
                opacity: 1,
                scale: 1,
                duration: 0.4,
                ease: "back.out(1.7)"
            });
            gsap.to(this.labelElement, {
                opacity: 1,
                y: 0,
                duration: 0.3,
                delay: 0.1,
                ease: "power2.out"
            });
        } else {
            this.element.classList.add('visible');
            this.labelElement.classList.add('visible');
        }
    }

    hide() {
        if (!this.isVisible) return;
        this.isVisible = false;
        
        if (typeof gsap !== 'undefined') {
            gsap.to(this.element, {
                opacity: 0,
                scale: 0.5,
                duration: 0.3,
                ease: "power2.in"
            });
            gsap.to(this.labelElement, {
                opacity: 0,
                y: -10,
                duration: 0.2,
                ease: "power2.in"
            });
        } else {
            this.element.classList.remove('visible');
            this.labelElement.classList.remove('visible');
        }
    }

    async moveTo(x, y, duration = 0.8) {
        return new Promise(resolve => {
            this.show();
            
            if (typeof gsap !== 'undefined') {
                // 使用 GSAP 的贝塞尔曲线移动
                gsap.to(this.element, {
                    left: x,
                    top: y,
                    duration: duration,
                    ease: "power2.inOut",
                    onUpdate: () => {
                        // 同步更新标签位置
                        const rect = this.element.getBoundingClientRect();
                        gsap.set(this.labelElement, {
                            left: rect.left + 35,
                            top: rect.top + 5
                        });
                    },
                    onComplete: resolve
                });

                // 添加轻微的旋转和缩放效果
                gsap.to(this.element.querySelector('.ai-cursor-pointer'), {
                    rotation: 5,
                    scale: 1.1,
                    duration: duration * 0.3,
                    ease: "power1.out",
                    yoyo: true,
                    repeat: 1
                });
            } else {
                // CSS 回退
                this.element.style.transition = `left ${duration}s ease, top ${duration}s ease`;
                this.element.style.left = `${x}px`;
                this.element.style.top = `${y}px`;
                this.labelElement.style.left = `${x + 35}px`;
                this.labelElement.style.top = `${y + 5}px`;
                setTimeout(resolve, duration * 1000);
            }
            
            this.currentX = x;
            this.currentY = y;
        });
    }

    click() {
        // 创建涟漪效果
        this._createRipple(this.currentX, this.currentY);
        
        if (typeof gsap !== 'undefined') {
            // 光标按下弹跳效果
            gsap.timeline()
                .to(this.element, {
                    scale: 0.85,
                    duration: 0.1,
                    ease: "power2.in"
                })
                .to(this.element, {
                    scale: 1,
                    duration: 0.3,
                    ease: "elastic.out(1, 0.5)"
                });

            // 光晕爆发
            gsap.timeline()
                .to(this.glowElement, {
                    scale: 2,
                    opacity: 0.8,
                    duration: 0.15,
                    ease: "power2.out"
                })
                .to(this.glowElement, {
                    scale: 1.3,
                    opacity: 0.3,
                    duration: 0.4,
                    ease: "power2.inOut"
                });
        }
    }

    _createRipple(x, y) {
        const ripple = document.createElement('div');
        ripple.className = 'ai-click-ripple';
        ripple.style.left = `${x}px`;
        ripple.style.top = `${y}px`;
        this.rippleContainer.appendChild(ripple);

        if (typeof gsap !== 'undefined') {
            gsap.timeline()
                .fromTo(ripple, 
                    { scale: 0, opacity: 1 },
                    { scale: 3, opacity: 0, duration: 0.6, ease: "power2.out" }
                )
                .then(() => ripple.remove());
        } else {
            ripple.classList.add('active');
            setTimeout(() => ripple.remove(), 600);
        }
    }

    type() {
        this.setLabel('输入中...');
        if (typeof gsap !== 'undefined') {
            gsap.to(this.element.querySelector('.ai-cursor-pointer'), {
                y: -3,
                duration: 0.15,
                repeat: -1,
                yoyo: true,
                ease: "sine.inOut"
            });
        }
    }

    stopType() {
        this.setLabel('AI');
        if (typeof gsap !== 'undefined') {
            gsap.killTweensOf(this.element.querySelector('.ai-cursor-pointer'));
            gsap.to(this.element.querySelector('.ai-cursor-pointer'), {
                y: 0,
                duration: 0.2
            });
        }
    }

    setLabel(text) {
        this.labelElement.querySelector('.label-text').textContent = text;
    }
}


// ========================================
// 元素高亮组件 - GSAP 增强版
// ========================================
class ElementHighlight {
    constructor() {
        this.element = null;
        this.labelElement = null;
        this.init();
    }

    init() {
        this.element = document.createElement('div');
        this.element.className = 'ai-highlight';
        
        this.labelElement = document.createElement('div');
        this.labelElement.className = 'ai-highlight-label';
        
        document.body.appendChild(this.element);
        document.body.appendChild(this.labelElement);
    }

    highlight(rect, label = '') {
        if (!rect) {
            this.hide();
            return;
        }

        if (typeof gsap !== 'undefined') {
            gsap.to(this.element, {
                left: rect.x - 4,
                top: rect.y - 4,
                width: rect.width + 8,
                height: rect.height + 8,
                opacity: 1,
                duration: 0.3,
                ease: "power2.out"
            });

            // 脉冲动画
            gsap.to(this.element, {
                boxShadow: "0 0 0 8px rgba(99, 102, 241, 0.2), 0 0 40px rgba(99, 102, 241, 0.5)",
                duration: 0.8,
                repeat: -1,
                yoyo: true,
                ease: "sine.inOut"
            });
        } else {
            this.element.style.left = `${rect.x - 4}px`;
            this.element.style.top = `${rect.y - 4}px`;
            this.element.style.width = `${rect.width + 8}px`;
            this.element.style.height = `${rect.height + 8}px`;
            this.element.classList.add('visible');
        }

        if (label) {
            this.labelElement.textContent = label;
            this.labelElement.style.left = `${rect.x}px`;
            this.labelElement.style.top = `${rect.y - 30}px`;
            
            if (typeof gsap !== 'undefined') {
                gsap.to(this.labelElement, {
                    opacity: 1,
                    y: 0,
                    duration: 0.2,
                    ease: "power2.out"
                });
            } else {
                this.labelElement.classList.add('visible');
            }
        }
    }

    hide() {
        if (typeof gsap !== 'undefined') {
            gsap.killTweensOf(this.element);
            gsap.to(this.element, {
                opacity: 0,
                duration: 0.2,
                ease: "power2.in"
            });
            gsap.to(this.labelElement, {
                opacity: 0,
                y: -10,
                duration: 0.15
            });
        } else {
            this.element.classList.remove('visible');
            this.labelElement.classList.remove('visible');
        }
    }
}


// ========================================
// 屏幕边缘光效 - GSAP 增强版
// ========================================
class ScreenGlow {
    constructor() {
        this.element = null;
        this.cornerElements = [];
        this.breatheAnimation = null;
        this.init();
    }

    init() {
        this.element = document.createElement('div');
        this.element.className = 'screen-glow';
        
        // 创建四角光效
        ['top-left', 'top-right', 'bottom-left', 'bottom-right'].forEach(pos => {
            const corner = document.createElement('div');
            corner.className = `screen-glow-corner ${pos}`;
            this.element.appendChild(corner);
            this.cornerElements.push(corner);
        });

        document.body.appendChild(this.element);
    }

    start(intensity = 'medium') {
        this.element.classList.add('active');
        
        const intensityMap = {
            low: { blur: 80, opacity: 0.15 },
            medium: { blur: 120, opacity: 0.25 },
            high: { blur: 180, opacity: 0.4 }
        };
        
        const config = intensityMap[intensity] || intensityMap.medium;

        if (typeof gsap !== 'undefined') {
            // 四角呼吸动画
            this.breatheAnimation = gsap.timeline({ repeat: -1, yoyo: true })
                .to(this.cornerElements, {
                    opacity: config.opacity * 1.5,
                    scale: 1.1,
                    duration: 2,
                    stagger: 0.2,
                    ease: "sine.inOut"
                });
        }
    }

    stop() {
        if (this.breatheAnimation) {
            this.breatheAnimation.kill();
        }
        
        if (typeof gsap !== 'undefined') {
            gsap.to(this.element, {
                opacity: 0,
                duration: 0.5,
                onComplete: () => this.element.classList.remove('active')
            });
        } else {
            this.element.classList.remove('active');
        }
    }

    pulse(color = '#6366f1') {
        this.element.style.setProperty('--glow-color', color);
        
        if (typeof gsap !== 'undefined') {
            gsap.timeline()
                .to(this.element, {
                    opacity: 1,
                    duration: 0.1
                })
                .to(this.cornerElements, {
                    opacity: 0.8,
                    scale: 1.3,
                    duration: 0.2,
                    ease: "power2.out"
                })
                .to(this.cornerElements, {
                    opacity: 0.2,
                    scale: 1,
                    duration: 0.4,
                    ease: "power2.inOut"
                });
        }
    }

    success() {
        this.pulse('#10b981');
        // 添加绿色闪烁
        if (typeof gsap !== 'undefined') {
            gsap.to(this.element, {
                boxShadow: 'inset 0 0 150px rgba(16, 185, 129, 0.4)',
                duration: 0.2,
                yoyo: true,
                repeat: 1
            });
        }
    }

    error() {
        this.pulse('#ef4444');
        // 添加红色闪烁
        if (typeof gsap !== 'undefined') {
            gsap.to(this.element, {
                boxShadow: 'inset 0 0 150px rgba(239, 68, 68, 0.4)',
                duration: 0.15,
                yoyo: true,
                repeat: 2
            });
        }
    }
}


// ========================================
// 步骤进度指示器
// ========================================
class StepProgress {
    constructor() {
        this.element = null;
        this.steps = [];
        this.maxSteps = 0;
        this.init();
    }

    init() {
        this.element = document.createElement('div');
        this.element.className = 'ai-step-progress';
        document.body.appendChild(this.element);
    }

    setMaxSteps(max) {
        this.maxSteps = max;
        this.element.innerHTML = '';
        this.steps = [];
        
        for (let i = 0; i < max; i++) {
            const step = document.createElement('div');
            step.className = 'step';
            this.element.appendChild(step);
            this.steps.push(step);
        }
    }

    show() {
        if (typeof gsap !== 'undefined') {
            gsap.to(this.element, {
                opacity: 1,
                y: 0,
                duration: 0.3,
                ease: "power2.out"
            });
        } else {
            this.element.classList.add('visible');
        }
    }

    hide() {
        if (typeof gsap !== 'undefined') {
            gsap.to(this.element, {
                opacity: 0,
                y: 20,
                duration: 0.2,
                ease: "power2.in"
            });
        } else {
            this.element.classList.remove('visible');
        }
    }

    setActive(stepIndex) {
        this.steps.forEach((step, i) => {
            step.classList.remove('active', 'completed', 'error');
            if (i < stepIndex) {
                step.classList.add('completed');
            } else if (i === stepIndex) {
                step.classList.add('active');
                if (typeof gsap !== 'undefined') {
                    gsap.fromTo(step, 
                        { scale: 0.8 },
                        { scale: 1, duration: 0.3, ease: "back.out(2)" }
                    );
                }
            }
        });
    }

    setCompleted(stepIndex, success = true) {
        if (this.steps[stepIndex]) {
            this.steps[stepIndex].classList.remove('active');
            this.steps[stepIndex].classList.add(success ? 'completed' : 'error');
        }
    }
}


// ========================================
// AI Overlay 主控制器
// ========================================
class AIOverlay {
    constructor() {
        this.cursor = new AICursor();
        this.highlight = new ElementHighlight();
        this.screenGlow = new ScreenGlow();
        this.stepProgress = new StepProgress();
        this.isActive = false;
        
        console.log('[NogicOS] AI Overlay initialized with GSAP');
    }

    activate() {
        this.isActive = true;
        this.screenGlow.start('low');
        console.log('[AIOverlay] Activated');
    }

    deactivate() {
        this.isActive = false;
        this.cursor.hide();
        this.highlight.hide();
        this.screenGlow.stop();
        this.stepProgress.hide();
        console.log('[AIOverlay] Deactivated');
    }

    // 处理 WebSocket 消息
    handleMessage(message) {
        const { type, data } = message;

        switch (type) {
            case 'cursor_move':
                this.cursor.moveTo(data.x, data.y, data.duration || 0.8);
                break;

            case 'cursor_click':
                this.cursor.click();
                break;

            case 'cursor_type':
                this.cursor.type();
                break;

            case 'cursor_stop_type':
                this.cursor.stopType();
                break;

            case 'highlight':
                this.highlight.highlight(data.rect, data.label);
                break;

            case 'highlight_hide':
                this.highlight.hide();
                break;

            case 'screen_glow':
                this.screenGlow.start(data.intensity || 'medium');
                break;

            case 'screen_glow_stop':
                this.screenGlow.stop();
                break;

            case 'screen_pulse':
                this.screenGlow.pulse(data.color);
                break;

            case 'task_start':
                this.activate();
                if (data.max_steps) {
                    this.stepProgress.setMaxSteps(data.max_steps);
                    this.stepProgress.show();
                }
                break;

            case 'step_start':
                this.stepProgress.setActive(data.step);
                this.screenGlow.start('medium');
                break;

            case 'step_complete':
                this.stepProgress.setCompleted(data.step, data.success !== false);
                break;

            case 'task_complete':
                this.screenGlow.success();
                setTimeout(() => this.deactivate(), 2000);
                break;

            case 'task_error':
                this.screenGlow.error();
                setTimeout(() => this.deactivate(), 2000);
                break;

            default:
                break;
        }
    }

    // 测试动画效果
    async demo() {
        console.log('[AIOverlay] Starting demo...');
        this.activate();
        
        // 移动光标
        await this.cursor.moveTo(200, 200, 0.8);
        await new Promise(r => setTimeout(r, 500));
        
        // 高亮元素
        this.highlight.highlight({ x: 180, y: 180, width: 100, height: 40 }, '目标元素');
        await new Promise(r => setTimeout(r, 800));
        
        // 点击
        this.cursor.click();
        await new Promise(r => setTimeout(r, 500));
        
        // 移动到另一个位置
        this.highlight.hide();
        await this.cursor.moveTo(500, 300, 1);
        
        // 输入
        this.cursor.type();
        await new Promise(r => setTimeout(r, 2000));
        this.cursor.stopType();
        
        // 成功效果
        this.screenGlow.success();
        
        await new Promise(r => setTimeout(r, 2000));
        this.deactivate();
        console.log('[AIOverlay] Demo complete');
    }
}


// 加载 GSAP
(function loadGSAP() {
    if (typeof gsap === 'undefined') {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js';
        script.onload = () => {
            console.log('[NogicOS] GSAP loaded successfully');
            window.aiOverlay = new AIOverlay();
        };
        script.onerror = () => {
            console.warn('[NogicOS] GSAP failed to load, using CSS fallback');
            window.aiOverlay = new AIOverlay();
        };
        document.head.appendChild(script);
    } else {
        window.aiOverlay = new AIOverlay();
    }
})();

