/**
 * ScreenSimulator - 虚拟屏幕模拟器
 * 展示 AI 操作的虚拟屏幕区域
 * 
 * 功能：
 * - 模拟浏览器/桌面界面
 * - 元素高亮
 * - 屏幕边缘光效
 * - 步骤进度指示
 */

import { motion, AnimatePresence } from 'motion/react'
import { cn } from '@/lib/utils'
import { AICursor, type CursorPosition, type CursorState } from './AICursor'

// 高亮区域
export interface HighlightRect {
  x: number
  y: number
  width: number
  height: number
  label?: string
}

// 屏幕光效状态
export type GlowState = 'off' | 'low' | 'medium' | 'high' | 'success' | 'error'

// 步骤状态
export interface StepInfo {
  current: number
  total: number
  status: 'pending' | 'active' | 'completed' | 'error'
}

export interface ScreenSimulatorProps {
  /** 光标位置 */
  cursorPosition: CursorPosition
  /** 光标状态 */
  cursorState?: CursorState
  /** 高亮区域 */
  highlight?: HighlightRect | null
  /** 屏幕光效 */
  glowState?: GlowState
  /** 当前步骤 */
  stepInfo?: StepInfo
  /** 是否显示光标 */
  showCursor?: boolean
  /** 模拟 URL */
  simulatedUrl?: string
  /** 屏幕标题 */
  title?: string
  className?: string
}

// 光效颜色映射
const GLOW_COLORS: Record<GlowState, string> = {
  off: 'transparent',
  low: 'rgba(99, 102, 241, 0.1)',
  medium: 'rgba(99, 102, 241, 0.2)',
  high: 'rgba(99, 102, 241, 0.35)',
  success: 'rgba(16, 185, 129, 0.3)',
  error: 'rgba(239, 68, 68, 0.3)',
}

// 光效 box-shadow
const GLOW_SHADOWS: Record<GlowState, string> = {
  off: 'none',
  low: 'inset 0 0 60px rgba(99, 102, 241, 0.1)',
  medium: 'inset 0 0 100px rgba(99, 102, 241, 0.2)',
  high: 'inset 0 0 150px rgba(99, 102, 241, 0.35)',
  success: 'inset 0 0 120px rgba(16, 185, 129, 0.3)',
  error: 'inset 0 0 120px rgba(239, 68, 68, 0.3)',
}

export function ScreenSimulator({
  cursorPosition,
  cursorState = 'idle',
  highlight,
  glowState = 'off',
  stepInfo,
  showCursor = true,
  simulatedUrl = 'https://example.com',
  title = 'AI 操作视图',
  className,
}: ScreenSimulatorProps) {
  return (
    <div className={cn('relative flex flex-col h-full', className)}>
      {/* 模拟浏览器窗口 */}
      <div className="flex-1 flex flex-col bg-[#0a0a0f] rounded-xl overflow-hidden border border-white/[0.08]">
        {/* 窗口标题栏 */}
        <div className="flex items-center gap-2 px-4 py-2.5 bg-[#111] border-b border-white/[0.06]">
          {/* 窗口按钮 */}
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
          </div>
          
          {/* URL 栏 */}
          <div className="flex-1 mx-4">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1a1a1a] rounded-lg">
              <svg className="w-3.5 h-3.5 text-white/40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
              </svg>
              <span className="text-xs text-white/50 font-mono truncate">
                {simulatedUrl}
              </span>
            </div>
          </div>
          
          {/* 标题 */}
          <span className="text-xs text-white/40">{title}</span>
        </div>
        
        {/* 屏幕内容区域 */}
        <div className="relative flex-1 bg-[#0d0d12] overflow-hidden">
          {/* 屏幕光效 */}
          <motion.div
            className="absolute inset-0 pointer-events-none"
            animate={{
              boxShadow: GLOW_SHADOWS[glowState],
            }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
          />
          
          {/* 四角光效 */}
          <AnimatePresence>
            {glowState !== 'off' && (
              <>
                {['top-left', 'top-right', 'bottom-left', 'bottom-right'].map((pos) => (
                  <motion.div
                    key={pos}
                    className={cn(
                      'absolute w-32 h-32 pointer-events-none',
                      pos === 'top-left' && 'top-0 left-0',
                      pos === 'top-right' && 'top-0 right-0',
                      pos === 'bottom-left' && 'bottom-0 left-0',
                      pos === 'bottom-right' && 'bottom-0 right-0',
                    )}
                    style={{
                      background: `radial-gradient(ellipse at ${pos.replace('-', ' ')}, ${GLOW_COLORS[glowState]}, transparent 70%)`,
                    }}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{
                      opacity: [0.2, 0.4, 0.2],
                      scale: [1, 1.1, 1],
                    }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                      ease: 'easeInOut',
                    }}
                  />
                ))}
              </>
            )}
          </AnimatePresence>
          
          {/* 模拟内容占位 */}
          <div className="absolute inset-0 p-4 flex flex-col gap-3">
            {/* 模拟标题 */}
            <div className="h-4 w-32 bg-white/5 rounded" />
            <div className="h-3 w-48 bg-white/3 rounded" />
            
            {/* 模拟内容块 */}
            <div className="flex gap-3 mt-4">
              <div className="w-16 h-16 bg-white/5 rounded-lg" />
              <div className="flex-1 flex flex-col gap-2">
                <div className="h-3 w-3/4 bg-white/5 rounded" />
                <div className="h-3 w-1/2 bg-white/3 rounded" />
                <div className="h-3 w-2/3 bg-white/3 rounded" />
              </div>
            </div>
            
            {/* 更多模拟内容 */}
            <div className="flex gap-3 mt-2">
              <div className="w-16 h-16 bg-white/5 rounded-lg" />
              <div className="flex-1 flex flex-col gap-2">
                <div className="h-3 w-2/3 bg-white/5 rounded" />
                <div className="h-3 w-1/3 bg-white/3 rounded" />
              </div>
            </div>
            
            {/* 模拟按钮区域 */}
            <div className="flex gap-2 mt-4">
              <div className="h-8 w-20 bg-indigo-500/20 rounded-lg border border-indigo-500/30" />
              <div className="h-8 w-24 bg-white/5 rounded-lg" />
            </div>
          </div>
          
          {/* 元素高亮 */}
          <AnimatePresence>
            {highlight && (
              <motion.div
                className="absolute pointer-events-none"
                style={{
                  left: highlight.x - 4,
                  top: highlight.y - 4,
                  width: highlight.width + 8,
                  height: highlight.height + 8,
                }}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{
                  opacity: 1,
                  scale: 1,
                  boxShadow: [
                    '0 0 0 4px rgba(99, 102, 241, 0.1), 0 0 20px rgba(99, 102, 241, 0.3)',
                    '0 0 0 8px rgba(99, 102, 241, 0.2), 0 0 40px rgba(99, 102, 241, 0.5)',
                    '0 0 0 4px rgba(99, 102, 241, 0.1), 0 0 20px rgba(99, 102, 241, 0.3)',
                  ],
                }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{
                  opacity: { duration: 0.2 },
                  scale: { duration: 0.2 },
                  boxShadow: { duration: 1.5, repeat: Infinity, ease: 'easeInOut' },
                }}
              >
                <div
                  className="w-full h-full rounded-md border-2 border-indigo-500"
                  style={{
                    boxShadow: 'inset 0 0 20px rgba(99, 102, 241, 0.1)',
                  }}
                />
                
                {/* 高亮标签 */}
                {highlight.label && (
                  <motion.div
                    className="absolute -top-7 left-0 px-2 py-1 bg-indigo-500 text-white text-xs font-medium rounded whitespace-nowrap"
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2, delay: 0.1 }}
                  >
                    {highlight.label}
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
          
          {/* AI 光标 */}
          {showCursor && (
            <AICursor
              targetPosition={cursorPosition}
              state={cursorState}
              visible={true}
            />
          )}
        </div>
      </div>
      
      {/* 步骤进度指示器 */}
      {stepInfo && stepInfo.total > 0 && (
        <motion.div
          className="flex justify-center gap-2 mt-3 py-3 px-4 bg-[#111] rounded-full border border-white/[0.06]"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {Array.from({ length: stepInfo.total }).map((_, i) => {
            const isCompleted = i < stepInfo.current
            const isActive = i === stepInfo.current
            const isError = stepInfo.status === 'error' && isActive
            
            return (
              <motion.div
                key={i}
                className={cn(
                  'w-2.5 h-2.5 rounded-full transition-colors duration-300',
                  isCompleted && 'bg-green-500',
                  isActive && !isError && 'bg-indigo-500',
                  isError && 'bg-red-500',
                  !isCompleted && !isActive && 'bg-white/20',
                )}
                animate={
                  isActive
                    ? {
                        scale: [1, 1.2, 1],
                        boxShadow: isError
                          ? ['0 0 0 0 rgba(239, 68, 68, 0)', '0 0 8px 4px rgba(239, 68, 68, 0.4)', '0 0 0 0 rgba(239, 68, 68, 0)']
                          : ['0 0 0 0 rgba(99, 102, 241, 0)', '0 0 8px 4px rgba(99, 102, 241, 0.4)', '0 0 0 0 rgba(99, 102, 241, 0)'],
                      }
                    : {}
                }
                transition={{
                  duration: 1,
                  repeat: isActive ? Infinity : 0,
                  ease: 'easeInOut',
                }}
              />
            )
          })}
        </motion.div>
      )}
    </div>
  )
}

export default ScreenSimulator

