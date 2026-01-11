'use client'

import { useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useOnboardingStore, calculateResults } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { Button, BackButton } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { personalizeText } from '../../utils/personalize'
import { AnimatedNumber } from '../motion/AnimatedNumber'
import { Mascot } from '../character'
import { ChatBubble } from '../ui/ChatBubble'
import { ConversationalLayout } from '../ui/ConversationalLayout'
import { colors, bigTextStyles, shadows, cardBorder } from '../../lib/design-tokens'

interface ResultScreenProps {
  config: ScreenConfig
}

/**
 * Result Screen - 简洁结果展示
 * 
 * BigText 模式：大字体 + 角色融入
 */
export function ResultScreen({ config }: ResultScreenProps) {
  const { results, userData, nextStep, prevStep, currentStep, totalSteps, setResults } = useOnboardingStore()
  const { currentVersion, characterStyle, conversationalFeedbackEnabled, copyStyle, prodStyle } = useABTestStore()
  
  const isProduction = currentVersion === 'production'
  const isBigText = isProduction && prodStyle === 'bigtext'
  
  // 总是重新计算结果，确保包含最新字段（protein/carbs/fat）
  const displayResults = useMemo(() => {
    return calculateResults(userData)
  }, [userData])
  
  useEffect(() => {
    if (displayResults) {
      setResults(displayResults)
    }
  }, [displayResults, setResults])
  
  const title = config.usePersonalization ? personalizeText(config.title, userData.name) : config.title
  const subtitle = config.usePersonalization ? personalizeText(config.subtitle, userData.name) : config.subtitle
  
  // 获取 resetDemo 用于重置
  const { resetDemo } = useOnboardingStore()
  
  if (!displayResults) {
    return (
      <div className="h-full flex flex-col items-center justify-center" style={{ background: colors.background.primary }}>
        <div className="text-center px-8">
          <p className="text-[16px] font-medium" style={{ color: colors.text.primary }}>Missing profile data</p>
          <p className="text-[14px] mt-2 mb-6" style={{ color: colors.text.secondary }}>Please complete your profile first</p>
          <Button onClick={resetDemo} size="lg">
            Start Over
          </Button>
        </div>
      </div>
    )
  }
  
  const weightDiff = (userData.targetWeight || 0) - (userData.currentWeight || 0)
  const isLosing = weightDiff < 0
  const isGaining = weightDiff > 0
  const weeksToGoal = Math.ceil(Math.abs(weightDiff) / 0.5)
  
  // 角色文案
  const mascotText = useMemo(() => {
    const texts = {
      witty: isLosing 
        ? `${weeksToGoal} weeks? You've totally got this!` 
        : `Building muscle mode ON! Let's crush it!`,
      warm: isLosing 
        ? `I believe in you! ${weeksToGoal} weeks and you'll be there!` 
        : `Every step counts! I'm so proud of you already!`,
      data: isLosing 
        ? `Based on 10,000+ users: 89% achieve their goal with this plan.` 
        : `Users with similar profiles see +15% strength gains in 8 weeks.`
    }
    return texts[copyStyle] || texts.warm
  }, [copyStyle, weeksToGoal, isLosing])
  
  // Production 版本 - 使用 ConversationalLayout 统一风格
  if (isProduction) {
    return (
      <ConversationalLayout
        currentStep={currentStep}
        totalSteps={totalSteps}
        onBack={prevStep}
        mascotState="proud"
        question={mascotText}
        ctaText="Continue"
        onCtaClick={nextStep}
      >
        {/* 大标题 */}
        <motion.h1
          className="text-[24px] font-medium mb-3"
          style={{ 
            color: colors.text.primary,
            letterSpacing: '-0.5px',
            lineHeight: '28px',
          }}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          {title}
        </motion.h1>
        
        {/* 主卡片 - 白色背景 */}
        <motion.div
          className="rounded-[12px] p-4 mb-3"
          style={{ 
            background: colors.white,
            border: cardBorder.default,
            boxShadow: shadows.card,
          }}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <p className="text-[12px] font-medium" style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}>Daily Target</p>
          <div className="flex items-baseline mt-1">
            <AnimatedNumber
              value={displayResults.dailyCalories}
              decimals={0}
              className="text-[32px] font-medium"
              style={{ color: colors.text.primary }}
              duration={2}
            />
            <span className="text-[12px] ml-2" style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}>kcal</span>
          </div>
          
          {/* 进度指示 */}
          <div className="mt-3 flex items-center gap-3">
            <div 
              className="w-2 h-2 rounded-full"
              style={{ background: colors.accent.primary }}
            />
            <p className="text-[12px]" style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}>
              {isLosing && `${weeksToGoal} weeks to reach ${userData.targetWeight}kg`}
              {isGaining && `${weeksToGoal} weeks to gain ${Math.abs(weightDiff).toFixed(1)}kg`}
              {!isLosing && !isGaining && 'Maintain current weight'}
            </p>
          </div>
        </motion.div>
        
        {/* 数据卡片网格 */}
        <motion.div 
          className="grid grid-cols-2 gap-3"
          initial="hidden"
          animate="visible"
          variants={{
            hidden: {},
            visible: { transition: { staggerChildren: 0.08, delayChildren: 0.25 } }
          }}
        >
          <motion.div
            className="rounded-[12px] p-3"
            style={{ 
              background: colors.white,
              border: cardBorder.default,
              boxShadow: shadows.card
            }}
            variants={{
              hidden: { opacity: 0, y: 8 },
              visible: { opacity: 1, y: 0 }
            }}
          >
            <p className="text-[12px] font-medium" style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}>Goal</p>
            <p className="text-[18px] font-medium mt-1" style={{ color: colors.text.primary }}>
              {isLosing ? '-' : isGaining ? '+' : ''}{Math.abs(weightDiff).toFixed(1)}
              <span className="text-[12px] ml-1" style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}>kg</span>
            </p>
          </motion.div>
          
          <motion.div
            className="rounded-[12px] p-3"
            style={{ 
              background: colors.white,
              border: cardBorder.default,
              boxShadow: shadows.card
            }}
            variants={{
              hidden: { opacity: 0, y: 8 },
              visible: { opacity: 1, y: 0 }
            }}
          >
            <p className="text-[12px] font-medium" style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}>Timeline</p>
            <p className="text-[18px] font-medium mt-1" style={{ color: colors.text.primary }}>
              {weeksToGoal}
              <span className="text-[12px] ml-1" style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}>weeks</span>
            </p>
          </motion.div>
        </motion.div>
        
        {/* 三大营养素 */}
        <motion.div 
          className="grid grid-cols-3 gap-3 mt-3"
          initial="hidden"
          animate="visible"
          variants={{
            hidden: {},
            visible: { transition: { staggerChildren: 0.05, delayChildren: 0.3 } }
          }}
        >
          <motion.div
            className="rounded-[12px] p-3"
            style={{ 
              background: colors.white,
              border: cardBorder.default,
              boxShadow: shadows.card
            }}
            variants={{
              hidden: { opacity: 0, y: 8 },
              visible: { opacity: 1, y: 0 }
            }}
          >
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ background: '#07D1EC' }} />
              <p className="text-[12px] font-medium" style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}>Protein</p>
            </div>
            <p className="text-[16px] font-medium mt-1" style={{ color: colors.text.primary }}>
              {displayResults.protein}g
            </p>
          </motion.div>
          
          <motion.div
            className="rounded-[12px] p-3"
            style={{ 
              background: colors.white,
              border: cardBorder.default,
              boxShadow: shadows.card
            }}
            variants={{
              hidden: { opacity: 0, y: 8 },
              visible: { opacity: 1, y: 0 }
            }}
          >
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ background: '#FDCA91' }} />
              <p className="text-[12px] font-medium" style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}>Carbs</p>
            </div>
            <p className="text-[16px] font-medium mt-1" style={{ color: colors.text.primary }}>
              {displayResults.carbs}g
            </p>
          </motion.div>
          
          <motion.div
            className="rounded-[12px] p-3"
            style={{ 
              background: colors.white,
              border: cardBorder.default,
              boxShadow: shadows.card
            }}
            variants={{
              hidden: { opacity: 0, y: 8 },
              visible: { opacity: 1, y: 0 }
            }}
          >
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ background: '#FB6C83' }} />
              <p className="text-[12px] font-medium" style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}>Fat</p>
            </div>
            <p className="text-[16px] font-medium mt-1" style={{ color: colors.text.primary }}>
              {displayResults.fat}g
            </p>
          </motion.div>
        </motion.div>
      </ConversationalLayout>
    )
  }
  
  // 原版 - 简化版
  return (
    <div className="h-full flex flex-col" style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}>
      <ProgressBar current={currentStep} total={totalSteps} />
      
      <div className="flex items-center justify-between px-5 py-2">
        <BackButton onClick={prevStep} />
        <div />
      </div>
      
      <div className="px-5 pt-4 pb-4">
        <motion.h1
          className="text-[24px] font-medium tracking-[-0.4px]"
          style={{ color: colors.text.primary }}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          {title}
        </motion.h1>
        <motion.p
          className="mt-3 text-[14px]"
          style={{ color: colors.text.secondary }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
        >
          {subtitle}
        </motion.p>
      </div>
      
      <div className="flex-1 px-5 pb-4 overflow-y-auto scrollbar-hide">
        <motion.div
          className="rounded-[20px] p-6 mb-4"
          style={{ background: colors.slate[900] }}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <p className="text-white/70 text-[13px] font-medium">Your Daily Target</p>
          <div className="flex items-baseline mt-2">
            <AnimatedNumber
              value={displayResults.dailyCalories}
              decimals={0}
              className="text-[48px] font-medium text-white"
            />
            <span className="text-white/70 ml-2 text-[18px]">kcal</span>
          </div>
          
          <div className="mt-4 flex items-center gap-2">
            <div className="w-2 h-2 rounded-full" style={{ background: colors.accent.primary }} />
            <p className="text-white/80 text-[13px]">
              {isLosing && `Lose ${Math.abs(weightDiff)}kg by ${displayResults.targetDate}`}
              {isGaining && `Gain ${Math.abs(weightDiff)}kg by ${displayResults.targetDate}`}
              {!isLosing && !isGaining && 'Maintain your current weight'}
            </p>
          </div>
        </motion.div>
        
        <div className="grid grid-cols-2 gap-4">
          <motion.div
            className="rounded-[16px] p-4"
            style={{ background: colors.surface.white, boxShadow: colors.shadows.card }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <p className="text-[12px] font-medium" style={{ color: colors.text.secondary }}>Your BMI</p>
            <AnimatedNumber
              value={displayResults.bmi}
              decimals={1}
              className="text-[24px] font-medium mt-3"
              style={{ color: colors.text.primary }}
            />
            <p className="text-[11px] mt-1" style={{ color: colors.text.primary }}>
              {displayResults.bmi < 18.5 ? 'Underweight' : 
               displayResults.bmi < 25 ? 'Normal' : 
               displayResults.bmi < 30 ? 'Overweight' : 'Obese'}
            </p>
          </motion.div>
          
          <motion.div
            className="rounded-[16px] p-4"
            style={{ background: colors.surface.white, boxShadow: colors.shadows.card }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
          >
            <p className="text-[12px] font-medium" style={{ color: colors.text.secondary }}>Your TDEE</p>
            <AnimatedNumber
              value={displayResults.tdee}
              decimals={0}
              className="text-[24px] font-medium mt-3"
              style={{ color: colors.text.primary }}
            />
            <p className="text-[11px] mt-1" style={{ color: colors.text.secondary }}>kcal/day</p>
          </motion.div>
        </div>
      </div>
      
      {/* 角色区域 */}
      {conversationalFeedbackEnabled && (
        <motion.div
          className="px-5 py-4 flex items-start gap-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <Mascot 
            style={characterStyle}
            state="proud"
            size="sm"
          />
          <div className="flex-1 pt-1">
            <ChatBubble
              text={mascotText}
              visible={true}
              position="bottom-right"
              size="sm"
            />
          </div>
        </motion.div>
      )}
      
      <motion.div
        className="px-5 py-6"
        style={{ background: colors.background.primary }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <Button fullWidth size="lg" onClick={nextStep}>
          Continue
        </Button>
      </motion.div>
    </div>
  )
}
