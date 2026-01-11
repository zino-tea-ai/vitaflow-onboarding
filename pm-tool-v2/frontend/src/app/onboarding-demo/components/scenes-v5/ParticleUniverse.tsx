'use client'

import React, { useMemo, useCallback } from 'react'
import { motion, useAnimation } from 'framer-motion'
import { colorsV5 } from '../../lib/design-tokens-v5'

export type ParticleMode = 'calm' | 'active' | 'focus' | 'celebrate'

interface ParticleUniverseProps {
  mode?: ParticleMode
  particleCount?: number
  primaryColor?: string
  secondaryColor?: string
  className?: string
  children?: React.ReactNode
}

interface Particle {
  id: number
  x: number
  y: number
  size: number
  opacity: number
  duration: number
  delay: number
  type: 'primary' | 'secondary' | 'accent'
}

export function ParticleUniverse({
  mode = 'calm',
  particleCount = 40,
  primaryColor = colorsV5.mint[500],
  secondaryColor = colorsV5.slate[300],
  className = '',
  children,
}: ParticleUniverseProps) {
  
  // 生成粒子
  const particles = useMemo<Particle[]>(() => {
    const result: Particle[] = []
    
    for (let i = 0; i < particleCount; i++) {
      const type = i % 3 === 0 ? 'primary' : i % 3 === 1 ? 'secondary' : 'accent'
      result.push({
        id: i,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: type === 'primary' ? 4 + Math.random() * 6 : 2 + Math.random() * 4,
        opacity: 0.3 + Math.random() * 0.4,
        duration: 10 + Math.random() * 20,
        delay: Math.random() * 5,
        type,
      })
    }
    
    return result
  }, [particleCount])

  // 获取粒子颜色
  const getParticleColor = useCallback((type: Particle['type']) => {
    switch (type) {
      case 'primary':
        return primaryColor
      case 'secondary':
        return secondaryColor
      case 'accent':
        return colorsV5.mint[300]
      default:
        return primaryColor
    }
  }, [primaryColor, secondaryColor])

  // 获取粒子动画
  const getParticleAnimation = useCallback((particle: Particle) => {
    const baseAnimation = {
      y: [0, -30, 0],
      x: [0, Math.sin(particle.id) * 20, 0],
      opacity: [particle.opacity, particle.opacity * 1.5, particle.opacity],
    }

    switch (mode) {
      case 'calm':
        return {
          ...baseAnimation,
          transition: {
            duration: particle.duration,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: particle.delay,
          },
        }
      case 'active':
        return {
          y: [0, -50, 0],
          x: [0, Math.sin(particle.id) * 40, 0],
          scale: [1, 1.3, 1],
          opacity: [particle.opacity, 1, particle.opacity],
          transition: {
            duration: particle.duration * 0.6,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: particle.delay * 0.5,
          },
        }
      case 'focus':
        // 粒子向中心聚集
        return {
          x: [particle.x, 50, particle.x],
          y: [particle.y, 50, particle.y],
          scale: [1, 0.5, 1],
          opacity: [particle.opacity, 1, particle.opacity],
          transition: {
            duration: 3,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: particle.delay * 0.3,
          },
        }
      case 'celebrate':
        // 爆发效果
        return {
          scale: [1, 2, 1],
          opacity: [particle.opacity, 1, 0],
          y: [0, -100 - Math.random() * 100, 0],
          x: [0, (Math.random() - 0.5) * 200, 0],
          transition: {
            duration: 2,
            repeat: Infinity,
            ease: 'easeOut',
            delay: particle.delay * 0.2,
          },
        }
      default:
        return baseAnimation
    }
  }, [mode])

  // 中心光晕动画
  const getCenterGlowAnimation = () => {
    switch (mode) {
      case 'calm':
        return {
          scale: [1, 1.1, 1],
          opacity: [0.2, 0.3, 0.2],
        }
      case 'active':
        return {
          scale: [1, 1.3, 1],
          opacity: [0.3, 0.5, 0.3],
        }
      case 'focus':
        return {
          scale: [1.5, 1.8, 1.5],
          opacity: [0.4, 0.6, 0.4],
        }
      case 'celebrate':
        return {
          scale: [1, 2, 1],
          opacity: [0.3, 0.8, 0.3],
        }
      default:
        return {}
    }
  }

  return (
    <div 
      className={`absolute inset-0 overflow-hidden ${className}`}
      style={{ 
        background: `linear-gradient(180deg, ${colorsV5.slate[50]} 0%, ${colorsV5.slate[100]} 100%)`,
      }}
    >
      {/* 中心光晕 */}
      <motion.div
        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          width: '60%',
          paddingBottom: '60%',
          background: `radial-gradient(circle, ${primaryColor}20 0%, transparent 70%)`,
          filter: 'blur(40px)',
        }}
        animate={getCenterGlowAnimation()}
        transition={{
          duration: mode === 'celebrate' ? 1 : 4,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* 次级光晕 */}
      <motion.div
        className="absolute left-1/4 top-1/3 rounded-full"
        style={{
          width: '30%',
          paddingBottom: '30%',
          background: `radial-gradient(circle, ${secondaryColor}15 0%, transparent 70%)`,
          filter: 'blur(30px)',
        }}
        animate={{
          x: [0, 30, 0],
          y: [0, -20, 0],
          scale: [1, 1.2, 1],
        }}
        transition={{
          duration: 8,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* 粒子层 */}
      {particles.map((particle) => (
        <motion.div
          key={particle.id}
          className="absolute rounded-full"
          style={{
            left: `${particle.x}%`,
            top: `${particle.y}%`,
            width: particle.size,
            height: particle.size,
            background: getParticleColor(particle.type),
            boxShadow: particle.type === 'primary' 
              ? `0 0 ${particle.size * 2}px ${primaryColor}60`
              : 'none',
          }}
          animate={getParticleAnimation(particle)}
        />
      ))}

      {/* 连接线 - Focus 模式 */}
      {mode === 'focus' && (
        <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.1 }}>
          {particles.slice(0, 10).map((p, i) => (
            <motion.line
              key={`line-${i}`}
              x1={`${p.x}%`}
              y1={`${p.y}%`}
              x2="50%"
              y2="50%"
              stroke={primaryColor}
              strokeWidth="1"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: [0, 1, 0] }}
              transition={{
                duration: 3,
                repeat: Infinity,
                delay: i * 0.2,
              }}
            />
          ))}
        </svg>
      )}

      {/* 脉冲环 - Active/Celebrate 模式 */}
      {(mode === 'active' || mode === 'celebrate') && (
        <>
          {[0, 1, 2].map((i) => (
            <motion.div
              key={`pulse-${i}`}
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
              style={{
                width: 100,
                height: 100,
                border: `2px solid ${primaryColor}`,
              }}
              initial={{ scale: 0.5, opacity: 0.5 }}
              animate={{
                scale: [0.5, 3],
                opacity: [0.5, 0],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                delay: i * 0.6,
                ease: 'easeOut',
              }}
            />
          ))}
        </>
      )}

      {/* 网格纹理 - 科技感 */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `
            linear-gradient(${colorsV5.slate[300]}08 1px, transparent 1px),
            linear-gradient(90deg, ${colorsV5.slate[300]}08 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
        }}
      />

      {/* 内容 */}
      {children}
    </div>
  )
}

export default ParticleUniverse
