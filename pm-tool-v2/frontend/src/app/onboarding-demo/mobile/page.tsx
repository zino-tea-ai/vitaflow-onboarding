'use client'

import { useEffect, useState } from 'react'
import { useOnboardingStore } from '../store/onboarding-store'
import { useABTestStore } from '../store/ab-test-store'
import { screensConfigProduction } from '../data/screens-config-production'
import { ScreenRenderer } from '../components/screens'
// supportsHaptics 导入已移除 - 可能导致 SSR 问题

export default function MobileOnboardingPage() {
  const { setTotalSteps, userData, resetDemo, currentStep } = useOnboardingStore()
  const { setVersion, setCharacterStyle, toggleConversationalFeedback, conversationalFeedbackEnabled } = useABTestStore()
  
  // #region agent log - 调试面板状态
  const [showDebug, setShowDebug] = useState(false)
  const [debugInfo, setDebugInfo] = useState('')
  
  useEffect(() => {
    // 运行时检测（在客户端）
    const canVibrate = typeof navigator !== 'undefined' && 'vibrate' in navigator
    const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent)
    const safariVersion = navigator.userAgent.match(/Version\/(\d+)/)?.[1] || '?'
    
    const info = `iOS: ${isIOS} | Safari: v${safariVersion} | vibrate API: ${canVibrate}\n${isIOS ? '🔔 使用 ios-haptics 真实震动!' : ''}`
    setDebugInfo(info)
    
    // 定时更新调试日志
    const interval = setInterval(() => {
      const logs = (window as any).__DEBUG_LOGS__ || []
      setDebugInfo(`iOS: ${isIOS} | Safari: v${safariVersion}\n---LOGS---\n${logs.join('\n')}`)
    }, 500)
    return () => clearInterval(interval)
  }, [])
  // #endregion
  
  // 初始化 - 强制使用 PROD 版本 + Orb 角色 + 重置到第1步
  useEffect(() => {
    resetDemo() // 重置到第1步
    setVersion('production')
    setTotalSteps(screensConfigProduction.length)
    setCharacterStyle('orb')
    // 确保对话反馈开启
    if (!conversationalFeedbackEnabled) {
      toggleConversationalFeedback()
    }
  }, []) // 只在首次 mount 时执行
  
  // 自动重置逻辑 - 确保数据完整性
  useEffect(() => {
    const currentConfig = screensConfigProduction[currentStep - 1]
    if (currentConfig && (currentConfig.id === 'result' || currentConfig.id === 'loading')) {
      if (!userData.goal || !userData.gender) {
        resetDemo()
      }
    }
  }, [currentStep, userData, resetDemo])
  
  const currentConfig = screensConfigProduction[currentStep - 1]
  
  if (!currentConfig) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F8F8FA]">
        <p className="text-gray-500">Loading...</p>
      </div>
    )
  }
  
  return (
    <div 
      className="h-[100dvh] w-full flex flex-col relative"
      style={{ 
        fontFamily: 'var(--font-outfit)',
        WebkitTapHighlightColor: 'transparent',
        background: '#F8F8FA',
      }}
    >
      <ScreenRenderer />
      
      {/* #region agent log - 调试面板 */}
      <button
        onClick={() => setShowDebug(!showDebug)}
        className="fixed bottom-4 right-4 w-10 h-10 bg-red-500 text-white rounded-full text-xs font-bold z-[9999] shadow-lg"
      >
        DBG
      </button>
      {showDebug && (
        <div className="fixed inset-x-4 bottom-16 bg-black/90 text-green-400 p-3 rounded-lg text-[10px] font-mono z-[9999] max-h-[40vh] overflow-auto">
          <pre id="debug-panel-content" className="whitespace-pre-wrap">{debugInfo}</pre>
        </div>
      )}
      {/* #endregion */}
    </div>
  )
}
