/**
 * Agent 快捷键 Hook
 * Phase 7.9: 快捷键支持
 */

import { useEffect, useCallback, useRef } from 'react';
import type { AgentController } from '@/types/agent';

interface UseAgentHotkeysOptions {
  enabled?: boolean;
  onEmergencyStop?: () => void;
  onTogglePause?: () => void;
  onConfirmAction?: () => void;
  onCycleWindow?: () => void;
}

/**
 * Agent 快捷键 Hook
 * 提供全局快捷键支持
 */
export function useAgentHotkeys(
  controller: AgentController | null,
  options: UseAgentHotkeysOptions = {}
) {
  const {
    enabled = true,
    onEmergencyStop,
    onTogglePause,
    onConfirmAction,
    onCycleWindow,
  } = options;

  // 使用 ref 存储最新的 callback，避免 effect 依赖更新
  const callbacksRef = useRef({
    onEmergencyStop,
    onTogglePause,
    onConfirmAction,
    onCycleWindow,
  });

  useEffect(() => {
    callbacksRef.current = {
      onEmergencyStop,
      onTogglePause,
      onConfirmAction,
      onCycleWindow,
    };
  });

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // 忽略输入框内的按键
      const target = e.target as HTMLElement;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target.isContentEditable
      ) {
        return;
      }

      const callbacks = callbacksRef.current;

      switch (e.key) {
        case 'Escape':
          e.preventDefault();
          if (callbacks.onEmergencyStop) {
            callbacks.onEmergencyStop();
          } else if (controller) {
            controller.emergencyStop();
          }
          break;

        case ' ': // Space
          e.preventDefault();
          if (callbacks.onTogglePause) {
            callbacks.onTogglePause();
          } else if (controller) {
            controller.togglePause();
          }
          break;

        case 'Enter':
          e.preventDefault();
          if (callbacks.onConfirmAction) {
            callbacks.onConfirmAction();
          } else if (controller) {
            controller.confirmPendingAction();
          }
          break;

        case 'Tab':
          e.preventDefault();
          if (callbacks.onCycleWindow) {
            callbacks.onCycleWindow();
          } else if (controller) {
            controller.cycleActiveWindow();
          }
          break;
      }
    },
    [controller]
  );

  useEffect(() => {
    if (!enabled) return;

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [enabled, handleKeyDown]);
}

/**
 * 简化版本的快捷键 Hook
 * 用于单个快捷键绑定
 */
export function useHotkey(
  key: string,
  callback: () => void,
  options: {
    enabled?: boolean;
    ignoreInputs?: boolean;
  } = {}
) {
  const { enabled = true, ignoreInputs = true } = options;
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  });

  useEffect(() => {
    if (!enabled) return;

    const handler = (e: KeyboardEvent) => {
      if (ignoreInputs) {
        const target = e.target as HTMLElement;
        if (
          target instanceof HTMLInputElement ||
          target instanceof HTMLTextAreaElement ||
          target.isContentEditable
        ) {
          return;
        }
      }

      if (e.key === key) {
        e.preventDefault();
        callbackRef.current();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [enabled, ignoreInputs, key]);
}
