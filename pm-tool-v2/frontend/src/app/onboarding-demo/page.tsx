'use client'

import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { useOnboardingStore } from './store/onboarding-store'
import { 
  useABTestStore, 
  VERSION_INFO, 
  FlowVersion,
  CHARACTER_STYLE_INFO,
  COPY_STYLE_INFO,
  CharacterStyle,
  CopyStyle,
  V5CharacterStyle,
  V5SceneStyle,
  V5_CHARACTER_STYLE_INFO,
  V5_SCENE_STYLE_INFO,
  // V5 Premium
  V5PremiumTheme,
  V5PremiumCharacter,
  V5_PREMIUM_THEME_INFO,
  V5_PREMIUM_CHARACTER_INFO,
  // PROD
  ProdStyle,
  PROD_STYLE_INFO
} from './store/ab-test-store'
import { getScreenConfig, screensConfig } from './data/screens-config'
import { getScreenConfigV2, screensConfigV2 } from './data/screens-config-v2'
import { getScreenConfigV3, screensConfigV3 } from './data/screens-config-v3'
import { getScreenConfigProduction, screensConfigProduction } from './data/screens-config-production'
import { screensConfigV5, getV5ScreenConfig } from './data/screens-config-v5'
import { PhoneFrame } from './components/ui/PhoneFrame'
import { ScreenRenderer } from './components/screens'
import { V5ScreenRenderer } from './components/screens-v5'
import { V5PremiumRenderer } from './components/v5-redesign'
import { 
  ChevronLeft, 
  ChevronRight, 
  RotateCcw, 
  Download,
  GitBranch,
  Check
} from 'lucide-react'

export default function OnboardingDemoPage() {
  const { 
    currentStep, 
    totalSteps, 
    nextStep, 
    prevStep, 
    goToStep,
    resetDemo,
    setTotalSteps,
    userData,
    results
  } = useOnboardingStore()
  
  const { 
    currentVersion, 
    setVersion,
    characterStyle,
    setCharacterStyle,
    copyStyle,
    setCopyStyle,
    conversationalFeedbackEnabled,
    toggleConversationalFeedback,
    showMascot,
    toggleMascot,
    // V5 配置 (旧)
    v5CharacterStyle,
    setV5CharacterStyle,
    v5SceneStyle,
    setV5SceneStyle,
    // V5 Premium 配置 (新)
    v5PremiumTheme,
    setV5PremiumTheme,
    v5PremiumCharacter,
    setV5PremiumCharacter,
    // PROD 配置
    prodStyle,
    setProdStyle
  } = useABTestStore()
  
  // 根据版本获取配置
  const currentConfig = currentVersion === 'v5'
    ? getV5ScreenConfig(currentStep - 1)
    : currentVersion === 'production'
    ? getScreenConfigProduction(currentStep)
    : currentVersion === 'v3'
    ? getScreenConfigV3(currentStep)
    : currentVersion === 'v2' 
    ? getScreenConfigV2(currentStep) 
    : getScreenConfig(currentStep)
  
  const currentScreensConfig = currentVersion === 'v5'
    ? screensConfigV5
    : currentVersion === 'production'
    ? screensConfigProduction
    : currentVersion === 'v3' 
    ? screensConfigV3 
    : currentVersion === 'v2' 
    ? screensConfigV2 
    : screensConfig
  const currentTotalSteps = currentVersion === 'v5' ? 12 : currentVersion === 'production' ? 18 : currentVersion === 'v3' ? 50 : currentVersion === 'v2' ? 40 : 37
  
  // 版本切换时更新 totalSteps
  useEffect(() => {
    setTotalSteps(currentTotalSteps)
  }, [currentVersion, currentTotalSteps, setTotalSteps])
  
  // 数据一致性检查 - 如果在需要数据的页面但没有数据，自动重置
  useEffect(() => {
    // 检查是否在结果/加载页但缺少必要数据
    const needsData = currentConfig?.type === 'result' || currentConfig?.type === 'loading'
    const hasBasicData = userData.gender && userData.age && userData.currentWeight && userData.height
    
    if (needsData && !hasBasicData && currentStep > 1) {
      console.log('Data inconsistency detected, resetting demo...')
      resetDemo()
    }
  }, [currentStep, currentConfig, userData, resetDemo])
  
  // 版本切换处理
  const handleVersionChange = (version: FlowVersion) => {
    if (version !== currentVersion) {
      setVersion(version)
      resetDemo()
    }
  }
  
  // 键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault()
        nextStep()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        prevStep()
      } else if (e.key === 'r' || e.key === 'R') {
        resetDemo()
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [nextStep, prevStep, resetDemo])
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      {/* 背景装饰 */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-pink-500/10 rounded-full blur-3xl" />
      </div>
      
      <div className="relative z-10 container mx-auto px-4 py-8">
        {/* 头部 */}
        <header className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">VitaFlow Onboarding Demo</h1>
            <p className="text-gray-400 text-sm mt-1">
              Interactive prototype • {currentTotalSteps} screens • 
              <span className={
                currentVersion === 'production' ? 'text-emerald-400' :
                currentVersion === 'v3' ? 'text-blue-400' :
                currentVersion === 'v2' ? 'text-green-400' : 'text-purple-400'
              }>
                {' '}{VERSION_INFO[currentVersion].name}
              </span>
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            {/* A/B Test 版本切换 */}
            <div className="flex items-center gap-1 bg-gray-800 rounded-xl p-1">
              {(['v1', 'v2', 'v3', 'production', 'v5'] as FlowVersion[]).map((version) => (
                <motion.button
                  key={version}
                  onClick={() => handleVersionChange(version)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    currentVersion === version
                      ? version === 'v5'
                        ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white'
                        : version === 'production'
                        ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white'
                        : version === 'v3'
                        ? 'bg-blue-600 text-white'
                        : version === 'v2' 
                        ? 'bg-green-600 text-white' 
                        : 'bg-purple-600 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                  whileHover={{ scale: currentVersion !== version ? 1.02 : 1 }}
                  whileTap={{ scale: 0.98 }}
                >
                  {currentVersion === version && <Check className="w-3 h-3" />}
                  {version === 'production' ? 'PROD' : version.toUpperCase()}
                  <span className="text-xs opacity-70">({VERSION_INFO[version].pages}p)</span>
                </motion.button>
              ))}
            </div>
            
            <motion.button
              onClick={resetDemo}
              className="flex items-center gap-2 px-4 py-2 bg-gray-800 text-gray-300 rounded-xl hover:bg-gray-700 transition-colors"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <RotateCcw className="w-4 h-4" />
              Reset
            </motion.button>
            
            <motion.button
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-500 transition-colors"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <Download className="w-4 h-4" />
              Export
            </motion.button>
          </div>
        </header>
        
        {/* 主要内容 */}
        <div className="flex gap-8 justify-center">
          {/* 手机预览 */}
          <div className="flex-shrink-0">
            <PhoneFrame>
              {currentVersion === 'v5' && currentConfig ? (
                <V5PremiumRenderer
                  config={currentConfig as any}
                  theme={v5PremiumTheme}
                  character={v5PremiumCharacter}
                  onNext={nextStep}
                />
              ) : (
                <ScreenRenderer />
              )}
            </PhoneFrame>
            
            {/* 导航控制 */}
            <div className="flex items-center justify-center gap-4 mt-6">
              <motion.button
                onClick={prevStep}
                disabled={currentStep === 1}
                className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${
                  currentStep === 1 
                    ? 'bg-gray-800 text-gray-600 cursor-not-allowed' 
                    : 'bg-gray-700 text-white hover:bg-gray-600'
                }`}
                whileHover={currentStep !== 1 ? { scale: 1.1 } : {}}
                whileTap={currentStep !== 1 ? { scale: 0.95 } : {}}
              >
                <ChevronLeft className="w-6 h-6" />
              </motion.button>
              
              <div className="text-center min-w-[100px]">
                <span className="text-white font-semibold">
                  {currentStep} / {totalSteps}
                </span>
                <p className="text-gray-500 text-xs mt-1">
                  {currentConfig?.type}
                </p>
              </div>
              
              <motion.button
                onClick={nextStep}
                disabled={currentStep === totalSteps}
                className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${
                  currentStep === totalSteps 
                    ? 'bg-gray-800 text-gray-600 cursor-not-allowed' 
                    : 'bg-purple-600 text-white hover:bg-purple-500'
                }`}
                whileHover={currentStep !== totalSteps ? { scale: 1.1 } : {}}
                whileTap={currentStep !== totalSteps ? { scale: 0.95 } : {}}
              >
                <ChevronRight className="w-6 h-6" />
              </motion.button>
            </div>
          </div>
          
          {/* 侧边栏信息 */}
          <div className="w-80 space-y-6">
            {/* 当前屏幕信息 */}
            <div className="bg-gray-800/50 rounded-2xl p-6 backdrop-blur-sm">
              <h3 className="text-white font-semibold mb-4">Current Screen</h3>
              <div className="space-y-3">
                <div>
                  <p className="text-gray-400 text-xs uppercase tracking-wide">Type</p>
                  <p className="text-white font-medium capitalize">{currentConfig?.type.replace('_', ' ')}</p>
                </div>
                <div>
                  <p className="text-gray-400 text-xs uppercase tracking-wide">Title</p>
                  <p className="text-white font-medium">{currentConfig?.title}</p>
                </div>
                <div>
                  <p className="text-gray-400 text-xs uppercase tracking-wide">Phase</p>
                  <p className="text-purple-400 font-medium capitalize">{currentConfig?.phase}</p>
                </div>
              </div>
            </div>
            
            {/* Conversational Onboarding 控制面板 */}
            <div className="bg-gradient-to-br from-amber-500/10 to-orange-500/10 border border-amber-500/20 rounded-2xl p-6 backdrop-blur-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-amber-400 font-semibold">Conversational Mode</h3>
                <motion.button
                  onClick={toggleConversationalFeedback}
                  className={`w-12 h-6 rounded-full p-1 transition-colors ${
                    conversationalFeedbackEnabled ? 'bg-amber-500' : 'bg-gray-600'
                  }`}
                  whileTap={{ scale: 0.95 }}
                >
                  <motion.div
                    className="w-4 h-4 bg-white rounded-full"
                    animate={{ x: conversationalFeedbackEnabled ? 24 : 0 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                  />
                </motion.button>
              </div>
              
              {conversationalFeedbackEnabled && (
                <motion.div
                  className="space-y-4"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  {/* 角色风格切换 */}
                  <div>
                    <p className="text-gray-400 text-xs uppercase tracking-wide mb-2">Character Style</p>
                    <div className="flex gap-2">
                      {(['v_logo', 'vita', 'abstract'] as CharacterStyle[]).map((style) => (
                        <motion.button
                          key={style}
                          onClick={() => setCharacterStyle(style)}
                          className={`flex-1 py-2 px-2 rounded-lg text-xs font-medium transition-colors ${
                            characterStyle === style
                              ? 'bg-amber-500 text-white'
                              : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                          }`}
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                        >
                          {CHARACTER_STYLE_INFO[style].name}
                        </motion.button>
                      ))}
                    </div>
                    <p className="text-gray-500 text-xs mt-1">
                      {CHARACTER_STYLE_INFO[characterStyle].preview}
                    </p>
                  </div>
                  
                  {/* 文案风格切换 */}
                  <div>
                    <p className="text-gray-400 text-xs uppercase tracking-wide mb-2">Copy Style</p>
                    <div className="flex gap-2">
                      {(['witty', 'warm', 'data'] as CopyStyle[]).map((style) => (
                        <motion.button
                          key={style}
                          onClick={() => setCopyStyle(style)}
                          className={`flex-1 py-2 px-2 rounded-lg text-xs font-medium transition-colors ${
                            copyStyle === style
                              ? 'bg-amber-500 text-white'
                              : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                          }`}
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                        >
                          {COPY_STYLE_INFO[style].name}
                        </motion.button>
                      ))}
                    </div>
                    <p className="text-gray-500 text-xs mt-1 italic">
                      {COPY_STYLE_INFO[copyStyle].example}
                    </p>
                  </div>
                  
                  {/* 显示角色开关 */}
                  <div className="flex items-center justify-between pt-2 border-t border-gray-700">
                    <span className="text-gray-400 text-sm">Show Mascot</span>
                    <motion.button
                      onClick={toggleMascot}
                      className={`w-10 h-5 rounded-full p-0.5 transition-colors ${
                        showMascot ? 'bg-amber-500' : 'bg-gray-600'
                      }`}
                      whileTap={{ scale: 0.95 }}
                    >
                      <motion.div
                        className="w-4 h-4 bg-white rounded-full"
                        animate={{ x: showMascot ? 20 : 0 }}
                        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                      />
                    </motion.button>
                  </div>
                </motion.div>
              )}
            </div>
            
            {/* 用户数据摘要 */}
            <div className="bg-gray-800/50 rounded-2xl p-6 backdrop-blur-sm">
              <h3 className="text-white font-semibold mb-4">Collected Data</h3>
              <div className="space-y-2 text-sm">
                {userData.goal && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Goal</span>
                    <span className="text-white capitalize">{userData.goal.replace('_', ' ')}</span>
                  </div>
                )}
                {userData.gender && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Gender</span>
                    <span className="text-white capitalize">{userData.gender}</span>
                  </div>
                )}
                {userData.age && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Age</span>
                    <span className="text-white">{userData.age} years</span>
                  </div>
                )}
                {userData.currentWeight && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Current Weight</span>
                    <span className="text-white">{userData.currentWeight} kg</span>
                  </div>
                )}
                {userData.targetWeight && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Target Weight</span>
                    <span className="text-white">{userData.targetWeight} kg</span>
                  </div>
                )}
                {results && (
                  <>
                    <div className="border-t border-gray-700 my-3" />
                    <div className="flex justify-between">
                      <span className="text-gray-400">Daily Calories</span>
                      <span className="text-purple-400 font-semibold">{results.dailyCalories} kcal</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">BMI</span>
                      <span className="text-white">{results.bmi}</span>
                    </div>
                  </>
                )}
              </div>
            </div>
            
            {/* 流程缩略图 */}
            <div className="bg-gray-800/50 rounded-2xl p-6 backdrop-blur-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-white font-semibold">Flow Overview</h3>
                <span className={`text-xs px-2 py-1 rounded-full ${
                  currentVersion === 'v5' ? 'bg-amber-500/20 text-amber-400' :
                  currentVersion === 'production' ? 'bg-emerald-500/20 text-emerald-400' :
                  currentVersion === 'v3' ? 'bg-blue-500/20 text-blue-400' :
                  currentVersion === 'v2' ? 'bg-green-500/20 text-green-400' : 'bg-purple-500/20 text-purple-400'
                }`}>
                  {VERSION_INFO[currentVersion].name}
                </span>
              </div>
              <div className="grid grid-cols-8 gap-1">
                {currentScreensConfig.map((screen, index) => {
                  const stepNumber = currentVersion === 'v5' ? index + 1 : screen.id
                  return (
                    <motion.button
                      key={screen.id || index}
                      onClick={() => goToStep(stepNumber)}
                      className={`
                        aspect-square rounded-sm text-[8px] font-bold
                        ${currentStep === stepNumber 
                          ? currentVersion === 'v5' ? 'bg-amber-500 text-white' :
                            currentVersion === 'production' ? 'bg-emerald-500 text-white' :
                            currentVersion === 'v3' ? 'bg-blue-500 text-white' :
                            currentVersion === 'v2' ? 'bg-green-500 text-white' : 'bg-purple-500 text-white'
                          : stepNumber < currentStep
                            ? currentVersion === 'v5' ? 'bg-amber-500/30 text-amber-300' :
                              currentVersion === 'production' ? 'bg-emerald-500/30 text-emerald-300' :
                              currentVersion === 'v3' ? 'bg-blue-500/30 text-blue-300' :
                              currentVersion === 'v2' ? 'bg-green-500/30 text-green-300' : 'bg-purple-500/30 text-purple-300'
                            : 'bg-gray-700 text-gray-500 hover:bg-gray-600'
                        }
                      `}
                      whileHover={{ scale: 1.2 }}
                      whileTap={{ scale: 0.9 }}
                      title={`${stepNumber}. ${screen.title}`}
                    >
                      {stepNumber}
                    </motion.button>
                  )
                })}
              </div>
              
              {/* 图例 */}
              <div className="flex items-center gap-4 mt-4 text-xs">
                <div className="flex items-center gap-1">
                  <div className={`w-3 h-3 rounded-sm ${
                    currentVersion === 'v5' ? 'bg-amber-500/30' :
                    currentVersion === 'production' ? 'bg-emerald-500/30' :
                    currentVersion === 'v3' ? 'bg-blue-500/30' :
                    currentVersion === 'v2' ? 'bg-green-500/30' : 'bg-purple-500/30'
                  }`} />
                  <span className="text-gray-400">Completed</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className={`w-3 h-3 rounded-sm ${
                    currentVersion === 'v5' ? 'bg-amber-500' :
                    currentVersion === 'production' ? 'bg-emerald-500' :
                    currentVersion === 'v3' ? 'bg-blue-500' :
                    currentVersion === 'v2' ? 'bg-green-500' : 'bg-purple-500'
                  }`} />
                  <span className="text-gray-400">Current</span>
                </div>
              </div>
            </div>
            
            {/* 版本改进说明 */}
            {(currentVersion === 'v2' || currentVersion === 'v3' || currentVersion === 'production' || currentVersion === 'v5') && (
              <motion.div 
                className={`border rounded-xl p-4 ${
                  currentVersion === 'v5' ? 'bg-amber-500/10 border-amber-500/20' :
                  currentVersion === 'production' ? 'bg-emerald-500/10 border-emerald-500/20' :
                  currentVersion === 'v3' ? 'bg-blue-500/10 border-blue-500/20' :
                  'bg-green-500/10 border-green-500/20'
                }`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <GitBranch className={`w-4 h-4 ${
                    currentVersion === 'v5' ? 'text-amber-400' :
                    currentVersion === 'production' ? 'text-emerald-400' :
                    currentVersion === 'v3' ? 'text-blue-400' :
                    'text-green-400'
                  }`} />
                  <h4 className={`text-sm font-medium ${
                    currentVersion === 'v5' ? 'text-amber-400' :
                    currentVersion === 'production' ? 'text-emerald-400' :
                    currentVersion === 'v3' ? 'text-blue-400' :
                    'text-green-400'
                  }`}>
                    {currentVersion === 'v5' ? 'V5 Premium 特性' :
                     currentVersion === 'production' ? 'Production 特性' :
                     currentVersion === 'v3' ? 'V3 优化要点' :
                     'V2 优化要点'}
                  </h4>
                </div>
                <ul className="space-y-1.5 text-xs text-gray-400">
                  {VERSION_INFO[currentVersion].highlights.map((item, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className={`mt-0.5 ${
                        currentVersion === 'v5' ? 'text-amber-400' :
                        currentVersion === 'production' ? 'text-emerald-400' :
                        currentVersion === 'v3' ? 'text-blue-400' :
                        'text-green-400'
                      }`}>•</span>
                      {item}
                    </li>
                  ))}
                </ul>
                
                {/* V5 Premium 配置 */}
                {currentVersion === 'v5' && (
                  <div className="mt-4 pt-4 border-t border-amber-500/20 space-y-3">
                    {/* 设计风格 */}
                    <div>
                      <p className="text-gray-400 text-xs uppercase tracking-wide mb-2">Design Theme</p>
                      <div className="grid grid-cols-2 gap-2">
                        {(['brilliant', 'apple'] as V5PremiumTheme[]).map((theme) => (
                          <motion.button
                            key={theme}
                            onClick={() => setV5PremiumTheme(theme)}
                            className={`py-2 px-2 rounded-lg text-xs font-medium transition-colors ${
                              v5PremiumTheme === theme
                                ? 'bg-amber-500 text-white'
                                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                            }`}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            {V5_PREMIUM_THEME_INFO[theme].name}
                          </motion.button>
                        ))}
                      </div>
                      <p className="text-gray-500 text-xs mt-1">
                        {V5_PREMIUM_THEME_INFO[v5PremiumTheme].preview}
                      </p>
                    </div>
                    {/* 角色方案 */}
                    <div>
                      <p className="text-gray-400 text-xs uppercase tracking-wide mb-2">Character</p>
                      <div className="grid grid-cols-2 gap-2">
                        {(['none', 'abstract', 'mascot', 'logo'] as V5PremiumCharacter[]).map((char) => (
                          <motion.button
                            key={char}
                            onClick={() => setV5PremiumCharacter(char)}
                            className={`py-2 px-2 rounded-lg text-xs font-medium transition-colors ${
                              v5PremiumCharacter === char
                                ? 'bg-amber-500 text-white'
                                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                            }`}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            {V5_PREMIUM_CHARACTER_INFO[char].name}
                          </motion.button>
                        ))}
                      </div>
                      <p className="text-gray-500 text-xs mt-1">
                        {V5_PREMIUM_CHARACTER_INFO[v5PremiumCharacter].preview}
                      </p>
                    </div>
                  </div>
                )}
                
                {/* PROD 样式配置 */}
                {currentVersion === 'production' && (
                  <div className="mt-4 pt-4 border-t border-emerald-500/20 space-y-3">
                    <div>
                      <p className="text-gray-400 text-xs uppercase tracking-wide mb-2">Display Style</p>
                      <div className="grid grid-cols-2 gap-2">
                        {(['default', 'bigtext'] as ProdStyle[]).map((style) => (
                          <motion.button
                            key={style}
                            onClick={() => setProdStyle(style)}
                            className={`py-2 px-2 rounded-lg text-xs font-medium transition-colors ${
                              prodStyle === style
                                ? 'bg-emerald-500 text-white'
                                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                            }`}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            {PROD_STYLE_INFO[style].name}
                          </motion.button>
                        ))}
                      </div>
                      <p className="text-gray-500 text-xs mt-1">
                        {PROD_STYLE_INFO[prodStyle].preview}
                      </p>
                    </div>
                  </div>
                )}
              </motion.div>
            )}
            
            {/* 键盘快捷键 */}
            <div className="bg-gray-800/30 rounded-xl p-4">
              <p className="text-gray-500 text-xs">
                <span className="text-gray-400">Shortcuts:</span>{' '}
                ← → Navigate • R Reset • Space Next
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}







