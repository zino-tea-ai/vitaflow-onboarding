// V5 Premium 角色组件导出

export { NoCharacter } from './NoCharacter'

export { AbstractOrb } from './AbstractOrb'
export type { OrbState } from './AbstractOrb'

export { RefinedMascot } from './RefinedMascot'
export type { MascotState } from './RefinedMascot'

export { LogoMark } from './LogoMark'
export type { LogoState } from './LogoMark'

// 角色类型
export type V5Character = 'none' | 'abstract' | 'mascot' | 'logo'
