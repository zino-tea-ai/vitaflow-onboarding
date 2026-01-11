'use client'

import { useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useOnboardingStore } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { Button, BackButton } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { Mascot, MascotState } from '../character'
import { ChatBubble } from '../ui/ChatBubble'
import { colors } from '../../lib/design-tokens'
import { personalizeText } from '../../utils/personalize'
import { getTransitionCopy, getPageTitle } from '../../data/feedback-copy'
import { Check, Zap, Target, Sparkles, Flame, Bell } from 'lucide-react'

interface TransitionScreenProps {
  config: ScreenConfig
}

function getMascotState(title: string): MascotState {
  if (title.includes('Nice to meet') || title.includes('meet you')) return 'waving'
  if (title.includes('Great') || title.includes('🎯')) return 'excited'
  if (title.includes('You can') || title.includes('💪')) return 'encouraging'
  if (title.includes('try it') || title.includes('📸')) return 'excited'
  if (title.includes('All Set') || title.includes('all set') || title.includes('🎉')) return 'happy'
  if (title.includes('Almost') || title.includes('⏳')) return 'thinking'
  if (title.includes('Pro tips') || title.includes('💡')) return 'happy'
  if (title.includes('sure') || title.includes('Are you')) return 'thinking'
  return 'neutral'
}

function isCompletionPage(title: string): boolean {
  return title.includes('All Set') || title.includes('all set') || title.toLowerCase().includes('complete')
}

export function TransitionScreen({ config }: TransitionScreenProps) {
  const { nextStep, prevStep, currentStep, totalSteps, goToStep, isManualNavigation, clearManualNavigation, userData } = useOnboardingStore()
  const { characterStyle, copyStyle, conversationalFeedbackEnabled, showMascot } = useABTestStore()
  
  const title = config.usePersonalization ? personalizeText(config.title, userData.name) : (config.title || '')
  const subtitle = config.usePersonalization ? personalizeText(config.subtitle, userData.name) : (config.subtitle || '')
  
  const mascotState = getMascotState(title)
  const isComplete = isCompletionPage(title)
  
  const bubbleText = useMemo(() => {
    if (!conversationalFeedbackEnabled) return ''
    if (isComplete) return getPageTitle('complete', copyStyle) || subtitle
    if (title.includes('Nice to meet')) return getTransitionCopy('ready', copyStyle) || subtitle
    if (title.includes('Great') || title.includes('🎯')) return getTransitionCopy('value_effectiveness', copyStyle) || subtitle
    if (title.includes('Almost')) return getTransitionCopy('almost_done', copyStyle) || subtitle
    return subtitle
  }, [title, subtitle, copyStyle, conversationalFeedbackEnabled, isComplete])
  
  useEffect(() => {
    if (isManualNavigation) {
      clearManualNavigation()
      return
    }
    if (config.autoAdvance) {
      const timer = setTimeout(() => nextStep(), conversationalFeedbackEnabled ? 2500 : 2000)
      return () => clearTimeout(timer)
    }
  }, [config.autoAdvance, nextStep, isManualNavigation, clearManualNavigation, conversationalFeedbackEnabled])
  
  const isConfirmationPage = config.id === 31
  const cleanTitle = title.replace(/[🎯💪📸🎉⏳💡]/g, '').trim()
  
  const handleConfirmLeave = () => goToStep(1)
  const handleStay = () => prevStep()
  const handleStartApp = () => {
    console.log('Onboarding completed!')
    nextStep()
  }
  
  // 完成页 - 对话式风格
  if (isComplete && !config.autoAdvance) {
    // 个性化文案 - 基于用户姓名和目标
    const userName = userData.name || 'friend'
    const goalText = userData.goal === 'lose_weight' 
      ? "Your weight loss journey begins now — I'll be right here cheering you on!" 
      : userData.goal === 'build_muscle'
      ? "Time to build that strength! I've got your back every rep of the way."
      : "Your healthy lifestyle starts today — let's make it happen together!"
    
    const completionBubbleText = `Hey ${userName}! We did it! ${goalText}`
    
    // 庆祝动画 - 五彩纸屑配置
    const confettiColors = ['#22C55E', '#FBBF24', '#3B82F6', '#EC4899', '#8B5CF6', '#F97316']
    const confettiCount = 50
    
    return (
      <div 
        className="h-full flex flex-col relative overflow-hidden"
        style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}
      >
        {/* 🎉 庆祝动画 - 五彩纸屑 */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden z-50">
          {Array.from({ length: confettiCount }).map((_, i) => {
            const color = confettiColors[i % confettiColors.length]
            const left = Math.random() * 100
            const delay = Math.random() * 0.8
            const duration = 2.5 + Math.random() * 1.5
            const size = 6 + Math.random() * 6
            const rotation = Math.random() * 360
            const swayAmount = 30 + Math.random() * 40
            const isCircle = Math.random() > 0.5
            
            return (
              <motion.div
                key={i}
                className="absolute"
                style={{
                  left: `${left}%`,
                  top: -20,
                  width: isCircle ? size : size * 0.6,
                  height: isCircle ? size : size * 1.2,
                  background: color,
                  borderRadius: isCircle ? '50%' : '2px',
                  transform: `rotate(${rotation}deg)`,
                }}
                initial={{ y: -20, opacity: 1, rotate: rotation }}
                animate={{
                  y: ['0vh', '110vh'],
                  x: [0, swayAmount, -swayAmount, swayAmount, 0],
                  rotate: [rotation, rotation + 360 * (Math.random() > 0.5 ? 1 : -1)],
                  opacity: [1, 1, 1, 0.8, 0],
                }}
                transition={{
                  duration: duration,
                  delay: delay,
                  ease: 'linear',
                  times: [0, 0.25, 0.5, 0.75, 1],
                }}
              />
            )
          })}
          
          {/* ✨ 星星爆炸效果 - 从中心散开 */}
          {Array.from({ length: 12 }).map((_, i) => {
            const angle = (i / 12) * 360
            const distance = 120 + Math.random() * 60
            const x = Math.cos((angle * Math.PI) / 180) * distance
            const y = Math.sin((angle * Math.PI) / 180) * distance
            const starColor = confettiColors[i % confettiColors.length]
            
            return (
              <motion.div
                key={`star-${i}`}
                className="absolute"
                style={{
                  left: '50%',
                  top: '35%',
                  width: 8,
                  height: 8,
                }}
                initial={{ x: 0, y: 0, scale: 0, opacity: 0 }}
                animate={{
                  x: [0, x],
                  y: [0, y],
                  scale: [0, 1.5, 0],
                  opacity: [0, 1, 0],
                }}
                transition={{
                  duration: 0.8,
                  delay: 0.3 + i * 0.03,
                  ease: 'easeOut',
                }}
              >
                <svg width="8" height="8" viewBox="0 0 8 8">
                  <path
                    d="M4 0L4.9 2.9H8L5.5 4.7L6.4 8L4 6L1.6 8L2.5 4.7L0 2.9H3.1L4 0Z"
                    fill={starColor}
                  />
                </svg>
              </motion.div>
            )
          })}
        </div>
        
        <ProgressBar current={currentStep} total={totalSteps} />
        
        {/* 头部导航 */}
        <div className="flex items-center justify-between px-5 py-3">
          <BackButton onClick={prevStep} />
          <div />
        </div>
        
        {/* 对话区域 - 角色 + 气泡 */}
        <motion.div 
          className="px-5 pt-3 pb-3 flex-shrink-0"
          style={{ height: '148px' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4 }}
        >
          <div className="flex items-start gap-4">
            {/* 角色 - lg size */}
            <motion.div
              className="flex-shrink-0"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.1 }}
            >
              <Mascot style={characterStyle} state="celebrating" size="lg" />
            </motion.div>
            
            {/* 问题气泡 */}
            <motion.div 
              className="flex-1 pt-3"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, delay: 0.2 }}
            >
              <div 
                className="inline-block px-4 py-4 rounded-[12px] rounded-tl-sm max-w-full"
                style={{
                  background: colors.white,
                  border: '1px solid rgba(15, 23, 42, 0.08)',
                  boxShadow: '0px 1px 3px rgba(15, 23, 42, 0.08)',
                }}
              >
                <p 
                  className="text-[20px] font-medium"
                  style={{ color: colors.text.primary, letterSpacing: '-0.4px', lineHeight: '28px' }}
                >
                  {completionBubbleText}
                </p>
              </div>
            </motion.div>
          </div>
        </motion.div>
        
        {/* 用户回复区域 - 精简总结 */}
        <motion.div 
          className="flex-1 px-5 pt-4 pb-4 flex flex-col justify-center"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.25 }}
        >
          {/* 3个关键总结 */}
          <div className="space-y-3">
            {[
              { 
                icon: Target, 
                title: 'Your goal', 
                desc: userData.goal === 'lose_weight' ? 'Lose weight' : userData.goal === 'build_muscle' ? 'Build muscle' : 'Stay healthy' 
              },
              { 
                icon: Flame, 
                title: 'Daily calories', 
                desc: 'Personalized just for you' 
              },
              { 
                icon: Bell, 
                title: 'Reminders', 
                desc: 'Smart notifications on' 
              },
            ].map((item, index) => (
              <motion.div
                key={item.title}
                className="flex items-center gap-4 p-5 rounded-[12px]"
                style={{ 
                  background: colors.white, 
                  border: '1px solid rgba(15, 23, 42, 0.08)',
                  boxShadow: '0px 1px 3px rgba(15, 23, 42, 0.08)',
                }}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 + index * 0.1 }}
              >
                <div 
                  className="w-12 h-12 rounded-[12px] flex items-center justify-center flex-shrink-0"
                  style={{ background: colors.slate[50] }}
                >
                  <item.icon className="w-6 h-6" style={{ color: colors.slate[600] }} strokeWidth={1.5} />
                </div>
                <div className="flex-1 min-w-0">
                  <p 
                    className="font-medium text-[17px]" 
                    style={{ color: colors.text.primary, letterSpacing: '-0.4px' }}
                  >
                    {item.title}
                  </p>
                  <p 
                    className="text-[14px] mt-1" 
                    style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}
                  >
                    {item.desc}
                  </p>
                </div>
                <motion.div
                  className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ background: colors.accent.primary }}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.5 + index * 0.1, type: 'spring', stiffness: 400 }}
                >
                  <Check className="w-4 h-4" style={{ color: colors.slate[900] }} strokeWidth={2.5} />
                </motion.div>
              </motion.div>
            ))}
          </div>
        </motion.div>
        
        {/* 底部 CTA */}
        <motion.div 
          className="px-5 pb-8 pt-4" 
          style={{ background: colors.background.primary }} 
          initial={{ opacity: 0, y: 16 }} 
          animate={{ opacity: 1, y: 0 }} 
          transition={{ delay: 0.5 }}
        >
          <Button fullWidth size="lg" onClick={handleStartApp}>Start Using VitaFlow</Button>
        </motion.div>
      </div>
    )
  }
  
  // 默认过渡页
  return (
    <div className="h-full flex flex-col" style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}>
      {!config.autoAdvance && <ProgressBar current={currentStep} total={totalSteps} />}
      
      {!config.autoAdvance && !isConfirmationPage && (
        <div className="flex items-center justify-between px-5 py-2">
          <BackButton onClick={prevStep} />
          <div />
        </div>
      )}
      
      {conversationalFeedbackEnabled && showMascot && !config.autoAdvance ? (
        <motion.div className="px-5 pt-2 pb-4 flex items-start gap-4" initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <Mascot style={characterStyle} state={mascotState} size="md" />
          <div className="flex-1 pt-3">
            <ChatBubble text={bubbleText} visible={!!bubbleText} position="bottom-right" size="md" />
          </div>
        </motion.div>
      ) : !config.autoAdvance ? (
        <motion.div className="px-5 pt-4 pb-2" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <motion.h1 className="text-[28px] font-medium tracking-[-0.4px]" style={{ color: colors.text.primary }}>{cleanTitle}</motion.h1>
          <motion.p className="mt-2 text-[15px]" style={{ color: colors.text.secondary }}>{subtitle}</motion.p>
        </motion.div>
      ) : null}
      
      <div className="flex-1 px-5 pt-2 flex flex-col items-center justify-center">
        {config.autoAdvance && (
          <>
            <motion.h1 className="text-[28px] font-medium tracking-[-0.4px] text-center" style={{ color: colors.text.primary }} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
              {cleanTitle}
            </motion.h1>
            <motion.p className="mt-2 text-[15px] text-center" style={{ color: colors.text.secondary }} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
              {subtitle}
            </motion.p>
          </>
        )}
      </div>
      
      {!config.autoAdvance && (
        <motion.div className="px-5 py-6 space-y-3" style={{ background: colors.background.primary }} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
          {isConfirmationPage ? (
            <>
              <Button fullWidth size="lg" onClick={handleStay}>Claim My 50% Discount</Button>
              <Button fullWidth size="lg" variant="ghost" onClick={handleConfirmLeave}>No thanks, I'll pay full price later</Button>
            </>
          ) : (
            <Button fullWidth size="lg" onClick={nextStep}>Continue</Button>
          )}
        </motion.div>
      )}
    </div>
  )
}
