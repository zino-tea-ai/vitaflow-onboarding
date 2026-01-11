'use client'

import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useOnboardingStore, UserData } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { ScreenConfigProduction } from '../../data/screens-config-production'
import { Button, BackButton } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { Mascot, MascotState } from '../character'
import { ChatBubble } from '../ui/ChatBubble'
import { colors, shadows, cardBorder } from '../../lib/design-tokens'
import { Bell } from 'lucide-react'
import { getPageTitle } from '../../data/feedback-copy'

interface PermissionScreenProps {
  config: ScreenConfig | ScreenConfigProduction
}

export function PermissionScreen({ config }: PermissionScreenProps) {
  const { setUserData, nextStep, prevStep, currentStep, totalSteps } = useOnboardingStore()
  const { characterStyle, copyStyle, conversationalFeedbackEnabled } = useABTestStore()
  
  // 弹窗显示状态
  const [showDialog, setShowDialog] = useState(false)
  
  const productionConfig = config as ScreenConfigProduction
  const permissionType = productionConfig.permissionType
  const storeKey = (Array.isArray(config.storeKey) ? config.storeKey[0] : config.storeKey) as keyof UserData | undefined
  
  const mascotState: MascotState = productionConfig.characterState || 'encouraging'
  
  const bubbleText = useMemo(() => {
    if (!conversationalFeedbackEnabled) return "I'll remind you to log meals so it becomes a long-term habit."
    const key = productionConfig.characterFeedbackKey || 'permission_notification'
    return getPageTitle(key, copyStyle) || "I'll remind you to log meals so it becomes a long-term habit."
  }, [copyStyle, conversationalFeedbackEnabled, productionConfig.characterFeedbackKey])
  
  const handleAllow = () => {
    if (storeKey) setUserData(storeKey, true as never)
    nextStep()
  }
  
  const handleSkip = () => {
    if (storeKey) setUserData(storeKey, false as never)
    nextStep()
  }
  
  const handleCTAClick = () => {
    setShowDialog(true)
  }
  
  // Notification 权限页 - 角色 + 气泡 + CTA + 弹窗
  if (permissionType === 'notification') {
    return (
      <div 
        className="h-full flex flex-col relative"
        style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}
      >
        <ProgressBar current={currentStep} total={totalSteps} />
        
        <div className="flex items-center justify-between px-5 py-2">
          <BackButton onClick={prevStep} />
          <div />
        </div>
        
        {/* 角色 + 气泡区域 - 与 ConversationalLayout 一致 */}
        <motion.div 
          className="px-5 pt-3 pb-3 flex items-start gap-4"
          style={{ height: '148px' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4 }}
        >
          {/* 角色 - lg = 96px */}
          <motion.div
            className="flex-shrink-0"
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.1 }}
          >
            <Mascot style={characterStyle} state={mascotState} size="lg" />
          </motion.div>
          
          {/* 气泡 */}
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
                border: cardBorder.default,
                boxShadow: shadows.card,
              }}
            >
              <p 
                className="text-[20px] font-medium"
                style={{ 
                  color: colors.text.primary,
                  letterSpacing: '-0.4px',
                  lineHeight: '28px',
                }}
              >
                {bubbleText}
              </p>
            </div>
          </motion.div>
        </motion.div>
        
        {/* 中心区域 - 权限说明 */}
        <div className="flex-1 flex flex-col items-center justify-center px-5">
          <motion.div
            className="text-center"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            {/* 图标 */}
            <motion.div 
              className="w-20 h-20 rounded-[20px] mx-auto mb-6 flex items-center justify-center"
              style={{ background: colors.slate[100] }}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.4, type: 'spring', stiffness: 200 }}
            >
              <Bell size={40} style={{ color: colors.slate[900] }} />
            </motion.div>
            
            {/* 标题 */}
            <h2 
              className="text-[24px] font-medium mb-3"
              style={{ color: colors.text.primary, letterSpacing: '-0.4px' }}
            >
              Stay on Track
            </h2>
            
            {/* 描述 */}
            <p 
              className="text-[15px] leading-[1.6] max-w-[280px] mx-auto"
              style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}
            >
              Get gentle reminders to log meals and celebrate your progress milestones.
            </p>
          </motion.div>
        </div>
        
        {/* 底部 CTA */}
        <motion.div 
          className="px-5 pb-8 pt-4"
          style={{ background: colors.background.primary }}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <motion.button 
            className="w-full py-4 rounded-xl text-[18px] font-medium"
            style={{
              background: colors.slate[900],
              color: colors.white,
              boxShadow: '0 2px 4px rgba(15, 23, 42, 0.15)',
              letterSpacing: '-0.4px',
              lineHeight: '24px',
            }}
            onClick={handleCTAClick}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
          >
            Continue
          </motion.button>
          
          {/* Skip 链接 */}
          <button 
            className="w-full py-3 text-[15px] font-medium"
            style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}
            onClick={handleSkip}
          >
            Maybe Later
          </button>
        </motion.div>
        
        {/* 弹窗遮罩 + 弹窗 */}
        <AnimatePresence>
          {showDialog && (
            <>
              {/* 遮罩 */}
              <motion.div
                className="absolute inset-0 z-40"
                style={{ background: 'rgba(0, 0, 0, 0.4)' }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setShowDialog(false)}
              />
              
              {/* 弹窗 */}
              <motion.div
                className="absolute inset-0 z-50 flex items-center justify-center px-5"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div className="relative w-full">
                  {/* 弹窗本体 - 苹果结构 + VitaFlow 风格 */}
                  <motion.div
                    className="w-full rounded-[12px]"
                    style={{ 
                      background: colors.white,
                      boxShadow: shadows.lg,
                    }}
                    initial={{ scale: 0.9, y: 20 }}
                    animate={{ scale: 1, y: 0 }}
                    exit={{ scale: 0.9, y: 20 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                  >
                    {/* 内容区 */}
                    <div className="px-5 pt-6 pb-5 text-center">
                      <p 
                        className="text-[18px] font-medium mb-3" 
                        style={{ color: colors.text.primary, letterSpacing: '-0.4px', lineHeight: '24px' }}
                      >
                        "VitaFlow" Would Like to Send You Notifications
                      </p>
                      <p 
                        className="text-[14px] leading-[1.5]" 
                        style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}
                      >
                        Notifications may include alerts, sounds, and icon badges. These can be configured in Settings.
                      </p>
                    </div>
                    
                    {/* 分隔线 */}
                    <div className="h-px" style={{ background: colors.border.light }} />
                    
                    {/* 按钮区 - 苹果风格并排 */}
                    <div className="flex">
                      <button 
                        className="flex-1 py-4 text-[17px] font-medium transition-colors active:bg-slate-50 rounded-bl-[12px]"
                        style={{ 
                          color: colors.text.secondary,
                          borderRight: `1px solid ${colors.border.light}`,
                          letterSpacing: '-0.4px',
                        }}
                        onClick={handleSkip}
                      >
                        Don't Allow
                      </button>
                      <button 
                        className="flex-1 py-4 text-[17px] font-medium transition-colors active:bg-slate-50 rounded-br-[12px]"
                        style={{ 
                          color: colors.accent.primary,
                          letterSpacing: '-0.4px',
                        }}
                        onClick={handleAllow}
                      >
                        Allow
                      </button>
                    </div>
                  </motion.div>
                  
                  {/* 指引箭头 - 放在弹窗外部，精确对齐 Allow 按钮 */}
                  <motion.div
                    className="mt-4 flex flex-col items-center"
                    style={{ marginLeft: '50%' }}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                  >
                    <motion.svg 
                      width="32" 
                      height="40" 
                      viewBox="0 0 32 40"
                      animate={{ y: [0, -6, 0] }}
                      transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
                    >
                      {/* 箭头朝上 */}
                      <path 
                        d="M16 36 L16 8 M8 16 L16 6 L24 16" 
                        stroke={colors.accent.primary}
                        strokeWidth="3" 
                        fill="none"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </motion.svg>
                    
                    {/* 提示文字 */}
                    <p 
                      className="text-[14px] font-medium text-center mt-1 whitespace-nowrap"
                      style={{ color: colors.accent.primary, letterSpacing: '-0.4px' }}
                    >
                      Tap here
                    </p>
                  </motion.div>
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>
    )
  }
  
  // 默认权限页
  return (
    <div className="h-full flex flex-col" style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}>
      <ProgressBar current={currentStep} total={totalSteps} />
      
      <div className="flex items-center justify-between px-5 py-2">
        <BackButton onClick={prevStep} />
        <div />
      </div>
      
      <div className="flex-1 flex flex-col items-center justify-center px-8">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 300, damping: 20 }}
        >
          <Mascot style={characterStyle} state={mascotState} size="lg" />
        </motion.div>
        
        <h1 className="text-[26px] font-semibold text-center mt-6 mb-3" style={{ color: colors.text.primary }}>{config.title}</h1>
        <p className="text-[15px] text-center max-w-[280px]" style={{ color: colors.text.secondary }}>{config.subtitle}</p>
      </div>
      
      <motion.div className="px-5 py-6 space-y-3" style={{ background: colors.background.primary }}>
        <Button fullWidth size="lg" onClick={handleAllow}>Allow</Button>
        <Button fullWidth size="lg" variant="ghost" onClick={handleSkip}>Skip</Button>
      </motion.div>
    </div>
  )
}
