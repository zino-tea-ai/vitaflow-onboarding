'use client'

import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { useOnboardingStore } from './store/onboarding-store'
import { getScreenConfig, screensConfig } from './data/screens-config'
import { PhoneFrame } from './components/ui/PhoneFrame'
import { ScreenRenderer } from './components/screens'
import { 
  ChevronLeft, 
  ChevronRight, 
  RotateCcw, 
  Download,
  Play,
  Pause
} from 'lucide-react'

export default function OnboardingDemoPage() {
  const { 
    currentStep, 
    totalSteps, 
    nextStep, 
    prevStep, 
    goToStep,
    resetDemo,
    userData,
    results
  } = useOnboardingStore()
  
  const currentConfig = getScreenConfig(currentStep)
  
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
              Interactive prototype • {totalSteps} screens
            </p>
          </div>
          
          <div className="flex items-center gap-4">
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
              <ScreenRenderer />
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
              <h3 className="text-white font-semibold mb-4">Flow Overview</h3>
              <div className="grid grid-cols-8 gap-1">
                {screensConfig.map((screen) => (
                  <motion.button
                    key={screen.id}
                    onClick={() => goToStep(screen.id)}
                    className={`
                      aspect-square rounded-sm text-[8px] font-bold
                      ${currentStep === screen.id 
                        ? 'bg-purple-500 text-white' 
                        : screen.id < currentStep
                          ? 'bg-purple-500/30 text-purple-300'
                          : 'bg-gray-700 text-gray-500 hover:bg-gray-600'
                      }
                    `}
                    whileHover={{ scale: 1.2 }}
                    whileTap={{ scale: 0.9 }}
                    title={`${screen.id}. ${screen.title}`}
                  >
                    {screen.id}
                  </motion.button>
                ))}
              </div>
              
              {/* 图例 */}
              <div className="flex items-center gap-4 mt-4 text-xs">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded-sm bg-purple-500/30" />
                  <span className="text-gray-400">Completed</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded-sm bg-purple-500" />
                  <span className="text-gray-400">Current</span>
                </div>
              </div>
            </div>
            
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







