'use client'

import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { colorsV5, easingsV5 } from '../../lib/design-tokens-v5'
import { characterAnimations } from '../../lib/animation-presets'

// 角色状态类型
export type CharacterState = 
  | 'idle' 
  | 'speaking' 
  | 'thinking' 
  | 'happy' 
  | 'surprised' 
  | 'encouraging' 
  | 'celebrating'
  | 'waving'

// 表情类型
export type Expression = 
  | 'neutral' 
  | 'smile' 
  | 'grin' 
  | 'wink' 
  | 'surprised' 
  | 'thinking'
  | 'excited'

interface VitaEvolutionProps {
  state?: CharacterState
  expression?: Expression
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
  showAccessory?: boolean
  accessoryType?: 'none' | 'chef-hat' | 'fitness-band' | 'glasses'
}

// 尺寸映射
const sizeMap = {
  sm: { body: 80, scale: 0.6 },
  md: { body: 120, scale: 0.8 },
  lg: { body: 160, scale: 1 },
  xl: { body: 200, scale: 1.25 },
}

export function VitaEvolution({ 
  state = 'idle',
  expression = 'neutral',
  size = 'lg',
  className = '',
  showAccessory = false,
  accessoryType = 'none',
}: VitaEvolutionProps) {
  const { body: bodySize, scale } = sizeMap[size]
  
  // 获取当前动画状态
  const getBodyAnimation = () => {
    switch (state) {
      case 'idle':
        return characterAnimations.idle
      case 'speaking':
        return characterAnimations.speaking
      case 'thinking':
        return characterAnimations.thinking
      case 'happy':
        return characterAnimations.happy
      case 'surprised':
        return characterAnimations.surprised
      case 'encouraging':
        return characterAnimations.encouraging
      case 'celebrating':
        return characterAnimations.celebrating
      case 'waving':
        return characterAnimations.waving
      default:
        return characterAnimations.idle
    }
  }

  // 眼睛表情
  const getEyeExpression = () => {
    switch (expression) {
      case 'smile':
      case 'grin':
        return { d: 'M 8 15 Q 15 10 22 15', scaleY: 1 } // 笑眼
      case 'wink':
        return { d: 'M 8 14 L 22 14', scaleY: 1 } // 眯眼
      case 'surprised':
        return { d: 'M 15 10 A 5 5 0 1 0 15 20 A 5 5 0 1 0 15 10', scaleY: 1.2 } // 圆眼
      case 'thinking':
        return { d: 'M 10 14 L 20 16', scaleY: 1 } // 斜眼
      case 'excited':
        return { d: 'M 10 12 L 10 18 M 20 12 L 20 18', scaleY: 1 } // 星星眼简化
      default:
        return { d: 'M 15 12 A 3 3 0 1 0 15 18 A 3 3 0 1 0 15 12', scaleY: 1 } // 正常圆眼
    }
  }

  // 嘴巴表情
  const getMouthExpression = () => {
    switch (expression) {
      case 'smile':
        return 'M 12 26 Q 15 30 18 26'
      case 'grin':
        return 'M 10 25 Q 15 32 20 25'
      case 'surprised':
        return 'M 13 26 A 2 3 0 1 0 17 26 A 2 3 0 1 0 13 26'
      case 'thinking':
        return 'M 12 27 Q 14 25 18 27'
      case 'wink':
        return 'M 12 26 Q 15 29 18 26'
      case 'excited':
        return 'M 10 24 Q 15 33 20 24'
      default:
        return 'M 13 26 Q 15 28 17 26'
    }
  }
  
  const eyeExpr = getEyeExpression()
  const mouthPath = getMouthExpression()

  return (
    <motion.div 
      className={`relative ${className}`}
      style={{ 
        width: bodySize * 1.5,
        height: bodySize * 2,
        transform: `scale(${scale})`,
        transformOrigin: 'center bottom',
      }}
    >
      {/* 身体阴影 */}
      <motion.div
        className="absolute bottom-0 left-1/2 -translate-x-1/2"
        style={{
          width: bodySize * 0.6,
          height: bodySize * 0.15,
          background: 'rgba(15, 23, 42, 0.1)',
          borderRadius: '50%',
          filter: 'blur(8px)',
        }}
        animate={{
          scale: state === 'celebrating' ? [1, 0.8, 1] : 1,
          opacity: state === 'celebrating' ? [0.2, 0.1, 0.2] : 0.2,
        }}
        transition={{ duration: 0.5 }}
      />

      {/* 腿部 */}
      <motion.div
        className="absolute bottom-4 left-1/2"
        style={{ x: '-50%' }}
      >
        {/* 左腿 */}
        <motion.div
          className="absolute"
          style={{
            width: 12,
            height: 35,
            background: colorsV5.mint[500],
            borderRadius: 6,
            left: -18,
            transformOrigin: 'top center',
          }}
          animate={state === 'celebrating' ? { rotate: [-10, 10, -10] } : { rotate: 0 }}
          transition={{ duration: 0.3, repeat: state === 'celebrating' ? Infinity : 0 }}
        />
        {/* 右腿 */}
        <motion.div
          className="absolute"
          style={{
            width: 12,
            height: 35,
            background: colorsV5.mint[500],
            borderRadius: 6,
            left: 6,
            transformOrigin: 'top center',
          }}
          animate={state === 'celebrating' ? { rotate: [10, -10, 10] } : { rotate: 0 }}
          transition={{ duration: 0.3, repeat: state === 'celebrating' ? Infinity : 0, delay: 0.15 }}
        />
      </motion.div>

      {/* 主体 (头+身体一体) */}
      <motion.div
        className="absolute bottom-[35px] left-1/2"
        style={{ x: '-50%' }}
        animate={getBodyAnimation()}
      >
        {/* 身体 SVG */}
        <svg
          width={bodySize}
          height={bodySize}
          viewBox="0 0 100 100"
          fill="none"
        >
          {/* 身体渐变定义 */}
          <defs>
            <linearGradient id="vitaBodyGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={colorsV5.mint[400]} />
              <stop offset="100%" stopColor={colorsV5.mint[500]} />
            </linearGradient>
            <filter id="vitaGlow">
              <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
          
          {/* 主体圆形 */}
          <motion.ellipse
            cx="50"
            cy="50"
            rx="38"
            ry="40"
            fill="url(#vitaBodyGradient)"
            filter="url(#vitaGlow)"
          />
          
          {/* 高光 */}
          <ellipse
            cx="38"
            cy="35"
            rx="12"
            ry="8"
            fill="rgba(255, 255, 255, 0.3)"
          />
          
          {/* 左眼 */}
          <motion.g transform="translate(28, 35)">
            <motion.circle
              cx="7"
              cy="7"
              r="6"
              fill={colorsV5.slate[900]}
              animate={expression === 'wink' ? { scaleY: 0.2 } : { scaleY: 1 }}
              transition={{ duration: 0.2 }}
            />
            {expression !== 'wink' && (
              <circle cx="9" cy="5" r="2" fill="white" />
            )}
          </motion.g>
          
          {/* 右眼 */}
          <motion.g transform="translate(55, 35)">
            <motion.circle
              cx="7"
              cy="7"
              r="6"
              fill={colorsV5.slate[900]}
              animate={{ scaleY: 1 }}
            />
            <circle cx="9" cy="5" r="2" fill="white" />
          </motion.g>
          
          {/* 腮红 */}
          {(expression === 'smile' || expression === 'grin' || expression === 'excited') && (
            <>
              <ellipse cx="25" cy="55" rx="6" ry="4" fill="rgba(255, 150, 150, 0.3)" />
              <ellipse cx="75" cy="55" rx="6" ry="4" fill="rgba(255, 150, 150, 0.3)" />
            </>
          )}
          
          {/* 嘴巴 */}
          <motion.path
            d={mouthPath}
            stroke={colorsV5.slate[900]}
            strokeWidth="3"
            strokeLinecap="round"
            fill={expression === 'surprised' || expression === 'grin' || expression === 'excited' ? colorsV5.slate[900] : 'none'}
            transform="translate(35, 30)"
          />
        </svg>
        
        {/* 左手臂 */}
        <motion.div
          className="absolute"
          style={{
            width: 10,
            height: 30,
            background: colorsV5.mint[500],
            borderRadius: 5,
            left: -5,
            top: bodySize * 0.4,
            transformOrigin: 'top center',
          }}
          animate={
            state === 'waving' 
              ? { rotate: [-30, 30, -30] }
              : state === 'celebrating'
              ? { rotate: [-45, 45, -45] }
              : { rotate: 15 }
          }
          transition={{ 
            duration: state === 'waving' || state === 'celebrating' ? 0.5 : 0.3,
            repeat: state === 'waving' || state === 'celebrating' ? Infinity : 0,
          }}
        />
        
        {/* 右手臂 */}
        <motion.div
          className="absolute"
          style={{
            width: 10,
            height: 30,
            background: colorsV5.mint[500],
            borderRadius: 5,
            right: -5,
            top: bodySize * 0.4,
            transformOrigin: 'top center',
          }}
          animate={
            state === 'celebrating'
              ? { rotate: [45, -45, 45] }
              : { rotate: -15 }
          }
          transition={{ 
            duration: 0.5,
            repeat: state === 'celebrating' ? Infinity : 0,
            delay: 0.25,
          }}
        />
      </motion.div>
      
      {/* 配饰 */}
      <AnimatePresence>
        {showAccessory && accessoryType !== 'none' && (
          <motion.div
            className="absolute top-0 left-1/2"
            style={{ x: '-50%' }}
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
          >
            {accessoryType === 'chef-hat' && (
              <div 
                className="w-12 h-10 bg-white rounded-t-full shadow-md"
                style={{ borderBottom: `3px solid ${colorsV5.slate[200]}` }}
              />
            )}
            {accessoryType === 'fitness-band' && (
              <div 
                className="w-8 h-3 rounded-full"
                style={{ background: colorsV5.slate[800] }}
              />
            )}
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* 情绪粒子效果 */}
      <AnimatePresence>
        {(state === 'happy' || state === 'celebrating' || state === 'excited') && (
          <>
            {[...Array(5)].map((_, i) => (
              <motion.div
                key={i}
                className="absolute"
                style={{
                  width: 8,
                  height: 8,
                  background: colorsV5.mint[400],
                  borderRadius: '50%',
                  left: `${30 + Math.random() * 40}%`,
                  top: `${10 + Math.random() * 30}%`,
                }}
                initial={{ opacity: 0, scale: 0 }}
                animate={{ 
                  opacity: [0, 1, 0],
                  scale: [0, 1, 0],
                  y: [-10, -30],
                }}
                transition={{
                  duration: 1,
                  delay: i * 0.1,
                  repeat: Infinity,
                  repeatDelay: 0.5,
                }}
              />
            ))}
          </>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default VitaEvolution
