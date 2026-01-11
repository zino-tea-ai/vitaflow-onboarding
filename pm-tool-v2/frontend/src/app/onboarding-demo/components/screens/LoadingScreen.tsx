'use client'

import { useEffect, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useOnboardingStore, calculateResults } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { personalizeText } from '../../utils/personalize'
import { Mascot, MascotState } from '../character'
import { ChatBubble } from '../ui/ChatBubble'
import { colors } from '../../lib/design-tokens'

interface LoadingScreenProps {
  config: ScreenConfig
}

/**
 * Loading Screen - 简洁等待页面
 * 
 * 简化设计：
 * - 移除浮动圆背景动效
 * - 简化进度环为单色
 * - 恢复角色 + 气泡陪伴
 */
export function LoadingScreen({ config }: LoadingScreenProps) {
  const { userData, setResults, nextStep, isManualNavigation, clearManualNavigation } = useOnboardingStore()
  const { characterStyle, copyStyle, conversationalFeedbackEnabled } = useABTestStore()
  
  // 分步加载动画
  const loadingSteps = useMemo(() => [
    { 
      text: personalizeText('Analyzing your goals, {{name}}...', userData.name), 
      duration: 1500,
      progress: 25
    },
    { 
      text: 'Calculating your calorie needs...', 
      duration: 1500,
      progress: 50
    },
    { 
      text: 'Creating your personalized plan...', 
      duration: 1500,
      progress: 75
    },
    { 
      text: personalizeText('Almost done, {{name}}!', userData.name), 
      duration: 1000,
      progress: 100
    }
  ], [userData.name])
  
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [progress, setProgress] = useState(0)
  
  // 角色状态
  const mascotState: MascotState = useMemo(() => {
    if (progress < 30) return 'thinking'
    if (progress < 70) return 'explaining'
    if (progress < 95) return 'excited'
    return 'celebrating'
  }, [progress])
  
  // 气泡文案
  const bubbleText = useMemo(() => {
    if (!conversationalFeedbackEnabled) return ''
    
    const texts = {
      witty: progress < 50 
        ? "Crunching those numbers like a champ..." 
        : progress < 90 
          ? "Almost there, hang tight!" 
          : "Done! You're gonna love this!",
      warm: progress < 50 
        ? "I'm working hard to create your perfect plan..." 
        : progress < 90 
          ? "Almost ready for you!" 
          : "All done! Can't wait to show you!",
      data: progress < 50 
        ? "Processing nutritional data..." 
        : progress < 90 
          ? "Optimizing recommendations..." 
          : "Analysis complete!"
    }
    return texts[copyStyle] || texts.warm
  }, [progress, copyStyle, conversationalFeedbackEnabled])
  
  useEffect(() => {
    if (isManualNavigation) {
      clearManualNavigation()
      return
    }
    
    let totalDuration = 0
    const stepTimers: NodeJS.Timeout[] = []
    
    loadingSteps.forEach((step, index) => {
      const timer = setTimeout(() => {
        setCurrentStepIndex(index)
        const targetProgress = step.progress
        const startProgress = index === 0 ? 0 : loadingSteps[index - 1].progress
        const duration = step.duration
        const steps = duration / 16
        
        let currentStep = 0
        const progressTimer = setInterval(() => {
          currentStep++
          const newProgress = startProgress + ((targetProgress - startProgress) * currentStep) / steps
          setProgress(newProgress)
          
          if (currentStep >= steps) {
            clearInterval(progressTimer)
            setProgress(targetProgress)
          }
        }, 16)
        
        if (index === loadingSteps.length - 1) {
          setTimeout(() => {
            const results = calculateResults(userData)
            if (results) {
              setResults(results)
            }
            nextStep()
          }, step.duration)
        }
      }, totalDuration)
      
      stepTimers.push(timer)
      totalDuration += step.duration
    })
    
    return () => {
      stepTimers.forEach(timer => clearTimeout(timer))
    }
  }, [loadingSteps, userData, setResults, nextStep, isManualNavigation, clearManualNavigation])
  
  return (
    <div 
      className="h-full flex flex-col items-center justify-center px-8" 
      style={{ 
        background: colors.background.primary, 
        fontFamily: 'var(--font-outfit)' 
      }}
    >
      {/* 简洁圆环进度 */}
      <div className="relative">
        <div className="relative w-40 h-40">
          {/* 背景环 */}
          <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
            <circle
              cx="50"
              cy="50"
              r="42"
              fill="none"
              stroke={colors.slate[200]}
              strokeWidth="6"
            />
            {/* 进度环 */}
            <circle
              cx="50"
              cy="50"
              r="42"
              fill="none"
              stroke={colors.slate[900]}
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={264}
              strokeDashoffset={264 - (264 * progress) / 100}
              style={{ transition: 'stroke-dashoffset 60ms linear' }}
            />
          </svg>
          
          {/* 中心百分比 */}
          <div className="absolute inset-0 flex items-center justify-center">
            <span 
              className="text-[28px] font-medium"
              style={{ color: colors.text.primary }}
            >
              {Math.round(progress)}%
            </span>
          </div>
        </div>
      </div>
      
      {/* 加载文本 */}
      <AnimatePresence mode="wait">
        <motion.p
          key={currentStepIndex}
          className="mt-6 text-center font-medium text-[15px]"
          style={{ color: colors.text.primary }}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.3 }}
        >
          {loadingSteps[currentStepIndex]?.text}
        </motion.p>
      </AnimatePresence>
      
      {/* 角色 + 气泡区域 */}
      {conversationalFeedbackEnabled && (
        <motion.div
          className="mt-8 flex items-start gap-4 max-w-sm"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
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
      
      {/* 底部提示 - 无角色时显示 */}
      {!conversationalFeedbackEnabled && (
        <motion.p
          className="absolute bottom-12 text-[13px]"
          style={{ color: colors.text.tertiary }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1 }}
        >
          This usually takes just a moment...
        </motion.p>
      )}
    </div>
  )
}
