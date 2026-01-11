'use client'

import { motion } from 'framer-motion'
import { useOnboardingStore } from '../../store/onboarding-store'
import { useABTestStore } from '../../store/ab-test-store'
import { ScreenConfig } from '../../data/screens-config'
import { ScreenConfigProduction } from '../../data/screens-config-production'
import { Button, BackButton, SkipButton } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { Mascot } from '../character'
import { colors, shadows, cardBorder } from '../../lib/design-tokens'

interface ValuePropScreenProps {
  config: ScreenConfig | ScreenConfigProduction
}

export function ValuePropScreen({ config }: ValuePropScreenProps) {
  const { nextStep, prevStep, currentStep, totalSteps } = useOnboardingStore()
  const { characterStyle } = useABTestStore()
  
  const productionConfig = config as ScreenConfigProduction
  const valuePropType = productionConfig.valuePropType
  
  // ========== Progress Tracking 页 ==========
  // 构图：角色居中 + 左侧图表（与 AI Scan 镜像）
  if (valuePropType === 'progress_tracking') {
    return (
      <div 
        className="h-full flex flex-col"
        style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}
      >
        <ProgressBar current={currentStep} total={totalSteps} />
        
        <div className="flex items-center justify-between px-5 py-2">
          <BackButton onClick={prevStep} />
          <SkipButton onClick={nextStep} />
        </div>
        
        {/* 主视觉区 - 无宽高限制 */}
        <div className="flex-1 flex flex-col items-center justify-center px-6">
          <motion.div
            className="relative"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          >
            {/* 背景 blob - 金色，200x140 与 AI Scan 一致 */}
            <motion.div
              className="absolute"
              style={{
                width: '200px',
                height: '140px',
                background: `linear-gradient(135deg, #FBBF24 0%, #F59E0B 50%, #D97706 100%)`,
                borderRadius: '60% 40% 50% 50% / 50% 50% 40% 60%',
                left: '50%',
                top: '50%',
                transform: 'translate(-50%, -30%)',
              }}
              animate={{
                borderRadius: [
                  '60% 40% 50% 50% / 50% 50% 40% 60%',
                  '50% 60% 40% 60% / 60% 40% 60% 40%',
                  '60% 40% 50% 50% / 50% 50% 40% 60%',
                ],
              }}
              transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
            />
            
            {/* Vita - 与 AI Scan 完全相同的 scale 和入场动画 */}
            <motion.div 
              className="relative z-10"
              style={{ transform: 'scale(2.2) translateY(-10px)' }}
              initial={{ scale: 1.8 }}
              animate={{ scale: 2.2 }}
              transition={{ delay: 0.2, type: 'spring', stiffness: 150 }}
            >
              <Mascot style={characterStyle} state="cheering" size="xl" />
            </motion.div>
            
            {/* 3D 装饰物 - 左侧图表卡片（与 AI Scan 相机镜像） */}
            <motion.div
              className="absolute z-20"
              style={{ left: '-90px', top: '10px' }}
              initial={{ opacity: 0, x: -30, rotate: -15 }}
              animate={{ opacity: 1, x: 0, rotate: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
            >
              <div 
                className="w-20 h-20 rounded-[16px] flex items-center justify-center relative"
                style={{ 
                  background: 'linear-gradient(145deg, #FEF3C7 0%, #FDE68A 100%)',
                  boxShadow: '0 20px 40px rgba(251, 191, 36, 0.35), inset 0 1px 0 rgba(255,255,255,0.5)',
                  transform: 'perspective(500px) rotateY(15deg) rotateX(5deg)',
                }}
              >
                {/* 上升曲线 */}
                <svg width="48" height="48" viewBox="0 0 48 48">
                  <motion.path
                    d="M6 38 L18 28 L28 32 L42 10"
                    fill="none"
                    stroke="#F59E0B"
                    strokeWidth="3"
                    strokeLinecap="round"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 0.8, duration: 0.8 }}
                  />
                  <motion.circle 
                    cx="42" cy="10" r="4" 
                    fill="#F59E0B"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 1.4, type: 'spring' }}
                  />
                </svg>
              </div>
            </motion.div>
          </motion.div>
          
          {/* 标题区 - mt-20 与 AI Scan 一致 */}
          <motion.h1
            className="text-[34px] font-bold tracking-[-0.8px] text-center mt-20"
            style={{ color: colors.text.primary, lineHeight: 1.1 }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            Every step counts
          </motion.h1>
          
          <motion.p
            className="text-[15px] text-center leading-[1.6] mt-5 px-6 max-w-[340px]"
            style={{ color: colors.text.secondary }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
          >
            Track your journey with streaks, milestones, and achievements. Watch yourself level up!
          </motion.p>
        </div>
        
        <motion.div 
          className="px-5 py-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
        >
          <Button fullWidth size="lg" onClick={nextStep}>Continue</Button>
        </motion.div>
      </div>
    )
  }
  
  // ========== Privacy 页 ==========
  // 构图：角色居中 + 右侧盾牌（与 AI Scan 类似位置但不同物件）
  if (valuePropType === 'privacy') {
    return (
      <div 
        className="h-full flex flex-col"
        style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}
      >
        <ProgressBar current={currentStep} total={totalSteps} />
        
        <div className="flex items-center justify-between px-5 py-2">
          <BackButton onClick={prevStep} />
          <SkipButton onClick={nextStep} />
        </div>
        
        {/* 主视觉区 - 无宽高限制 */}
        <div className="flex-1 flex flex-col items-center justify-center px-6">
          <motion.div
            className="relative"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          >
            {/* 背景 blob - 绿色，200x140 与 AI Scan 一致 */}
            <motion.div
              className="absolute"
              style={{
                width: '200px',
                height: '140px',
                background: `linear-gradient(135deg, ${colors.accent.primary} 0%, #34D399 100%)`,
                borderRadius: '60% 40% 50% 50% / 50% 50% 40% 60%',
                left: '50%',
                top: '50%',
                transform: 'translate(-50%, -30%)',
              }}
              animate={{
                borderRadius: [
                  '60% 40% 50% 50% / 50% 50% 40% 60%',
                  '50% 60% 40% 60% / 60% 40% 60% 40%',
                  '60% 40% 50% 50% / 50% 50% 40% 60%',
                ],
              }}
              transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
            />
            
            {/* Vita - 与 AI Scan 完全相同的 scale 和入场动画 */}
            <motion.div 
              className="relative z-10"
              style={{ transform: 'scale(2.2) translateY(-10px)' }}
              initial={{ scale: 1.8 }}
              animate={{ scale: 2.2 }}
              transition={{ delay: 0.2, type: 'spring', stiffness: 150 }}
            >
              <Mascot style={characterStyle} state="proud" size="xl" />
            </motion.div>
            
            {/* 3D 装饰物 - 右侧盾牌（与 AI Scan 相机相同位置） */}
            <motion.div
              className="absolute z-20"
              style={{ right: '-90px', top: '10px' }}
              initial={{ opacity: 0, x: 30, rotate: 15 }}
              animate={{ opacity: 1, x: 0, rotate: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
            >
              <div 
                className="w-20 h-20 flex items-center justify-center relative"
                style={{ 
                  background: 'linear-gradient(145deg, #22C55E 0%, #16A34A 100%)',
                  borderRadius: '50% 50% 50% 50% / 30% 30% 70% 70%',
                  boxShadow: '0 20px 40px rgba(34, 197, 94, 0.4), inset 0 1px 0 rgba(255,255,255,0.3)',
                  transform: 'perspective(500px) rotateY(-15deg) rotateX(5deg)',
                }}
              >
                {/* 勾号 */}
                <motion.svg 
                  width="36" height="36" viewBox="0 0 24 24"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.8, type: 'spring' }}
                >
                  <motion.path
                    d="M5 13l4 4L19 7"
                    fill="none"
                    stroke="white"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 1, duration: 0.5 }}
                  />
                </motion.svg>
              </div>
            </motion.div>
          </motion.div>
          
          {/* 标题区 - mt-20 与 AI Scan 一致 */}
          <motion.h1
            className="text-[34px] font-bold tracking-[-0.8px] text-center mt-20"
            style={{ color: colors.text.primary, lineHeight: 1.1 }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            We've got your back
          </motion.h1>
          
          <motion.p
            className="text-[15px] text-center leading-[1.6] mt-5 px-6 max-w-[340px]"
            style={{ color: colors.text.secondary }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
          >
            Your data is encrypted end-to-end. We never share or sell your information. Ever.
          </motion.p>
        </div>
        
        <motion.div 
          className="px-5 py-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
        >
          <Button fullWidth size="lg" onClick={nextStep}>Continue</Button>
        </motion.div>
      </div>
    )
  }
  
  // ========== AI Scan 页 ==========
  // 构图：角色 + 哑铃式3D物体组合（参考Brilliant第一张）
  // 角色和物体融为一体，像一个完整的3D渲染插画
  if (valuePropType === 'ai_scan') {
    return (
      <div 
        className="h-full flex flex-col"
        style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}
      >
        <ProgressBar current={currentStep} total={totalSteps} />
        
        <div className="flex items-center justify-between px-5 py-2">
          <BackButton onClick={prevStep} />
          <SkipButton onClick={nextStep} />
        </div>
        
        {/* 主视觉区 - 一体化插画 */}
        <div className="flex-1 flex flex-col items-center justify-center px-6">
          <motion.div
            className="relative"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          >
            {/* 背景形状 - 有机的blob，角色站在上面 */}
            <motion.div
              className="absolute"
              style={{
                width: '200px',
                height: '140px',
                background: `linear-gradient(135deg, ${colors.accent.primary} 0%, #34D399 100%)`,
                borderRadius: '60% 40% 50% 50% / 50% 50% 40% 60%',
                left: '50%',
                top: '50%',
                transform: 'translate(-50%, -30%)',
                filter: 'blur(0px)',
              }}
              animate={{
                borderRadius: [
                  '60% 40% 50% 50% / 50% 50% 40% 60%',
                  '50% 60% 40% 60% / 60% 40% 60% 40%',
                  '60% 40% 50% 50% / 50% 50% 40% 60%',
                ],
              }}
              transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
            />
            
            {/* 角色 - 超大，站在blob上 */}
            <motion.div 
              className="relative z-10"
              style={{ transform: 'scale(2.2) translateY(-10px)' }}
              initial={{ scale: 1.8 }}
              animate={{ scale: 2.2 }}
              transition={{ delay: 0.2, type: 'spring', stiffness: 150 }}
            >
              <Mascot style={characterStyle} state="excited" size="xl" />
            </motion.div>
            
            {/* 3D 哑铃式物体 - 相机，与角色形成组合 */}
            <motion.div
              className="absolute z-20"
              style={{ right: '-90px', top: '10px' }}
              initial={{ opacity: 0, x: 30, rotate: 15 }}
              animate={{ opacity: 1, x: 0, rotate: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
            >
              {/* 3D相机 - 更大更有质感 */}
              <div 
                className="w-20 h-20 rounded-[16px] flex items-center justify-center relative"
                style={{ 
                  background: 'linear-gradient(145deg, #4B5563 0%, #1F2937 100%)',
                  boxShadow: '0 20px 40px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.15)',
                  transform: 'perspective(500px) rotateY(-15deg) rotateX(5deg)',
                }}
              >
                {/* 镜头 */}
                <div 
                  className="w-12 h-12 rounded-full"
                  style={{ 
                    background: 'radial-gradient(circle at 30% 30%, #374151 0%, #111827 100%)',
                    boxShadow: 'inset 0 4px 8px rgba(0,0,0,0.6), 0 2px 0 rgba(255,255,255,0.1)',
                  }}
                >
                  <motion.div 
                    className="w-full h-full rounded-full flex items-center justify-center"
                    animate={{ scale: [1, 1.05, 1] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <div 
                      className="w-6 h-6 rounded-full"
                      style={{ 
                        background: `radial-gradient(circle at 40% 40%, ${colors.accent.primary}, #059669)`,
                        boxShadow: `0 0 20px ${colors.accent.primary}80`,
                      }}
                    />
                  </motion.div>
                </div>
                {/* 快门按钮 */}
                <div 
                  className="absolute top-1 right-2 w-3 h-3 rounded-full"
                  style={{ background: '#DC2626', boxShadow: '0 0 8px #DC262680' }}
                />
              </div>
            </motion.div>
          </motion.div>
          
          {/* 标题区 - 大字体，放更下面 */}
          <motion.h1
            className="text-[34px] font-bold tracking-[-0.8px] text-center mt-20"
            style={{ color: colors.text.primary, lineHeight: 1.1 }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            Scan food in seconds
          </motion.h1>
          
          <motion.p
            className="text-[15px] text-center leading-[1.6] mt-5 px-6 max-w-[340px]"
            style={{ color: colors.text.secondary }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
          >
            Point your camera at any meal. Our AI instantly recognizes ingredients and calculates calories, macros, and more.
          </motion.p>
        </div>
        
        <motion.div 
          className="px-5 py-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
        >
          <Button fullWidth size="lg" onClick={nextStep}>Continue</Button>
        </motion.div>
      </div>
    )
  }
  
  // ========== Personalized 页 ==========
  // 构图：角色 + 散落的卡片（参考Brilliant第二张）
  // 卡片以不同角度散开，形成深度感
  if (valuePropType === 'personalized') {
    return (
      <div 
        className="h-full flex flex-col"
        style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}
      >
        <ProgressBar current={currentStep} total={totalSteps} />
        
        <div className="flex items-center justify-between px-5 py-2">
          <BackButton onClick={prevStep} />
          <SkipButton onClick={nextStep} />
        </div>
        
        {/* 主视觉区 */}
        <div className="flex-1 flex flex-col items-center justify-center px-6">
          <motion.div
            className="relative w-full max-w-[340px] h-[300px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
          >
            {/* 卡片1 - 左上，大角度倾斜 - Figma 规范 */}
            <motion.div
              className="absolute w-[72px] h-[72px] rounded-[12px] flex items-center justify-center"
              style={{ 
                background: '#FFFFFF',
                boxShadow: shadows.card,
                border: cardBorder.default,
                left: '8%',
                top: '5%',
              }}
              initial={{ opacity: 0, y: -30, rotate: -25 }}
              animate={{ opacity: 1, y: 0, rotate: -18 }}
              transition={{ delay: 0.15, duration: 0.5 }}
            >
              <span className="text-[32px]">🔬</span>
            </motion.div>
            
            {/* 卡片2 - 右上 - Figma 规范 */}
            <motion.div
              className="absolute w-[80px] h-[72px] rounded-[12px] overflow-hidden"
              style={{ 
                background: '#FFFFFF',
                boxShadow: shadows.card,
                border: cardBorder.default,
                right: '5%',
                top: '0%',
              }}
              initial={{ opacity: 0, y: -30, rotate: 20 }}
              animate={{ opacity: 1, y: 0, rotate: 12 }}
              transition={{ delay: 0.25, duration: 0.5 }}
            >
              <div className="w-full h-full flex items-center justify-center p-2">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-400 via-orange-500 to-red-500 flex items-center justify-center">
                  <span className="text-white text-lg">🌍</span>
                </div>
              </div>
            </motion.div>
            
            {/* 角色 - 中心偏左，带背景blob */}
            <motion.div
              className="absolute z-10"
              style={{ left: '12%', top: '28%' }}
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.1, type: 'spring', stiffness: 150 }}
            >
              {/* 背景blob */}
              <div
                className="absolute"
                style={{
                  width: '120px',
                  height: '100px',
                  background: `linear-gradient(160deg, ${colors.accent.primary} 0%, #34D399 100%)`,
                  borderRadius: '50% 50% 50% 50% / 60% 60% 40% 40%',
                  left: '50%',
                  top: '50%',
                  transform: 'translate(-50%, -40%)',
                  zIndex: -1,
                }}
              />
              <div style={{ transform: 'scale(2)' }}>
                <Mascot style={characterStyle} state="happy" size="xl" />
              </div>
            </motion.div>
            
            {/* 卡片3 - 右侧中间，UI界面 - Figma 规范 */}
            <motion.div
              className="absolute w-[100px] h-[80px] rounded-[12px] overflow-hidden"
              style={{ 
                background: '#FFFFFF',
                boxShadow: shadows.card,
                border: cardBorder.default,
                right: '0%',
                top: '35%',
              }}
              initial={{ opacity: 0, x: 30, rotate: 8 }}
              animate={{ opacity: 1, x: 0, rotate: 5 }}
              transition={{ delay: 0.35, duration: 0.5 }}
            >
              <div className="p-2.5">
                <div className="flex items-center gap-1.5 mb-2">
                  <div className="w-4 h-4 rounded-full" style={{ background: colors.accent.primary }} />
                  <div className="w-10 h-1.5 rounded-full" style={{ background: colors.slate[200] }} />
                </div>
                <div className="space-y-1.5">
                  <div className="w-full h-1.5 rounded-full" style={{ background: colors.slate[100] }} />
                  <div className="w-4/5 h-1.5 rounded-full" style={{ background: colors.slate[100] }} />
                  <div className="w-3/5 h-1.5 rounded-full" style={{ background: colors.slate[100] }} />
                </div>
              </div>
            </motion.div>
            
            {/* 卡片4 - 底部中间 - Figma 规范 */}
            <motion.div
              className="absolute w-[110px] h-[70px] rounded-[12px] overflow-hidden"
              style={{ 
                background: '#FFFFFF',
                boxShadow: shadows.card,
                border: cardBorder.default,
                left: '50%',
                bottom: '0%',
                transform: 'translateX(-50%)',
              }}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.45, duration: 0.5 }}
            >
              <div className="p-2.5 flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: colors.slate[100] }}>
                  <span className="text-lg">📈</span>
                </div>
                <div className="flex-1">
                  <div className="text-[10px] font-medium mb-1" style={{ color: colors.text.primary }}>Progress</div>
                  <div className="h-2 rounded-full overflow-hidden" style={{ background: colors.slate[100] }}>
                    <motion.div 
                      className="h-full rounded-full"
                      style={{ background: colors.accent.primary }}
                      initial={{ width: 0 }}
                      animate={{ width: '75%' }}
                      transition={{ delay: 0.8, duration: 0.6 }}
                    />
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
          
          {/* 标题 - 放更下面 */}
          <motion.h1
            className="text-[34px] font-bold tracking-[-0.8px] text-center mt-6"
            style={{ color: colors.text.primary, lineHeight: 1.1 }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.55 }}
          >
            You'll fit right in
          </motion.h1>
          
          <motion.p
            className="text-[15px] text-center leading-[1.6] mt-5 px-6 max-w-[340px]"
            style={{ color: colors.text.secondary }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.65 }}
          >
            Millions of users trust VitaFlow to reach their health goals with personalized AI guidance.
          </motion.p>
        </div>
        
        <motion.div 
          className="px-5 py-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.75 }}
        >
          <Button fullWidth size="lg" onClick={nextStep}>Continue</Button>
        </motion.div>
      </div>
    )
  }
  
  // 默认
  return (
    <div className="h-full flex flex-col" style={{ background: colors.background.primary, fontFamily: 'var(--font-outfit)' }}>
      <ProgressBar current={currentStep} total={totalSteps} />
      <div className="flex items-center justify-between px-5 py-2">
        <BackButton onClick={prevStep} />
        <SkipButton onClick={nextStep} />
      </div>
      <div className="flex-1 flex flex-col items-center justify-center px-8">
        <div style={{ transform: 'scale(2)' }}>
          <Mascot style={characterStyle} state="explaining" size="xl" />
        </div>
        <h1 className="text-[34px] font-bold text-center mt-10" style={{ color: colors.text.primary }}>{config.title}</h1>
        <p className="text-[15px] text-center mt-4" style={{ color: colors.text.secondary }}>{config.subtitle}</p>
      </div>
      <div className="px-5 py-6"><Button fullWidth size="lg" onClick={nextStep}>Continue</Button></div>
    </div>
  )
}
