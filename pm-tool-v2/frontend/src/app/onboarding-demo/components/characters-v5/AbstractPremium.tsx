'use client'

import React, { useMemo } from 'react'
import { motion } from 'framer-motion'
import { colorsV5, easingsV5 } from '../../lib/design-tokens-v5'

export type AbstractState = 
  | 'idle' 
  | 'active' 
  | 'thinking' 
  | 'success' 
  | 'celebrating'

interface AbstractPremiumProps {
  state?: AbstractState
  size?: 'sm' | 'md' | 'lg' | 'xl'
  intensity?: 'subtle' | 'medium' | 'dramatic'
  className?: string
}

const sizeMap = {
  sm: 100,
  md: 150,
  lg: 200,
  xl: 280,
}

export function AbstractPremium({
  state = 'idle',
  size = 'lg',
  intensity = 'medium',
  className = '',
}: AbstractPremiumProps) {
  const baseSize = sizeMap[size]
  
  // 根据强度调整动画参数
  const intensityMultiplier = intensity === 'subtle' ? 0.5 : intensity === 'dramatic' ? 1.5 : 1
  
  // 生成流体 blob 路径
  const blobPaths = useMemo(() => {
    const paths = [
      'M50 10 C70 10 90 30 90 50 C90 70 70 90 50 90 C30 90 10 70 10 50 C10 30 30 10 50 10',
      'M50 15 C65 10 85 25 90 45 C95 65 75 85 55 90 C35 95 15 75 10 55 C5 35 25 15 50 15',
      'M45 12 C68 8 88 28 92 48 C96 68 78 88 52 92 C32 96 12 78 8 52 C4 32 28 12 45 12',
    ]
    return paths
  }, [])

  // 获取动画配置
  const getAnimation = () => {
    const baseFloating = {
      y: [0, -10 * intensityMultiplier, 0],
      transition: {
        duration: 4,
        repeat: Infinity,
        ease: 'easeInOut' as const,
      },
    }

    switch (state) {
      case 'idle':
        return baseFloating
      case 'active':
        return {
          ...baseFloating,
          scale: [1, 1.05, 1],
          transition: {
            duration: 2,
            repeat: Infinity,
            ease: 'easeInOut' as const,
          },
        }
      case 'thinking':
        return {
          rotate: [0, 5, -5, 0],
          scale: [1, 0.98, 1.02, 1],
          transition: {
            duration: 3,
            repeat: Infinity,
            ease: 'easeInOut' as const,
          },
        }
      case 'success':
        return {
          scale: [1, 1.15, 1],
          transition: {
            duration: 0.6,
            ease: [0.34, 1.56, 0.64, 1] as const,
          },
        }
      case 'celebrating':
        return {
          scale: [1, 1.2, 0.95, 1.1, 1],
          rotate: [0, -10, 10, -5, 0],
          transition: {
            duration: 0.8,
            ease: [0.34, 1.56, 0.64, 1] as const,
          },
        }
      default:
        return baseFloating
    }
  }

  // 粒子配置
  const particles = useMemo(() => {
    const count = intensity === 'subtle' ? 8 : intensity === 'dramatic' ? 20 : 12
    return Array.from({ length: count }, (_, i) => ({
      id: i,
      x: Math.cos((i / count) * Math.PI * 2) * (baseSize * 0.5 + Math.random() * 20),
      y: Math.sin((i / count) * Math.PI * 2) * (baseSize * 0.5 + Math.random() * 20),
      size: 3 + Math.random() * 5,
      delay: i * 0.1,
      duration: 3 + Math.random() * 2,
    }))
  }, [baseSize, intensity])

  return (
    <motion.div
      className={`relative ${className}`}
      style={{
        width: baseSize,
        height: baseSize,
      }}
      animate={getAnimation()}
    >
      {/* 外层光晕 */}
      <motion.div
        className="absolute inset-0"
        style={{
          background: `radial-gradient(circle, ${colorsV5.mint[500]}20 0%, transparent 70%)`,
          borderRadius: '50%',
          filter: 'blur(20px)',
        }}
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* 主体 - 流体形态 */}
      <svg
        viewBox="0 0 100 100"
        className="absolute inset-0 w-full h-full"
      >
        <defs>
          {/* 主渐变 */}
          <linearGradient id="abstractGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={colorsV5.mint[400]} />
            <stop offset="50%" stopColor={colorsV5.mint[500]} />
            <stop offset="100%" stopColor="#34D399" />
          </linearGradient>
          
          {/* 高光渐变 */}
          <radialGradient id="abstractHighlight" cx="30%" cy="30%" r="50%">
            <stop offset="0%" stopColor="rgba(255, 255, 255, 0.4)" />
            <stop offset="100%" stopColor="rgba(255, 255, 255, 0)" />
          </radialGradient>
          
          {/* 模糊滤镜 */}
          <filter id="abstractGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* 噪点纹理 */}
          <filter id="noise">
            <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="4" result="noise" />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="2" />
          </filter>
        </defs>
        
        {/* 背景 blob - 动画路径 */}
        <motion.path
          d={blobPaths[0]}
          fill="url(#abstractGradient)"
          filter="url(#abstractGlow)"
          animate={{
            d: blobPaths,
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
        
        {/* 高光层 */}
        <motion.ellipse
          cx="35"
          cy="35"
          rx="20"
          ry="15"
          fill="url(#abstractHighlight)"
          animate={{
            rx: [20, 22, 20],
            ry: [15, 17, 15],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
        
        {/* 内部光点 */}
        <motion.circle
          cx="50"
          cy="50"
          r="8"
          fill="rgba(255, 255, 255, 0.6)"
          animate={{
            r: [8, 10, 8],
            opacity: [0.6, 0.8, 0.6],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      </svg>

      {/* 环绕粒子 */}
      {particles.map((particle) => (
        <motion.div
          key={particle.id}
          className="absolute rounded-full"
          style={{
            width: particle.size,
            height: particle.size,
            background: colorsV5.mint[400],
            left: '50%',
            top: '50%',
            boxShadow: `0 0 ${particle.size * 2}px ${colorsV5.mint.glow}`,
          }}
          animate={{
            x: [particle.x * 0.8, particle.x, particle.x * 0.8],
            y: [particle.y * 0.8, particle.y, particle.y * 0.8],
            opacity: [0.3, 0.7, 0.3],
            scale: [0.8, 1.2, 0.8],
          }}
          transition={{
            duration: particle.duration,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: particle.delay,
          }}
        />
      ))}

      {/* 脉冲环 - 活跃状态 */}
      {(state === 'active' || state === 'success' || state === 'celebrating') && (
        <>
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="absolute inset-0 rounded-full"
              style={{
                border: `2px solid ${colorsV5.mint[500]}`,
              }}
              initial={{ scale: 1, opacity: 0.5 }}
              animate={{
                scale: [1, 1.5 + i * 0.2],
                opacity: [0.5, 0],
              }}
              transition={{
                duration: 1.5,
                repeat: Infinity,
                delay: i * 0.3,
                ease: 'easeOut',
              }}
            />
          ))}
        </>
      )}

      {/* 庆祝粒子爆发 */}
      {state === 'celebrating' && (
        <>
          {[...Array(12)].map((_, i) => (
            <motion.div
              key={`burst-${i}`}
              className="absolute rounded-full"
              style={{
                width: 6,
                height: 6,
                background: i % 2 === 0 ? colorsV5.mint[500] : colorsV5.mint[300],
                left: '50%',
                top: '50%',
              }}
              initial={{ x: 0, y: 0, opacity: 1 }}
              animate={{
                x: Math.cos((i / 12) * Math.PI * 2) * 100,
                y: Math.sin((i / 12) * Math.PI * 2) * 100,
                opacity: 0,
                scale: [1, 0],
              }}
              transition={{
                duration: 0.8,
                ease: 'easeOut',
              }}
            />
          ))}
        </>
      )}
    </motion.div>
  )
}

export default AbstractPremium
