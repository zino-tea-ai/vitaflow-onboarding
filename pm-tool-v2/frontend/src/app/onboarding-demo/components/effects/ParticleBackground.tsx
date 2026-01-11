'use client'

import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { colors } from '../../lib/design-tokens'

interface Particle {
  x: number
  y: number
  size: number
  speedX: number
  speedY: number
  opacity: number
}

interface ParticleBackgroundProps {
  particleCount?: number
  color?: string
  className?: string
  gradient?: boolean
}

/**
 * 粒子背景组件
 * 用于 Launch 页面的品牌动画
 */
export function ParticleBackground({
  particleCount = 30,
  color = colors.accent.primary,
  className = '',
  gradient = true
}: ParticleBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const particlesRef = useRef<Particle[]>([])
  const animationRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // 设置 canvas 尺寸
    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio
      canvas.height = canvas.offsetHeight * window.devicePixelRatio
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
    }
    resizeCanvas()
    window.addEventListener('resize', resizeCanvas)

    // 初始化粒子
    const initParticles = () => {
      particlesRef.current = []
      for (let i = 0; i < particleCount; i++) {
        particlesRef.current.push({
          x: Math.random() * canvas.offsetWidth,
          y: Math.random() * canvas.offsetHeight,
          size: Math.random() * 3 + 1,
          speedX: (Math.random() - 0.5) * 0.5,
          speedY: (Math.random() - 0.5) * 0.5,
          opacity: Math.random() * 0.5 + 0.2
        })
      }
    }
    initParticles()

    // 动画循环
    const animate = () => {
      ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight)

      particlesRef.current.forEach((particle) => {
        // 更新位置
        particle.x += particle.speedX
        particle.y += particle.speedY

        // 边界处理
        if (particle.x < 0) particle.x = canvas.offsetWidth
        if (particle.x > canvas.offsetWidth) particle.x = 0
        if (particle.y < 0) particle.y = canvas.offsetHeight
        if (particle.y > canvas.offsetHeight) particle.y = 0

        // 绘制粒子
        ctx.beginPath()
        ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2)
        ctx.fillStyle = color.replace(')', `, ${particle.opacity})`).replace('rgb', 'rgba')
        
        // 如果是 hex 颜色，转换为 rgba
        if (color.startsWith('#')) {
          const r = parseInt(color.slice(1, 3), 16)
          const g = parseInt(color.slice(3, 5), 16)
          const b = parseInt(color.slice(5, 7), 16)
          ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${particle.opacity})`
        }
        
        ctx.fill()
      })

      animationRef.current = requestAnimationFrame(animate)
    }
    animate()

    return () => {
      window.removeEventListener('resize', resizeCanvas)
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [particleCount, color])

  return (
    <div className={`absolute inset-0 overflow-hidden ${className}`}>
      {/* 渐变背景 */}
      {gradient && (
        <motion.div
          className="absolute inset-0"
          style={{
            background: colors.primary.gradient
          }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1 }}
        />
      )}
      
      {/* 粒子 Canvas */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ mixBlendMode: 'screen' }}
      />
      
      {/* 额外的光晕效果 */}
      <motion.div
        className="absolute top-1/4 left-1/2 w-64 h-64 -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl"
        style={{
          background: `radial-gradient(circle, ${colors.accent.primary}20, transparent)`
        }}
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.5, 0.3]
        }}
        transition={{
          duration: 4,
          repeat: Infinity,
          ease: 'easeInOut'
        }}
      />
      
      <motion.div
        className="absolute bottom-1/4 right-1/4 w-48 h-48 rounded-full blur-3xl"
        style={{
          background: `radial-gradient(circle, ${colors.slate[600]}15, transparent)`
        }}
        animate={{
          scale: [1, 1.3, 1],
          opacity: [0.2, 0.4, 0.2]
        }}
        transition={{
          duration: 5,
          repeat: Infinity,
          ease: 'easeInOut',
          delay: 1
        }}
      />
    </div>
  )
}

/**
 * 简化版粒子背景（纯 CSS，性能更好）
 */
export function ParticleBackgroundSimple({
  className = ''
}: {
  className?: string
}) {
  return (
    <div className={`absolute inset-0 overflow-hidden ${className}`}>
      {/* 渐变背景 */}
      <div
        className="absolute inset-0"
        style={{
          background: colors.primary.gradient
        }}
      />
      
      {/* 浮动圆圈 */}
      {[...Array(6)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: 60 + i * 20,
            height: 60 + i * 20,
            left: `${(i * 17) % 100}%`,
            top: `${(i * 23) % 100}%`,
            background: i % 2 === 0 
              ? `radial-gradient(circle, ${colors.accent.primary}15, transparent)`
              : `radial-gradient(circle, ${colors.slate[600]}10, transparent)`,
            filter: 'blur(20px)'
          }}
          animate={{
            x: [0, 30 * (i % 2 === 0 ? 1 : -1), 0],
            y: [0, 20 * (i % 2 === 0 ? -1 : 1), 0],
            scale: [1, 1.1, 1],
            opacity: [0.3, 0.6, 0.3]
          }}
          transition={{
            duration: 4 + i * 0.5,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: i * 0.3
          }}
        />
      ))}
    </div>
  )
}

export default ParticleBackground
