'use client'

import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { appleTheme, sharedStyles } from './tokens'

// Apple Style 布局 - 高端渐变 + 玻璃态
// 参考 Apple 的设计语言

interface AppleLayoutProps {
  children: React.ReactNode
  // 角色区域
  characterSlot?: React.ReactNode
  // 标题
  title?: string
  // 副标题
  subtitle?: string
  className?: string
}

export function AppleLayout({
  children,
  characterSlot,
  title,
  subtitle,
  className = '',
}: AppleLayoutProps) {
  const theme = appleTheme
  const styles = sharedStyles

  return (
    <motion.div
      className={`relative h-full w-full flex flex-col overflow-hidden ${className}`}
      style={{
        background: theme.background.primary,
        fontFamily: styles.typography.fontFamily,
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* 背景装饰 - 微妙的光斑 */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <motion.div
          className="absolute rounded-full"
          style={{
            width: 300,
            height: 300,
            top: '-10%',
            right: '-20%',
            background: 'radial-gradient(circle, rgba(0, 113, 227, 0.08) 0%, transparent 70%)',
            filter: 'blur(40px)',
          }}
          animate={{
            scale: [1, 1.1, 1],
            opacity: [0.5, 0.7, 0.5],
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
        <motion.div
          className="absolute rounded-full"
          style={{
            width: 250,
            height: 250,
            bottom: '10%',
            left: '-15%',
            background: 'radial-gradient(circle, rgba(52, 199, 89, 0.06) 0%, transparent 70%)',
            filter: 'blur(40px)',
          }}
          animate={{
            scale: [1, 1.15, 1],
            opacity: [0.4, 0.6, 0.4],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: 2,
          }}
        />
      </div>

      {/* 上半部分 - 角色 + 标题 */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 pt-12 relative z-10">
        {/* 角色区域 */}
        {characterSlot && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, ease: [0.34, 1.56, 0.64, 1] }}
          >
            {characterSlot}
          </motion.div>
        )}

        {/* 标题 */}
        <AnimatePresence mode="wait">
          {title && (
            <motion.h1
              key={title}
              className="text-center mt-6"
              style={{
                ...styles.typography.title,
                color: theme.text.primary,
              }}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.4, delay: 0.15 }}
            >
              {title}
            </motion.h1>
          )}
        </AnimatePresence>

        {/* 副标题 */}
        <AnimatePresence mode="wait">
          {subtitle && (
            <motion.p
              key={subtitle}
              className="text-center mt-3 max-w-[260px]"
              style={{
                ...styles.typography.subtitle,
                color: theme.text.secondary,
              }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3, delay: 0.25 }}
            >
              {subtitle}
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* 下半部分 - 交互区域 */}
      <motion.div
        className="px-6 pb-8 relative z-10"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.3 }}
      >
        {children}
      </motion.div>
    </motion.div>
  )
}

// Apple 风格的选项卡片 - 玻璃态
interface AppleOptionProps {
  label: string
  description?: string
  selected?: boolean
  onClick?: () => void
}

export function AppleOption({
  label,
  description,
  selected = false,
  onClick,
}: AppleOptionProps) {
  const theme = appleTheme
  const styles = sharedStyles

  return (
    <motion.button
      className="w-full text-left transition-all"
      style={{
        padding: '16px 20px',
        borderRadius: styles.radius.xl,
        background: selected ? theme.option.backgroundSelected : theme.option.background,
        backdropFilter: selected ? 'none' : `blur(${theme.card.blur})`,
        WebkitBackdropFilter: selected ? 'none' : `blur(${theme.card.blur})`,
        border: `1px solid ${selected ? theme.option.borderSelected : theme.option.border}`,
        color: selected ? theme.option.textSelected : theme.text.primary,
        boxShadow: selected ? theme.card.shadowHover : 'none',
      }}
      onClick={onClick}
      whileHover={{ 
        scale: 1.02,
        boxShadow: theme.card.shadow,
      }}
      whileTap={{ scale: 0.98 }}
    >
      <div style={{ ...styles.typography.body, fontWeight: '500' }}>
        {label}
      </div>
      {description && (
        <div 
          style={{ 
            ...styles.typography.caption, 
            color: selected ? 'rgba(255,255,255,0.8)' : theme.text.secondary,
            marginTop: '4px',
          }}
        >
          {description}
        </div>
      )}
    </motion.button>
  )
}

// Apple 风格的输入框 - 玻璃态
interface AppleInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  onSubmit?: () => void
}

export function AppleInput({
  value,
  onChange,
  placeholder = 'Type here...',
  onSubmit,
}: AppleInputProps) {
  const theme = appleTheme
  const styles = sharedStyles

  return (
    <div 
      className="relative"
      style={{
        background: theme.input.background,
        backdropFilter: `blur(${theme.card.blur})`,
        WebkitBackdropFilter: `blur(${theme.card.blur})`,
        borderRadius: styles.radius.xl,
        border: `1px solid ${theme.input.border}`,
      }}
    >
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && onSubmit?.()}
        placeholder={placeholder}
        className="w-full outline-none bg-transparent"
        style={{
          padding: '18px 20px',
          fontSize: styles.typography.body.fontSize,
          color: theme.text.primary,
        }}
      />
    </div>
  )
}

// Apple 风格的按钮
interface AppleButtonProps {
  children: React.ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: 'primary' | 'secondary'
}

export function AppleButton({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
}: AppleButtonProps) {
  const theme = appleTheme
  const styles = sharedStyles
  const buttonStyle = variant === 'primary' ? theme.button.primary : theme.button.secondary

  return (
    <motion.button
      className="w-full transition-all"
      style={{
        padding: '16px 24px',
        borderRadius: styles.radius.xl,
        background: buttonStyle.background,
        color: buttonStyle.text,
        ...styles.typography.button,
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        boxShadow: variant === 'primary' ? buttonStyle.shadow : 'none',
      }}
      onClick={disabled ? undefined : onClick}
      whileHover={disabled ? {} : { 
        scale: 1.02,
        background: variant === 'primary' ? buttonStyle.backgroundHover : buttonStyle.background,
      }}
      whileTap={disabled ? {} : { scale: 0.98 }}
    >
      {children}
    </motion.button>
  )
}

export default AppleLayout
