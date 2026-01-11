'use client'

import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { colorsV5, easingsV5 } from '../../lib/design-tokens-v5'

export type IllustratedState = 
  | 'idle' 
  | 'speaking' 
  | 'thinking' 
  | 'happy' 
  | 'surprised'
  | 'encouraging' 
  | 'celebrating'
  | 'waving'

interface IllustratedVitaProps {
  state?: IllustratedState
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
  showShadow?: boolean
}

const sizeMap = {
  sm: { scale: 0.5, height: 180 },
  md: { scale: 0.7, height: 250 },
  lg: { scale: 1, height: 360 },
  xl: { scale: 1.3, height: 470 },
}

export function IllustratedVita({
  state = 'idle',
  size = 'lg',
  className = '',
  showShadow = true,
}: IllustratedVitaProps) {
  const { scale, height } = sizeMap[size]
  
  // 身体动画
  const getBodyAnimation = () => {
    switch (state) {
      case 'idle':
        return {
          y: [0, -6, 0],
          transition: { duration: 3, repeat: Infinity, ease: 'easeInOut' },
        }
      case 'speaking':
        return {
          y: [0, -3, 0],
          transition: { duration: 0.5, repeat: Infinity },
        }
      case 'thinking':
        return {
          rotate: [-2, 2, -2],
          transition: { duration: 2, repeat: Infinity, ease: 'easeInOut' },
        }
      case 'happy':
        return {
          y: [0, -15, 0],
          scale: [1, 1.05, 1],
          transition: { duration: 0.5, ease: easingsV5.outBack },
        }
      case 'surprised':
        return {
          scale: [1, 1.1, 1],
          transition: { duration: 0.3 },
        }
      case 'encouraging':
        return {
          rotate: [0, -5, 5, 0],
          transition: { duration: 0.6 },
        }
      case 'celebrating':
        return {
          y: [0, -25, 0, -15, 0],
          rotate: [0, -8, 8, -4, 0],
          transition: { duration: 1, ease: easingsV5.outBack },
        }
      case 'waving':
        return {
          rotate: [0, 3, -3, 0],
          transition: { duration: 1, ease: 'easeInOut' },
        }
      default:
        return {}
    }
  }

  // 手臂动画
  const getArmAnimation = (isLeft: boolean) => {
    if (state === 'waving' && !isLeft) {
      return {
        rotate: [-20, 40, -20],
        transition: { duration: 0.6, repeat: 3 },
      }
    }
    if (state === 'celebrating') {
      return {
        rotate: isLeft ? [-10, -60, -10] : [10, 60, 10],
        transition: { duration: 0.5, repeat: 2 },
      }
    }
    if (state === 'encouraging') {
      return {
        rotate: isLeft ? [20, 30, 20] : [-20, -30, -20],
        transition: { duration: 0.4 },
      }
    }
    return {
      rotate: isLeft ? 15 : -15,
    }
  }

  // 腿动画
  const getLegAnimation = (isLeft: boolean) => {
    if (state === 'celebrating') {
      return {
        rotate: isLeft ? [-5, 10, -5] : [5, -10, 5],
        transition: { duration: 0.3, repeat: 3, delay: isLeft ? 0 : 0.15 },
      }
    }
    return {}
  }

  // 表情
  const getExpression = () => {
    switch (state) {
      case 'happy':
      case 'celebrating':
        return { eyeType: 'happy', mouthType: 'grin' }
      case 'surprised':
        return { eyeType: 'wide', mouthType: 'o' }
      case 'thinking':
        return { eyeType: 'look-up', mouthType: 'hmm' }
      case 'waving':
      case 'encouraging':
        return { eyeType: 'happy', mouthType: 'smile' }
      case 'speaking':
        return { eyeType: 'normal', mouthType: 'speaking' }
      default:
        return { eyeType: 'normal', mouthType: 'smile' }
    }
  }

  const expression = getExpression()

  return (
    <motion.div
      className={`relative ${className}`}
      style={{
        width: 200 * scale,
        height: height,
        transformOrigin: 'center bottom',
      }}
    >
      {/* 地面阴影 */}
      {showShadow && (
        <motion.div
          className="absolute bottom-0 left-1/2 -translate-x-1/2"
          style={{
            width: 100 * scale,
            height: 20 * scale,
            background: 'rgba(15, 23, 42, 0.1)',
            borderRadius: '50%',
            filter: 'blur(8px)',
          }}
          animate={{
            scale: state === 'celebrating' ? [1, 0.7, 1] : 1,
            opacity: state === 'celebrating' ? [0.15, 0.08, 0.15] : 0.15,
          }}
        />
      )}

      {/* 身体组 */}
      <motion.div
        className="absolute bottom-[20px] left-1/2"
        style={{ 
          x: '-50%',
          transformOrigin: 'center bottom',
        }}
        animate={getBodyAnimation()}
      >
        {/* 腿 */}
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 flex gap-[8px]">
          {/* 左腿 */}
          <motion.div
            style={{
              width: 18 * scale,
              height: 55 * scale,
              transformOrigin: 'top center',
            }}
            animate={getLegAnimation(true)}
          >
            {/* 大腿 */}
            <div
              style={{
                width: '100%',
                height: '60%',
                background: colorsV5.mint[500],
                borderRadius: 9 * scale,
              }}
            />
            {/* 小腿 */}
            <div
              style={{
                width: '100%',
                height: '45%',
                background: colorsV5.mint[500],
                borderRadius: 9 * scale,
                marginTop: -4 * scale,
              }}
            />
            {/* 鞋子 */}
            <div
              style={{
                width: 26 * scale,
                height: 16 * scale,
                background: colorsV5.slate[800],
                borderRadius: `${8 * scale}px ${12 * scale}px ${8 * scale}px ${8 * scale}px`,
                marginTop: -2 * scale,
                marginLeft: -4 * scale,
              }}
            />
          </motion.div>
          
          {/* 右腿 */}
          <motion.div
            style={{
              width: 18 * scale,
              height: 55 * scale,
              transformOrigin: 'top center',
            }}
            animate={getLegAnimation(false)}
          >
            <div
              style={{
                width: '100%',
                height: '60%',
                background: colorsV5.mint[500],
                borderRadius: 9 * scale,
              }}
            />
            <div
              style={{
                width: '100%',
                height: '45%',
                background: colorsV5.mint[500],
                borderRadius: 9 * scale,
                marginTop: -4 * scale,
              }}
            />
            <div
              style={{
                width: 26 * scale,
                height: 16 * scale,
                background: colorsV5.slate[800],
                borderRadius: `${12 * scale}px ${8 * scale}px ${8 * scale}px ${8 * scale}px`,
                marginTop: -2 * scale,
                marginLeft: -4 * scale,
              }}
            />
          </motion.div>
        </div>

        {/* 身体 + 头 (一体化设计) */}
        <div
          className="absolute left-1/2 -translate-x-1/2"
          style={{ bottom: 50 * scale }}
        >
          <svg
            width={160 * scale}
            height={200 * scale}
            viewBox="0 0 160 200"
            fill="none"
          >
            <defs>
              <linearGradient id="illustratedBodyGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor={colorsV5.mint[400]} />
                <stop offset="100%" stopColor={colorsV5.mint[500]} />
              </linearGradient>
            </defs>

            {/* 身体主体 - 水滴/心形造型 */}
            <path
              d="M 80 10 
                 C 130 10 150 50 150 100 
                 C 150 150 120 190 80 190 
                 C 40 190 10 150 10 100 
                 C 10 50 30 10 80 10"
              fill="url(#illustratedBodyGradient)"
            />
            
            {/* 高光 */}
            <ellipse
              cx="55"
              cy="50"
              rx="25"
              ry="18"
              fill="rgba(255, 255, 255, 0.25)"
            />

            {/* 眼睛 */}
            <g transform="translate(45, 70)">
              {/* 左眼 */}
              <motion.g
                animate={
                  expression.eyeType === 'happy'
                    ? { scaleY: 0.3, y: 5 }
                    : expression.eyeType === 'wide'
                    ? { scaleY: 1.2 }
                    : expression.eyeType === 'look-up'
                    ? { y: -3 }
                    : {}
                }
                transition={{ duration: 0.2 }}
              >
                <circle cx="0" cy="0" r="10" fill={colorsV5.slate[900]} />
                {expression.eyeType !== 'happy' && (
                  <circle cx="3" cy="-3" r="3" fill="white" />
                )}
              </motion.g>
              
              {/* 右眼 */}
              <motion.g
                transform="translate(70, 0)"
                animate={
                  expression.eyeType === 'happy'
                    ? { scaleY: 0.3, y: 5 }
                    : expression.eyeType === 'wide'
                    ? { scaleY: 1.2 }
                    : expression.eyeType === 'look-up'
                    ? { y: -3 }
                    : {}
                }
                transition={{ duration: 0.2 }}
              >
                <circle cx="0" cy="0" r="10" fill={colorsV5.slate[900]} />
                {expression.eyeType !== 'happy' && (
                  <circle cx="3" cy="-3" r="3" fill="white" />
                )}
              </motion.g>
            </g>

            {/* 腮红 */}
            {(state === 'happy' || state === 'celebrating' || state === 'waving') && (
              <>
                <ellipse cx="35" cy="110" rx="12" ry="7" fill="rgba(255, 150, 150, 0.35)" />
                <ellipse cx="125" cy="110" rx="12" ry="7" fill="rgba(255, 150, 150, 0.35)" />
              </>
            )}

            {/* 嘴巴 */}
            <motion.path
              d={
                expression.mouthType === 'grin'
                  ? 'M 55 125 Q 80 155 105 125'
                  : expression.mouthType === 'o'
                  ? 'M 70 130 A 10 12 0 1 0 90 130 A 10 12 0 1 0 70 130'
                  : expression.mouthType === 'hmm'
                  ? 'M 60 128 Q 70 125 90 130'
                  : expression.mouthType === 'speaking'
                  ? 'M 65 125 Q 80 140 95 125'
                  : 'M 60 125 Q 80 140 100 125'
              }
              stroke={expression.mouthType === 'o' ? 'none' : colorsV5.slate[900]}
              strokeWidth="5"
              strokeLinecap="round"
              fill={expression.mouthType === 'o' || expression.mouthType === 'grin' ? colorsV5.slate[900] : 'none'}
              animate={
                expression.mouthType === 'speaking'
                  ? { d: ['M 65 125 Q 80 140 95 125', 'M 65 128 Q 80 135 95 128', 'M 65 125 Q 80 140 95 125'] }
                  : {}
              }
              transition={{ duration: 0.3, repeat: state === 'speaking' ? Infinity : 0 }}
            />
          </svg>

          {/* 左手臂 */}
          <motion.div
            className="absolute"
            style={{
              width: 14 * scale,
              height: 50 * scale,
              background: colorsV5.mint[500],
              borderRadius: 7 * scale,
              left: -5 * scale,
              top: 90 * scale,
              transformOrigin: 'top center',
            }}
            animate={getArmAnimation(true)}
          >
            {/* 手 */}
            <div
              className="absolute -bottom-2 left-1/2 -translate-x-1/2"
              style={{
                width: 20 * scale,
                height: 18 * scale,
                background: colorsV5.mint[500],
                borderRadius: '50%',
              }}
            />
          </motion.div>

          {/* 右手臂 */}
          <motion.div
            className="absolute"
            style={{
              width: 14 * scale,
              height: 50 * scale,
              background: colorsV5.mint[500],
              borderRadius: 7 * scale,
              right: -5 * scale,
              top: 90 * scale,
              transformOrigin: 'top center',
            }}
            animate={getArmAnimation(false)}
          >
            <div
              className="absolute -bottom-2 left-1/2 -translate-x-1/2"
              style={{
                width: 20 * scale,
                height: 18 * scale,
                background: colorsV5.mint[500],
                borderRadius: '50%',
              }}
            />
          </motion.div>
        </div>
      </motion.div>

      {/* 庆祝粒子 */}
      <AnimatePresence>
        {state === 'celebrating' && (
          <>
            {[...Array(12)].map((_, i) => (
              <motion.div
                key={i}
                className="absolute rounded-full"
                style={{
                  width: (6 + Math.random() * 6) * scale,
                  height: (6 + Math.random() * 6) * scale,
                  background: i % 3 === 0 ? colorsV5.mint[500] : i % 3 === 1 ? colorsV5.mint[300] : colorsV5.slate[300],
                  left: '50%',
                  top: '30%',
                }}
                initial={{ x: 0, y: 0, opacity: 1 }}
                animate={{
                  x: (Math.random() - 0.5) * 200 * scale,
                  y: (Math.random() - 0.8) * 150 * scale,
                  opacity: 0,
                  rotate: Math.random() * 360,
                }}
                exit={{ opacity: 0 }}
                transition={{
                  duration: 0.8 + Math.random() * 0.4,
                  ease: 'easeOut',
                }}
              />
            ))}
          </>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default IllustratedVita
