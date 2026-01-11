'use client'

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowRight, Camera, Brain, TrendingUp, Sparkles } from 'lucide-react'
import { V5ScreenLayout } from './V5ScreenLayout'
import { V5ScreenConfig } from '../../data/screens-config-v5'
import { colorsV5, typographyV5, radiiV5 } from '../../lib/design-tokens-v5'
import { 
  ConversationalSelect, 
  ConversationalInput, 
  NaturalNumberInput, 
  PrimaryButton,
  SelectOption 
} from '../interactions-v5'
import { CharacterStyle, UnifiedCharacterState } from '../characters-v5'
import { SceneStyle } from '../scenes-v5'
import { useOnboardingStore } from '../../store/onboarding-store'

interface V5ScreenRendererProps {
  config: V5ScreenConfig
  characterStyle?: CharacterStyle
  onNext?: () => void
}

export function V5ScreenRenderer({
  config,
  characterStyle = 'illustrated',
  onNext,
}: V5ScreenRendererProps) {
  const { userData, setUserData } = useOnboardingStore()
  const [localValue, setLocalValue] = useState<string | number>('')
  const [isDialogComplete, setIsDialogComplete] = useState(false)
  const [characterState, setCharacterState] = useState<UnifiedCharacterState>(
    (config.characterState as UnifiedCharacterState) || 'idle'
  )

  // 初始化本地值
  useEffect(() => {
    if (config.field && userData[config.field as keyof typeof userData]) {
      setLocalValue(userData[config.field as keyof typeof userData] as string | number)
    }
  }, [config.field, userData])

  // 处理选择变化
  const handleSelectChange = (value: string) => {
    setLocalValue(value)
    if (config.field) {
      setUserData({ [config.field]: value })
    }
    // 角色反应
    setCharacterState('happy')
    setTimeout(() => setCharacterState('encouraging'), 500)
  }

  // 处理数字变化
  const handleNumberChange = (value: number) => {
    setLocalValue(value)
    if (config.field) {
      setUserData({ [config.field]: value })
    }
    setCharacterState('thinking')
  }

  // 处理文本输入
  const handleTextChange = (value: string) => {
    setLocalValue(value)
    if (config.field) {
      setUserData({ [config.field]: value })
    }
  }

  // 处理继续
  const handleContinue = () => {
    setCharacterState('happy')
    setTimeout(() => {
      onNext?.()
    }, 300)
  }

  // 转换选项格式
  const convertOptions = (options?: any[]): SelectOption[] => {
    if (!options) return []
    return options.map(opt => ({
      id: opt.id,
      label: opt.label,
      description: opt.description,
      emoji: opt.emoji,
    }))
  }

  // 获取图标组件
  const getIconComponent = (iconName: string) => {
    const icons: Record<string, React.ReactNode> = {
      Camera: <Camera size={28} />,
      Brain: <Brain size={28} />,
      TrendingUp: <TrendingUp size={28} />,
      Sparkles: <Sparkles size={28} />,
    }
    return icons[iconName] || <Sparkles size={28} />
  }

  // 渲染不同类型的内容
  const renderContent = () => {
    switch (config.type) {
      case 'launch':
        return (
          <div className="text-center">
            <motion.div
              className="mb-8"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.5 }}
            >
              {/* Logo */}
              <div
                className="w-20 h-20 mx-auto mb-6 rounded-2xl flex items-center justify-center"
                style={{ background: colorsV5.mint[500] }}
              >
                <span 
                  className="text-3xl font-bold"
                  style={{ color: colorsV5.slate[900] }}
                >
                  V
                </span>
              </div>
              <h1
                style={{
                  fontSize: typographyV5.fontSize['4xl'],
                  fontWeight: typographyV5.fontWeight.bold,
                  color: colorsV5.slate[900],
                }}
              >
                {config.title}
              </h1>
              <p
                className="mt-2"
                style={{
                  fontSize: typographyV5.fontSize.lg,
                  color: colorsV5.slate[500],
                }}
              >
                {config.subtitle}
              </p>
            </motion.div>
            <PrimaryButton onClick={handleContinue} size="xl" fullWidth>
              Get Started
            </PrimaryButton>
          </div>
        )

      case 'introduction':
        return (
          <div className="text-center">
            <PrimaryButton 
              onClick={handleContinue} 
              size="xl" 
              fullWidth
              icon={<ArrowRight size={20} />}
            >
              Let's Get Started
            </PrimaryButton>
          </div>
        )

      case 'text_input':
        return (
          <div className="space-y-6">
            <ConversationalInput
              value={localValue as string}
              onChange={handleTextChange}
              onSubmit={handleContinue}
              placeholder={config.placeholder || 'Type here...'}
              maxLength={30}
            />
          </div>
        )

      case 'question_single':
        return (
          <div className="space-y-6">
            <ConversationalSelect
              options={convertOptions(config.options)}
              value={localValue as string}
              onChange={handleSelectChange}
              layout="vertical"
              size="md"
            />
            {localValue && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <PrimaryButton 
                  onClick={handleContinue} 
                  size="lg" 
                  fullWidth
                  icon={<ArrowRight size={20} />}
                >
                  Continue
                </PrimaryButton>
              </motion.div>
            )}
          </div>
        )

      case 'number_input':
        return (
          <div className="space-y-8">
            <NaturalNumberInput
              value={(localValue as number) || config.min || 25}
              onChange={handleNumberChange}
              min={config.min}
              max={config.max}
              unit={config.unit}
              showSlider={true}
            />
            <PrimaryButton 
              onClick={handleContinue} 
              size="lg" 
              fullWidth
              icon={<ArrowRight size={20} />}
            >
              Continue
            </PrimaryButton>
          </div>
        )

      case 'combined':
        return (
          <div className="space-y-6">
            {/* 身高 */}
            <div>
              <p 
                className="text-center mb-3"
                style={{ color: colorsV5.slate[500], fontSize: typographyV5.fontSize.sm }}
              >
                Height
              </p>
              <NaturalNumberInput
                value={userData.height || 170}
                onChange={(v) => setUserData({ height: v })}
                min={100}
                max={250}
                unit="cm"
                size="md"
                showSlider={false}
              />
            </div>
            {/* 体重 */}
            <div>
              <p 
                className="text-center mb-3"
                style={{ color: colorsV5.slate[500], fontSize: typographyV5.fontSize.sm }}
              >
                Weight
              </p>
              <NaturalNumberInput
                value={userData.currentWeight || 70}
                onChange={(v) => setUserData({ currentWeight: v })}
                min={30}
                max={200}
                unit="kg"
                size="md"
                showSlider={false}
              />
            </div>
            <PrimaryButton 
              onClick={handleContinue} 
              size="lg" 
              fullWidth
              icon={<ArrowRight size={20} />}
            >
              Continue
            </PrimaryButton>
          </div>
        )

      case 'value_prop':
        return (
          <div className="space-y-6">
            {/* 特性列表 */}
            <div className="space-y-4">
              {config.features?.map((feature, index) => (
                <motion.div
                  key={index}
                  className="flex items-center gap-4 p-4 rounded-2xl"
                  style={{ background: colorsV5.white }}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 + index * 0.1 }}
                >
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ background: colorsV5.mint[100], color: colorsV5.mint[500] }}
                  >
                    {getIconComponent(feature.icon)}
                  </div>
                  <div>
                    <h4
                      style={{
                        fontSize: typographyV5.fontSize.lg,
                        fontWeight: typographyV5.fontWeight.semibold,
                        color: colorsV5.slate[900],
                      }}
                    >
                      {feature.title}
                    </h4>
                    <p
                      style={{
                        fontSize: typographyV5.fontSize.sm,
                        color: colorsV5.slate[500],
                      }}
                    >
                      {feature.description}
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>
            <PrimaryButton 
              onClick={handleContinue} 
              size="lg" 
              fullWidth
              icon={<ArrowRight size={20} />}
            >
              Continue
            </PrimaryButton>
          </div>
        )

      case 'loading':
        return (
          <div className="text-center py-8">
            <motion.div
              className="w-16 h-16 mx-auto mb-6 rounded-full"
              style={{ 
                border: `3px solid ${colorsV5.slate[200]}`,
                borderTopColor: colorsV5.mint[500],
              }}
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            />
            <p style={{ color: colorsV5.slate[500] }}>
              Analyzing your profile...
            </p>
          </div>
        )

      case 'result':
        return (
          <div className="space-y-6">
            {/* 结果卡片 */}
            <motion.div
              className="p-6 rounded-3xl text-center"
              style={{ background: colorsV5.slate[900] }}
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
            >
              <p
                style={{
                  fontSize: typographyV5.fontSize.sm,
                  color: colorsV5.slate[400],
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                }}
              >
                Daily Target
              </p>
              <p
                style={{
                  fontSize: typographyV5.fontSize['5xl'],
                  fontWeight: typographyV5.fontWeight.bold,
                  color: colorsV5.white,
                }}
              >
                {userData.targetCalories || 2000}
              </p>
              <p style={{ color: colorsV5.mint[500] }}>calories</p>
            </motion.div>

            {/* 营养素分布 */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: 'Protein', value: userData.targetProtein || 150, unit: 'g', color: colorsV5.mint[500] },
                { label: 'Carbs', value: userData.targetCarbs || 200, unit: 'g', color: '#F59E0B' },
                { label: 'Fat', value: userData.targetFat || 65, unit: 'g', color: '#8B5CF6' },
              ].map((macro, i) => (
                <motion.div
                  key={macro.label}
                  className="p-4 rounded-2xl text-center"
                  style={{ background: colorsV5.white }}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 + i * 0.1 }}
                >
                  <p 
                    style={{ 
                      fontSize: typographyV5.fontSize['2xl'], 
                      fontWeight: typographyV5.fontWeight.bold,
                      color: macro.color,
                    }}
                  >
                    {macro.value}{macro.unit}
                  </p>
                  <p style={{ fontSize: typographyV5.fontSize.sm, color: colorsV5.slate[500] }}>
                    {macro.label}
                  </p>
                </motion.div>
              ))}
            </div>

            <PrimaryButton 
              onClick={handleContinue} 
              size="xl" 
              fullWidth
            >
              Start My Journey
            </PrimaryButton>
          </div>
        )

      default:
        return (
          <div className="text-center">
            <p style={{ color: colorsV5.slate[500] }}>
              Screen type "{config.type}" not implemented
            </p>
            <PrimaryButton onClick={handleContinue} className="mt-4">
              Continue
            </PrimaryButton>
          </div>
        )
    }
  }

  // 是否显示角色
  const shouldShowCharacter = !['launch', 'loading'].includes(config.type)

  return (
    <V5ScreenLayout
      sceneStyle={(config.sceneStyle as SceneStyle) || 'gradient'}
      sceneProgress={config.sceneProgress || 0}
      showCharacter={shouldShowCharacter}
      characterStyle={characterStyle}
      characterState={characterState}
      characterSize={config.type === 'result' ? 'md' : 'lg'}
      showDialog={Boolean(config.dialogText) && shouldShowCharacter}
      dialogText={config.dialogText}
      dialogTyping={config.dialogTyping}
      onDialogComplete={() => setIsDialogComplete(true)}
      contentPosition={config.type === 'launch' ? 'center' : 'bottom'}
    >
      {renderContent()}
    </V5ScreenLayout>
  )
}

export default V5ScreenRenderer
