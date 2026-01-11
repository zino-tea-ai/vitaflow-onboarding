'use client'

import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { colorsV5, layoutV5 } from '../../lib/design-tokens-v5'
import { pageTransitions } from '../../lib/animation-presets'
import { SceneRenderer, SceneStyle } from '../scenes-v5'
import { CharacterRenderer, CharacterStyle, UnifiedCharacterState } from '../characters-v5'
import { DialogBubble } from '../interactions-v5'

interface V5ScreenLayoutProps {
  children: React.ReactNode
  // 场景配置
  sceneStyle?: SceneStyle
  sceneProgress?: number
  // 角色配置
  showCharacter?: boolean
  characterStyle?: CharacterStyle
  characterState?: UnifiedCharacterState
  characterSize?: 'sm' | 'md' | 'lg' | 'xl'
  // 对话配置
  showDialog?: boolean
  dialogText?: string
  dialogTyping?: boolean
  onDialogComplete?: () => void
  // 布局配置
  contentPosition?: 'bottom' | 'center' | 'top'
  className?: string
}

export function V5ScreenLayout({
  children,
  sceneStyle = 'gradient',
  sceneProgress = 0,
  showCharacter = true,
  characterStyle = 'illustrated',
  characterState = 'idle',
  characterSize = 'lg',
  showDialog = false,
  dialogText = '',
  dialogTyping = false,
  onDialogComplete,
  contentPosition = 'bottom',
  className = '',
}: V5ScreenLayoutProps) {
  const getContentPositionStyles = () => {
    switch (contentPosition) {
      case 'top':
        return 'justify-start pt-16'
      case 'center':
        return 'justify-center'
      case 'bottom':
      default:
        return 'justify-end pb-8'
    }
  }

  return (
    <motion.div
      className={`relative h-full w-full overflow-hidden ${className}`}
      variants={pageTransitions.default}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      {/* 场景背景 */}
      <SceneRenderer
        style={sceneStyle}
        progress={sceneProgress}
        animated={true}
      />

      {/* 主内容容器 */}
      <div className="relative h-full flex flex-col z-10">
        {/* 角色区域 - 上半部分 */}
        {showCharacter && (
          <div 
            className="flex-shrink-0 flex flex-col items-center justify-center"
            style={{ 
              height: `${layoutV5.characterAreaRatio * 100}%`,
              paddingTop: layoutV5.safeArea.top,
            }}
          >
            {/* 角色 */}
            <motion.div
              initial={{ opacity: 0, y: 50, scale: 0.8 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{
                duration: 0.8,
                delay: 0.2,
                ease: [0.34, 1.56, 0.64, 1],
              }}
            >
              <CharacterRenderer
                style={characterStyle}
                state={characterState}
                size={characterSize}
              />
            </motion.div>

            {/* 对话气泡 */}
            <AnimatePresence>
              {showDialog && dialogText && (
                <motion.div
                  className="mt-4 px-6"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ delay: 0.5 }}
                >
                  <DialogBubble
                    text={dialogText}
                    typing={dialogTyping}
                    onTypingComplete={onDialogComplete}
                    size="md"
                    showTail={true}
                    tailPosition="top"
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* 交互区域 - 下半部分 */}
        <div 
          className={`flex-1 flex flex-col ${getContentPositionStyles()} px-6`}
          style={{
            paddingBottom: layoutV5.safeArea.bottom + 8,
          }}
        >
          <motion.div
            className="w-full"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.5 }}
          >
            {children}
          </motion.div>
        </div>
      </div>
    </motion.div>
  )
}

export default V5ScreenLayout
