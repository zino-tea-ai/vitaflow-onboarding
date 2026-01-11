// VitaFlow Onboarding V3 - 个性化文本工具函数
// 扩展支持动态内容、个性化图标、情感化反馈

import { UserData } from '../store/onboarding-store'

/**
 * 替换文本中的 {{name}} 占位符
 * @param text 原始文本
 * @param name 用户姓名
 * @returns 替换后的文本
 */
export function personalizeText(text: string | undefined, name: string | null): string {
  if (!text) return ''
  
  // 如果没有名字，使用 "there" 作为默认值
  const displayName = name?.trim() || 'there'
  
  return text.replace(/\{\{name\}\}/g, displayName)
}

/**
 * 生成个性化文案
 * 根据用户数据和上下文动态生成文案
 */
export function generatePersonalizedCopy(
  template: string,
  userData: UserData,
  context: 'goal' | 'progress' | 'result' | 'paywall' = 'goal'
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
  
  if (context === 'result') {
    if (userData.targetWeight && userData.currentWeight) {
      const diff = Math.abs(userData.targetWeight - userData.currentWeight)
      copy = copy.replace(/\{\{weight_diff\}\}/g, `${diff}kg`)
    }
    
    // 根据目标生成结果文案
    if (userData.goal === 'lose_weight') {
      copy = copy.replace(/\{\{result_text\}\}/g, `You'll lose ${userData.targetWeight ? Math.abs(userData.currentWeight! - userData.targetWeight) : 5}kg`)
    } else if (userData.goal === 'build_muscle') {
      copy = copy.replace(/\{\{result_text\}\}/g, "You'll gain 3kg muscle in 10 weeks")
    }
  }
  
  return copy
}

/**
 * 获取情感化反馈消息
 * 根据进度和用户数据生成鼓励消息
 */
export function getEncouragementMessage(
  progress: number,
  userData: UserData
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
 * 根据用户目标获取个性化图标
 */
export function getPersonalizedIcon(goal: UserData['goal']): string {
  switch (goal) {
    case 'lose_weight':
      return 'TrendingDown'
    case 'build_muscle':
      return 'Dumbbell'
    case 'maintain_weight':
      return 'Scale'
    default:
      return 'Target'
  }
}

/**
 * 根据用户数据生成动态内容
 */
export function getDynamicContent(
  userData: UserData,
  type: 'goal_confirmation' | 'progress_update' | 'result_preview'
): string {
  const name = userData.name || 'there'
  
  switch (type) {
    case 'goal_confirmation':
      if (userData.goal === 'lose_weight' && userData.targetWeight && userData.currentWeight) {
        const diff = Math.abs(userData.currentWeight - userData.targetWeight)
        return `You can do it, ${name}! You'll lose ${diff}kg and feel amazing! 🔥`
      }
      return `Great choice, ${name}! Your goal is totally achievable. 🎯`
      
    case 'progress_update':
      return `You're making great progress, ${name}! Keep going! 💪`
      
    case 'result_preview':
      if (userData.goal === 'lose_weight' && userData.targetWeight) {
        return `Based on your goal, you could reach ${userData.targetWeight}kg by March 2026.`
      }
      return `Your personalized plan is ready, ${name}!`
      
    default:
      return ''
  }
}
