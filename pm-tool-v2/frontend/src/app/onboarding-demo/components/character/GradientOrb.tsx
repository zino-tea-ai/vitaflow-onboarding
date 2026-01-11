'use client'

import { motion, useAnimation, useMotionValue, useTransform, animate } from 'framer-motion'
import { useEffect, useState, useRef } from 'react'
import { colors } from '../../lib/design-tokens'
import { MascotState } from './index'

/**
 * VitaFlow 球体角色 - 真正的 3 层叠加动画系统
 * 
 * 核心理念：每层动画独立运行，通过 transform 叠加
 * - Layer 1 (Life): 永远运行，不会被打断
 * - Layer 2 (Emotion): 平滑过渡的情感状态
 * - Layer 3 (Action): 一次性动作，叠加而非替换
 */

interface GradientOrbProps {
  state?: MascotState
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
}

const sizeMap = {
  sm: 56,
  md: 72,
  lg: 96,
  xl: 128,
}

// ============ 情感配置 ============
interface EmotionConfig {
  eyeScaleY: number
  eyeScaleX: number
  eyeOffsetY: number
  eyeLookX: number      // 眼睛看向的 X 方向
  pupilSize: number     // 瞳孔大小比例
  showBlush: boolean
  showSparkle: boolean
  glowIntensity: number // 光晕强度
  tiltAngle: number     // 歪头角度
}

const emotionConfigs: Record<string, EmotionConfig> = {
  neutral: {
    eyeScaleY: 1, eyeScaleX: 1, eyeOffsetY: 0, eyeLookX: 0,
    pupilSize: 1, showBlush: false, showSparkle: false, glowIntensity: 0.6, tiltAngle: 0
  },
  happy: {
    // 普通开心 - 不脸红，只是光晕稍强
    eyeScaleY: 1, eyeScaleX: 1, eyeOffsetY: 0, eyeLookX: 0,
    pupilSize: 1, showBlush: false, showSparkle: false, glowIntensity: 0.75, tiltAngle: 0
  },
  curious: {
    eyeScaleY: 1.15, eyeScaleX: 1.1, eyeOffsetY: -1, eyeLookX: 2,
    pupilSize: 1.1, showBlush: false, showSparkle: false, glowIntensity: 0.7, tiltAngle: 6
  },
  thinking: {
    eyeScaleY: 0.95, eyeScaleX: 1, eyeOffsetY: -2, eyeLookX: -2,
    pupilSize: 0.9, showBlush: false, showSparkle: false, glowIntensity: 0.5, tiltAngle: -4
  },
  surprised: {
    eyeScaleY: 1.4, eyeScaleX: 1.3, eyeOffsetY: -2, eyeLookX: 0,
    pupilSize: 0.75, showBlush: false, showSparkle: false, glowIntensity: 0.9, tiltAngle: 0
  },
  proud: {
    // proud - 不脸红
    eyeScaleY: 1, eyeScaleX: 1, eyeOffsetY: 0, eyeLookX: 0,
    pupilSize: 1, showBlush: false, showSparkle: false, glowIntensity: 0.8, tiltAngle: 2
  },
  excited: {
    // 只有 excited/celebrating 才脸红 - 特别开心的时刻
    eyeScaleY: 1, eyeScaleX: 1, eyeOffsetY: 0, eyeLookX: 0,
    pupilSize: 1, showBlush: true, showSparkle: true, glowIntensity: 1, tiltAngle: 0
  },
}

// 状态到情感的映射
function getEmotionFromState(state: MascotState): string {
  switch (state) {
    // 只有庆祝时才用 excited（会脸红）
    case 'celebrating':
    case 'cheering':
    case 'excited':
      return 'excited'
    // 普通开心状态 - 不脸红
    case 'happy':
    case 'greeting':
    case 'waving':
    case 'encouraging':
      return 'happy'
    case 'listening':
      return 'curious'
    case 'thinking':
      return 'thinking'
    case 'surprised':
      return 'surprised'
    case 'proud':
    case 'explaining':
      return 'proud'
    default:
      return 'neutral'
  }
}

// 判断是否有动作
function getActionFromState(state: MascotState): string | null {
  switch (state) {
    case 'greeting':
    case 'waving':
      return 'wave'
    case 'celebrating':
    case 'cheering':
      return 'bounce'
    case 'encouraging':
      return 'nod'
    case 'explaining':
      return 'talk'
    case 'thinking':
      return 'sway'
    default:
      return null
  }
}

export function GradientOrb({ 
  state = 'idle', 
  size = 'md',
  className = '' 
}: GradientOrbProps) {
  const s = sizeMap[size]
  const eyeWidth = s * 0.09
  const eyeHeight = s * 0.24
  const eyeGap = s * 0.26
  const eyeBaseY = s * 0.36
  
  // ============ Layer 1: 基础生命 (永远运行) ============
  
  // 呼吸 - 使用 motion value 实现持续动画
  const breatheY = useMotionValue(0)
  const breatheScale = useMotionValue(1)
  
  useEffect(() => {
    // 呼吸动画 - 轻柔自然
    const breatheAnimation = animate(breatheY, [0, -2.5, 0], {
      duration: 2.8,
      repeat: Infinity,
      ease: 'easeInOut',
    })
    const scaleAnimation = animate(breatheScale, [1, 1.02, 1], {
      duration: 2.8,
      repeat: Infinity,
      ease: 'easeInOut',
    })
    return () => {
      breatheAnimation.stop()
      scaleAnimation.stop()
    }
  }, [breatheY, breatheScale])
  
  
  // 微小随机漂移
  const driftX = useMotionValue(0)
  const driftRotate = useMotionValue(0)
  
  useEffect(() => {
    // 随机漂移 - 轻微自然
    const driftXAnim = animate(driftX, [0, 1, -1, 0.5, 0], {
      duration: 7,
      repeat: Infinity,
      ease: 'easeInOut',
    })
    const driftRotateAnim = animate(driftRotate, [0, 1.5, -1.5, 1, 0], {
      duration: 6,
      repeat: Infinity,
      ease: 'easeInOut',
    })
    return () => {
      driftXAnim.stop()
      driftRotateAnim.stop()
    }
  }, [driftX, driftRotate])
  
  // 眼睛偶尔四处看
  const [lookDirection, setLookDirection] = useState({ x: 0, y: 0 })
  
  useEffect(() => {
    const lookAround = () => {
      const delay = 4000 + Math.random() * 5000
      setTimeout(() => {
        // 随机看一个方向
        const directions = [
          { x: 0, y: 0 },    // 正前
          { x: 2, y: 0 },    // 右
          { x: -2, y: 0 },   // 左
          { x: 0, y: -1 },   // 上
          { x: 1, y: -1 },   // 右上
        ]
        const dir = directions[Math.floor(Math.random() * directions.length)]
        setLookDirection(dir)
        // 1.5秒后恢复
        setTimeout(() => setLookDirection({ x: 0, y: 0 }), 1500)
        lookAround()
      }, delay)
    }
    lookAround()
  }, [])
  
  // ============ Layer 2: 情感状态 (平滑过渡) ============
  const emotion = getEmotionFromState(state)
  const config = emotionConfigs[emotion] || emotionConfigs.neutral
  
  // 使用 motion values 实现平滑过渡
  const emotionEyeScaleY = useMotionValue(config.eyeScaleY)
  const emotionEyeScaleX = useMotionValue(config.eyeScaleX)
  const emotionEyeOffsetY = useMotionValue(config.eyeOffsetY)
  const emotionTilt = useMotionValue(config.tiltAngle)
  const emotionGlow = useMotionValue(config.glowIntensity)
  
  useEffect(() => {
    // 平滑过渡到新的情感状态
    animate(emotionEyeScaleY, config.eyeScaleY, { duration: 0.4, ease: 'easeOut' })
    animate(emotionEyeScaleX, config.eyeScaleX, { duration: 0.4, ease: 'easeOut' })
    animate(emotionEyeOffsetY, config.eyeOffsetY, { duration: 0.3, ease: 'easeOut' })
    animate(emotionTilt, config.tiltAngle, { duration: 0.5, ease: 'easeOut' })
    animate(emotionGlow, config.glowIntensity, { duration: 0.6, ease: 'easeOut' })
  }, [emotion, config, emotionEyeScaleY, emotionEyeScaleX, emotionEyeOffsetY, emotionTilt, emotionGlow])
  
  // ============ Layer 3: 特殊动作 (叠加) ============
  const actionY = useMotionValue(0)
  const actionScale = useMotionValue(1)
  const actionRotate = useMotionValue(0)
  
  const action = getActionFromState(state)
  const actionRef = useRef<string | null>(null)
  
  useEffect(() => {
    if (action === actionRef.current) return
    actionRef.current = action
    
    if (!action) {
      // 恢复到默认
      animate(actionY, 0, { duration: 0.3 })
      animate(actionScale, 1, { duration: 0.3 })
      animate(actionRotate, 0, { duration: 0.3 })
      return
    }
    
    const playAction = async () => {
      switch (action) {
        case 'wave':
          // 左右摇摆 - 轻柔
          const waveAnim = animate(actionRotate, [0, 6, -6, 4, -4, 2, 0], {
            duration: 1.2,
            ease: 'easeInOut',
          })
          const waveY = animate(actionY, [0, -2, -1, -2, -1, -2, 0], {
            duration: 1.2,
            ease: 'easeInOut',
          })
          await Promise.all([waveAnim, waveY])
          break
          
        case 'bounce':
          // 弹跳庆祝 - 轻柔
          for (let i = 0; i < 2; i++) {
            await animate(actionY, [0, -6, 1, -3, 0], {
              duration: 0.45,
              ease: 'easeOut',
            })
            await animate(actionScale, [1, 1.05, 0.98, 1.02, 1], {
              duration: 0.45,
              ease: 'easeOut',
            })
          }
          break
          
        case 'nod':
          // 点头 - 轻柔
          for (let i = 0; i < 2; i++) {
            await animate(actionY, [0, 2, -1, 0], {
              duration: 0.35,
              ease: 'easeInOut',
            })
          }
          break
          
        case 'talk':
          // 说话 - 轻微起伏
          const talkLoop = () => {
            animate(actionScale, [1, 1.02, 1, 1.01, 1], {
              duration: 1.2,
              ease: 'easeInOut',
              onComplete: () => {
                if (actionRef.current === 'talk') talkLoop()
              }
            })
            animate(actionY, [0, -1, 0, -0.5, 0], {
              duration: 1.2,
              ease: 'easeInOut',
            })
          }
          talkLoop()
          return
          
        case 'sway':
          // 思考时左右摇摆 - 轻柔
          const swayLoop = () => {
            animate(actionRotate, [0, 2, -2, 1, -1, 0], {
              duration: 3.5,
              ease: 'easeInOut',
              onComplete: () => {
                if (actionRef.current === 'sway') swayLoop()
              }
            })
          }
          swayLoop()
          return
      }
    }
    
    playAction()
  }, [action, actionY, actionScale, actionRotate])
  
  // ============ 合并所有层的变换 ============
  // Layer 1 + Layer 2 + Layer 3 叠加
  const combinedY = useTransform([breatheY, actionY], ([b, a]) => (b as number) + (a as number))
  const combinedScale = useTransform([breatheScale, actionScale], ([b, a]) => (b as number) * (a as number))
  const combinedRotate = useTransform(
    [driftRotate, emotionTilt, actionRotate], 
    ([d, e, a]) => (d as number) + (e as number) + (a as number)
  )
  
  // ============ 眼睛动态系统 ============
  // 统一使用自然眨眼，所有状态都一样
  const [blinkPhase, setBlinkPhase] = useState(0) // 0-3: open, closing, closed, opening
  const blinkRef = useRef<NodeJS.Timeout | null>(null)
  
  useEffect(() => {
    // 眨眼动画：2.5-5秒随机间隔
    const scheduleBlink = () => {
      const delay = 2500 + Math.random() * 2500
      blinkRef.current = setTimeout(() => {
        // 眨眼序列：open -> closing -> closed -> opening -> open
        setBlinkPhase(1) // closing
        setTimeout(() => setBlinkPhase(2), 60)  // closed
        setTimeout(() => setBlinkPhase(3), 120) // opening
        setTimeout(() => setBlinkPhase(0), 200) // open
        scheduleBlink()
      }, delay)
    }
    
    scheduleBlink()
    return () => {
      if (blinkRef.current) clearTimeout(blinkRef.current)
    }
  }, [])
  
  // 根据眨眼阶段和情感计算眼睛 scaleY
  const getEyeScaleY = () => {
    // 眨眼时的缩放
    const blinkScales = [1, 0.3, 0.05, 0.5]
    const blinkScale = blinkScales[blinkPhase]
    
    // 基础眼睛大小来自情感配置
    return config.eyeScaleY * blinkScale
  }
  
  // 眼睛 scaleX 直接使用配置
  const getEyeScaleX = () => config.eyeScaleX
  
  // 边框粗细
  const borderWidth = size === 'sm' ? 2 : size === 'md' ? 2.5 : size === 'lg' ? 3 : 3.5
  
  return (
    <motion.div
      className={`relative ${className}`}
      style={{ 
        width: s, 
        height: s,
        y: combinedY,
        scale: combinedScale,
        rotate: combinedRotate,
        x: driftX,
      }}
    >
      {/* 外层光晕 - 响应情感 */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          background: `radial-gradient(circle, ${colors.accent.primary}25 0%, transparent 65%)`,
          filter: 'blur(12px)',
          scale: 1.3,
          opacity: emotionGlow,
        }}
        animate={{
          scale: [1.25, 1.35, 1.25],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />
      
      {/* 兴奋时的额外粒子 */}
      {config.showSparkle && (
        <>
          {[...Array(4)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute rounded-full"
              style={{
                width: 4,
                height: 4,
                background: colors.accent.primary,
                top: `${20 + i * 15}%`,
                left: i % 2 === 0 ? '-8%' : '104%',
              }}
              animate={{
                y: [0, -10, 0],
                opacity: [0, 1, 0],
                scale: [0.5, 1.2, 0.5],
              }}
              transition={{
                duration: 1.5,
                repeat: Infinity,
                delay: i * 0.3,
                ease: 'easeInOut',
              }}
            />
          ))}
        </>
      )}

      {/* 主球体 */}
      <div
        className="relative w-full h-full rounded-full overflow-hidden"
        style={{
          background: colors.white,
          border: `${borderWidth}px solid ${colors.accent.primary}`,
          boxShadow: `
            0 4px 12px ${colors.slate[200]},
            0 8px 24px ${colors.slate[100]},
            inset 0 3px 6px ${colors.white},
            inset 0 -6px 12px ${colors.slate[50]}
          `,
        }}
      >
        {/* 顶部高光 */}
        <motion.div
          className="absolute"
          style={{
            width: s * 0.45,
            height: s * 0.2,
            left: s * 0.18,
            top: s * 0.1,
            background: `linear-gradient(180deg, rgba(255,255,255,0.95) 0%, transparent 100%)`,
            borderRadius: '50%',
          }}
          animate={{
            opacity: [0.85, 0.95, 0.85],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />

        {/* 左眼 */}
        <motion.div
          className="absolute rounded-full"
          style={{
            width: eyeWidth,
            height: eyeHeight,
            left: s / 2 - eyeGap / 2 - eyeWidth / 2 + config.eyeLookX + lookDirection.x,
            top: eyeBaseY + lookDirection.y,
            background: colors.slate[800],
            transformOrigin: 'center',
          }}
          animate={{
            scaleX: getEyeScaleX(),
            scaleY: getEyeScaleY(),
            y: config.eyeOffsetY,
          }}
          transition={{ 
            duration: emotion === 'happy' ? 0.15 : 0.08,
            ease: 'easeOut',
          }}
        />

        {/* 右眼 */}
        <motion.div
          className="absolute rounded-full"
          style={{
            width: eyeWidth,
            height: eyeHeight,
            left: s / 2 + eyeGap / 2 - eyeWidth / 2 + config.eyeLookX + lookDirection.x,
            top: eyeBaseY + lookDirection.y,
            background: colors.slate[800],
            transformOrigin: 'center',
          }}
          animate={{
            scaleX: getEyeScaleX(),
            scaleY: getEyeScaleY(),
            y: config.eyeOffsetY,
          }}
          transition={{ 
            duration: emotion === 'happy' ? 0.15 : 0.08,
            ease: 'easeOut',
          }}
        />

        {/* 腮红 */}
        <motion.div
          className="absolute rounded-full"
          style={{
            width: s * 0.14,
            height: s * 0.07,
            left: s * 0.08,
            top: s * 0.54,
            background: 'linear-gradient(90deg, #FFB5B5, #FFD4D4)',
            filter: 'blur(1px)',
          }}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ 
            scale: config.showBlush ? 1 : 0, 
            opacity: config.showBlush ? 0.7 : 0 
          }}
          transition={{ type: 'spring', stiffness: 300, damping: 20 }}
        />
        <motion.div
          className="absolute rounded-full"
          style={{
            width: s * 0.14,
            height: s * 0.07,
            right: s * 0.08,
            top: s * 0.54,
            background: 'linear-gradient(90deg, #FFD4D4, #FFB5B5)',
            filter: 'blur(1px)',
          }}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ 
            scale: config.showBlush ? 1 : 0, 
            opacity: config.showBlush ? 0.7 : 0 
          }}
          transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.05 }}
        />
        
        {/* 思考气泡 */}
        {emotion === 'thinking' && (
          <>
            <motion.div
              className="absolute rounded-full"
              style={{
                width: s * 0.06,
                height: s * 0.06,
                right: -s * 0.02,
                top: s * 0.2,
                background: colors.slate[200],
              }}
              animate={{ 
                scale: [0, 1, 1, 0],
                opacity: [0, 0.8, 0.8, 0],
              }}
              transition={{ 
                duration: 2.5,
                repeat: Infinity,
                times: [0, 0.15, 0.85, 1],
              }}
            />
            <motion.div
              className="absolute rounded-full"
              style={{
                width: s * 0.04,
                height: s * 0.04,
                right: -s * 0.06,
                top: s * 0.08,
                background: colors.slate[300],
              }}
              animate={{ 
                scale: [0, 1, 1, 0],
                opacity: [0, 0.6, 0.6, 0],
              }}
              transition={{ 
                duration: 2.5,
                repeat: Infinity,
                times: [0, 0.2, 0.8, 1],
                delay: 0.3,
              }}
            />
          </>
        )}
      </div>
    </motion.div>
  )
}

export default GradientOrb
