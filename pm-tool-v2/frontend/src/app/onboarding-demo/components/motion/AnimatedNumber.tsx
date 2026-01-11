'use client'

import { motion, useSpring, useTransform } from 'framer-motion'
import { useEffect, ReactNode } from 'react'
import { numberAnimations } from '../../lib/motion-config'

interface AnimatedNumberProps {
  value: number
  duration?: number
  decimals?: number
  prefix?: string
  suffix?: string
  className?: string
  style?: React.CSSProperties
}

/**
 * 数字动画组件
 * 用于计数器、进度条等数字滚动效果
 */
export function AnimatedNumber({
  value,
  duration = 1.5,
  decimals = 0,
  prefix = '',
  suffix = '',
  className = '',
  style
}: AnimatedNumberProps) {
  const spring = useSpring(0, {
    ...numberAnimations.counter.transition,
    duration
  })

  const display = useTransform(spring, (current) => {
    return current.toFixed(decimals)
  })

  useEffect(() => {
    spring.set(value)
  }, [value, spring])

  return (
    <span className={className} style={style}>
      {prefix}
      <motion.span>{display}</motion.span>
      {suffix}
    </span>
  )
}

/**
 * 进度环组件
 * 用于显示圆形进度
 */
interface ProgressRingProps {
  progress: number // 0-100
  size?: number
  strokeWidth?: number
  color?: string
  className?: string
}

export function ProgressRing({
  progress,
  size = 60,
  strokeWidth = 4,
  color = '#2B2735',
  className = ''
}: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const offset = circumference - (progress / 100) * circumference

  return (
    <div className={`relative ${className}`} style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        className="transform -rotate-90"
      >
        {/* 背景圆环 */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(43, 39, 53, 0.1)"
          strokeWidth={strokeWidth}
          fill="none"
        />
        {/* 进度圆环 */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={numberAnimations.progressRing.transition}
        />
      </svg>
      {/* 中心文字 */}
      <div className="absolute inset-0 flex items-center justify-center">
        <AnimatedNumber
          value={progress}
          decimals={0}
          suffix="%"
          className="text-sm font-semibold"
          style={{ color }}
        />
      </div>
    </div>
  )
}

/**
 * 图表动画包装器
 * 用于体重预测曲线等图表的渐入动画
 */
interface ChartAnimationProps {
  children: ReactNode
  delay?: number
  className?: string
}

export function ChartAnimation({
  children,
  delay = 0,
  className = ''
}: ChartAnimationProps) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.6,
        delay,
        ease: [0.25, 0.46, 0.45, 0.94]
      }}
    >
      {children}
    </motion.div>
  )
}
