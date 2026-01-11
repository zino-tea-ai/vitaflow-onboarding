'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { colors, shadows, cardBorder } from '../../lib/design-tokens'

interface ChatBubbleProps {
  /** 显示的文本 */
  text: string
  /** 是否显示 */
  visible?: boolean
  /** 气泡位置 */
  position?: 'top' | 'right' | 'bottom-right' | 'top-center'
  /** 是否启用打字机效果 */
  typewriter?: boolean
  /** 打字速度（毫秒/字符） */
  typewriterSpeed?: number
  /** 气泡背景色 */
  backgroundColor?: string
  /** 文字颜色 */
  textColor?: string
  /** 尺寸 */
  size?: 'sm' | 'md' | 'lg'
  /** 额外样式 */
  className?: string
  /** 文字变化时的回调 */
  onTextChange?: () => void
}

/**
 * 对话气泡组件 - Figma 规范
 * 
 * 设计规范：
 * - 白色背景
 * - 圆角 12px
 * - Figma shadow/sm
 * - 1px 边框 rgba(15, 23, 42, 0.01)
 */
export function ChatBubble({
  text,
  visible = true,
  position = 'right',
  typewriter = false,
  typewriterSpeed = 30,
  backgroundColor = colors.surface.white,
  textColor = colors.text.primary,
  size = 'md',
  className = '',
  onTextChange,
}: ChatBubbleProps) {
  const [displayText, setDisplayText] = useState(typewriter ? '' : text)
  const [isTyping, setIsTyping] = useState(false)
  
  // 打字机效果
  useEffect(() => {
    if (!typewriter) {
      setDisplayText(text)
      return
    }
    
    setIsTyping(true)
    setDisplayText('')
    
    let currentIndex = 0
    const interval = setInterval(() => {
      if (currentIndex < text.length) {
        setDisplayText(text.slice(0, currentIndex + 1))
        currentIndex++
      } else {
        clearInterval(interval)
        setIsTyping(false)
      }
    }, typewriterSpeed)
    
    return () => clearInterval(interval)
  }, [text, typewriter, typewriterSpeed])
  
  // 文字变化时触发回调
  useEffect(() => {
    if (onTextChange && !isTyping) {
      onTextChange()
    }
  }, [text, isTyping, onTextChange])
  
  // 尺寸配置 - Figma 规范
  const sizeConfig = {
    sm: {
      padding: '8px 12px',
      fontSize: '12px',
      lineHeight: '1.25',
      letterSpacing: '-0.4px',
      maxWidth: '200px',
      minHeight: '32px',
      borderRadius: '12px',
    },
    md: {
      padding: '12px 16px',
      fontSize: '14px',
      lineHeight: '1.29',
      letterSpacing: '-0.4px',
      maxWidth: '260px',
      minHeight: '40px',
      borderRadius: '12px',
    },
    lg: {
      padding: '16px 20px',
      fontSize: '16px',
      lineHeight: '1.25',
      letterSpacing: '-0.2px',
      maxWidth: '300px',
      minHeight: '48px',
      borderRadius: '12px',
    },
  }
  
  const config = sizeConfig[size]
  
  // 位置配置（箭头方向）
  const positionStyles: Record<string, {
    tail: React.CSSProperties
  }> = {
    top: {
      tail: {
        position: 'absolute',
        bottom: -8,
        left: '50%',
        transform: 'translateX(-50%)',
        width: 0,
        height: 0,
        borderLeft: '8px solid transparent',
        borderRight: '8px solid transparent',
        borderTop: `10px solid ${backgroundColor}`,
      },
    },
    'top-center': {
      tail: {
        position: 'absolute',
        top: -8,
        left: '50%',
        transform: 'translateX(-50%) rotate(180deg)',
        width: 0,
        height: 0,
        borderLeft: '8px solid transparent',
        borderRight: '8px solid transparent',
        borderTop: `10px solid ${backgroundColor}`,
      },
    },
    right: {
      tail: {
        position: 'absolute',
        left: -8,
        top: '50%',
        transform: 'translateY(-50%)',
        width: 0,
        height: 0,
        borderTop: '8px solid transparent',
        borderBottom: '8px solid transparent',
        borderRight: `10px solid ${backgroundColor}`,
      },
    },
    'bottom-right': {
      tail: {
        position: 'absolute',
        left: -6,
        bottom: 12,
        width: 0,
        height: 0,
        borderTop: '8px solid transparent',
        borderBottom: '8px solid transparent',
        borderRight: `10px solid ${backgroundColor}`,
      },
    },
  }
  
  const posStyle = positionStyles[position] || positionStyles.right
  
  // 动画配置
  const bubbleVariants = {
    hidden: {
      opacity: 0,
      scale: 0.9,
      y: position === 'top' || position === 'top-center' ? -10 : 0,
      x: position.includes('right') ? -10 : 0,
    },
    visible: {
      opacity: 1,
      scale: 1,
      y: 0,
      x: 0,
      transition: {
        type: 'spring' as const,
        stiffness: 400,
        damping: 25,
      },
    },
    exit: {
      opacity: 0,
      scale: 0.95,
      transition: {
        duration: 0.15,
      },
    },
  }
  
  return (
    <AnimatePresence mode="wait">
      {visible && (
        <motion.div
          className={`relative ${className}`}
          variants={bubbleVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          key={text}
        >
          {/* 气泡主体 - Figma 规范 */}
          <div
            style={{
              background: backgroundColor,
              color: textColor,
              padding: config.padding,
              borderRadius: config.borderRadius,
              fontSize: config.fontSize,
              lineHeight: config.lineHeight,
              letterSpacing: config.letterSpacing,
              minHeight: config.minHeight,
              maxWidth: config.maxWidth,
              fontWeight: 500,
              border: cardBorder.default,
              boxShadow: shadows.card,
              fontFamily: 'var(--font-outfit)',
            }}
          >
            {displayText}
            {/* 打字机光标 */}
            {isTyping && (
              <motion.span
                className="inline-block w-0.5 h-4 ml-0.5"
                style={{ background: colors.slate[400] }}
                animate={{ opacity: [1, 0] }}
                transition={{ duration: 0.5, repeat: Infinity }}
              />
            )}
          </div>
          
          {/* 气泡尾巴 */}
          <div style={posStyle.tail as React.CSSProperties} />
        </motion.div>
      )}
    </AnimatePresence>
  )
}

/**
 * 角色 + 气泡组合组件
 */
interface MascotWithBubbleProps {
  mascot: React.ReactNode
  bubbleText: string
  bubbleVisible?: boolean
  layout?: 'horizontal' | 'vertical'
  className?: string
}

export function MascotWithBubble({
  mascot,
  bubbleText,
  bubbleVisible = true,
  layout = 'horizontal',
  className = '',
}: MascotWithBubbleProps) {
  return (
    <div 
      className={`flex items-center ${layout === 'vertical' ? 'flex-col' : 'flex-row'} gap-3 ${className}`}
    >
      {mascot}
      <ChatBubble
        text={bubbleText}
        visible={bubbleVisible}
        position={layout === 'vertical' ? 'top' : 'right'}
      />
    </div>
  )
}

export default ChatBubble
