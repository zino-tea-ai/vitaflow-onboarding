'use client'

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowRight } from 'lucide-react'

// 主题
import { V5Theme, brilliantTheme, appleTheme } from './themes'
import { BrilliantLayout, BrilliantOption, BrilliantInput, BrilliantButton } from './themes/BrilliantLayout'
import { AppleLayout, AppleOption, AppleInput, AppleButton } from './themes/AppleLayout'

// 角色
import { V5Character, NoCharacter, AbstractOrb, RefinedMascot, LogoMark } from './characters'

// Store
import { useOnboardingStore } from '../../store/onboarding-store'

// 配置类型
interface V5PremiumConfig {
  id: string
  type: 'launch' | 'text_input' | 'question_single' | 'number_input' | 'combined' | 'value_prop' | 'loading' | 'result'
  title: string
  subtitle?: string
  field?: string
  placeholder?: string
  options?: Array<{ id: string; label: string; description?: string }>
  min?: number
  max?: number
  unit?: string
}

interface V5PremiumRendererProps {
  config: V5PremiumConfig
  theme: V5Theme
  character: V5Character
  onNext?: () => void
}

export function V5PremiumRenderer({
  config,
  theme,
  character,
  onNext,
}: V5PremiumRendererProps) {
  const { userData, setUserData } = useOnboardingStore()
  const [localValue, setLocalValue] = useState<string | number>('')
  const [characterState, setCharacterState] = useState<string>('idle')

  // 初始化本地值
  useEffect(() => {
    if (config.field && userData[config.field as keyof typeof userData]) {
      setLocalValue(userData[config.field as keyof typeof userData] as string | number)
    }
  }, [config.field, userData])

  // 选择变化
  const handleSelectChange = (value: string) => {
    setLocalValue(value)
    if (config.field) {
      setUserData({ [config.field]: value })
    }
    setCharacterState('happy')
    setTimeout(() => setCharacterState('idle'), 500)
  }

  // 输入变化
  const handleInputChange = (value: string) => {
    setLocalValue(value)
    if (config.field) {
      setUserData({ [config.field]: value })
    }
  }

  // 数字变化
  const handleNumberChange = (value: number) => {
    setLocalValue(value)
    if (config.field) {
      setUserData({ [config.field]: value })
    }
  }

  // 继续
  const handleContinue = () => {
    setCharacterState('success')
    setTimeout(() => onNext?.(), 300)
  }

  // 渲染角色
  const renderCharacter = () => {
    const themeColor = theme === 'brilliant' ? '#1A1A1A' : '#0071E3'
    const mascotColor = '#10B981'

    switch (character) {
      case 'none':
        return <NoCharacter />
      case 'abstract':
        return <AbstractOrb state={characterState as any} size={80} color={themeColor} />
      case 'mascot':
        return <RefinedMascot state={characterState as any} size={100} primaryColor={mascotColor} />
      case 'logo':
        return (
          <LogoMark 
            state={characterState as any} 
            size={64} 
            backgroundColor={themeColor}
          />
        )
      default:
        return null
    }
  }

  // 渲染选项组件
  const OptionComponent = theme === 'brilliant' ? BrilliantOption : AppleOption
  const InputComponent = theme === 'brilliant' ? BrilliantInput : AppleInput
  const ButtonComponent = theme === 'brilliant' ? BrilliantButton : AppleButton

  // 渲染内容
  const renderContent = () => {
    switch (config.type) {
      case 'launch':
        return (
          <div className="space-y-4">
            <ButtonComponent onClick={handleContinue}>
              Get Started
            </ButtonComponent>
          </div>
        )

      case 'text_input':
        return (
          <div className="space-y-4">
            <InputComponent
              value={localValue as string}
              onChange={handleInputChange}
              placeholder={config.placeholder || 'Type here...'}
              onSubmit={handleContinue}
            />
            {localValue && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <ButtonComponent onClick={handleContinue}>
                  Continue
                </ButtonComponent>
              </motion.div>
            )}
          </div>
        )

      case 'question_single':
        return (
          <div className="space-y-3">
            {config.options?.map((option) => (
              <OptionComponent
                key={option.id}
                label={option.label}
                description={option.description}
                selected={localValue === option.id}
                onClick={() => handleSelectChange(option.id)}
              />
            ))}
            {localValue && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="pt-2"
              >
                <ButtonComponent onClick={handleContinue}>
                  Continue
                </ButtonComponent>
              </motion.div>
            )}
          </div>
        )

      case 'number_input':
        return (
          <div className="space-y-6">
            {/* 简单的数字输入 */}
            <div className="text-center">
              <div className="flex items-center justify-center gap-4">
                <motion.button
                  className="w-12 h-12 rounded-full flex items-center justify-center"
                  style={{
                    background: theme === 'brilliant' ? '#F5F5F5' : 'rgba(0,0,0,0.05)',
                  }}
                  onClick={() => handleNumberChange(Math.max(config.min || 0, (localValue as number || config.min || 0) - 1))}
                  whileTap={{ scale: 0.95 }}
                >
                  -
                </motion.button>
                <motion.span
                  className="text-5xl font-bold"
                  style={{ color: theme === 'brilliant' ? '#1A1A1A' : '#1D1D1F' }}
                  key={localValue}
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  {localValue || config.min || 25}
                </motion.span>
                <motion.button
                  className="w-12 h-12 rounded-full flex items-center justify-center"
                  style={{
                    background: theme === 'brilliant' ? '#F5F5F5' : 'rgba(0,0,0,0.05)',
                  }}
                  onClick={() => handleNumberChange(Math.min(config.max || 100, (localValue as number || config.min || 0) + 1))}
                  whileTap={{ scale: 0.95 }}
                >
                  +
                </motion.button>
              </div>
              {config.unit && (
                <p 
                  className="mt-2"
                  style={{ color: theme === 'brilliant' ? '#6B7280' : '#86868B' }}
                >
                  {config.unit}
                </p>
              )}
            </div>
            <ButtonComponent onClick={handleContinue}>
              Continue
            </ButtonComponent>
          </div>
        )

      case 'combined':
        return (
          <div className="space-y-6">
            {/* 身高 */}
            <div>
              <p className="text-center text-sm mb-2" style={{ color: theme === 'brilliant' ? '#6B7280' : '#86868B' }}>
                Height (cm)
              </p>
              <div className="flex items-center justify-center gap-4">
                <motion.button
                  className="w-10 h-10 rounded-full flex items-center justify-center text-lg"
                  style={{ background: theme === 'brilliant' ? '#F5F5F5' : 'rgba(0,0,0,0.05)' }}
                  onClick={() => setUserData({ height: Math.max(100, (userData.height || 170) - 1) })}
                  whileTap={{ scale: 0.95 }}
                >-</motion.button>
                <span className="text-3xl font-bold w-20 text-center">{userData.height || 170}</span>
                <motion.button
                  className="w-10 h-10 rounded-full flex items-center justify-center text-lg"
                  style={{ background: theme === 'brilliant' ? '#F5F5F5' : 'rgba(0,0,0,0.05)' }}
                  onClick={() => setUserData({ height: Math.min(250, (userData.height || 170) + 1) })}
                  whileTap={{ scale: 0.95 }}
                >+</motion.button>
              </div>
            </div>
            {/* 体重 */}
            <div>
              <p className="text-center text-sm mb-2" style={{ color: theme === 'brilliant' ? '#6B7280' : '#86868B' }}>
                Weight (kg)
              </p>
              <div className="flex items-center justify-center gap-4">
                <motion.button
                  className="w-10 h-10 rounded-full flex items-center justify-center text-lg"
                  style={{ background: theme === 'brilliant' ? '#F5F5F5' : 'rgba(0,0,0,0.05)' }}
                  onClick={() => setUserData({ currentWeight: Math.max(30, (userData.currentWeight || 70) - 1) })}
                  whileTap={{ scale: 0.95 }}
                >-</motion.button>
                <span className="text-3xl font-bold w-20 text-center">{userData.currentWeight || 70}</span>
                <motion.button
                  className="w-10 h-10 rounded-full flex items-center justify-center text-lg"
                  style={{ background: theme === 'brilliant' ? '#F5F5F5' : 'rgba(0,0,0,0.05)' }}
                  onClick={() => setUserData({ currentWeight: Math.min(200, (userData.currentWeight || 70) + 1) })}
                  whileTap={{ scale: 0.95 }}
                >+</motion.button>
              </div>
            </div>
            <ButtonComponent onClick={handleContinue}>
              Continue
            </ButtonComponent>
          </div>
        )

      case 'loading':
        return (
          <div className="text-center py-8">
            <motion.div
              className="w-12 h-12 mx-auto rounded-full border-3"
              style={{
                borderColor: theme === 'brilliant' ? '#E5E7EB' : 'rgba(0,0,0,0.1)',
                borderTopColor: theme === 'brilliant' ? '#1A1A1A' : '#0071E3',
              }}
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            />
            <p className="mt-4" style={{ color: theme === 'brilliant' ? '#6B7280' : '#86868B' }}>
              Creating your plan...
            </p>
          </div>
        )

      case 'result':
        return (
          <div className="space-y-4">
            {/* 卡片结果 */}
            <motion.div
              className="p-6 rounded-2xl text-center"
              style={{
                background: theme === 'brilliant' ? '#1A1A1A' : '#0071E3',
                color: '#FFFFFF',
              }}
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
            >
              <p className="text-xs uppercase tracking-wider opacity-70">Daily Target</p>
              <p className="text-4xl font-bold mt-1">{userData.targetCalories || 2000}</p>
              <p className="text-sm opacity-80">calories</p>
            </motion.div>
            <ButtonComponent onClick={handleContinue}>
              Start My Journey
            </ButtonComponent>
          </div>
        )

      default:
        return (
          <ButtonComponent onClick={handleContinue}>
            Continue
          </ButtonComponent>
        )
    }
  }

  // 根据主题选择布局
  const LayoutComponent = theme === 'brilliant' ? BrilliantLayout : AppleLayout

  // 获取对话文字（仅用于 Brilliant 布局）
  const getDialogText = () => {
    if (config.type === 'launch') return 'Your AI Nutrition Companion'
    return config.title
  }

  return (
    <LayoutComponent
      characterSlot={character !== 'none' ? renderCharacter() : undefined}
      dialogText={theme === 'brilliant' ? getDialogText() : undefined}
      showDialog={theme === 'brilliant'}
      title={theme === 'apple' ? config.title : undefined}
      subtitle={theme === 'apple' ? config.subtitle : undefined}
    >
      {renderContent()}
    </LayoutComponent>
  )
}

export default V5PremiumRenderer
