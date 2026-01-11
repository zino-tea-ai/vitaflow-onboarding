'use client'

import React from 'react'
import { motion } from 'framer-motion'

// 方案 D: 仅 Logo - VitaFlow 的 V 标志
// 品牌化、简洁、带微妙动画

export type LogoState = 'idle' | 'active' | 'success' | 'pulse'

interface LogoMarkProps {
  state?: LogoState
  size?: number
  color?: string
  backgroundColor?: string
  className?: string
}

export function LogoMark({
  state = 'idle',
  size = 64,
  color = '#FFFFFF',
  backgroundColor = '#1A1A1A',
  className = '',
}: LogoMarkProps) {
  
  // 容器动画
  const getContainerAnimation = () => {
    switch (state) {
      case 'idle':
        return { scale: 1 }
      case 'active':
        return { scale: [1, 1.05, 1] }
      case 'success':
        return { scale: [1, 1.15, 1], rotate: [0, 5, -5, 0] }
      case 'pulse':
        return { scale: [1, 1.08, 1] }
      default:
        return {}
    }
  }

  const getContainerTransition = () => {
    switch (state) {
      case 'active':
        return { duration: 2, repeat: Infinity, ease: 'easeInOut' }
      case 'success':
        return { duration: 0.6, ease: [0.34, 1.56, 0.64, 1] }
      case 'pulse':
        return { duration: 1.5, repeat: Infinity, ease: 'easeInOut' }
      default:
        return { duration: 0.3 }
    }
  }

  return (
    <motion.div
      className={`relative ${className}`}
      style={{ width: size, height: size }}
      animate={getContainerAnimation()}
      transition={getContainerTransition()}
    >
      {/* 外层光晕 - 仅在活跃状态 */}
      {(state === 'active' || state === 'pulse') && (
        <motion.div
          className="absolute inset-0 rounded-2xl"
          style={{
            background: backgroundColor,
            filter: 'blur(15px)',
            opacity: 0.3,
          }}
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.2, 0.4, 0.2],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      )}

      {/* Logo 容器 */}
      <div
        className="relative w-full h-full flex items-center justify-center rounded-2xl overflow-hidden"
        style={{
          background: backgroundColor,
          boxShadow: state === 'success' 
            ? `0 8px 24px ${backgroundColor}40`
            : `0 2px 8px ${backgroundColor}20`,
        }}
      >
        {/* V 字母 */}
        <motion.svg
          viewBox="0 0 24 24"
          fill="none"
          style={{ width: '50%', height: '50%' }}
          animate={state === 'success' ? { scale: [1, 1.1, 1] } : {}}
          transition={{ duration: 0.4 }}
        >
          <motion.path
            d="M4 6L12 18L20 6"
            stroke={color}
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
          />
        </motion.svg>

        {/* 微光效果 */}
        <motion.div
          className="absolute inset-0"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.15) 0%, transparent 50%)',
          }}
        />
      </div>

      {/* Success 效果 - 环形扩散 */}
      {state === 'success' && (
        <>
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="absolute inset-0 rounded-2xl"
              style={{
                border: `2px solid ${backgroundColor}`,
              }}
              initial={{ scale: 1, opacity: 0.5 }}
              animate={{
                scale: [1, 1.5 + i * 0.2],
                opacity: [0.5, 0],
              }}
              transition={{
                duration: 0.8,
                delay: i * 0.15,
                ease: 'easeOut',
              }}
            />
          ))}
        </>
      )}
    </motion.div>
  )
}

export default LogoMark
