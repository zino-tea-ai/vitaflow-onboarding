// VitaFlow Onboarding V3 - 认知负荷管理
// 负责问题复杂度评分、负荷验证、自动插入过渡页

import { ScreenConfig, ScreenType } from '../data/screens-config-v2'

/**
 * 问题复杂度评分
 * 用于评估每个页面对用户的认知负荷
 */
export const questionComplexity: Record<ScreenType, number> = {
  'launch': 0,              // 无负荷（自动）
  'welcome': 0,             // 无负荷（阅读）
  'question_single': 1,     // 低负荷（单选）
  'question_multi': 2,      // 中负荷（多选）
  'number_input': 1.5,      // 中低负荷（数字输入）
  'text_input': 2,          // 中负荷（文本输入）
  'value_prop': 0,          // 无负荷（阅读）
  'loading': 0,            // 无负荷（等待）
  'result': 0.5,           // 低负荷（阅读结果）
  'game_scan': 0.5,        // 低负荷（娱乐）
  'game_spin': 0.5,        // 低负荷（娱乐）
  'permission': 1.5,       // 中低负荷（需要决策）
  'paywall': 2,            // 中负荷（需要决策）
  'celebration': 0,         // 无负荷（庆祝）
  'account': 2,            // 中负荷（表单）
  'transition': 0,         // 无负荷（休息）
  'soft_commit': 1         // 低负荷（简单承诺）
}

/**
 * 获取单个屏幕的认知负荷
 */
export function getScreenComplexity(screen: ScreenConfig): number {
  return questionComplexity[screen.type] || 1
}

/**
 * 验证问题序列的认知负荷
 * 确保连续问题复杂度总和不超过 5
 */
export function validateQuestionSequence(
  screens: ScreenConfig[]
): { isValid: boolean; issues: Array<{ index: number; cumulativeLoad: number }> } {
  let cumulativeLoad = 0
  const issues: Array<{ index: number; cumulativeLoad: number }> = []
  const MAX_LOAD = 5
  
  for (let i = 0; i < screens.length; i++) {
    const screen = screens[i]
    const load = getScreenComplexity(screen)
    
    cumulativeLoad += load
    
    // 如果累积负荷过高，记录问题
    if (cumulativeLoad > MAX_LOAD && screen.type !== 'transition' && screen.type !== 'value_prop') {
      issues.push({
        index: i,
        cumulativeLoad: cumulativeLoad
      })
    }
    
    // 过渡页或价值页重置负荷
    if (screen.type === 'transition' || screen.type === 'value_prop') {
      cumulativeLoad = 0
    }
  }
  
  return {
    isValid: issues.length === 0,
    issues
  }
}

/**
 * 自动插入过渡页
 * 当累积负荷过高时，建议插入过渡页
 */
export function suggestTransitionInsertion(
  screens: ScreenConfig[],
  maxLoadBeforeTransition: number = 4
): Array<{ afterIndex: number; reason: string }> {
  const suggestions: Array<{ afterIndex: number; reason: string }> = []
  let cumulativeLoad = 0
  let questionCount = 0
  
  for (let i = 0; i < screens.length; i++) {
    const screen = screens[i]
    const load = getScreenComplexity(screen)
    const isQuestion = [
      'question_single',
      'question_multi',
      'number_input',
      'text_input'
    ].includes(screen.type)
    
    if (isQuestion) {
      questionCount++
      cumulativeLoad += load
      
      // 如果累积负荷接近阈值，建议插入过渡页
      if (cumulativeLoad >= maxLoadBeforeTransition && 
          screen.type !== 'transition' && 
          screen.type !== 'value_prop') {
        suggestions.push({
          afterIndex: i,
          reason: `累积负荷 ${cumulativeLoad.toFixed(1)}，已连续 ${questionCount} 个问题`
        })
        cumulativeLoad = 0
        questionCount = 0
      }
    } else if (screen.type === 'transition' || screen.type === 'value_prop') {
      cumulativeLoad = 0
      questionCount = 0
    }
  }
  
  return suggestions
}

/**
 * 计算流程的平均认知负荷
 */
export function calculateAverageLoad(screens: ScreenConfig[]): {
  average: number
  max: number
  min: number
  distribution: Array<{ range: string; count: number }>
} {
  const loads = screens.map(s => getScreenComplexity(s))
  const questionLoads = loads.filter(l => l > 0)
  
  const average = questionLoads.length > 0
    ? questionLoads.reduce((a, b) => a + b, 0) / questionLoads.length
    : 0
  
  const max = Math.max(...loads, 0)
  const min = Math.min(...loads.filter(l => l > 0), 0)
  
  // 负荷分布
  const distribution = [
    { range: '0 (无负荷)', count: loads.filter(l => l === 0).length },
    { range: '0-1 (低负荷)', count: loads.filter(l => l > 0 && l <= 1).length },
    { range: '1-2 (中负荷)', count: loads.filter(l => l > 1 && l <= 2).length },
    { range: '2+ (高负荷)', count: loads.filter(l => l > 2).length }
  ]
  
  return { average, max, min, distribution }
}

/**
 * 优化流程的认知负荷
 * 自动在合适位置插入过渡页
 */
export function optimizeCognitiveLoad(
  screens: ScreenConfig[]
): ScreenConfig[] {
  const optimized: ScreenConfig[] = []
  let cumulativeLoad = 0
  let questionCount = 0
  let screenId = screens.length + 1 // 新插入的屏幕 ID
  
  for (let i = 0; i < screens.length; i++) {
    const screen = screens[i]
    const load = getScreenComplexity(screen)
    const isQuestion = [
      'question_single',
      'question_multi',
      'number_input',
      'text_input'
    ].includes(screen.type)
    
    // 如果累积负荷过高，插入过渡页
    if (cumulativeLoad >= 4 && isQuestion && questionCount >= 3) {
      optimized.push({
        id: screenId++,
        type: 'transition',
        title: "Great progress! 💪",
        subtitle: "You're doing amazing. Let's keep going.",
        phase: screen.phase,
        autoAdvance: true,
        animationType: 'spring'
      })
      cumulativeLoad = 0
      questionCount = 0
    }
    
    optimized.push(screen)
    
    if (isQuestion) {
      questionCount++
      cumulativeLoad += load
    } else if (screen.type === 'transition' || screen.type === 'value_prop') {
      cumulativeLoad = 0
      questionCount = 0
    }
  }
  
  return optimized
}
