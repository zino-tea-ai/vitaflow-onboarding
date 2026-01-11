'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useOnboardingStore } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { Mascot, MascotState } from '../character'
import { Button } from '../ui/Button'
import { colors } from '../../lib/design-tokens'

interface IntroductionScreenProps {
  config: ScreenConfig
}

// 开场白 - 产品定位 + 核心功能
const INTRO_LINES = [
  { text: "Snap a photo.", delay: 0.5 },
  { text: "Get nutrition insights.", delay: 1.8 },
  { text: "Instantly.", delay: 3.0 },
]

/**
 * 电影式开场序列
 * 
 * Phase 1: Logo 失焦聚焦入场 → 停留 → 淡出
 * Phase 2: 电影开场白一句句出现
 * Phase 3: 角色从无到有，闭眼到睁眼
 */
export function IntroductionScreen({ config }: IntroductionScreenProps) {
  const { nextStep } = useOnboardingStore()
  const { characterStyle } = useABTestStore()
  
  const [phase, setPhase] = useState<1 | 2 | 3>(1)
  const [mascotState, setMascotState] = useState<MascotState>('idle')
  const [showButton, setShowButton] = useState(false)
  
  // Phase 1: Logo 序列 - 震撼的停留
  useEffect(() => {
    if (phase === 1) {
      // Logo 停留后消失，进入 Phase 2
      const timer = setTimeout(() => setPhase(2), 4000)
      return () => clearTimeout(timer)
    }
  }, [phase])
  
  // Phase 2: 开场白序列 - 三句话
  useEffect(() => {
    if (phase === 2) {
      // 文字展示完后进入 Phase 3
      const timer = setTimeout(() => setPhase(3), 6000)
      return () => clearTimeout(timer)
    }
  }, [phase])
  
  // Phase 3: 角色登场序列 - 震撼登场
  useEffect(() => {
    if (phase === 3) {
      // 角色震撼出现 → 情感变化 → 显示按钮
      const greetTimer = setTimeout(() => setMascotState('greeting'), 2500)
      const happyTimer = setTimeout(() => setMascotState('happy'), 4000)
      const buttonTimer = setTimeout(() => setShowButton(true), 4500)
      
      return () => {
        clearTimeout(greetTimer)
        clearTimeout(happyTimer)
        clearTimeout(buttonTimer)
      }
    }
  }, [phase])
  
  const handleContinue = () => {
    setMascotState('happy')
    // 跳过 WelcomeScreen (id=3)，直接进入表单 (id=4)
    setTimeout(() => {
      nextStep() // 先到 id=3
      setTimeout(() => nextStep(), 50) // 再跳到 id=4
    }, 300)
  }

  // Logo 字母
  const logoLetters = ['V', 'i', 't', 'a', 'f', 'l', 'o', 'w']

  return (
    <div 
      className="h-full flex flex-col relative overflow-hidden"
      style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}
    >
      <div className="flex-1 flex flex-col items-center justify-center px-6 relative z-10">
        <AnimatePresence mode="wait">
          
          {/* ========== Phase 1: Logo 入场 - 更震撼 ========== */}
          {phase === 1 && (
            <motion.div
              key="logo"
              className="flex flex-col items-center"
              exit={{ opacity: 0, scale: 1.05 }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            >
              {/* 背景微光 */}
              <motion.div
                className="absolute w-[500px] h-[500px] rounded-full"
                style={{
                  background: `radial-gradient(circle, ${colors.accent.primary}08 0%, transparent 60%)`,
                }}
                initial={{ scale: 0.3, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 1.5, ease: 'easeOut' }}
              />
              
              <h1
                className="text-[90px] font-medium select-none flex relative z-10"
                style={{ 
                  color: colors.slate[900],
                  letterSpacing: '-1px',
                  fontFeatureSettings: '"liga" 0, "clig" 0',
                  fontKerning: 'none',
                }}
              >
                {logoLetters.map((char, index) => (
                  <motion.span
                    key={index}
                    style={{ 
                      display: 'inline-block',
                      willChange: 'filter, opacity',
                    }}
                    initial={{ 
                      opacity: 0,
                      filter: 'blur(24px)',
                      y: 10,
                    }}
                    animate={{ 
                      opacity: 1,
                      filter: 'blur(0.01px)',
                      y: 0,
                    }}
                    transition={{
                      duration: 0.7,
                      delay: 0.3 + index * 0.07,
                      ease: [0.16, 1, 0.3, 1],
                    }}
                  >
                    {char}
                  </motion.span>
                ))}
              </h1>
            </motion.div>
          )}
          
          {/* ========== Phase 2: 电影开场白 - 居中大气排版 ========== */}
          {phase === 2 && (
            <motion.div
              key="intro"
              className="flex flex-col items-center justify-center text-center gap-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            >
              {INTRO_LINES.map((line, index) => (
                <motion.p
                  key={index}
                  className="text-[48px] font-medium leading-[1.1]"
                  style={{ 
                    color: colors.slate[900],
                    letterSpacing: '-1px',
                    willChange: 'filter, opacity',
                  }}
                  initial={{ 
                    opacity: 0, 
                    y: 40,
                    filter: 'blur(20px)',
                  }}
                  animate={{ 
                    opacity: 1, 
                    y: 0,
                    filter: 'blur(0.01px)',
                  }}
                  transition={{
                    duration: 1.0,
                    delay: line.delay,
                    ease: [0.16, 1, 0.3, 1],
                  }}
                >
                  {line.text}
                </motion.p>
              ))}
            </motion.div>
          )}
          
          {/* ========== Phase 3: 角色震撼登场 - 大气有张力 ========== */}
          {phase === 3 && (
            <motion.div
              key="character"
              className="flex flex-col items-center justify-between h-full py-16"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 1.5, ease: 'easeOut' }}
            >
              {/* 上半部分 - 巨大角色 */}
              <div className="flex-1 flex items-center justify-center relative w-full">
                {/* 大范围背景光晕 */}
                <motion.div
                  className="absolute w-[600px] h-[600px] rounded-full"
                  style={{
                    background: `radial-gradient(circle, ${colors.accent.primary}06 0%, transparent 60%)`,
                  }}
                  initial={{ opacity: 0, scale: 0.3 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 2, ease: 'easeOut' }}
                />
                
                {/* 角色容器 - 震撼登场 */}
                <motion.div
                  className="relative"
                  initial={{ opacity: 0, scale: 0.3, filter: 'blur(30px)' }}
                  animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
                  transition={{ 
                    duration: 2.2,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                >
                  {/* 角色 - 超大海报感 */}
                  <motion.div 
                    className="relative z-10"
                    style={{ transform: 'scale(7)' }}
                    initial={{ y: 50, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ duration: 2.0, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
                  >
                    <Mascot 
                      style={characterStyle}
                      state={mascotState}
                      size="xl"
                    />
                  </motion.div>
                </motion.div>
              </div>
              
              {/* 下半部分 - 居中大气排版 */}
              <motion.div className="text-center px-8 mt-16">
                {/* 主标题 */}
                <motion.h2
                  className="text-[40px] font-medium leading-[1.2]"
                  style={{ 
                    color: colors.slate[900],
                    letterSpacing: '-0.5px',
                    willChange: 'filter, opacity',
                  }}
                  initial={{ opacity: 0, y: 30, filter: 'blur(14px)' }}
                  animate={{ opacity: 1, y: 0, filter: 'blur(0.01px)' }}
                  transition={{ delay: 2.5, duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
                >
                  Let me learn about you.
                </motion.h2>
                
                {/* 副标题 - 12px gap */}
                <motion.p
                  className="text-[14px] mt-4"
                  style={{ 
                    color: colors.text.secondary,
                    willChange: 'filter, opacity',
                  }}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 3.1, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                >
                  To build your personal plan.
                </motion.p>
              </motion.div>
            </motion.div>
          )}
          
        </AnimatePresence>
      </div>
      
      {/* 底部按钮 - 更平滑的出现 */}
      <div 
        className="px-5 pb-8 pt-4 relative z-10"
        style={{ background: colors.background.primary }}
      >
        <motion.div
          initial={{ opacity: 0, y: 15, filter: 'blur(8px)' }}
          animate={{ 
            opacity: showButton ? 1 : 0, 
            y: showButton ? 0 : 15,
            filter: showButton ? 'blur(0px)' : 'blur(8px)',
          }}
          transition={{ 
            duration: 0.6, 
            ease: [0.16, 1, 0.3, 1],
          }}
        >
          <Button 
            fullWidth 
            size="lg" 
            onClick={handleContinue}
            disabled={!showButton}
            style={{
              height: '52px',
              fontSize: '16px',
              letterSpacing: '-0.2px',
            }}
          >
            Next
          </Button>
        </motion.div>
      </div>
    </div>
  )
}

export default IntroductionScreen
