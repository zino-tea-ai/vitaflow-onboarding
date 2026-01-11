'use client'

import React, { useMemo } from 'react'
import { motion } from 'framer-motion'
import { colorsV5 } from '../../lib/design-tokens-v5'

export type NatureTheme = 'fresh' | 'tropical' | 'minimal' | 'garden'

interface NatureElementsProps {
  theme?: NatureTheme
  density?: 'sparse' | 'normal' | 'dense'
  animated?: boolean
  className?: string
  children?: React.ReactNode
}

// 主题配置
const themeConfigs = {
  fresh: {
    bg: `linear-gradient(180deg, ${colorsV5.slate[50]} 0%, #ECFDF5 100%)`,
    leafColor: colorsV5.mint[500],
    accentColor: colorsV5.mint[300],
  },
  tropical: {
    bg: `linear-gradient(180deg, #ECFDF5 0%, #D1FAE5 100%)`,
    leafColor: '#22C55E',
    accentColor: '#86EFAC',
  },
  minimal: {
    bg: `linear-gradient(180deg, ${colorsV5.slate[50]} 0%, ${colorsV5.slate[100]} 100%)`,
    leafColor: colorsV5.slate[400],
    accentColor: colorsV5.slate[300],
  },
  garden: {
    bg: `linear-gradient(180deg, #FEF9C3 0%, #ECFDF5 100%)`,
    leafColor: '#16A34A',
    accentColor: '#4ADE80',
  },
}

// 叶子 SVG 路径
const leafPaths = [
  'M 0 20 Q 10 0 20 20 Q 10 25 0 20', // 简单叶子
  'M 0 30 Q 15 0 30 30 Q 20 35 10 35 Q 0 35 0 30', // 宽叶
  'M 5 0 Q 0 15 5 30 Q 10 15 5 0', // 细长叶
]

export function NatureElements({
  theme = 'fresh',
  density = 'normal',
  animated = true,
  className = '',
  children,
}: NatureElementsProps) {
  const config = themeConfigs[theme]
  
  // 生成植物元素
  const elements = useMemo(() => {
    const count = density === 'sparse' ? 6 : density === 'dense' ? 16 : 10
    const result = []
    
    for (let i = 0; i < count; i++) {
      const isLeft = i % 2 === 0
      result.push({
        id: i,
        x: isLeft ? -5 + Math.random() * 25 : 75 + Math.random() * 25,
        y: 50 + Math.random() * 45,
        scale: 0.6 + Math.random() * 0.8,
        rotation: isLeft ? -20 + Math.random() * 40 : 140 + Math.random() * 40,
        pathIndex: Math.floor(Math.random() * leafPaths.length),
        delay: i * 0.2,
      })
    }
    
    return result
  }, [density])

  // 装饰圆点
  const decorDots = useMemo(() => {
    const count = density === 'sparse' ? 10 : density === 'dense' ? 30 : 18
    return Array.from({ length: count }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 70,
      size: 4 + Math.random() * 8,
      opacity: 0.1 + Math.random() * 0.2,
      duration: 5 + Math.random() * 10,
    }))
  }, [density])

  return (
    <div 
      className={`absolute inset-0 overflow-hidden ${className}`}
      style={{ background: config.bg }}
    >
      {/* 顶部装饰弧线 */}
      <svg
        className="absolute top-0 left-0 w-full"
        viewBox="0 0 400 100"
        preserveAspectRatio="none"
        style={{ height: '15%' }}
      >
        <motion.path
          d="M 0 100 Q 100 20 200 60 Q 300 100 400 50 L 400 0 L 0 0 Z"
          fill={`${config.leafColor}10`}
          animate={animated ? {
            d: [
              'M 0 100 Q 100 20 200 60 Q 300 100 400 50 L 400 0 L 0 0 Z',
              'M 0 100 Q 100 40 200 40 Q 300 80 400 60 L 400 0 L 0 0 Z',
              'M 0 100 Q 100 20 200 60 Q 300 100 400 50 L 400 0 L 0 0 Z',
            ],
          } : {}}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      </svg>

      {/* 装饰圆点 */}
      {decorDots.map((dot) => (
        <motion.div
          key={`dot-${dot.id}`}
          className="absolute rounded-full"
          style={{
            left: `${dot.x}%`,
            top: `${dot.y}%`,
            width: dot.size,
            height: dot.size,
            background: config.leafColor,
            opacity: dot.opacity,
          }}
          animate={animated ? {
            y: [0, -15, 0],
            opacity: [dot.opacity, dot.opacity * 1.5, dot.opacity],
          } : {}}
          transition={{
            duration: dot.duration,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: dot.id * 0.1,
          }}
        />
      ))}

      {/* 植物/叶子元素 */}
      {elements.map((el) => (
        <motion.div
          key={el.id}
          className="absolute"
          style={{
            left: `${el.x}%`,
            top: `${el.y}%`,
            transformOrigin: 'bottom center',
          }}
          animate={animated ? {
            rotate: [el.rotation - 5, el.rotation + 5, el.rotation - 5],
          } : { rotate: el.rotation }}
          transition={{
            duration: 3 + el.delay,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: el.delay,
          }}
        >
          <svg
            width={40 * el.scale}
            height={50 * el.scale}
            viewBox="0 0 40 50"
          >
            {/* 茎 */}
            <motion.path
              d="M 20 50 Q 20 30 20 15"
              stroke={config.leafColor}
              strokeWidth="3"
              fill="none"
              strokeLinecap="round"
            />
            {/* 叶子 */}
            <motion.path
              d={leafPaths[el.pathIndex]}
              fill={config.leafColor}
              transform="translate(10, 5)"
              animate={animated ? {
                scale: [1, 1.05, 1],
              } : {}}
              transition={{
                duration: 2,
                repeat: Infinity,
                delay: el.delay * 0.5,
              }}
            />
            {/* 叶子高光 */}
            <ellipse
              cx="20"
              cy="15"
              rx="5"
              ry="8"
              fill={`${config.accentColor}40`}
            />
          </svg>
        </motion.div>
      ))}

      {/* 底部地面装饰 */}
      <div
        className="absolute bottom-0 left-0 right-0"
        style={{
          height: '20%',
          background: `linear-gradient(180deg, transparent 0%, ${config.leafColor}08 100%)`,
        }}
      />

      {/* 底部草地波浪 */}
      <svg
        className="absolute bottom-0 left-0 w-full"
        viewBox="0 0 400 60"
        preserveAspectRatio="none"
        style={{ height: '8%' }}
      >
        <motion.path
          d="M 0 60 L 0 30 Q 50 20 100 30 Q 150 40 200 30 Q 250 20 300 30 Q 350 40 400 30 L 400 60 Z"
          fill={`${config.leafColor}15`}
          animate={animated ? {
            d: [
              'M 0 60 L 0 30 Q 50 20 100 30 Q 150 40 200 30 Q 250 20 300 30 Q 350 40 400 30 L 400 60 Z',
              'M 0 60 L 0 35 Q 50 25 100 35 Q 150 45 200 35 Q 250 25 300 35 Q 350 45 400 35 L 400 60 Z',
              'M 0 60 L 0 30 Q 50 20 100 30 Q 150 40 200 30 Q 250 20 300 30 Q 350 40 400 30 L 400 60 Z',
            ],
          } : {}}
          transition={{
            duration: 6,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      </svg>

      {/* 蝴蝶/装饰元素 - 仅在 tropical 和 garden 主题 */}
      {(theme === 'tropical' || theme === 'garden') && animated && (
        <>
          {[0, 1].map((i) => (
            <motion.div
              key={`butterfly-${i}`}
              className="absolute"
              style={{
                left: i === 0 ? '20%' : '70%',
                top: '30%',
              }}
              animate={{
                x: [0, 50, 0, -30, 0],
                y: [0, -30, -50, -20, 0],
              }}
              transition={{
                duration: 8,
                repeat: Infinity,
                delay: i * 3,
                ease: 'easeInOut',
              }}
            >
              <svg width="24" height="20" viewBox="0 0 24 20">
                {/* 蝴蝶翅膀 */}
                <motion.ellipse
                  cx="6"
                  cy="10"
                  rx="6"
                  ry="8"
                  fill={config.accentColor}
                  animate={{
                    scaleX: [1, 0.3, 1],
                  }}
                  transition={{
                    duration: 0.3,
                    repeat: Infinity,
                  }}
                />
                <motion.ellipse
                  cx="18"
                  cy="10"
                  rx="6"
                  ry="8"
                  fill={config.accentColor}
                  animate={{
                    scaleX: [1, 0.3, 1],
                  }}
                  transition={{
                    duration: 0.3,
                    repeat: Infinity,
                  }}
                />
                <ellipse cx="12" cy="10" rx="2" ry="6" fill={config.leafColor} />
              </svg>
            </motion.div>
          ))}
        </>
      )}

      {/* 内容 */}
      {children}
    </div>
  )
}

export default NatureElements
