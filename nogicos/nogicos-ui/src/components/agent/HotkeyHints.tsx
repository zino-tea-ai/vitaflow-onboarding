/**
 * 快捷键提示
 * Phase 7.9: 快捷键支持
 */

import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/lib/utils';

interface Hotkey {
  key: string;
  label: string;
  enabled?: boolean;
}

const DEFAULT_HOTKEYS: Hotkey[] = [
  { key: 'Esc', label: '紧急停止' },
  { key: 'Space', label: '暂停/继续' },
  { key: 'Enter', label: '确认操作' },
  { key: 'Tab', label: '切换窗口' },
];

interface HotkeyHintsProps {
  visible: boolean;
  hotkeys?: Hotkey[];
  position?: 'bottom-left' | 'bottom-right' | 'bottom-center';
  className?: string;
}

export function HotkeyHints({
  visible,
  hotkeys = DEFAULT_HOTKEYS,
  position = 'bottom-right',
  className,
}: HotkeyHintsProps) {
  const positionClasses = {
    'bottom-left': 'left-4 bottom-4',
    'bottom-right': 'right-4 bottom-4',
    'bottom-center': 'left-1/2 bottom-4 -translate-x-1/2',
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className={cn(
            'fixed z-50 flex gap-2 rounded-lg border border-white/10 bg-zinc-900/90 px-3 py-2 backdrop-blur-sm',
            positionClasses[position],
            className
          )}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        >
          {hotkeys.map((hotkey) => (
            <HotkeyItem
              key={hotkey.key}
              hotkey={hotkey}
            />
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// 单个快捷键项
function HotkeyItem({ hotkey }: { hotkey: Hotkey }) {
  const isDisabled = hotkey.enabled === false;

  return (
    <div
      className={cn(
        'flex items-center gap-1.5 text-xs',
        isDisabled && 'opacity-40'
      )}
    >
      <kbd
        className={cn(
          'inline-flex h-5 min-w-[20px] items-center justify-center rounded border px-1.5 font-mono text-[10px] font-medium',
          isDisabled
            ? 'border-white/5 bg-white/5 text-white/40'
            : 'border-white/20 bg-white/10 text-white/80'
        )}
      >
        {hotkey.key}
      </kbd>
      <span className={isDisabled ? 'text-white/30' : 'text-white/60'}>
        {hotkey.label}
      </span>
    </div>
  );
}

// 内联快捷键显示（用于对话框等）
export function InlineHotkey({ shortcut }: { shortcut: string }) {
  return (
    <kbd className="ml-1 inline-flex h-4 items-center rounded border border-white/10 bg-white/5 px-1 font-mono text-[10px] text-white/50">
      {shortcut}
    </kbd>
  );
}

// 快捷键帮助浮层
export function HotkeyHelp({ className }: { className?: string }) {
  const allHotkeys = [
    { key: 'Esc', label: '紧急停止所有任务', category: '控制' },
    { key: 'Space', label: '暂停/继续当前任务', category: '控制' },
    { key: 'Enter', label: '确认待处理操作', category: '确认' },
    { key: 'Tab', label: '切换活跃窗口', category: '导航' },
    { key: '⌘+K', label: '打开命令面板', category: '快捷' },
    { key: '⌘+N', label: '新建会话', category: '快捷' },
  ];

  return (
    <div
      className={cn(
        'rounded-lg border border-white/10 bg-zinc-900/95 p-4',
        className
      )}
    >
      <h3 className="mb-3 text-sm font-medium text-white">键盘快捷键</h3>
      <div className="space-y-3">
        {['控制', '确认', '导航', '快捷'].map((category) => {
          const items = allHotkeys.filter((h) => h.category === category);
          if (items.length === 0) return null;

          return (
            <div key={category}>
              <p className="mb-1.5 text-xs font-medium text-white/40">
                {category}
              </p>
              <div className="space-y-1">
                {items.map((hotkey) => (
                  <div
                    key={hotkey.key}
                    className="flex items-center justify-between text-xs"
                  >
                    <span className="text-white/60">{hotkey.label}</span>
                    <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-white/70">
                      {hotkey.key}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
