// VitaFlow Production Design Tokens
// 对齐正式产品 - 7:2:1 配色比例

export const colors = {
  // Slate 色阶 - 主色系统
  slate: {
    900: '#0F172A',  // 按钮、标题、选中态 (20%)
    800: '#1E293B',
    700: '#334155',
    600: '#475569',
    500: '#64748B',  // 次要文字
    400: '#94A3B8',
    300: '#CBD5E1',  // 默认边框
    200: '#E2E8F0',
    100: '#F1F5F9',
    50:  '#F8FAFC',  // 主背景 (70%)
  },
  
  // 点缀色 (10%)
  accent: {
    primary: '#61E0BD',   // 薄荷绿 - 进度条、成功状态
    light: '#A7F3D0',     // 浅薄荷绿
  },
  
  // 语义色
  semantic: {
    success: '#61E0BD',   // 薄荷绿
    error: '#EF4444',     // 红色
    warning: '#F59E0B',   // 橙色
    info: '#3B82F6',      // 蓝色
  },
  
  // 高光
  white: '#FFFFFF',       // 卡片背景
  
  // 语义别名 - 向后兼容
  primary: {
    dark: '#0F172A',      // slate-900
    light: '#334155',     // slate-700
    gradient: 'linear-gradient(135deg, #0F172A 0%, #334155 100%)',
  },
  
  background: {
    primary: '#F8FAFC',   // slate-50
    secondary: '#F1F5F9', // slate-100
    card: '#FFFFFF',
    dark: '#0F172A',      // slate-900 (Launch用)
  },
  
  surface: {
    white: '#FFFFFF',
    card: '#FFFFFF',
    elevated: '#FFFFFF',
  },
  
  text: {
    primary: '#0F172A',   // slate-900
    secondary: '#64748B', // slate-500
    tertiary: '#94A3B8',  // slate-400
    inverse: '#FFFFFF',
    accent: '#61E0BD',    // 薄荷绿
  },
  
  border: {
    light: '#E2E8F0',     // slate-200
    medium: '#CBD5E1',    // slate-300
    focus: '#0F172A',     // slate-900
    selected: '#0F172A',  // slate-900
  },
  
  // Shadow Colors
  shadow: {
    light: 'rgba(15, 23, 42, 0.08)',
    medium: 'rgba(15, 23, 42, 0.15)',
    heavy: 'rgba(15, 23, 42, 0.25)',
    accent: 'rgba(97, 224, 189, 0.3)',
  },
  
  // Box Shadows (convenience)
  shadows: {
    sm: '0px 1px 2px rgba(15, 23, 42, 0.05)',
    md: '0px 4px 12px rgba(15, 23, 42, 0.1)',
    lg: '0px 10px 40px -10px rgba(15, 23, 42, 0.15)',
    xl: '0px 20px 60px -15px rgba(15, 23, 42, 0.2)',
    card: '0px 1px 3px rgba(15, 23, 42, 0.08)',
    cardHover: '0px 10px 40px -10px rgba(15, 23, 42, 0.15)',
    cardSelected: '0px 0px 0px 2px #0F172A',
    button: '0px 1px 3px rgba(15, 23, 42, 0.1)',
    glow: '0px 0px 20px rgba(97, 224, 189, 0.4)',
  },
}

// Box Shadows - Figma 规范
export const shadows = {
  // Figma shadow/sm
  sm: '0px 2px 4px rgba(15, 23, 42, 0.03), 0px 1px 2px rgba(15, 23, 42, 0.04)',
  // Figma shadow/md
  md: '0px 2px 6px -2px rgba(15, 23, 42, 0.03), 0px 1px 2px rgba(15, 23, 42, 0.04)',
  lg: '0px 10px 40px -10px rgba(15, 23, 42, 0.15)',
  xl: '0px 20px 60px -15px rgba(15, 23, 42, 0.2)',
  // Figma 卡片阴影
  card: '0px 2px 4px rgba(15, 23, 42, 0.03), 0px 1px 2px rgba(15, 23, 42, 0.04)',
  cardHover: '0px 4px 12px rgba(15, 23, 42, 0.08)',
  cardSelected: '0px 0px 0px 2px #0F172A',
  button: '0px 1px 3px rgba(15, 23, 42, 0.1)',
  // Figma shadow/glow
  glow: '0px 0px 12px rgba(7, 209, 236, 0.1)',
  // Figma shadow/text
  text: '0px 1px 2px rgba(15, 23, 42, 0.08)',
  textLight: '0px 1px 2px rgba(15, 23, 42, 0.05)',
}

// Figma 卡片边框
export const cardBorder = {
  default: '1px solid rgba(15, 23, 42, 0.01)',
  light: '1px solid rgba(15, 23, 42, 0.05)',
}

// Border Radius
export const radii = {
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '20px',
  '2xl': '24px',
  full: '9999px',
}

// Typography
// 注意：最重字体为 medium (500)
export const typography = {
  fontFamily: {
    primary: 'var(--font-outfit)',
    mono: 'monospace',
  },
  fontSize: {
    xs: '12px',
    sm: '13px',
    base: '14px',
    md: '15px',
    lg: '17px',
    xl: '20px',
    '2xl': '24px',
    '3xl': '32px',
    '4xl': '48px',  // 最大字号
  },
  fontWeight: {
    normal: '400',
    medium: '500',  // 最重字体
  },
  lineHeight: {
    tight: '1.2',
    normal: '1.5',
    relaxed: '1.6',
  },
  // Letter Spacing - VitaFlow 规范
  letterSpacing: {
    '48': '-1.5px',    // 48px
    '40': '-0.5px',    // 40px
    default: '-0.4px', // 28px 及以下全部
  },
}

// Spacing
// 间距范围：12px - 32px
export const spacing = {
  0: '0',
  3: '12px',   // 最小间距
  4: '16px',
  5: '20px',
  6: '24px',
  8: '32px',   // 最大间距
}

// Z-Index
export const zIndex = {
  base: 0,
  dropdown: 10,
  modal: 100,
  toast: 200,
  tooltip: 300,
}

// BigText 样式 - 无角色大字体版本
// 字体最重：medium (500)，数字最大：48px
export const bigTextStyles = {
  // 标题样式 (36px = -0.4px)
  title: {
    fontSize: '36px',
    fontWeight: '500',  // medium
    lineHeight: '1.15',
    letterSpacing: '-0.4px',
    color: colors.text.primary,
  },
  
  // 副标题样式
  subtitle: {
    fontSize: '18px',
    fontWeight: '400',
    lineHeight: '1.4',
    color: colors.text.secondary,
  },
  
  // 选项文字样式
  option: {
    fontSize: '18px',
    fontWeight: '500',  // medium
    lineHeight: '1.3',
    color: colors.text.primary,
  },
  
  // 选项描述样式
  optionDescription: {
    fontSize: '14px',
    fontWeight: '400',
    lineHeight: '1.4',
    color: colors.text.secondary,
  },
  
  // 输入框文字样式
  input: {
    fontSize: '20px',
    fontWeight: '500',  // medium
    lineHeight: '1.4',
    color: colors.text.primary,
  },
  
  // 数字输入样式 - 使用滚轮选择器 (48px = -1.5px)
  numberDisplay: {
    fontSize: '48px',   // 最大字号
    fontWeight: '500',  // medium
    lineHeight: '1',
    letterSpacing: '-1.5px',
    color: colors.text.primary,
  },
  
  // CTA 按钮样式
  cta: {
    fontSize: '18px',
    fontWeight: '500',  // medium
    padding: '16px 32px',
    borderRadius: '12px',
  },
  
  // 间距 - 12px 到 32px
  spacing: {
    titleTop: '32px',   // 最大间距
    titleBottom: '16px',
    contentGap: '16px',
    ctaBottom: '32px',  // 最大间距
  },
}

// 导出完整的 Design System
export const designTokens = {
  colors,
  shadows,
  radii,
  typography,
  spacing,
  zIndex,
  bigTextStyles,
}

export default designTokens
