'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useOnboardingStore } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { useLongPress } from '../../hooks/useLongPress'
import { Button, BackButton, SkipButton } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { colors, shadows, cardBorder } from '../../lib/design-tokens'
import { haptic } from '../../lib/haptics'
import { Check, X, Zap } from 'lucide-react'

interface ScanGameScreenProps {
  config: ScreenConfig
}

export function ScanGameScreen({ config }: ScanGameScreenProps) {
  const { completeScanGame, scanGameCompleted, nextStep, prevStep, currentStep, totalSteps } = useOnboardingStore()
  const [showResult, setShowResult] = useState(false)
  const [scanPhase, setScanPhase] = useState<'idle' | 'scanning' | 'analyzing' | 'complete'>('idle')
  
  const { isPressed, progress, handlers } = useLongPress({
    threshold: 2000,
    onStart: () => {
      haptic('light')
      setScanPhase('scanning')
    },
    onComplete: () => {
      haptic('success')
      setScanPhase('analyzing')
      setTimeout(() => {
        setScanPhase('complete')
        setShowResult(true)
        completeScanGame()
      }, 800)
    }
  })
  
  useEffect(() => {
    if (scanGameCompleted && showResult) {
      const timer = setTimeout(() => nextStep(), 2500)
      return () => clearTimeout(timer)
    }
  }, [scanGameCompleted, showResult, nextStep])
  
  // 沉浸式相机扫描界面
  return (
    <div 
      className="h-full flex flex-col relative overflow-hidden"
      style={{ 
        background: '#0A0A0B',
        fontFamily: 'var(--font-outfit)' 
      }}
    >
      {/* 顶部状态栏 - 半透明 */}
      <div className="relative z-20">
        <ProgressBar current={currentStep} total={totalSteps} />
        
        <div className="flex items-center justify-between px-5 py-2">
          <button 
            onClick={prevStep}
            className="w-10 h-10 rounded-full flex items-center justify-center"
            style={{ background: 'rgba(255,255,255,0.1)' }}
          >
            <X className="w-5 h-5 text-white" />
          </button>
          <SkipButton onClick={nextStep} />
        </div>
        
        {/* 叙事承接标题 */}
        {!showResult && (
          <motion.div 
            className="text-center px-5 mt-2"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <h1 className="text-[24px] font-bold text-white tracking-[-0.5px]">
              Log your first meal
            </h1>
            <p className="text-[14px] mt-1" style={{ color: 'rgba(255,255,255,0.6)' }}>
              Your plan is ready — let's start tracking!
            </p>
          </motion.div>
        )}
      </div>
      
      {/* 主相机视图区域 */}
      <div className="flex-1 relative flex items-center justify-center">
        {/* 相机取景器背景 */}
        <div 
          className="absolute inset-4 rounded-[24px] overflow-hidden"
          style={{ 
            background: 'linear-gradient(180deg, #1a1a1b 0%, #0f0f10 100%)',
            border: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          {/* 网格线 - 三分法 */}
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute left-1/3 top-0 bottom-0 w-px" style={{ background: 'rgba(255,255,255,0.06)' }} />
            <div className="absolute right-1/3 top-0 bottom-0 w-px" style={{ background: 'rgba(255,255,255,0.06)' }} />
            <div className="absolute top-1/3 left-0 right-0 h-px" style={{ background: 'rgba(255,255,255,0.06)' }} />
            <div className="absolute bottom-1/3 left-0 right-0 h-px" style={{ background: 'rgba(255,255,255,0.06)' }} />
          </div>
          
          {/* 食物 - 居中 */}
          <div className="absolute inset-0 flex items-center justify-center">
            <motion.div
              animate={{ 
                scale: isPressed ? [1, 1.05, 1] : 1,
                rotate: scanPhase === 'analyzing' ? [0, 3, -3, 0] : 0
              }}
              transition={{ 
                duration: isPressed ? 0.8 : 0.5, 
                repeat: isPressed || scanPhase === 'analyzing' ? Infinity : 0 
              }}
            >
              <span className="text-[120px] drop-shadow-2xl">🍕</span>
            </motion.div>
          </div>
          
          {/* 扫描框 - 四角 */}
          <div className="absolute inset-12 pointer-events-none">
            {/* 左上 */}
            <motion.div 
              className="absolute top-0 left-0 w-12 h-12"
              animate={{ 
                borderColor: isPressed ? colors.accent.primary : 'rgba(255,255,255,0.4)',
              }}
            >
              <div className="absolute top-0 left-0 w-full h-1 rounded-full" style={{ background: isPressed ? colors.accent.primary : 'rgba(255,255,255,0.4)' }} />
              <div className="absolute top-0 left-0 w-1 h-full rounded-full" style={{ background: isPressed ? colors.accent.primary : 'rgba(255,255,255,0.4)' }} />
            </motion.div>
            {/* 右上 */}
            <motion.div className="absolute top-0 right-0 w-12 h-12">
              <div className="absolute top-0 right-0 w-full h-1 rounded-full" style={{ background: isPressed ? colors.accent.primary : 'rgba(255,255,255,0.4)' }} />
              <div className="absolute top-0 right-0 w-1 h-full rounded-full" style={{ background: isPressed ? colors.accent.primary : 'rgba(255,255,255,0.4)' }} />
            </motion.div>
            {/* 左下 */}
            <motion.div className="absolute bottom-0 left-0 w-12 h-12">
              <div className="absolute bottom-0 left-0 w-full h-1 rounded-full" style={{ background: isPressed ? colors.accent.primary : 'rgba(255,255,255,0.4)' }} />
              <div className="absolute bottom-0 left-0 w-1 h-full rounded-full" style={{ background: isPressed ? colors.accent.primary : 'rgba(255,255,255,0.4)' }} />
            </motion.div>
            {/* 右下 */}
            <motion.div className="absolute bottom-0 right-0 w-12 h-12">
              <div className="absolute bottom-0 right-0 w-full h-1 rounded-full" style={{ background: isPressed ? colors.accent.primary : 'rgba(255,255,255,0.4)' }} />
              <div className="absolute bottom-0 right-0 w-1 h-full rounded-full" style={{ background: isPressed ? colors.accent.primary : 'rgba(255,255,255,0.4)' }} />
            </motion.div>
          </div>
          
          {/* 扫描线动画 */}
          {isPressed && (
            <motion.div
              className="absolute left-12 right-12 h-1 rounded-full"
              style={{ 
                background: `linear-gradient(90deg, transparent 0%, ${colors.accent.primary} 50%, transparent 100%)`,
                boxShadow: `0 0 20px ${colors.accent.primary}`,
              }}
              animate={{ top: ['15%', '85%', '15%'] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
            />
          )}
          
          {/* 扫描进度覆盖 */}
          {isPressed && (
            <motion.div
              className="absolute inset-0"
              style={{ 
                background: `linear-gradient(180deg, ${colors.accent.primary}15 0%, transparent ${progress * 100}%)`,
              }}
            />
          )}
          
          {/* AI 分析状态 */}
          {scanPhase === 'analyzing' && (
            <motion.div
              className="absolute inset-0 flex items-center justify-center"
              style={{ background: 'rgba(0,0,0,0.6)' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <motion.div
                className="w-20 h-20 rounded-full flex items-center justify-center"
                style={{ 
                  background: `linear-gradient(135deg, ${colors.accent.primary} 0%, #34D399 100%)`,
                  boxShadow: `0 0 40px ${colors.accent.primary}60`,
                }}
                animate={{ scale: [1, 1.1, 1], rotate: [0, 180, 360] }}
                transition={{ duration: 1, repeat: Infinity }}
              >
                <Zap className="w-10 h-10 text-white" />
              </motion.div>
            </motion.div>
          )}
        </div>
        
        {/* 实时识别标签 */}
        <AnimatePresence>
          {isPressed && scanPhase === 'scanning' && (
            <motion.div
              className="absolute top-8 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full"
              style={{ 
                background: 'rgba(0,0,0,0.7)',
                backdropFilter: 'blur(10px)',
                border: `1px solid ${colors.accent.primary}40`,
              }}
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <div className="flex items-center gap-2">
                <motion.div 
                  className="w-2 h-2 rounded-full"
                  style={{ background: colors.accent.primary }}
                  animate={{ opacity: [1, 0.4, 1] }}
                  transition={{ duration: 0.8, repeat: Infinity }}
                />
                <span className="text-white text-[14px] font-medium">
                  Detecting... {Math.round(progress * 100)}%
                </span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        
        {/* 结果卡片 - 从底部滑入 */}
        <AnimatePresence>
          {showResult && (
            <motion.div
              className="absolute bottom-4 left-4 right-4 p-5 rounded-[12px]"
              style={{ 
                background: colors.white,
                border: cardBorder.default,
                boxShadow: shadows.lg,
              }}
              initial={{ y: 300, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            >
              {/* 成功标记 */}
              <motion.div
                className="absolute -top-5 left-1/2 -translate-x-1/2 w-10 h-10 rounded-full flex items-center justify-center"
                style={{ background: colors.accent.primary }}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.2, type: 'spring' }}
              >
                <Check className="w-5 h-5" style={{ color: colors.slate[900] }} strokeWidth={2.5} />
              </motion.div>
              
              <div className="mt-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div 
                      className="w-14 h-14 rounded-[12px] flex items-center justify-center"
                      style={{ background: colors.slate[50] }}
                    >
                      <span className="text-[28px]">🍕</span>
                    </div>
                    <div>
                      <p 
                        className="font-medium text-[17px]" 
                        style={{ color: colors.text.primary, letterSpacing: '-0.4px' }}
                      >
                        Pizza Slice
                      </p>
                      <p 
                        className="text-[13px] mt-0.5" 
                        style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}
                      >
                        Italian • 1 slice
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p 
                      className="font-medium text-[24px]" 
                      style={{ color: colors.text.primary, letterSpacing: '-0.4px' }}
                    >
                      285
                    </p>
                    <p 
                      className="text-[12px]" 
                      style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}
                    >
                      kcal
                    </p>
                  </div>
                </div>
                
                {/* 营养素 - 简洁横排 */}
                <div 
                  className="mt-4 p-3 rounded-[10px] flex items-center justify-between"
                  style={{ background: colors.slate[50] }}
                >
                  {[
                    { label: 'Protein', value: '12g' },
                    { label: 'Carbs', value: '36g' },
                    { label: 'Fat', value: '10g' },
                  ].map((item, i) => (
                    <motion.div 
                      key={item.label}
                      className="text-center"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.3 + i * 0.08 }}
                    >
                      <p 
                        className="text-[15px] font-medium" 
                        style={{ color: colors.text.primary, letterSpacing: '-0.4px' }}
                      >
                        {item.value}
                      </p>
                      <p 
                        className="text-[12px] mt-0.5" 
                        style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}
                      >
                        {item.label}
                      </p>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      
      {/* 底部控制区 */}
      <motion.div 
        className="relative z-20 px-5 pt-4 pb-8"
        style={{ background: 'linear-gradient(180deg, transparent 0%, #0A0A0B 30%)' }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        {!showResult ? (
          <>
            {/* 提示文字 */}
            <p className="text-center mb-5 text-[15px]" style={{ color: 'rgba(255,255,255,0.7)' }}>
              {isPressed ? 'AI is analyzing...' : 'Hold the button to scan'}
            </p>
            
            {/* 快门按钮 - 圆形 */}
            <div className="flex justify-center">
              <motion.button
                className="relative w-20 h-20 rounded-full flex items-center justify-center"
                style={{ 
                  background: 'transparent',
                  border: '4px solid rgba(255,255,255,0.9)',
                }}
                {...handlers}
                whileTap={{ scale: 0.95 }}
              >
                {/* 内圈 */}
                <motion.div
                  className="w-16 h-16 rounded-full"
                  style={{ 
                    background: isPressed 
                      ? `conic-gradient(${colors.accent.primary} ${progress * 360}deg, rgba(255,255,255,0.2) 0deg)`
                      : 'rgba(255,255,255,0.9)',
                  }}
                  animate={{ 
                    scale: isPressed ? 0.9 : 1,
                  }}
                  transition={{ duration: 0.2 }}
                />
                
                {/* 脉冲效果 */}
                {isPressed && (
                  <motion.div
                    className="absolute inset-0 rounded-full"
                    style={{ border: `2px solid ${colors.accent.primary}` }}
                    animate={{ scale: [1, 1.3, 1], opacity: [0.8, 0, 0.8] }}
                    transition={{ duration: 1, repeat: Infinity }}
                  />
                )}
              </motion.button>
            </div>
            
            <p className="text-center mt-4 text-[13px]" style={{ color: 'rgba(255,255,255,0.4)' }}>
              Press and hold for 2 seconds
            </p>
          </>
        ) : (
          <div className="space-y-3">
            <p className="text-center text-[15px] text-white font-medium">
              First meal logged!
            </p>
            <Button fullWidth size="lg" onClick={nextStep}>
              Continue
            </Button>
          </div>
        )}
      </motion.div>
    </div>
  )
}
