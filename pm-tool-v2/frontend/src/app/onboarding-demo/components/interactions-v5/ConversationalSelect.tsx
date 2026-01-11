'use client'

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Check } from 'lucide-react'
import { colorsV5, shadowsV5, radiiV5 } from '../../lib/design-tokens-v5'
import { interactionAnimations, staggerAnimations } from '../../lib/animation-presets'

export interface SelectOption {
  id: string
  label: string
  description?: string
  icon?: React.ReactNode
  emoji?: string
}

interface ConversationalSelectProps {
  options: SelectOption[]
  value?: string
  onChange?: (value: string) => void
  multiSelect?: boolean
  layout?: 'vertical' | 'horizontal' | 'grid'
  size?: 'sm' | 'md' | 'lg'
  showCheckmark?: boolean
  className?: string
}

const sizeStyles = {
  sm: {
    padding: '12px 16px',
    fontSize: '14px',
    iconSize: 20,
    gap: '8px',
  },
  md: {
    padding: '16px 20px',
    fontSize: '16px',
    iconSize: 24,
    gap: '12px',
  },
  lg: {
    padding: '20px 24px',
    fontSize: '18px',
    iconSize: 32,
    gap: '16px',
  },
}

export function ConversationalSelect({
  options,
  value,
  onChange,
  multiSelect = false,
  layout = 'vertical',
  size = 'md',
  showCheckmark = true,
  className = '',
}: ConversationalSelectProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const styles = sizeStyles[size]
  const selectedValues = multiSelect ? (value?.split(',') || []) : [value]

  const handleSelect = (optionId: string) => {
    if (multiSelect) {
      const currentValues = value?.split(',').filter(Boolean) || []
      const newValues = currentValues.includes(optionId)
        ? currentValues.filter(v => v !== optionId)
        : [...currentValues, optionId]
      onChange?.(newValues.join(','))
    } else {
      onChange?.(optionId)
    }
  }

  const isSelected = (optionId: string) => selectedValues.includes(optionId)

  const getLayoutStyles = () => {
    switch (layout) {
      case 'horizontal':
        return 'flex flex-row gap-3 flex-wrap justify-center'
      case 'grid':
        return 'grid grid-cols-2 gap-3'
      default:
        return 'flex flex-col gap-3'
    }
  }

  return (
    <motion.div
      className={`${getLayoutStyles()} ${className}`}
      variants={staggerAnimations.container}
      initial="initial"
      animate="animate"
    >
      {options.map((option, index) => {
        const selected = isSelected(option.id)
        const hovered = hoveredId === option.id

        return (
          <motion.button
            key={option.id}
            className="relative text-left transition-all duration-200 outline-none"
            style={{
              padding: styles.padding,
              borderRadius: radiiV5.xl,
              background: selected 
                ? colorsV5.slate[900]
                : colorsV5.white,
              color: selected 
                ? colorsV5.white 
                : colorsV5.slate[900],
              boxShadow: selected
                ? shadowsV5.card.selected
                : hovered
                ? shadowsV5.card.hover
                : shadowsV5.card.default,
              border: `2px solid ${selected ? colorsV5.slate[900] : 'transparent'}`,
            }}
            variants={staggerAnimations.item}
            whileHover={{ 
              scale: 1.02, 
              y: -4,
              transition: { duration: 0.2 }
            }}
            whileTap={{ scale: 0.98 }}
            onHoverStart={() => setHoveredId(option.id)}
            onHoverEnd={() => setHoveredId(null)}
            onClick={() => handleSelect(option.id)}
          >
            <div className="flex items-center" style={{ gap: styles.gap }}>
              {/* Icon or Emoji */}
              {(option.icon || option.emoji) && (
                <div
                  className="flex items-center justify-center shrink-0"
                  style={{
                    width: styles.iconSize + 16,
                    height: styles.iconSize + 16,
                    borderRadius: radiiV5.lg,
                    background: selected 
                      ? `${colorsV5.white}15`
                      : colorsV5.slate[100],
                    fontSize: styles.iconSize,
                  }}
                >
                  {option.emoji || option.icon}
                </div>
              )}

              {/* Text Content */}
              <div className="flex-1 min-w-0">
                <div 
                  className="font-semibold"
                  style={{ fontSize: styles.fontSize }}
                >
                  {option.label}
                </div>
                {option.description && (
                  <div 
                    className="mt-1 opacity-70"
                    style={{ fontSize: `calc(${styles.fontSize} - 2px)` }}
                  >
                    {option.description}
                  </div>
                )}
              </div>

              {/* Checkmark */}
              {showCheckmark && (
                <AnimatePresence>
                  {selected && (
                    <motion.div
                      className="flex items-center justify-center shrink-0"
                      style={{
                        width: 24,
                        height: 24,
                        borderRadius: radiiV5.full,
                        background: colorsV5.mint[500],
                      }}
                      initial={{ scale: 0, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0, opacity: 0 }}
                      transition={{ 
                        type: 'spring',
                        stiffness: 500,
                        damping: 30,
                      }}
                    >
                      <Check size={14} color={colorsV5.slate[900]} strokeWidth={3} />
                    </motion.div>
                  )}
                </AnimatePresence>
              )}
            </div>

            {/* Selection indicator line */}
            <motion.div
              className="absolute left-0 top-1/2 -translate-y-1/2 rounded-r-full"
              style={{
                width: 4,
                height: '60%',
                background: colorsV5.mint[500],
              }}
              initial={{ scaleY: 0 }}
              animate={{ scaleY: selected ? 1 : 0 }}
              transition={{ duration: 0.2 }}
            />
          </motion.button>
        )
      })}
    </motion.div>
  )
}

export default ConversationalSelect
