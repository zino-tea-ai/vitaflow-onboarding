'use client'

import { motion } from 'framer-motion'
import { Check } from 'lucide-react'

interface Phase {
  id: string
  name: string
  icon?: string
}

interface PhaseProgressProps {
  currentPhase: string
  phases: Phase[]
  currentStep: number
  totalSteps: number
  showRemaining?: boolean
  className?: string
}

/**
 * 阶段化进度组件
 * 显示当前阶段、里程碑、剩余步骤
 */
export function PhaseProgress({
  currentPhase,
  phases,
  currentStep,
  totalSteps,
  showRemaining = true,
  className = ''
}: PhaseProgressProps) {
  const currentPhaseIndex = phases.findIndex(p => p.id === currentPhase)
  const progress = (currentStep / totalSteps) * 100
  const remaining = totalSteps - currentStep

  return (
    <div className={`w-full ${className}`}>
      {/* 阶段指示器 */}
      <div className="flex items-center justify-between mb-4 px-6">
        {phases.map((phase, index) => {
          const isActive = phase.id === currentPhase
          const isCompleted = index < currentPhaseIndex
          const isUpcoming = index > currentPhaseIndex

          return (
            <div key={phase.id} className="flex items-center flex-1">
              {/* 阶段点 */}
              <div className="flex flex-col items-center">
                <motion.div
                  className={`
                    w-8 h-8 rounded-full flex items-center justify-center
                    ${isCompleted 
                      ? 'bg-[#2B2735] text-white' 
                      : isActive 
                        ? 'bg-[#2B2735] text-white scale-110' 
                        : 'bg-gray-200 text-gray-400'
                    }
                  `}
                  animate={{
                    scale: isActive ? 1.1 : 1
                  }}
                  transition={{ duration: 0.2 }}
                >
                  {isCompleted ? (
                    <Check size={16} />
                  ) : (
                    <span className="text-xs font-semibold">{index + 1}</span>
                  )}
                </motion.div>
                {/* 阶段名称 */}
                <span
                  className={`
                    mt-2 text-xs font-medium text-center
                    ${isActive ? 'text-[#2B2735]' : 'text-gray-400'}
                  `}
                  style={{ fontFamily: 'var(--font-outfit)' }}
                >
                  {phase.name}
                </span>
              </div>
              
              {/* 连接线 */}
              {index < phases.length - 1 && (
                <div
                  className={`
                    flex-1 h-0.5 mx-2 -mt-4
                    ${isCompleted ? 'bg-[#2B2735]' : 'bg-gray-200'}
                  `}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* 进度条和剩余步骤 */}
      <div className="px-6">
        <div className="flex items-center justify-between mb-2">
          <span
            className="text-sm font-medium"
            style={{ color: '#999999', fontFamily: 'var(--font-outfit)' }}
          >
            Phase {currentPhaseIndex + 1} of {phases.length}
          </span>
          {showRemaining && remaining > 0 && (
            <span
              className="text-sm font-medium"
              style={{ color: '#999999', fontFamily: 'var(--font-outfit)' }}
            >
              {remaining} {remaining === 1 ? 'step' : 'steps'} remaining
            </span>
          )}
        </div>
        
        {/* 进度条 */}
        <div
          className="relative h-1 rounded-full overflow-hidden"
          style={{ background: 'rgba(43, 39, 53, 0.1)' }}
        >
          <motion.div
            className="absolute left-0 top-0 h-full rounded-full"
            style={{ background: '#2B2735' }}
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{
              duration: 0.5,
              ease: [0.25, 0.46, 0.45, 0.94]
            }}
          />
        </div>
      </div>
    </div>
  )
}

/**
 * 里程碑组件
 * 完成阶段时显示徽章动画
 */
interface MilestoneProps {
  phaseName: string
  onComplete?: () => void
}

export function Milestone({ phaseName, onComplete }: MilestoneProps) {
  return (
    <motion.div
      className="flex flex-col items-center justify-center p-6"
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      transition={{ duration: 0.5 }}
      onAnimationComplete={onComplete}
    >
      <motion.div
        className="w-16 h-16 rounded-full bg-[#2B2735] flex items-center justify-center mb-4"
        animate={{
          scale: [1, 1.2, 1],
          rotate: [0, 10, -10, 0]
        }}
        transition={{
          duration: 0.5,
          ease: 'easeOut'
        }}
      >
        <Check size={32} className="text-white" />
      </motion.div>
      <h3
        className="text-lg font-semibold mb-2"
        style={{ color: '#2B2735', fontFamily: 'var(--font-outfit)' }}
      >
        Phase Complete! 🎉
      </h3>
      <p
        className="text-sm text-center"
        style={{ color: '#999999', fontFamily: 'var(--font-outfit)' }}
      >
        {phaseName} completed
      </p>
    </motion.div>
  )
}
