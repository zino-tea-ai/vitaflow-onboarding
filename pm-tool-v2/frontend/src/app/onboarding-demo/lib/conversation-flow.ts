// VitaFlow Onboarding V3 - 对话流程优化
// 负责引导逻辑、上下文感知文案、动态调整

import { ScreenConfig } from '../data/screens-config-v2'
import { UserData } from '../store/onboarding-store'

/**
 * 根据用户选择动态调整后续内容
 */
export function getNextScreenSequence(
  currentScreen: ScreenConfig,
  userData: UserData
): ScreenConfig[] | null {
  // 如果用户选择"减重"
  if (userData.goal === 'lose_weight') {
    return getWeightLossSequence()
  }
  
  // 如果用户选择"增肌"
  if (userData.goal === 'build_muscle') {
    return getMuscleGainSequence()
  }
  
  // 如果用户选择"保持体重"
  if (userData.goal === 'maintain_weight') {
    return getMaintainWeightSequence()
  }
  
  return null // 使用默认流程
}

/**
 * 减重流程序列
 */
function getWeightLossSequence(): ScreenConfig[] {
  // 返回需要强调的内容
  // 实际实现中，这些会在配置中标记
  return []
}

/**
 * 增肌流程序列
 */
function getMuscleGainSequence(): ScreenConfig[] {
  return []
}

/**
 * 保持体重流程序列
 */
function getMaintainWeightSequence(): ScreenConfig[] {
  return []
}

/**
 * 根据已收集数据调整问题文案
 */
export function getContextualQuestion(
  questionId: string,
  userData: UserData
): { title: string; subtitle?: string } | null {
  // 如果已经知道用户目标是减重
  if (questionId === 'target_weight' && userData.goal === 'lose_weight') {
    return {
      title: "What's your ideal weight?",
      subtitle: "We'll help you get there safely and sustainably"
    }
  }
  
  // 如果用户之前使用过类似 App
  if (questionId === 'barriers' && userData.previousAppExperience === 'yes') {
    return {
      title: "What didn't work for you before?",
      subtitle: "We'll make sure it's different this time"
    }
  }
  
  // 如果用户是健身老手
  if (questionId === 'activityLevel' && userData.workoutFrequency === 'often') {
    return {
      title: "How active are you?",
      subtitle: "We see you work out regularly - that's great!"
    }
  }
  
  return null // 使用默认文案
}

/**
 * 根据用户进度获取鼓励消息
 */
export function getEncouragementMessage(
  progress: number,
  userData: UserData,
  currentPhase: string
): string {
  const name = userData.name || 'there'
  
  if (progress < 0.2) {
    return `Great start, ${name}! 🎯`
  }
  
  if (progress < 0.4) {
    return `You're doing amazing! 💪`
  }
  
  if (progress < 0.6) {
    return `Keep going, ${name}! You're halfway there! 🔥`
  }
  
  if (progress < 0.8) {
    return `Almost there, ${name}! You've got this! ⚡`
  }
  
  return `You're almost done! Final push! 🚀`
}

/**
 * 根据用户选择生成个性化文案
 */
export function generatePersonalizedCopy(
  template: string,
  userData: UserData,
  context: 'goal' | 'progress' | 'result' | 'paywall'
): string {
  let copy = template
  const name = userData.name || 'there'
  
  // 替换姓名
  copy = copy.replace(/\{\{name\}\}/g, name)
  
  // 根据上下文替换内容
  if (context === 'goal') {
    if (userData.goal === 'lose_weight') {
      copy = copy.replace(/\{\{goal_text\}\}/g, 'lose weight')
      copy = copy.replace(/\{\{motivation\}\}/g, 'feel lighter and more confident')
    } else if (userData.goal === 'build_muscle') {
      copy = copy.replace(/\{\{goal_text\}\}/g, 'build muscle')
      copy = copy.replace(/\{\{motivation\}\}/g, 'gain strength and mass')
    } else {
      copy = copy.replace(/\{\{goal_text\}\}/g, 'maintain your weight')
      copy = copy.replace(/\{\{motivation\}\}/g, 'stay healthy and balanced')
    }
  }
  
  if (context === 'result' && userData.targetWeight && userData.currentWeight) {
    const diff = Math.abs(userData.targetWeight - userData.currentWeight)
    copy = copy.replace(/\{\{weight_diff\}\}/g, `${diff}kg`)
  }
  
  return copy
}

/**
 * 获取情感化反馈
 */
export function getEmotionalFeedback(
  userData: UserData,
  milestone: 'first_question' | 'halfway' | 'almost_done' | 'complete'
): string {
  const name = userData.name || 'there'
  
  switch (milestone) {
    case 'first_question':
      return `Nice to meet you, ${name}! 👋 Let's create a plan that works for you.`
    case 'halfway':
      return `You're doing great, ${name}! 💪 We're halfway there.`
    case 'almost_done':
      return `Almost there, ${name}! 🔥 Just a few more questions.`
    case 'complete':
      return `Congratulations, ${name}! 🎉 Your personalized plan is ready!`
    default:
      return `Keep going, ${name}!`
  }
}

/**
 * 根据用户数据调整选项文案
 */
export function getContextualOptions(
  questionId: string,
  userData: UserData
): Array<{ id: string; title: string; subtitle?: string }> | null {
  // 如果用户目标是减重，调整减重速度选项的强调
  if (questionId === 'weeklyLossRate' && userData.goal === 'lose_weight') {
    return [
      {
        id: '0.5',
        title: 'Slow & Steady',
        subtitle: '0.5 kg per week - Most sustainable'
      },
      {
        id: '1',
        title: 'Recommended',
        subtitle: '1 kg per week - Best balance'
      },
      {
        id: '1.5',
        title: 'Aggressive',
        subtitle: '1.5 kg per week - Requires discipline'
      }
    ]
  }
  
  return null
}
