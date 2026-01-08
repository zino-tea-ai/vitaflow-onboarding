/**
 * Agent WebSocket Hook
 * Phase 7: Agent 专用 WebSocket 通信
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type {
  AgentStatus,
  AgentProgress,
  AgentEvent,
  AgentError,
  AgentTask,
} from '@/types/agent';
import type { SensitiveAction } from '@/types/sensitive-action';

// Agent API 类型定义
interface AgentAPIType {
  onAgentEvent: (callback: (event: AgentEvent) => void) => () => void;
  onBatchEvents?: (callback: (events: AgentEvent[]) => void) => () => void;
  startTask: (task: string, targetHwnds: number[]) => Promise<{ taskId: string }>;
  stopTask: (taskId: string) => Promise<void>;
  resumeTask: (taskId: string) => Promise<void>;
  confirmSensitiveAction: (taskId: string, actionId: string, approved: boolean) => Promise<void>;
}

// Agent 状态
interface AgentState {
  status: AgentStatus;
  progress: AgentProgress | null;
  currentTask: AgentTask | null;
  pendingAction: SensitiveAction | null;
  error: AgentError | null;
}

// 初始状态
const initialState: AgentState = {
  status: 'idle',
  progress: null,
  currentTask: null,
  pendingAction: null,
  error: null,
};

// Toast 类型
type AgentToastItem = { id: string; message: string; timestamp: number };

// Hook 返回类型
interface UseAgentWebSocketReturn {
  state: AgentState;
  isConnected: boolean;
  toastQueue: AgentToastItem[];
  // 任务控制
  startTask: (task: string, targetHwnds: number[]) => Promise<string | null>;
  stopTask: () => void;
  resumeTask: () => void;
  // 敏感操作
  confirmAction: (actionId: string, approved: boolean) => void;
  // 状态
  clearError: () => void;
  clearToasts: () => void;
  dismissToast: (id: string) => void;
}

/**
 * Agent WebSocket Hook
 * 通过 Electron IPC 与 Agent 后端通信
 */
export function useAgentWebSocket(): UseAgentWebSocketReturn {
  const [state, setState] = useState<AgentState>(initialState);
  const [isConnected, setIsConnected] = useState(false);
  const currentTaskIdRef = useRef<string | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  // 获取 agentAPI
  const getAgentAPI = useCallback(() => {
    if (typeof window !== 'undefined' && (window as Window & { agentAPI?: AgentAPIType }).agentAPI) {
      return (window as Window & { agentAPI?: AgentAPIType }).agentAPI;
    }
    return null;
  }, []);

  // Toast 队列（用于显示无 hwnd 操作的提示）
  const [toastQueue, setToastQueue] = useState<AgentToastItem[]>([]);

  // 处理 Agent 事件
  const handleAgentEvent = useCallback((event: AgentEvent) => {
    switch (event.type) {
      case 'status':
        setState((prev) => ({
          ...prev,
          status: event.data as AgentStatus,
          error: null,
        }));
        break;

      case 'progress':
        setState((prev) => ({
          ...prev,
          progress: event.data as AgentProgress,
        }));
        break;

      case 'confirm':
        setState((prev) => ({
          ...prev,
          status: 'confirm',
          pendingAction: event.data as SensitiveAction,
        }));
        break;

      case 'error':
        setState((prev) => ({
          ...prev,
          status: 'failed',
          error: event.data as AgentError,
        }));
        break;

      case 'complete':
        setState((prev) => ({
          ...prev,
          status: 'completed',
          pendingAction: null,
        }));
        currentTaskIdRef.current = null;
        break;

      case 'tool':
        // 工具执行事件，可用于显示当前操作
        setState((prev) => ({
          ...prev,
          status: 'executing',
        }));
        break;

      case 'toast': {
        // 无 hwnd 操作的 toast 提示
        const toastData = event.data as { message: string; tool_name: string; timestamp: number };
        if (toastData?.message) {
          const toastId = `${toastData.timestamp}-${Math.random().toString(36).slice(2)}`;
          setToastQueue((prev) => [...prev, { id: toastId, message: toastData.message, timestamp: toastData.timestamp }]);
          // 3秒后自动移除
          setTimeout(() => {
            setToastQueue((prev) => prev.filter((t) => t.id !== toastId));
          }, 3000);
        }
        break;
      }
    }
  }, []);

  // 订阅 Agent 事件（单个和批量）
  useEffect(() => {
    const api = getAgentAPI();
    if (!api) {
      console.warn('[useAgentWebSocket] agentAPI not available');
      return;
    }

    // 订阅单个事件
    const unsubscribeSingle = api.onAgentEvent(handleAgentEvent);
    
    // 订阅批量事件（高频事件优化，带容错）
    let unsubscribeBatch: (() => void) | null = null;
    if (api.onBatchEvents) {
      unsubscribeBatch = api.onBatchEvents((events: AgentEvent[]) => {
        // 逐条处理批量事件，单条失败不影响其他
        events.forEach((event, index) => {
          try {
            handleAgentEvent(event);
          } catch (error) {
            console.error(`[useAgentWebSocket] Batch event #${index} processing failed:`, error);
          }
        });
      });
    }
    
    unsubscribeRef.current = () => {
      unsubscribeSingle();
      unsubscribeBatch?.();
    };
    setIsConnected(true);

    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
      setIsConnected(false);
    };
  }, [getAgentAPI, handleAgentEvent]);

  // 启动任务
  const startTask = useCallback(
    async (task: string, targetHwnds: number[]): Promise<string | null> => {
      const api = getAgentAPI();
      if (!api) {
        console.error('[useAgentWebSocket] agentAPI not available');
        return null;
      }

      try {
        setState((prev) => ({
          ...prev,
          status: 'queued',
          error: null,
        }));

        const result = await api.startTask(task, targetHwnds);
        currentTaskIdRef.current = result.taskId;

        setState((prev) => ({
          ...prev,
          status: 'thinking',
          currentTask: {
            id: result.taskId,
            task_text: task,
            status: 'thinking',
            progress: {
              iteration: 0,
              maxIterations: 10,
              toolCalls: 0,
              currentWindow: '',
            },
            targetHwnds,
            createdAt: Date.now(),
            updatedAt: Date.now(),
          },
        }));

        return result.taskId;
      } catch (error) {
        console.error('[useAgentWebSocket] startTask error:', error);
        setState((prev) => ({
          ...prev,
          status: 'failed',
          error: {
            type: 'unknown',
            message: error instanceof Error ? error.message : 'Failed to start task',
            recoverable: true,
          },
        }));
        return null;
      }
    },
    [getAgentAPI]
  );

  // 停止任务
  const stopTask = useCallback(() => {
    const api = getAgentAPI();
    const taskId = currentTaskIdRef.current;
    if (!api || !taskId) return;

    api.stopTask(taskId).then(() => {
      setState((prev) => ({
        ...prev,
        status: 'idle',
        pendingAction: null,
      }));
      currentTaskIdRef.current = null;
    });
  }, [getAgentAPI]);

  // 恢复任务
  const resumeTask = useCallback(() => {
    const api = getAgentAPI();
    const taskId = currentTaskIdRef.current;
    if (!api || !taskId) return;

    api.resumeTask(taskId).then(() => {
      setState((prev) => ({
        ...prev,
        status: 'recovering',
        error: null,
      }));
    });
  }, [getAgentAPI]);

  // 确认敏感操作
  const confirmAction = useCallback(
    (actionId: string, approved: boolean) => {
      const api = getAgentAPI();
      const taskId = currentTaskIdRef.current;
      if (!api || !taskId) return;

      api.confirmSensitiveAction(taskId, actionId, approved).then(() => {
        setState((prev) => ({
          ...prev,
          status: approved ? 'executing' : 'paused',
          pendingAction: null,
        }));
      });
    },
    [getAgentAPI]
  );

  // 清除错误
  const clearError = useCallback(() => {
    setState((prev) => ({
      ...prev,
      error: null,
    }));
  }, []);

  // 清除所有 toast
  const clearToasts = useCallback(() => {
    setToastQueue([]);
  }, []);

  // 移除单条 toast
  const dismissToast = useCallback((id: string) => {
    setToastQueue((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return {
    state,
    isConnected,
    toastQueue,
    startTask,
    stopTask,
    resumeTask,
    confirmAction,
    clearError,
    clearToasts,
    dismissToast,
  };
}
