'use client'

import { motion } from 'framer-motion'
import { colors } from '../../lib/design-tokens'

interface ProgressBarProps {
  current: number
  total: number
  showLabel?: boolean
}

/**
 * 简洁进度条
 * 
 * - Slate-900 填充
 * - Slate-200 背景
 * - 无渐变/光效
 */
export function ProgressBar({ current, total, showLabel = false }: ProgressBarProps) {
  const progress = (current / total) * 100
  
  return (
    <div className="w-full px-6 py-3">
      {/* 进度条容器 */}
      <div 
        className="relative h-[3px] rounded-full overflow-hidden"
        style={{ background: colors.slate[200] }}
      >
        {/* 进度填充 */}
        <motion.div
          className="absolute left-0 top-0 h-full rounded-full"
          style={{ background: colors.slate[900] }}
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ 
            type: 'spring',
            stiffness: 300,
            damping: 30,
            mass: 1
          }}
        />
      </div>
      
      {/* 标签 - 可选 */}
      {showLabel && (
        <div className="flex justify-between items-center mt-2">
          <motion.span 
            className="text-[11px] font-medium"
            style={{ color: colors.text.secondary, fontFamily: 'var(--font-outfit)' }}
            key={current}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            Step {current} of {total}
          </motion.span>
        </div>
      )}
    </div>
  )
}

// 分页点样式
export function ProgressDots({ current, total }: { current: number; total: number }) {
  const visibleCount = Math.min(5, total)
  const startIndex = Math.max(0, Math.min(current - 3, total - visibleCount))
  
  return (
    <div className="flex items-center justify-center gap-[6px] py-4">
      {Array.from({ length: visibleCount }).map((_, i) => {
        const index = startIndex + i + 1
        const isActive = index === current
        const isPast = index < current
        
        return (
          <motion.div
            key={index}
            className="rounded-full transition-all duration-300"
            style={{
              width: isActive ? '20px' : '5px',
              height: '5px',
              background: isActive 
                ? colors.slate[900] 
                : isPast 
                  ? colors.slate[400] 
                  : colors.slate[200]
            }}
            initial={false}
            animate={{
              scale: isActive ? 1 : 0.9,
              opacity: isActive ? 1 : isPast ? 0.7 : 0.4
            }}
          />
        )
      })}
    </div>
  )
}
