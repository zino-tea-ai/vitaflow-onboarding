import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { TitleBar, Sidebar, ChatArea, ChatKitArea, ExecutionStats, ExecutionPlan } from '@/components/nogicos';
import type { Session, Message, ToolExecution, ThinkingState, ExecutionStatsData, ExecutionPlanData, ConnectedApp } from '@/components/nogicos';
import { MinimalChatArea, SystemChatArea, CursorChatArea, PremiumChatArea } from '@/components/chat';
import type { ChatMessage } from '@/components/chat/MinimalChatArea';
import { Toaster } from '@/components/ui/sonner';
import { toast } from 'sonner';
import { useWebSocket } from '@/hooks/useWebSocket';
import type { ConnectionState } from '@/hooks/useWebSocket';
import { CommandPalette } from '@/components/command/CommandPalette';
import { useElectron } from '@/hooks/useElectron';
import { useSessionPersist } from '@/hooks/useSessionPersist';
import { useAgentWebSocket } from '@/hooks/useAgentWebSocket';

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
  
  // Session Persistence - use persistedSessions directly
  const {
    sessions: persistedSessions,
    loadSession,
    saveSession,
    deleteSession: deletePersistedSession,
    // refreshSessions, // Available but not currently used
  } = useSessionPersist({ autoLoad: true });
  
  // State - define these FIRST
  // Always have a session ID ready (create one if needed)
  const initialSessionId = useRef(`session-${Date.now()}`).current;
  const [activeSessionId, setActiveSessionId] = useState<string>(initialSessionId);
  
  // Track current unsaved session (for display in sidebar)
  const [currentUnsavedSession, setCurrentUnsavedSession] = useState<Session | null>(null);
  
  // Track all active sessions (for parallel streaming)
  // Each session in this set will have its own MinimalChatArea instance rendered
  const [activeSessions, setActiveSessions] = useState<Set<string>>(() => new Set([initialSessionId]));
  
  // Convert to UI format and include unsaved session (wrapped in useMemo to prevent dependency issues)
  const sessions: Session[] = useMemo(() => {
    const persistedUISession: Session[] = persistedSessions.map(s => ({
      id: s.id,
      title: s.title,
      preview: s.preview,
      timestamp: new Date(s.updated_at),
    }));
    
    // Merge: unsaved session first (if it's not already in persisted), then persisted sessions
    return currentUnsavedSession && !persistedUISession.find(s => s.id === currentUnsavedSession.id)
      ? [currentUnsavedSession, ...persistedUISession]
      : persistedUISession;
  }, [persistedSessions, currentUnsavedSession]);
  
  const [messages, setMessages] = useState<Message[]>([]);
  // Store all sessions' messages in a map
  const [chatSessions, setChatSessions] = useState<Record<string, ChatMessage[]>>({});
  const [tools, setTools] = useState<ToolExecution[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  
  // 连接的应用列表（从 ConnectorPanel 同步）
  const [connectedApps, setConnectedApps] = useState<ConnectedApp[]>([]);
  const [thinkingState, setThinkingState] = useState<ThinkingState>({
    isThinking: false,
    content: '',
  });
  
  // Ref to track if initial load has happened
  const initialLoadDone = useRef(false);
  
  // Refs for values needed in handleWsMessage (to avoid stale closures)
  const activeSessionIdRef = useRef<string>(activeSessionId);
  const sessionsRef = useRef(sessions);
  const messagesRef = useRef(messages);
  
  // Keep refs updated
  useEffect(() => { activeSessionIdRef.current = activeSessionId; }, [activeSessionId]);
  useEffect(() => { sessionsRef.current = sessions; }, [sessions]);
  useEffect(() => { messagesRef.current = messages; }, [messages]);

  // Auto-select most recent session on initial load (if there are saved sessions)
  useEffect(() => {
    if (sessions.length > 0 && !initialLoadDone.current) {
      initialLoadDone.current = true;
      const mostRecent = sessions[0];
      setActiveSessionId(mostRecent.id);
      // Load messages for the most recent session
      // [P1 FIX] Enhanced type safety for loaded data
      loadSession(mostRecent.id).then(detail => {
        if (detail?.history && Array.isArray(detail.history)) {
          const chatMessages: ChatMessage[] = detail.history
            .filter((m: unknown) => {
              if (!m || typeof m !== 'object') return false;
              const msg = m as Record<string, unknown>;
              return (
                typeof msg.role === 'string' &&
                (msg.role === 'user' || msg.role === 'assistant') &&
                typeof msg.content === 'string'
              );
            })
            .map((m: unknown, i: number) => {
              const msg = m as { role: string; content: string; parts?: Array<{ type: string; text?: string; [key: string]: unknown }> };
              return {
                id: `loaded-${mostRecent.id}-${i}`,
                role: msg.role as 'user' | 'assistant',
                content: msg.content,
                ...(Array.isArray(msg.parts) ? { parts: msg.parts } : {}),
                isHistory: true,
              };
            });
          setChatSessions(prev => ({ ...prev, [mostRecent.id]: chatMessages }));
        }
      }).catch(err => {
        console.error('[App] Failed to load session:', err);
      });
    }
  }, [sessions, loadSession]);

  // Execution Stats state (for YC Demo)
  const [showExecutionStats, setShowExecutionStats] = useState(false);
  const [executionStats, setExecutionStats] = useState<ExecutionStatsData | null>(null);
  const executionTracker = useRef({
    startTime: 0,
    toolsUsed: 0,
    iterations: 0,
    apps: new Set<string>(),
    usedCachedPlan: false,
    cacheSimilarity: 0,
    patternsLearned: 0,
  });

  // Execution Plan state (for YC Demo - streaming plan display)
  const [executionPlan, setExecutionPlan] = useState<ExecutionPlanData | null>(null);
  const [showExecutionPlan, setShowExecutionPlan] = useState(false);

  // Reset execution tracker when starting a new task
  const resetExecutionTracker = useCallback(() => {
    executionTracker.current = {
      startTime: Date.now(),
      toolsUsed: 0,
      iterations: 0,
      apps: new Set<string>(),
      usedCachedPlan: false,
      cacheSimilarity: 0,
      patternsLearned: 0,
    };
    setShowExecutionStats(false);
    setExecutionStats(null);
    // Also reset execution plan
    setExecutionPlan(null);
    setShowExecutionPlan(false);
  }, []);

  // Phase 7: Agent WebSocket Hook
  const {
    state: agentState,
    toastQueue,
    isConnected: agentConnected,
    startTask: agentStartTask,
    stopTask: agentStopTask,
    resumeTask: agentResumeTask,
    confirmAction: agentConfirmAction,
    clearError: agentClearError,
    dismissToast,
  } = useAgentWebSocket();
  
  // Phase 7: Toast dismiss handler
  const handleDismissToast = useCallback((id: string) => {
    dismissToast(id);
  }, [dismissToast]);
  
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
        // Track tools used for execution stats
        executionTracker.current.toolsUsed += 1;
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
        // Reset execution tracker for new task
        resetExecutionTracker();
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

      // step_start is now handled below with execution plan update

      case 'step_complete':
        if (msg.data) {
          const stepData = msg.data as { step: number; success?: boolean };
          // Update execution plan progress
          setExecutionPlan(prev => prev ? { ...prev, currentStep: stepData.step + 1 } : null);
          setVizState(prev => ({
            ...prev,
            step: prev.step ? { ...prev.step, status: stepData.success !== false ? 'completed' : 'error' } : null,
          }));
          addActionLog('step', `Step ${stepData.step + 1} ${stepData.success !== false ? 'completed' : 'failed'}`);
        }
        break;

      case 'task_complete':
        // CRITICAL: Unlock input IMMEDIATELY when task completes
        // Don't wait for HTTP stream to finish
        setIsExecuting(false);
        setVizState(prev => ({
          ...prev,
          glow: 'success',
          cursor: { ...prev.cursor, state: 'idle' },
        }));
        addActionLog('complete', '任务完成');
        // Show execution stats (YC Demo moment!)
        {
          const tracker = executionTracker.current;
          const totalTime = (Date.now() - tracker.startTime) / 1000;
          setExecutionStats({
            success: true,
            totalTime,
            iterations: tracker.iterations,
            toolsUsed: tracker.toolsUsed,
            apps: Array.from(tracker.apps),
            usedCachedPlan: tracker.usedCachedPlan,
            cacheSimilarity: tracker.cacheSimilarity,
            patternsLearned: tracker.patternsLearned,
            estimatedSpeedup: tracker.patternsLearned > 0 ? 6.0 : undefined,
          });
          setShowExecutionStats(true);
        }
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
        // Show error stats
        {
          const tracker = executionTracker.current;
          const totalTime = (Date.now() - tracker.startTime) / 1000;
          setExecutionStats({
            success: false,
            totalTime,
            iterations: tracker.iterations,
            toolsUsed: tracker.toolsUsed,
            apps: Array.from(tracker.apps),
          });
          setShowExecutionStats(true);
        }
        setTimeout(() => {
          setVizState(prev => ({ ...prev, glow: 'off' }));
        }, 2000);
        break;

      // YC Demo: Plan Cache hit - Pattern recognized!
      case 'plan_cache_hit':
        if (msg.data) {
          const cacheData = msg.data as { similarity?: number; original_time?: number; expected_speedup?: string };
          executionTracker.current.usedCachedPlan = true;
          executionTracker.current.cacheSimilarity = cacheData.similarity ?? 0;
          addActionLog('cache', `Pattern recognized! (${((cacheData.similarity ?? 0) * 100).toFixed(0)}% match)`);
          toast.success('Pattern recognized! Using optimized approach', { duration: 3000 });
          // Update execution plan with cache info
          setExecutionPlan(prev => prev ? {
            ...prev,
            usedCache: true,
            cacheSimilarity: cacheData.similarity ?? 0
          } : null);
        }
        break;

      // YC Demo: Plan generating (streaming start)
      case 'plan_generating':
        setShowExecutionPlan(true);
        setExecutionPlan({
          steps: [],
          currentStep: 0,
          isGenerating: true,
        });
        break;

      // YC Demo: Plan generated with steps
      case 'plan':
      case 'plan_generated':
        if (msg.data) {
          const planData = msg.data as { steps?: string[]; plan?: { steps?: string[] } };
          const steps = planData.steps || planData.plan?.steps || [];
          setExecutionPlan(prev => ({
            ...prev,
            steps,
            currentStep: 0,
            isGenerating: false,
            usedCache: prev?.usedCache ?? false,
            cacheSimilarity: prev?.cacheSimilarity,
          }));
          setShowExecutionPlan(true);
          addActionLog('step', `Plan generated: ${steps.length} steps`);
        }
        break;

      // YC Demo: Step progress update
      case 'step_start':
        if (msg.data) {
          const stepData = msg.data as { step: number };
          setExecutionPlan(prev => prev ? { ...prev, currentStep: stepData.step } : null);
          setVizState(prev => ({
            ...prev,
            step: prev.step ? { ...prev.step, current: stepData.step, status: 'active' } : null,
            glow: 'medium',
          }));
          addActionLog('step', `Step ${stepData.step + 1} started`);
        }
        break;

      // YC Demo: Model Cascade info
      case 'model_cascade':
        if (msg.data) {
          const cascadeData = msg.data as { iteration?: number; model_display?: string; is_fast_mode?: boolean };
          executionTracker.current.iterations = cascadeData.iteration ?? 0;
          if (cascadeData.is_fast_mode) {
            addActionLog('cascade', `Using ${cascadeData.model_display || 'Haiku'} (fast mode)`);
          }
        }
        break;


      // Track patterns learned (Plan Cache save)
      case 'plan_cached':
        executionTracker.current.patternsLearned += 1;
        addActionLog('learn', 'New pattern learned and cached');
        break;

      default:
        // Ignore unknown types (pong handled by hook)
        break;
    }
  }, [addActionLog, saveSession, resetExecutionTracker]);

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
    // Create unsaved session for display
    const newSession: Session = {
      id,
      title: 'New Session',
      preview: 'Start a new conversation',
      timestamp: new Date(),
    };
    setCurrentUnsavedSession(newSession);
    setActiveSessionId(id);
    setActiveSessions(prev => new Set([...prev, id])); // Add to active sessions for parallel rendering
    setMessages([]);
    setChatSessions(prev => ({ ...prev, [id]: [] }));  // Initialize empty for new session
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

  // Ref for chatSessions to avoid dependency issues
  const chatSessionsRef = useRef(chatSessions);
  useEffect(() => { chatSessionsRef.current = chatSessions; }, [chatSessions]);

  // Select session
  const handleSelectSession = useCallback(async (id: string) => {
    // Add to active sessions (for parallel rendering)
    setActiveSessions(prev => new Set([...prev, id]));
    
    // Check if we already have this session's messages in memory (and it's not empty)
    const cached = chatSessionsRef.current[id];
    if (cached && cached.length > 0) {
      setActiveSessionId(id);
      setMessages([]);
      setTools([]);
      return;
    }
    
    // Otherwise, load from backend
    const detail = await loadSession(id);
    
    // Prepare messages
    let chatMessages: ChatMessage[] = [];
    if (detail?.history && detail.history.length > 0) {
      chatMessages = detail.history.map((m: { role: string; content: string; parts?: Array<{ type: string; text?: string; [key: string]: unknown }> }, i: number) => ({
        id: `loaded-${id}-${i}`,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        ...(m.parts ? { parts: m.parts } : {}),
        isHistory: true,
      }));
    }
    
    // Update state
    setChatSessions(prev => ({ ...prev, [id]: chatMessages }));
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
    // Delete from backend (this updates persistedSessions automatically)
    await deletePersistedSession(id);
    
    // Clear local state if deleted current session - create new session
    if (activeSessionIdRef.current === id) {
      const newId = `session-${Date.now()}`;
      setActiveSessionId(newId);
      setMessages([]);
      setTools([]);
      setChatSessions(prev => ({ ...prev, [newId]: [] }));
    }
    toast.success('Session deleted');
  }, [deletePersistedSession]);

  // Handle session title/preview update from chat
  // NOTE: DO NOT create new session here - it will trigger key change and remount
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleSessionUpdate = useCallback((_title: string, _preview: string) => {
    // Session updates are handled by saveSession which updates persistedSessions
    // Session creation happens in handleMessagesChange
  }, []);

  // Handle messages change from chat - save to backend and update cache
  const handleMessagesChange = useCallback((msgs: ChatMessage[]) => {
    const sessionId = activeSessionIdRef.current;
    if (sessionId && msgs.length > 0) {
      // Update cache (use functional update to avoid needing chatSessions in deps)
      setChatSessions(prev => {
        // Only update if messages actually changed
        const current = prev[sessionId];
        if (current && current.length === msgs.length) {
          return prev; // No change needed
        }
        return { ...prev, [sessionId]: msgs };
      });
      
      // Get title from first user message
      const firstUserMsg = msgs.find(m => m.role === 'user');
      const title = firstUserMsg?.content?.slice(0, 30) || 'New Session';
      
      // Save to backend (this will add to persistedSessions)
      const toSave: Array<{ role: 'user' | 'assistant' | 'system'; content: string }> = msgs.map(m => ({
        role: m.role as 'user' | 'assistant' | 'system',
        content: m.content,
      }));
      saveSession(sessionId, toSave, title);
      
      // Don't clear unsaved session here - let the effect below handle it
      // to avoid the flash of disappearing sidebar item
    }
  }, [saveSession]);
  
  // Clear unsaved session only after it appears in persistedSessions
  useEffect(() => {
    if (currentUnsavedSession) {
      const isNowPersisted = persistedSessions.some(s => s.id === currentUnsavedSession.id);
      if (isNowPersisted) {
        setCurrentUnsavedSession(null);
      }
    }
  }, [persistedSessions, currentUnsavedSession]);

  // Send message
  const handleSendMessage = useCallback(async (content: string) => {
    // Reset thinking state for new task
    setThinkingState({ isThinking: false, content: '' });
    
    // Create session if none exists
    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      const id = `session-${Date.now()}`;
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

    // Save session to backend (this will update persistedSessions)
    const sessionTitle = content.slice(0, 30);
    const historyToSave = newMessages.map(m => ({
      role: m.role,
      content: m.content,
      timestamp: m.timestamp?.toISOString(),
    }));
    saveSession(currentSessionId, historyToSave, sessionTitle);

    // Execute task
    setIsExecuting(true);
    try {
      // Phase 8 修复: 优先使用 Agent WebSocket (支持状态追踪/敏感操作确认/热键)
      // 传递连接的窗口 hwnd 列表，如果没有连接则让后端自动检测
      if (agentConnected && agentStartTask) {
        const targetHwnds = connectedApps.map(app => app.hwnd).filter(hwnd => hwnd > 0);
        console.log('[App] Starting task with target hwnds:', targetHwnds);
        const taskId = await agentStartTask(content, targetHwnds);
        if (!taskId) {
          toast.error('Failed to start agent task');
        }
        // Agent events will be received via useAgentWebSocket hook
        // UI updates handled by agentState
        return;
      }
      
      // Fallback: 使用旧的 HTTP API (非 Electron 环境或 Agent 不可用时)
      const response = await fetch(`${API_URL}/v2/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: content,
          session_id: currentSessionId,
        }),
      });

      // [P1 FIX] Enhanced fetch error handling
      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        toast.error(`Server error: ${response.status} - ${errorText.slice(0, 100)}`);
        return;
      }

      const result = await response.json();

      // Note: Don't add assistant message here - WebSocket streams handle it
      // This API call just triggers the task; responses come via WebSocket
      if (!result.success) {
        toast.error(result.error || 'Task failed');
      }
    } catch (error) {
      // [P1 FIX] More specific error handling
      if (error instanceof TypeError && error.message.includes('fetch')) {
        toast.error('Network error: Failed to connect to NogicOS server');
      } else {
        toast.error('Failed to connect to NogicOS server');
      }
      console.error('Execute error:', error);
    } finally {
      setIsExecuting(false);
    }
  }, [activeSessionId, messages, saveSession, agentConnected, agentStartTask, connectedApps]);

  // Stop execution
  const handleStopExecution = useCallback(async () => {
    try {
      // Phase 8 修复: 优先使用 Agent WebSocket 停止任务
      if (agentConnected && agentStopTask) {
        agentStopTask();
        setIsExecuting(false);
        toast.info('Execution stopped');
        return;
      }
      
      // Fallback: HTTP API
      await fetch(`${API_URL}/stop`, { method: 'POST' });
      setIsExecuting(false);
      toast.info('Execution stopped');
    } catch (e) {
      console.error('Failed to stop:', e);
      setIsExecuting(false);
    }
  }, [agentConnected, agentStopTask]);

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
        // Render ALL active sessions simultaneously for parallel streaming
        <div className="flex-1 flex min-h-0">
          <Sidebar
            sessions={sessions}
            activeSessionId={activeSessionId || undefined}
            onNewSession={handleNewSession}
            onSelectSession={handleSelectSession}
            onDeleteSession={handleDeleteSession}
            onConnectedAppsChange={setConnectedApps}
          />
          {/* Render all active sessions - only the active one is visible */}
          {Array.from(activeSessions).map(sessionId => (
            <MinimalChatArea
              key={sessionId}
              apiUrl={VERCEL_AI_API_URL}
              sessionId={sessionId}
              initialMessages={chatSessions[sessionId] || []}
              onSessionUpdate={handleSessionUpdate}
              onMessagesChange={handleMessagesChange}
              style={{ display: sessionId === activeSessionId ? 'flex' : 'none' }}
            />
          ))}
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
          onConnectedAppsChange={setConnectedApps}
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
          // Phase 7: Agent 状态
          agentStatus={agentState.status}
          agentProgress={agentState.progress}
          agentError={agentState.error}
          pendingAction={agentState.pendingAction}
          onConfirmAction={agentConfirmAction}
          onRecoverFromError={(handler) => {
            if (handler === 'retry') agentResumeTask();
            else if (handler === 'clear') agentClearError();
          }}
          // Phase 7: Toast
          toastQueue={toastQueue}
          onDismissToast={handleDismissToast}
        />
          )}
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

      {/* Execution Plan Panel (YC Demo - streaming plan display) */}
      <div className="fixed top-20 right-6 z-40 w-[320px]">
        <ExecutionPlan
          data={executionPlan}
          visible={showExecutionPlan}
        />
      </div>

      {/* Execution Stats Panel (YC Demo) */}
      {executionStats && (
        <ExecutionStats
          data={executionStats}
          visible={showExecutionStats}
          onDismiss={() => setShowExecutionStats(false)}
        />
      )}

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
