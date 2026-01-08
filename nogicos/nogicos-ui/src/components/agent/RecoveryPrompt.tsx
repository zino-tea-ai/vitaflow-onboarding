/**
 * 任务恢复提示
 * Phase 7.8: 任务恢复提示
 */

import { motion, AnimatePresence } from 'motion/react';
import { History, Trash2, Play } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import type { AgentTask } from '@/types/agent';

interface RecoveryPromptProps {
  tasks: AgentTask[];
  onRecover: (taskId: string) => void;
  onDiscard: (taskId: string) => void;
  onDiscardAll: () => void;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function RecoveryPrompt({
  tasks,
  onRecover,
  onDiscard,
  onDiscardAll,
  open = true,
  onOpenChange,
}: RecoveryPromptProps) {
  if (tasks.length === 0) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md border-white/10 bg-zinc-900/95 backdrop-blur-xl">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-blue-500/20 p-2">
              <History className="h-5 w-5 text-blue-400" />
            </div>
            <div>
              <DialogTitle className="text-white">发现未完成的任务</DialogTitle>
              <p className="mt-0.5 text-xs text-white/50">
                上次会话中有 {tasks.length} 个任务未完成
              </p>
            </div>
          </div>
        </DialogHeader>

        <div className="max-h-64 space-y-2 overflow-y-auto py-4">
          <AnimatePresence mode="popLayout">
            {tasks.map((task, index) => (
              <TaskItem
                key={task.id}
                task={task}
                index={index}
                onRecover={onRecover}
                onDiscard={onDiscard}
              />
            ))}
          </AnimatePresence>
        </div>

        <div className="flex justify-between border-t border-white/5 pt-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={onDiscardAll}
            className="text-white/50 hover:bg-red-500/10 hover:text-red-400"
          >
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            全部放弃
          </Button>
          <p className="text-xs text-white/30">
            按 ESC 稍后处理
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// 单个任务项
function TaskItem({
  task,
  index,
  onRecover,
  onDiscard,
}: {
  task: AgentTask;
  index: number;
  onRecover: (taskId: string) => void;
  onDiscard: (taskId: string) => void;
}) {
  const progressPercent = Math.round(
    (task.progress.iteration / task.progress.maxIterations) * 100
  );

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20, scale: 0.9 }}
      transition={{ delay: index * 0.05 }}
      className="group rounded-lg border border-white/10 bg-white/5 p-3 transition-colors hover:border-white/20"
    >
      <div className="flex items-start justify-between gap-3">
        {/* 任务信息 */}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-white">
            {task.task_text}
          </p>
          <div className="mt-1 flex items-center gap-3 text-xs text-white/50">
            <span>
              进度: {task.progress.iteration}/{task.progress.maxIterations} ({progressPercent}%)
            </span>
            <span>·</span>
            <span>{formatTimeAgo(task.updatedAt)}</span>
          </div>
          {/* 迷你进度条 */}
          <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full bg-emerald-400 transition-all"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="flex shrink-0 gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onDiscard(task.id)}
            className="h-8 w-8 p-0 text-white/40 hover:bg-red-500/10 hover:text-red-400"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            onClick={() => onRecover(task.id)}
            className="h-8 bg-emerald-500/20 px-3 text-emerald-400 hover:bg-emerald-500/30"
          >
            <Play className="mr-1 h-3.5 w-3.5" />
            继续
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

// 格式化时间
function formatTimeAgo(timestamp: number): string {
  const now = Date.now();
  const diff = now - timestamp;

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (days > 0) return `${days} 天前`;
  if (hours > 0) return `${hours} 小时前`;
  if (minutes > 0) return `${minutes} 分钟前`;
  return '刚刚';
}
