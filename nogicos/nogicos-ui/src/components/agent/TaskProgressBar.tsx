/**
 * 任务进度条
 * Phase 7.2: 进度可视化
 */

import { motion } from 'motion/react';
import { cn } from '@/lib/utils';
import type { AgentProgress } from '@/types/agent';

interface TaskProgressBarProps {
  progress: AgentProgress;
  className?: string;
  showDetails?: boolean;
}

export function TaskProgressBar({
  progress,
  className,
  showDetails = true,
}: TaskProgressBarProps) {
  const percent = Math.min(
    (progress.iteration / progress.maxIterations) * 100,
    100
  );

  return (
    <div className={cn('space-y-2', className)}>
      {/* 进度条 */}
      <div className="relative h-2 overflow-hidden rounded-full bg-white/10">
        <motion.div
          className="absolute inset-y-0 left-0 bg-gradient-to-r from-emerald-500 to-emerald-400"
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ type: 'spring', stiffness: 100, damping: 15 }}
        />
        {/* 进度条光效 */}
        <motion.div
          className="absolute inset-y-0 w-20 bg-gradient-to-r from-transparent via-white/20 to-transparent"
          animate={{ x: ['0%', '500%'] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
        />
      </div>

      {/* 进度信息 */}
      {showDetails && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-white/60">
          {/* 步骤进度 */}
          <span className="font-medium text-white/80">
            步骤 {progress.iteration}/{progress.maxIterations}
          </span>

          {/* 工具调用数 */}
          <span className="flex items-center gap-1">
            <span className="text-emerald-400">⚡</span>
            已执行 {progress.toolCalls} 个操作
          </span>

          {/* 当前操作窗口 */}
          {progress.currentWindow && (
            <span className="flex items-center gap-1">
              <span className="text-blue-400">🖥</span>
              {progress.currentWindow}
            </span>
          )}

          {/* 预计剩余时间 */}
          {progress.estimatedTime !== undefined && progress.estimatedTime > 0 && (
            <span className="flex items-center gap-1">
              <span className="text-yellow-400">⏱</span>
              预计 {formatTime(progress.estimatedTime)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// 格式化时间显示
function formatTime(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

// 紧凑版进度指示器
export function CompactProgress({ progress }: { progress: AgentProgress }) {
  const percent = Math.min(
    (progress.iteration / progress.maxIterations) * 100,
    100
  );

  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-white/10">
        <motion.div
          className="h-full bg-emerald-400"
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ type: 'spring', stiffness: 100 }}
        />
      </div>
      <span className="text-white/50">
        {progress.iteration}/{progress.maxIterations}
      </span>
    </div>
  );
}
