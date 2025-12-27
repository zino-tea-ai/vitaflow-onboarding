import { useState } from 'react'
import { motion, AnimatePresence, useMotionValue, useTransform, animate } from 'motion/react'
import { useEffect, useRef } from 'react'
import './App.css'

// 数字滚动组件
function AnimatedNumber({ value }: { value: number }) {
  const nodeRef = useRef<HTMLSpanElement>(null)
  
  useEffect(() => {
    const node = nodeRef.current
    if (!node) return
    
    const controls = animate(0, value, {
      duration: 1.5,
      ease: [0.16, 1, 0.3, 1],
      onUpdate(value) {
        node.textContent = Math.round(value).toLocaleString()
      },
    })
    
    return () => controls.stop()
  }, [value])
  
  return <span ref={nodeRef}>0</span>
}

// 拖拽卡片
function DraggableCard() {
  const x = useMotionValue(0)
  const rotateZ = useTransform(x, [-150, 150], [-15, 15])
  const opacity = useTransform(x, [-150, 0, 150], [0.5, 1, 0.5])
  
  return (
    <motion.div
      className="drag-card"
      drag="x"
      dragConstraints={{ left: -150, right: 150 }}
      style={{ x, rotateZ, opacity }}
      whileTap={{ scale: 0.95 }}
    >
      <span>← 拖拽我 →</span>
    </motion.div>
  )
}

// 进度条组件
function ProgressBar({ progress, color }: { progress: number; color: string }) {
  return (
    <div className="progress-container">
      <motion.div
        className="progress-bar"
        initial={{ width: 0 }}
        animate={{ width: `${progress}%` }}
        transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
        style={{ backgroundColor: color }}
      />
    </div>
  )
}

function App() {
  const [showCards, setShowCards] = useState(true)
  const [activeTab, setActiveTab] = useState(0)
  
  const listItems = ['蛋白质 120g', '碳水 200g', '脂肪 65g', '纤维 30g', '水分 2.5L']
  const tabs = ['今日', '本周', '本月']

  return (
    <div className="container">
      <motion.h1
        initial={{ opacity: 0, y: -30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        Motion 动效演示
      </motion.h1>

      {/* Section 1: 入场动画 */}
      <motion.section
        className="section"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1 }}
      >
        <h2>1. 数字滚动 + 进度条</h2>
        <div className="stats-grid">
          <motion.div 
            className="stat-card"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.2, type: "spring", bounce: 0.4 }}
          >
            <div className="stat-value" style={{ color: '#10b981' }}>
              <AnimatedNumber value={2505} />
            </div>
            <div className="stat-label">卡路里</div>
            <ProgressBar progress={75} color="#10b981" />
          </motion.div>
          
          <motion.div 
            className="stat-card"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.3, type: "spring", bounce: 0.4 }}
          >
            <div className="stat-value" style={{ color: '#f59e0b' }}>
              <AnimatedNumber value={165} />g
            </div>
            <div className="stat-label">碳水</div>
            <ProgressBar progress={60} color="#f59e0b" />
          </motion.div>
          
          <motion.div 
            className="stat-card"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.4, type: "spring", bounce: 0.4 }}
          >
            <div className="stat-value" style={{ color: '#ef4444' }}>
              <AnimatedNumber value={98} />g
            </div>
            <div className="stat-label">脂肪</div>
            <ProgressBar progress={45} color="#ef4444" />
          </motion.div>
        </div>
      </motion.section>

      {/* Section 2: Tab 切换动画 */}
      <motion.section
        className="section"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.2 }}
      >
        <h2>2. Tab 切换 (Layout Animation)</h2>
        <div className="tabs">
          {tabs.map((tab, i) => (
            <button
              key={tab}
              className={`tab ${activeTab === i ? 'active' : ''}`}
              onClick={() => setActiveTab(i)}
            >
              {tab}
              {activeTab === i && (
                <motion.div
                  className="tab-indicator"
                  layoutId="tab-indicator"
                  transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                />
              )}
            </button>
          ))}
        </div>
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            className="tab-content"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
          >
            {activeTab === 0 && "今日摄入 2,505 卡路里，目标完成 75%"}
            {activeTab === 1 && "本周平均 2,300 卡路里，比上周 ↑12%"}
            {activeTab === 2 && "本月累计消耗 68,500 卡路里 🎉"}
          </motion.div>
        </AnimatePresence>
      </motion.section>

      {/* Section 3: 列表 Stagger */}
      <motion.section
        className="section"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.3 }}
      >
        <h2>3. 列表 Stagger 动画</h2>
        <button className="toggle-btn" onClick={() => setShowCards(!showCards)}>
          {showCards ? '隐藏列表' : '显示列表'}
        </button>
        <AnimatePresence>
          {showCards && (
            <motion.ul className="list">
              {listItems.map((item, i) => (
                <motion.li
                  key={item}
                  className="list-item"
                  initial={{ opacity: 0, x: -30 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 30, transition: { delay: (listItems.length - i - 1) * 0.05 } }}
                  transition={{ 
                    duration: 0.4, 
                    delay: i * 0.08,
                    ease: [0.16, 1, 0.3, 1]
                  }}
                  whileHover={{ 
                    x: 8, 
                    backgroundColor: 'rgba(255,255,255,0.1)',
                    transition: { duration: 0.2 }
                  }}
                >
                  <span className="list-icon">✓</span>
                  {item}
                </motion.li>
              ))}
            </motion.ul>
          )}
        </AnimatePresence>
      </motion.section>

      {/* Section 4: 拖拽交互 */}
      <motion.section
        className="section"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.4 }}
      >
        <h2>4. 拖拽手势</h2>
        <div className="drag-area">
          <DraggableCard />
        </div>
      </motion.section>

      {/* Section 5: 弹簧按钮 */}
      <motion.section
        className="section"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.5 }}
      >
        <h2>5. 弹簧交互按钮</h2>
        <div className="buttons-row">
          <motion.button
            className="spring-btn primary"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            transition={{ type: "spring", stiffness: 400, damping: 17 }}
          >
            添加食物
          </motion.button>
          
          <motion.button
            className="spring-btn secondary"
            whileHover={{ scale: 1.05, rotate: [0, -2, 2, 0] }}
            whileTap={{ scale: 0.9 }}
            transition={{ type: "spring", stiffness: 400, damping: 17 }}
          >
            扫描条码
          </motion.button>
          
          <motion.button
            className="spring-btn ghost"
            whileHover={{ 
              scale: 1.02,
              boxShadow: "0 0 20px rgba(16, 185, 129, 0.4)"
            }}
            whileTap={{ scale: 0.98 }}
          >
            查看详情
          </motion.button>
        </div>
      </motion.section>

      {/* Section 6: 呼吸动画 */}
      <motion.section
        className="section"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.6 }}
      >
        <h2>6. 循环动画</h2>
        <div className="breathing-container">
          <motion.div
            className="breathing-circle"
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.7, 1, 0.7],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
          <motion.div
            className="pulse-ring"
            animate={{
              scale: [1, 1.5],
              opacity: [0.5, 0],
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: "easeOut",
            }}
          />
          <span className="breathing-text">录入中...</span>
        </div>
      </motion.section>
    </div>
  )
}

export default App
