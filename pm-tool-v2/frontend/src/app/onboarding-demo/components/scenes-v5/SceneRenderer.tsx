'use client'

import React from 'react'
import { GradientFlow, TimeOfDay } from './GradientFlow'
import { ParticleUniverse, ParticleMode } from './ParticleUniverse'
import { NatureElements, NatureTheme } from './NatureElements'

// 场景风格类型
export type SceneStyle = 'gradient' | 'particle' | 'nature'

interface SceneRendererProps {
  style: SceneStyle
  progress?: number
  className?: string
  children?: React.ReactNode
  // GradientFlow specific
  timeOfDay?: TimeOfDay
  // ParticleUniverse specific
  particleMode?: ParticleMode
  particleCount?: number
  // NatureElements specific
  natureTheme?: NatureTheme
  density?: 'sparse' | 'normal' | 'dense'
  // Common
  animated?: boolean
}

export function SceneRenderer({
  style,
  progress = 0,
  className = '',
  children,
  timeOfDay,
  particleMode = 'calm',
  particleCount,
  natureTheme = 'fresh',
  density = 'normal',
  animated = true,
}: SceneRendererProps) {
  switch (style) {
    case 'gradient':
      return (
        <GradientFlow
          progress={progress}
          timeOfDay={timeOfDay}
          className={className}
          animated={animated}
        >
          {children}
        </GradientFlow>
      )
    
    case 'particle':
      return (
        <ParticleUniverse
          mode={particleMode}
          particleCount={particleCount}
          className={className}
        >
          {children}
        </ParticleUniverse>
      )
    
    case 'nature':
      return (
        <NatureElements
          theme={natureTheme}
          density={density}
          animated={animated}
          className={className}
        >
          {children}
        </NatureElements>
      )
    
    default:
      return (
        <GradientFlow
          progress={progress}
          className={className}
          animated={animated}
        >
          {children}
        </GradientFlow>
      )
  }
}

export default SceneRenderer
