'use client'

import { useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { colors } from '../../lib/design-tokens'

interface ConfettiPiece {
  id: number
  x: number
  y: number
  rotation: number
  scale: number
  color: string
  speedY: number
  speedX: number
  rotationSpeed: number
}

interface ConfettiProps {
  active?: boolean
  duration?: number
  pieceCount?: number
  onComplete?: () => void
}

/**
 * Confetti 庆祝组件
 * 用于阶段完成、成功等场景
 */
// 常量定义在组件外部
const CONFETTI_COLORS = [
  colors.accent.primary,
  colors.slate[500],
  colors.slate[400],
  '#FFD700', // 金色
  '#FF6B6B', // 粉红
  '#4ECDC4', // 青色
]

export function Confetti({
  active = false,
  duration = 3000,
  pieceCount = 50,
  onComplete
}: ConfettiProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const piecesRef = useRef<ConfettiPiece[]>([])
  const animationRef = useRef<number | undefined>(undefined)

  const createPieces = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return []

    const pieces: ConfettiPiece[] = []
    for (let i = 0; i < pieceCount; i++) {
      pieces.push({
        id: i,
        x: Math.random() * canvas.offsetWidth,
        y: -20 - Math.random() * 100,
        rotation: Math.random() * 360,
        scale: Math.random() * 0.5 + 0.5,
        color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
        speedY: Math.random() * 3 + 2,
        speedX: (Math.random() - 0.5) * 2,
        rotationSpeed: (Math.random() - 0.5) * 10
      })
    }
    return pieces
  }, [pieceCount])

  useEffect(() => {
    if (!active) return

    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // 设置 canvas 尺寸
    canvas.width = canvas.offsetWidth * window.devicePixelRatio
    canvas.height = canvas.offsetHeight * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

    // 创建 confetti
    piecesRef.current = createPieces()

    // 动画开始时间
    const startTime = Date.now()

    // 动画循环
    const animate = () => {
      const elapsed = Date.now() - startTime

      // 检查是否结束
      if (elapsed > duration) {
        ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight)
        if (animationRef.current) {
          cancelAnimationFrame(animationRef.current)
        }
        onComplete?.()
        return
      }

      ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight)

      piecesRef.current.forEach((piece) => {
        // 更新位置
        piece.y += piece.speedY
        piece.x += piece.speedX
        piece.rotation += piece.rotationSpeed

        // 添加重力效果
        piece.speedY += 0.05

        // 绘制 confetti
        ctx.save()
        ctx.translate(piece.x, piece.y)
        ctx.rotate((piece.rotation * Math.PI) / 180)
        ctx.scale(piece.scale, piece.scale)

        // 随机形状
        ctx.fillStyle = piece.color
        if (piece.id % 3 === 0) {
          // 圆形
          ctx.beginPath()
          ctx.arc(0, 0, 5, 0, Math.PI * 2)
          ctx.fill()
        } else if (piece.id % 3 === 1) {
          // 矩形
          ctx.fillRect(-4, -2, 8, 4)
        } else {
          // 三角形
          ctx.beginPath()
          ctx.moveTo(0, -5)
          ctx.lineTo(-4, 5)
          ctx.lineTo(4, 5)
          ctx.closePath()
          ctx.fill()
        }

        ctx.restore()
      })

      animationRef.current = requestAnimationFrame(animate)
    }

    animate()

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [active, duration, createPieces, onComplete])

  if (!active) return null

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none z-50"
    />
  )
}

/**
 * CSS 版本的 Confetti（简化版，性能更好）
 */
export function ConfettiCSS({
  active = false,
  onComplete
}: {
  active?: boolean
  onComplete?: () => void
}) {
  useEffect(() => {
    if (active && onComplete) {
      const timer = setTimeout(onComplete, 2500)
      return () => clearTimeout(timer)
    }
  }, [active, onComplete])

  return (
    <AnimatePresence>
      {active && (
        <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
          {[...Array(30)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-3 h-3 rounded-sm"
              style={{
                left: `${Math.random() * 100}%`,
                backgroundColor: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
              }}
              initial={{
                y: -20,
                x: 0,
                rotate: 0,
                opacity: 1
              }}
              animate={{
                y: window.innerHeight + 50,
                x: (Math.random() - 0.5) * 200,
                rotate: Math.random() * 720,
                opacity: [1, 1, 0]
              }}
              exit={{ opacity: 0 }}
              transition={{
                duration: 2 + Math.random(),
                delay: Math.random() * 0.5,
                ease: 'easeIn'
              }}
            />
          ))}
        </div>
      )}
    </AnimatePresence>
  )
}

/**
 * 徽章解锁动画
 */
interface BadgeUnlockProps {
  show: boolean
  icon?: string
  title: string
  subtitle?: string
  onComplete?: () => void
}

export function BadgeUnlock({
  show,
  icon = '🏆',
  title,
  subtitle,
  onComplete
}: BadgeUnlockProps) {
  useEffect(() => {
    if (show && onComplete) {
      const timer = setTimeout(onComplete, 2000)
      return () => clearTimeout(timer)
    }
  }, [show, onComplete])

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="fixed inset-0 flex items-center justify-center z-50 pointer-events-none"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {/* 背景模糊 */}
          <motion.div
            className="absolute inset-0 bg-black/20 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          
          {/* 徽章 */}
          <motion.div
            className="relative flex flex-col items-center"
            initial={{ scale: 0, rotate: -180 }}
            animate={{ scale: 1, rotate: 0 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{
              type: 'spring',
              stiffness: 200,
              damping: 15
            }}
          >
            {/* 光环 */}
            <motion.div
              className="absolute w-32 h-32 rounded-full"
              style={{
                background: `radial-gradient(circle, ${colors.accent.primary}40, transparent)`
              }}
              animate={{
                scale: [1, 1.5, 1],
                opacity: [0.5, 0, 0.5]
              }}
              transition={{
                duration: 1.5,
                repeat: Infinity,
                ease: 'easeInOut'
              }}
            />
            
            {/* 徽章主体 */}
            <motion.div
              className="w-24 h-24 rounded-full flex items-center justify-center shadow-2xl"
              style={{
                background: `linear-gradient(135deg, ${colors.slate[700]}, ${colors.slate[500]})`,
                boxShadow: `0 0 30px ${colors.slate[600]}50`
              }}
              animate={{
                boxShadow: [
                  `0 0 30px ${colors.slate[600]}50`,
                  `0 0 50px ${colors.slate[600]}70`,
                  `0 0 30px ${colors.slate[600]}50`
                ]
              }}
              transition={{
                duration: 1.5,
                repeat: Infinity,
                ease: 'easeInOut'
              }}
            >
              <span className="text-4xl">{icon}</span>
            </motion.div>
            
            {/* 文字 */}
            <motion.div
              className="mt-4 text-center"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <h3
                className="text-xl font-bold"
                style={{ color: colors.text.inverse }}
              >
                {title}
              </h3>
              {subtitle && (
                <p
                  className="text-sm mt-1"
                  style={{ color: 'rgba(255,255,255,0.8)' }}
                >
                  {subtitle}
                </p>
              )}
            </motion.div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default Confetti
