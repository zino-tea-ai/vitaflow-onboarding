// VitaFlow Onboarding V3 - 条件分支逻辑
// 根据用户路径动态调整流程

import { ScreenConfig } from '../data/screens-config-v2'
import { UserData } from '../store/onboarding-store'

/**
 * 条件屏幕配置
 * 根据用户选择决定是否跳过某些页面
 */
export interface ConditionalScreen {
  condition: (userData: UserData) => boolean
  skipScreens: number[] // 如果条件满足，跳过这些页面 ID
  insertScreens?: ScreenConfig[] // 可选：插入的页面
  modifyScreens?: Array<{
    screenId: number
    modifications: Partial<ScreenConfig>
  }> // 可选：修改的页面
}

/**
 * 条件流程规则
 */
export const conditionalFlows: ConditionalScreen[] = [
  {
    // 如果用户选择"保持体重"，跳过减重速度选择
    condition: (data) => data.goal === 'maintain_weight',
    skipScreens: [16], // 跳过 weeklyLossRate 页面
    modifyScreens: [
      {
        screenId: 15, // targetWeight 页面
        modifications: {
          subtitle: "What's your target weight? (We'll help you maintain it)"
        }
      }
    ]
  },
  {
    // 如果用户没有饮食限制，简化偏好收集
    condition: (data) => data.dietaryPreferences?.includes('none') || 
                        (data.dietaryPreferences?.length === 0),
    skipScreens: [23, 24], // 跳过过敏和不喜欢的食物（如果配置中有）
  },
  {
    // 如果用户是健身老手，跳过基础运动问题
    condition: (data) => data.previousAppExperience === 'yes' && 
                        data.workoutFrequency === 'often',
    skipScreens: [8, 9], // 跳过活动水平和运动频率（如果已收集）
  },
  {
    // 如果用户已经连接 Health Kit，跳过权限请求
    condition: (data) => data.healthKitConnected === true,
    skipScreens: [18], // 跳过 Health Kit 权限页面
  },
  {
    // 如果用户已经启用通知，跳过通知权限
    condition: (data) => data.notificationsEnabled === true,
    skipScreens: [25], // 跳过通知权限页面
  }
]

/**
 * 检查条件并应用规则
 */
export function applyConditionalLogic(
  screens: ScreenConfig[],
  userData: UserData
): ScreenConfig[] {
  let filteredScreens = [...screens]
  
  // 应用每个条件规则
  for (const rule of conditionalFlows) {
    if (rule.condition(userData)) {
      // 跳过指定的屏幕
      filteredScreens = filteredScreens.filter(
        screen => !rule.skipScreens.includes(screen.id)
      )
      
      // 插入新屏幕（如果有）
      if (rule.insertScreens && rule.insertScreens.length > 0) {
        // 在适当位置插入
        // 这里可以根据需要实现插入逻辑
      }
      
      // 修改屏幕（如果有）
      if (rule.modifyScreens) {
        for (const mod of rule.modifyScreens) {
          const screenIndex = filteredScreens.findIndex(s => s.id === mod.screenId)
          if (screenIndex !== -1) {
            filteredScreens[screenIndex] = {
              ...filteredScreens[screenIndex],
              ...mod.modifications
            }
          }
        }
      }
    }
  }
  
  return filteredScreens
}

/**
 * 获取应该跳过的屏幕 ID 列表
 */
export function getSkippedScreens(userData: UserData): number[] {
  const skipped: number[] = []
  
  for (const rule of conditionalFlows) {
    if (rule.condition(userData)) {
      skipped.push(...rule.skipScreens)
    }
  }
  
  return skipped
}

/**
 * 检查屏幕是否应该显示
 */
export function shouldShowScreen(
  screenId: number,
  userData: UserData
): boolean {
  const skipped = getSkippedScreens(userData)
  return !skipped.includes(screenId)
}

/**
 * 获取动态流程长度
 * 考虑条件跳过后，实际需要显示的屏幕数量
 */
export function getDynamicFlowLength(
  totalScreens: number,
  userData: UserData
): number {
  const skipped = getSkippedScreens(userData)
  return totalScreens - skipped.length
}
