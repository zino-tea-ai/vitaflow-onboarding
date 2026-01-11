'use client'

import React, { useMemo } from 'react'
import { motion } from 'framer-motion'
import { colorsV5 } from '../../lib/design-tokens-v5'

export type TimeOfDay = 'dawn' | 'morning' | 'noon' | 'afternoon' | 'dusk' | 'night'

interface GradientFlowProps {
  progress?: number  // 0-100, 用于根据进度改变时间
  timeOfDay?: TimeOfDay
  className?: string
  animated?: boolean
  children?: React.ReactNode
}

// 时间对应的渐变配色
const timeGradients: Record<TimeOfDay, { bg: string; accent: string; overlay: string }> = {
  dawn: {
    bg: 'linear-gradient(180deg, #FEF3C7 0%, #FDE68A 30%, #FBBF24 100%)',
    accent: '#F59E0B',
    overlay: 'rgba(251, 191, 36, 0.1)',
  },
  morning: {
    bg: 'linear-gradient(180deg, #E0F2FE 0%, #BAE6FD 40%, #7DD3FC 100%)',
    accent: '#0EA5E9',
    overlay: 'rgba(14, 165, 233, 0.1)',
  },
  noon: {
    bg: 'linear-gradient(180deg, #F0FDF4 0%, #DCFCE7 40%, #BBF7D0 100%)',
    accent: '#22C55E',
    overlay: 'rgba(34, 197, 94, 0.1)',
  },
  afternoon: {
    bg: 'linear-gradient(180deg, #FEF9C3 0%, #FEF08A 40%, #FDE047 100%)',
    accent: '#EAB308',
    overlay: 'rgba(234, 179, 8, 0.1)',
  },
  dusk: {
    bg: 'linear-gradient(180deg, #FED7AA 0%, #FDBA74 40%, #FB923C 100%)',
    accent: '#F97316',
    overlay: 'rgba(249, 115, 22, 0.1)',
  },
  night: {
    bg: 'linear-gradient(180deg, #1E293B 0%, #0F172A 100%)',
    accent: '#61E0BD',
    overlay: 'rgba(97, 224, 189, 0.05)',
  },
}

// 根据进度计算时间
const getTimeFromProgress = (progress: number): TimeOfDay => {
  if (progress < 15) return 'dawn'
  if (progress < 35) return 'morning'
  if (progress < 55) return 'noon'
  if (progress < 75) return 'afternoon'
  if (progress < 90) return 'dusk'
  return 'night'
}

export function GradientFlow({
  progress = 0,
  timeOfDay,
  className = '',
  animated = true,
  children,
}: GradientFlowProps) {
  const currentTime = timeOfDay || getTimeFromProgress(progress)
  const gradient = timeGradients[currentTime]

  // 装饰元素
  const decorativeElements = useMemo(() => {
    const elements = []
    const count = currentTime === 'night' ? 20 : 8
    
    for (let i = 0; i < count; i++) {
      elements.push({
        id: i,
        x: Math.random() * 100,
        y: Math.random() * 60,
        size: currentTime === 'night' ? 2 + Math.random() * 2 : 20 + Math.random() * 40,
        opacity: currentTime === 'night' ? 0.5 + Math.random() * 0.5 : 0.3 + Math.random() * 0.3,
        duration: 10 + Math.random() * 20,
      })
    }
    return elements
  }, [currentTime])

  return (
    <div 
      className={`absolute inset-0 overflow-hidden ${className}`}
      style={{ background: gradient.bg }}
    >
      {/* 渐变叠加层 - 动画 */}
      {animated && (
        <motion.div
          className="absolute inset-0"
          style={{
            background: `radial-gradient(ellipse 80% 50% at 50% 0%, ${gradient.overlay}, transparent)`,
          }}
          animate={{
            opacity: [0.5, 0.8, 0.5],
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      )}

      {/* 装饰圆形/星星 */}
      {decorativeElements.map((el) => (
        <motion.div
          key={el.id}
          className="absolute rounded-full"
          style={{
            left: `${el.x}%`,
            top: `${el.y}%`,
            width: el.size,
            height: el.size,
            background: currentTime === 'night' 
              ? 'white' 
              : `radial-gradient(circle, white 0%, transparent 70%)`,
            opacity: el.opacity,
          }}
          animate={animated ? {
            y: [0, -20, 0],
            opacity: [el.opacity, el.opacity * 1.5, el.opacity],
            scale: currentTime === 'night' ? [1, 1.2, 1] : [1, 1.1, 1],
          } : {}}
          transition={{
            duration: el.duration,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: el.id * 0.5,
          }}
        />
      ))}

      {/* 太阳/月亮 */}
      {currentTime !== 'night' && (
        <motion.div
          className="absolute"
          style={{
            right: '15%',
            top: currentTime === 'dawn' ? '60%' : currentTime === 'dusk' ? '50%' : '20%',
            width: 60,
            height: 60,
            background: currentTime === 'dusk' 
              ? 'linear-gradient(135deg, #FBBF24 0%, #F97316 100%)'
              : 'linear-gradient(135deg, #FEF3C7 0%, #FBBF24 100%)',
            borderRadius: '50%',
            boxShadow: `0 0 60px ${currentTime === 'dusk' ? '#F97316' : '#FBBF24'}40`,
          }}
          animate={animated ? {
            y: [0, -10, 0],
            scale: [1, 1.05, 1],
          } : {}}
          transition={{
            duration: 6,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      )}

      {/* 月亮 - 夜间 */}
      {currentTime === 'night' && (
        <motion.div
          className="absolute"
          style={{
            right: '20%',
            top: '15%',
            width: 50,
            height: 50,
            background: 'linear-gradient(135deg, #F1F5F9 0%, #E2E8F0 100%)',
            borderRadius: '50%',
            boxShadow: `0 0 40px rgba(241, 245, 249, 0.3)`,
          }}
          animate={animated ? {
            opacity: [0.8, 1, 0.8],
          } : {}}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      )}

      {/* 云朵 - 白天 */}
      {currentTime !== 'night' && (
        <>
          <motion.div
            className="absolute"
            style={{
              left: '10%',
              top: '25%',
              width: 80,
              height: 30,
              background: 'rgba(255, 255, 255, 0.8)',
              borderRadius: 20,
              filter: 'blur(1px)',
            }}
            animate={animated ? {
              x: [0, 20, 0],
            } : {}}
            transition={{
              duration: 20,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          >
            <div
              className="absolute"
              style={{
                left: '20%',
                top: '-50%',
                width: 35,
                height: 35,
                background: 'rgba(255, 255, 255, 0.8)',
                borderRadius: '50%',
              }}
            />
            <div
              className="absolute"
              style={{
                left: '45%',
                top: '-80%',
                width: 45,
                height: 45,
                background: 'rgba(255, 255, 255, 0.8)',
                borderRadius: '50%',
              }}
            />
          </motion.div>

          <motion.div
            className="absolute"
            style={{
              right: '30%',
              top: '35%',
              width: 60,
              height: 22,
              background: 'rgba(255, 255, 255, 0.6)',
              borderRadius: 15,
              filter: 'blur(1px)',
            }}
            animate={animated ? {
              x: [0, -15, 0],
            } : {}}
            transition={{
              duration: 25,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          >
            <div
              className="absolute"
              style={{
                left: '25%',
                top: '-60%',
                width: 28,
                height: 28,
                background: 'rgba(255, 255, 255, 0.6)',
                borderRadius: '50%',
              }}
            />
          </motion.div>
        </>
      )}

      {/* 地面渐变 */}
      <div
        className="absolute bottom-0 left-0 right-0"
        style={{
          height: '30%',
          background: currentTime === 'night'
            ? 'linear-gradient(180deg, transparent 0%, rgba(15, 23, 42, 0.3) 100%)'
            : 'linear-gradient(180deg, transparent 0%, rgba(255, 255, 255, 0.2) 100%)',
        }}
      />

      {/* 内容 */}
      {children}
    </div>
  )
}

export default GradientFlow
