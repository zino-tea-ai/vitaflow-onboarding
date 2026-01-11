'use client'

import { motion } from 'framer-motion'
import * as LucideIcons from 'lucide-react'
import { LucideIcon } from 'lucide-react'
import { shadows, cardBorder } from '../../lib/design-tokens'

interface OptionCardProps {
  icon: string
  title: string
  subtitle?: string
  selected?: boolean
  onClick?: () => void
  index?: number
}

// 动态获取 Lucide 图标
function getIcon(name: string): LucideIcon {
  const icons = LucideIcons as unknown as Record<string, LucideIcon>
  return icons[name] || LucideIcons.Circle
}

export function OptionCard({ 
  icon, 
  title, 
  subtitle, 
  selected = false, 
  onClick,
  index = 0
}: OptionCardProps) {
  const Icon = getIcon(icon)
  
  return (
    <motion.button
      onClick={onClick}
      className="relative w-full p-4 rounded-[12px] text-left transition-all duration-200"
      style={{
        background: '#FFFFFF',
        border: cardBorder.default,
        boxShadow: selected 
          ? shadows.cardSelected
          : shadows.card,
        fontFamily: 'var(--font-outfit)'
      }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.4,
        delay: index * 0.08,
        ease: [0.25, 0.46, 0.45, 0.94]
      }}
      whileHover={{ 
        y: -2,
        boxShadow: shadows.cardHover
      }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="relative flex items-center gap-4">
        {/* 图标容器 - Slate 配色 */}
        <motion.div 
          className="flex-shrink-0 w-12 h-12 rounded-[8px] flex items-center justify-center"
          style={{
            background: selected ? '#0F172A' : '#F1F5F9'
          }}
          animate={{
            scale: selected ? [1, 1.05, 1] : 1,
          }}
          transition={{ 
            duration: 0.3,
            ease: 'easeInOut'
          }}
        >
          <Icon 
            className="w-6 h-6"
            style={{ color: selected ? '#FFFFFF' : '#0F172A' }}
            strokeWidth={2}
          />
        </motion.div>
        
        {/* 文本 - Figma 规范 */}
        <div className="flex-1 min-w-0">
          <p 
            className="font-medium text-[14px]"
            style={{ 
              color: '#0F172A',
              letterSpacing: '-0.4px',
            }}
          >
            {title}
          </p>
          {subtitle && (
            <p 
              className="text-[12px] mt-1"
              style={{ 
                color: '#64748B',
                letterSpacing: '-0.4px',
              }}
            >
              {subtitle}
            </p>
          )}
        </div>
        
        {/* 选中指示器 - Slate-900 */}
        <motion.div 
          className="flex-shrink-0 w-6 h-6 rounded-full border-2 flex items-center justify-center"
          style={{
            borderColor: selected ? '#0F172A' : '#CBD5E1',
            background: selected ? '#0F172A' : 'transparent'
          }}
        >
          {selected && (
            <motion.svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.2, delay: 0.1 }}
            >
              <path
                d="M2 6L5 9L10 3"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </motion.svg>
          )}
        </motion.div>
      </div>
    </motion.button>
  )
}

// VitaFlow 多选版本 - Figma 规范
export function OptionCardMulti({ 
  icon, 
  title, 
  subtitle, 
  selected = false, 
  onClick,
  index = 0
}: OptionCardProps) {
  const Icon = getIcon(icon)
  
  return (
    <motion.button
      onClick={onClick}
      className="relative w-full p-3 rounded-[12px] text-left transition-all duration-200"
      style={{
        background: '#FFFFFF',
        border: cardBorder.default,
        boxShadow: selected 
          ? shadows.cardSelected
          : shadows.card,
        fontFamily: 'var(--font-outfit)'
      }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.4,
        delay: index * 0.06,
        ease: [0.25, 0.46, 0.45, 0.94]
      }}
      whileHover={{ boxShadow: shadows.cardHover }}
      whileTap={{ scale: 0.99 }}
    >
      <div className="relative flex items-center gap-3">
        {/* 复选框 - Slate 配色 */}
        <motion.div 
          className="flex-shrink-0 w-6 h-6 rounded-[6px] border-2 flex items-center justify-center"
          style={{
            borderColor: selected ? '#0F172A' : '#CBD5E1',
            background: selected ? '#0F172A' : '#FFFFFF'
          }}
        >
          {selected && (
            <motion.svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 500, damping: 30 }}
            >
              <path
                d="M2 6L5 9L10 3"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </motion.svg>
          )}
        </motion.div>
        
        {/* 图标 */}
        <div 
          className="flex-shrink-0 w-10 h-10 rounded-[8px] flex items-center justify-center"
          style={{
            background: selected ? 'rgba(15, 23, 42, 0.1)' : '#F1F5F9'
          }}
        >
          <Icon 
            className="w-5 h-5"
            style={{ color: selected ? '#0F172A' : '#64748B' }}
            strokeWidth={2}
          />
        </div>
        
        {/* 文本 - Figma 规范 */}
        <div className="flex-1 min-w-0">
          <p 
            className="font-medium text-[14px]"
            style={{ 
              color: '#0F172A',
              letterSpacing: '-0.4px',
            }}
          >
            {title}
          </p>
          {subtitle && (
            <p 
              className="text-[12px] mt-1"
              style={{ 
                color: '#64748B',
                letterSpacing: '-0.4px',
              }}
            >
              {subtitle}
            </p>
          )}
        </div>
      </div>
    </motion.button>
  )
}
