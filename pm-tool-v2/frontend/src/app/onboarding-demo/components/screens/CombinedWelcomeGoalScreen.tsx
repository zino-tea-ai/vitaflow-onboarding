'use client'

import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useOnboardingStore, UserData } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfigProduction } from '../../data/screens-config-production'
import { OptionCard } from '../ui/OptionCard'
import { Button, BackButton } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { ConfettiCSS } from '../effects/Confetti'
import { Mascot, MascotState } from '../character'
import { ChatBubble } from '../ui/ChatBubble'
import { ConversationalLayout, ConversationalOption } from '../ui/ConversationalLayout'
import { colors, bigTextStyles } from '../../lib/design-tokens'
import { personalizeText } from '../../utils/personalize'
import { getOptionFeedback, getPageTitle, optionIdToFeedbackKey } from '../../data/feedback-copy'

interface CombinedWelcomeGoalScreenProps {
  config: ScreenConfigProduction
}

/**
 * 合并页：欢迎 + 目标选择
 * 支持两种模式：
 * - default: 角色 + 气泡对话反馈
 * - bigtext: 大字体无角色，CTA固定底部
 */
export function CombinedWelcomeGoalScreen({ config }: CombinedWelcomeGoalScreenProps) {
  const { userData, setUserData, nextStep, prevStep, currentStep, totalSteps } = useOnboardingStore()
  const { characterStyle, copyStyle, conversationalFeedbackEnabled, currentVersion, prodStyle } = useABTestStore()
  
  // BigText 模式判断
  const isBigText = currentVersion === 'production' && prodStyle === 'bigtext'
  
  const [selected, setSelected] = useState<string | null>(userData.goal as string | null)
  const [showCelebration, setShowCelebration] = useState(false)
  const [mascotState, setMascotState] = useState<MascotState>('idle')
  
  // 个性化标题
  const title = personalizeText(config.title, userData.name)
  
  // 获取反馈文案
  const feedbackText = useMemo(() => {
    if (!selected) return null
    const feedbackKey = optionIdToFeedbackKey('goal', selected)
    return getOptionFeedback(feedbackKey, copyStyle)
  }, [selected, copyStyle])
  
  // 主问题文案（用于对话式布局）
  const questionText = useMemo(() => {
    return feedbackText || title
  }, [feedbackText, title])
  
  // 气泡文案（用于默认模式）
  const bubbleText = useMemo(() => {
    if (!conversationalFeedbackEnabled) return ''
    if (selected) {
      const feedbackKey = optionIdToFeedbackKey('goal', selected)
      return getOptionFeedback(feedbackKey, copyStyle) || getPageTitle('goal_selection', copyStyle)
    }
    return getPageTitle('goal_selection', copyStyle)
  }, [selected, copyStyle, conversationalFeedbackEnabled])
  
  // 检查这个组件实例是否是当前活动页面
  const isActive = currentStep === config.id
  
  // 如果不是活动页面，完全不渲染
  if (!isActive) {
    return null
  }
  
  const handleSelect = (optionId: string) => {
    if (!isActive) return
    setSelected(optionId)
    setUserData('goal', optionId as UserData['goal'])
    
    // 更新角色状态
    if (conversationalFeedbackEnabled) {
      setMascotState('happy')
      setTimeout(() => setMascotState('encouraging'), 500)
    }
  }
  
  const handleContinue = () => {
    if (!isActive) return
    
    if (selected && config.celebrateAfter) {
      setMascotState('cheering')
      setShowCelebration(true)
      setTimeout(() => {
        setShowCelebration(false)
        nextStep()
      }, 1200)
    } else {
      nextStep()
    }
  }
  
  // BigText 对话式布局
  if (isBigText) {
    return (
      <>
        <ConfettiCSS active={showCelebration} />
        <ConversationalLayout
          currentStep={currentStep}
          totalSteps={totalSteps}
          onBack={prevStep}
          mascotState={mascotState}
          question={questionText}
          hint={config.subtitle}
          ctaText="Continue"
          ctaDisabled={!selected}
          onCtaClick={handleContinue}
        >
          {/* 目标选项作为用户的"回复" */}
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
      </>
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
      {/* Confetti 效果 */}
      <ConfettiCSS active={showCelebration} />
      
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
            {title}
          </motion.h1>
          
          <motion.p
            className="mt-2 text-[15px]"
            style={{ color: colors.text.secondary }}
          >
            {config.subtitle}
          </motion.p>
        </motion.div>
      )}
      
      {/* 目标选项 */}
      <div className="flex-1 px-5 pt-2 overflow-y-auto scrollbar-hide pb-4">
        <motion.div 
          className="space-y-4"
          initial="hidden"
          animate="visible"
          variants={{
            hidden: {},
            visible: {
              transition: {
                staggerChildren: 0.1,
                delayChildren: 0.2
              }
            }
          }}
        >
          {config.options?.map((option, index) => (
            <motion.div
              key={option.id}
              variants={{
                hidden: { opacity: 0, y: 20 },
                visible: { opacity: 1, y: 0 }
              }}
            >
              <OptionCard
                icon={option.icon}
                title={option.title}
                subtitle={option.subtitle}
                selected={selected === option.id}
                onClick={() => handleSelect(option.id)}
                index={index}
              />
            </motion.div>
          ))}
        </motion.div>
      </div>
      
      {/* 底部按钮 */}
      <motion.div
        className="px-5 py-6"
        style={{ background: colors.background.primary }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Button 
          fullWidth 
          size="lg" 
          onClick={handleContinue}
          disabled={!selected || !isActive}
        >
          Continue
        </Button>
      </motion.div>
    </div>
  )
}

export default CombinedWelcomeGoalScreen
