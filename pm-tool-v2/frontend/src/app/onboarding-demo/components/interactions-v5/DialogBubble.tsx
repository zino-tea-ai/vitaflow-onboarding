'use client'

import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { colorsV5, shadowsV5, radiiV5, typographyV5 } from '../../lib/design-tokens-v5'

interface DialogBubbleProps {
  text: string
  typing?: boolean
  typingSpeed?: number
  onTypingComplete?: () => void
  position?: 'center' | 'left' | 'right'
  size?: 'sm' | 'md' | 'lg'
  showTail?: boolean
  tailPosition?: 'bottom' | 'top'
  className?: string
}

export function DialogBubble({
  text,
  typing = false,
  typingSpeed = 30,
  onTypingComplete,
  position = 'center',
  size = 'md',
  showTail = true,
  tailPosition = 'bottom',
  className = '',
}: DialogBubbleProps) {
  const [displayedText, setDisplayedText] = useState(typing ? '' : text)
  const [isTyping, setIsTyping] = useState(typing)

  // Typing effect
  useEffect(() => {
    if (!typing) {
      setDisplayedText(text)
      return
    }

    setDisplayedText('')
    setIsTyping(true)
    let currentIndex = 0

    const interval = setInterval(() => {
      if (currentIndex < text.length) {
        setDisplayedText(text.slice(0, currentIndex + 1))
        currentIndex++
      } else {
        clearInterval(interval)
        setIsTyping(false)
        onTypingComplete?.()
      }
    }, typingSpeed)

    return () => clearInterval(interval)
  }, [text, typing, typingSpeed, onTypingComplete])

  const sizeStyles = {
    sm: {
      padding: '12px 18px',
      fontSize: typographyV5.fontSize.base,
      maxWidth: 280,
    },
    md: {
      padding: '16px 24px',
      fontSize: typographyV5.fontSize.lg,
      maxWidth: 340,
    },
    lg: {
      padding: '20px 28px',
      fontSize: typographyV5.fontSize.xl,
      maxWidth: 400,
    },
  }

  const styles = sizeStyles[size]

  const getPositionStyles = () => {
    switch (position) {
      case 'left':
        return { alignSelf: 'flex-start', marginLeft: 20 }
      case 'right':
        return { alignSelf: 'flex-end', marginRight: 20 }
      default:
        return { alignSelf: 'center' }
    }
  }

  return (
    <motion.div
      className={`relative ${className}`}
      style={getPositionStyles()}
      initial={{ opacity: 0, scale: 0.9, y: 20 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9, y: -10 }}
      transition={{
        type: 'spring',
        stiffness: 400,
        damping: 30,
      }}
    >
      {/* 气泡主体 */}
      <div
        className="relative"
        style={{
          padding: styles.padding,
          maxWidth: styles.maxWidth,
          background: colorsV5.white,
          borderRadius: radiiV5['2xl'],
          boxShadow: shadowsV5.lg,
        }}
      >
        {/* 文字内容 */}
        <p
          style={{
            fontSize: styles.fontSize,
            fontWeight: typographyV5.fontWeight.medium,
            color: colorsV5.slate[800],
            lineHeight: typographyV5.lineHeight.relaxed,
            margin: 0,
          }}
        >
          {displayedText}
          {/* 打字光标 */}
          <AnimatePresence>
            {isTyping && (
              <motion.span
                style={{
                  display: 'inline-block',
                  width: 2,
                  height: '1em',
                  marginLeft: 2,
                  background: colorsV5.mint[500],
                  verticalAlign: 'text-bottom',
                }}
                animate={{ opacity: [1, 0] }}
                transition={{ duration: 0.5, repeat: Infinity }}
              />
            )}
          </AnimatePresence>
        </p>
      </div>

      {/* 气泡尾巴 */}
      {showTail && (
        <div
          className="absolute left-1/2 -translate-x-1/2"
          style={{
            [tailPosition === 'bottom' ? 'bottom' : 'top']: -10,
            transform: `translateX(-50%) ${tailPosition === 'top' ? 'rotate(180deg)' : ''}`,
          }}
        >
          <svg width="24" height="12" viewBox="0 0 24 12">
            <path
              d="M 0 0 L 12 12 L 24 0 Z"
              fill={colorsV5.white}
            />
          </svg>
        </div>
      )}

      {/* 阴影尾巴 */}
      {showTail && (
        <div
          className="absolute left-1/2 -translate-x-1/2 -z-10"
          style={{
            [tailPosition === 'bottom' ? 'bottom' : 'top']: -12,
            transform: `translateX(-50%) ${tailPosition === 'top' ? 'rotate(180deg)' : ''}`,
            filter: 'blur(4px)',
            opacity: 0.15,
          }}
        >
          <svg width="28" height="14" viewBox="0 0 28 14">
            <path
              d="M 0 0 L 14 14 L 28 0 Z"
              fill={colorsV5.slate[900]}
            />
          </svg>
        </div>
      )}
    </motion.div>
  )
}

export default DialogBubble
