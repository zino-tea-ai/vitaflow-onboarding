// VitaFlow Onboarding V3 - 内容逻辑引擎
// 负责问题顺序优化、价值穿插策略、流程结构优化

import { ScreenConfig } from '../data/screens-config-v2'

/**
 * 问题顺序优化原则
 * 1. 从易到难（Commitment Gradient）
 * 2. 价值穿插策略
 * 3. 上下文连贯性
 */

/**
 * 获取推荐的问题顺序
 * 基于心理学原则：简单选择 → 中等投入 → 高投入
 */
export function getOptimalQuestionOrder(): {
  simple: string[]  // 简单选择（目标方向、性别）
  medium: string[] // 中等投入（身体数据）
  complex: string[] // 高投入（详细偏好）
} {
  return {
    simple: ['goal', 'gender', 'activityLevel'],
    medium: ['age', 'height', 'currentWeight', 'targetWeight'],
    complex: ['dietaryPreferences', 'previousBarriers', 'secondaryGoals']
  }
}

/**
 * 价值穿插策略
 * 每 5-7 个问题后插入价值展示页
 */
export function shouldInsertValueProp(
  currentIndex: number,
  questionCount: number
): boolean {
  // 每 5-7 个问题后插入价值页
  return questionCount > 0 && questionCount % 6 === 0
}

/**
 * 检查问题节奏
 * 确保连续问题不超过 4 个
 */
export function validateQuestionRhythm(
  screens: ScreenConfig[],
  startIndex: number
): { isValid: boolean; needsTransition: boolean } {
  let questionCount = 0
  let maxQuestions = 0
  
  for (let i = startIndex; i < screens.length; i++) {
    const screen = screens[i]
    const isQuestion = [
      'question_single',
      'question_multi',
      'number_input',
      'text_input'
    ].includes(screen.type)
    
    if (isQuestion) {
      questionCount++
      maxQuestions = Math.max(maxQuestions, questionCount)
    } else if (screen.type === 'transition' || screen.type === 'value_prop') {
      questionCount = 0 // 重置计数
    }
  }
  
  return {
    isValid: maxQuestions <= 4,
    needsTransition: maxQuestions > 3
  }
}

/**
 * 上下文连贯性检查
 * 确保相关问题分组，避免逻辑跳跃
 */
export function validateContextCoherence(
  screens: ScreenConfig[]
): { isValid: boolean; issues: string[] } {
  const issues: string[] = []
  
  // 检查身体数据是否连续
  const biometricScreens = screens.filter(s => 
    ['age', 'height', 'currentWeight', 'targetWeight'].includes(s.storeKey || '')
  )
  
  if (biometricScreens.length > 0) {
    const indices = biometricScreens.map(s => screens.indexOf(s))
    const isConsecutive = indices.every((idx, i) => 
      i === 0 || idx === indices[i - 1] + 1
    )
    
    if (!isConsecutive) {
      issues.push('身体数据（年龄、身高、体重）应该连续收集')
    }
  }
  
  // 检查活动数据是否连续
  const activityScreens = screens.filter(s => 
    ['activityLevel', 'workoutFrequency'].includes(s.storeKey || '')
  )
  
  if (activityScreens.length > 0) {
    const indices = activityScreens.map(s => screens.indexOf(s))
    const isConsecutive = indices.every((idx, i) => 
      i === 0 || idx === indices[i - 1] + 1
    )
    
    if (!isConsecutive) {
      issues.push('活动数据（活动水平、运动频率）应该连续收集')
    }
  }
  
  return {
    isValid: issues.length === 0,
    issues
  }
}

/**
 * 获取价值展示的最佳时机
 * 基于流程进度百分比
 */
export function getValuePropTiming(progress: number): {
  shouldShow: boolean
  type: 'early' | 'mid' | 'late' | 'pre_conversion'
} {
  if (progress >= 0.1 && progress < 0.15) {
    return { shouldShow: true, type: 'early' } // 核心价值（AI 扫描）
  }
  if (progress >= 0.4 && progress < 0.5) {
    return { shouldShow: true, type: 'mid' } // 个性化价值（为什么需要这些数据）
  }
  if (progress >= 0.8 && progress < 0.85) {
    return { shouldShow: true, type: 'late' } // 完整价值（个性化计划结果）
  }
  if (progress >= 0.9 && progress < 0.95) {
    return { shouldShow: true, type: 'pre_conversion' } // 对比价值（使用 vs 不使用）
  }
  
  return { shouldShow: false, type: 'early' }
}

/**
 * 流程结构优化建议
 * 基于竞品分析的最佳实践
 */
export interface FlowStructure {
  phase: string
  screens: number[]
  purpose: string
  psychology: string[]
}

export function getRecommendedFlowStructure(): FlowStructure[] {
  return [
    {
      phase: '品牌建立',
      screens: [1, 2, 3],
      purpose: '建立第一印象，传达核心价值',
      psychology: ['Brand Recognition', 'Value Proposition']
    },
    {
      phase: '目标设定',
      screens: [4, 5, 6, 7, 8],
      purpose: '收集用户目标，建立小承诺',
      psychology: ['Commitment & Consistency', 'Personalization']
    },
    {
      phase: '活动习惯',
      screens: [9, 10, 11, 12],
      purpose: '了解用户活动水平',
      psychology: ['Progressive Disclosure']
    },
    {
      phase: '身体数据',
      screens: [13, 14, 15, 16, 17, 18, 19, 20],
      purpose: '收集身体指标，计算个性化计划',
      psychology: ['Commitment & Consistency', 'Immediate Feedback']
    },
    {
      phase: '饮食偏好',
      screens: [21, 22, 23, 24, 25, 26],
      purpose: '了解饮食限制和偏好',
      psychology: ['Personalization']
    },
    {
      phase: '价值建立',
      screens: [27, 28, 29, 30],
      purpose: '展示产品价值，建立信任',
      psychology: ['Reciprocity', 'Value Proposition']
    },
    {
      phase: '伏笔问题',
      screens: [31, 32, 33, 34, 35],
      purpose: '为后续个性化做准备',
      psychology: ['Commitment & Consistency']
    },
    {
      phase: '权限请求',
      screens: [36, 37, 38],
      purpose: '请求通知权限',
      psychology: ['Reciprocity', 'Value Proposition']
    },
    {
      phase: '计划生成',
      screens: [39, 40, 41, 42],
      purpose: '展示个性化结果',
      psychology: ['Labor Illusion', 'Personalization']
    },
    {
      phase: '游戏化体验',
      screens: [43, 44],
      purpose: '增强参与度',
      psychology: ['Gamification', 'Engagement']
    },
    {
      phase: '最终权限',
      screens: [45, 46],
      purpose: '请求 ATT 追踪权限',
      psychology: ['Positive Framing']
    },
    {
      phase: '转化准备',
      screens: [47, 48],
      purpose: '强化社会证明，准备转化',
      psychology: ['Social Proof', 'Loss Aversion']
    },
    {
      phase: '付费墙',
      screens: [49, 50, 51],
      purpose: '完成付费转化',
      psychology: ['Scarcity', 'Urgency', 'Risk Reversal']
    },
    {
      phase: '完成',
      screens: [52, 53],
      purpose: '庆祝完成，引导首次使用',
      psychology: ['Progress Achievement', 'Completion']
    }
  ]
}
