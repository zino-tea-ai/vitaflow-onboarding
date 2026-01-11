'use client'

import React from 'react'

// 方案 A: 无角色 - 纯文字对话，最极简
// 这个组件返回 null，用于保持接口一致性

interface NoCharacterProps {
  state?: string
  className?: string
}

export function NoCharacter({ className = '' }: NoCharacterProps) {
  // 无角色方案 - 返回空
  return null
}

export default NoCharacter
