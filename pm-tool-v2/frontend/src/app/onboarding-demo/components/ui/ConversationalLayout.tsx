'use client'

import { ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { colors, shadows, cardBorder } from '../../lib/design-tokens'
import { ProgressBar } from './ProgressBar'
import { BackButton, SkipButton } from './Button'
import { Mascot, MascotState } from '../character'
import { useABTestStore } from '../../store/ab-test-store'
import { haptic } from '../../lib/haptics'
import { WheelPicker } from './WheelPicker'

interface ConversationalLayoutProps {
  // 进度
  currentStep: number
  totalSteps: number
  
  // 导航
  onBack?: () => void
  onSkip?: () => void
  showSkip?: boolean
  
  // 角色对话 - 这是主要内容，不是附加内容
  mascotState?: MascotState
  question: string  // 主问题，显示在气泡里
  hint?: string     // 小字提示，显示在气泡下方
  
  // 用户回复区域（选项/输入等）
  children: ReactNode
  
  // CTA
  ctaText?: string
  ctaDisabled?: boolean
  onCtaClick?: () => void
  showCta?: boolean
  
  // 样式
  className?: string
}

/**
 * 对话式布局 - 真正融合的设计
 * 
 * 核心理念：
 * - 角色是"对话发起者"，不是页面装饰
 * - 气泡包含主问题，取代传统标题
 * - 用户选项/输入是"回复"
 * - 整个体验像自然对话
 */
export function ConversationalLayout({
  currentStep,
  totalSteps,
  onBack,
  onSkip,
  showSkip = false,
  mascotState = 'idle',
  question,
  hint,
  children,
  ctaText = 'Continue',
  ctaDisabled = false,
  onCtaClick,
  showCta = true,
  className = '',
}: ConversationalLayoutProps) {
  const { characterStyle, conversationalFeedbackEnabled } = useABTestStore()
  
  return (
    <div 
      className={`h-full flex flex-col ${className}`}
      style={{ 
        background: colors.background.primary, 
        fontFamily: 'var(--font-outfit)' 
      }}
    >
      {/* 进度条 */}
      <ProgressBar current={currentStep} total={totalSteps} />
      
      {/* 头部导航 - 20px 水平，12px 垂直 */}
      <div className="flex items-center justify-between px-5 py-3">
        {onBack ? <BackButton onClick={onBack} /> : <div />}
        {showSkip && onSkip ? <SkipButton onClick={onSkip} /> : <div />}
      </div>
      
      {/* 对话区域 - 角色 + 问题气泡 */}
      {/* 紧凑布局，让内容更靠上 */}
      <motion.div 
        className="px-5 pt-3 pb-3 flex-shrink-0"
        style={{ height: '148px' }}  
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex items-start gap-4">
          {/* 角色 - lg = 96px */}
          <motion.div
            className="flex-shrink-0"
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ 
              type: 'spring', 
              stiffness: 300, 
              damping: 20,
              delay: 0.1 
            }}
          >
            <Mascot 
              style={characterStyle} 
              state={mascotState} 
              size="lg" 
            />
          </motion.div>
          
          {/* 问题气泡 - 16px padding, 12px 圆角 */}
          {/* 用 key 控制动画：只在问题内容变化时重新动画 */}
          <motion.div 
            key={question}
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
                  lineHeight: '28px',  // 固定行高 = 字号 + 8px
                }}
              >
                {question}
              </p>
              {hint && (
                <p 
                  className="text-[14px] mt-3"
                  style={{ 
                    color: colors.text.secondary, 
                    letterSpacing: '-0.4px',
                    lineHeight: '20px',  // 固定行高
                  }}
                >
                  {hint}
                </p>
              )}
            </div>
          </motion.div>
        </div>
      </motion.div>
      
      {/* 用户回复区域 - flex 容器，让子组件可自行控制位置 */}
      {/* pt-6 (24px) 给气泡留出更多空间，避免与选项重叠 */}
      <motion.div 
        className="flex-1 px-5 pt-6 pb-4 flex flex-col overflow-y-auto scrollbar-hide"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.25 }}
      >
        {children}
      </motion.div>
      
      {/* 固定底部 CTA - 20px padding, 32px 底部安全区 */}
      {showCta && onCtaClick && (
        <motion.div
          className="px-5 pb-8 pt-4"
          style={{ background: colors.background.primary }}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <motion.button 
            className="w-full py-4 rounded-xl text-[18px] font-medium"
            style={{
              background: ctaDisabled ? colors.slate[200] : colors.slate[900],
              color: ctaDisabled ? colors.slate[400] : colors.white,
              cursor: ctaDisabled ? 'not-allowed' : 'pointer',
              boxShadow: ctaDisabled ? 'none' : '0 2px 4px rgba(15, 23, 42, 0.15)',
              letterSpacing: '-0.4px',
              lineHeight: '24px',  // 固定行高
            }}
            onClick={ctaDisabled ? undefined : () => {
              haptic('medium')
              onCtaClick()
            }}
            whileHover={ctaDisabled ? {} : { scale: 1.01 }}
            whileTap={ctaDisabled ? {} : { scale: 0.98 }}
          >
            {ctaText}
          </motion.button>
        </motion.div>
      )}
    </div>
  )
}

/**
 * 对话式选项卡 - 像是用户的回复
 */
interface ConversationalOptionProps {
  label: string
  description?: string
  selected?: boolean
  onClick: () => void
  index?: number
  emoji?: string
}

export function ConversationalOption({ 
  label, 
  description, 
  selected = false, 
  onClick, 
  index = 0,
  emoji,
}: ConversationalOptionProps) {
  const handleClick = () => {
    haptic('selection')
    onClick()
  }
  
  return (
    <motion.button
      className="w-full text-left px-5 py-5 rounded-[12px] mb-4 last:mb-0 transition-all"
      style={{
        background: selected ? colors.slate[900] : colors.white,
        border: selected ? 'none' : cardBorder.default,
        boxShadow: selected 
          ? shadows.cardSelected
          : shadows.card,
      }}
      onClick={handleClick}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ 
        duration: 0.25, 
        delay: 0.15 + index * 0.04,
        ease: [0.25, 0.1, 0.25, 1]
      }}
      whileHover={{ 
        y: -2,
        boxShadow: shadows.cardHover,
      }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex items-center gap-4">
        {emoji && (
          <span className="text-2xl">{emoji}</span>
        )}
        <div className="flex-1">
          <span 
            className="text-[18px] font-medium"
            style={{ 
              color: selected ? colors.white : colors.text.primary,
              letterSpacing: '-0.4px',
              lineHeight: '24px',  // 固定行高
            }}
          >
            {label}
          </span>
          {description && (
            <span 
              className="block text-[14px] mt-3"
              style={{ 
                color: selected ? 'rgba(255,255,255,0.75)' : colors.text.secondary,
                letterSpacing: '-0.4px',
                lineHeight: '20px',  // 固定行高
              }}
            >
              {description}
            </span>
          )}
        </div>
        
        {/* 选中指示 - 24px */}
        <motion.div
          className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
          style={{
            background: selected ? colors.accent.primary : 'transparent',
            border: selected ? 'none' : `2px solid ${colors.slate[300]}`,
          }}
          animate={{ scale: selected ? 1 : 1 }}
        >
          {selected && (
            <motion.svg 
              width="12" 
              height="12" 
              viewBox="0 0 12 12"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 500, damping: 25 }}
            >
              <path 
                d="M2.5 6L5 8.5L9.5 4" 
                stroke={colors.slate[900]}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </motion.svg>
          )}
        </motion.div>
      </div>
    </motion.button>
  )
}

/**
 * 对话式输入框 - 像是用户在打字回复
 */
interface ConversationalInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  maxLength?: number
  onKeyDown?: (e: React.KeyboardEvent) => void
  inputRef?: React.RefObject<HTMLInputElement>
  autoFocus?: boolean
}

export function ConversationalInput({
  value,
  onChange,
  placeholder = 'Type your answer...',
  maxLength = 50,
  onKeyDown,
  inputRef,
  autoFocus = true,
}: ConversationalInputProps) {
  return (
    <motion.div
      className="relative"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.2 }}
    >
      <div 
        className="rounded-[12px] overflow-hidden"
        style={{
          background: colors.white,
          border: cardBorder.default,
          boxShadow: shadows.card,
        }}
      >
        <input
          ref={inputRef as React.RefObject<HTMLInputElement>}
          type="text"
          value={value}
          onChange={(e) => {
            haptic('light')
            onChange(e.target.value)
          }}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          maxLength={maxLength}
          autoFocus={autoFocus}
          className="w-full px-5 py-5 text-[18px] font-medium outline-none bg-transparent"
          style={{ color: colors.text.primary, letterSpacing: '-0.4px', lineHeight: '24px' }}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
        />
      </div>
      
      {/* 字数指示 - 只在接近上限时显示 */}
      {value.length > maxLength * 0.7 && (
        <motion.p
          className="absolute right-4 -bottom-6 text-[11px]"
          style={{ 
            color: value.length >= maxLength 
              ? colors.semantic.warning 
              : colors.text.tertiary 
          }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {value.length}/{maxLength}
        </motion.p>
      )}
    </motion.div>
  )
}

/**
 * 对话式数字选择
 */
interface ConversationalNumberProps {
  value: number
  onChange: (value: number) => void
  min: number
  max: number
  step?: number
  unit: string
  label?: string
}

export function ConversationalNumber({
  value,
  onChange,
  min,
  max,
  step = 1,
  unit,
  label,
}: ConversationalNumberProps) {
  return (
    <motion.div
      className="rounded-[12px] p-5 my-auto"
      style={{
        background: colors.white,
        border: cardBorder.default,
        boxShadow: shadows.card,
      }}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.15 }}
    >
      {/* 使用滚轮选择器 */}
      <WheelPicker
        value={value}
        onChange={onChange}
        min={min}
        max={max}
        step={step}
        unit={unit}
        label={label}
        orientation="horizontal"
      />
    </motion.div>
  )
}
