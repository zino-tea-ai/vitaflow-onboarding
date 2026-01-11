'use client'

import React, { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowRight, X } from 'lucide-react'
import { colorsV5, shadowsV5, radiiV5, typographyV5 } from '../../lib/design-tokens-v5'

interface ConversationalInputProps {
  value: string
  onChange: (value: string) => void
  onSubmit?: () => void
  placeholder?: string
  type?: 'text' | 'email' | 'tel'
  autoFocus?: boolean
  showSubmitButton?: boolean
  showClearButton?: boolean
  maxLength?: number
  validation?: (value: string) => boolean
  errorMessage?: string
  className?: string
}

export function ConversationalInput({
  value,
  onChange,
  onSubmit,
  placeholder = 'Type here...',
  type = 'text',
  autoFocus = true,
  showSubmitButton = true,
  showClearButton = true,
  maxLength,
  validation,
  errorMessage = 'Please enter a valid value',
  className = '',
}: ConversationalInputProps) {
  const [isFocused, setIsFocused] = useState(false)
  const [hasError, setHasError] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (autoFocus) {
      inputRef.current?.focus()
    }
  }, [autoFocus])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    if (maxLength && newValue.length > maxLength) return
    
    onChange(newValue)
    
    if (validation && newValue) {
      setHasError(!validation(newValue))
    } else {
      setHasError(false)
    }
  }

  const handleSubmit = () => {
    if (validation && !validation(value)) {
      setHasError(true)
      return
    }
    onSubmit?.()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && value.trim()) {
      handleSubmit()
    }
  }

  const handleClear = () => {
    onChange('')
    setHasError(false)
    inputRef.current?.focus()
  }

  const isValid = value.trim().length > 0 && !hasError

  return (
    <div className={`w-full max-w-md mx-auto ${className}`}>
      {/* 输入框容器 */}
      <motion.div
        className="relative"
        animate={{
          scale: isFocused ? 1.02 : 1,
        }}
        transition={{ duration: 0.2 }}
      >
        {/* 背景 */}
        <motion.div
          className="absolute inset-0 rounded-2xl"
          style={{
            background: colorsV5.white,
            boxShadow: isFocused 
              ? `0 0 0 2px ${hasError ? colorsV5.semantic.error : colorsV5.slate[900]}, ${shadowsV5.lg}`
              : shadowsV5.card.default,
          }}
          animate={{
            boxShadow: isFocused 
              ? `0 0 0 2px ${hasError ? colorsV5.semantic.error : colorsV5.slate[900]}, ${shadowsV5.lg}`
              : shadowsV5.card.default,
          }}
        />

        {/* 输入框 */}
        <div className="relative flex items-center">
          <input
            ref={inputRef}
            type={type}
            value={value}
            onChange={handleChange}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="w-full bg-transparent outline-none"
            style={{
              padding: '20px 24px',
              paddingRight: showSubmitButton || showClearButton ? '100px' : '24px',
              fontSize: typographyV5.fontSize.xl,
              fontWeight: typographyV5.fontWeight.medium,
              color: colorsV5.slate[900],
              caretColor: colorsV5.mint[500],
            }}
          />

          {/* 按钮区域 */}
          <div className="absolute right-3 flex items-center gap-2">
            {/* 清除按钮 */}
            <AnimatePresence>
              {showClearButton && value && (
                <motion.button
                  className="flex items-center justify-center"
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: radiiV5.full,
                    background: colorsV5.slate[100],
                    color: colorsV5.slate[500],
                  }}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  whileHover={{ background: colorsV5.slate[200] }}
                  whileTap={{ scale: 0.9 }}
                  onClick={handleClear}
                  type="button"
                >
                  <X size={16} />
                </motion.button>
              )}
            </AnimatePresence>

            {/* 提交按钮 */}
            {showSubmitButton && (
              <motion.button
                className="flex items-center justify-center"
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: radiiV5.full,
                  background: isValid ? colorsV5.slate[900] : colorsV5.slate[200],
                  color: isValid ? colorsV5.white : colorsV5.slate[400],
                }}
                animate={{
                  background: isValid ? colorsV5.slate[900] : colorsV5.slate[200],
                }}
                whileHover={isValid ? { scale: 1.05 } : {}}
                whileTap={isValid ? { scale: 0.95 } : {}}
                onClick={handleSubmit}
                disabled={!isValid}
                type="button"
              >
                <ArrowRight size={20} />
              </motion.button>
            )}
          </div>
        </div>

        {/* 下划线动画 */}
        <motion.div
          className="absolute bottom-0 left-6 right-6 h-0.5 rounded-full"
          style={{
            background: hasError ? colorsV5.semantic.error : colorsV5.mint[500],
            transformOrigin: 'left',
          }}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: isFocused ? 1 : 0 }}
          transition={{ duration: 0.3 }}
        />
      </motion.div>

      {/* 错误信息 */}
      <AnimatePresence>
        {hasError && (
          <motion.div
            className="mt-3 text-center"
            style={{
              fontSize: typographyV5.fontSize.sm,
              color: colorsV5.semantic.error,
            }}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            {errorMessage}
          </motion.div>
        )}
      </AnimatePresence>

      {/* 字符计数 */}
      {maxLength && (
        <motion.div
          className="mt-2 text-right"
          style={{
            fontSize: typographyV5.fontSize.sm,
            color: value.length >= maxLength ? colorsV5.semantic.error : colorsV5.slate[400],
          }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {value.length}/{maxLength}
        </motion.div>
      )}
    </div>
  )
}

export default ConversationalInput
