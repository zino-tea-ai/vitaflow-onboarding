'use client'

import { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { colors, bigTextStyles } from '../../lib/design-tokens'
import { ProgressBar } from './ProgressBar'
import { BackButton, SkipButton } from './Button'
import { Mascot, MascotState } from '../character'
import { ChatBubble } from './ChatBubble'
import { useABTestStore } from '../../store/ab-test-store'

interface BigTextLayoutProps {
  // 进度
  currentStep: number
  totalSteps: number
  
  // 导航
  onBack?: () => void
  onSkip?: () => void
  showSkip?: boolean
  
  // 内容
  title?: string
  subtitle?: string
  children: ReactNode
  
  // 角色气泡
  mascotState?: MascotState
  bubbleText?: string
  showMascot?: boolean
  
  // CTA
  ctaText?: string
  ctaDisabled?: boolean
  onCtaClick?: () => void
  
  // 样式
  className?: string
  darkMode?: boolean
}

/**
 * BigText 统一布局组件
 * 大字体 + 角色气泡融入 + CTA 固定底部
 */
export function BigTextLayout({
  currentStep,
  totalSteps,
  onBack,
  onSkip,
  showSkip = false,
  title,
  subtitle,
  children,
  mascotState = 'idle',
  bubbleText,
  showMascot = true,
  ctaText = 'Continue',
  ctaDisabled = false,
  onCtaClick,
  className = '',
  darkMode = false,
}: BigTextLayoutProps) {
  const { characterStyle, conversationalFeedbackEnabled } = useABTestStore()
  
  // 是否显示角色区域
  const shouldShowMascot = showMascot && conversationalFeedbackEnabled
  
  const bgColor = darkMode ? colors.background.dark : colors.background.primary
  const textColor = darkMode ? colors.text.inverse : colors.text.primary
  const subtitleColor = darkMode ? 'rgba(255,255,255,0.7)' : colors.text.secondary
  
  return (
    <div 
      className={`h-full flex flex-col ${className}`}
      style={{ 
        background: bgColor, 
        fontFamily: 'var(--font-outfit)' 
      }}
    >
      {/* 进度条 */}
      <ProgressBar current={currentStep} total={totalSteps} />
      
      {/* 头部导航 */}
      <div className="flex items-center justify-between px-5 py-2">
        {onBack ? <BackButton onClick={onBack} /> : <div />}
        {showSkip && onSkip ? <SkipButton onClick={onSkip} /> : <div />}
      </div>
      
      {/* 标题 + 角色区域 */}
      <div className="px-6 pt-4">
        {/* 角色 + 气泡 - 小巧版本放在标题上方 */}
        {shouldShowMascot && (
          <motion.div 
            className="flex items-start gap-3 mb-4"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <Mascot 
              style={characterStyle} 
              state={mascotState} 
              size="sm" 
            />
            {bubbleText && (
              <div className="flex-1">
                <ChatBubble 
                  text={bubbleText}
                  visible={true}
                  position="bottom-right"
                  size="sm"
                />
              </div>
            )}
          </motion.div>
        )}
        
        {/* 大标题 */}
        {title && (
          <motion.h1
            style={{
              ...bigTextStyles.title,
              color: textColor,
            }}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: shouldShowMascot ? 0.1 : 0 }}
          >
            {title}
          </motion.h1>
        )}
        
        {/* 副标题 */}
        {subtitle && (
          <motion.p
            className="mt-3"
            style={{
              ...bigTextStyles.subtitle,
              color: subtitleColor,
            }}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: shouldShowMascot ? 0.15 : 0.1 }}
          >
            {subtitle}
          </motion.p>
        )}
      </div>
      
      {/* 内容区域 */}
      <div className="flex-1 px-6 pt-6 overflow-y-auto scrollbar-hide">
        {children}
      </div>
      
      {/* 固定底部 CTA */}
      {onCtaClick && (
        <motion.div
          className="px-6 pb-8 pt-4"
          style={{ background: bgColor }}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <motion.button 
            className="w-full"
            style={{
              ...bigTextStyles.cta,
              background: ctaDisabled 
                ? (darkMode ? 'rgba(255,255,255,0.2)' : colors.slate[300])
                : (darkMode ? colors.white : colors.slate[900]),
              color: ctaDisabled 
                ? (darkMode ? 'rgba(255,255,255,0.5)' : colors.slate[500])
                : (darkMode ? colors.slate[900] : colors.white),
              cursor: ctaDisabled ? 'not-allowed' : 'pointer',
            }}
            onClick={ctaDisabled ? undefined : onCtaClick}
            whileHover={ctaDisabled ? {} : { scale: 1.01 }}
            whileTap={ctaDisabled ? {} : { scale: 0.99 }}
          >
            {ctaText}
          </motion.button>
        </motion.div>
      )}
    </div>
  )
}

/**
 * BigText 选项按钮
 */
interface BigTextOptionProps {
  label: string
  description?: string
  selected?: boolean
  onClick: () => void
  index?: number
  icon?: string
}

export function BigTextOption({ 
  label, 
  description, 
  selected = false, 
  onClick, 
  index = 0,
  icon,
}: BigTextOptionProps) {
  return (
    <motion.button
      className="w-full text-left p-5 rounded-2xl transition-all"
      style={{
        background: selected ? colors.slate[900] : colors.white,
        border: `2px solid ${selected ? colors.slate[900] : colors.border.light}`,
        boxShadow: selected ? colors.shadows.cardSelected : colors.shadows.card,
      }}
      onClick={onClick}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex items-center gap-3">
        {icon && (
          <span className="text-2xl">{icon}</span>
        )}
        <div className="flex-1">
          <span 
            style={{
              ...bigTextStyles.option,
              color: selected ? colors.white : colors.text.primary,
            }}
          >
            {label}
          </span>
          {description && (
            <span 
              className="block mt-1"
              style={{
                ...bigTextStyles.optionDescription,
                color: selected ? 'rgba(255,255,255,0.7)' : colors.text.secondary,
              }}
            >
              {description}
            </span>
          )}
        </div>
      </div>
    </motion.button>
  )
}

/**
 * BigText 数字输入
 */
interface BigTextNumberInputProps {
  value: number
  onChange: (value: number) => void
  min: number
  max: number
  step?: number
  unit: string
}

export function BigTextNumberInput({
  value,
  onChange,
  min,
  max,
  step = 1,
  unit,
}: BigTextNumberInputProps) {
  return (
    <motion.div
      className="flex items-center justify-center gap-6"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
    >
      {/* 减少按钮 */}
      <motion.button
        className="w-14 h-14 rounded-full flex items-center justify-center text-2xl font-bold"
        style={{
          background: colors.slate[100],
          color: colors.slate[700],
        }}
        onClick={() => onChange(Math.max(min, value - step))}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        −
      </motion.button>
      
      {/* 数字显示 */}
      <motion.div
        className="text-center min-w-[140px]"
        key={value}
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.15 }}
      >
        <span style={bigTextStyles.numberDisplay}>
          {value}
        </span>
        <p 
          className="mt-1"
          style={{ 
            fontSize: '18px', 
            color: colors.text.secondary,
            fontWeight: '500',
          }}
        >
          {unit}
        </p>
      </motion.div>
      
      {/* 增加按钮 */}
      <motion.button
        className="w-14 h-14 rounded-full flex items-center justify-center text-2xl font-bold"
        style={{
          background: colors.slate[100],
          color: colors.slate[700],
        }}
        onClick={() => onChange(Math.min(max, value + step))}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        +
      </motion.button>
    </motion.div>
  )
}

/**
 * BigText 文本输入
 */
interface BigTextTextInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  maxLength?: number
  onKeyDown?: (e: React.KeyboardEvent) => void
  inputRef?: React.RefObject<HTMLInputElement>
}

export function BigTextTextInput({
  value,
  onChange,
  placeholder = 'Enter text...',
  maxLength = 50,
  onKeyDown,
  inputRef,
}: BigTextTextInputProps) {
  return (
    <motion.div
      className="relative rounded-2xl transition-all duration-300"
      style={{
        background: colors.white,
        border: `2px solid ${colors.border.light}`,
        boxShadow: colors.shadows.card,
      }}
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ delay: 0.2 }}
      whileFocus={{
        borderColor: colors.slate[900],
        boxShadow: colors.shadows.cardSelected,
      }}
    >
      <input
        ref={inputRef as React.RefObject<HTMLInputElement>}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        maxLength={maxLength}
        className="w-full px-5 py-5 rounded-2xl outline-none bg-transparent"
        style={{ 
          ...bigTextStyles.input,
          color: colors.text.primary,
        }}
        autoComplete="off"
        autoCorrect="off"
        spellCheck={false}
      />
    </motion.div>
  )
}
