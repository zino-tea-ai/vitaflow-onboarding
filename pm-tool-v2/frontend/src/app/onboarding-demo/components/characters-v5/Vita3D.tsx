'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { colorsV5, easingsV5 } from '../../lib/design-tokens-v5'

export type Vita3DState = 
  | 'idle' 
  | 'speaking' 
  | 'thinking' 
  | 'happy' 
  | 'celebrating'

interface Vita3DProps {
  state?: Vita3DState
  size?: 'sm' | 'md' | 'lg' | 'xl'
  rotateX?: number
  rotateY?: number
  className?: string
}

const sizeMap = {
  sm: 100,
  md: 140,
  lg: 180,
  xl: 240,
}

export function Vita3D({
  state = 'idle',
  size = 'lg',
  rotateX = -10,
  rotateY = 15,
  className = '',
}: Vita3DProps) {
  const baseSize = sizeMap[size]
  
  // 获取状态动画
  const getStateAnimation = () => {
    switch (state) {
      case 'idle':
        return {
          y: [0, -8, 0],
          rotateY: [rotateY - 5, rotateY + 5, rotateY - 5],
          transition: {
            duration: 4,
            repeat: Infinity,
            ease: 'easeInOut',
          },
        }
      case 'speaking':
        return {
          scale: [1, 1.02, 1],
          rotateY: [rotateY, rotateY + 3, rotateY],
          transition: {
            duration: 0.4,
            repeat: Infinity,
          },
        }
      case 'thinking':
        return {
          rotateY: [rotateY, rotateY + 20, rotateY],
          rotateX: [rotateX, rotateX - 5, rotateX],
          transition: {
            duration: 2,
            repeat: Infinity,
            ease: 'easeInOut',
          },
        }
      case 'happy':
        return {
          y: [0, -20, 0],
          scale: [1, 1.1, 1],
          rotateY: [rotateY, rotateY, rotateY],
          transition: {
            duration: 0.5,
            ease: easingsV5.outBack,
          },
        }
      case 'celebrating':
        return {
          y: [0, -25, 0, -15, 0],
          rotateY: [rotateY, rotateY + 30, rotateY - 30, rotateY + 15, rotateY],
          scale: [1, 1.15, 1.1, 1.12, 1],
          transition: {
            duration: 1,
            ease: easingsV5.outBack,
          },
        }
      default:
        return {}
    }
  }

  return (
    <motion.div
      className={`relative ${className}`}
      style={{
        width: baseSize,
        height: baseSize * 1.2,
        perspective: 1000,
        perspectiveOrigin: 'center center',
      }}
      animate={getStateAnimation()}
    >
      {/* 3D 容器 */}
      <motion.div
        className="relative w-full h-full"
        style={{
          transformStyle: 'preserve-3d',
          transform: `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`,
        }}
      >
        {/* 阴影 */}
        <motion.div
          className="absolute bottom-0 left-1/2 -translate-x-1/2"
          style={{
            width: baseSize * 0.5,
            height: baseSize * 0.1,
            background: 'rgba(15, 23, 42, 0.15)',
            borderRadius: '50%',
            filter: 'blur(10px)',
            transform: 'rotateX(90deg) translateZ(-10px)',
          }}
        />

        {/* 主体 - 3D 球体效果 */}
        <div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
          style={{
            width: baseSize * 0.8,
            height: baseSize * 0.85,
            transformStyle: 'preserve-3d',
          }}
        >
          {/* 基础形状 - 使用多层实现 3D 效果 */}
          <motion.div
            className="absolute inset-0 rounded-full"
            style={{
              background: `linear-gradient(135deg, ${colorsV5.mint[400]} 0%, ${colorsV5.mint[500]} 50%, #34D399 100%)`,
              boxShadow: `
                inset -${baseSize * 0.15}px -${baseSize * 0.15}px ${baseSize * 0.3}px rgba(0, 0, 0, 0.15),
                inset ${baseSize * 0.05}px ${baseSize * 0.05}px ${baseSize * 0.2}px rgba(255, 255, 255, 0.3),
                0 ${baseSize * 0.1}px ${baseSize * 0.25}px rgba(15, 23, 42, 0.2)
              `,
              transform: 'translateZ(0px)',
            }}
          />
          
          {/* 高光层 */}
          <div
            className="absolute rounded-full"
            style={{
              width: baseSize * 0.35,
              height: baseSize * 0.25,
              background: 'linear-gradient(180deg, rgba(255,255,255,0.5) 0%, rgba(255,255,255,0) 100%)',
              top: '15%',
              left: '20%',
              filter: 'blur(2px)',
              transform: 'translateZ(5px)',
            }}
          />
          
          {/* 反光点 */}
          <div
            className="absolute rounded-full"
            style={{
              width: baseSize * 0.08,
              height: baseSize * 0.08,
              background: 'rgba(255, 255, 255, 0.8)',
              top: '22%',
              left: '28%',
              transform: 'translateZ(10px)',
            }}
          />

          {/* 眼睛容器 */}
          <div
            className="absolute"
            style={{
              top: '35%',
              left: '50%',
              transform: 'translateX(-50%) translateZ(15px)',
              display: 'flex',
              gap: baseSize * 0.15,
            }}
          >
            {/* 左眼 */}
            <motion.div
              className="relative"
              style={{
                width: baseSize * 0.12,
                height: baseSize * 0.12,
              }}
            >
              <div
                className="absolute inset-0 rounded-full"
                style={{
                  background: colorsV5.slate[900],
                  boxShadow: `
                    inset 2px 2px 4px rgba(255,255,255,0.1),
                    0 2px 4px rgba(0,0,0,0.2)
                  `,
                }}
              />
              {/* 眼睛高光 */}
              <div
                className="absolute rounded-full bg-white"
                style={{
                  width: baseSize * 0.04,
                  height: baseSize * 0.04,
                  top: '20%',
                  left: '55%',
                }}
              />
            </motion.div>
            
            {/* 右眼 */}
            <motion.div
              className="relative"
              style={{
                width: baseSize * 0.12,
                height: baseSize * 0.12,
              }}
            >
              <div
                className="absolute inset-0 rounded-full"
                style={{
                  background: colorsV5.slate[900],
                  boxShadow: `
                    inset 2px 2px 4px rgba(255,255,255,0.1),
                    0 2px 4px rgba(0,0,0,0.2)
                  `,
                }}
              />
              <div
                className="absolute rounded-full bg-white"
                style={{
                  width: baseSize * 0.04,
                  height: baseSize * 0.04,
                  top: '20%',
                  left: '55%',
                }}
              />
            </motion.div>
          </div>

          {/* 嘴巴 */}
          <motion.div
            className="absolute"
            style={{
              top: '60%',
              left: '50%',
              transform: 'translateX(-50%) translateZ(12px)',
            }}
            animate={
              state === 'happy' || state === 'celebrating'
                ? { scaleY: [1, 1.3, 1] }
                : state === 'speaking'
                ? { scaleY: [1, 0.6, 1] }
                : {}
            }
            transition={{ duration: 0.3, repeat: state === 'speaking' ? Infinity : 0 }}
          >
            <svg
              width={baseSize * 0.2}
              height={baseSize * 0.1}
              viewBox="0 0 40 20"
            >
              <motion.path
                d={
                  state === 'happy' || state === 'celebrating'
                    ? 'M 5 5 Q 20 20 35 5'
                    : 'M 10 8 Q 20 14 30 8'
                }
                stroke={colorsV5.slate[900]}
                strokeWidth="4"
                strokeLinecap="round"
                fill="none"
              />
            </svg>
          </motion.div>
          
          {/* 腮红 */}
          {(state === 'happy' || state === 'celebrating') && (
            <>
              <motion.div
                className="absolute rounded-full"
                style={{
                  width: baseSize * 0.1,
                  height: baseSize * 0.06,
                  background: 'rgba(255, 150, 150, 0.4)',
                  top: '52%',
                  left: '15%',
                  transform: 'translateZ(8px)',
                  filter: 'blur(2px)',
                }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              />
              <motion.div
                className="absolute rounded-full"
                style={{
                  width: baseSize * 0.1,
                  height: baseSize * 0.06,
                  background: 'rgba(255, 150, 150, 0.4)',
                  top: '52%',
                  right: '15%',
                  transform: 'translateZ(8px)',
                  filter: 'blur(2px)',
                }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              />
            </>
          )}
        </div>

        {/* 装饰光环 */}
        <motion.div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            width: baseSize * 1.1,
            height: baseSize * 1.1,
            border: `2px solid ${colorsV5.mint[500]}20`,
            transform: 'rotateX(75deg) translateZ(-20px)',
          }}
          animate={{
            rotateZ: [0, 360],
          }}
          transition={{
            duration: 20,
            repeat: Infinity,
            ease: 'linear',
          }}
        />

        {/* 环绕小球 */}
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="absolute rounded-full"
            style={{
              width: baseSize * 0.06,
              height: baseSize * 0.06,
              background: colorsV5.mint[400],
              left: '50%',
              top: '50%',
              boxShadow: `0 0 10px ${colorsV5.mint.glow}`,
            }}
            animate={{
              x: Math.cos((i / 3) * Math.PI * 2 + Date.now() * 0.001) * baseSize * 0.6,
              y: Math.sin((i / 3) * Math.PI * 2 + Date.now() * 0.001) * baseSize * 0.3,
              z: Math.sin((i / 3) * Math.PI * 2 + Date.now() * 0.001) * 20,
            }}
            transition={{
              duration: 0,
            }}
          />
        ))}
      </motion.div>
      
      {/* 庆祝效果 */}
      {state === 'celebrating' && (
        <motion.div className="absolute inset-0 pointer-events-none">
          {[...Array(8)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute left-1/2 top-1/2 rounded-full"
              style={{
                width: 8,
                height: 8,
                background: i % 2 === 0 ? colorsV5.mint[500] : colorsV5.mint[300],
              }}
              initial={{ x: 0, y: 0, opacity: 1, scale: 1 }}
              animate={{
                x: Math.cos((i / 8) * Math.PI * 2) * 80,
                y: Math.sin((i / 8) * Math.PI * 2) * 80 - 30,
                opacity: 0,
                scale: 0,
              }}
              transition={{
                duration: 0.8,
                ease: 'easeOut',
              }}
            />
          ))}
        </motion.div>
      )}
    </motion.div>
  )
}

export default Vita3D
