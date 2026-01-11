'use client'

import { motion } from 'framer-motion'
import { useOnboardingStore } from '../../store/onboarding-store'
import { ScreenConfig } from '../../data/screens-config'
import { Button, BackButton } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { colors } from '../../lib/design-tokens'
import { haptic } from '../../lib/haptics'
import { User } from 'lucide-react'

interface AccountScreenProps {
  config: ScreenConfig
}

export function AccountScreen({ config }: AccountScreenProps) {
  const { nextStep, prevStep, currentStep, totalSteps } = useOnboardingStore()
  
  const handleAppleSignIn = () => {
    haptic('medium')
    nextStep()
  }
  
  const handleGoogleSignIn = () => {
    haptic('medium')
    nextStep()
  }
  
  const handleEmailSignUp = () => {
    haptic('light')
    nextStep()
  }
  
  return (
    <div 
      className="h-full flex flex-col"
      style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}
    >
      <ProgressBar current={currentStep} total={totalSteps} />
      
      <div className="flex items-center justify-between px-5 py-2">
        <BackButton onClick={prevStep} />
        <div />
      </div>
      
      {/* 主要内容 */}
      <div className="flex-1 px-5 pt-4 overflow-y-auto scrollbar-hide pb-4">
        {/* 图标 + 标题卡片 */}
        <motion.div
          className="p-6 rounded-[16px] text-center mb-6"
          style={{ background: '#FFFFFF', boxShadow: '0px 1px 3px rgba(15, 23, 42, 0.08)' }}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          {/* 图标 */}
          <motion.div
            className="w-16 h-16 rounded-[16px] flex items-center justify-center mx-auto mb-5"
            style={{ background: colors.slate[100] }}
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.2 }}
          >
            <User className="w-8 h-8" style={{ color: colors.slate[700] }} strokeWidth={1.5} />
          </motion.div>
          
          {/* 标题 */}
          <motion.h1
            className="text-[28px] font-medium tracking-[-0.4px]"
            style={{ color: colors.text.primary }}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            {config.title}
          </motion.h1>
          
          {/* 副标题 */}
          <motion.p
            className="mt-2 text-[15px]"
            style={{ color: colors.text.secondary }}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
          >
            {config.subtitle}
          </motion.p>
        </motion.div>
        
        {/* 登录按钮 */}
        <motion.div
          className="space-y-3"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          {/* Apple 登录 */}
          <motion.button
            onClick={handleAppleSignIn}
            className="w-full h-14 rounded-[16px] font-medium flex items-center justify-center gap-3"
            style={{ 
              background: colors.slate[900], 
              color: '#FFFFFF',
              boxShadow: '0px 1px 3px rgba(15, 23, 42, 0.08)'
            }}
            whileTap={{ scale: 0.98 }}
          >
            <svg width="18" height="22" viewBox="0 0 20 24" fill="currentColor">
              <path d="M19.665 17.811c-.456 1.004-.673 1.453-1.258 2.347-.817 1.249-1.97 2.804-3.4 2.817-1.27.013-1.598-.826-3.323-.814-1.725.01-2.086.83-3.358.816-1.428-.014-2.52-1.418-3.34-2.667C2.63 16.638 2.417 12.15 4.29 9.774c1.322-1.677 3.32-2.66 5.176-2.66 1.623 0 2.64.83 3.98.83 1.302 0 2.097-.832 3.974-.832 1.65 0 3.417.883 4.735 2.41-4.16 2.282-3.488 8.223.51 10.289zM14.25 4.56c.635-.816 1.118-1.97.995-3.14-1.08.074-2.343.758-3.08 1.647-.67.807-1.223 1.974-1.007 3.12 1.18.038 2.4-.662 3.092-1.627z" />
            </svg>
            <span className="text-[15px]">Continue with Apple</span>
          </motion.button>
          
          {/* Google 登录 */}
          <motion.button
            onClick={handleGoogleSignIn}
            className="w-full h-14 rounded-[16px] font-medium flex items-center justify-center gap-3"
            style={{ 
              background: '#FFFFFF', 
              color: colors.text.primary,
              border: `1px solid ${colors.border.light}`,
              boxShadow: '0px 1px 3px rgba(15, 23, 42, 0.08)'
            }}
            whileTap={{ scale: 0.98 }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            <span className="text-[15px]">Continue with Google</span>
          </motion.button>
        </motion.div>
        
        {/* 分隔线 */}
        <motion.div
          className="flex items-center gap-4 my-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          <div className="flex-1 h-px" style={{ background: colors.border.light }} />
          <span className="text-[13px]" style={{ color: colors.text.tertiary }}>or</span>
          <div className="flex-1 h-px" style={{ background: colors.border.light }} />
        </motion.div>
        
        {/* 邮箱注册提示 */}
        <motion.button
          className="w-full text-center font-medium text-[14px]"
          style={{ color: colors.slate[600] }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          onClick={handleEmailSignUp}
          whileTap={{ scale: 0.95 }}
        >
          Sign up with email instead
        </motion.button>
      </div>
      
      {/* 底部条款 */}
      <motion.div
        className="px-5 py-6"
        style={{ background: colors.background.primary }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.7 }}
      >
        <p className="text-[12px] text-center leading-relaxed" style={{ color: colors.text.tertiary }}>
          By continuing, you agree to our{' '}
          <span style={{ color: colors.text.secondary }}>Terms of Service</span> and{' '}
          <span style={{ color: colors.text.secondary }}>Privacy Policy</span>
        </p>
      </motion.div>
    </div>
  )
}
