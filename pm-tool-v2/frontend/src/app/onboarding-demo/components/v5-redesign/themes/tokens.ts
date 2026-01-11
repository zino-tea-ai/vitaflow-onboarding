// V5 Premium Design Tokens
// 两套顶级设计主题：Brilliant (极简白底) + Apple (高端渐变)

export type V5Theme = 'brilliant' | 'apple'

// ============================================
// Brilliant Theme - 极简白底
// 参考 Brilliant.org 的设计语言
// ============================================

export const brilliantTheme = {
  name: 'brilliant' as const,
  
  // 背景
  background: {
    primary: '#FFFFFF',
    secondary: '#FAFAFA',
    tertiary: '#F5F5F5',
  },
  
  // 文字
  text: {
    primary: '#1A1A1A',
    secondary: '#6B7280',
    tertiary: '#9CA3AF',
    inverse: '#FFFFFF',
  },
  
  // 卡片
  card: {
    background: '#FFFFFF',
    border: '#E5E7EB',
    shadow: '0 1px 3px rgba(0, 0, 0, 0.08)',
    shadowHover: '0 4px 12px rgba(0, 0, 0, 0.1)',
  },
  
  // 输入框
  input: {
    background: '#FFFFFF',
    border: '#E5E7EB',
    borderFocus: '#1A1A1A',
    placeholder: '#9CA3AF',
  },
  
  // 按钮
  button: {
    primary: {
      background: '#1A1A1A',
      text: '#FFFFFF',
      shadow: '0 1px 2px rgba(0, 0, 0, 0.1)',
    },
    secondary: {
      background: '#F5F5F5',
      text: '#1A1A1A',
      border: '#E5E7EB',
    },
  },
  
  // 强调色
  accent: {
    primary: '#1A1A1A',
    success: '#10B981',
    info: '#3B82F6',
  },
  
  // 选项卡片
  option: {
    background: '#FFFFFF',
    backgroundHover: '#FAFAFA',
    backgroundSelected: '#1A1A1A',
    border: '#E5E7EB',
    borderSelected: '#1A1A1A',
    textSelected: '#FFFFFF',
  },
}

// ============================================
// Apple Theme - 高端渐变
// 参考 Apple 的设计语言
// ============================================

export const appleTheme = {
  name: 'apple' as const,
  
  // 背景
  background: {
    primary: 'linear-gradient(180deg, #FAFAFA 0%, #F5F5F7 100%)',
    secondary: '#F5F5F7',
    tertiary: '#E8E8ED',
    solid: '#FAFAFA', // 用于需要纯色的地方
  },
  
  // 文字
  text: {
    primary: '#1D1D1F',
    secondary: '#86868B',
    tertiary: '#AEAEB2',
    inverse: '#FFFFFF',
  },
  
  // 卡片 - 玻璃态
  card: {
    background: 'rgba(255, 255, 255, 0.72)',
    backgroundSolid: '#FFFFFF',
    border: 'rgba(0, 0, 0, 0.04)',
    shadow: '0 2px 12px rgba(0, 0, 0, 0.08)',
    shadowHover: '0 8px 24px rgba(0, 0, 0, 0.12)',
    blur: '20px',
  },
  
  // 输入框
  input: {
    background: 'rgba(255, 255, 255, 0.8)',
    border: 'rgba(0, 0, 0, 0.08)',
    borderFocus: '#0071E3',
    placeholder: '#AEAEB2',
  },
  
  // 按钮
  button: {
    primary: {
      background: '#0071E3',
      backgroundHover: '#0077ED',
      text: '#FFFFFF',
      shadow: '0 2px 8px rgba(0, 113, 227, 0.3)',
    },
    secondary: {
      background: 'rgba(0, 0, 0, 0.05)',
      text: '#0071E3',
      border: 'transparent',
    },
  },
  
  // 强调色
  accent: {
    primary: '#0071E3',  // Apple Blue
    success: '#34C759',  // Apple Green
    info: '#5AC8FA',     // Apple Teal
  },
  
  // 选项卡片
  option: {
    background: 'rgba(255, 255, 255, 0.6)',
    backgroundHover: 'rgba(255, 255, 255, 0.8)',
    backgroundSelected: '#0071E3',
    border: 'rgba(0, 0, 0, 0.06)',
    borderSelected: '#0071E3',
    textSelected: '#FFFFFF',
  },
}

// ============================================
// 共享样式
// ============================================

export const sharedStyles = {
  // 圆角
  radius: {
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '20px',
    '2xl': '24px',
    full: '9999px',
  },
  
  // 字体
  typography: {
    fontFamily: "'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    
    // 标题 - 大而 bold
    title: {
      fontSize: '28px',
      fontWeight: '700',
      lineHeight: '1.2',
      letterSpacing: '-0.02em',
    },
    
    // 副标题
    subtitle: {
      fontSize: '17px',
      fontWeight: '400',
      lineHeight: '1.4',
    },
    
    // 正文
    body: {
      fontSize: '17px',
      fontWeight: '400',
      lineHeight: '1.5',
    },
    
    // 小字
    caption: {
      fontSize: '13px',
      fontWeight: '400',
      lineHeight: '1.4',
    },
    
    // 按钮
    button: {
      fontSize: '17px',
      fontWeight: '600',
      lineHeight: '1',
    },
  },
  
  // 间距
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
  },
  
  // 动画
  animation: {
    duration: {
      fast: '150ms',
      normal: '250ms',
      slow: '400ms',
    },
    easing: {
      default: 'cubic-bezier(0.25, 0.1, 0.25, 1)',
      spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      smooth: 'cubic-bezier(0.4, 0, 0.2, 1)',
    },
  },
}

// ============================================
// 主题获取函数
// ============================================

export const getTheme = (themeName: V5Theme) => {
  return themeName === 'brilliant' ? brilliantTheme : appleTheme
}

// 类型导出
export type BrilliantTheme = typeof brilliantTheme
export type AppleTheme = typeof appleTheme
export type ThemeTokens = BrilliantTheme | AppleTheme
