/**
 * 错误状态显示组件
 * Phase 7.7: 错误状态 UI
 */

import { motion } from 'motion/react';
import { RefreshCw, XCircle, AlertTriangle, StopCircle, WifiOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { AgentErrorType, AgentError } from '@/types/agent';

// 错误类型配置
interface ErrorConfig {
  icon: React.ReactNode;
  title: string;
  message: string;
  action?: {
    label: string;
    handler: string;
  };
  color: string;
}

const ERROR_TYPES: Record<AgentErrorType, ErrorConfig> = {
  api_timeout: {
    icon: <RefreshCw className="h-5 w-5 animate-spin" />,
    title: 'API 响应超时',
    message: '正在自动重试...',
    action: undefined,
    color: 'yellow',
  },
  window_lost: {
    icon: <XCircle className="h-5 w-5" />,
    title: '目标窗口丢失',
    message: '请重新打开窗口',
    action: { label: '重新连接', handler: 'reconnect' },
    color: 'red',
  },
  tool_failed: {
    icon: <AlertTriangle className="h-5 w-5" />,
    title: '操作执行失败',
    message: 'AI 正在尝试其他方法',
    action: undefined,
    color: 'orange',
  },
  emergency_stop: {
    icon: <StopCircle className="h-5 w-5" />,
    title: '紧急停止',
    message: '任务已保存，可恢复',
    action: { label: '恢复任务', handler: 'resume' },
    color: 'red',
  },
  connection_error: {
    icon: <WifiOff className="h-5 w-5" />,
    title: '连接中断',
    message: '正在尝试重新连接...',
    action: { label: '手动重连', handler: 'reconnect' },
    color: 'yellow',
  },
  unknown: {
    icon: <AlertTriangle className="h-5 w-5" />,
    title: '未知错误',
    message: '发生了意外错误',
    action: { label: '重试', handler: 'retry' },
    color: 'red',
  },
};

const colorClasses: Record<string, { bg: string; border: string; text: string }> = {
  yellow: {
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    text: 'text-yellow-400',
  },
  red: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    text: 'text-red-400',
  },
  orange: {
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/30',
    text: 'text-orange-400',
  },
};

interface ErrorDisplayProps {
  error: AgentError;
  onAction?: (handler: string) => void;
  className?: string;
  compact?: boolean;
}

export function ErrorDisplay({
  error,
  onAction,
  className,
  compact = false,
}: ErrorDisplayProps) {
  const config = ERROR_TYPES[error.type] || ERROR_TYPES.unknown;
  const colors = colorClasses[config.color];

  return (
    <motion.div
      className={cn(
        'rounded-lg border',
        colors.bg,
        colors.border,
        compact ? 'px-3 py-2' : 'p-4',
        className
      )}
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
    >
      <div className={cn('flex items-start gap-3', compact && 'items-center')}>
        {/* 图标 */}
        <div className={cn(colors.text, compact && 'scale-90')}>
          {config.icon}
        </div>

        {/* 内容 */}
        <div className="flex-1 min-w-0">
          <h4 className={cn('font-medium text-white', compact && 'text-sm')}>
            {config.title}
          </h4>
          {!compact && (
            <p className="mt-0.5 text-sm text-white/60">{config.message}</p>
          )}
          {error.detail && !compact && (
            <p className="mt-1 text-xs text-white/40 font-mono truncate">
              {error.detail}
            </p>
          )}
        </div>

        {/* 操作按钮 */}
        {config.action && onAction && (
          <Button
            size={compact ? 'sm' : 'default'}
            variant="ghost"
            className={cn(
              'shrink-0',
              colors.text,
              'hover:bg-white/10 hover:text-white'
            )}
            onClick={() => onAction(config.action!.handler)}
          >
            {config.action.label}
          </Button>
        )}
      </div>
    </motion.div>
  );
}

// 紧凑型错误提示（用于消息列表）
export function InlineError({
  message,
  recoverable = false,
  onRetry,
}: {
  message: string;
  recoverable?: boolean;
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md bg-red-500/10 px-3 py-2 text-xs text-red-400">
      <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
      <span className="flex-1">{message}</span>
      {recoverable && onRetry && (
        <button
          onClick={onRetry}
          className="rounded px-2 py-0.5 text-white/70 transition-colors hover:bg-white/10 hover:text-white"
        >
          重试
        </button>
      )}
    </div>
  );
}
