/**
 * NogicOS Animation Primitives Demo
 * 
 * 六大动画原语的交互演示：
 * 1. Focus - 聚焦光圈
 * 2. Path - 轨迹线
 * 3. Input - 输入动画
 * 4. Action - 动作反馈
 * 5. Change - 变化高亮
 * 6. Complete - 完成效果
 */

import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence, animate, useMotionValue } from 'motion/react'
import { Typewriter } from 'motion-plus/react'

// ============================================================
// Animation Tokens
// ============================================================

const tokens = {
  duration: {
    instant: 0.1,
    fast: 0.2,
    normal: 0.35,
    slow: 0.5,
    deliberate: 0.8,
  },
  spring: {
    snappy: { type: 'spring' as const, visualDuration: 0.3, bounce: 0.15 },
    smooth: { type: 'spring' as const, visualDuration: 0.5, bounce: 0.25 },
    bouncy: { type: 'spring' as const, visualDuration: 0.8, bounce: 0.4 },
  },
  colors: {
    focus: '#3B82F6',    // 蓝
    path: '#8B5CF6',     // 紫
    input: '#10B981',    // 绿
    action: '#F59E0B',   // 橙
    success: '#10B981',
    error: '#EF4444',
    warning: '#F59E0B',
    info: '#3B82F6',
  }
}

// ============================================================
// 1. Focus Primitive - 聚焦光圈
// ============================================================

function FocusDemo() {
  const [isFocused, setIsFocused] = useState(false)

  return (
    <div className="demo-section">
      <h3 className="demo-title">1. Focus 聚焦</h3>
      <p className="demo-desc">点击按钮触发聚焦光圈效果</p>
      
      <div className="demo-area">
        <div className="relative inline-block">
          <motion.button
            className="demo-target-btn"
            onClick={() => setIsFocused(!isFocused)}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {isFocused ? '取消聚焦' : '聚焦此元素'}
          </motion.button>
          
          <AnimatePresence>
            {isFocused && (
              <motion.div
                className="focus-ring"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ 
                  opacity: [0.6, 0.4, 0.6],
                  scale: [1, 1.05, 1],
                }}
                exit={{ opacity: 0, scale: 1.2 }}
                transition={{
                  opacity: { duration: 1.5, repeat: Infinity },
                  scale: { duration: 1.5, repeat: Infinity },
                  ...tokens.spring.smooth
                }}
              />
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}

// ============================================================
// 2. Path Primitive - 轨迹线
// ============================================================

function PathDemo() {
  const [isDrawing, setIsDrawing] = useState(false)

  const handleDraw = () => {
    setIsDrawing(true)
    setTimeout(() => setIsDrawing(false), 1500)
  }

  return (
    <div className="demo-section">
      <h3 className="demo-title">2. Path 轨迹</h3>
      <p className="demo-desc">展示从 A 到 B 的运动轨迹</p>
      
      <div className="demo-area">
        <div className="path-container">
          {/* 起点 */}
          <motion.div 
            className="path-point path-start"
            animate={isDrawing ? { scale: [1, 1.2, 1] } : {}}
            transition={{ duration: 0.3 }}
          >
            A
          </motion.div>
          
          {/* SVG 轨迹 */}
          <svg className="path-svg" viewBox="0 0 300 100">
            <motion.path
              d="M 30 50 Q 150 10 270 50"
              fill="none"
              stroke={tokens.colors.path}
              strokeWidth="2"
              strokeDasharray="5 5"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: isDrawing ? 1 : 0 }}
              transition={{ duration: 0.8, ease: "easeInOut" }}
            />
            
            {/* 移动的点 */}
            <AnimatePresence>
              {isDrawing && (
                <motion.circle
                  cx="30"
                  cy="50"
                  r="6"
                  fill={tokens.colors.path}
                  initial={{ offsetDistance: '0%' }}
                  animate={{ offsetDistance: '100%' }}
                  transition={{ duration: 0.8, ease: "easeInOut" }}
                  style={{
                    offsetPath: "path('M 30 50 Q 150 10 270 50')",
                  }}
                />
              )}
            </AnimatePresence>
          </svg>
          
          {/* 终点 */}
          <motion.div 
            className="path-point path-end"
            animate={isDrawing ? { 
              scale: [1, 1.3, 1],
              boxShadow: ['0 0 0 0 rgba(139, 92, 246, 0)', '0 0 0 10px rgba(139, 92, 246, 0.3)', '0 0 0 0 rgba(139, 92, 246, 0)']
            } : {}}
            transition={{ duration: 0.5, delay: 0.6 }}
          >
            B
          </motion.div>
        </div>
        
        <motion.button
          className="demo-trigger-btn"
          onClick={handleDraw}
          disabled={isDrawing}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          {isDrawing ? '绘制中...' : '绘制轨迹'}
        </motion.button>
      </div>
    </div>
  )
}

// ============================================================
// 3. Input Primitive - 使用 Motion+ 官方 Typewriter 组件
// ============================================================

const INPUT_SCRIPT = [
  { text: 'Hello, NogicOS!', endDelay: 1.5 },
  { text: 'AI is typing...', endDelay: 1 },
  { text: 'Cursor for Everyone.', endDelay: 2 },
]

function InputDemo() {
  const [scriptIndex, setScriptIndex] = useState(0)
  const [isTyping, setIsTyping] = useState(false)
  
  const currentScript = INPUT_SCRIPT[scriptIndex]

  const startTyping = () => {
    setIsTyping(true)
    setScriptIndex((prev) => (prev + 1) % INPUT_SCRIPT.length)
  }

  return (
    <div className="demo-section">
      <h3 className="demo-title">3. Input 输入</h3>
      <p className="demo-desc">Motion+ 官方 Typewriter 组件</p>
      
      <div className="demo-area">
        <div className="input-container">
          <div className="input-field typewriter-field">
            <Typewriter
              as="span"
              speed="fast"
              variance="natural"
              cursorStyle={{
                background: '#10B981',
                width: 2,
                borderRadius: 1,
              }}
              textStyle={{
                fontFamily: "'SF Mono', 'Fira Code', monospace",
                fontSize: '0.95rem',
                color: '#f5f5f5',
              }}
              backspace="character"
              onComplete={() => setIsTyping(false)}
            >
              {currentScript.text}
            </Typewriter>
          </div>
        </div>
        
        <motion.button
          className="demo-trigger-btn"
          onClick={startTyping}
          disabled={isTyping}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          {isTyping ? '输入中...' : '开始输入'}
        </motion.button>
      </div>
    </div>
  )
}

// ============================================================
// 4. Action Primitive - 动作反馈
// ============================================================

function ActionDemo() {
  const [ripples, setRipples] = useState<{ id: number; x: number; y: number }[]>([])
  const buttonRef = useRef<HTMLButtonElement>(null)

  const handleClick = (e: React.MouseEvent) => {
    if (!buttonRef.current) return
    
    const rect = buttonRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    
    const newRipple = { id: Date.now(), x, y }
    setRipples(prev => [...prev, newRipple])
    
    setTimeout(() => {
      setRipples(prev => prev.filter(r => r.id !== newRipple.id))
    }, 600)
  }

  return (
    <div className="demo-section">
      <h3 className="demo-title">4. Action 动作</h3>
      <p className="demo-desc">点击产生涟漪反馈效果</p>
      
      <div className="demo-area">
        <motion.button
          ref={buttonRef}
          className="action-btn"
          onClick={handleClick}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          点击我
          
          {/* 涟漪效果 */}
          <AnimatePresence>
            {ripples.map(ripple => (
              <motion.span
                key={ripple.id}
                className="ripple"
                style={{ left: ripple.x, top: ripple.y }}
                initial={{ scale: 0, opacity: 0.5 }}
                animate={{ scale: 4, opacity: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.6, ease: "easeOut" }}
              />
            ))}
          </AnimatePresence>
        </motion.button>
      </div>
    </div>
  )
}

// ============================================================
// 5. Change Primitive - 变化高亮
// ============================================================

function ChangeDemo() {
  const [version, setVersion] = useState(0)
  const texts = [
    '原始内容',
    '修改后的内容',
    '再次修改',
  ]

  const handleChange = () => {
    setVersion(v => (v + 1) % texts.length)
  }

  return (
    <div className="demo-section">
      <h3 className="demo-title">5. Change 变化</h3>
      <p className="demo-desc">内容变化时的高亮效果</p>
      
      <div className="demo-area">
        <div className="change-container">
          <AnimatePresence mode="wait">
            <motion.div
              key={version}
              className="change-content"
              initial={{ 
                opacity: 0, 
                y: 10,
                backgroundColor: 'rgba(245, 158, 11, 0.3)'
              }}
              animate={{ 
                opacity: 1, 
                y: 0,
                backgroundColor: 'rgba(245, 158, 11, 0)'
              }}
              exit={{ 
                opacity: 0, 
                y: -10,
                textDecoration: 'line-through'
              }}
              transition={tokens.spring.smooth}
            >
              {texts[version]}
            </motion.div>
          </AnimatePresence>
        </div>
        
        <motion.button
          className="demo-trigger-btn"
          onClick={handleChange}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          修改内容
        </motion.button>
      </div>
    </div>
  )
}

// ============================================================
// 6. Complete Primitive - 基于 Motion+ Multi-State Badge 官方示例
// ============================================================

// 基于官方示例的 Spring 配置
const COMPLETE_SPRING = {
  type: "spring" as const,
  stiffness: 600,
  damping: 30,
}

const ICON_SPRING = {
  type: "spring" as const,
  stiffness: 150,
  damping: 20,
}

// 官方示例的图标动画配置
const iconAnimations = {
  initial: { pathLength: 0 },
  animate: { pathLength: 1 },
  transition: ICON_SPRING,
}

// 官方 Check 图标
function CheckIcon() {
  return (
    <motion.svg
      width="32"
      height="32"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#10B981"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <motion.polyline points="4 12 9 17 20 6" {...iconAnimations} />
    </motion.svg>
  )
}

// 官方 Loader 图标 - 使用 useTime + useTransform 实现无限旋转
function LoaderIcon() {
  const time = useMotionValue(0)
  
  useEffect(() => {
    const controls = animate(time, 360, {
      duration: 1,
      repeat: Infinity,
      ease: "linear",
    })
    return controls.stop
  }, [time])

  return (
    <motion.div style={{ rotate: time }}>
      <motion.svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        stroke="url(#loaderGradient)"
        strokeWidth="2.5"
        strokeLinecap="round"
      >
        <defs>
          <linearGradient id="loaderGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#3B82F6" />
            <stop offset="100%" stopColor="#8B5CF6" />
          </linearGradient>
        </defs>
        <motion.path d="M21 12a9 9 0 1 1-6.219-8.56" {...iconAnimations} />
      </motion.svg>
    </motion.div>
  )
}

// 官方 X 图标
function XIcon() {
  return (
    <motion.svg
      width="32"
      height="32"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#EF4444"
      strokeWidth="2.5"
      strokeLinecap="round"
    >
      <motion.line x1="6" y1="6" x2="18" y2="18" {...iconAnimations} />
      <motion.line 
        x1="18" y1="6" x2="6" y2="18" 
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ ...ICON_SPRING, delay: 0.1 }}
      />
    </motion.svg>
  )
}

const COMPLETE_STATES = {
  idle: "准备就绪",
  loading: "处理中",
  success: "完成",
  error: "出错了",
} as const

function CompleteDemo() {
  const [status, setStatus] = useState<keyof typeof COMPLETE_STATES>('idle')
  const badgeRef = useRef<HTMLDivElement>(null)

  const triggerComplete = (type: 'success' | 'error') => {
    setStatus('loading')
    setTimeout(() => {
      setStatus(type)
      setTimeout(() => setStatus('idle'), 3000)
    }, 1000)
  }

  // 官方示例的抖动/弹跳动画
  useEffect(() => {
    if (!badgeRef.current) return
    
    if (status === 'error') {
      animate(
        badgeRef.current,
        { x: [0, -6, 6, -6, 6, -3, 3, 0] },
        { duration: 0.4, ease: "easeInOut", delay: 0.1 }
      )
    } else if (status === 'success') {
      animate(
        badgeRef.current,
        { scale: [1, 1.15, 1] },
        { duration: 0.3, ease: "easeInOut" }
      )
    }
  }, [status])

  // 获取当前图标
  const getIcon = () => {
    switch (status) {
      case 'loading': return <LoaderIcon />
      case 'success': return <CheckIcon />
      case 'error': return <XIcon />
      default: return null
    }
  }

  // 获取状态颜色
  const getStateColor = () => {
    switch (status) {
      case 'loading': return 'rgba(139, 92, 246, 0.15)'
      case 'success': return 'rgba(16, 185, 129, 0.15)'
      case 'error': return 'rgba(239, 68, 68, 0.15)'
      default: return 'rgba(255, 255, 255, 0.05)'
    }
  }

  const getBorderColor = () => {
    switch (status) {
      case 'loading': return 'rgba(139, 92, 246, 0.4)'
      case 'success': return 'rgba(16, 185, 129, 0.4)'
      case 'error': return 'rgba(239, 68, 68, 0.4)'
      default: return 'rgba(255, 255, 255, 0.1)'
    }
  }

  return (
    <div className="demo-section">
      <h3 className="demo-title">6. Complete 完成</h3>
      <p className="demo-desc">基于 Motion+ Multi-State Badge 官方示例</p>
      
      <div className="demo-area">
        {/* 基于官方 Badge 的状态徽章 */}
        <motion.div
          ref={badgeRef}
          className="complete-badge"
          style={{ gap: status === 'idle' ? 0 : 12 }}
          animate={{
            backgroundColor: getStateColor(),
            borderColor: getBorderColor(),
          }}
          transition={COMPLETE_SPRING}
        >
          {/* 图标容器 */}
          <motion.span
            className="badge-icon-container"
            animate={{ width: status === 'idle' ? 0 : 32 }}
            transition={COMPLETE_SPRING}
          >
            <AnimatePresence mode="popLayout">
              <motion.span
                key={status}
                className="badge-icon"
                initial={{ y: -30, scale: 0.5, filter: 'blur(4px)' }}
                animate={{ y: 0, scale: 1, filter: 'blur(0px)' }}
                exit={{ y: 30, scale: 0.5, filter: 'blur(4px)' }}
                transition={{ duration: 0.2, ease: "easeInOut" }}
              >
                {getIcon()}
              </motion.span>
            </AnimatePresence>
          </motion.span>
          
          {/* 文字标签 */}
          <motion.span className="badge-label-container">
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.span
                key={status}
                className="badge-label"
                initial={{ y: -15, opacity: 0, filter: 'blur(6px)' }}
                animate={{ y: 0, opacity: 1, filter: 'blur(0px)' }}
                exit={{ y: 15, opacity: 0, filter: 'blur(6px)' }}
                transition={{ duration: 0.2, ease: "easeInOut" }}
              >
                {COMPLETE_STATES[status]}
              </motion.span>
            </AnimatePresence>
          </motion.span>
        </motion.div>
        
        <div className="complete-buttons-v2">
          <motion.button
            className="trigger-btn-success"
            onClick={() => triggerComplete('success')}
            disabled={status !== 'idle'}
            whileHover={{ scale: 1.05, boxShadow: '0 0 20px rgba(16, 185, 129, 0.4)' }}
            whileTap={{ scale: 0.95 }}
          >
            <span className="btn-icon">✓</span>
            触发成功
          </motion.button>
          <motion.button
            className="trigger-btn-error"
            onClick={() => triggerComplete('error')}
            disabled={status !== 'idle'}
            whileHover={{ scale: 1.05, boxShadow: '0 0 20px rgba(239, 68, 68, 0.4)' }}
            whileTap={{ scale: 0.95 }}
          >
            <span className="btn-icon">✕</span>
            触发失败
          </motion.button>
        </div>
      </div>
    </div>
  )
}

// ============================================================
// Main Demo Component
// ============================================================

export function AnimationPrimitivesDemo() {
  return (
    <div className="animation-demo-container">
      <header className="demo-header">
        <motion.h1
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={tokens.spring.smooth}
        >
          NogicOS Animation Primitives
        </motion.h1>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          六大通用动画原语 - 组合覆盖 95%+ 场景
        </motion.p>
      </header>
      
      <motion.div 
        className="demo-grid"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        <FocusDemo />
        <PathDemo />
        <InputDemo />
        <ActionDemo />
        <ChangeDemo />
        <CompleteDemo />
      </motion.div>
      
      <footer className="demo-footer">
        <p>Spring Presets: snappy (0.3s) | smooth (0.5s) | bouncy (0.8s)</p>
      </footer>
    </div>
  )
}

export default AnimationPrimitivesDemo

