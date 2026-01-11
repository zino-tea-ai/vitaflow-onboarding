'use client'

import React from 'react'
import { motion } from 'framer-motion'

// 方案 C: 精致吉祥物 - 使用精致 SVG 而非 CSS
// 参考 Gentler Streak 的 Yorhart 品质

export type MascotState = 'idle' | 'happy' | 'thinking' | 'waving' | 'celebrating'

interface RefinedMascotProps {
  state?: MascotState
  size?: number
  primaryColor?: string
  className?: string
}

export function RefinedMascot({
  state = 'idle',
  size = 120,
  primaryColor = '#10B981', // 绿色
  className = '',
}: RefinedMascotProps) {
  
  // 表情映射
  const getEyeStyle = () => {
    switch (state) {
      case 'happy':
      case 'celebrating':
        return 'happy' // 笑眼
      case 'thinking':
        return 'look-up'
      default:
        return 'normal'
    }
  }

  const getMouthPath = () => {
    switch (state) {
      case 'happy':
      case 'celebrating':
        return 'M 35 58 Q 50 70 65 58' // 大笑
      case 'thinking':
        return 'M 40 60 Q 50 58 60 60' // 扁嘴
      default:
        return 'M 38 58 Q 50 65 62 58' // 微笑
    }
  }

  // 身体动画
  const bodyAnimation = () => {
    switch (state) {
      case 'idle':
        return { y: [0, -4, 0] }
      case 'happy':
        return { y: [0, -8, 0], scale: [1, 1.02, 1] }
      case 'thinking':
        return { rotate: [-2, 2, -2] }
      case 'waving':
        return { rotate: [0, 3, -3, 0] }
      case 'celebrating':
        return { y: [0, -15, 0], scale: [1, 1.05, 1] }
      default:
        return {}
    }
  }

  const bodyTransition = () => {
    switch (state) {
      case 'idle':
        return { duration: 3, repeat: Infinity, ease: 'easeInOut' }
      case 'celebrating':
        return { duration: 0.6, ease: [0.34, 1.56, 0.64, 1] }
      default:
        return { duration: 2, repeat: Infinity, ease: 'easeInOut' }
    }
  }

  const eyeStyle = getEyeStyle()

  return (
    <motion.div
      className={`relative ${className}`}
      style={{ width: size, height: size }}
      animate={bodyAnimation()}
      transition={bodyTransition()}
    >
      <svg
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ width: '100%', height: '100%' }}
      >
        {/* 阴影 */}
        <ellipse
          cx="50"
          cy="92"
          rx="25"
          ry="6"
          fill="rgba(0, 0, 0, 0.1)"
        />

        {/* 身体 - 简洁的水滴/椭圆形 */}
        <ellipse
          cx="50"
          cy="52"
          rx="32"
          ry="38"
          fill={primaryColor}
        />
        
        {/* 身体高光 */}
        <ellipse
          cx="40"
          cy="38"
          rx="15"
          ry="12"
          fill="rgba(255, 255, 255, 0.25)"
        />

        {/* 左眼 */}
        {eyeStyle === 'happy' ? (
          <path
            d="M 35 42 Q 38 38 41 42"
            stroke="#1A1A1A"
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
        ) : (
          <circle cx="38" cy="42" r="5" fill="#1A1A1A">
            {eyeStyle === 'look-up' && (
              <animate attributeName="cy" values="42;40;42" dur="2s" repeatCount="indefinite" />
            )}
          </circle>
        )}

        {/* 右眼 */}
        {eyeStyle === 'happy' ? (
          <path
            d="M 59 42 Q 62 38 65 42"
            stroke="#1A1A1A"
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
        ) : (
          <circle cx="62" cy="42" r="5" fill="#1A1A1A">
            {eyeStyle === 'look-up' && (
              <animate attributeName="cy" values="42;40;42" dur="2s" repeatCount="indefinite" />
            )}
          </circle>
        )}

        {/* 眼睛高光 */}
        {eyeStyle !== 'happy' && (
          <>
            <circle cx="40" cy="40" r="1.5" fill="white" />
            <circle cx="64" cy="40" r="1.5" fill="white" />
          </>
        )}

        {/* 腮红 */}
        {(state === 'happy' || state === 'celebrating') && (
          <>
            <ellipse cx="28" cy="52" rx="6" ry="4" fill="rgba(255, 150, 150, 0.4)" />
            <ellipse cx="72" cy="52" rx="6" ry="4" fill="rgba(255, 150, 150, 0.4)" />
          </>
        )}

        {/* 嘴巴 */}
        <motion.path
          d={getMouthPath()}
          stroke="#1A1A1A"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
        />
      </svg>

      {/* 庆祝效果 - 小星星 */}
      {state === 'celebrating' && (
        <>
          {[...Array(5)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute rounded-full"
              style={{
                width: 6,
                height: 6,
                background: primaryColor,
                left: `${30 + Math.random() * 40}%`,
                top: `${10 + Math.random() * 30}%`,
              }}
              initial={{ opacity: 0, scale: 0 }}
              animate={{
                opacity: [0, 1, 0],
                scale: [0, 1, 0],
                y: [0, -20],
              }}
              transition={{
                duration: 0.8,
                delay: i * 0.1,
                repeat: Infinity,
                repeatDelay: 0.5,
              }}
            />
          ))}
        </>
      )}
    </motion.div>
  )
}

export default RefinedMascot
