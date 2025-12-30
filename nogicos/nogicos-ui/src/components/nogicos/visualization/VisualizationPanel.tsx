/**
 * VisualizationPanel - 可视化面板主组件
 * 展示 AI 操作的实时可视化效果
 * 
 * 功能：
 * - 虚拟屏幕模拟器
 * - AI 光标动画
 * - 操作日志
 * - 状态指示
 */

import { motion, AnimatePresence } from 'motion/react'
import { useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { Eye, EyeOff, Maximize2, Minimize2 } from 'lucide-react'
import { ScreenSimulator, type HighlightRect, type GlowState, type StepInfo } from './ScreenSimulator'
import type { CursorPosition, CursorState } from './AICursor'

// 可视化状态
export interface VisualizationState {
  cursor: {
    position: CursorPosition
    state: CursorState
    visible: boolean
  }
  highlight: HighlightRect | null
  glow: GlowState
  step: StepInfo | null
  url: string
  actionLog: ActionLogEntry[]
}

// 操作日志条目
export interface ActionLogEntry {
  id: string
  timestamp: Date
  type: 'cursor_move' | 'click' | 'type' | 'highlight' | 'step' | 'complete' | 'error'
  description: string
}

export interface VisualizationPanelProps {
  /** 可视化状态 */
  state: VisualizationState
  /** 是否显示 */
  visible?: boolean
  /** 是否可折叠 */
  collapsible?: boolean
  /** 初始折叠状态 */
  initialCollapsed?: boolean
  /** 标题 */
  title?: string
  className?: string
}

// 默认可视化状态
export const defaultVisualizationState: VisualizationState = {
  cursor: {
    position: { x: 100, y: 100 },
    state: 'idle',
    visible: true,
  },
  highlight: null,
  glow: 'off',
  step: null,
  url: 'https://example.com',
  actionLog: [],
}

export function VisualizationPanel({
  state,
  visible = true,
  collapsible = true,
  initialCollapsed = false,
  title = 'AI 可视化',
  className,
}: VisualizationPanelProps) {
  const [isCollapsed, setIsCollapsed] = useState(initialCollapsed)
  const [showLog, setShowLog] = useState(false)
  
  const toggleCollapse = useCallback(() => {
    setIsCollapsed(prev => !prev)
  }, [])
  
  const toggleLog = useCallback(() => {
    setShowLog(prev => !prev)
  }, [])
  
  if (!visible) return null
  
  return (
    <motion.div
      className={cn(
        'flex flex-col h-full bg-[#0a0a0f] border-l border-white/[0.06]',
        isCollapsed ? 'w-12' : 'w-[400px]',
        className,
      )}
      animate={{ width: isCollapsed ? 48 : 400 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* 头部 */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-white/[0.06] bg-[#111]">
        {!isCollapsed && (
          <motion.div
            className="flex items-center gap-2"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
          >
            <div className="relative">
              <div className="w-2 h-2 rounded-full bg-indigo-500" />
              <motion.div
                className="absolute inset-0 rounded-full bg-indigo-500"
                animate={{
                  scale: [1, 1.5, 1],
                  opacity: [0.5, 0, 0.5],
                }}
                transition={{
                  duration: 1.5,
                  repeat: Infinity,
                  ease: 'easeInOut',
                }}
              />
            </div>
            <span className="text-sm font-medium text-white/80">{title}</span>
          </motion.div>
        )}
        
        <div className={cn('flex items-center gap-1', isCollapsed && 'mx-auto')}>
          {!isCollapsed && (
            <button
              onClick={toggleLog}
              className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
              title={showLog ? '隐藏日志' : '显示日志'}
            >
              {showLog ? (
                <EyeOff className="w-4 h-4 text-white/50" />
              ) : (
                <Eye className="w-4 h-4 text-white/50" />
              )}
            </button>
          )}
          
          {collapsible && (
            <button
              onClick={toggleCollapse}
              className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
              title={isCollapsed ? '展开面板' : '折叠面板'}
            >
              {isCollapsed ? (
                <Maximize2 className="w-4 h-4 text-white/50" />
              ) : (
                <Minimize2 className="w-4 h-4 text-white/50" />
              )}
            </button>
          )}
        </div>
      </div>
      
      {/* 内容区域 */}
      <AnimatePresence>
        {!isCollapsed && (
          <motion.div
            className="flex-1 flex flex-col p-3 overflow-hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {/* 屏幕模拟器 */}
            <div className={cn('flex-1', showLog ? 'h-1/2' : 'h-full')}>
              <ScreenSimulator
                cursorPosition={state.cursor.position}
                cursorState={state.cursor.state}
                highlight={state.highlight}
                glowState={state.glow}
                stepInfo={state.step || undefined}
                showCursor={state.cursor.visible}
                simulatedUrl={state.url}
              />
            </div>
            
            {/* 操作日志 */}
            <AnimatePresence>
              {showLog && (
                <motion.div
                  className="flex flex-col mt-3 h-1/2"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="text-xs text-white/40 mb-2 font-medium">操作日志</div>
                  <div className="flex-1 bg-[#111] rounded-lg border border-white/[0.06] overflow-y-auto">
                    {state.actionLog.length === 0 ? (
                      <div className="flex items-center justify-center h-full text-xs text-white/30">
                        暂无操作
                      </div>
                    ) : (
                      <div className="p-2 space-y-1">
                        {state.actionLog.slice(-10).reverse().map((entry) => (
                          <motion.div
                            key={entry.id}
                            className="flex items-start gap-2 py-1.5 px-2 rounded bg-white/[0.02]"
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.2 }}
                          >
                            <div
                              className={cn(
                                'w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0',
                                entry.type === 'complete' && 'bg-green-500',
                                entry.type === 'error' && 'bg-red-500',
                                entry.type === 'click' && 'bg-indigo-500',
                                entry.type === 'type' && 'bg-yellow-500',
                                !['complete', 'error', 'click', 'type'].includes(entry.type) && 'bg-white/30',
                              )}
                            />
                            <div className="flex-1 min-w-0">
                              <div className="text-xs text-white/60 truncate">
                                {entry.description}
                              </div>
                              <div className="text-[10px] text-white/30">
                                {entry.timestamp.toLocaleTimeString()}
                              </div>
                            </div>
                          </motion.div>
                        ))}
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* 折叠状态下的指示器 */}
      {isCollapsed && (
        <motion.div
          className="flex-1 flex flex-col items-center py-4 gap-2"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          {/* 状态指示灯 */}
          <div
            className={cn(
              'w-3 h-3 rounded-full',
              state.glow === 'success' && 'bg-green-500',
              state.glow === 'error' && 'bg-red-500',
              state.glow !== 'success' && state.glow !== 'error' && state.glow !== 'off' && 'bg-indigo-500 animate-pulse',
              state.glow === 'off' && 'bg-white/20',
            )}
          />
          
          {/* 步骤指示 */}
          {state.step && (
            <div className="text-[10px] text-white/40 text-center">
              {state.step.current + 1}/{state.step.total}
            </div>
          )}
        </motion.div>
      )}
    </motion.div>
  )
}

export default VisualizationPanel

