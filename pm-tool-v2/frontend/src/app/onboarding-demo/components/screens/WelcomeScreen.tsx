'use client'

import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useOnboardingStore } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { Button } from '../ui/Button'
import { Mascot, MascotState } from '../character'
import { ChatBubble } from '../ui/ChatBubble'
import { colors } from '../../lib/design-tokens'
import { Camera, Sparkles, Clock } from 'lucide-react'

interface WelcomeScreenProps {
  config: ScreenConfig
}

/**
 * Welcome Screen - 简洁产品展示
 * 
 * 简化设计：
 * - 移除 3D 手机模型
 * - 使用简单图标展示功能
 * - 恢复角色 + 气泡
 */
export function WelcomeScreen({ config }: WelcomeScreenProps) {
  const { nextStep } = useOnboardingStore()
  const { currentVersion, characterStyle, copyStyle, conversationalFeedbackEnabled } = useABTestStore()
  
  const [mascotState] = useState<MascotState>('explaining')
  
  const isProduction = currentVersion === 'production'
  
  // 气泡文案
  const bubbleText = useMemo(() => {
    if (!conversationalFeedbackEnabled) return ''
    
    const texts = {
      witty: "Snap a photo, get instant nutrition info. It's like having a dietitian in your pocket!",
      warm: "I can analyze any food just by taking a photo. Let me show you how easy healthy eating can be!",
      data: "Our AI identifies 10,000+ foods with 98% accuracy. Ready to optimize your nutrition?"
    }
    return texts[copyStyle] || texts.warm
  }, [copyStyle, conversationalFeedbackEnabled])
  
  // Production 版本 - 电影式叙事延续
  if (isProduction) {
    return (
      <div 
        className="h-full flex flex-col" 
        style={{ 
          background: colors.background.primary, 
          fontFamily: 'var(--font-outfit)' 
        }}
      >
        {/* 主要内容区 - 大留白、电影感 */}
        <div className="flex-1 flex flex-col items-center justify-center px-8">
          {/* 核心功能 + 过渡到表单 */}
          <motion.div
            className="text-center max-w-[320px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6 }}
          >
            {/* 主标题 - 模糊入场 */}
            <motion.h1
              className="text-[36px] font-medium leading-tight"
              style={{ 
                color: colors.slate[900],
                letterSpacing: '-0.4px',
                willChange: 'filter, opacity',
              }}
              initial={{ opacity: 0, y: 20, filter: 'blur(12px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0.01px)' }}
              transition={{ delay: 0.2, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
            >
              Snap a photo.
            </motion.h1>
            
            <motion.h1
              className="text-[36px] font-medium leading-tight mt-1"
              style={{ 
                color: colors.slate[900],
                letterSpacing: '-0.4px',
                willChange: 'filter, opacity',
              }}
              initial={{ opacity: 0, y: 20, filter: 'blur(12px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0.01px)' }}
              transition={{ delay: 0.5, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
            >
              Get instant insights.
            </motion.h1>
            
            {/* 过渡到表单的提示 */}
            <motion.p
              className="mt-8 text-[16px] leading-relaxed"
              style={{ 
                color: colors.text.secondary,
                willChange: 'filter, opacity',
              }}
              initial={{ opacity: 0, y: 15, filter: 'blur(8px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0.01px)' }}
              transition={{ delay: 0.9, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            >
              First, let's personalize your experience.
            </motion.p>
          </motion.div>
        </div>
        
        {/* 底部区域 */}
        <div className="px-5 pb-8 pt-4">
          <motion.div
            initial={{ opacity: 0, y: 15, filter: 'blur(8px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            transition={{ delay: 1.2, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <Button 
              fullWidth 
              size="lg" 
              onClick={nextStep}
              style={{
                height: '52px',
                fontSize: '16px',
                letterSpacing: '-0.2px',
              }}
            >
              Continue
            </Button>
          </motion.div>
          
          {/* 简洁的时间承诺 */}
          <motion.p 
            className="mt-4 text-[13px] text-center"
            style={{ color: colors.text.tertiary }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.5, duration: 0.5 }}
          >
            Takes about 2 minutes
          </motion.p>
        </div>
      </div>
    )
  }
  
  // 原版 - 也简化
  return (
    <div 
      className="h-full flex flex-col" 
      style={{ 
        background: colors.background.primary, 
        fontFamily: 'var(--font-outfit)' 
      }}
    >
      <div className="flex-1 flex flex-col items-center justify-center px-8">
        {/* 简洁图标 */}
        <motion.div
          className="relative mb-8"
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div 
            className="w-28 h-28 rounded-[24px] flex items-center justify-center"
            style={{ background: colors.slate[100] }}
          >
            <Camera size={48} style={{ color: colors.slate[900] }} strokeWidth={1.5} />
          </div>
        </motion.div>
        
        <motion.h1
            className="text-[24px] font-medium text-center tracking-[-0.4px]"
          style={{ color: colors.text.primary }}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          {config.title}
        </motion.h1>
        
        <motion.p
          className="mt-4 text-center text-[14px] leading-relaxed max-w-xs"
          style={{ color: colors.text.secondary }}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          {config.subtitle}
        </motion.p>
        
        {/* 角色 + 气泡 */}
        {conversationalFeedbackEnabled && (
          <motion.div
            className="mt-8 flex items-start gap-4 max-w-sm"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Mascot 
              style={characterStyle}
              state={mascotState}
              size="sm"
            />
            <div className="flex-1 pt-3">
              <ChatBubble
                text={bubbleText}
                visible={true}
                position="bottom-right"
                size="sm"
              />
            </div>
          </motion.div>
        )}
      </div>
      
      <motion.div
        className="px-5 pb-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <Button fullWidth size="lg" onClick={nextStep}>
          Get Started
        </Button>
        
        <p className="mt-4 text-xs text-center" style={{ color: colors.text.secondary }}>
          By continuing, you agree to our{' '}
          <span style={{ color: colors.text.primary }}>Terms</span> and{' '}
          <span style={{ color: colors.text.primary }}>Privacy Policy</span>
        </p>
      </motion.div>
    </div>
  )
}
