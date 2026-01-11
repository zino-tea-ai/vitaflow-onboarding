// VitaFlow Onboarding V3 - 统一动效配置系统
// 定义页面过渡、微交互、stagger 等动画参数

/**
 * 页面过渡动画配置
 * iOS 原生感的 Slide + Fade 组合
 */
export const pageTransitions = {
  forward: {
    initial: { x: 100, opacity: 0 },
    animate: { x: 0, opacity: 1 },
    exit: { x: -100, opacity: 0 },
    transition: {
      type: 'spring' as const,
      stiffness: 300,
      damping: 30,
      mass: 1
    }
  },
  backward: {
    initial: { x: -100, opacity: 0 },
    animate: { x: 0, opacity: 1 },
    exit: { x: 100, opacity: 0 },
    transition: {
      type: 'spring' as const,
      stiffness: 300,
      damping: 30,
      mass: 1
    }
  }
}

/**
 * 微交互动画配置
 * 按钮、卡片等交互元素的动画
 */
export const microInteractions = {
  buttonTap: {
    scale: 0.96,
    transition: { duration: 0.1, ease: 'easeOut' as const }
  },
  buttonHover: {
    scale: 1.02,
    transition: { duration: 0.2, ease: 'easeOut' as const }
  },
  cardHover: {
    y: -4,
    scale: 1.02,
    boxShadow: '0 10px 40px -10px rgba(43, 39, 53, 0.15)',
    transition: { duration: 0.2, ease: 'easeOut' as const }
  },
  cardSelect: {
    scale: 1.05,
    rotateY: 2,
    transition: {
      type: 'spring' as const,
      stiffness: 300,
      damping: 20
    }
  },
  iconBounce: {
    scale: [1, 1.2, 1],
    transition: {
      duration: 0.3,
      ease: 'easeOut' as const
    }
  }
}

/**
 * Stagger 动画系统
 * 用于列表、选项等元素的依次出现
 */
export const staggerConfig = {
  container: {
    staggerChildren: 0.08,
    delayChildren: 0.1
  },
  item: {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -20 }
  },
  // 快速 stagger（用于选项卡片）
  fast: {
    staggerChildren: 0.05,
    delayChildren: 0.05
  },
  // 慢速 stagger（用于重要内容）
  slow: {
    staggerChildren: 0.12,
    delayChildren: 0.2
  }
}

/**
 * 数字动画配置
 * 用于计数器、进度条等数字动画
 */
export const numberAnimations = {
  counter: {
    transition: {
      duration: 1.5,
      ease: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number]
    }
  },
  progressRing: {
    transition: {
      duration: 2,
      ease: 'easeOut' as const
    }
  }
}

/**
 * 3D 效果配置
 * 用于卡片、转盘等 3D 效果
 */
export const threeDEffects = {
  cardPerspective: '1000px',
  cardHover: {
    rotateY: 2,
    rotateX: 1,
    transition: { duration: 0.2 }
  },
  wheelPerspective: '1200px',
  wheelRotation: {
    transition: {
      type: 'spring' as const,
      stiffness: 100,
      damping: 15
    }
  }
}

/**
 * 成功/庆祝动画
 */
export const celebrationAnimations = {
  confetti: {
    scale: [1, 1.2, 1],
    rotate: [0, 180, 360],
    transition: {
      duration: 0.6,
      ease: 'easeOut' as const
    }
  },
  badge: {
    scale: [0, 1.2, 1],
    rotate: [0, 10, -10, 0],
    transition: {
      duration: 0.5,
      ease: 'easeOut' as const
    }
  }
}

/**
 * 加载动画配置
 */
export const loadingAnimations = {
  spinner: {
    rotate: 360,
    transition: {
      duration: 1,
      repeat: Infinity,
      ease: 'linear' as const
    }
  },
  pulse: {
    scale: [1, 1.1, 1],
    opacity: [1, 0.7, 1],
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: 'easeInOut' as const
    }
  }
}

/**
 * 动效时长标准
 */
export const motionDurations = {
  micro: 0.1,      // 微交互（按钮、开关）
  fast: 0.2,       // 快速切换
  normal: 0.3,     // 标准过渡
  slow: 0.5,       // 慢速过渡
  complex: 1.0     // 复杂动画
}

/**
 * 缓动函数预设
 */
export const easingFunctions = {
  easeOut: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number],
  easeInOut: [0.42, 0, 0.58, 1] as [number, number, number, number],
  spring: {
    type: 'spring' as const,
    stiffness: 300,
    damping: 30
  }
}

/**
 * 性能优化配置
 * 确保所有动画使用 GPU 加速
 */
export const performanceConfig = {
  willChange: 'transform, opacity',
  transform: 'translateZ(0)', // 强制 GPU 加速
  backfaceVisibility: 'hidden' as const
}
