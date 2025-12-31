/**
 * useSessionPersist Hook
 * 
 * 封装后端 Session 持久化 API
 * 对接 /v2/sessions 端点
 */

import { useState, useCallback, useEffect } from 'react';

const API_URL = 'http://localhost:8080';

// Types
export interface SessionSummary {
  id: string;
  title: string;
  preview: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail {
  id: string;
  title: string;
  history: Message[];
  preferences: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  tool_calls?: unknown[];
  timestamp?: string;
}

interface UseSessionPersistOptions {
  autoLoad?: boolean;
  onError?: (error: Error) => void;
}

export function useSessionPersist(options: UseSessionPersistOptions = {}) {
  const { autoLoad = true, onError } = options;
  
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // 处理错误
  const handleError = useCallback((e: unknown) => {
    const err = e instanceof Error ? e : new Error(String(e));
    setError(err);
    onError?.(err);
    console.error('[SessionPersist] Error:', err);
  }, [onError]);

  // 加载 Session 列表
  const loadSessions = useCallback(async (limit = 20, offset = 0) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `${API_URL}/v2/sessions?limit=${limit}&offset=${offset}`
      );
      
      if (!response.ok) {
        throw new Error(`Failed to load sessions: ${response.status}`);
      }
      
      const data = await response.json();
      
      // 转换为前端格式
      const formattedSessions: SessionSummary[] = (data.sessions || []).map((s: any) => ({
        id: s.id,
        title: s.title || 'Untitled',
        preview: s.preview || '',
        message_count: s.message_count || 0,
        created_at: s.created_at,
        updated_at: s.updated_at,
      }));
      
      setSessions(formattedSessions);
      return formattedSessions;
    } catch (e) {
      handleError(e);
      return [];
    } finally {
      setIsLoading(false);
    }
  }, [handleError]);

  // 加载单个 Session 详情（包含历史消息）
  const loadSession = useCallback(async (sessionId: string): Promise<SessionDetail | null> => {
    try {
      const response = await fetch(`${API_URL}/v2/sessions/${sessionId}`);
      
      if (!response.ok) {
        if (response.status === 404) {
          return null; // Session 不存在
        }
        throw new Error(`Failed to load session: ${response.status}`);
      }
      
      const data = await response.json();
      return {
        id: data.id,
        title: data.title || 'Untitled',
        history: data.history || [],
        preferences: data.preferences || {},
        created_at: data.created_at,
        updated_at: data.updated_at,
      };
    } catch (e) {
      handleError(e);
      return null;
    }
  }, [handleError]);

  // 保存 Session
  const saveSession = useCallback(async (
    sessionId: string,
    history: Message[],
    title?: string,
    preferences?: Record<string, unknown>
  ) => {
    try {
      const response = await fetch(`${API_URL}/v2/sessions/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          history,
          title,
          preferences,
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to save session: ${response.status}`);
      }
      
      const result = await response.json();
      
      // 更新本地 sessions 列表
      setSessions(prev => {
        const exists = prev.find(s => s.id === sessionId);
        if (exists) {
          return prev.map(s => s.id === sessionId ? {
            ...s,
            title: title || s.title,
            message_count: history.length,
            updated_at: new Date().toISOString(),
          } : s);
        }
        // 新 Session，添加到列表开头
        return [{
          id: sessionId,
          title: title || 'New Session',
          preview: history[0]?.content?.slice(0, 50) || '',
          message_count: history.length,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }, ...prev];
      });
      
      return result;
    } catch (e) {
      handleError(e);
      return null;
    }
  }, [handleError]);

  // 删除 Session
  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      const response = await fetch(`${API_URL}/v2/sessions/${sessionId}`, {
        method: 'DELETE',
      });
      
      if (!response.ok) {
        throw new Error(`Failed to delete session: ${response.status}`);
      }
      
      // 从本地列表移除
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      return true;
    } catch (e) {
      handleError(e);
      return false;
    }
  }, [handleError]);

  // 自动加载
  useEffect(() => {
    if (autoLoad) {
      loadSessions();
    }
  }, [autoLoad, loadSessions]);

  return {
    // State
    sessions,
    isLoading,
    error,
    
    // Actions
    loadSessions,
    loadSession,
    saveSession,
    deleteSession,
    
    // Helpers
    refreshSessions: () => loadSessions(),
  };
}

export default useSessionPersist;

