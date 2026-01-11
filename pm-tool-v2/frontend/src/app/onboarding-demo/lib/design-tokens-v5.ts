// VitaFlow V5 Design Tokens
// 顶级设计 - 去表单化、角色主导、场景沉浸

// ============================================
// 颜色系统 - 保持 VitaFlow 风格，更有张力
// ============================================

export const colorsV5 = {
  // Slate 色阶 - 主色系统 (70%)
  slate: {
    950: '#020617',  // 极深，用于特殊强调
    900: '#0F172A',  // 按钮、标题
    800: '#1E293B',  // 次级按钮
    700: '#334155',
    600: '#475569',
    500: '#64748B',  // 次要文字
    400: '#94A3B8',
    300: '#CBD5E1',
    200: '#E2E8F0',
    100: '#F1F5F9',
    50:  '#F8FAFC',  // 主背景
  },
  
  // 品牌绿 - 点缀色 (10%)
  mint: {
    500: '#61E0BD',  // 主品牌色
    400: '#7EE7C9',
    300: '#A7F3D0',
    200: '#D1FAE5',
    100: '#ECFDF5',
    gradient: 'linear-gradient(135deg, #61E0BD 0%, #34D399 100%)',
    glow: 'rgba(97, 224, 189, 0.4)',
  },
  
  // 场景渐变色
  scene: {
    dawn: 'linear-gradient(180deg, #FEF3C7 0%, #FDE68A 50%, #FCD34D 100%)',
    morning: 'linear-gradient(180deg, #DBEAFE 0%, #BFDBFE 50%, #93C5FD 100%)',
    noon: 'linear-gradient(180deg, #E0F2FE 0%, #BAE6FD 50%, #7DD3FC 100%)',
    afternoon: 'linear-gradient(180deg, #FEF9C3 0%, #FEF08A 50%, #FDE047 100%)',
    dusk: 'linear-gradient(180deg, #FECACA 0%, #FCA5A5 50%, #F87171 100%)',
    night: 'linear-gradient(180deg, #1E293B 0%, #0F172A 100%)',
    
    // 中性渐变
    soft: 'linear-gradient(180deg, #F8FAFC 0%, #F1F5F9 100%)',
    warm: 'linear-gradient(180deg, #FFFBEB 0%, #FEF3C7 100%)',
    cool: 'linear-gradient(180deg, #F0F9FF 0%, #E0F2FE 100%)',
    fresh: 'linear-gradient(180deg, #ECFDF5 0%, #D1FAE5 100%)',
  },
  
  // 语义色
  semantic: {
    success: '#61E0BD',
    error: '#EF4444',
    warning: '#F59E0B',
    info: '#3B82F6',
  },
  
  // 基础
  white: '#FFFFFF',
  black: '#000000',
  transparent: 'transparent',
}

// ============================================
// 阴影系统 - 更有层次感
// ============================================

export const shadowsV5 = {
  // 基础阴影
  xs: '0 1px 2px rgba(15, 23, 42, 0.04)',
  sm: '0 2px 4px rgba(15, 23, 42, 0.06)',
  md: '0 4px 8px rgba(15, 23, 42, 0.08)',
  lg: '0 8px 16px rgba(15, 23, 42, 0.10)',
  xl: '0 16px 32px rgba(15, 23, 42, 0.12)',
  '2xl': '0 24px 48px rgba(15, 23, 42, 0.16)',
  
  // 特殊效果
  glow: {
    mint: '0 0 40px rgba(97, 224, 189, 0.3)',
    mintStrong: '0 0 60px rgba(97, 224, 189, 0.5)',
    white: '0 0 40px rgba(255, 255, 255, 0.3)',
  },
  
  // 内阴影
  inner: {
    light: 'inset 0 2px 4px rgba(15, 23, 42, 0.05)',
    dark: 'inset 0 2px 4px rgba(0, 0, 0, 0.1)',
  },
  
  // 卡片
  card: {
    default: '0 4px 12px rgba(15, 23, 42, 0.08)',
    hover: '0 12px 28px rgba(15, 23, 42, 0.12)',
    selected: '0 0 0 2px #0F172A, 0 8px 24px rgba(15, 23, 42, 0.15)',
  },
  
  // 按钮
  button: {
    default: '0 2px 8px rgba(15, 23, 42, 0.15)',
    hover: '0 4px 16px rgba(15, 23, 42, 0.2)',
    active: '0 1px 4px rgba(15, 23, 42, 0.15)',
  },
}

// ============================================
// 圆角系统
// ============================================

export const radiiV5 = {
  none: '0',
  sm: '6px',
  md: '10px',
  lg: '14px',
  xl: '18px',
  '2xl': '24px',
  '3xl': '32px',
  full: '9999px',
}

// ============================================
// 字体系统 - 更有层次
// ============================================

export const typographyV5 = {
  fontFamily: {
    primary: "'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    display: "'Outfit', -apple-system, BlinkMacSystemFont, sans-serif",
    mono: "'SF Mono', 'Consolas', monospace",
  },
  
  // 字号 - 更大胆的层次
  fontSize: {
    '2xs': '11px',
    xs: '12px',
    sm: '14px',
    base: '16px',
    lg: '18px',
    xl: '20px',
    '2xl': '24px',
    '3xl': '30px',
    '4xl': '36px',
    '5xl': '48px',
    '6xl': '60px',
    '7xl': '72px',
  },
  
  fontWeight: {
    light: '300',
    normal: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
    extrabold: '800',
  },
  
  lineHeight: {
    none: '1',
    tight: '1.1',
    snug: '1.25',
    normal: '1.4',
    relaxed: '1.5',
    loose: '1.75',
  },
  
  letterSpacing: {
    tighter: '-0.05em',
    tight: '-0.025em',
    normal: '0',
    wide: '0.025em',
    wider: '0.05em',
    widest: '0.1em',
  },
}

// ============================================
// 间距系统
// ============================================

export const spacingV5 = {
  px: '1px',
  0: '0',
  0.5: '2px',
  1: '4px',
  1.5: '6px',
  2: '8px',
  2.5: '10px',
  3: '12px',
  3.5: '14px',
  4: '16px',
  5: '20px',
  6: '24px',
  7: '28px',
  8: '32px',
  9: '36px',
  10: '40px',
  11: '44px',
  12: '48px',
  14: '56px',
  16: '64px',
  20: '80px',
  24: '96px',
  28: '112px',
  32: '128px',
}

// ============================================
// 动画缓动函数 - 顶级质感
// ============================================

export const easingsV5 = {
  // 基础缓动
  linear: [0, 0, 1, 1],
  easeIn: [0.4, 0, 1, 1],
  easeOut: [0, 0, 0.2, 1],
  easeInOut: [0.4, 0, 0.2, 1],
  
  // 高级缓动 - Apple 风格
  smooth: [0.25, 0.1, 0.25, 1],
  snappy: [0.4, 0, 0.2, 1],
  bounce: [0.68, -0.55, 0.265, 1.55],
  
  // 精确缓动 - 用于高级动画
  outExpo: [0.16, 1, 0.3, 1],
  outQuart: [0.25, 1, 0.5, 1],
  outBack: [0.34, 1.56, 0.64, 1],
  inOutQuint: [0.83, 0, 0.17, 1],
  
  // 弹性缓动
  spring: { type: 'spring', stiffness: 400, damping: 30 },
  springBounce: { type: 'spring', stiffness: 300, damping: 20 },
  springGentle: { type: 'spring', stiffness: 200, damping: 25 },
  springSnappy: { type: 'spring', stiffness: 500, damping: 35 },
}

// ============================================
// 动画时长
// ============================================

export const durationsV5 = {
  instant: 0.1,
  fast: 0.2,
  normal: 0.3,
  slow: 0.5,
  slower: 0.7,
  slowest: 1,
  
  // 特殊动画
  pageTransition: 0.6,
  characterEnter: 0.8,
  characterReact: 0.4,
  optionSelect: 0.25,
  buttonPress: 0.15,
}

// ============================================
// Z-Index 层级
// ============================================

export const zIndexV5 = {
  behind: -1,
  base: 0,
  scene: 1,
  character: 10,
  content: 20,
  overlay: 30,
  modal: 40,
  toast: 50,
  tooltip: 60,
}

// ============================================
// 布局常量
// ============================================

export const layoutV5 = {
  // 手机屏幕模拟器
  phoneWidth: 375,
  phoneHeight: 812,
  
  // 区域比例
  characterAreaRatio: 0.5,  // 角色区域占 50%
  dialogAreaHeight: 80,     // 对话区域高度
  interactionAreaRatio: 0.35, // 交互区域占 35%
  
  // 安全区域
  safeArea: {
    top: 47,    // 状态栏
    bottom: 34, // 底部指示器
  },
  
  // 内容边距
  contentPadding: 24,
}

// ============================================
// 默认主题配置
// ============================================

export const themeV5 = {
  colors: colorsV5,
  shadows: shadowsV5,
  radii: radiiV5,
  typography: typographyV5,
  spacing: spacingV5,
  easings: easingsV5,
  durations: durationsV5,
  zIndex: zIndexV5,
  layout: layoutV5,
}

export default themeV5
