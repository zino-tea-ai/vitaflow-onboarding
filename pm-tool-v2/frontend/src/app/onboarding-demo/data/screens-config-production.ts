// VitaFlow Production Onboarding - 16页精简高转化流程
// 基于心理学理论框架 + 顶级 UI/UX 设计标准
// 核心目标：引导用户完成首次 AI 扫描食物体验

import { ScreenType, ScreenOption } from './screens-config'

// 角色状态类型
export type CharacterState = 
  | 'idle' | 'greeting' | 'listening' | 'thinking' 
  | 'explaining' | 'happy' | 'excited' | 'encouraging' 
  | 'proud' | 'celebrating' | 'surprised' | 'waving' | 'cheering'

// 权限好处条目
export interface PermissionBenefit {
  icon: string
  text: string
}

// Production 版本扩展配置
export interface ScreenConfigProduction {
  id: number
  type: ScreenType | 'combined_welcome_goal' | 'combined_height_weight' | 'introduction'
  title: string
  subtitle?: string
  storeKey?: string | string[]  // 支持多个 storeKey（合并页）
  options?: ScreenOption[]
  numberConfig?: {
    min: number
    max: number
    unit: string
    step: number
    defaultValue: number
  }
  textConfig?: {
    placeholder: string
    maxLength?: number
  }
  autoAdvance?: boolean
  skipButton?: boolean
  phase: string
  usePersonalization?: boolean
  
  // Production 特有字段
  showPrivacyBadge?: boolean      // 显示隐私徽章
  showInstantInsight?: boolean    // 显示即时洞察
  showSocialProof?: boolean       // 显示社会证明
  showLossAversion?: boolean      // 显示损失厌恶对比
  celebrateAfter?: boolean        // 完成后庆祝
  animationType?: 'particles' | 'gradient' | 'spring' | 'stagger' | 'confetti'
  
  // Conversational Onboarding 字段
  characterState?: CharacterState // 角色状态
  characterFeedbackKey?: string   // 反馈文案 key
  
  // 价值页特有字段
  valuePropType?: 'ai_scan' | 'personalized' | 'privacy' | 'community' | 'progress_tracking'
  
  // 权限页特有字段
  permissionType?: 'notification' | 'health' | 'camera' | 'location'
  permissionBenefits?: PermissionBenefit[]
}

export const screensConfigProduction: ScreenConfigProduction[] = [
  // ============ Phase 1: Hook 品牌建立 (P1-3) ============
  {
    id: 1,
    type: 'launch',
    title: 'VitaFlow',
    subtitle: 'Your AI Nutrition Companion',
    phase: 'brand',
    autoAdvance: true,
    animationType: 'particles',
    characterState: 'greeting',
  },
  {
    id: 2,
    type: 'introduction',  // 角色开场白页面
    title: 'Meet Vita',
    subtitle: 'Your AI nutrition companion',
    phase: 'brand',
    characterState: 'greeting',
    characterFeedbackKey: 'greeting',
    skipButton: true,
    animationType: 'spring',
  },
  {
    id: 3,
    type: 'welcome',
    title: 'AI Photo Scan',
    subtitle: 'Snap a photo. Get instant nutrition insights powered by AI.',
    phase: 'brand',
    showSocialProof: true,
    animationType: 'gradient',
    characterState: 'explaining',
  },
  
  // ============ Phase 2: 轻松开始 (P4-5) ============
  {
    id: 4,
    type: 'text_input',
    title: "What's your name?",
    subtitle: "We'll use this to personalize your experience",
    storeKey: 'name',
    phase: 'start',
    textConfig: {
      placeholder: 'Enter your name',
      maxLength: 30
    },
    animationType: 'spring',
    characterState: 'listening',
  },
  {
    id: 5,
    type: 'combined_welcome_goal',
    title: "Nice to meet you, {{name}}!",
    subtitle: 'Choose your main goal',
    storeKey: 'goal',
    phase: 'start',
    usePersonalization: true,
    options: [
      { id: 'lose_weight', icon: 'TrendingDown', title: 'Lose Weight', subtitle: 'Burn fat, get lighter' },
      { id: 'build_muscle', icon: 'Dumbbell', title: 'Build Muscle', subtitle: 'Gain strength and muscle' },
      { id: 'maintain', icon: 'Scale', title: 'Maintain', subtitle: 'Keep current weight' }
    ],
    celebrateAfter: false,
    animationType: 'stagger',
    characterState: 'happy',
    characterFeedbackKey: 'goal_selection',
  },
  
  // ============ 价值页 A: AI 扫描（Goal 后，展示核心功能）============
  {
    id: 6,
    type: 'value_prop',
    title: 'Snap & Know in Seconds',
    subtitle: 'Our AI instantly analyzes any meal photo for calories, macros, and ingredients.',
    phase: 'start',
    showSocialProof: false,
    characterState: 'excited',
    characterFeedbackKey: 'value_ai_scan',
    valuePropType: 'ai_scan',
  },
  
  // ============ Phase 3: 了解你 (P7-12) ============
  {
    id: 7,
    type: 'question_single',
    title: "What's your gender?",
    subtitle: 'This helps us calculate more accurately',
    storeKey: 'gender',
    phase: 'profile',
    skipButton: true,
    options: [
      { id: 'male', icon: 'User', title: 'Male', subtitle: '' },
      { id: 'female', icon: 'User', title: 'Female', subtitle: '' },
      { id: 'other', icon: 'Users', title: 'Other', subtitle: '' }
    ],
    showInstantInsight: true,
    autoAdvance: true,
    characterState: 'listening',
    characterFeedbackKey: 'gender_selection',
  },
  {
    id: 8,
    type: 'number_input',
    title: 'How old are you?',
    subtitle: 'This helps us calculate your basal metabolic rate',
    storeKey: 'age',
    phase: 'profile',
    numberConfig: {
      min: 16,
      max: 80,
      unit: 'years',
      step: 1,
      defaultValue: 25
    },
    characterState: 'listening',
    characterFeedbackKey: 'age_input',
  },
  {
    id: 9,
    type: 'combined_height_weight',
    title: 'Your height and weight',
    subtitle: 'We need this to calculate your BMI',
    storeKey: ['height', 'currentWeight'],
    phase: 'profile',
    showPrivacyBadge: true,
    numberConfig: {
      min: 140,
      max: 220,
      unit: 'cm',
      step: 1,
      defaultValue: 170
    },
    characterState: 'listening',
    characterFeedbackKey: 'height_weight',
  },
  
  // ============ 价值页 B: 个性化（身高体重后，承诺定制体验）============
  {
    id: 10,
    type: 'value_prop',
    title: 'Personalized Just for You',
    subtitle: 'Smart recommendations based on your goals, preferences, and progress.',
    phase: 'profile',
    showSocialProof: true,
    characterState: 'explaining',
    characterFeedbackKey: 'value_personalized',
    valuePropType: 'personalized',
  },
  
  {
    id: 11,
    type: 'question_single',
    title: "How active are you?",
    subtitle: 'This helps us calculate your daily calorie needs',
    storeKey: 'activityLevel',
    phase: 'profile',
    options: [
      { id: 'sedentary', icon: 'Sofa', title: 'Not Very Active', subtitle: 'Little or no exercise' },
      { id: 'moderate', icon: 'Walk', title: 'Moderately Active', subtitle: '2-4 days/week' },
      { id: 'active', icon: 'Flame', title: 'Very Active', subtitle: '5+ days/week' }
    ],
    autoAdvance: true,
    characterState: 'listening',
    characterFeedbackKey: 'activity_level',
  },
  {
    id: 12,
    type: 'number_input',
    title: "What's your target weight?",
    subtitle: 'Set a healthy achievable goal',
    storeKey: 'targetWeight',
    phase: 'profile',
    numberConfig: {
      min: 40,
      max: 150,
      unit: 'kg',
      step: 0.5,
      defaultValue: 65
    },
    showInstantInsight: true,
    celebrateAfter: false,
    characterState: 'encouraging',
    characterFeedbackKey: 'target_weight',
  },
  
  // ============ Phase 4: 价值交付 (P13-14) ============
  {
    id: 13,
    type: 'loading',
    title: 'Analyzing your data...',
    subtitle: '',
    phase: 'value',
    autoAdvance: true,
    usePersonalization: true,
    characterState: 'thinking',
  },
  {
    id: 14,
    type: 'result',
    title: "{{name}}'s Personal Plan",
    subtitle: "Based on your data, we've created this plan for you",
    phase: 'value',
    usePersonalization: true,
    showLossAversion: true,
    animationType: 'stagger',
    characterState: 'proud',
    characterFeedbackKey: 'result_page',
  },
  
  // ============ Phase 5: 体验启动 (P15-16) ============
  // Scan Game 紧跟 Result，叙事："看了你的计划，来试试记录第一餐"
  {
    id: 15,
    type: 'game_scan',
    title: 'Try AI Scan',
    subtitle: 'Hold to scan the food below, experience AI magic',
    phase: 'action',
    characterState: 'excited',
  },
  
  // ============ 价值页 C: 进度追踪（体验后，强化坚持）============
  {
    id: 16,
    type: 'value_prop',
    title: 'Track your progress',
    subtitle: 'Watch your journey unfold with beautiful charts and insights.',
    phase: 'action',
    characterState: 'proud',
    characterFeedbackKey: 'value_progress',
    valuePropType: 'progress_tracking',
  },
  
  // ============ Phase 6: 权限申请 (P17) ============
  {
    id: 17,
    type: 'permission',
    title: 'Stay on Track',
    subtitle: "Get gentle reminders to log meals and celebrate your wins",
    storeKey: 'notificationEnabled',
    phase: 'permission',
    skipButton: true,
    characterState: 'encouraging',
    characterFeedbackKey: 'permission_notification',
    permissionType: 'notification',
    permissionBenefits: [
      { icon: '⏰', text: 'Meal reminders at your preferred times' },
      { icon: '🎯', text: 'Weekly progress summaries' },
      { icon: '💪', text: 'Motivational nudges when you need them' }
    ],
  },
  
  // ============ 价值页 D: 隐私安全（权限后，给用户安心）============
  {
    id: 18,
    type: 'value_prop',
    title: 'Your data stays private',
    subtitle: 'Your health data is encrypted and never shared.',
    phase: 'permission',
    characterState: 'explaining',
    characterFeedbackKey: 'value_privacy',
    valuePropType: 'privacy',
  },
  {
    id: 19,
    type: 'transition',
    title: "You're All Set!",
    subtitle: "Ready to start your health journey with VitaFlow",
    phase: 'complete',
    usePersonalization: true,
    characterState: 'happy',
    characterFeedbackKey: 'complete',
  },
  
  // ============ Phase 8: 注册账号 (P20) ============
  {
    id: 20,
    type: 'account',
    title: 'Create your account',
    subtitle: 'Sign in to sync your data across devices',
    phase: 'account',
    characterState: 'encouraging',
  },
]

// 获取指定步骤的配置
export function getScreenConfigProduction(step: number): ScreenConfigProduction | undefined {
  return screensConfigProduction.find(s => s.id === step)
}

// 获取阶段信息
export function getPhaseInfo(phase: string): { name: string; color: string } {
  const phases: Record<string, { name: string; color: string }> = {
    brand: { name: '欢迎', color: '#7C3AED' },
    start: { name: '开始', color: '#00F5A0' },
    profile: { name: '了解你', color: '#00D4AA' },
    value: { name: '计划', color: '#F59E0B' },
    permission: { name: '权限', color: '#F59E0B' },
    action: { name: '体验', color: '#00F5A0' },
    complete: { name: '完成', color: '#7C3AED' },
    account: { name: '注册', color: '#0F172A' },
  }
  return phases[phase] || { name: phase, color: '#2B2735' }
}

// Production 版本摘要
export const PRODUCTION_FLOW_SUMMARY = {
  totalPages: 20,
  phases: {
    brand: 3,       // P1-3 (Launch, Introduction, Welcome)
    start: 3,       // P4-6 (Name, Goal, AI Scan Value)
    profile: 6,     // P7-12 (Gender, Age, Height/Weight, Personalized Value, Activity, Target)
    value: 2,       // P13-14 (Loading, Result)
    action: 2,      // P15-16 (Scan Game, Progress Tracking Value)
    permission: 2,  // P17-18 (Notification, Privacy Value)
    complete: 1,    // P19 (Transition)
    account: 1,     // P20 (Create Account)
  },
  keyFeatures: [
    '页面合并：欢迎+目标、身高+体重',
    '价值页叙事穿插：4页价值页按叙事逻辑分布',
    '  - Goal 后：AI扫描价值页（展示核心功能）',
    '  - Height/Weight 后：个性化价值页（承诺定制体验）',
    '  - Scan Game 后：进度追踪价值页（强化坚持）',
    '  - Permission 后：隐私安全价值页（给用户安心）',
    'Scan Game 紧跟 Result：叙事连贯，"看了计划，来试试记录第一餐"',
    '权限申请：体验后再请求，转化率更高',
  ],
  expectedMetrics: {
    completionRate: '75-85%',
    firstScanRate: '85%+',
    permissionAcceptRate: '70%+',
    avgCompletionTime: '2.5-3min',
  }
}
