/**
 * AICursor - AI 光标组件
 * 使用 Motion+ Cursor 和 useSpring 实现 Atlas 级别的光标动画
 * 
 * 功能：
 * - Spring 弹簧动画移动
 * - 点击涟漪效果
 * - 输入状态动画
 * - 光晕呼吸效果
 */

import { motion, useSpring, useMotionValue, AnimatePresence } from 'motion/react'
import { useState, useEffect, useCallback } from 'react'
import { cn } from '@/lib/utils'

// 光标状态类型
export type CursorState = 'idle' | 'moving' | 'clicking' | 'typing' | 'hidden'

export interface CursorPosition {
  x: number
  y: number
}

export interface AICursorProps {
  /** 目标位置 */
  targetPosition: CursorPosition
  /** 光标状态 */
  state?: CursorState
  /** 是否显示 */
  visible?: boolean
  /** 标签文字 */
  label?: string
  /** 容器边界（用于约束光标） */
  containerRef?: React.RefObject<HTMLDivElement>
  /** 动画完成回调 */
  onAnimationComplete?: () => void
  className?: string
}

// Spring 配置 - 基于 Motion 官方最佳实践
const SPRING_CONFIG = {
  stiffness: 300,
  damping: 25,
  mass: 0.8,
}

// 快速 Spring（用于点击等快速动作）
const SPRING_FAST = {
  stiffness: 500,
  damping: 30,
}

export function AICursor({
  targetPosition,
  state = 'idle',
  visible = true,
  label = 'AI',
  onAnimationComplete,
  className,
}: AICursorProps) {
  // Motion values for smooth animation
  const x = useMotionValue(targetPosition.x)
  const y = useMotionValue(targetPosition.y)
  
  // Spring-animated values
  const springX = useSpring(x, SPRING_CONFIG)
  const springY = useSpring(y, SPRING_CONFIG)
  
  // Ripple state for click effects
  const [ripples, setRipples] = useState<Array<{ id: number; x: number; y: number }>>([])
  const [rippleId, setRippleId] = useState(0)
  
  // Update position when target changes
  useEffect(() => {
    x.set(targetPosition.x)
    y.set(targetPosition.y)
  }, [targetPosition.x, targetPosition.y, x, y])
  
  // Create ripple effect on click
  const createRipple = useCallback(() => {
    const newRipple = {
      id: rippleId,
      x: targetPosition.x,
      y: targetPosition.y,
    }
    setRipples(prev => [...prev, newRipple])
    setRippleId(prev => prev + 1)
    
    // Remove ripple after animation
    setTimeout(() => {
      setRipples(prev => prev.filter(r => r.id !== newRipple.id))
    }, 600)
  }, [rippleId, targetPosition])
  
  // Trigger ripple on clicking state
  useEffect(() => {
    if (state === 'clicking') {
      createRipple()
    }
  }, [state, createRipple])
  
  if (!visible) return null
  
  return (
    <div className={cn('absolute inset-0 pointer-events-none overflow-hidden', className)}>
      {/* Ripple container */}
      <AnimatePresence>
        {ripples.map(ripple => (
          <motion.div
            key={ripple.id}
            className="absolute w-8 h-8 -ml-4 -mt-4 rounded-full border-2 border-indigo-500"
            style={{
              left: ripple.x,
              top: ripple.y,
              willChange: 'transform, opacity',
            }}
            initial={{ scale: 0, opacity: 1 }}
            animate={{ scale: 3, opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          />
        ))}
      </AnimatePresence>
      
      {/* Main cursor */}
      <motion.div
        className="absolute"
        style={{
          x: springX,
          y: springY,
          willChange: 'transform',
        }}
        onAnimationComplete={onAnimationComplete}
      >
        {/* Cursor glow */}
        <motion.div
          className="absolute -inset-4 rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(99, 102, 241, 0.4) 0%, transparent 70%)',
            willChange: 'transform, opacity',
          }}
          animate={{
            scale: state === 'clicking' ? [1, 2, 1] : [1, 1.3, 1],
            opacity: state === 'clicking' ? [0.6, 0.8, 0.3] : [0.3, 0.6, 0.3],
          }}
          transition={{
            duration: state === 'clicking' ? 0.3 : 2,
            repeat: state === 'clicking' ? 0 : Infinity,
            ease: 'easeInOut',
          }}
        />
        
        {/* Cursor pointer SVG */}
        <motion.div
          className="relative"
          animate={{
            scale: state === 'clicking' ? [1, 0.85, 1] : 1,
            y: state === 'typing' ? [0, -3, 0] : 0,
            rotate: state === 'moving' ? [0, 5, 0] : 0,
          }}
          transition={
            state === 'typing'
              ? { duration: 0.3, repeat: Infinity, ease: 'easeInOut' }
              : state === 'clicking'
              ? { ...SPRING_FAST, duration: 0.3 }
              : { ...SPRING_CONFIG, duration: 0.3 }
          }
        >
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            className="drop-shadow-lg"
            style={{ filter: 'drop-shadow(0 2px 8px rgba(99, 102, 241, 0.5))' }}
          >
            <defs>
              <linearGradient id="cursor-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#818cf8" />
                <stop offset="50%" stopColor="#6366f1" />
                <stop offset="100%" stopColor="#4f46e5" />
              </linearGradient>
            </defs>
            <path
              d="M5.5 3.21V20.79C5.5 21.3 6.0 21.58 6.4 21.28L11.17 17.21L13.8 22.74C14.0 23.18 14.56 23.37 15.0 23.17L17.27 22.13C17.71 21.93 17.9 21.37 17.7 20.93L15.07 15.41L21.5 14.79C22.05 14.73 22.32 14.07 21.96 13.64L6.96 3.36C6.6 3.06 6.0 3.26 5.5 3.71Z"
              fill="url(#cursor-gradient)"
              stroke="rgba(255,255,255,0.8)"
              strokeWidth="1.5"
            />
          </svg>
        </motion.div>
        
        {/* Cursor label */}
        <motion.div
          className="absolute left-8 top-1 px-2.5 py-1 rounded-xl text-xs font-semibold text-white whitespace-nowrap"
          style={{
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            boxShadow: '0 4px 12px rgba(99, 102, 241, 0.4)',
          }}
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
        >
          <span className="inline-block w-1.5 h-1.5 bg-white rounded-full mr-1.5 animate-pulse" />
          {state === 'typing' ? '输入中...' : label}
        </motion.div>
      </motion.div>
    </div>
  )
}

export default AICursor

