'use client'

import React, { ReactNode } from 'react'
import { motion, HTMLMotionProps } from 'framer-motion'
import { haptic, enableAudioHaptics } from '../../lib/haptics'

interface ButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  children: ReactNode
  variant?: 'primary' | 'secondary' | 'ghost' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  fullWidth?: boolean
  loading?: boolean
  icon?: ReactNode
  iconPosition?: 'left' | 'right'
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  loading = false,
  icon,
  iconPosition = 'left',
  className = '',
  disabled,
  onClick,
  ...props
}: ButtonProps) {
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    // 首次点击时启用音频系统（iOS 需要用户交互才能播放音频）
    enableAudioHaptics()
    if (!disabled && !loading) {
      haptic('medium')
    }
    onClick?.(e)
  }
  // VitaFlow 设计系统 - Slate 配色
  const baseStyles = `
    relative inline-flex items-center justify-center gap-2
    transition-all duration-200 overflow-hidden
    disabled:opacity-50 disabled:cursor-not-allowed
  `
  
  // VitaFlow 风格按钮变体 - 使用 Slate-900 + Pill 样式
  const variants = {
    primary: `
      bg-[#0F172A] text-white font-medium rounded-full
      shadow-[0px_1px_3px_rgba(15,23,42,0.1)]
      hover:bg-[#1E293B]
      active:bg-[#334155]
    `,
    secondary: `
      bg-white text-[#0F172A] font-medium rounded-full
      shadow-[0px_1px_3px_rgba(15,23,42,0.08)]
      hover:bg-[#F8FAFC]
    `,
    ghost: `
      bg-transparent text-[#64748B] font-medium rounded-full
      hover:bg-[#F1F5F9]
    `,
    outline: `
      bg-transparent border-2 border-[#CBD5E1] text-[#0F172A] font-medium rounded-full
      hover:border-[#0F172A]
    `
  }
  
  const sizes = {
    sm: 'px-4 py-2 text-sm',
    md: 'px-6 py-4 text-base',
    lg: 'px-8 py-4 text-[17px]'
  }
  
  return (
    <motion.button
      className={`
        ${baseStyles}
        ${variants[variant]}
        ${sizes[size]}
        ${fullWidth ? 'w-full' : ''}
        ${className}
      `}
      style={{ fontFamily: 'var(--font-outfit)' }}
      whileHover={{ 
        scale: disabled ? 1 : 1.02,
        transition: { duration: 0.2 }
      }}
      whileTap={{ 
        scale: disabled ? 1 : 0.96,
        transition: { duration: 0.1 }
      }}
      disabled={disabled || loading}
      onClick={handleClick}
      {...props}
    >
      {/* 内容 */}
      <span className="relative flex items-center gap-2">
        {loading ? (
          <motion.svg
            className="w-5 h-5"
            viewBox="0 0 24 24"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          >
            <circle
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="3"
              fill="none"
              strokeDasharray="30 60"
              strokeLinecap="round"
            />
          </motion.svg>
        ) : (
          <>
            {icon && iconPosition === 'left' && icon}
            {children}
            {icon && iconPosition === 'right' && icon}
          </>
        )}
      </span>
    </motion.button>
  )
}

// VitaFlow 返回按钮 - 长按回到开头
export function BackButton({ onClick }: { onClick: () => void }) {
  const longPressRef = React.useRef<NodeJS.Timeout | null>(null)
  const [isLongPressing, setIsLongPressing] = React.useState(false)
  
  const handleClick = () => {
    if (isLongPressing) return // 长按后不触发普通点击
    enableAudioHaptics()
    haptic('light')
    onClick()
  }
  
  const handlePressStart = () => {
    longPressRef.current = setTimeout(() => {
      setIsLongPressing(true)
      haptic('success')
      // 动态导入 store 并重置
      import('../../store/onboarding-store').then(({ useOnboardingStore }) => {
        useOnboardingStore.getState().resetDemo()
      })
    }, 800) // 长按 800ms 触发
  }
  
  const handlePressEnd = () => {
    if (longPressRef.current) {
      clearTimeout(longPressRef.current)
      longPressRef.current = null
    }
    setTimeout(() => setIsLongPressing(false), 100)
  }
  
  return (
    <motion.button
      onClick={handleClick}
      onMouseDown={handlePressStart}
      onMouseUp={handlePressEnd}
      onMouseLeave={handlePressEnd}
      onTouchStart={handlePressStart}
      onTouchEnd={handlePressEnd}
      className="w-10 h-10 rounded-full bg-white flex items-center justify-center shadow-[0px_1px_3px_rgba(15,23,42,0.08)]"
      style={{ color: '#0F172A' }}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
    >
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path
          d="M12.5 15L7.5 10L12.5 5"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </motion.button>
  )
}

// VitaFlow 跳过按钮
export function SkipButton({ onClick }: { onClick: () => void }) {
  const handleClick = () => {
    enableAudioHaptics()
    haptic('light')
    onClick()
  }
  
  return (
    <motion.button
      onClick={handleClick}
      className="text-sm font-medium transition-colors"
      style={{ color: '#64748B', fontFamily: 'var(--font-outfit)' }}
      whileHover={{ x: 3, color: '#0F172A' }}
      whileTap={{ scale: 0.95 }}
    >
      Skip
    </motion.button>
  )
}
