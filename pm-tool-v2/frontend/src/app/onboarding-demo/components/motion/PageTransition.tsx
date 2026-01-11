'use client'

import { motion, HTMLMotionProps } from 'framer-motion'
import { ReactNode } from 'react'
import { pageTransitions } from '../../lib/motion-config'

interface PageTransitionProps {
  children: ReactNode
  direction?: 'forward' | 'backward'
  className?: string
}

/**
 * 页面过渡组件
 * iOS 原生感的 Slide + Fade 组合
 */
export function PageTransition({
  children,
  direction = 'forward',
  className = ''
}: PageTransitionProps) {
  const transition = direction === 'forward' 
    ? pageTransitions.forward 
    : pageTransitions.backward

  return (
    <motion.div
      className={className}
      initial={transition.initial}
      animate={transition.animate}
      exit={transition.exit}
      transition={transition.transition}
      style={{
        willChange: 'transform, opacity',
        backfaceVisibility: 'hidden',
        transform: 'translateZ(0)' // GPU 加速
      }}
    >
      {children}
    </motion.div>
  )
}

/**
 * 页面容器组件
 * 自动应用过渡动画
 */
export function PageContainer({
  children,
  direction = 'forward',
  ...props
}: PageTransitionProps & Omit<HTMLMotionProps<'div'>, 'children'>) {
  return (
    <PageTransition direction={direction} {...props}>
      {children}
    </PageTransition>
  )
}
