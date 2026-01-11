'use client'

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

export type FlowVersion = 'v1' | 'v2' | 'v3' | 'production' | 'v5'

// 角色风格类型 (兼容旧版 + V5)
export type CharacterStyle = 'v_logo' | 'vita' | 'abstract' | 'orb'

// V5 角色风格 (旧版)
export type V5CharacterStyle = 'evolution' | 'abstract' | '3d' | 'illustrated'

// V5 场景风格 (旧版)
export type V5SceneStyle = 'gradient' | 'particle' | 'nature'

// V5 Premium 主题
export type V5PremiumTheme = 'brilliant' | 'apple'

// V5 Premium 角色
export type V5PremiumCharacter = 'none' | 'abstract' | 'mascot' | 'logo'

// PROD 样式类型
export type ProdStyle = 'default' | 'bigtext'

// 文案风格类型
export type CopyStyle = 'witty' | 'warm' | 'data'

interface ABTestState {
  // 当前选择的流程版本
  currentVersion: FlowVersion
  
  // 是否启用 A/B 测试模式
  abTestEnabled: boolean
  
  // === Conversational Onboarding 配置 ===
  
  // 角色风格
  characterStyle: CharacterStyle
  
  // 文案风格
  copyStyle: CopyStyle
  
  // 是否启用对话式反馈
  conversationalFeedbackEnabled: boolean
  
  // 是否显示角色
  showMascot: boolean
  
  // === V5 配置 (旧版) ===
  v5CharacterStyle: V5CharacterStyle
  v5SceneStyle: V5SceneStyle
  
  // === V5 Premium 配置 (新版) ===
  v5PremiumTheme: V5PremiumTheme
  v5PremiumCharacter: V5PremiumCharacter
  
  // === PROD 配置 ===
  prodStyle: ProdStyle
  
  // 切换版本
  setVersion: (version: FlowVersion) => void
  
  // 切换 A/B 测试模式
  toggleABTest: () => void
  
  // === Conversational Onboarding Actions ===
  
  // 设置角色风格
  setCharacterStyle: (style: CharacterStyle) => void
  
  // 设置文案风格
  setCopyStyle: (style: CopyStyle) => void
  
  // 切换对话式反馈
  toggleConversationalFeedback: () => void
  
  // 切换角色显示
  toggleMascot: () => void
  
  // === V5 Actions (旧版) ===
  setV5CharacterStyle: (style: V5CharacterStyle) => void
  setV5SceneStyle: (style: V5SceneStyle) => void
  
  // === V5 Premium Actions (新版) ===
  setV5PremiumTheme: (theme: V5PremiumTheme) => void
  setV5PremiumCharacter: (character: V5PremiumCharacter) => void
  
  // === PROD Actions ===
  setProdStyle: (style: ProdStyle) => void
}

export const useABTestStore = create<ABTestState>()(
  persist(
    (set) => ({
      currentVersion: 'v1',
      abTestEnabled: false,
      
      // Conversational Onboarding 默认配置
      characterStyle: 'vita',
      copyStyle: 'warm',
      conversationalFeedbackEnabled: true,
      showMascot: true,
      
      // V5 默认配置 (旧版)
      v5CharacterStyle: 'illustrated',
      v5SceneStyle: 'gradient',
      
      // V5 Premium 默认配置 (新版)
      v5PremiumTheme: 'brilliant',
      v5PremiumCharacter: 'abstract',
      
      // PROD 默认配置
      prodStyle: 'bigtext',
      
      setVersion: (version) => set({ currentVersion: version }),
      
      toggleABTest: () => set((state) => ({ abTestEnabled: !state.abTestEnabled })),
      
      // Conversational Onboarding Actions
      setCharacterStyle: (style) => set({ characterStyle: style }),
      
      setCopyStyle: (style) => set({ copyStyle: style }),
      
      toggleConversationalFeedback: () => set((state) => ({ 
        conversationalFeedbackEnabled: !state.conversationalFeedbackEnabled 
      })),
      
      toggleMascot: () => set((state) => ({ showMascot: !state.showMascot })),
      
      // V5 Actions (旧版)
      setV5CharacterStyle: (style) => set({ v5CharacterStyle: style }),
      setV5SceneStyle: (style) => set({ v5SceneStyle: style }),
      
      // V5 Premium Actions (新版)
      setV5PremiumTheme: (theme) => set({ v5PremiumTheme: theme }),
      setV5PremiumCharacter: (character) => set({ v5PremiumCharacter: character }),
      
      // PROD Actions
      setProdStyle: (style) => set({ prodStyle: style }),
    }),
    {
      name: 'vitaflow-ab-test',
      storage: createJSONStorage(() => localStorage)
    }
  )
)

// 版本信息
export const VERSION_INFO = {
  v1: {
    name: 'Original Flow',
    pages: 37,
    description: '当前版本 - 基础流程',
    highlights: [
      '37页完整流程',
      '权限集中在后段',
      '标准问题节奏'
    ]
  },
  v2: {
    name: 'Optimized Flow',
    pages: 40,
    description: '优化版本 - 基于竞品分析',
    highlights: [
      '40页优化流程',
      '权限分散：间隔7-9页',
      '问题节奏：最多3连问',
      '软承诺设计：打断0-input',
      '更多鼓励过渡页'
    ]
  },
  v3: {
    name: 'Premium Flow',
    pages: 50,
    description: '顶级版本 - 全方位升级',
    highlights: [
      '50页顶级流程',
      '统一动效系统',
      '阶段化进度显示',
      '认知负荷管理',
      '条件分支逻辑',
      '完整个性化体验',
      '心理学策略强化'
    ]
  },
  production: {
    name: 'Production Flow',
    pages: 18,
    description: '正式版 - 高转化精简流程',
    highlights: [
      '18页精简流程',
      '页面合并优化',
      '活动水平页（精确计算 TDEE）',
      '2个价值展示页（AI扫描 + 个性化）',
      '权限申请优化（先展示好处）',
      '账号注册（最后一页）',
    ]
  },
  v5: {
    name: 'V5 Premium',
    pages: 12,
    description: '顶级设计 - Brilliant/Apple 风格',
    highlights: [
      '12页极简流程',
      '2种设计风格：Brilliant / Apple',
      '4种角色方案可选',
      '极简白底 or 高端渐变',
      '真正的顶级设计感',
      '去掉花哨元素',
      '参考 Brilliant.org 品质'
    ]
  }
}

// 角色风格信息
export const CHARACTER_STYLE_INFO = {
  v_logo: {
    name: 'V Logo',
    description: 'VitaFlow Logo 表情版',
    preview: '基于品牌 Logo，简约风格',
  },
  vita: {
    name: 'Vita',
    description: '萌芽角色（推荐）',
    preview: '拟人化吉祥物，丰富表情',
  },
  abstract: {
    name: 'Abstract',
    description: '抽象圆点',
    preview: '最简洁，纯动画表达',
  },
}

// 文案风格信息
export const COPY_STYLE_INFO = {
  witty: {
    name: 'Witty',
    description: '幽默俏皮',
    example: '"Watch out, fat. Here comes trouble."',
  },
  warm: {
    name: 'Warm',
    description: '温暖鼓励',
    example: '"太棒了！每一步都是进步"',
  },
  data: {
    name: 'Data',
    description: '数据驱动',
    example: '"预计 12 周后减轻 6kg"',
  },
}

// V5 角色风格信息
export const V5_CHARACTER_STYLE_INFO = {
  evolution: {
    name: 'Vita Evolution',
    description: '升级版绿色角色',
    preview: '有身体、表情丰富的 Vita',
  },
  abstract: {
    name: 'Abstract Premium',
    description: '抽象流体形态',
    preview: 'Apple 风格的动态图形',
  },
  '3d': {
    name: '3D Vita',
    description: '三维立体角色',
    preview: 'CSS 3D 效果的立体感',
  },
  illustrated: {
    name: 'Illustrated',
    description: '插画风格（推荐）',
    preview: '完整插画角色，最有设计感',
  },
}

// V5 场景风格信息 (旧版)
export const V5_SCENE_STYLE_INFO = {
  gradient: {
    name: 'Gradient Flow',
    description: '渐变天空',
    preview: '随进度变化的时间渐变',
  },
  particle: {
    name: 'Particle Universe',
    description: '粒子宇宙',
    preview: '科技感的漂浮光点',
  },
  nature: {
    name: 'Nature Elements',
    description: '自然元素',
    preview: '植物和有机形状装饰',
  },
}

// V5 Premium 主题信息 (新版)
export const V5_PREMIUM_THEME_INFO = {
  brilliant: {
    name: 'Brilliant',
    description: '极简白底',
    preview: '参考 Brilliant.org，纯净简洁',
  },
  apple: {
    name: 'Apple',
    description: '高端渐变',
    preview: '玻璃态效果，微妙光效',
  },
}

// V5 Premium 角色信息 (新版)
export const V5_PREMIUM_CHARACTER_INFO = {
  none: {
    name: 'None',
    description: '无角色',
    preview: '纯文字对话，最极简',
  },
  abstract: {
    name: 'Abstract Orb',
    description: '抽象光球',
    preview: '类似 Siri，科技感',
  },
  mascot: {
    name: 'Mascot',
    description: '精致吉祥物',
    preview: '参考 Gentler Streak',
  },
  logo: {
    name: 'Logo Only',
    description: '仅 V Logo',
    preview: '品牌化，带动画',
  },
}

// PROD 样式信息
export const PROD_STYLE_INFO = {
  default: {
    name: 'Default',
    description: '默认样式',
    preview: '带角色和对话气泡',
  },
  bigtext: {
    name: 'BigText',
    description: '大字体无角色',
    preview: '简洁大标题，CTA固定底部',
  },
}
