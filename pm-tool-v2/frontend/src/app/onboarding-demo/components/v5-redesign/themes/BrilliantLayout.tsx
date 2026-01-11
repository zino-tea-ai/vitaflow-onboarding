'use client'

import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { brilliantTheme, sharedStyles } from './tokens'

// Brilliant Style 布局 - 极简白底
// 参考 Brilliant.org 的设计语言

interface BrilliantLayoutProps {
  children: React.ReactNode
  // 角色区域
  characterSlot?: React.ReactNode
  // 对话文字
  dialogText?: string
  // 是否显示对话
  showDialog?: boolean
  className?: string
}

export function BrilliantLayout({
  children,
  characterSlot,
  dialogText,
  showDialog = true,
  className = '',
}: BrilliantLayoutProps) {
  const theme = brilliantTheme
  const styles = sharedStyles

  return (
    <motion.div
      className={`relative h-full w-full flex flex-col ${className}`}
      style={{
        background: theme.background.primary,
        fontFamily: styles.typography.fontFamily,
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* 上半部分 - 角色 + 对话 */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 pt-12">
        {/* 角色区域 */}
        {characterSlot && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            {characterSlot}
          </motion.div>
        )}

        {/* 对话文字 */}
        <AnimatePresence mode="wait">
          {showDialog && dialogText && (
            <motion.p
              key={dialogText}
              className="text-center mt-6 max-w-[280px]"
              style={{
                ...styles.typography.title,
                color: theme.text.primary,
              }}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.3, delay: 0.2 }}
            >
              {dialogText}
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* 下半部分 - 交互区域 */}
      <motion.div
        className="px-6 pb-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.3 }}
      >
        {children}
      </motion.div>
    </motion.div>
  )
}

// Brilliant 风格的选项卡片
interface BrilliantOptionProps {
  label: string
  description?: string
  selected?: boolean
  onClick?: () => void
}

export function BrilliantOption({
  label,
  description,
  selected = false,
  onClick,
}: BrilliantOptionProps) {
  const theme = brilliantTheme
  const styles = sharedStyles

  return (
    <motion.button
      className="w-full text-left transition-all"
      style={{
        padding: '16px 20px',
        borderRadius: styles.radius.xl,
        background: selected ? theme.option.backgroundSelected : theme.option.background,
        border: `1.5px solid ${selected ? theme.option.borderSelected : theme.option.border}`,
        color: selected ? theme.option.textSelected : theme.text.primary,
      }}
      onClick={onClick}
      whileHover={{ 
        scale: 1.01,
        background: selected ? theme.option.backgroundSelected : theme.option.backgroundHover,
      }}
      whileTap={{ scale: 0.99 }}
    >
      <div style={{ ...styles.typography.body, fontWeight: '500' }}>
        {label}
      </div>
      {description && (
        <div 
          style={{ 
            ...styles.typography.caption, 
            color: selected ? 'rgba(255,255,255,0.7)' : theme.text.secondary,
            marginTop: '4px',
          }}
        >
          {description}
        </div>
      )}
    </motion.button>
  )
}

// Brilliant 风格的输入框
interface BrilliantInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  onSubmit?: () => void
}

export function BrilliantInput({
  value,
  onChange,
  placeholder = 'Type here...',
  onSubmit,
}: BrilliantInputProps) {
  const theme = brilliantTheme
  const styles = sharedStyles

  return (
    <div className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && onSubmit?.()}
        placeholder={placeholder}
        className="w-full outline-none transition-all"
        style={{
          padding: '18px 20px',
          borderRadius: styles.radius.xl,
          border: `1.5px solid ${theme.input.border}`,
          background: theme.input.background,
          fontSize: styles.typography.body.fontSize,
          color: theme.text.primary,
        }}
      />
    </div>
  )
}

// Brilliant 风格的按钮
interface BrilliantButtonProps {
  children: React.ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: 'primary' | 'secondary'
}

export function BrilliantButton({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
}: BrilliantButtonProps) {
  const theme = brilliantTheme
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
        border: variant === 'secondary' ? `1.5px solid ${buttonStyle.border}` : 'none',
      }}
      onClick={disabled ? undefined : onClick}
      whileHover={disabled ? {} : { scale: 1.01 }}
      whileTap={disabled ? {} : { scale: 0.99 }}
    >
      {children}
    </motion.button>
  )
}

export default BrilliantLayout
