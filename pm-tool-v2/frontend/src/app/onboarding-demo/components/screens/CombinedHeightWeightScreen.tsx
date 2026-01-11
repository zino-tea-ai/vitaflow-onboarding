'use client'

import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useOnboardingStore } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfigProduction } from '../../data/screens-config-production'
import { NumberPicker } from '../ui/NumberPicker'
import { Button, BackButton } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { Mascot, MascotState } from '../character'
import { ChatBubble } from '../ui/ChatBubble'
import { ConversationalLayout } from '../ui/ConversationalLayout'
import { colors, bigTextStyles, shadows, cardBorder } from '../../lib/design-tokens'
import { Lock } from 'lucide-react'
import { WheelPicker } from '../ui/WheelPicker'

interface CombinedHeightWeightScreenProps {
  config: ScreenConfigProduction
}

/**
 * 合并页：身高 + 体重
 * 支持两种模式：
 * - default: 角色 + 气泡对话反馈
 * - bigtext: 大字体无角色，CTA固定底部
 */
// 单位转换函数
const cmToFtIn = (cm: number) => {
  const inches = cm / 2.54
  const feet = Math.floor(inches / 12)
  const remainingInches = Math.round(inches % 12)
  return { feet, inches: remainingInches, display: `${feet}'${remainingInches}"` }
}

const ftInToCm = (feet: number, inches: number) => {
  return Math.round((feet * 12 + inches) * 2.54)
}

const kgToLb = (kg: number) => Math.round(kg * 2.20462)
const lbToKg = (lb: number) => Math.round(lb / 2.20462)

export function CombinedHeightWeightScreen({ config }: CombinedHeightWeightScreenProps) {
  const { userData, setUserData, nextStep, prevStep, currentStep, totalSteps, unitSystem, setUnitSystem } = useOnboardingStore()
  const { characterStyle, copyStyle, conversationalFeedbackEnabled, currentVersion, prodStyle } = useABTestStore()
  
  // BigText 模式判断
  const isBigText = currentVersion === 'production' && prodStyle === 'bigtext'
  
  // 内部始终用公制存储
  const [heightCm, setHeightCm] = useState(userData.height || 170)
  const [weightKg, setWeightKg] = useState(userData.currentWeight || 65)
  const [mascotState, setMascotState] = useState<MascotState>('idle')
  const [hasInteracted, setHasInteracted] = useState(false)  // 跟踪用户是否操作过
  
  // 显示值（根据单位系统转换）
  const displayHeight = unitSystem === 'imperial' 
    ? Math.round(heightCm / 2.54)  // 总英寸数
    : heightCm
  const displayWeight = unitSystem === 'imperial' 
    ? kgToLb(weightKg) 
    : weightKg
  
  // 气泡文案 - 只有用户操作后才显示 insight
  const bubbleText = useMemo(() => {
    // 用户未操作时，显示引导问题
    if (!hasInteracted) return config.title
    
    if (!conversationalFeedbackEnabled) return config.title
    
    // 用户操作后，显示基于数据的 insight
    const heightInM = heightCm / 100
    const bmiVal = weightKg / (heightInM * heightInM)
    
    if (copyStyle === 'witty') {
      if (bmiVal < 18.5) return "Looking light! Let's fuel you up properly."
      if (bmiVal < 24) return "Right in the sweet spot!"
      if (bmiVal < 28) return "No judgment here. We'll get you moving."
      return "Time for a change. You've got this!"
    } else if (copyStyle === 'warm') {
      if (bmiVal < 18.5) return "We'll help you gain healthy weight!"
      if (bmiVal < 24) return "Your body is healthy! Keep it up."
      if (bmiVal < 28) return "Let's work together, you'll do great."
      return "It's never too late to start."
    } else {
      // 数据向文案也不显示 BMI 数值
      if (bmiVal < 18.5) return "We'll help you reach a healthy weight."
      if (bmiVal < 24) return "You're in a healthy range!"
      if (bmiVal < 28) return "Let's work on your goals together."
      return "We'll create a plan just for you."
    }
  }, [hasInteracted, heightCm, weightKg, copyStyle, conversationalFeedbackEnabled, config.title])
  
  // 检查这个组件实例是否是当前活动页面
  const isActive = currentStep === config.id
  
  // 如果不是活动页面，完全不渲染
  if (!isActive) {
    return null
  }
  
  const handleHeightChange = (val: number) => {
    // 根据单位系统转换回公制存储
    const cmValue = unitSystem === 'imperial' 
      ? Math.round(val * 2.54)  // 英寸转厘米
      : val
    // 只有值真的变化时才更新（避免单位切换时的抖动）
    if (cmValue !== heightCm) {
      setHeightCm(cmValue)
      setHasInteracted(true)  // 标记用户已操作
      if (conversationalFeedbackEnabled && !isBigText) {
        setMascotState('thinking')
        setTimeout(() => setMascotState('encouraging'), 300)
      }
    }
  }
  
  const handleWeightChange = (val: number) => {
    // 根据单位系统转换回公制存储
    const kgValue = unitSystem === 'imperial' 
      ? lbToKg(val) 
      : val
    // 只有值真的变化时才更新（避免单位切换时的抖动）
    if (kgValue !== weightKg) {
      setWeightKg(kgValue)
      setHasInteracted(true)  // 标记用户已操作
      if (conversationalFeedbackEnabled && !isBigText) {
        setMascotState('thinking')
        setTimeout(() => setMascotState('encouraging'), 300)
      }
    }
  }
  
  const handleContinue = () => {
    if (!isActive) return
    // 始终以公制存储
    setUserData('height', heightCm)
    setUserData('currentWeight', weightKg)
    if (conversationalFeedbackEnabled && !isBigText) {
      setMascotState('happy')
    }
    nextStep()
  }
  
  // BigText 模式 - 使用 ConversationalLayout 统一风格
  if (isBigText) {
    return (
      <ConversationalLayout
        currentStep={currentStep}
        totalSteps={totalSteps}
        onBack={prevStep}
        mascotState={mascotState}
        question={bubbleText || config.title}
        hint={config.subtitle}
        ctaText="Continue"
        onCtaClick={handleContinue}
      >
        {/* 单位切换器 */}
        <motion.div
          className="flex justify-center gap-2 mb-3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2 }}
        >
          <button
            className="px-4 py-2 rounded-lg text-[14px] font-medium transition-all"
            style={{
              background: unitSystem === 'metric' ? colors.slate[900] : colors.slate[100],
              color: unitSystem === 'metric' ? colors.white : colors.text.secondary,
            }}
            onClick={() => setUnitSystem('metric')}
          >
            Metric
          </button>
          <button
            className="px-4 py-2 rounded-lg text-[14px] font-medium transition-all"
            style={{
              background: unitSystem === 'imperial' ? colors.slate[900] : colors.slate[100],
              color: unitSystem === 'imperial' ? colors.white : colors.text.secondary,
            }}
            onClick={() => setUnitSystem('imperial')}
          >
            Imperial
          </button>
        </motion.div>

        {/* 双滚轮作为用户"回复" */}
        <motion.div
          className="space-y-3"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.15 }}
        >
          {/* 身高滚轮 */}
          <div 
            className="bg-white rounded-[12px] px-4 py-3" 
            style={{ 
              boxShadow: shadows.card,
              border: cardBorder.default,
            }}
          >
            <WheelPicker
              value={displayHeight}
              onChange={handleHeightChange}
              min={unitSystem === 'imperial' ? 48 : 140}   // 4' = 48", 140cm
              max={unitSystem === 'imperial' ? 90 : 220}   // 7'6" = 90", 220cm
              step={1}
              unit={unitSystem === 'imperial' ? 'in' : 'cm'}
              label="Height"
              orientation="horizontal"
            />
          </div>
          
          {/* 体重滚轮 */}
          <div 
            className="bg-white rounded-[12px] px-4 py-3" 
            style={{ 
              boxShadow: shadows.card,
              border: cardBorder.default,
            }}
          >
            <WheelPicker
              value={displayWeight}
              onChange={handleWeightChange}
              min={unitSystem === 'imperial' ? 66 : 30}    // 30kg = 66lb
              max={unitSystem === 'imperial' ? 330 : 150}  // 150kg = 330lb
              step={1}
              unit={unitSystem === 'imperial' ? 'lb' : 'kg'}
              label="Weight"
              orientation="horizontal"
            />
          </div>
          
        </motion.div>
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
      
      {/* 隐私承诺徽章 */}
      {config.showPrivacyBadge && (
        <motion.div 
          className="mx-5 mb-2"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div 
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm"
            style={{ 
              background: `${colors.accent.primary}15`,
              color: colors.accent.primary
            }}
          >
            <Lock size={14} />
            <span>Your data is completely private</span>
          </div>
        </motion.div>
      )}
      
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
        <div className="px-5 pt-2 pb-4">
          <motion.h1
            className="text-[24px] font-medium tracking-[-0.4px]"
            style={{ color: colors.text.primary }}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {config.title}
          </motion.h1>
          {config.subtitle && (
            <motion.p
              className="mt-3 text-[14px]"
              style={{ color: colors.text.secondary }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.1 }}
            >
              {config.subtitle}
            </motion.p>
          )}
        </div>
      )}
      
      {/* 双 Picker 区域 */}
      <div className="flex-1 px-5 flex flex-col justify-center">
        <motion.div
          className="flex gap-6 justify-center"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          {/* 身高 Picker */}
          <div className="flex flex-col items-center">
            <span 
              className="text-sm font-medium mb-3"
              style={{ color: colors.text.secondary }}
            >
              Height
            </span>
            <NumberPicker
              value={height}
              onChange={handleHeightChange}
              min={140}
              max={220}
              step={1}
              unit="cm"
            />
          </div>
          
          {/* 分隔线 */}
          <div 
            className="w-px self-stretch my-8"
            style={{ background: colors.border.light }}
          />
          
          {/* 体重 Picker */}
          <div className="flex flex-col items-center">
            <span 
              className="text-sm font-medium mb-3"
              style={{ color: colors.text.secondary }}
            >
              Weight
            </span>
            <NumberPicker
              value={weight}
              onChange={handleWeightChange}
              min={30}
              max={150}
              step={0.5}
              unit="kg"
            />
          </div>
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
          disabled={!isActive}
        >
          Continue
        </Button>
      </motion.div>
    </div>
  )
}

export default CombinedHeightWeightScreen
