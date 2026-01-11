'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, Check, Heart, ThumbsUp } from 'lucide-react'

interface InlineFeedbackProps {
  text: string
  visible: boolean
  icon?: 'sparkles' | 'check' | 'heart' | 'thumbsUp'
  className?: string
}

const iconMap = {
  sparkles: Sparkles,
  check: Check,
  heart: Heart,
  thumbsUp: ThumbsUp,
}

/**
 * InlineFeedback - 纯文字内联反馈组件
 * 用于表单页选择/输入后的即时反馈
 * 无角色头像，只有图标+文字
 */
export function InlineFeedback({ 
  text, 
  visible, 
  icon = 'sparkles',
  className = ''
}: InlineFeedbackProps) {
  const Icon = iconMap[icon]
  
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className={`flex items-center gap-1.5 ${className}`}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ 
            duration: 0.25, 
            ease: 'easeOut' 
          }}
        >
          <Icon 
            size={14} 
            className="text-[#61E0BD] flex-shrink-0" 
          />
          <span 
            className="text-sm"
            style={{ 
              color: '#64748B',
              fontFamily: 'var(--font-outfit)'
            }}
          >
            {text}
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

/**
 * InlineFeedbackSuccess - 成功状态反馈
 */
export function InlineFeedbackSuccess({ 
  text, 
  visible,
  className = ''
}: Omit<InlineFeedbackProps, 'icon'>) {
  return (
    <InlineFeedback 
      text={text} 
      visible={visible} 
      icon="check"
      className={className}
    />
  )
}

/**
 * InlineFeedbackEncourage - 鼓励反馈
 */
export function InlineFeedbackEncourage({ 
  text, 
  visible,
  className = ''
}: Omit<InlineFeedbackProps, 'icon'>) {
  return (
    <InlineFeedback 
      text={text} 
      visible={visible} 
      icon="heart"
      className={className}
    />
  )
}
