import { useState, useCallback, useEffect, useRef } from 'react';
import { TitleBar, Sidebar, ChatArea, ChatKitArea, VisualizationPanel, defaultVisualizationState } from '@/components/nogicos';
import type { Session, Message, ToolExecution, ThinkingState, VisualizationState, ActionLogEntry, GlowState } from '@/components/nogicos';
import { MinimalChatArea, SystemChatArea, CursorChatArea, PremiumChatArea } from '@/components/chat';
import { Toaster } from '@/components/ui/sonner';
import { toast } from 'sonner';
import { useWebSocket } from '@/hooks/useWebSocket';
import type { ConnectionState } from '@/hooks/useWebSocket';
import { CommandPalette } from '@/components/command/CommandPalette';
import { useElectron } from '@/hooks/useElectron';
import { useSessionPersist } from '@/hooks/useSessionPersist';

// Config
const WS_URL = 'ws://localhost:8765';
const API_URL = 'http://localhost:8080';
const CHATKIT_API_URL = 'http://localhost:8080/chatkit';
const VERCEL_AI_API_URL = 'http://localhost:8080/api/chat';

// Chat 模式选择
// - minimal: 极致克制，纯黑白灰 (Recommended)
// - system: 系统级 AI 工具界面
// - premium: Linear/Raycast 风格聊天界面
// - cursor: Cursor IDE 风格聊天界面
// - chatkit: OpenAI ChatKit UI
// - legacy: 原始自定义聊天界面
type ChatMode = 'minimal' | 'system' | 'premium' | 'cursor' | 'chatkit' | 'legacy';
const CHAT_MODE: ChatMode = 'minimal';

function App() {
  // Electron API
  const { isElectron, onNewSession } = useElectron();
  
  // Session Persistence
  const {
    sessions: persistedSessions,
    loadSession,
    saveSession,
    deleteSession: deletePersistedSession,
  } = useSessionPersist({ autoLoad: true });
  
  // State
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [minimalInitialMessages, setMinimalInitialMessages] = useState<Array<{ id: string; role: 'user' | 'assistant'; content: string; parts?: any[] }>>([]);
  const [tools, setTools] = useState<ToolExecution[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [thinkingState, setThinkingState] = useState<ThinkingState>({
    isThinking: false,
    content: '',
  });
  
  // Ref to track if initial load has happened
  const initialLoadDone = useRef(false);
  
  // Refs for values needed in handleWsMessage (to avoid stale closures)
  const activeSessionIdRef = useRef(activeSessionId);
  const sessionsRef = useRef(sessions);
  const messagesRef = useRef(messages);
  
  // Keep refs updated
  useEffect(() => { activeSessionIdRef.current = activeSessionId; }, [activeSessionId]);
  useEffect(() => { sessionsRef.current = sessions; }, [sessions]);
  useEffect(() => { messagesRef.current = messages; }, [messages]);

  // Sync persisted sessions to local state on initial load
  useEffect(() => {
    if (persistedSessions.length > 0 && !initialLoadDone.current) {
      initialLoadDone.current = true;
      // Convert persisted sessions to UI format
      const uiSessions: Session[] = persistedSessions.map(s => ({
        id: s.id,
        title: s.title,
        preview: s.preview,
        timestamp: new Date(s.updated_at),
      }));
      setSessions(uiSessions);
      
      // Auto-select the most recent session
      if (uiSessions.length > 0 && !activeSessionId) {
        const mostRecent = uiSessions[0];
        setActiveSessionId(mostRecent.id);
        // Load messages for the most recent session
        loadSession(mostRecent.id).then(detail => {
          if (detail?.history) {
            const loadedMessages: Message[] = detail.history.map((m, i) => ({
              id: `loaded-${mostRecent.id}-${i}`,
              role: m.role as 'user' | 'assistant',
              content: m.content,
              timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
            }));
            setMessages(loadedMessages);
            
            // Also set for MinimalChatArea (include parts for reasoning)
            const minimalMessages = detail.history.map((m: any, i) => ({
              id: `loaded-${mostRecent.id}-${i}`,
              role: m.role as 'user' | 'assistant',
              content: m.content,
              ...(m.parts ? { parts: m.parts } : {}),
            }));
            setMinimalInitialMessages(minimalMessages);
          }
        });
      }
    }
  }, [persistedSessions, activeSessionId, loadSession]);

  // Visualization state
  const [vizState, setVizState] = useState<VisualizationState>(defaultVisualizationState);
  const [showVisualization] = useState(true);
  
  // Helper to add action log entry
  const addActionLog = useCallback((type: ActionLogEntry['type'], description: string) => {
    const entry: ActionLogEntry = {
      id: `log-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      type,
      description,
    };
    setVizState(prev => ({
      ...prev,
      actionLog: [...prev.actionLog.slice(-50), entry], // Keep last 50 entries
    }));
  }, []);

  // Handle WebSocket messages
  const handleWsMessage = useCallback((data: unknown) => {
    const msg = data as {
      type: string;
      data?: { agent?: { state: string } };
      message_id?: string;
      content?: string;
      thinking?: string;
      duration_ms?: number;
      tool_id?: string;
      tool_name?: string;
      result?: string;
      error?: string;
    };
    
    switch (msg.type) {
      case 'status':
        if (msg.data?.agent) {
          const agentState = msg.data.agent.state;
          if (agentState === 'thinking' || agentState === 'acting') {
            setIsExecuting(true);
          } else if (agentState === 'done' || agentState === 'idle' || agentState === 'error') {
            setIsExecuting(false);
          }
        }
        break;

      // === Thinking Events (Extended Thinking) ===
      case 'thinking_start':
        setThinkingState({
          isThinking: true,
          content: '',
        });
        break;

      case 'thinking_delta':
        if (msg.thinking) {
          setThinkingState((prev) => ({
            ...prev,
            content: prev.content + msg.thinking,
          }));
        }
        break;

      case 'thinking_end':
        setThinkingState((prev) => ({
          ...prev,
          isThinking: false,
          durationMs: msg.duration_ms,
        }));
        break;

      // === Content Events ===
      case 'content':
        if (msg.message_id && msg.content) {
          const messageId = msg.message_id;
          const content = msg.content;
          setMessages((prev) => {
            const existing = prev.find((m) => m.id === messageId);
            if (existing) {
              return prev.map((m) =>
                m.id === messageId
                  ? { ...m, content: m.content + content, isStreaming: true }
                  : m
              );
            }
            return [
              ...prev,
              {
                id: messageId,
                role: 'assistant' as const,
                content: content,
                timestamp: new Date(),
                isStreaming: true,
              },
            ];
          });
        }
        break;

      case 'content_end':
        if (msg.message_id) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === msg.message_id ? { ...m, isStreaming: false } : m
            )
          );
        }
        break;

      // === Tool Events ===
      case 'tool_start':
        if (msg.tool_id && msg.tool_name) {
          setTools((prev) => [
            ...prev,
            {
              id: msg.tool_id!,
              messageId: msg.message_id || '',
              name: msg.tool_name!,
              args: {},
              status: 'executing' as const,
              startTime: new Date(),
            },
          ]);
        }
        break;

      case 'tool_result':
        if (msg.tool_id) {
          setTools((prev) =>
            prev.map((t) =>
              t.id === msg.tool_id
                ? {
                    ...t,
                    status: msg.error ? 'error' : 'success',
                    output: msg.result,
                    error: msg.error,
                    endTime: new Date(),
                  }
                : t
            )
          );
        }
        break;

      // === Execution Events ===
      case 'execution_complete':
        setIsExecuting(false);
        // Clear thinking state
        setThinkingState({ isThinking: false, content: '' });
        // Mark all streaming messages as complete and save session
        setMessages((prev) => {
          const updated = prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m));
          // Save complete session after execution (use refs for latest values)
          const currentSessionId = activeSessionIdRef.current;
          if (currentSessionId) {
            const historyToSave = updated.map(m => ({
              role: m.role,
              content: m.content,
              timestamp: m.timestamp?.toISOString(),
            }));
            const session = sessionsRef.current.find(s => s.id === currentSessionId);
            saveSession(currentSessionId, historyToSave, session?.title);
          }
          return updated;
        });
        break;

      case 'action':
        // Action update - could add visual feedback
        break;

      // === Visualization Events ===
      case 'cursor_move':
        if (msg.data) {
          const moveData = msg.data as { x: number; y: number; duration?: number };
          setVizState(prev => ({
            ...prev,
            cursor: {
              ...prev.cursor,
              position: { x: moveData.x, y: moveData.y },
              state: 'moving',
              visible: true,
            },
            glow: 'medium' as GlowState,
          }));
          addActionLog('cursor_move', `移动到 (${moveData.x}, ${moveData.y})`);
          // Reset cursor state after movement
          setTimeout(() => {
            setVizState(prev => ({
              ...prev,
              cursor: { ...prev.cursor, state: 'idle' },
            }));
          }, (moveData.duration || 0.8) * 1000);
        }
        break;

      case 'cursor_click':
        setVizState(prev => ({
          ...prev,
          cursor: { ...prev.cursor, state: 'clicking' },
        }));
        addActionLog('click', '点击元素');
        setTimeout(() => {
          setVizState(prev => ({
            ...prev,
            cursor: { ...prev.cursor, state: 'idle' },
          }));
        }, 300);
        break;

      case 'cursor_type':
        setVizState(prev => ({
          ...prev,
          cursor: { ...prev.cursor, state: 'typing' },
        }));
        addActionLog('type', '开始输入');
        break;

      case 'cursor_stop_type':
        setVizState(prev => ({
          ...prev,
          cursor: { ...prev.cursor, state: 'idle' },
        }));
        addActionLog('type', '输入完成');
        break;

      case 'highlight':
        if (msg.data) {
          const highlightData = msg.data as { rect: { x: number; y: number; width: number; height: number }; label?: string };
          setVizState(prev => ({
            ...prev,
            highlight: {
              ...highlightData.rect,
              label: highlightData.label,
            },
          }));
          addActionLog('highlight', highlightData.label || '高亮元素');
        }
        break;

      case 'highlight_hide':
        setVizState(prev => ({
          ...prev,
          highlight: null,
        }));
        break;

      case 'screen_glow':
        if (msg.data) {
          const glowData = msg.data as { intensity?: GlowState };
          setVizState(prev => ({
            ...prev,
            glow: glowData.intensity || 'medium',
          }));
        }
        break;

      case 'screen_glow_stop':
        setVizState(prev => ({
          ...prev,
          glow: 'off',
        }));
        break;

      case 'task_start':
        if (msg.data) {
          const taskData = msg.data as { max_steps?: number; url?: string };
          setVizState(prev => ({
            ...prev,
            cursor: { ...prev.cursor, visible: true, state: 'idle' },
            glow: 'low',
            step: taskData.max_steps ? { current: 0, total: taskData.max_steps, status: 'active' } : null,
            url: taskData.url || prev.url,
          }));
          addActionLog('step', '任务开始');
        }
        break;

      case 'step_start':
        if (msg.data) {
          const stepData = msg.data as { step: number };
          setVizState(prev => ({
            ...prev,
            step: prev.step ? { ...prev.step, current: stepData.step, status: 'active' } : null,
            glow: 'medium',
          }));
          addActionLog('step', `步骤 ${stepData.step + 1} 开始`);
        }
        break;

      case 'step_complete':
        if (msg.data) {
          const stepData = msg.data as { step: number; success?: boolean };
          setVizState(prev => ({
            ...prev,
            step: prev.step ? { ...prev.step, status: stepData.success !== false ? 'completed' : 'error' } : null,
          }));
          addActionLog('step', `步骤 ${stepData.step + 1} ${stepData.success !== false ? '完成' : '失败'}`);
        }
        break;

      case 'task_complete':
        setVizState(prev => ({
          ...prev,
          glow: 'success',
          cursor: { ...prev.cursor, state: 'idle' },
        }));
        addActionLog('complete', '任务完成');
        // Reset glow after 2 seconds
        setTimeout(() => {
          setVizState(prev => ({ ...prev, glow: 'off' }));
        }, 2000);
        break;

      case 'task_error':
        setVizState(prev => ({
          ...prev,
          glow: 'error',
          step: prev.step ? { ...prev.step, status: 'error' } : null,
        }));
        addActionLog('error', '任务出错');
        setTimeout(() => {
          setVizState(prev => ({ ...prev, glow: 'off' }));
        }, 2000);
        break;

      default:
        // Ignore unknown types (pong handled by hook)
        break;
    }
  }, [addActionLog, saveSession]);

  // Track if we've shown the connected toast
  const [hasShownConnectedToast, setHasShownConnectedToast] = useState(false);

  // WebSocket connection with heartbeat
  const { state: wsState, reconnect } = useWebSocket({
    url: WS_URL,
    onMessage: handleWsMessage,
    onConnect: () => {
      // Only show toast once per session
      if (!hasShownConnectedToast) {
        toast.success('Connected to NogicOS', { duration: 2000 });
        setHasShownConnectedToast(true);
      }
    },
    onDisconnect: () => {
      // DON'T reset toast flag - we only want to show it once per app session
      // setHasShownConnectedToast(false);
    },
    heartbeatInterval: 30000, // 30 seconds
    reconnectDelay: 2000,
    maxReconnectDelay: 10000,
  });

  // Connection state helpers
  const wsConnected = wsState === 'connected';
  const isReconnecting = wsState === 'reconnecting';

  // Get title based on connection state
  const getTitle = (state: ConnectionState): string => {
    switch (state) {
      case 'connected':
        return 'NogicOS';
      case 'connecting':
        return 'NogicOS (Connecting...)';
      case 'reconnecting':
        return 'NogicOS (Reconnecting...)';
      case 'disconnected':
        return 'NogicOS (Disconnected)';
    }
  };

  // Create new session
  const handleNewSession = useCallback(() => {
    const id = `session-${Date.now()}`;
    const newSession: Session = {
      id,
      title: 'New Session',
      preview: 'Start a new conversation',
      timestamp: new Date(),
    };
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(id);
    setMessages([]);
    setMinimalInitialMessages([]);  // Clear for new session
    setTools([]);
  }, []);

  // Listen for Electron new session event
  useEffect(() => {
    if (isElectron) {
      const cleanup = onNewSession(() => {
        handleNewSession();
        toast.success('New session created');
      });
      return cleanup;
    }
  }, [isElectron, onNewSession, handleNewSession]);

  // Select session
  const handleSelectSession = useCallback(async (id: string) => {
    const detail = await loadSession(id);
    
    // Prepare messages for MinimalChatArea (include parts for reasoning/tools)
    let minimalMessages: Array<{ id: string; role: 'user' | 'assistant'; content: string; parts?: any[] }> = [];
    if (detail?.history && detail.history.length > 0) {
      minimalMessages = detail.history.map((m: any, i) => ({
        id: `loaded-${id}-${i}`,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        // Preserve parts if they exist (contains reasoning/tools)
        ...(m.parts ? { parts: m.parts } : {}),
      }));
    }
    
    // Update state
    setMinimalInitialMessages(minimalMessages);
    setActiveSessionId(id);
    setMessages([]);
    setTools([]);
    
    // Also update legacy messages state
    if (detail?.history) {
      const loadedMessages: Message[] = detail.history.map((m, i) => ({
        id: `loaded-${id}-${i}`,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
      }));
      setMessages(loadedMessages);
    }
  }, [loadSession]);

  // Delete session
  const handleDeleteSession = useCallback(async (id: string) => {
    // Delete from backend
    await deletePersistedSession(id);
    
    // Delete from local state
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setMessages([]);
      setTools([]);
    }
    toast.success('Session deleted');
  }, [activeSessionId, deletePersistedSession]);

  // Send message
  const handleSendMessage = useCallback(async (content: string) => {
    // Reset thinking state for new task
    setThinkingState({ isThinking: false, content: '' });
    
    // Create session if none exists
    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      const id = `session-${Date.now()}`;
      const newSession: Session = {
        id,
        title: content.slice(0, 30),
        preview: content,
        timestamp: new Date(),
      };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(id);
      currentSessionId = id;
    }

    // Add user message
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
    };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);

    // Update session preview
    const sessionTitle = content.slice(0, 30);
    setSessions((prev) =>
      prev.map((s) =>
        s.id === currentSessionId
          ? { ...s, title: sessionTitle, preview: content, timestamp: new Date() }
          : s
      )
    );

    // Save session to backend (user message)
    const historyToSave = newMessages.map(m => ({
      role: m.role,
      content: m.content,
      timestamp: m.timestamp?.toISOString(),
    }));
    saveSession(currentSessionId, historyToSave, sessionTitle);

    // Execute task
    setIsExecuting(true);
    try {
      const response = await fetch(`${API_URL}/v2/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: content,
          session_id: currentSessionId,
        }),
      });

      const result = await response.json();

      // Note: Don't add assistant message here - WebSocket streams handle it
      // This API call just triggers the task; responses come via WebSocket
      if (!result.success) {
        toast.error(result.error || 'Task failed');
      }
    } catch (error) {
      toast.error('Failed to connect to NogicOS server');
      console.error('Execute error:', error);
    } finally {
      setIsExecuting(false);
    }
  }, [activeSessionId, messages, saveSession]);

  // Stop execution
  const handleStopExecution = useCallback(async () => {
    try {
      await fetch(`${API_URL}/stop`, { method: 'POST' });
      setIsExecuting(false);
      toast.info('Execution stopped');
    } catch (e) {
      console.error('Failed to stop:', e);
      setIsExecuting(false);
    }
  }, []);

  return (
    <div className="h-screen w-screen flex flex-col bg-background overflow-hidden">
      {/* Title Bar */}
      <TitleBar 
        title={getTitle(wsState)} 
        onReconnect={!wsConnected ? reconnect : undefined}
      />

      {/* Reconnecting Banner */}
      {isReconnecting && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-1.5 text-center">
          <span className="text-xs text-amber-400">
            Connection lost. Reconnecting...
          </span>
        </div>
      )}

      {/* Main Content */}
      {CHAT_MODE === 'minimal' ? (
        // Minimal 模式：极致克制（带侧边栏）
        <div className="flex-1 flex min-h-0">
          <Sidebar
            sessions={sessions}
            activeSessionId={activeSessionId || undefined}
            onNewSession={handleNewSession}
            onSelectSession={handleSelectSession}
            onDeleteSession={handleDeleteSession}
          />
          <MinimalChatArea
            apiUrl={VERCEL_AI_API_URL}
            sessionId={activeSessionId || 'default'}
            initialMessages={minimalInitialMessages}
            onSessionUpdate={(title, preview) => {
              // Create session if none exists
              let sessionId = activeSessionId;
              if (!sessionId) {
                sessionId = `session-${Date.now()}`;
                const newSession: Session = {
                  id: sessionId,
                  title,
                  preview,
                  timestamp: new Date(),
                };
                setSessions((prev) => [newSession, ...prev]);
                setActiveSessionId(sessionId);
              } else {
                // Update existing session
                setSessions((prev) =>
                  prev.map((s) =>
                    s.id === sessionId
                      ? { ...s, title, preview, timestamp: new Date() }
                      : s
                  )
                );
              }
            }}
            onMessagesChange={(msgs) => {
              // Save messages to backend
              const sessionId = activeSessionId;
              if (sessionId) {
                const session = sessions.find(s => s.id === sessionId);
                saveSession(sessionId, msgs as any, session?.title);
              }
            }}
          />
        </div>
      ) : CHAT_MODE === 'system' ? (
        // System 模式：全屏布局（自带侧边栏）
        <div className="flex-1 min-h-0">
          <SystemChatArea
            apiUrl={VERCEL_AI_API_URL}
            sessionId={activeSessionId || 'default'}
          />
        </div>
      ) : (
        // 其他模式：三栏布局
      <div className="flex-1 flex min-h-0">
        {/* Sidebar */}
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId || undefined}
          onNewSession={handleNewSession}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
        />

        {/* Chat Area */}
          {CHAT_MODE === 'premium' ? (
            <PremiumChatArea
              apiUrl={VERCEL_AI_API_URL}
              sessionId={activeSessionId || 'default'}
            />
          ) : CHAT_MODE === 'cursor' ? (
            <CursorChatArea
              apiUrl={VERCEL_AI_API_URL}
              sessionId={activeSessionId || 'default'}
            />
          ) : CHAT_MODE === 'chatkit' ? (
            <ChatKitArea
              apiUrl={CHATKIT_API_URL}
              onShowVisualization={() => {
                setVizState(prev => ({ ...prev, glow: 'medium' }));
              }}
              onHighlight={(params) => {
                setVizState(prev => ({
                  ...prev,
                  highlight: {
                    x: params.x,
                    y: params.y,
                    width: params.width,
                    height: params.height,
                    label: params.label,
                  },
                }));
              }}
              onCursorMove={(params) => {
                setVizState(prev => ({
                  ...prev,
                  cursor: {
                    ...prev.cursor,
                    position: { x: params.x, y: params.y },
                    state: 'moving',
                    visible: true,
                  },
                }));
                setTimeout(() => {
                  setVizState(prev => ({
                    ...prev,
                    cursor: { ...prev.cursor, state: 'idle' },
                  }));
                }, 800);
              }}
            />
          ) : (
        <ChatArea
          messages={messages}
          tools={tools}
          isExecuting={isExecuting}
          thinkingState={thinkingState}
          onSendMessage={handleSendMessage}
          onStopExecution={handleStopExecution}
        />
          )}

        {/* Visualization Panel */}
        <VisualizationPanel
          state={vizState}
          visible={showVisualization}
          collapsible={true}
          initialCollapsed={false}
          title="AI 可视化"
        />
      </div>
      )}

      {/* Command Palette (Ctrl+K) */}
      <CommandPalette
        onNewSession={handleNewSession}
        onClearHistory={() => {
          setMessages([]);
          setTools([]);
          toast.success('Chat history cleared');
        }}
      />

      {/* Toast Notifications */}
      <Toaster 
        position="bottom-right"
        toastOptions={{
          className: 'glass-panel',
        }}
      />
    </div>
  );
}

export default App;
