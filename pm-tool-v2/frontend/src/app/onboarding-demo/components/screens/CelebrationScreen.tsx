'use client'

import { useEffect, useRef, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useOnboardingStore } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { Button, BackButton } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { Mascot } from '../character'
import { ChatBubble } from '../ui/ChatBubble'
import { colors } from '../../lib/design-tokens'
import { personalizeText } from '../../utils/personalize'
import { Check, Camera } from 'lucide-react'

interface CelebrationScreenProps {
  config: ScreenConfig
}

export function CelebrationScreen({ config }: CelebrationScreenProps) {
  const { nextStep, prevStep, currentStep, totalSteps, userData } = useOnboardingStore()
  const { characterStyle, showMascot, conversationalFeedbackEnabled, copyStyle } = useABTestStore()
  
  // 个性化文本
  const title = config.usePersonalization ? personalizeText(config.title, userData.name) : config.title
  const subtitle = config.usePersonalization ? personalizeText(config.subtitle, userData.name) : config.subtitle
  const isLastScreen = currentStep === totalSteps
  
  // 角色文案
  const mascotText = useMemo(() => {
    const name = userData.name || 'there'
    const texts = {
      witty: isLastScreen 
        ? `${name}! We're gonna be best friends!` 
        : `High five, ${name}! That was epic!`,
      warm: isLastScreen 
        ? `So excited to start this journey with you, ${name}!` 
        : `Amazing progress, ${name}! I'm cheering for you!`,
      data: isLastScreen 
        ? `Setup complete, ${name}. Ready for optimized nutrition tracking.` 
        : `Milestone achieved. Continuing to next phase.`
    }
    return texts[copyStyle] || texts.warm
  }, [copyStyle, userData.name, isLastScreen])
  
  return (
    <div 
      className="h-full flex flex-col"
      style={{ 
        background: colors.background.primary,
        fontFamily: 'var(--font-outfit)'
      }}
    >
      {/* 进度条 */}
      <ProgressBar current={currentStep} total={totalSteps} />
      
      {/* 头部导航 */}
      <div className="flex items-center justify-between px-5 py-2">
        <BackButton onClick={prevStep} />
        <div />
      </div>
      
      {/* 角色 + 气泡区域 */}
      {showMascot && conversationalFeedbackEnabled ? (
        <motion.div 
          className="px-5 pt-2 pb-4 flex items-start gap-4"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Mascot 
            style={characterStyle} 
            state="celebrating" 
            size="md" 
          />
          <div className="flex-1 pt-3">
            <ChatBubble 
              text={mascotText}
              visible={true}
              position="bottom-right"
              size="md"
            />
          </div>
        </motion.div>
      ) : (
        /* 无角色时的标题区域 */
        <motion.div 
          className="px-5 pt-4 pb-2"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <motion.h1
            className="text-[28px] font-medium tracking-[-0.4px]"
            style={{ color: colors.text.primary }}
          >
            {title.replace(/[🎊🚀]/g, '').trim()}
          </motion.h1>
          
          <motion.p
            className="mt-2 text-[15px]"
            style={{ color: colors.text.secondary }}
          >
            {subtitle}
          </motion.p>
        </motion.div>
      )}
      
      {/* 内容区域 */}
      <div className="flex-1 px-5 pt-2 overflow-y-auto scrollbar-hide pb-4">
        {/* 成功卡片 - 与 OptionCard 风格一致 */}
        <motion.div
          className="p-4 rounded-[16px] text-left"
          style={{
            background: '#FFFFFF',
            boxShadow: '0px 1px 3px rgba(15, 23, 42, 0.08)'
          }}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <div className="flex items-center gap-4">
            {/* 图标容器 - 选中状态 */}
            <motion.div 
              className="flex-shrink-0 w-12 h-12 rounded-[12px] flex items-center justify-center"
              style={{ background: '#0F172A' }}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.3 }}
            >
              <Check 
                className="w-6 h-6"
                style={{ color: '#FFFFFF' }}
                strokeWidth={2}
              />
            </motion.div>
            
            {/* 文本 */}
            <div className="flex-1 min-w-0">
              <p 
                className="font-medium text-[15px]"
                style={{ color: '#0F172A' }}
              >
                {title.replace(/[🎊🚀]/g, '').trim()}
              </p>
              <p 
                className="text-[13px] mt-0.5"
                style={{ color: '#64748B' }}
              >
                {subtitle}
              </p>
            </div>
          </div>
        </motion.div>
        
        {/* 额外信息卡片 */}
        {isLastScreen && (
          <motion.div
            className="mt-4 p-4 rounded-[16px]"
            style={{
              background: '#FFFFFF',
              boxShadow: '0px 1px 3px rgba(15, 23, 42, 0.08)'
            }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.3 }}
          >
            <div className="flex items-center gap-4">
              <div 
                className="flex-shrink-0 w-12 h-12 rounded-[12px] flex items-center justify-center"
                style={{ background: '#F1F5F9' }}
              >
                <Camera className="w-6 h-6" style={{ color: '#64748B' }} strokeWidth={1.5} />
              </div>
              <div className="flex-1 min-w-0">
                <p 
                  className="font-medium text-[15px]"
                  style={{ color: '#0F172A' }}
                >
                  Ready to scan?
                </p>
                <p 
                  className="text-[13px] mt-0.5"
                  style={{ color: '#64748B' }}
                >
                  Your first meal is waiting!
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </div>
      
      {/* 底部按钮 */}
      <motion.div
        className="px-5 py-6"
        style={{ background: colors.background.primary }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Button fullWidth size="lg" onClick={nextStep}>
          {isLastScreen ? "Let's Go" : 'Continue'}
        </Button>
      </motion.div>
    </div>
  )
}
