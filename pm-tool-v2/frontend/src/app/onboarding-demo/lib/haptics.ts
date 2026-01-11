/**
 * 触觉反馈工具
 * 
 * 支持三种模式：
 * 1. Android: 使用 Vibration API
 * 2. iOS Safari 17.4+: 使用 ios-haptics 库（真实震动！）
 * 3. iOS 旧版本: 使用音频反馈
 */

// #region agent log - 调试面板
const debugLogs: string[] = []
function addDebugLog(msg: string) {
  debugLogs.push(`${new Date().toLocaleTimeString()}: ${msg}`)
  if (debugLogs.length > 20) debugLogs.shift()
  if (typeof window !== 'undefined') {
    (window as any).__DEBUG_LOGS__ = debugLogs
  }
}
// #endregion

// 运行时检测
function checkVibrationSupport(): boolean {
  return typeof navigator !== 'undefined' && 'vibrate' in navigator
}

function checkIsIOS(): boolean {
  if (typeof navigator === 'undefined') return false
  return /iPhone|iPad|iPod/.test(navigator.userAgent)
}

// 导出检测结果
export const supportsHaptics = checkVibrationSupport()

// 震动模式（Android）
export const HapticPatterns = {
  light: [10],
  medium: [20],
  heavy: [30],
  success: [10, 50, 20],
  error: [50, 30, 50],
  selection: [8],
  slide: [5],
  celebration: [20, 30, 10, 30, 20, 50, 30],
} as const

export type HapticType = keyof typeof HapticPatterns

// ============ iOS 原生震动（Safari 17.4+）============
// 必须同步导入，不能使用 dynamic import，否则会脱离用户交互上下文
import { haptic as iosHaptic, supportsHaptics as iosSupportsHaptics } from 'ios-haptics'

// iOS 原生震动 - 单次强震动
function triggerIOSHaptic(type: HapticType): boolean {
  try {
    addDebugLog(`iOS haptic: ${type}`)
    
    // 所有类型都用最强的 confirm（双击感）或 error（三击感）
    if (type === 'success' || type === 'celebration' || type === 'heavy') {
      iosHaptic.confirm() // 最强的确认震动
    } else if (type === 'error') {
      iosHaptic.error() // 错误震动
    } else {
      iosHaptic() // 标准单次震动
    }
    
    return true
  } catch (e) {
    addDebugLog(`iOS haptic error: ${e}`)
    return false
  }
}

// 音频已移除，只使用震动

/**
 * 触发触觉反馈（纯震动，无声音）
 */
export function haptic(type: HapticType = 'light'): void {
  const canVibrate = checkVibrationSupport()
  const isIOS = checkIsIOS()
  
  addDebugLog(`haptic(${type}) iOS=${isIOS} vibrate=${canVibrate}`)
  
  // Android: 使用 Vibration API
  if (canVibrate) {
    try {
      navigator.vibrate(HapticPatterns[type])
    } catch (e) {
      addDebugLog(`vibrate error: ${e}`)
    }
    return
  }
  
  // iOS: 只用震动，无声音
  if (isIOS) {
    triggerIOSHaptic(type)
  }
}

/**
 * 启用触觉反馈（需要在用户交互时调用一次）
 */
export function enableAudioHaptics() {
  addDebugLog(`Haptics enabled, iosSupports=${iosSupportsHaptics}`)
}

/**
 * 创建带震动的点击处理器
 */
export function withHaptic<T extends (...args: unknown[]) => unknown>(
  handler: T,
  type: HapticType = 'light'
): T {
  return ((...args: Parameters<T>) => {
    haptic(type)
    return handler(...args)
  }) as T
}

/**
 * React Hook: 在组件中使用震动
 */
export function useHaptic() {
  return {
    haptic,
    light: () => haptic('light'),
    medium: () => haptic('medium'),
    heavy: () => haptic('heavy'),
    success: () => haptic('success'),
    error: () => haptic('error'),
    selection: () => haptic('selection'),
    slide: () => haptic('slide'),
    celebration: () => haptic('celebration'),
  }
}
