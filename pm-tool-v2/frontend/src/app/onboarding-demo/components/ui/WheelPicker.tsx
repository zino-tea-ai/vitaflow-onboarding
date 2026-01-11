'use client'

import { useRef, useEffect, useCallback } from 'react'
import { colors } from '../../lib/design-tokens'
import { haptic } from '../../lib/haptics'

interface WheelPickerProps {
  value: number
  onChange: (value: number) => void
  min: number
  max: number
  step?: number
  unit?: string
  label?: string
  orientation?: 'vertical' | 'horizontal'
}

/**
 * 滚轮数字选择器 - iOS 原生滚动版
 * 
 * 使用 CSS scroll-snap 实现丝滑滚动
 * 比 Framer Motion drag 更流畅
 */
export function WheelPicker({
  value,
  onChange,
  min,
  max,
  step = 1,
  unit = '',
  label,
  orientation = 'vertical',
}: WheelPickerProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const isScrollingRef = useRef(false)
  const lastValueRef = useRef(value)
  const touchStartYRef = useRef(0)
  const lastHapticValueRef = useRef(value)
  
  // 生成可选值
  const values: number[] = []
  for (let v = min; v <= max; v += step) {
    values.push(v)
  }
  
  const currentIndex = values.findIndex(v => v === value)
  const itemSize = orientation === 'vertical' ? 48 : 52  // 水平模式更紧凑
  
  // 滚动到指定值
  const scrollToValue = useCallback((targetValue: number, smooth = true) => {
    const container = scrollRef.current
    if (!container) return
    
    const targetIndex = values.findIndex(v => v === targetValue)
    if (targetIndex < 0) return
    
    const scrollPos = targetIndex * itemSize
    
    if (orientation === 'vertical') {
      container.scrollTo({
        top: scrollPos,
        behavior: smooth ? 'smooth' : 'auto'
      })
    } else {
      container.scrollTo({
        left: scrollPos,
        behavior: smooth ? 'smooth' : 'auto'
      })
    }
  }, [values, itemSize, orientation])
  
  // 初始化滚动位置
  useEffect(() => {
    scrollToValue(value, false)
  }, []) // 只在挂载时执行一次
  
  // 外部 value 变化时滚动
  useEffect(() => {
    if (value !== lastValueRef.current && !isScrollingRef.current) {
      scrollToValue(value, true)
      lastValueRef.current = value
    }
  }, [value, scrollToValue])
  
  // 处理滚动事件
  const handleScroll = useCallback(() => {
    const container = scrollRef.current
    if (!container) return
    
    isScrollingRef.current = true
    
    const scrollPos = orientation === 'vertical' 
      ? container.scrollTop 
      : container.scrollLeft
    
    const newIndex = Math.round(scrollPos / itemSize)
    const clampedIndex = Math.max(0, Math.min(values.length - 1, newIndex))
    const newValue = values[clampedIndex]
    
    if (newValue !== undefined && newValue !== lastValueRef.current) {
      lastValueRef.current = newValue
      onChange(newValue)
    }
    
    // 延迟重置滚动状态
    setTimeout(() => {
      isScrollingRef.current = false
    }, 100)
  }, [orientation, itemSize, values, onChange])
  
  // Touch 事件 - 在用户交互上下文中触发震动
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    touchStartYRef.current = orientation === 'vertical' 
      ? e.touches[0].clientY 
      : e.touches[0].clientX
    lastHapticValueRef.current = value
  }, [orientation, value])
  
  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    const container = scrollRef.current
    if (!container) return
    
    const scrollPos = orientation === 'vertical' 
      ? container.scrollTop 
      : container.scrollLeft
    
    const newIndex = Math.round(scrollPos / itemSize)
    const clampedIndex = Math.max(0, Math.min(values.length - 1, newIndex))
    const newValue = values[clampedIndex]
    
    // 值变化时触发震动（在 touch 上下文中！）
    if (newValue !== undefined && newValue !== lastHapticValueRef.current) {
      haptic('light')
      lastHapticValueRef.current = newValue
    }
  }, [orientation, itemSize, values])
  
  // 垂直模式
  if (orientation === 'vertical') {
    return (
      <div className="flex flex-col items-center">
        {label && (
          <p 
            className="text-[14px] font-medium mb-4"
            style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}
          >
            {label}
          </p>
        )}
        
        <div className="relative" style={{ height: itemSize * 5 }}>
          {/* 选中指示条 - 最底层 */}
          <div 
            className="absolute left-0 right-0 top-1/2 -translate-y-1/2 rounded-xl pointer-events-none"
            style={{ 
              height: itemSize,
              background: colors.slate[100],
              border: `1px solid ${colors.slate[200]}`,
              zIndex: 1,
            }}
          />
          
          {/* 滚动容器 - 中间层，阻止水平滚动传播 */}
          <div
            ref={scrollRef}
            className="h-full overflow-y-auto scrollbar-hide relative"
            style={{
              scrollSnapType: 'y mandatory',
              WebkitOverflowScrolling: 'touch',
              scrollbarWidth: 'none',
              msOverflowStyle: 'none',
              zIndex: 2,
              touchAction: 'pan-y',  // 只允许垂直滑动
              overscrollBehavior: 'contain',  // 阻止滚动传播
            }}
            onScroll={handleScroll}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
          >
            {/* 顶部填充 */}
            <div style={{ height: itemSize * 2 }} />
            
            {/* 数值列表 */}
            {values.map((v) => {
              const isSelected = v === value
              return (
                <div
                  key={v}
                  className="flex items-center justify-center"
                  style={{ 
                    height: itemSize,
                    scrollSnapAlign: 'center',
                  }}
                >
                  <div className="flex items-baseline gap-3">
                    <span 
                      className="text-[40px] font-medium tabular-nums transition-all duration-150"
                      style={{ 
                        color: isSelected ? colors.text.primary : colors.text.tertiary,
                        letterSpacing: '-0.5px',
                        opacity: isSelected ? 1 : 0.35,
                        transform: isSelected ? 'scale(1)' : 'scale(0.75)',
                      }}
                    >
                      {v}
                    </span>
                    {unit && isSelected && (
                      <span 
                        className="text-[18px] font-medium"
                        style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}
                      >
                        {unit}
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
            
            {/* 底部填充 */}
            <div style={{ height: itemSize * 2 }} />
          </div>
          
          {/* 渐变遮罩 - 最上层，但不遮挡中间选中区域 */}
          <div 
            className="absolute inset-x-0 top-0 pointer-events-none"
            style={{ 
              height: itemSize * 1.8,
              background: `linear-gradient(to bottom, ${colors.white} 0%, ${colors.white} 30%, transparent 100%)`,
              zIndex: 3,
            }}
          />
          <div 
            className="absolute inset-x-0 bottom-0 pointer-events-none"
            style={{ 
              height: itemSize * 1.8,
              background: `linear-gradient(to top, ${colors.white} 0%, ${colors.white} 30%, transparent 100%)`,
              zIndex: 3,
            }}
          />
        </div>
      </div>
    )
  }
  
  // 水平模式 - 紧凑设计
  return (
    <div className="flex flex-col items-center">
      {label && (
        <p 
          className="text-[12px] font-medium mb-2"
          style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}
        >
          {label}
        </p>
      )}
      
      <div className="relative w-full" style={{ height: 56 }}>
        {/* 选中指示条 - 最底层 */}
        <div 
          className="absolute left-1/2 top-0 bottom-0 -translate-x-1/2 rounded-xl pointer-events-none"
          style={{ 
            width: itemSize,
            background: colors.slate[100],
            border: `1px solid ${colors.slate[200]}`,
            zIndex: 1,
          }}
        />
        
        {/* 滚动容器 - 中间层，阻止垂直滚动传播 */}
        <div
          ref={scrollRef}
          className="h-full overflow-x-auto scrollbar-hide flex items-center relative"
          style={{
            scrollSnapType: 'x mandatory',
            WebkitOverflowScrolling: 'touch',
            scrollbarWidth: 'none',
            msOverflowStyle: 'none',
            zIndex: 2,
            touchAction: 'pan-x',  // 只允许水平滑动
            overscrollBehavior: 'contain',  // 阻止滚动传播
          }}
          onScroll={handleScroll}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
        >
          {/* 左侧填充 */}
          <div className="flex-shrink-0" style={{ width: `calc(50% - ${itemSize / 2}px)` }} />
          
          {/* 数值列表 */}
          {values.map((v) => {
            const isSelected = v === value
            return (
              <div
                key={v}
                className="flex-shrink-0 flex items-center justify-center"
                style={{ 
                  width: itemSize,
                  scrollSnapAlign: 'center',
                }}
              >
                <span 
                  className="text-[26px] font-medium tabular-nums transition-all duration-150"
                  style={{ 
                    color: isSelected ? colors.text.primary : colors.text.tertiary,
                    letterSpacing: '-0.4px',
                    opacity: isSelected ? 1 : 0.4,
                    transform: isSelected ? 'scale(1)' : 'scale(0.75)',
                  }}
                >
                  {v}
                </span>
              </div>
            )
          })}
          
          {/* 右侧填充 */}
          <div className="flex-shrink-0" style={{ width: `calc(50% - ${itemSize / 2}px)` }} />
        </div>
        
        {/* 渐变遮罩 - 最上层，淡化边缘 */}
        <div 
          className="absolute inset-y-0 left-0 pointer-events-none"
          style={{ 
            width: itemSize * 1.5,
            background: `linear-gradient(to right, ${colors.white} 0%, ${colors.white} 20%, transparent 100%)`,
            zIndex: 3,
          }}
        />
        <div 
          className="absolute inset-y-0 right-0 pointer-events-none"
          style={{ 
            width: itemSize * 1.5,
            background: `linear-gradient(to left, ${colors.white} 0%, ${colors.white} 20%, transparent 100%)`,
            zIndex: 3,
          }}
        />
      </div>
      
      {unit && (
        <p 
          className="text-[14px] font-medium mt-1"
          style={{ color: colors.text.secondary, letterSpacing: '-0.4px' }}
        >
          {unit}
        </p>
      )}
    </div>
  )
}
