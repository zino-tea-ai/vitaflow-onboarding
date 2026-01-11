'use client'

import React, { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence, useMotionValue, useTransform } from 'framer-motion'
import { Minus, Plus } from 'lucide-react'
import { colorsV5, shadowsV5, radiiV5, typographyV5 } from '../../lib/design-tokens-v5'

interface NaturalNumberInputProps {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  unit?: string
  label?: string
  size?: 'sm' | 'md' | 'lg'
  showSlider?: boolean
  className?: string
}

export function NaturalNumberInput({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  unit = '',
  label,
  size = 'lg',
  showSlider = true,
  className = '',
}: NaturalNumberInputProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [inputValue, setInputValue] = useState(value.toString())
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  
  // 拖拽相关
  const dragStartY = useRef(0)
  const dragStartValue = useRef(value)
  
  const fontSizes = {
    sm: typographyV5.fontSize['4xl'],
    md: typographyV5.fontSize['5xl'],
    lg: typographyV5.fontSize['6xl'],
  }

  // 更新输入值
  useEffect(() => {
    if (!isEditing) {
      setInputValue(value.toString())
    }
  }, [value, isEditing])

  // 处理拖拽
  const handleDragStart = (e: React.MouseEvent | React.TouchEvent) => {
    setIsDragging(true)
    dragStartY.current = 'touches' in e ? e.touches[0].clientY : e.clientY
    dragStartValue.current = value
  }

  const handleDrag = (e: MouseEvent | TouchEvent) => {
    if (!isDragging) return
    
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY
    const delta = dragStartY.current - clientY
    const valueChange = Math.round(delta / 10) * step
    const newValue = Math.min(max, Math.max(min, dragStartValue.current + valueChange))
    
    onChange(newValue)
  }

  const handleDragEnd = () => {
    setIsDragging(false)
  }

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleDrag)
      window.addEventListener('mouseup', handleDragEnd)
      window.addEventListener('touchmove', handleDrag)
      window.addEventListener('touchend', handleDragEnd)
      
      return () => {
        window.removeEventListener('mousemove', handleDrag)
        window.removeEventListener('mouseup', handleDragEnd)
        window.removeEventListener('touchmove', handleDrag)
        window.removeEventListener('touchend', handleDragEnd)
      }
    }
  }, [isDragging])

  // 增减按钮
  const increment = () => {
    const newValue = Math.min(max, value + step)
    onChange(newValue)
  }

  const decrement = () => {
    const newValue = Math.max(min, value - step)
    onChange(newValue)
  }

  // 直接编辑
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value)
  }

  const handleInputBlur = () => {
    setIsEditing(false)
    const numValue = parseFloat(inputValue)
    if (!isNaN(numValue)) {
      const clampedValue = Math.min(max, Math.max(min, numValue))
      onChange(clampedValue)
      setInputValue(clampedValue.toString())
    } else {
      setInputValue(value.toString())
    }
  }

  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleInputBlur()
    }
  }

  // 计算进度百分比
  const progress = ((value - min) / (max - min)) * 100

  return (
    <div className={`flex flex-col items-center ${className}`}>
      {/* 标签 */}
      {label && (
        <motion.div
          className="mb-4 text-center"
          style={{
            fontSize: typographyV5.fontSize.lg,
            color: colorsV5.slate[500],
          }}
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          {label}
        </motion.div>
      )}

      {/* 主输入区域 */}
      <div
        ref={containerRef}
        className="relative flex items-center justify-center gap-6"
      >
        {/* 减少按钮 */}
        <motion.button
          className="flex items-center justify-center"
          style={{
            width: 48,
            height: 48,
            borderRadius: radiiV5.full,
            background: colorsV5.slate[100],
            color: colorsV5.slate[600],
          }}
          whileHover={{ 
            scale: 1.1, 
            background: colorsV5.slate[200],
          }}
          whileTap={{ scale: 0.95 }}
          onClick={decrement}
          disabled={value <= min}
        >
          <Minus size={20} strokeWidth={2.5} />
        </motion.button>

        {/* 数字显示 */}
        <motion.div
          className="relative cursor-ns-resize select-none"
          onMouseDown={handleDragStart}
          onTouchStart={handleDragStart}
          onClick={() => {
            setIsEditing(true)
            setTimeout(() => inputRef.current?.focus(), 0)
          }}
          animate={{
            scale: isDragging ? 1.05 : 1,
          }}
          transition={{ duration: 0.15 }}
        >
          {isEditing ? (
            <input
              ref={inputRef}
              type="number"
              value={inputValue}
              onChange={handleInputChange}
              onBlur={handleInputBlur}
              onKeyDown={handleInputKeyDown}
              className="text-center bg-transparent outline-none"
              style={{
                fontSize: fontSizes[size],
                fontWeight: typographyV5.fontWeight.bold,
                color: colorsV5.slate[900],
                width: `${Math.max(3, inputValue.length + 1)}ch`,
                caretColor: colorsV5.mint[500],
              }}
            />
          ) : (
            <motion.span
              style={{
                fontSize: fontSizes[size],
                fontWeight: typographyV5.fontWeight.bold,
                color: colorsV5.slate[900],
                lineHeight: 1,
              }}
              key={value}
              initial={{ opacity: 0, y: isDragging ? -20 : 0 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.15 }}
            >
              {value}
            </motion.span>
          )}
          
          {/* 单位 */}
          {unit && !isEditing && (
            <span
              className="ml-2"
              style={{
                fontSize: typographyV5.fontSize['2xl'],
                fontWeight: typographyV5.fontWeight.medium,
                color: colorsV5.slate[400],
              }}
            >
              {unit}
            </span>
          )}

          {/* 拖拽提示 */}
          <AnimatePresence>
            {isDragging && (
              <motion.div
                className="absolute left-1/2 -translate-x-1/2 -top-8"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                style={{
                  fontSize: typographyV5.fontSize.sm,
                  color: colorsV5.slate[500],
                  whiteSpace: 'nowrap',
                }}
              >
                Drag to adjust
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* 增加按钮 */}
        <motion.button
          className="flex items-center justify-center"
          style={{
            width: 48,
            height: 48,
            borderRadius: radiiV5.full,
            background: colorsV5.slate[100],
            color: colorsV5.slate[600],
          }}
          whileHover={{ 
            scale: 1.1, 
            background: colorsV5.slate[200],
          }}
          whileTap={{ scale: 0.95 }}
          onClick={increment}
          disabled={value >= max}
        >
          <Plus size={20} strokeWidth={2.5} />
        </motion.button>
      </div>

      {/* 滑块 */}
      {showSlider && (
        <motion.div
          className="w-full max-w-[280px] mt-8"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          {/* 滑块轨道 */}
          <div
            className="relative h-2 rounded-full overflow-hidden"
            style={{ background: colorsV5.slate[200] }}
          >
            {/* 进度条 */}
            <motion.div
              className="absolute left-0 top-0 h-full rounded-full"
              style={{ background: colorsV5.mint[500] }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.2 }}
            />
          </div>

          {/* 范围标签 */}
          <div
            className="flex justify-between mt-2"
            style={{
              fontSize: typographyV5.fontSize.sm,
              color: colorsV5.slate[400],
            }}
          >
            <span>{min}{unit}</span>
            <span>{max}{unit}</span>
          </div>
        </motion.div>
      )}
    </div>
  )
}

export default NaturalNumberInput
