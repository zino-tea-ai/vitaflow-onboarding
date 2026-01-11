'use client'

import { motion } from 'framer-motion'
import { Check } from 'lucide-react'
import { celebrationAnimations } from '../../lib/motion-config'

interface ProgressMilestoneProps {
  phaseName: string
  phaseNumber: number
  totalPhases: number
  onComplete?: () => void
  className?: string
}

/**
 * 进度里程碑组件
 * 完成阶段时显示徽章动画
 */
export function ProgressMilestone({
  phaseName,
  phaseNumber,
  totalPhases,
  onComplete,
  className = ''
}: ProgressMilestoneProps) {
  return (
    <motion.div
      className={`flex flex-col items-center justify-center p-6 ${className}`}
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      transition={{ duration: 0.5 }}
      onAnimationComplete={onComplete}
    >
      <motion.div
        className="w-20 h-20 rounded-full bg-[#2B2735] flex items-center justify-center mb-4 shadow-lg"
        animate={{
          scale: celebrationAnimations.badge.scale,
          rotate: celebrationAnimations.badge.rotate
        }}
        transition={celebrationAnimations.badge.transition}
      >
        <Check size={40} className="text-white" />
      </motion.div>
      <h3
        className="text-xl font-semibold mb-2"
        style={{ color: '#2B2735', fontFamily: 'var(--font-outfit)' }}
      >
        Phase {phaseNumber} Complete! 🎉
      </h3>
      <p
        className="text-sm text-center mb-2"
        style={{ color: '#999999', fontFamily: 'var(--font-outfit)' }}
      >
        {phaseName}
      </p>
      <p
        className="text-xs text-center"
        style={{ color: '#999999', fontFamily: 'var(--font-outfit)' }}
      >
        {phaseNumber} of {totalPhases} phases completed
      </p>
    </motion.div>
  )
}

/**
 * 社会证明组件
 * 显示用户数、评价等
 */
interface SocialProofProps {
  userCount?: number
  rating?: number
  testimonial?: string
  className?: string
}

export function SocialProof({
  userCount = 50000,
  rating = 4.8,
  testimonial,
  className = ''
}: SocialProofProps) {
  return (
    <motion.div
      className={`p-4 bg-white rounded-[16px] ${className}`}
      style={{ boxShadow: '0px 0px 2px 0px #E8E8E8' }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {userCount > 0 && (
        <div className="flex items-center gap-2 mb-3">
          <div className="flex -space-x-2">
            {[...Array(3)].map((_, i) => (
              <div
                key={i}
                className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 border-2 border-white"
              />
            ))}
          </div>
          <p
            className="text-sm font-medium"
            style={{ color: '#2B2735', fontFamily: 'var(--font-outfit)' }}
          >
            Join {userCount.toLocaleString()}+ people transforming their health
          </p>
        </div>
      )}
      
      {rating > 0 && (
        <div className="flex items-center gap-2">
          <div className="flex">
            {[...Array(5)].map((_, i) => (
              <span key={i} className="text-yellow-400">⭐</span>
            ))}
          </div>
          <p
            className="text-sm"
            style={{ color: '#999999', fontFamily: 'var(--font-outfit)' }}
          >
            {rating} rating from {Math.floor(userCount * 0.1).toLocaleString()}+ reviews
          </p>
        </div>
      )}
      
      {testimonial && (
        <motion.p
          className="mt-3 text-sm italic"
          style={{ color: '#2B2735', fontFamily: 'var(--font-outfit)' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          "{testimonial}"
        </motion.p>
      )}
    </motion.div>
  )
}

/**
 * 损失厌恶组件
 * 展示"不使用 vs 使用"的对比
 */
interface LossAversionProps {
  withoutTitle: string
  withoutDescription: string
  withTitle: string
  withDescription: string
  className?: string
}

export function LossAversion({
  withoutTitle,
  withoutDescription,
  withTitle,
  withDescription,
  className = ''
}: LossAversionProps) {
  return (
    <motion.div
      className={`grid grid-cols-2 gap-4 ${className}`}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* 不使用 */}
      <motion.div
        className="p-4 bg-gray-100 rounded-[16px] border-2 border-gray-200"
        whileHover={{ scale: 1.02 }}
      >
        <div className="text-4xl mb-2">😩</div>
        <h4
          className="text-base font-semibold mb-1"
          style={{ color: '#2B2735', fontFamily: 'var(--font-outfit)' }}
        >
          {withoutTitle}
        </h4>
        <p
          className="text-sm"
          style={{ color: '#999999', fontFamily: 'var(--font-outfit)' }}
        >
          {withoutDescription}
        </p>
      </motion.div>
      
      {/* 使用 */}
      <motion.div
        className="p-4 bg-white rounded-[16px] border-2 border-[#2B2735] shadow-lg"
        whileHover={{ scale: 1.02 }}
      >
        <div className="text-4xl mb-2">🚀</div>
        <h4
          className="text-base font-semibold mb-1"
          style={{ color: '#2B2735', fontFamily: 'var(--font-outfit)' }}
        >
          {withTitle}
        </h4>
        <p
          className="text-sm"
          style={{ color: '#999999', fontFamily: 'var(--font-outfit)' }}
        >
          {withDescription}
        </p>
      </motion.div>
    </motion.div>
  )
}
