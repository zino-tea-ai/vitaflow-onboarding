'use client'

import { AnimatePresence, motion } from 'framer-motion'
import { useOnboardingStore } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { getScreenConfig, ScreenConfig } from '../../data/screens-config'
import { getScreenConfigV2, ScreenConfig as ScreenConfigV2 } from '../../data/screens-config-v2'
import { getScreenConfigV3, ScreenConfigV3 } from '../../data/screens-config-v3'
import { getScreenConfigProduction, ScreenConfigProduction } from '../../data/screens-config-production'

// 统一的配置类型
type AnyScreenConfig = ScreenConfig | ScreenConfigV2 | ScreenConfigV3 | ScreenConfigProduction

// 导入所有屏幕组件
import { LaunchScreen } from './LaunchScreen'
import { WelcomeScreen } from './WelcomeScreen'
import { IntroductionScreen } from './IntroductionScreen'
import { QuestionSingleScreen } from './QuestionSingleScreen'
import { QuestionMultiScreen } from './QuestionMultiScreen'
import { NumberInputScreen } from './NumberInputScreen'
import { TextInputScreen } from './TextInputScreen'
import { TransitionScreen } from './TransitionScreen'
import { LoadingScreen } from './LoadingScreen'
import { ResultScreen } from './ResultScreen'
import { ValuePropScreen } from './ValuePropScreen'
import { ScanGameScreen } from './ScanGameScreen'
import { SpinGameScreen } from './SpinGameScreen'
import { PermissionScreen } from './PermissionScreen'
import { PaywallScreen } from './PaywallScreen'
import { CelebrationScreen } from './CelebrationScreen'
import { AccountScreen } from './AccountScreen'
import { SoftCommitScreen } from './SoftCommitScreen'

// Production 版本专用组件
import { CombinedWelcomeGoalScreen } from './CombinedWelcomeGoalScreen'
import { CombinedHeightWeightScreen } from './CombinedHeightWeightScreen'

// 页面过渡动效
const pageVariants = {
  initial: (direction: number) => ({
    opacity: 0,
    x: direction > 0 ? 100 : -100,
    scale: 0.98
  }),
  animate: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: {
      type: 'spring' as const,
      stiffness: 300,
      damping: 30,
      mass: 1
    }
  },
  exit: (direction: number) => ({
    opacity: 0,
    x: direction > 0 ? -100 : 100,
    scale: 0.98,
    transition: {
      type: 'spring' as const,
      stiffness: 300,
      damping: 30,
      mass: 1
    }
  })
}

export function ScreenRenderer() {
  const { currentStep, direction } = useOnboardingStore()
  const { currentVersion } = useABTestStore()
  
  // 根据 A/B Test 版本选择配置
  const config = currentVersion === 'production'
    ? getScreenConfigProduction(currentStep)
    : currentVersion === 'v3'
    ? getScreenConfigV3(currentStep)
    : currentVersion === 'v2' 
    ? getScreenConfigV2(currentStep) 
    : getScreenConfig(currentStep)

  if (!config) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500">Screen not found</p>
      </div>
    )
  }
  
  // 使用类型断言来处理不同版本的配置
  const screenConfig = config as ScreenConfig
  const productionConfig = config as ScreenConfigProduction
  
  const renderScreen = () => {
    // Production 版本的特殊组件
    if (currentVersion === 'production') {
      switch (config.type) {
        case 'combined_welcome_goal':
          return <CombinedWelcomeGoalScreen config={productionConfig} />
        case 'combined_height_weight':
          return <CombinedHeightWeightScreen config={productionConfig} />
        case 'introduction':
          return <IntroductionScreen config={screenConfig} />
      }
    }
    
    // 通用组件渲染
    switch (config.type) {
      case 'introduction':
        return <IntroductionScreen config={screenConfig} />
      case 'launch':
        return <LaunchScreen config={screenConfig} />
      case 'welcome':
        return <WelcomeScreen config={screenConfig} />
      case 'question_single':
        return <QuestionSingleScreen config={screenConfig} />
      case 'question_multi':
        return <QuestionMultiScreen config={screenConfig} />
      case 'number_input':
        return <NumberInputScreen config={screenConfig} />
      case 'text_input':
        return <TextInputScreen config={screenConfig} />
      case 'transition':
        return <TransitionScreen config={screenConfig} />
      case 'loading':
        return <LoadingScreen config={screenConfig} />
      case 'result':
        return <ResultScreen config={screenConfig} />
      case 'value_prop':
        return <ValuePropScreen config={screenConfig} />
      case 'game_scan':
        return <ScanGameScreen config={screenConfig} />
      case 'game_spin':
        return <SpinGameScreen config={screenConfig} />
      case 'permission':
        return <PermissionScreen config={screenConfig} />
      case 'paywall':
        return <PaywallScreen config={screenConfig} />
      case 'celebration':
        return <CelebrationScreen config={screenConfig} />
      case 'account':
        return <AccountScreen config={screenConfig} />
      case 'soft_commit':
        return <SoftCommitScreen config={screenConfig as Parameters<typeof SoftCommitScreen>[0]['config']} />
      default:
        return <TransitionScreen config={screenConfig} />
    }
  }
  
  return (
    <AnimatePresence mode="wait" custom={direction}>
      <motion.div
        key={currentStep}
        custom={direction}
        variants={pageVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        className="h-full"
      >
        {renderScreen()}
      </motion.div>
    </AnimatePresence>
  )
}
