'use client'

import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { useOnboardingStore } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { colors } from '../../lib/design-tokens'

interface LaunchScreenProps {
  config: ScreenConfig
}

/**
 * Launch Screen
 * 
 * Production: 快速跳转（动画在 IntroductionScreen 中）
 * 其他版本: 显示 Logo 后跳转
 */
export function LaunchScreen({ config }: LaunchScreenProps) {
  const { nextStep, isManualNavigation, clearManualNavigation } = useOnboardingStore()
  const { currentVersion } = useABTestStore()
  
  const isProduction = currentVersion === 'production'
  
  // 自动前进
  useEffect(() => {
    if (isManualNavigation) {
      clearManualNavigation()
      return
    }
    
    // Production 版本立即跳转（Logo 动画在 IntroductionScreen）
    const duration = isProduction ? 50 : 2000
    
    const timer = setTimeout(() => {
      nextStep()
    }, duration)
    
    return () => clearTimeout(timer)
  }, [nextStep, isManualNavigation, clearManualNavigation, isProduction])
  
  // Production 版本 - 空白快速跳转
  if (isProduction) {
    return (
      <div 
        className="h-full"
        style={{ background: colors.background.primary }}
      />
    )
  }
  
  // 其他版本 - 显示 Logo
  return (
    <div 
      className="h-full flex flex-col items-center justify-center overflow-hidden" 
      style={{ 
        background: colors.background.primary, 
        fontFamily: 'var(--font-outfit)' 
      }}
    >
      <motion.h1
        className="text-[64px] font-bold tracking-[-2px]"
        style={{ color: colors.slate[900] }}
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 200, damping: 20 }}
      >
        VitaFlow
      </motion.h1>
    </div>
  )
}
