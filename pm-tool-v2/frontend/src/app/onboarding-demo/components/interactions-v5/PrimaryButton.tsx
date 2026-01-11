'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import { colorsV5, shadowsV5, radiiV5, typographyV5 } from '../../lib/design-tokens-v5'

interface PrimaryButtonProps {
  children: React.ReactNode
  onClick?: () => void
  disabled?: boolean
  loading?: boolean
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md' | 'lg' | 'xl'
  fullWidth?: boolean
  icon?: React.ReactNode
  iconPosition?: 'left' | 'right'
  className?: string
}

const sizeStyles = {
  sm: {
    height: 40,
    padding: '0 20px',
    fontSize: typographyV5.fontSize.sm,
    iconSize: 16,
    borderRadius: radiiV5.lg,
  },
  md: {
    height: 48,
    padding: '0 24px',
    fontSize: typographyV5.fontSize.base,
    iconSize: 18,
    borderRadius: radiiV5.xl,
  },
  lg: {
    height: 56,
    padding: '0 32px',
    fontSize: typographyV5.fontSize.lg,
    iconSize: 20,
    borderRadius: radiiV5.xl,
  },
  xl: {
    height: 64,
    padding: '0 40px',
    fontSize: typographyV5.fontSize.xl,
    iconSize: 24,
    borderRadius: radiiV5['2xl'],
  },
}

export function PrimaryButton({
  children,
  onClick,
  disabled = false,
  loading = false,
  variant = 'primary',
  size = 'lg',
  fullWidth = false,
  icon,
  iconPosition = 'right',
  className = '',
}: PrimaryButtonProps) {
  const styles = sizeStyles[size]
  
  const getVariantStyles = () => {
    switch (variant) {
      case 'primary':
        return {
          background: colorsV5.slate[900],
          color: colorsV5.white,
          boxShadow: shadowsV5.button.default,
        }
      case 'secondary':
        return {
          background: colorsV5.white,
          color: colorsV5.slate[900],
          boxShadow: shadowsV5.card.default,
          border: `2px solid ${colorsV5.slate[200]}`,
        }
      case 'ghost':
        return {
          background: 'transparent',
          color: colorsV5.slate[600],
          boxShadow: 'none',
        }
      default:
        return {}
    }
  }

  const getHoverStyles = () => {
    switch (variant) {
      case 'primary':
        return {
          background: colorsV5.slate[800],
          boxShadow: shadowsV5.button.hover,
        }
      case 'secondary':
        return {
          background: colorsV5.slate[50],
          borderColor: colorsV5.slate[300],
        }
      case 'ghost':
        return {
          background: colorsV5.slate[100],
        }
      default:
        return {}
    }
  }

  const isDisabled = disabled || loading

  return (
    <motion.button
      className={`
        relative inline-flex items-center justify-center gap-3
        font-semibold transition-colors
        ${fullWidth ? 'w-full' : ''}
        ${className}
      `}
      style={{
        height: styles.height,
        padding: styles.padding,
        fontSize: styles.fontSize,
        borderRadius: styles.borderRadius,
        opacity: isDisabled ? 0.5 : 1,
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        ...getVariantStyles(),
      }}
      onClick={isDisabled ? undefined : onClick}
      whileHover={isDisabled ? {} : {
        scale: 1.02,
        y: -2,
        ...getHoverStyles(),
      }}
      whileTap={isDisabled ? {} : { scale: 0.98 }}
      transition={{ duration: 0.2 }}
    >
      {/* Loading spinner */}
      {loading && (
        <motion.div
          className="absolute inset-0 flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <Loader2 
            size={styles.iconSize} 
            className="animate-spin" 
          />
        </motion.div>
      )}

      {/* Content */}
      <motion.div
        className="flex items-center gap-3"
        animate={{ opacity: loading ? 0 : 1 }}
      >
        {icon && iconPosition === 'left' && (
          <span className="flex-shrink-0">{icon}</span>
        )}
        <span>{children}</span>
        {icon && iconPosition === 'right' && (
          <span className="flex-shrink-0">{icon}</span>
        )}
      </motion.div>

      {/* Shine effect */}
      {variant === 'primary' && !isDisabled && (
        <motion.div
          className="absolute inset-0 overflow-hidden rounded-inherit"
          style={{ borderRadius: 'inherit' }}
        >
          <motion.div
            className="absolute inset-0"
            style={{
              background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent)',
              transform: 'translateX(-100%)',
            }}
            animate={{
              transform: ['translateX(-100%)', 'translateX(100%)'],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              repeatDelay: 3,
              ease: 'easeInOut',
            }}
          />
        </motion.div>
      )}
    </motion.button>
  )
}

export default PrimaryButton
