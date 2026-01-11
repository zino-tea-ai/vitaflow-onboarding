// VitaFlow V5 Animation Presets
// 顶级动画系统 - 像素级精确、有意义的运动

import { Variants, Transition, TargetAndTransition } from 'framer-motion'
import { easingsV5, durationsV5 } from './design-tokens-v5'

// ============================================
// 页面转场动画
// ============================================

export const pageTransitions: Record<string, Variants> = {
  // 默认转场 - 优雅上滑
  default: {
    initial: { opacity: 0, y: 40, scale: 0.98 },
    animate: { 
      opacity: 1, 
      y: 0, 
      scale: 1,
      transition: {
        duration: durationsV5.pageTransition,
        ease: easingsV5.outExpo,
      }
    },
    exit: { 
      opacity: 0, 
      y: -20,
      transition: { duration: 0.3, ease: easingsV5.easeIn }
    },
  },
  
  // 角色入场 - 从下方弹出
  characterEnter: {
    initial: { opacity: 0, y: 100, scale: 0.8 },
    animate: { 
      opacity: 1, 
      y: 0, 
      scale: 1,
      transition: {
        duration: durationsV5.characterEnter,
        ease: easingsV5.outBack,
      }
    },
    exit: { 
      opacity: 0, 
      scale: 0.9,
      transition: { duration: 0.3 }
    },
  },
  
  // 场景淡入
  sceneFade: {
    initial: { opacity: 0 },
    animate: { 
      opacity: 1,
      transition: { duration: 0.8, ease: easingsV5.smooth }
    },
    exit: { 
      opacity: 0,
      transition: { duration: 0.4 }
    },
  },
  
  // 内容滑入
  contentSlide: {
    initial: { opacity: 0, x: 30 },
    animate: { 
      opacity: 1, 
      x: 0,
      transition: {
        duration: 0.5,
        ease: easingsV5.outQuart,
      }
    },
    exit: { 
      opacity: 0, 
      x: -30,
      transition: { duration: 0.3 }
    },
  },
}

// ============================================
// 角色动画状态
// ============================================

export const characterAnimations = {
  // 闲置状态 - 轻微漂浮
  idle: {
    y: [0, -8, 0],
    transition: {
      duration: 3,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
  
  // 说话状态
  speaking: {
    scale: [1, 1.02, 1],
    transition: {
      duration: 0.3,
      repeat: Infinity,
      repeatDelay: 0.1,
    },
  },
  
  // 思考状态
  thinking: {
    rotate: [-3, 3, -3],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
  
  // 开心状态
  happy: {
    y: [0, -15, 0],
    scale: [1, 1.1, 1],
    transition: {
      duration: 0.5,
      ease: easingsV5.bounce,
    },
  },
  
  // 惊喜状态
  surprised: {
    scale: [1, 1.2, 0.95, 1.05, 1],
    transition: {
      duration: 0.6,
      ease: easingsV5.outBack,
    },
  },
  
  // 鼓励状态
  encouraging: {
    rotate: [0, -10, 10, -5, 5, 0],
    transition: {
      duration: 0.8,
      ease: 'easeOut',
    },
  },
  
  // 庆祝状态
  celebrating: {
    y: [0, -30, 0, -20, 0, -10, 0],
    rotate: [0, -15, 15, -10, 10, -5, 0],
    scale: [1, 1.2, 1.1, 1.15, 1.05, 1.1, 1],
    transition: {
      duration: 1.2,
      ease: easingsV5.outBack,
    },
  },
  
  // 挥手
  waving: {
    rotate: [0, 14, -8, 14, -4, 10, 0],
    transition: {
      duration: 1,
      ease: 'easeInOut',
    },
  },
}

// ============================================
// 交互元素动画
// ============================================

export const interactionAnimations = {
  // 选项卡片
  optionCard: {
    initial: { opacity: 0, y: 20, scale: 0.95 },
    animate: { 
      opacity: 1, 
      y: 0, 
      scale: 1,
    },
    hover: { 
      scale: 1.02,
      y: -4,
      boxShadow: '0 12px 28px rgba(15, 23, 42, 0.12)',
    },
    tap: { 
      scale: 0.98,
    },
    selected: {
      scale: 1,
      boxShadow: '0 0 0 2px #0F172A, 0 8px 24px rgba(15, 23, 42, 0.15)',
    },
  },
  
  // 按钮
  button: {
    initial: { opacity: 0, y: 10 },
    animate: { 
      opacity: 1, 
      y: 0,
      transition: { duration: 0.3, ease: easingsV5.outQuart }
    },
    hover: { 
      scale: 1.02,
      boxShadow: '0 4px 16px rgba(15, 23, 42, 0.2)',
    },
    tap: { 
      scale: 0.98,
    },
    disabled: {
      opacity: 0.5,
    },
  },
  
  // 输入框
  input: {
    initial: { opacity: 0, y: 10 },
    animate: { 
      opacity: 1, 
      y: 0,
    },
    focus: {
      boxShadow: '0 0 0 2px #0F172A',
    },
  },
  
  // 对话气泡
  chatBubble: {
    initial: { opacity: 0, scale: 0.8, y: 20 },
    animate: { 
      opacity: 1, 
      scale: 1, 
      y: 0,
      transition: {
        duration: 0.4,
        ease: easingsV5.outBack,
      }
    },
    exit: { 
      opacity: 0, 
      scale: 0.9,
      transition: { duration: 0.2 }
    },
  },
}

// ============================================
// 场景动画
// ============================================

export const sceneAnimations = {
  // 渐变流动
  gradientFlow: {
    animate: {
      backgroundPosition: ['0% 0%', '100% 100%'],
      transition: {
        duration: 20,
        repeat: Infinity,
        repeatType: 'reverse' as const,
        ease: 'linear',
      },
    },
  },
  
  // 粒子漂浮
  particleFloat: (index: number) => ({
    y: [0, -30, 0],
    x: [0, Math.sin(index) * 20, 0],
    opacity: [0.3, 0.6, 0.3],
    transition: {
      duration: 4 + index * 0.5,
      repeat: Infinity,
      ease: 'easeInOut',
      delay: index * 0.2,
    },
  }),
  
  // 自然元素摇曳
  naturalSway: (index: number) => ({
    rotate: [-5, 5, -5],
    transition: {
      duration: 3 + index * 0.3,
      repeat: Infinity,
      ease: 'easeInOut',
      delay: index * 0.1,
    },
  }),
  
  // 光晕脉动
  glowPulse: {
    opacity: [0.3, 0.6, 0.3],
    scale: [1, 1.1, 1],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
}

// ============================================
// 进度动画
// ============================================

export const progressAnimations = {
  // 进度条填充
  progressFill: (progress: number) => ({
    width: `${progress}%`,
    transition: {
      duration: 0.5,
      ease: easingsV5.outQuart,
    },
  }),
  
  // 进度点
  progressDot: (isActive: boolean, isCompleted: boolean) => ({
    scale: isActive ? 1.2 : 1,
    backgroundColor: isCompleted ? '#61E0BD' : isActive ? '#0F172A' : '#E2E8F0',
    transition: {
      duration: 0.3,
      ease: easingsV5.outQuart,
    },
  }),
  
  // 旅程路径
  journeyPath: (progress: number) => ({
    pathLength: progress / 100,
    transition: {
      duration: 0.8,
      ease: easingsV5.outQuart,
    },
  }),
}

// ============================================
// 数字动画
// ============================================

export const numberAnimations = {
  // 计数动画
  countUp: (from: number, to: number, duration = 1) => ({
    textContent: to,
    transition: {
      duration,
      ease: easingsV5.outQuart,
    },
  }),
  
  // 数字切换
  digitSwitch: {
    initial: { y: 20, opacity: 0 },
    animate: { 
      y: 0, 
      opacity: 1,
      transition: { duration: 0.3, ease: easingsV5.outQuart }
    },
    exit: { 
      y: -20, 
      opacity: 0,
      transition: { duration: 0.2 }
    },
  },
}

// ============================================
// 列表动画 (stagger)
// ============================================

export const staggerAnimations = {
  // 容器
  container: {
    animate: {
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.2,
      },
    },
  },
  
  // 快速 stagger
  containerFast: {
    animate: {
      transition: {
        staggerChildren: 0.05,
        delayChildren: 0.1,
      },
    },
  },
  
  // 慢速 stagger
  containerSlow: {
    animate: {
      transition: {
        staggerChildren: 0.15,
        delayChildren: 0.3,
      },
    },
  },
  
  // 子元素
  item: {
    initial: { opacity: 0, y: 20 },
    animate: { 
      opacity: 1, 
      y: 0,
      transition: { duration: 0.4, ease: easingsV5.outQuart }
    },
  },
  
  // 从左滑入
  itemFromLeft: {
    initial: { opacity: 0, x: -20 },
    animate: { 
      opacity: 1, 
      x: 0,
      transition: { duration: 0.4, ease: easingsV5.outQuart }
    },
  },
  
  // 缩放入场
  itemScale: {
    initial: { opacity: 0, scale: 0.8 },
    animate: { 
      opacity: 1, 
      scale: 1,
      transition: { duration: 0.4, ease: easingsV5.outBack }
    },
  },
}

// ============================================
// 特效动画
// ============================================

export const effectAnimations = {
  // 闪光
  shimmer: {
    backgroundPosition: ['-200%', '200%'],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: 'linear',
    },
  },
  
  // 呼吸
  breathe: {
    scale: [1, 1.05, 1],
    opacity: [0.8, 1, 0.8],
    transition: {
      duration: 3,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
  
  // 震动
  shake: {
    x: [-10, 10, -8, 8, -4, 4, 0],
    transition: {
      duration: 0.5,
      ease: 'easeOut',
    },
  },
  
  // 弹跳
  bounce: {
    y: [0, -20, 0, -10, 0, -5, 0],
    transition: {
      duration: 0.6,
      ease: 'easeOut',
    },
  },
  
  // 旋转入场
  spinIn: {
    initial: { rotate: -180, opacity: 0, scale: 0 },
    animate: { 
      rotate: 0, 
      opacity: 1, 
      scale: 1,
      transition: { duration: 0.6, ease: easingsV5.outBack }
    },
  },
  
  // 爆炸效果
  explode: {
    scale: [1, 1.5, 0],
    opacity: [1, 0.8, 0],
    transition: {
      duration: 0.4,
      ease: easingsV5.outQuart,
    },
  },
}

// ============================================
// 组合动画序列
// ============================================

export const sequences = {
  // 页面入场序列
  pageEnter: {
    scene: { delay: 0 },
    character: { delay: 0.3 },
    dialog: { delay: 0.6 },
    options: { delay: 0.8 },
    button: { delay: 1 },
  },
  
  // 选择反馈序列
  selectFeedback: {
    optionPop: { delay: 0 },
    characterReact: { delay: 0.1 },
    dialogUpdate: { delay: 0.3 },
    buttonEnable: { delay: 0.5 },
  },
  
  // 庆祝序列
  celebrate: {
    confetti: { delay: 0 },
    character: { delay: 0.2 },
    content: { delay: 0.5 },
  },
}

// ============================================
// 动画 hooks 帮助函数
// ============================================

export const createStaggerDelay = (index: number, baseDelay = 0.1) => 
  index * baseDelay

export const createRandomDelay = (min = 0, max = 0.3) => 
  Math.random() * (max - min) + min

export const createSpringConfig = (
  stiffness = 400, 
  damping = 30, 
  mass = 1
): Transition => ({
  type: 'spring',
  stiffness,
  damping,
  mass,
})

// 默认导出
export default {
  page: pageTransitions,
  character: characterAnimations,
  interaction: interactionAnimations,
  scene: sceneAnimations,
  progress: progressAnimations,
  number: numberAnimations,
  stagger: staggerAnimations,
  effect: effectAnimations,
  sequences,
}
