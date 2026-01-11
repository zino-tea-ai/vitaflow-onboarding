'use client'

import { motion } from 'framer-motion'
import { colors } from '../../lib/design-tokens'
import { MascotState } from './VitaCharacter'

interface AbstractCharacterProps {
  state?: MascotState
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

interface StateConfig {
  color: string
  glowColor: string
  animation: object
  pulseRings?: number
}

/**
 * 风格 C - 抽象圆点
 * 简单的彩色圆点/光晕，状态通过颜色和动画表达
 */
export function AbstractCharacter({ 
  state = 'idle', 
  size = 'md',
  className = '' 
}: AbstractCharacterProps) {
  const sizeMap = {
    sm: 32,
    md: 44,
    lg: 56,
  }
  
  const s = sizeMap[size]
  
  // 状态配置：颜色 + 动画（支持所有新状态）
  const stateConfig: Record<string, StateConfig> = {
    neutral: {
      color: colors.accent.primary,
      glowColor: `${colors.accent.primary}30`,
      animation: { scale: [1, 1.02, 1], transition: { duration: 2, repeat: Infinity, ease: 'easeInOut' } },
    },
    idle: {
      color: colors.accent.primary,
      glowColor: `${colors.accent.primary}30`,
      animation: { scale: [1, 1.05, 1], y: [0, -2, 0], transition: { duration: 2.5, repeat: Infinity, ease: 'easeInOut' } },
    },
    greeting: {
      color: colors.accent.primary,
      glowColor: `${colors.accent.primary}50`,
      animation: { scale: [1, 1.15, 1], x: [-5, 5, -5, 0], transition: { duration: 0.8, ease: 'easeInOut' } },
      pulseRings: 2,
    },
    listening: {
      color: colors.accent.primary,
      glowColor: `${colors.accent.primary}30`,
      animation: { scale: [1, 1.03, 1], transition: { duration: 1.5, repeat: Infinity, ease: 'easeInOut' } },
    },
    thinking: {
      color: colors.slate[600],
      glowColor: `${colors.slate[600]}40`,
      animation: { opacity: [1, 0.6, 1], transition: { duration: 1.5, repeat: Infinity, ease: 'easeInOut' } },
    },
    explaining: {
      color: colors.accent.primary,
      glowColor: `${colors.accent.primary}40`,
      animation: { scale: [1, 1.05, 1], transition: { duration: 1, repeat: Infinity, ease: 'easeInOut' } },
    },
    happy: {
      color: colors.accent.primary,
      glowColor: `${colors.accent.primary}50`,
      animation: { scale: [1, 1.1, 1], transition: { duration: 0.4, ease: 'easeInOut' } },
      pulseRings: 2,
    },
    excited: {
      color: '#FFD700',
      glowColor: 'rgba(255, 215, 0, 0.4)',
      animation: { scale: [1, 1.2, 1], y: [0, -5, 0], transition: { duration: 0.4, ease: 'easeOut' } },
      pulseRings: 3,
    },
    encouraging: {
      color: colors.accent.primary,
      glowColor: `${colors.accent.primary}60`,
      animation: { scale: [1, 1.15, 1], transition: { duration: 0.5, ease: 'easeInOut' } },
      pulseRings: 2,
    },
    proud: {
      color: colors.accent.primary,
      glowColor: `${colors.accent.primary}60`,
      animation: { scale: [1, 1.2, 1.1], transition: { duration: 0.6, ease: 'easeOut' } },
      pulseRings: 2,
    },
    celebrating: {
      color: '#FFD700',
      glowColor: 'rgba(255, 215, 0, 0.5)',
      animation: { scale: [1, 1.3, 1], y: [0, -10, 0], transition: { duration: 0.6, ease: 'easeOut' } },
      pulseRings: 4,
    },
    surprised: {
      color: colors.slate[600],
      glowColor: `${colors.slate[600]}50`,
      animation: { scale: [1, 1.3, 1.1], transition: { duration: 0.25, ease: 'easeOut' } },
      pulseRings: 2,
    },
    waving: {
      color: colors.accent.primary,
      glowColor: `${colors.accent.primary}40`,
      animation: { x: [-3, 3, -3, 0], transition: { duration: 0.6, ease: 'easeInOut' } },
    },
    cheering: {
      color: '#FF6B6B',
      glowColor: 'rgba(255, 107, 107, 0.4)',
      animation: { scale: [1, 1.25, 1], y: [0, -8, 0], transition: { duration: 0.4, ease: 'easeOut' } },
      pulseRings: 3,
    },
  }
  
  const config = stateConfig[state] || stateConfig.idle
  
  // 渲染脉冲圆环
  const renderPulseRings = () => {
    if (!config.pulseRings) return null
    
    return Array.from({ length: config.pulseRings }).map((_, i) => (
      <motion.div
        key={i}
        className="absolute rounded-full"
        style={{
          width: s,
          height: s,
          left: 0,
          top: 0,
          border: `2px solid ${config.color}`,
        }}
        initial={{ scale: 1, opacity: 0.6 }}
        animate={{ 
          scale: [1, 1.8 + i * 0.3], 
          opacity: [0.6, 0],
        }}
        transition={{ 
          duration: 0.8, 
          delay: i * 0.15,
          ease: 'easeOut',
        }}
      />
    ))
  }
  
  return (
    <motion.div
      className={`relative flex items-center justify-center ${className}`}
      style={{ width: s, height: s }}
    >
      {/* 脉冲圆环 */}
      {renderPulseRings()}
      
      {/* 光晕 */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: s * 1.5,
          height: s * 1.5,
          background: `radial-gradient(circle, ${config.glowColor}, transparent)`,
        }}
        animate={{ scale: [1, 1.1, 1], opacity: [0.5, 0.8, 0.5] }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      />
      
      {/* 主圆点 */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: s,
          height: s,
          background: config.color,
          boxShadow: `0 0 20px ${config.glowColor}`,
        }}
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ 
          scale: 1, 
          opacity: 1,
          ...config.animation 
        }}
      />
      
      {/* 高光点 */}
      <motion.div
        className="absolute rounded-full bg-white"
        style={{
          width: s * 0.25,
          height: s * 0.25,
          top: s * 0.15,
          left: s * 0.2,
          opacity: 0.6,
        }}
      />
    </motion.div>
  )
}

export default AbstractCharacter
