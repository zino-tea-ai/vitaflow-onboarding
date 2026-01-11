'use client'

import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { Minus, Plus } from 'lucide-react'
import { useOnboardingStore, UserData } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { NumberSlider } from '../ui/NumberPicker'
import { Button, BackButton } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { Mascot, MascotState } from '../character'
import { ChatBubble } from '../ui/ChatBubble'
import { ConversationalLayout, ConversationalNumber } from '../ui/ConversationalLayout'
import { colors, bigTextStyles } from '../../lib/design-tokens'
import { getInputFeedback } from '../../data/feedback-copy'

interface NumberInputScreenProps {
  config: ScreenConfig
}

/**
 * 数字输入页
 * 支持两种模式：
 * - default: 角色 + 气泡对话反馈
 * - bigtext: 大字体无角色，CTA固定底部
 */
export function NumberInputScreen({ config }: NumberInputScreenProps) {
  const { userData, setUserData, nextStep, prevStep, currentStep, totalSteps } = useOnboardingStore()
  const { characterStyle, copyStyle, conversationalFeedbackEnabled, currentVersion, prodStyle } = useABTestStore()
  
  // BigText 模式判断
  const isBigText = currentVersion === 'production' && prodStyle === 'bigtext'
  
  const storeKey = config.storeKey as keyof UserData | undefined
  const currentValue = storeKey ? (userData[storeKey] as number | null) : null
  const defaultVal = config.numberConfig?.defaultValue || 0
  
  const [value, setValue] = useState<number>(currentValue || defaultVal)
  const [mascotState, setMascotState] = useState<MascotState>('idle')
  const [hasInteracted, setHasInteracted] = useState(false)  // 跟踪用户是否操作过
  
  // 获取气泡文案 - 只有用户操作后才显示 insight
  const bubbleText = useMemo(() => {
    // 用户未操作时，显示引导问题
    if (!hasInteracted) return config.title
    
    if (!conversationalFeedbackEnabled || !storeKey) return config.title
    
    // targetWeight 特殊处理：根据与当前体重的差值给不同反馈
    if (storeKey === 'targetWeight' && userData.currentWeight) {
      const diff = userData.currentWeight - value  // 正数=减重，负数=增重
      const absDiff = Math.abs(diff)
      
      if (copyStyle === 'witty') {
        if (diff > 0) {
          // 减重目标
          if (absDiff <= 5) return "A quick win! You'll crush this."
          if (absDiff <= 10) return "Solid goal. Let's make it happen!"
          if (absDiff <= 20) return "Ambitious! I like your style."
          return "Big dreams need big plans. I'm in!"
        } else if (diff < 0) {
          // 增重目标
          if (absDiff <= 5) return "Bulk mode: activated!"
          return "Gains incoming! Let's fuel up."
        } else {
          return "Maintaining? Smart move."
        }
      } else if (copyStyle === 'warm') {
        if (diff > 0) {
          if (absDiff <= 5) return "Almost there! You can do this."
          if (absDiff <= 10) return "A healthy goal. We'll get there together!"
          if (absDiff <= 20) return "I believe in you. One step at a time."
          return "Every journey starts with a single step."
        } else if (diff < 0) {
          if (absDiff <= 5) return "Let's build you up!"
          return "Healthy gains, here we come!"
        } else {
          return "Staying balanced is a great goal!"
        }
      } else {
        // data style
        if (diff > 0) {
          const weeks = Math.ceil(absDiff / 0.5)  // 0.5kg/week 健康减重
          return `${absDiff}kg to lose. ~${weeks} weeks at healthy pace.`
        } else if (diff < 0) {
          const weeks = Math.ceil(absDiff / 0.25)  // 0.25kg/week 健康增重
          return `${absDiff}kg to gain. ~${weeks} weeks recommended.`
        } else {
          return "Maintenance mode. Balanced calories."
        }
      }
    }
    
    const feedbackKey = storeKey.includes('eight') 
      ? (storeKey.includes('target') ? 'targetWeight' : 'weight')
      : storeKey.includes('height') 
        ? 'height' 
        : storeKey.includes('age') 
          ? 'age' 
          : null
    
    if (feedbackKey) {
      return getInputFeedback(feedbackKey, value, copyStyle) || config.title
    }
    return config.title
  }, [hasInteracted, value, storeKey, copyStyle, conversationalFeedbackEnabled, config.title, userData.currentWeight])
  
  const handleValueChange = (newValue: number) => {
    setValue(newValue)
    setHasInteracted(true)  // 标记用户已操作
    
    if (conversationalFeedbackEnabled) {
      setMascotState('thinking')
      setTimeout(() => setMascotState('encouraging'), 300)
    }
  }
  
  const handleContinue = () => {
    if (storeKey) {
      setUserData(storeKey, value as never)
    }
    if (conversationalFeedbackEnabled) {
      setMascotState('happy')
    }
    nextStep()
  }
  
  if (!config.numberConfig) {
    return <div>Missing number config</div>
  }
  
  const { min, max, step, unit } = config.numberConfig

  // BigText 对话式布局
  if (isBigText) {
    return (
      <ConversationalLayout
        currentStep={currentStep}
        totalSteps={totalSteps}
        onBack={prevStep}
        mascotState={mascotState}
        question={bubbleText}
        hint={config.subtitle}
        ctaText="Continue"
        onCtaClick={handleContinue}
      >
        {/* 数字选择器作为用户的"回复" */}
        <ConversationalNumber
          value={value}
          onChange={handleValueChange}
          min={min}
          max={max}
          step={step}
          unit={unit}
          label={storeKey === 'age' ? 'Age' : storeKey === 'targetWeight' ? 'Target' : undefined}
        />
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
        <div />
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
        <div className="px-5 pt-4 pb-8">
          <motion.h1
            className="text-[24px] font-medium text-center tracking-[-0.4px]"
            style={{ color: colors.text.primary }}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            {config.title}
          </motion.h1>
          
          {config.subtitle && (
            <motion.p
              className="mt-2 text-[14px] text-center"
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
      
      {/* 数字选择器 */}
      <motion.div
        className="flex-1 flex items-center justify-center px-5"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        <NumberSlider
          value={value}
          onChange={handleValueChange}
          min={min}
          max={max}
          step={step}
          unit={unit}
        />
      </motion.div>
      
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
        >
          Continue
        </Button>
      </motion.div>
    </div>
  )
}
