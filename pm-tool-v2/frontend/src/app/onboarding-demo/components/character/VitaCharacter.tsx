'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { colors } from '../../lib/design-tokens'

export type MascotState = 
  | 'idle'        // 默认等待，眨眼 + 微浮动
  | 'greeting'    // 开场白挥手
  | 'listening'   // 等待用户输入
  | 'thinking'    // 处理中
  | 'explaining'  // 讲解价值点
  | 'happy'       // 开心
  | 'excited'     // 兴奋
  | 'encouraging' // 鼓励
  | 'proud'       // 展示结果时骄傲
  | 'celebrating' // 里程碑庆祝
  | 'surprised'   // 惊讶
  | 'waving'      // 挥手
  | 'cheering'    // 欢呼
  // 兼容旧状态名
  | 'neutral'

interface VitaCharacterProps {
  state?: MascotState
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
  className?: string
  /** 是否显示挥手动画的手臂 */
  showArm?: boolean
}

/**
 * Vita 角色 2.0
 * 绿色萌芽/叶子造型的拟人角色
 * 
 * 特性：
 * - 永远有 idle 微动（呼吸感）
 * - 眨眼动画
 * - 丰富的表情系统
 * - 平滑状态切换
 */
export function VitaCharacter({ 
  state = 'idle', 
  size = 'md',
  className = '',
  showArm = false
}: VitaCharacterProps) {
  // 兼容旧状态名
  const normalizedState = state === 'neutral' ? 'idle' : state
  
  // 眨眼状态
  const [isBlinking, setIsBlinking] = useState(false)
  
  // 定时眨眼
  useEffect(() => {
    const blinkInterval = setInterval(() => {
      setIsBlinking(true)
      setTimeout(() => setIsBlinking(false), 150)
    }, 3000 + Math.random() * 2000) // 3-5秒随机眨眼
    
    return () => clearInterval(blinkInterval)
  }, [])
  
  // 尺寸配置
  const sizeMap = {
    xs: 40,
    sm: 56,
    md: 72,
    lg: 96,
    xl: 120,
  }
  
  const s = sizeMap[size]
  
  // 状态配置
  type EyeStyle = 'normal' | 'happy' | 'star' | 'dot' | 'wide' | 'closed' | 'wink'
  type MouthStyle = 'neutral' | 'smile' | 'open' | 'o' | 'wave' | 'grin' | 'proud'
  type Accessory = 'none' | 'sparkle' | 'heart' | 'question' | 'exclamation' | 'sweat' | 'confetti'
  
  interface StateConfig {
    eyeStyle: EyeStyle
    mouthStyle: MouthStyle
    bodyAnimation?: { y?: number[]; scale?: number[]; rotate?: number[]; transition?: { duration?: number; repeat?: number; ease?: string } }
    accessory?: Accessory
    armAnimation?: { rotate?: number[]; transition?: { duration?: number; repeat?: number; ease?: string } }
  }
  
  const stateConfig: Record<MascotState, StateConfig> = {
    neutral: { eyeStyle: 'normal', mouthStyle: 'neutral' },
    
    idle: {
      eyeStyle: 'normal',
      mouthStyle: 'smile',
      bodyAnimation: { 
        y: [0, -3, 0], 
        transition: { duration: 2, repeat: Infinity, ease: 'easeInOut' } 
      }
    },
    
    greeting: {
      eyeStyle: 'happy',
      mouthStyle: 'grin',
      bodyAnimation: { 
        rotate: [-5, 5, -5, 0], 
        transition: { duration: 0.8, ease: 'easeInOut' } 
      },
      armAnimation: {
        rotate: [0, -20, 20, -20, 20, 0],
        transition: { duration: 1.2, ease: 'easeInOut' }
      }
    },
    
    listening: {
      eyeStyle: 'normal',
      mouthStyle: 'neutral',
      bodyAnimation: { 
        rotate: [0, 3, 0], 
        transition: { duration: 1.5, repeat: Infinity, ease: 'easeInOut' } 
      }
    },
    
    thinking: {
      eyeStyle: 'dot',
      mouthStyle: 'wave',
      bodyAnimation: { 
        rotate: [-3, 3, -3, 0], 
        transition: { duration: 2, repeat: Infinity, ease: 'easeInOut' } 
      },
      accessory: 'question'
    },
    
    explaining: {
      eyeStyle: 'normal',
      mouthStyle: 'open',
      bodyAnimation: { 
        scale: [1, 1.02, 1], 
        transition: { duration: 0.8, repeat: Infinity, ease: 'easeInOut' } 
      }
    },
    
    happy: {
      eyeStyle: 'happy',
      mouthStyle: 'smile',
      bodyAnimation: { 
        scale: [1, 1.05, 1], 
        transition: { duration: 0.4, ease: 'easeInOut' } 
      },
      accessory: 'sparkle'
    },
    
    excited: {
      eyeStyle: 'star',
      mouthStyle: 'grin',
      bodyAnimation: { 
        y: [0, -8, 0], 
        transition: { duration: 0.4, ease: 'easeOut' } 
      },
      accessory: 'sparkle'
    },
    
    encouraging: {
      eyeStyle: 'happy',
      mouthStyle: 'smile',
      bodyAnimation: { 
        scale: [1, 1.08, 1], 
        transition: { duration: 0.5, ease: 'easeInOut' } 
      },
      accessory: 'heart'
    },
    
    proud: {
      eyeStyle: 'happy',
      mouthStyle: 'proud',
      bodyAnimation: { 
        scale: [1, 1.1, 1.05], 
        transition: { duration: 0.6, ease: 'easeOut' } 
      },
      accessory: 'sparkle'
    },
    
    celebrating: {
      eyeStyle: 'star',
      mouthStyle: 'grin',
      bodyAnimation: { 
        y: [0, -12, 0], 
        rotate: [-5, 5, -5, 5, 0],
        scale: [1, 1.15, 1],
        transition: { duration: 0.8, ease: 'easeOut' } 
      },
      accessory: 'confetti'
    },
    
    surprised: {
      eyeStyle: 'wide',
      mouthStyle: 'o',
      bodyAnimation: { 
        scale: [1, 1.15, 1.08], 
        transition: { duration: 0.3, ease: 'easeOut' } 
      },
      accessory: 'exclamation'
    },
    
    waving: {
      eyeStyle: 'happy',
      mouthStyle: 'smile',
      bodyAnimation: { 
        rotate: [-8, 8, -8, 0], 
        transition: { duration: 0.6, ease: 'easeInOut' } 
      }
    },
    
    cheering: {
      eyeStyle: 'star',
      mouthStyle: 'grin',
      bodyAnimation: { 
        y: [0, -10, 0], 
        scale: [1, 1.1, 1], 
        transition: { duration: 0.4, ease: 'easeOut' } 
      },
      accessory: 'sparkle'
    },
  }
  
  const config = stateConfig[normalizedState] || stateConfig.idle
  
  // ============ 眼睛渲染 ============
  const renderEyes = () => {
    // 眨眼时显示闭眼
    if (isBlinking && config.eyeStyle !== 'star' && config.eyeStyle !== 'wide') {
      return renderClosedEyes()
    }
    
    const eyeSize = s * 0.09
    const eyeY = s * 0.38
    const eyeSpacing = s * 0.22
    
    switch (config.eyeStyle) {
      case 'happy':
        return (
          <>
            <motion.div 
              className="absolute bg-[#2B2735]"
              style={{ 
                width: eyeSize * 1.3, 
                height: eyeSize * 0.4,
                left: `calc(50% - ${eyeSpacing / 2 + eyeSize * 0.6}px)`,
                top: eyeY,
                borderRadius: '0 0 100px 100px',
              }}
              initial={{ scaleY: 0 }}
              animate={{ scaleY: 1 }}
              transition={{ duration: 0.2 }}
            />
            <motion.div 
              className="absolute bg-[#2B2735]"
              style={{ 
                width: eyeSize * 1.3, 
                height: eyeSize * 0.4,
                left: `calc(50% + ${eyeSpacing / 2 - eyeSize * 0.6}px)`,
                top: eyeY,
                borderRadius: '0 0 100px 100px',
              }}
              initial={{ scaleY: 0 }}
              animate={{ scaleY: 1 }}
              transition={{ duration: 0.2 }}
            />
          </>
        )
        
      case 'star':
        return (
          <>
            <motion.span 
              className="absolute"
              style={{ 
                fontSize: eyeSize * 1.8,
                left: `calc(50% - ${eyeSpacing / 2 + eyeSize}px)`,
                top: eyeY - eyeSize * 0.5,
                color: '#FFD700',
              }}
              animate={{ 
                scale: [1, 1.2, 1],
                rotate: [0, 10, 0],
              }}
              transition={{ duration: 0.6, repeat: Infinity }}
            >
              ★
            </motion.span>
            <motion.span 
              className="absolute"
              style={{ 
                fontSize: eyeSize * 1.8,
                left: `calc(50% + ${eyeSpacing / 2 - eyeSize * 0.8}px)`,
                top: eyeY - eyeSize * 0.5,
                color: '#FFD700',
              }}
              animate={{ 
                scale: [1, 1.2, 1],
                rotate: [0, -10, 0],
              }}
              transition={{ duration: 0.6, repeat: Infinity, delay: 0.1 }}
            >
              ★
            </motion.span>
          </>
        )
        
      case 'dot':
        return (
          <>
            <motion.div 
              className="absolute rounded-full bg-[#2B2735]"
              style={{ 
                width: eyeSize * 0.5, 
                height: eyeSize * 0.5,
                left: `calc(50% - ${eyeSpacing / 2 + eyeSize * 0.2}px)`,
                top: eyeY + eyeSize * 0.2,
              }}
              animate={{ x: [0, 2, 0] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <motion.div 
              className="absolute rounded-full bg-[#2B2735]"
              style={{ 
                width: eyeSize * 0.5, 
                height: eyeSize * 0.5,
                left: `calc(50% + ${eyeSpacing / 2 - eyeSize * 0.2}px)`,
                top: eyeY + eyeSize * 0.2,
              }}
              animate={{ x: [0, 2, 0] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
          </>
        )
        
      case 'wide':
        return (
          <>
            <motion.div 
              className="absolute rounded-full bg-white border-2 border-[#2B2735]"
              style={{ 
                width: eyeSize * 1.6, 
                height: eyeSize * 1.6,
                left: `calc(50% - ${eyeSpacing / 2 + eyeSize * 0.8}px)`,
                top: eyeY - eyeSize * 0.3,
              }}
              initial={{ scale: 0.5 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.2, type: 'spring' }}
            >
              <div 
                className="absolute rounded-full bg-[#2B2735]"
                style={{
                  width: eyeSize * 0.8,
                  height: eyeSize * 0.8,
                  top: '50%',
                  left: '50%',
                  transform: 'translate(-50%, -50%)',
                }}
              />
            </motion.div>
            <motion.div 
              className="absolute rounded-full bg-white border-2 border-[#2B2735]"
              style={{ 
                width: eyeSize * 1.6, 
                height: eyeSize * 1.6,
                left: `calc(50% + ${eyeSpacing / 2 - eyeSize * 0.8}px)`,
                top: eyeY - eyeSize * 0.3,
              }}
              initial={{ scale: 0.5 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.2, type: 'spring' }}
            >
              <div 
                className="absolute rounded-full bg-[#2B2735]"
                style={{
                  width: eyeSize * 0.8,
                  height: eyeSize * 0.8,
                  top: '50%',
                  left: '50%',
                  transform: 'translate(-50%, -50%)',
                }}
              />
            </motion.div>
          </>
        )
        
      default: // normal
        return (
          <>
            <motion.div 
              className="absolute rounded-full bg-[#2B2735]"
              style={{ 
                width: eyeSize, 
                height: eyeSize,
                left: `calc(50% - ${eyeSpacing / 2 + eyeSize * 0.5}px)`,
                top: eyeY,
              }}
            />
            <motion.div 
              className="absolute rounded-full bg-[#2B2735]"
              style={{ 
                width: eyeSize, 
                height: eyeSize,
                left: `calc(50% + ${eyeSpacing / 2 - eyeSize * 0.5}px)`,
                top: eyeY,
              }}
            />
          </>
        )
    }
  }
  
  // 闭眼状态
  const renderClosedEyes = () => {
    const eyeSize = s * 0.09
    const eyeY = s * 0.4
    const eyeSpacing = s * 0.22
    
    return (
      <>
        <motion.div 
          className="absolute bg-[#2B2735]"
          style={{ 
            width: eyeSize * 1.2, 
            height: 2,
            left: `calc(50% - ${eyeSpacing / 2 + eyeSize * 0.6}px)`,
            top: eyeY,
            borderRadius: 1,
          }}
        />
        <motion.div 
          className="absolute bg-[#2B2735]"
          style={{ 
            width: eyeSize * 1.2, 
            height: 2,
            left: `calc(50% + ${eyeSpacing / 2 - eyeSize * 0.6}px)`,
            top: eyeY,
            borderRadius: 1,
          }}
        />
      </>
    )
  }
  
  // ============ 嘴巴渲染 ============
  const renderMouth = () => {
    const mouthY = s * 0.55
    const mouthSize = s * 0.12
    
    switch (config.mouthStyle) {
      case 'smile':
        return (
          <motion.div 
            className="absolute"
            style={{ 
              width: mouthSize * 1.2, 
              height: mouthSize * 0.6,
              left: '50%',
              top: mouthY,
              transform: 'translateX(-50%)',
              borderRadius: '0 0 100px 100px',
              border: '2.5px solid #2B2735',
              borderTop: 'none',
            }}
          />
        )
        
      case 'grin':
        return (
          <motion.div 
            className="absolute bg-[#2B2735]"
            style={{ 
              width: mouthSize * 1.5, 
              height: mouthSize * 0.8,
              left: '50%',
              top: mouthY,
              transform: 'translateX(-50%)',
              borderRadius: '0 0 100px 100px',
            }}
          >
            {/* 舌头 */}
            <div 
              className="absolute bg-pink-400"
              style={{
                width: mouthSize * 0.6,
                height: mouthSize * 0.4,
                bottom: 2,
                left: '50%',
                transform: 'translateX(-50%)',
                borderRadius: '0 0 50px 50px',
              }}
            />
          </motion.div>
        )
        
      case 'open':
        return (
          <motion.div 
            className="absolute rounded-full bg-[#2B2735]"
            style={{ 
              width: mouthSize, 
              height: mouthSize * 0.8,
              left: '50%',
              top: mouthY,
              transform: 'translateX(-50%)',
            }}
            animate={{ 
              scaleY: [1, 0.8, 1],
            }}
            transition={{ duration: 0.5, repeat: Infinity }}
          />
        )
        
      case 'o':
        return (
          <motion.div 
            className="absolute rounded-full border-2 border-[#2B2735]"
            style={{ 
              width: mouthSize * 0.8, 
              height: mouthSize * 0.8,
              left: '50%',
              top: mouthY,
              transform: 'translateX(-50%)',
            }}
          />
        )
        
      case 'wave':
        return (
          <motion.div 
            className="absolute text-[#2B2735] font-bold"
            style={{ 
              fontSize: mouthSize,
              left: '50%',
              top: mouthY - mouthSize * 0.2,
              transform: 'translateX(-50%)',
            }}
          >
            ~
          </motion.div>
        )
        
      case 'proud':
        return (
          <motion.div 
            className="absolute"
            style={{ 
              width: mouthSize * 1.4, 
              height: mouthSize * 0.5,
              left: '50%',
              top: mouthY,
              transform: 'translateX(-50%)',
              borderRadius: '0 0 100px 100px',
              background: '#2B2735',
            }}
          />
        )
        
      default: // neutral
        return (
          <motion.div 
            className="absolute bg-[#2B2735]"
            style={{ 
              width: mouthSize * 0.8, 
              height: 2.5,
              left: '50%',
              top: mouthY,
              transform: 'translateX(-50%)',
              borderRadius: 2,
            }}
          />
        )
    }
  }
  
  // ============ 配饰渲染 ============
  const renderAccessory = () => {
    const accessory = config.accessory || 'none'
    
    switch (accessory) {
      case 'sparkle':
        return (
          <>
            <motion.span 
              className="absolute text-yellow-400"
              style={{ fontSize: s * 0.18, top: 0, right: 0 }}
              animate={{ opacity: [0, 1, 0], scale: [0.5, 1.2, 0.5], rotate: [0, 180, 360] }}
              transition={{ duration: 1, repeat: Infinity }}
            >
              ✦
            </motion.span>
            <motion.span 
              className="absolute text-yellow-300"
              style={{ fontSize: s * 0.12, top: s * 0.15, right: s * 0.2 }}
              animate={{ opacity: [0, 1, 0], scale: [0.5, 1, 0.5] }}
              transition={{ duration: 0.8, repeat: Infinity, delay: 0.3 }}
            >
              ✦
            </motion.span>
          </>
        )
        
      case 'heart':
        return (
          <motion.span 
            className="absolute text-pink-500"
            style={{ fontSize: s * 0.2, top: -s * 0.05, right: -s * 0.05 }}
            animate={{ 
              scale: [1, 1.3, 1],
              y: [0, -5, 0],
            }}
            transition={{ duration: 0.8, repeat: Infinity }}
          >
            ❤️
          </motion.span>
        )
        
      case 'question':
        return (
          <motion.span 
            className="absolute text-[#2B2735]"
            style={{ fontSize: s * 0.25, top: -s * 0.1, right: -s * 0.05 }}
            animate={{ 
              y: [0, -3, 0],
              rotate: [-5, 5, -5],
            }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            ?
          </motion.span>
        )
        
      case 'exclamation':
        return (
          <motion.span 
            className="absolute text-red-500"
            style={{ fontSize: s * 0.25, top: -s * 0.1, right: -s * 0.05 }}
            animate={{ scale: [1, 1.3, 1] }}
            transition={{ duration: 0.3, repeat: 3 }}
          >
            !
          </motion.span>
        )
        
      case 'confetti':
        return (
          <>
            {[...Array(6)].map((_, i) => (
              <motion.span 
                key={i}
                className="absolute"
                style={{ 
                  fontSize: s * 0.12, 
                  top: -s * 0.1 - i * 3,
                  left: `${20 + i * 12}%`,
                }}
                animate={{ 
                  y: [0, s * 0.5],
                  opacity: [1, 0],
                  rotate: [0, 360],
                }}
                transition={{ 
                  duration: 1.5, 
                  repeat: Infinity, 
                  delay: i * 0.1 
                }}
              >
                {['🎊', '✨', '🎉', '⭐', '💫', '🌟'][i]}
              </motion.span>
            ))}
          </>
        )
        
      default:
        return null
    }
  }
  
  // ============ 手臂渲染（用于挥手） ============
  const renderArm = () => {
    if (!showArm && normalizedState !== 'greeting') return null
    
    return (
      <motion.div
        className="absolute"
        style={{
          width: s * 0.2,
          height: s * 0.35,
          right: -s * 0.1,
          top: s * 0.5,
          background: colors.accent.primary,
          borderRadius: s * 0.1,
          transformOrigin: 'top center',
        }}
        animate={(config.armAnimation || { rotate: [0, -15, 15, -15, 0] }) as any}
        transition={{ duration: 1, repeat: normalizedState === 'greeting' ? 2 : 0, ease: 'easeInOut' }}
      />
    )
  }
  
  return (
    <motion.div
      className={`relative ${className}`}
      style={{ width: s, height: s * 1.1 }}
      animate={config.bodyAnimation as any}
      initial={{ scale: 0.9, opacity: 0 }}
      whileInView={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {/* 身体 - 萌芽/叶子形状 */}
      <motion.div
        className="absolute"
        style={{
          width: s * 0.85,
          height: s * 0.85,
          left: '50%',
          top: s * 0.15,
          transform: 'translateX(-50%)',
          background: `linear-gradient(135deg, ${colors.accent.primary}, ${colors.accent.light || colors.accent.primary})`,
          borderRadius: '50% 50% 45% 45%',
          boxShadow: `0 8px 24px ${colors.accent.primary}40`,
        }}
      />
      
      {/* 头顶小叶子 */}
      <motion.div
        className="absolute"
        style={{
          width: s * 0.18,
          height: s * 0.22,
          left: '50%',
          top: s * 0.02,
          transform: 'translateX(-50%) rotate(-15deg)',
          background: colors.accent.primary,
          borderRadius: '50% 50% 50% 0',
          transformOrigin: 'bottom center',
        }}
        animate={{ 
          rotate: [-15, -8, -15],
        }}
        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
      />
      
      {/* 手臂 */}
      {renderArm()}
      
      {/* 表情 */}
      <AnimatePresence mode="wait">
        <motion.div key={`eyes-${normalizedState}`}>
          {renderEyes()}
        </motion.div>
      </AnimatePresence>
      {renderMouth()}
      
      {/* 配饰 */}
      {renderAccessory()}
    </motion.div>
  )
}

export default VitaCharacter
