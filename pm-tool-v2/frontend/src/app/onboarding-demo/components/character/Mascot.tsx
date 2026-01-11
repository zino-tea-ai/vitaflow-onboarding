'use client'

import { VLogoCharacter } from './VLogoCharacter'
import { VitaCharacter, MascotState as VitaMascotState } from './VitaCharacter'
import { AbstractCharacter } from './AbstractCharacter'
import { GradientOrb } from './GradientOrb'

export type CharacterStyle = 'v_logo' | 'vita' | 'abstract' | 'orb'

// 导出完整的状态类型
export type MascotState = VitaMascotState

// 尺寸类型
export type MascotSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl'

interface MascotProps {
  /** 角色风格 */
  style?: CharacterStyle
  /** 角色状态/表情 */
  state?: MascotState
  /** 尺寸 */
  size?: MascotSize
  /** 额外样式 */
  className?: string
  /** 是否显示手臂（用于挥手动画） */
  showArm?: boolean
}

/**
 * 统一的吉祥物组件 2.0
 * 根据 style 参数渲染不同风格的角色
 * 
 * 状态系统：
 * - idle: 默认等待，眨眼 + 微浮动
 * - greeting: 开场白挥手
 * - listening: 等待用户输入
 * - thinking: 处理中
 * - explaining: 讲解价值点
 * - happy: 开心
 * - excited: 兴奋
 * - encouraging: 鼓励
 * - proud: 展示结果时骄傲
 * - celebrating: 里程碑庆祝
 * - surprised: 惊讶
 * - waving: 挥手
 * - cheering: 欢呼
 */
export function Mascot({ 
  style = 'vita',
  state = 'idle',
  size = 'md',
  className = '',
  showArm = false
}: MascotProps) {
  // 将 xs/xl 映射到其他角色支持的尺寸
  const mappedSize = size === 'xs' ? 'sm' : size === 'xl' ? 'lg' : size
  
  switch (style) {
    case 'v_logo':
      return <VLogoCharacter state={state} size={mappedSize as 'sm' | 'md' | 'lg'} className={className} />
    case 'vita':
      return <VitaCharacter state={state} size={size} className={className} showArm={showArm} />
    case 'abstract':
      return <AbstractCharacter state={state} size={mappedSize as 'sm' | 'md' | 'lg'} className={className} />
    case 'orb':
      return <GradientOrb state={state} size={mappedSize as 'sm' | 'md' | 'lg'} className={className} />
    default:
      return <GradientOrb state={state} size={mappedSize as 'sm' | 'md' | 'lg'} className={className} />
  }
}

export default Mascot
