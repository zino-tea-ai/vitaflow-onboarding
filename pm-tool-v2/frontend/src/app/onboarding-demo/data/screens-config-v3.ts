// VitaFlow Onboarding V3 - 50页顶级优化流程配置
// 基于深度竞品分析 + 心理学最佳实践 + 内容逻辑优化
// 核心改进：
// 1. 流程扩展至 50 页（基于竞品分析建议）
// 2. 价值穿插策略：每 5-7 个问题后插入价值页
// 3. 认知负荷管理：确保连续问题复杂度不超过 5
// 4. 上下文连贯性：相关问题分组收集
// 5. 条件分支逻辑：根据用户选择动态调整
// 6. 阶段化进度：清晰的阶段划分和里程碑

import { ScreenConfig, ScreenType, ScreenOption } from './screens-config-v2'

// V3 扩展的配置字段
export interface ScreenConfigV3 extends ScreenConfig {
  // V3 新增字段
  milestone?: boolean  // 是否为里程碑页面
  socialProof?: boolean  // 是否显示社会证明
  personalizationLevel?: 'none' | 'name' | 'full'  // 个性化程度
  staggerDelay?: number  // Stagger 动画延迟
  cognitiveLoad?: number  // 认知负荷评分
  valuePropTiming?: 'early' | 'mid' | 'late' | 'pre_conversion'  // 价值展示时机
  conditionalSkip?: {
    condition: string  // 条件表达式
    skipIf: boolean
  }  // 条件跳过逻辑
}

export const screensConfigV3: ScreenConfigV3[] = [
  // ============ Phase 1: 品牌建立 (P1-3) ============
  {
    id: 1,
    type: 'launch',
    title: 'VitaFlow',
    subtitle: 'Your AI Nutrition Companion',
    phase: 'brand',
    autoAdvance: true,
    animationType: 'scale',
    cognitiveLoad: 0,
    personalizationLevel: 'none',
    milestone: false
  },
  {
    id: 2,
    type: 'welcome',
    title: 'Calorie tracking made easy',
    subtitle: 'Snap a photo. Get instant nutrition insights powered by AI.',
    phase: 'brand',
    animationType: 'fade',
    cognitiveLoad: 0,
    personalizationLevel: 'none',
    socialProof: true  // 显示用户数
  },
  {
    id: 3,
    type: 'value_prop',
    title: 'How it works',
    subtitle: '3 minutes to create your personalized plan',
    phase: 'brand',
    cognitiveLoad: 0,
    personalizationLevel: 'none',
    valuePropTiming: 'early'
  },
  
  // ============ Phase 2: 目标设定 (P4-9) ============
  {
    id: 4,
    type: 'text_input',
    title: "What should we call you?",
    subtitle: "We'll use this to personalize your experience",
    storeKey: 'name',
    phase: 'goals',
    textConfig: {
      placeholder: 'Enter your name',
      maxLength: 30
    },
    cognitiveLoad: 2,
    personalizationLevel: 'name'
  },
  {
    id: 5,
    type: 'transition',
    title: "Nice to meet you, {{name}}! 👋",
    subtitle: "We're excited to be part of your health journey. Let's create a plan that works for you.",
    phase: 'goals',
    usePersonalization: true,
    autoAdvance: true,
    animationType: 'spring',
    cognitiveLoad: 0,
    personalizationLevel: 'name'
  },
  {
    id: 6,
    type: 'question_single',
    title: "What's your main goal?",
    storeKey: 'goal',
    phase: 'goals',
    options: [
      { id: 'lose_weight', icon: 'TrendingDown', title: 'Lose Weight', subtitle: 'Burn fat and feel lighter' },
      { id: 'build_muscle', icon: 'Dumbbell', title: 'Build Muscle', subtitle: 'Gain strength and mass' },
      { id: 'maintain_weight', icon: 'Scale', title: 'Maintain Weight', subtitle: 'Stay at your current level' }
    ],
    autoAdvance: true,
    cognitiveLoad: 1,
    personalizationLevel: 'name'
  },
  {
    id: 7,
    type: 'question_single',
    title: "What's your biological sex?",
    subtitle: 'This helps us calculate your metabolism accurately',
    storeKey: 'gender',
    phase: 'goals',
    options: [
      { id: 'female', icon: 'Venus', title: 'Female' },
      { id: 'male', icon: 'Mars', title: 'Male' },
      { id: 'other', icon: 'CircleDot', title: 'Other / Prefer not to say' }
    ],
    autoAdvance: true,
    cognitiveLoad: 1,
    personalizationLevel: 'name'
  },
  {
    id: 8,
    type: 'transition',
    title: "Great choice, {{name}}! 🎯",
    subtitle: "Your goal is totally achievable. Let's learn more about you.",
    phase: 'goals',
    usePersonalization: true,
    animationType: 'spring',
    cognitiveLoad: 0,
    personalizationLevel: 'name',
    milestone: true  // Phase 2 完成里程碑
  },
  
  // ============ Phase 3: 活动习惯 (P9-13) ============
  {
    id: 9,
    type: 'question_single',
    title: 'How active are you?',
    subtitle: 'Be honest for the best results',
    storeKey: 'activityLevel',
    phase: 'habits',
    options: [
      { id: 'sedentary', icon: 'Sofa', title: 'Sedentary', subtitle: 'Little to no exercise' },
      { id: 'light', icon: 'Footprints', title: 'Lightly Active', subtitle: '1-3 days/week' },
      { id: 'moderate', icon: 'Bike', title: 'Moderately Active', subtitle: '3-5 days/week' },
      { id: 'active', icon: 'Flame', title: 'Very Active', subtitle: '6-7 days/week' }
    ],
    autoAdvance: true,
    cognitiveLoad: 1,
    personalizationLevel: 'name'
  },
  {
    id: 10,
    type: 'question_single',
    title: 'How often do you work out?',
    storeKey: 'workoutFrequency',
    phase: 'habits',
    options: [
      { id: 'rarely', icon: 'Moon', title: 'Rarely', subtitle: 'Workouts are not my thing yet' },
      { id: 'sometimes', icon: 'Sun', title: 'Sometimes', subtitle: 'A few times a month' },
      { id: 'often', icon: 'Zap', title: 'Regularly', subtitle: 'Multiple times a week' }
    ],
    autoAdvance: true,
    cognitiveLoad: 1,
    personalizationLevel: 'name'
  },
  {
    id: 11,
    type: 'transition',
    title: "Perfect! 💪",
    subtitle: "Now let's personalize your plan with a few body measurements.",
    phase: 'habits',
    usePersonalization: true,
    animationType: 'spring',
    cognitiveLoad: 0,
    personalizationLevel: 'name'
  },
  {
    id: 12,
    type: 'value_prop',
    title: 'Why we need this',
    subtitle: 'Your body metrics help us calculate your exact calorie needs',
    phase: 'habits',
    cognitiveLoad: 0,
    personalizationLevel: 'name',
    valuePropTiming: 'mid'
  },
  
  // ============ Phase 4: 身体数据 (P13-21) ============
  {
    id: 13,
    type: 'number_input',
    title: 'How old are you?',
    storeKey: 'age',
    phase: 'biometrics',
    numberConfig: {
      min: 16,
      max: 100,
      unit: 'years',
      step: 1,
      defaultValue: 28
    },
    cognitiveLoad: 1.5,
    personalizationLevel: 'name'
  },
  {
    id: 14,
    type: 'number_input',
    title: "What's your height?",
    storeKey: 'height',
    phase: 'biometrics',
    numberConfig: {
      min: 140,
      max: 220,
      unit: 'cm',
      step: 1,
      defaultValue: 170
    },
    cognitiveLoad: 1.5,
    personalizationLevel: 'name'
  },
  {
    id: 15,
    type: 'number_input',
    title: "What's your current weight?",
    storeKey: 'currentWeight',
    phase: 'biometrics',
    numberConfig: {
      min: 40,
      max: 200,
      unit: 'kg',
      step: 0.5,
      defaultValue: 70
    },
    cognitiveLoad: 1.5,
    personalizationLevel: 'name'
  },
  {
    id: 16,
    type: 'transition',
    title: "Almost there! ⏳",
    subtitle: "Just a couple more questions to build your perfect plan.",
    phase: 'biometrics',
    usePersonalization: true,
    animationType: 'spring',
    cognitiveLoad: 0,
    personalizationLevel: 'name'
  },
  {
    id: 17,
    type: 'number_input',
    title: "What's your goal weight?",
    storeKey: 'targetWeight',
    phase: 'biometrics',
    numberConfig: {
      min: 40,
      max: 200,
      unit: 'kg',
      step: 0.5,
      defaultValue: 65
    },
    cognitiveLoad: 1.5,
    personalizationLevel: 'full',
    conditionalSkip: {
      condition: 'goal === "maintain_weight"',
      skipIf: false  // 保持体重的用户也需要目标体重
    }
  },
  {
    id: 18,
    type: 'question_single',
    title: 'How fast do you want to reach your goal?',
    subtitle: 'A slower pace is more sustainable long-term',
    storeKey: 'weeklyLossRate',
    phase: 'biometrics',
    options: [
      { id: '0.5', icon: 'Turtle', title: 'Slow & Steady', subtitle: '0.5 kg per week' },
      { id: '1', icon: 'Rabbit', title: 'Recommended', subtitle: '1 kg per week' },
      { id: '1.5', icon: 'Rocket', title: 'Aggressive', subtitle: '1.5 kg per week' }
    ],
    autoAdvance: true,
    cognitiveLoad: 1,
    personalizationLevel: 'full',
    conditionalSkip: {
      condition: 'goal === "maintain_weight"',
      skipIf: true  // 保持体重跳过减重速度
    }
  },
  {
    id: 19,
    type: 'transition',
    title: "You can do it, {{name}}! 🔥",
    subtitle: "Based on your goal, you could reach {{targetWeight}} kg by March 2026. Every journey begins with a single step.",
    phase: 'biometrics',
    usePersonalization: true,
    animationType: 'spring',
    cognitiveLoad: 0,
    personalizationLevel: 'full',
    milestone: true  // Phase 4 完成里程碑
  },
  
  // ============ Phase 5: 第一个权限 - Health (P20-22) ============
  {
    id: 20,
    type: 'value_prop',
    title: 'Connect Apple Health',
    subtitle: 'Sync your activity data for more accurate calorie calculations',
    phase: 'permission_health',
    cognitiveLoad: 0,
    personalizationLevel: 'name',
    valuePropTiming: 'mid'
  },
  {
    id: 21,
    type: 'permission',
    title: 'Connect Apple Health',
    subtitle: 'Sync your activity data for more accurate calorie calculations',
    storeKey: 'healthKitConnected',
    phase: 'permission_health',
    skipButton: true,
    cognitiveLoad: 1.5,
    personalizationLevel: 'name'
  },
  
  // ============ Phase 6: 饮食偏好 (P22-28) ============
  {
    id: 22,
    type: 'question_single',
    title: 'Any dietary preferences?',
    storeKey: 'dietaryPreferences',
    phase: 'preferences',
    skipButton: true,
    options: [
      { id: 'none', icon: 'Utensils', title: 'No restrictions' },
      { id: 'vegetarian', icon: 'Leaf', title: 'Vegetarian' },
      { id: 'vegan', icon: 'Vegan', title: 'Vegan' },
      { id: 'keto', icon: 'Beef', title: 'Keto / Low-carb' },
      { id: 'halal', icon: 'Moon', title: 'Halal' },
      { id: 'kosher', icon: 'Star', title: 'Kosher' }
    ],
    cognitiveLoad: 1,
    personalizationLevel: 'name'
  },
  {
    id: 23,
    type: 'question_multi',
    title: 'Any food allergies?',
    storeKey: 'allergies',
    phase: 'preferences',
    skipButton: true,
    options: [
      { id: 'nuts', icon: 'AlertCircle', title: 'Nuts' },
      { id: 'dairy', icon: 'Milk', title: 'Dairy' },
      { id: 'gluten', icon: 'Wheat', title: 'Gluten' },
      { id: 'shellfish', icon: 'Fish', title: 'Shellfish' },
      { id: 'none', icon: 'CheckCircle', title: 'None' }
    ],
    cognitiveLoad: 2,
    personalizationLevel: 'name',
    conditionalSkip: {
      condition: 'dietaryPreferences.includes("none")',
      skipIf: false  // 即使无限制也可能有过敏
    }
  },
  {
    id: 24,
    type: 'question_multi',
    title: "Foods you don't like?",
    storeKey: 'dislikes',
    phase: 'preferences',
    skipButton: true,
    options: [
      { id: 'vegetables', icon: 'Carrot', title: 'Vegetables' },
      { id: 'fruits', icon: 'Apple', title: 'Fruits' },
      { id: 'meat', icon: 'Drumstick', title: 'Meat' },
      { id: 'seafood', icon: 'Fish', title: 'Seafood' },
      { id: 'none', icon: 'CheckCircle', title: 'I like everything' }
    ],
    cognitiveLoad: 2,
    personalizationLevel: 'name'
  },
  {
    id: 25,
    type: 'transition',
    title: "Great! 🎉",
    subtitle: "We're building a plan that fits your preferences perfectly.",
    phase: 'preferences',
    usePersonalization: true,
    animationType: 'spring',
    cognitiveLoad: 0,
    personalizationLevel: 'name'
  },
  {
    id: 26,
    type: 'question_single',
    title: 'How often do you cook?',
    storeKey: 'cookingFrequency',
    phase: 'preferences',
    skipButton: true,
    options: [
      { id: 'daily', icon: 'ChefHat', title: 'Daily' },
      { id: 'often', icon: 'UtensilsCrossed', title: 'Often' },
      { id: 'sometimes', icon: 'Clock', title: 'Sometimes' },
      { id: 'rarely', icon: 'Coffee', title: 'Rarely' }
    ],
    cognitiveLoad: 1,
    personalizationLevel: 'name'
  },
  {
    id: 27,
    type: 'question_single',
    title: 'How often do you eat out?',
    storeKey: 'eatingOutFrequency',
    phase: 'preferences',
    skipButton: true,
    options: [
      { id: 'daily', icon: 'Store', title: 'Daily' },
      { id: 'often', icon: 'Calendar', title: '3-4 times/week' },
      { id: 'sometimes', icon: 'CalendarDays', title: '1-2 times/week' },
      { id: 'rarely', icon: 'Home', title: 'Rarely' }
    ],
    cognitiveLoad: 1,
    personalizationLevel: 'name'
  },
  
  // ============ Phase 7: 伏笔问题 (P28-33) ============
  {
    id: 28,
    type: 'question_single',
    title: 'How did you hear about us?',
    storeKey: 'acquisitionChannel',
    phase: 'foreshadow',
    skipButton: true,
    options: [
      { id: 'social', icon: 'Instagram', title: 'Social Media' },
      { id: 'friend', icon: 'Users', title: 'Friend or Family' },
      { id: 'search', icon: 'Search', title: 'App Store Search' },
      { id: 'ad', icon: 'Megaphone', title: 'Advertisement' },
      { id: 'other', icon: 'MoreHorizontal', title: 'Other' }
    ],
    autoAdvance: true,
    cognitiveLoad: 1,
    personalizationLevel: 'name'
  },
  {
    id: 29,
    type: 'question_single',
    title: 'Have you used a calorie tracking app before?',
    storeKey: 'previousAppExperience',
    phase: 'foreshadow',
    options: [
      { id: 'yes', icon: 'CheckCircle', title: 'Yes, I have' },
      { id: 'no', icon: 'Circle', title: "No, this is my first" }
    ],
    autoAdvance: true,
    cognitiveLoad: 1,
    personalizationLevel: 'name'
  },
  {
    id: 30,
    type: 'question_multi',
    title: "What's stopped you from reaching your goals before?",
    storeKey: 'previousBarriers',
    phase: 'foreshadow',
    skipButton: true,
    options: [
      { id: 'time', icon: 'Clock', title: 'Not enough time' },
      { id: 'motivation', icon: 'Battery', title: 'Lost motivation' },
      { id: 'tracking', icon: 'ListTodo', title: 'Tracking was too tedious' },
      { id: 'knowledge', icon: 'BookOpen', title: "Didn't know what to eat" },
      { id: 'none', icon: 'Sparkles', title: 'Nothing — this is my first try!' }
    ],
    cognitiveLoad: 2,
    personalizationLevel: 'name'
  },
  {
    id: 31,
    type: 'transition',
    title: "We understand, {{name}} 💙",
    subtitle: "That's exactly why we built VitaFlow — to make tracking effortless.",
    phase: 'foreshadow',
    usePersonalization: true,
    animationType: 'spring',
    cognitiveLoad: 0,
    personalizationLevel: 'name'
  },
  {
    id: 32,
    type: 'question_multi',
    title: 'Any other goals you want to achieve?',
    storeKey: 'secondaryGoals',
    phase: 'foreshadow',
    skipButton: true,
    options: [
      { id: 'energy', icon: 'Zap', title: 'More energy' },
      { id: 'sleep', icon: 'Moon', title: 'Better sleep' },
      { id: 'skin', icon: 'Sparkles', title: 'Clearer skin' },
      { id: 'mood', icon: 'Smile', title: 'Improved mood' },
      { id: 'focus', icon: 'Brain', title: 'Better focus' }
    ],
    cognitiveLoad: 2,
    personalizationLevel: 'name'
  },
  
  // ============ Phase 8: 第二个权限 - Notification (P33-35) ============
  {
    id: 33,
    type: 'value_prop',
    title: 'Stay consistent with gentle reminders',
    subtitle: '89% of successful users enable notifications to build healthy habits',
    phase: 'permission_notification',
    cognitiveLoad: 0,
    personalizationLevel: 'name',
    socialProof: true,
    valuePropTiming: 'mid'
  },
  {
    id: 34,
    type: 'permission',
    title: 'Enable Reminders',
    subtitle: "We'll send gentle nudges to help you log your meals",
    storeKey: 'notificationsEnabled',
    phase: 'permission_notification',
    skipButton: true,
    cognitiveLoad: 1.5,
    personalizationLevel: 'name'
  },
  {
    id: 35,
    type: 'text_input',
    title: 'Have a referral code?',
    subtitle: 'Enter it here to unlock special rewards',
    storeKey: 'referralCode',
    phase: 'extra',
    skipButton: true,
    textConfig: {
      placeholder: 'Enter code (optional)',
      maxLength: 20
    },
    cognitiveLoad: 2,
    personalizationLevel: 'name'
  },
  
  // ============ Phase 9: Loading + Result (P36-40) ============
  {
    id: 36,
    type: 'loading',
    title: 'Analyzing your profile, {{name}}...',
    subtitle: 'Creating your personalized nutrition plan',
    phase: 'value',
    autoAdvance: true,
    usePersonalization: true,
    animationType: 'fade',
    cognitiveLoad: 0,
    personalizationLevel: 'full',
    valuePropTiming: 'late'
  },
  {
    id: 37,
    type: 'result',
    title: '{{name}}, your plan is ready!',
    subtitle: 'Based on your goals and body metrics',
    phase: 'value',
    usePersonalization: true,
    cognitiveLoad: 0.5,
    personalizationLevel: 'full',
    milestone: true  // Phase 9 完成里程碑
  },
  {
    id: 38,
    type: 'value_prop',
    title: 'Track meals in seconds',
    subtitle: 'Just snap a photo — our AI does the rest',
    phase: 'value',
    cognitiveLoad: 0,
    personalizationLevel: 'full',
    valuePropTiming: 'late'
  },
  {
    id: 39,
    type: 'soft_commit',
    title: "Ready to start your journey?",
    subtitle: "Tap below to see how our AI technology works",
    phase: 'value',
    softCommitText: "Yes, show me! 📸",
    animationType: 'spring',
    cognitiveLoad: 1,
    personalizationLevel: 'full'
  },
  
  // ============ Phase 10: AI 扫描游戏 (P40-41) ============
  {
    id: 40,
    type: 'game_scan',
    title: 'Hold to Scan',
    subtitle: 'Press and hold to see AI nutrition analysis in action',
    phase: 'game',
    cognitiveLoad: 0.5,
    personalizationLevel: 'full'
  },
  {
    id: 41,
    type: 'transition',
    title: "Amazing! 🎉",
    subtitle: "That's how easy it is to track your meals with VitaFlow.",
    phase: 'game',
    usePersonalization: true,
    animationType: 'spring',
    cognitiveLoad: 0,
    personalizationLevel: 'full'
  },
  
  // ============ Phase 11: 第三个权限 - ATT (P42-43) ============
  {
    id: 42,
    type: 'value_prop',
    title: 'Get personalized recommendations',
    subtitle: 'Allow tracking to see content tailored to your health goals',
    phase: 'permission_att',
    cognitiveLoad: 0,
    personalizationLevel: 'name',
    valuePropTiming: 'pre_conversion'
  },
  {
    id: 43,
    type: 'permission',
    title: 'Help us improve VitaFlow',
    subtitle: 'Allow tracking to see personalized content and measure app improvements',
    storeKey: 'trackingAllowed',
    phase: 'permission_att',
    skipButton: true,
    cognitiveLoad: 1.5,
    personalizationLevel: 'name'
  },
  
  // ============ Phase 12: 成功过渡 (P44-46) ============
  {
    id: 44,
    type: 'transition',
    title: "You're all set, {{name}}! 🎉",
    subtitle: 'Your personalized nutrition journey starts now',
    phase: 'pre_conversion',
    usePersonalization: true,
    animationType: 'spring',
    cognitiveLoad: 0,
    personalizationLevel: 'full',
    milestone: true  // Phase 12 完成里程碑
  },
  {
    id: 45,
    type: 'value_prop',
    title: 'Join 50,000+ people transforming their health',
    subtitle: 'See what others are saying about VitaFlow',
    phase: 'pre_conversion',
    cognitiveLoad: 0,
    personalizationLevel: 'name',
    socialProof: true,
    valuePropTiming: 'pre_conversion'
  },
  
  // ============ Phase 13: 付费墙 + 轮盘 (P46-49) ============
  {
    id: 46,
    type: 'paywall',
    title: '{{name}}, start your transformation',
    subtitle: 'Unlock all premium features',
    phase: 'conversion',
    usePersonalization: true,
    cognitiveLoad: 2,
    personalizationLevel: 'full',
    valuePropTiming: 'pre_conversion'
  },
  {
    id: 47,
    type: 'game_spin',
    title: "Wait, {{name}}! Here's a gift 🎁",
    subtitle: 'Spin the wheel for an exclusive discount',
    phase: 'conversion',
    usePersonalization: true,
    cognitiveLoad: 0.5,
    personalizationLevel: 'full'
  },
  {
    id: 48,
    type: 'paywall',
    title: '🎉 50% OFF Unlocked!',
    subtitle: '{{name}}, claim your exclusive discount now',
    phase: 'conversion',
    usePersonalization: true,
    cognitiveLoad: 2,
    personalizationLevel: 'full'
  },
  
  // ============ Phase 14: 成功 + 账号 (P49-50) ============
  {
    id: 49,
    type: 'celebration',
    title: 'Welcome to VitaFlow, {{name}}! 🎊',
    subtitle: 'Your transformation journey begins now',
    phase: 'success',
    usePersonalization: true,
    animationType: 'spring',
    cognitiveLoad: 0,
    personalizationLevel: 'full',
    milestone: true  // 完成里程碑
  },
  {
    id: 50,
    type: 'account',
    title: 'Create your account',
    subtitle: 'Sign in to sync your data across devices',
    phase: 'success',
    cognitiveLoad: 2,
    personalizationLevel: 'name'
  }
]

// 获取当前屏幕配置
export function getScreenConfigV3(step: number): ScreenConfigV3 | undefined {
  return screensConfigV3.find(s => s.id === step)
}

// 获取阶段进度
export function getPhaseProgressV3(currentStep: number): { phase: string; progress: number } {
  const current = getScreenConfigV3(currentStep)
  if (!current) return { phase: 'unknown', progress: 0 }
  
  const phaseScreens = screensConfigV3.filter(s => s.phase === current.phase)
  const indexInPhase = phaseScreens.findIndex(s => s.id === currentStep)
  
  return {
    phase: current.phase,
    progress: (indexInPhase + 1) / phaseScreens.length
  }
}

// V3 版本的流程特点摘要
export const V3_FLOW_SUMMARY = {
  totalPages: 50,
  questionPages: 20,
  valuePages: 8,
  transitionPages: 10,
  permissionPages: 3,
  gamePages: 2,
  conversionPages: 4,
  
  // 关键改进
  improvements: [
    '流程扩展：40页 → 50页（基于竞品分析）',
    '价值穿插：每 5-7 个问题后插入价值页',
    '认知负荷管理：连续问题复杂度不超过 5',
    '上下文连贯：相关问题分组收集',
    '条件分支：根据用户选择动态调整',
    '阶段化进度：清晰的阶段划分和里程碑',
    '个性化升级：从 name → full 个性化',
    '社会证明：关键页面显示用户数和评价'
  ]
}
