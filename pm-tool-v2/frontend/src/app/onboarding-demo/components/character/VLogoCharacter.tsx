'use client'

import { motion } from 'framer-motion'
import { colors } from '../../lib/design-tokens'
import { MascotState } from './VitaCharacter'

interface VLogoCharacterProps {
  state?: MascotState
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

// 表情配置类型
interface Expression {
  eyes: string
  mouth: string
  animation?: { scale?: number[]; rotate?: number[]; y?: number[]; transition?: object }
}

/**
 * 风格 A - V Logo 表情版
 * 基于 VitaFlow V Logo，添加眼睛/嘴巴状态
 */
export function VLogoCharacter({ 
  state = 'idle', 
  size = 'md',
  className = '' 
}: VLogoCharacterProps) {
  const sizeMap = {
    sm: 48,
    md: 64,
    lg: 80,
  }
  
  const s = sizeMap[size]
  
  // 表情配置（支持所有新状态）
  const expressions: Record<string, Expression> = {
    neutral: { eyes: '● ●', mouth: '—' },
    idle: { 
      eyes: '● ●', 
      mouth: '◡',
      animation: { y: [0, -2, 0], transition: { duration: 2, repeat: Infinity, ease: 'easeInOut' } }
    },
    greeting: {
      eyes: '◠ ◠',
      mouth: 'D',
      animation: { rotate: [-8, 8, -8, 0], transition: { duration: 0.8, ease: 'easeInOut' } }
    },
    listening: { eyes: '● ●', mouth: '—' },
    thinking: {
      eyes: '· ·',
      mouth: '~',
      animation: { y: [0, -3, 0], transition: { duration: 1.5, repeat: Infinity, ease: 'easeInOut' } }
    },
    explaining: {
      eyes: '● ●',
      mouth: 'o',
      animation: { scale: [1, 1.02, 1], transition: { duration: 0.8, repeat: Infinity, ease: 'easeInOut' } }
    },
    happy: {
      eyes: '◠ ◠',
      mouth: '◡',
      animation: { scale: [1, 1.05, 1], transition: { duration: 0.3 } }
    },
    excited: {
      eyes: '★ ★',
      mouth: 'D',
      animation: { rotate: [-5, 5, -5, 0], transition: { duration: 0.4, ease: 'easeInOut' } }
    },
    encouraging: {
      eyes: '^ ^',
      mouth: '◡',
      animation: { scale: [1, 1.08, 1], transition: { duration: 0.5, ease: 'easeInOut' } }
    },
    proud: {
      eyes: '◠ ◠',
      mouth: 'D',
      animation: { scale: [1, 1.1, 1.05], transition: { duration: 0.6, ease: 'easeOut' } }
    },
    celebrating: {
      eyes: '✧ ✧',
      mouth: 'D',
      animation: { y: [0, -10, 0], rotate: [-5, 5, 0], transition: { duration: 0.6, ease: 'easeOut' } }
    },
    surprised: {
      eyes: '⊙ ⊙',
      mouth: 'o',
      animation: { scale: [1, 1.15, 1], transition: { duration: 0.3, ease: 'easeOut' } }
    },
    waving: {
      eyes: '◠ ◠',
      mouth: '◡',
      animation: { rotate: [-10, 10, -10, 0], transition: { duration: 0.6, ease: 'easeInOut' } }
    },
    cheering: {
      eyes: '✧ ✧',
      mouth: 'D',
      animation: { y: [0, -8, 0], transition: { duration: 0.4, ease: 'easeOut' } }
    },
  }
  
  const expr = expressions[state] || expressions.idle
  
  return (
    <motion.div
      className={`relative flex items-center justify-center ${className}`}
      style={{ width: s, height: s }}
      animate={expr.animation}
    >
      {/* V Logo 背景 */}
      <motion.div
        className="absolute inset-0 rounded-2xl flex items-center justify-center"
        style={{ 
          background: `linear-gradient(135deg, ${colors.accent.primary}, ${colors.accent.light || colors.accent.primary})`,
          boxShadow: colors.shadows.glow,
        }}
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        {/* V 形状 */}
        <svg 
          width={s * 0.5} 
          height={s * 0.5} 
          viewBox="0 0 24 24" 
          fill="none"
        >
          <motion.path
            d="M6 8L12 18L18 8"
            stroke="white"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          />
        </svg>
      </motion.div>
      
      {/* 表情层 - 眼睛 */}
      <motion.div
        className="absolute flex gap-1 text-white font-bold"
        style={{ 
          top: s * 0.22,
          fontSize: s * 0.12,
          letterSpacing: s * 0.08,
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        {expr.eyes.split(' ')[0]}
        <span style={{ marginLeft: s * 0.06 }}>{expr.eyes.split(' ')[1]}</span>
      </motion.div>
      
      {/* 表情层 - 嘴巴 */}
      <motion.div
        className="absolute text-white font-bold"
        style={{ 
          bottom: s * 0.2,
          fontSize: s * 0.15,
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        {expr.mouth}
      </motion.div>
    </motion.div>
  )
}

export default VLogoCharacter
