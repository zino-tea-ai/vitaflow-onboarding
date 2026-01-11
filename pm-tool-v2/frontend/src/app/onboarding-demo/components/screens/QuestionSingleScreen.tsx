'use client'

import { useState, useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useOnboardingStore, UserData } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { OptionCard } from '../ui/OptionCard'
import { Button, BackButton, SkipButton } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { Mascot, MascotState } from '../character'
import { ChatBubble } from '../ui/ChatBubble'
import { ConversationalLayout, ConversationalOption } from '../ui/ConversationalLayout'
import { colors, bigTextStyles } from '../../lib/design-tokens'
import { getOptionFeedback, optionIdToFeedbackKey } from '../../data/feedback-copy'

interface QuestionSingleScreenProps {
  config: ScreenConfig
}

/**
 * 单选问题页
 * 支持两种模式：
 * - default: 角色 + 气泡对话反馈
 * - bigtext: 对话式融合布局
 */
export function QuestionSingleScreen({ config }: QuestionSingleScreenProps) {
  const { userData, setUserData, nextStep, prevStep, currentStep, totalSteps } = useOnboardingStore()
  const { characterStyle, copyStyle, conversationalFeedbackEnabled, currentVersion, prodStyle } = useABTestStore()
  
  // BigText 模式判断
  const isBigText = currentVersion === 'production' && prodStyle === 'bigtext'
  
  const storeKey = config.storeKey as keyof UserData | undefined
  const currentValue = storeKey ? userData[storeKey] : null
  const [selected, setSelected] = useState<string | null>(currentValue as string | null)
  const [mascotState, setMascotState] = useState<MascotState>('idle')
  
  // 获取反馈文案 - 选中后显示
  const feedbackText = useMemo(() => {
    if (!selected || !storeKey) return null
    const feedbackKey = optionIdToFeedbackKey(storeKey, selected)
    return getOptionFeedback(feedbackKey, copyStyle)
  }, [selected, storeKey, copyStyle])
  
  // 主问题文案
  const questionText = useMemo(() => {
    return feedbackText || config.title
  }, [feedbackText, config.title])
  
  // 自动前进逻辑
  useEffect(() => {
    if (config.autoAdvance && selected && selected !== currentValue) {
      if (storeKey) {
        setUserData(storeKey, selected as never)
      }
      
      const timer = setTimeout(() => {
        nextStep()
      }, isBigText ? 300 : (conversationalFeedbackEnabled ? 800 : 400))
      
      return () => clearTimeout(timer)
    }
  }, [selected, config.autoAdvance, currentValue, storeKey, setUserData, nextStep, conversationalFeedbackEnabled, isBigText])
  
  const handleSelect = (optionId: string) => {
    setSelected(optionId)
    
    if (!config.autoAdvance && storeKey) {
      setUserData(storeKey, optionId as never)
    }
    
    // 更新角色状态
    if (conversationalFeedbackEnabled) {
      setMascotState('happy')
      setTimeout(() => setMascotState('encouraging'), 500)
    }
  }
  
  const handleContinue = () => {
    if (storeKey && selected) {
      setUserData(storeKey, selected as never)
    }
    nextStep()
  }
  
  // BigText 对话式布局 - 真正融合的设计
  if (isBigText) {
    return (
      <ConversationalLayout
        currentStep={currentStep}
        totalSteps={totalSteps}
        onBack={prevStep}
        onSkip={config.skipButton ? nextStep : undefined}
        showSkip={config.skipButton}
        mascotState={mascotState}
        question={questionText}
        hint={config.subtitle}
        ctaText="Continue"
        ctaDisabled={!selected}
        onCtaClick={handleContinue}
      >
        {/* 选项作为用户的"回复" */}
        <div className="space-y-4">
          {config.options?.map((option, index) => (
            <ConversationalOption
              key={option.id}
              label={option.title}
              description={option.subtitle}
              selected={selected === option.id}
              onClick={() => handleSelect(option.id)}
              index={index}
            />
          ))}
        </div>
      </ConversationalLayout>
    )
  }
  
  // 默认模式渲染
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
        {config.skipButton && <SkipButton onClick={nextStep} />}
      </div>
      
      {/* 角色 + 气泡区域 */}
      {conversationalFeedbackEnabled ? (
        <motion.div 
          className="px-5 pt-2 pb-4 flex items-start gap-4"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Mascot 
            style={characterStyle} 
            state={mascotState} 
            size="md" 
          />
          <div className="flex-1 pt-3">
            <ChatBubble 
              text={bubbleText}
              visible={!!bubbleText}
              position="bottom-right"
              size="md"
            />
          </div>
        </motion.div>
      ) : (
        /* 无角色时的标题区域 */
        <div className="px-5 pt-4 pb-6">
          <motion.h1
            className="text-[24px] font-medium tracking-[-0.4px]"
            style={{ color: colors.text.primary }}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            {config.title}
          </motion.h1>
          
          {config.subtitle && (
            <motion.p
              className="mt-2 text-[14px]"
              style={{ color: colors.text.secondary }}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.1 }}
            >
              {config.subtitle}
            </motion.p>
          )}
        </div>
      )}
      
      {/* 选项列表 */}
      <div className="flex-1 px-5 overflow-y-auto scrollbar-hide pb-4">
        <div className="space-y-4">
          {config.options?.map((option, index) => (
            <OptionCard
              key={option.id}
              icon={option.icon}
              title={option.title}
              subtitle={option.subtitle}
              selected={selected === option.id}
              onClick={() => handleSelect(option.id)}
              index={index}
            />
          ))}
        </div>
      </div>
      
      {/* 底部按钮 */}
      <motion.div
        className="px-5 py-6"
        style={{ background: colors.background.primary }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Button 
          fullWidth 
          size="lg" 
          onClick={handleContinue}
          disabled={!selected}
        >
          Continue
        </Button>
      </motion.div>
    </div>
  )
}
