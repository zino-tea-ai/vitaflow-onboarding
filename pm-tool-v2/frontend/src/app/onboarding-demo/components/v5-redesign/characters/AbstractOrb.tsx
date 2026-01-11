'use client'

import React from 'react'
import { motion } from 'framer-motion'

// 方案 B: 抽象光球 - 类似 Siri 的呼吸光效
// 简洁、科技感、不是具象角色

export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'success'

interface AbstractOrbProps {
  state?: OrbState
  size?: number
  color?: string
  className?: string
}

export function AbstractOrb({
  state = 'idle',
  size = 80,
  color = '#1A1A1A',
  className = '',
}: AbstractOrbProps) {
  
  // 根据状态获取动画配置
  const getAnimation = () => {
    switch (state) {
      case 'idle':
        return {
          scale: [1, 1.05, 1],
          opacity: [0.8, 1, 0.8],
        }
      case 'listening':
        return {
          scale: [1, 1.1, 1],
          opacity: [0.9, 1, 0.9],
        }
      case 'thinking':
        return {
          scale: [1, 1.08, 0.95, 1.05, 1],
          rotate: [0, 5, -5, 3, 0],
        }
      case 'speaking':
        return {
          scale: [1, 1.12, 1.05, 1.1, 1],
        }
      case 'success':
        return {
          scale: [1, 1.2, 1],
          opacity: [1, 1, 1],
        }
      default:
        return { scale: 1 }
    }
  }

  const getTransition = () => {
    switch (state) {
      case 'idle':
        return { duration: 3, repeat: Infinity, ease: 'easeInOut' }
      case 'listening':
        return { duration: 1.5, repeat: Infinity, ease: 'easeInOut' }
      case 'thinking':
        return { duration: 2, repeat: Infinity, ease: 'easeInOut' }
      case 'speaking':
        return { duration: 0.8, repeat: Infinity, ease: 'easeInOut' }
      case 'success':
        return { duration: 0.5, ease: [0.34, 1.56, 0.64, 1] }
      default:
        return { duration: 0.3 }
    }
  }

  return (
    <div className={`relative ${className}`} style={{ width: size, height: size }}>
      {/* 外层光晕 */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          background: `radial-gradient(circle, ${color}15 0%, transparent 70%)`,
          filter: 'blur(10px)',
        }}
        animate={{
          scale: state === 'speaking' ? [1, 1.3, 1] : [1, 1.15, 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{
          duration: state === 'speaking' ? 0.6 : 2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* 主光球 */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          background: `radial-gradient(circle at 30% 30%, ${color}40 0%, ${color} 100%)`,
          boxShadow: `
            0 0 ${size * 0.3}px ${color}20,
            inset 0 0 ${size * 0.2}px rgba(255, 255, 255, 0.3)
          `,
        }}
        animate={getAnimation()}
        transition={getTransition()}
      />

      {/* 高光点 */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 0.15,
          height: size * 0.15,
          top: '20%',
          left: '25%',
          background: 'rgba(255, 255, 255, 0.6)',
          filter: 'blur(2px)',
        }}
        animate={{
          opacity: [0.6, 0.8, 0.6],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* 次级高光 */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 0.08,
          height: size * 0.08,
          top: '35%',
          left: '60%',
          background: 'rgba(255, 255, 255, 0.4)',
          filter: 'blur(1px)',
        }}
      />
    </div>
  )
}

export default AbstractOrb
