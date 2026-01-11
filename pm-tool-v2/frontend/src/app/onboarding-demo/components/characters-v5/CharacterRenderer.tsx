'use client'

import React from 'react'
import { VitaEvolution, CharacterState, Expression } from './VitaEvolution'
import { AbstractPremium, AbstractState } from './AbstractPremium'
import { Vita3D, Vita3DState } from './Vita3D'
import { IllustratedVita, IllustratedState } from './IllustratedVita'

// 角色风格类型
export type CharacterStyle = 'evolution' | 'abstract' | '3d' | 'illustrated'

// 统一的状态类型
export type UnifiedCharacterState = 
  | 'idle' 
  | 'speaking' 
  | 'thinking' 
  | 'happy' 
  | 'surprised'
  | 'encouraging' 
  | 'celebrating'
  | 'waving'
  | 'active'
  | 'success'

interface CharacterRendererProps {
  style: CharacterStyle
  state?: UnifiedCharacterState
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
  // VitaEvolution specific
  expression?: Expression
  showAccessory?: boolean
  accessoryType?: 'none' | 'chef-hat' | 'fitness-band' | 'glasses'
  // AbstractPremium specific
  intensity?: 'subtle' | 'medium' | 'dramatic'
  // Vita3D specific
  rotateX?: number
  rotateY?: number
  // IllustratedVita specific
  showShadow?: boolean
}

// 状态映射函数
const mapStateToEvolution = (state: UnifiedCharacterState): CharacterState => {
  const mapping: Record<UnifiedCharacterState, CharacterState> = {
    idle: 'idle',
    speaking: 'speaking',
    thinking: 'thinking',
    happy: 'happy',
    surprised: 'surprised',
    encouraging: 'encouraging',
    celebrating: 'celebrating',
    waving: 'waving',
    active: 'happy',
    success: 'celebrating',
  }
  return mapping[state] || 'idle'
}

const mapStateToAbstract = (state: UnifiedCharacterState): AbstractState => {
  const mapping: Record<UnifiedCharacterState, AbstractState> = {
    idle: 'idle',
    speaking: 'active',
    thinking: 'thinking',
    happy: 'success',
    surprised: 'active',
    encouraging: 'active',
    celebrating: 'celebrating',
    waving: 'active',
    active: 'active',
    success: 'success',
  }
  return mapping[state] || 'idle'
}

const mapStateTo3D = (state: UnifiedCharacterState): Vita3DState => {
  const mapping: Record<UnifiedCharacterState, Vita3DState> = {
    idle: 'idle',
    speaking: 'speaking',
    thinking: 'thinking',
    happy: 'happy',
    surprised: 'happy',
    encouraging: 'happy',
    celebrating: 'celebrating',
    waving: 'happy',
    active: 'speaking',
    success: 'celebrating',
  }
  return mapping[state] || 'idle'
}

const mapStateToIllustrated = (state: UnifiedCharacterState): IllustratedState => {
  const mapping: Record<UnifiedCharacterState, IllustratedState> = {
    idle: 'idle',
    speaking: 'speaking',
    thinking: 'thinking',
    happy: 'happy',
    surprised: 'surprised',
    encouraging: 'encouraging',
    celebrating: 'celebrating',
    waving: 'waving',
    active: 'happy',
    success: 'celebrating',
  }
  return mapping[state] || 'idle'
}

export function CharacterRenderer({
  style,
  state = 'idle',
  size = 'lg',
  className = '',
  expression,
  showAccessory,
  accessoryType,
  intensity,
  rotateX,
  rotateY,
  showShadow,
}: CharacterRendererProps) {
  switch (style) {
    case 'evolution':
      return (
        <VitaEvolution
          state={mapStateToEvolution(state)}
          expression={expression}
          size={size}
          className={className}
          showAccessory={showAccessory}
          accessoryType={accessoryType}
        />
      )
    
    case 'abstract':
      return (
        <AbstractPremium
          state={mapStateToAbstract(state)}
          size={size}
          intensity={intensity}
          className={className}
        />
      )
    
    case '3d':
      return (
        <Vita3D
          state={mapStateTo3D(state)}
          size={size}
          rotateX={rotateX}
          rotateY={rotateY}
          className={className}
        />
      )
    
    case 'illustrated':
      return (
        <IllustratedVita
          state={mapStateToIllustrated(state)}
          size={size}
          className={className}
          showShadow={showShadow}
        />
      )
    
    default:
      return (
        <IllustratedVita
          state={mapStateToIllustrated(state)}
          size={size}
          className={className}
        />
      )
  }
}

export default CharacterRenderer
