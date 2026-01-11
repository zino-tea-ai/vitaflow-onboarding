// VitaFlow Onboarding V5 - 顶级设计配置
// 去表单化、角色主导、场景沉浸

import { ScreenConfig } from './screens-config'

export interface V5ScreenConfig extends ScreenConfig {
  // 场景配置
  sceneStyle?: 'gradient' | 'particle' | 'nature'
  sceneProgress?: number  // 0-100，用于渐变场景的时间变化
  
  // 角色配置
  characterState?: 'idle' | 'speaking' | 'thinking' | 'happy' | 'celebrating' | 'waving' | 'encouraging'
  characterPosition?: 'center' | 'left' | 'right'
  
  // 对话配置
  dialogText?: string
  dialogTyping?: boolean
  
  // 交互配置
  interactionType?: 'select' | 'input' | 'number' | 'combined' | 'none'
}

// V5 屏幕配置 - 12页精简流程
export const screensConfigV5: V5ScreenConfig[] = [
  // 1. Splash - 品牌启动
  {
    id: 'launch-v5',
    type: 'launch',
    title: 'VitaFlow',
    subtitle: 'Your AI Nutrition Companion',
    phase: 'brand',
    sceneStyle: 'gradient',
    sceneProgress: 0,
    characterState: 'idle',
  },
  
  // 2. Introduction - 角色介绍
  {
    id: 'introduction-v5',
    type: 'introduction',
    title: 'Meet Vita',
    subtitle: '',
    phase: 'brand',
    sceneStyle: 'gradient',
    sceneProgress: 8,
    characterState: 'waving',
    characterPosition: 'center',
    dialogText: "Hi! I'm Vita, and I'm here to help you on your health journey. Let's make this easy together!",
    dialogTyping: true,
  },
  
  // 3. Name Input - 名字输入
  {
    id: 'name-v5',
    type: 'text_input',
    title: "What should I call you?",
    subtitle: '',
    phase: 'profile',
    field: 'name',
    placeholder: 'Your name',
    sceneStyle: 'gradient',
    sceneProgress: 16,
    characterState: 'speaking',
    dialogText: "I'd love to get to know you better. What's your name?",
    interactionType: 'input',
  },
  
  // 4. Goal Selection - 目标选择
  {
    id: 'goal-v5',
    type: 'question_single',
    title: 'What brings you here today?',
    subtitle: '',
    phase: 'goals',
    field: 'primaryGoal',
    options: [
      { id: 'lose-weight', label: 'Lose Weight', description: 'Shed pounds healthily', emoji: '⚖️' },
      { id: 'build-muscle', label: 'Build Muscle', description: 'Get stronger', emoji: '💪' },
      { id: 'eat-healthier', label: 'Eat Healthier', description: 'Better nutrition', emoji: '🥗' },
    ],
    sceneStyle: 'gradient',
    sceneProgress: 25,
    characterState: 'speaking',
    dialogText: "Everyone's journey is unique. What's your main focus?",
    interactionType: 'select',
  },
  
  // 5. Gender Selection - 性别选择
  {
    id: 'gender-v5',
    type: 'question_single',
    title: "Let's personalize your experience",
    subtitle: '',
    phase: 'profile',
    field: 'gender',
    options: [
      { id: 'male', label: 'Male', emoji: '👨' },
      { id: 'female', label: 'Female', emoji: '👩' },
      { id: 'other', label: 'Other', emoji: '🌟' },
    ],
    sceneStyle: 'gradient',
    sceneProgress: 33,
    characterState: 'speaking',
    dialogText: "This helps me give you more accurate recommendations.",
    interactionType: 'select',
  },
  
  // 6. Age Input - 年龄输入
  {
    id: 'age-v5',
    type: 'number_input',
    title: 'How young are you?',
    subtitle: '',
    phase: 'profile',
    field: 'age',
    min: 13,
    max: 100,
    unit: 'years',
    sceneStyle: 'gradient',
    sceneProgress: 42,
    characterState: 'thinking',
    dialogText: "Age is just a number, but it helps me understand your needs better!",
    interactionType: 'number',
  },
  
  // 7. Height & Weight - 合并页
  {
    id: 'body-metrics-v5',
    type: 'combined',
    title: 'Your body metrics',
    subtitle: '',
    phase: 'profile',
    fields: ['height', 'currentWeight'],
    sceneStyle: 'gradient',
    sceneProgress: 50,
    characterState: 'encouraging',
    dialogText: "Don't worry, your data is safe with me. This helps calculate your needs accurately.",
    interactionType: 'combined',
  },
  
  // 8. Activity Level - 活动水平
  {
    id: 'activity-v5',
    type: 'question_single',
    title: 'How active are you?',
    subtitle: '',
    phase: 'goals',
    field: 'activityLevel',
    options: [
      { id: 'sedentary', label: 'Sedentary', description: 'Little to no exercise', emoji: '🛋️' },
      { id: 'light', label: 'Lightly Active', description: '1-3 days/week', emoji: '🚶' },
      { id: 'moderate', label: 'Moderately Active', description: '3-5 days/week', emoji: '🏃' },
      { id: 'very', label: 'Very Active', description: '6-7 days/week', emoji: '🏋️' },
    ],
    sceneStyle: 'gradient',
    sceneProgress: 58,
    characterState: 'speaking',
    dialogText: "Movement matters! How much do you usually move?",
    interactionType: 'select',
  },
  
  // 9. Diet Style - 饮食偏好
  {
    id: 'diet-v5',
    type: 'question_single',
    title: "What's your eating style?",
    subtitle: '',
    phase: 'preferences',
    field: 'dietStyle',
    options: [
      { id: 'omnivore', label: 'Omnivore', description: 'I eat everything', emoji: '🍖' },
      { id: 'vegetarian', label: 'Vegetarian', description: 'No meat', emoji: '🥬' },
      { id: 'vegan', label: 'Vegan', description: 'Plant-based only', emoji: '🌱' },
      { id: 'keto', label: 'Keto', description: 'Low-carb, high-fat', emoji: '🥑' },
    ],
    sceneStyle: 'gradient',
    sceneProgress: 67,
    characterState: 'happy',
    dialogText: "Great progress! Let me know your food preferences.",
    interactionType: 'select',
  },
  
  // 10. Value Proposition - 价值展示
  {
    id: 'value-prop-v5',
    type: 'value_prop',
    title: "Here's what I can do for you",
    subtitle: '',
    phase: 'value',
    sceneStyle: 'gradient',
    sceneProgress: 75,
    characterState: 'encouraging',
    dialogText: "Based on what you've told me, I've got some exciting things planned!",
    features: [
      { icon: 'Camera', title: 'Snap & Track', description: 'Just take a photo of your food' },
      { icon: 'Brain', title: 'AI Analysis', description: 'Instant nutrition breakdown' },
      { icon: 'TrendingUp', title: 'Smart Goals', description: 'Personalized to your needs' },
    ],
  },
  
  // 11. Loading/Analysis - 分析中
  {
    id: 'loading-v5',
    type: 'loading',
    title: 'Creating your plan...',
    subtitle: '',
    phase: 'result',
    sceneStyle: 'particle',
    characterState: 'thinking',
    dialogText: "Give me a moment while I crunch the numbers for you...",
  },
  
  // 12. Result - 结果展示
  {
    id: 'result-v5',
    type: 'result',
    title: 'Your Personalized Plan',
    subtitle: '',
    phase: 'result',
    sceneStyle: 'gradient',
    sceneProgress: 100,
    characterState: 'celebrating',
    dialogText: "Amazing! Your journey starts now. I'll be with you every step of the way!",
  },
]

// 导出总页数
export const totalScreensV5 = screensConfigV5.length

// 获取屏幕配置的辅助函数
export const getV5ScreenConfig = (index: number): V5ScreenConfig | null => {
  return screensConfigV5[index] || null
}

// 根据 ID 获取屏幕
export const getV5ScreenById = (id: string): V5ScreenConfig | null => {
  return screensConfigV5.find(s => s.id === id) || null
}

// 计算进度百分比
export const getV5Progress = (currentStep: number): number => {
  return Math.round((currentStep / totalScreensV5) * 100)
}

export default screensConfigV5
