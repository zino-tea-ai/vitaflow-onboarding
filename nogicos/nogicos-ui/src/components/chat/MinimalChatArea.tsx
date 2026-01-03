/**
 * NogicOS Minimal Chat Area
 * 
 * Architecture:
 * - App.tsx controls the source of truth for messages (stored per session)
 * - MinimalChatArea is a controlled component that displays messages and handles input
 * - useChat handles the streaming communication, but we sync its state with parent
 */

import { useState, useRef, useEffect, useCallback, useMemo, memo } from 'react';
import type { KeyboardEvent } from 'react';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { motion, AnimatePresence } from 'motion/react';
import { ArrowUp, ChevronRight, Square, Terminal, CheckCircle2, Loader2, AlertCircle, Bot, Search, ListTodo } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';
import './styles/minimal-theme.css';

// === MODE TYPES ===
type AgentMode = 'agent' | 'ask' | 'plan';

const MODE_CONFIG = {
  agent: { label: 'Agent', icon: Bot, color: '#10b981', desc: '自主执行' },
  ask: { label: 'Ask', icon: Search, color: '#3b82f6', desc: '只读查询' },
  plan: { label: 'Plan', icon: ListTodo, color: '#f59e0b', desc: '生成计划' },
} as const;

// === SPRING CONFIGURATIONS ===
const springs = {
  gentle: { type: 'spring' as const, stiffness: 120, damping: 14 },
  snappy: { type: 'spring' as const, stiffness: 400, damping: 30 },
  smooth: { type: 'spring' as const, stiffness: 200, damping: 20 },
  micro: { type: 'spring' as const, stiffness: 500, damping: 35 },
} as const;

// Message type
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  parts?: any[];
  isHistory?: boolean;  // True for loaded messages (skip animations)
}

interface MinimalChatAreaProps {
  apiUrl?: string;
  sessionId: string;
  className?: string;
  style?: React.CSSProperties;
  // History loaded from backend
  initialMessages?: ChatMessage[];
  // Called when messages change (for saving)
  onMessagesChange?: (messages: ChatMessage[]) => void;
  // Called when session title/preview should update
  onSessionUpdate?: (title: string, preview: string) => void;
}

export function MinimalChatArea({
  apiUrl = 'http://localhost:8080/api/chat',
  sessionId,
  className,
  style,
  initialMessages = [],
  onMessagesChange,
  onSessionUpdate,
}: MinimalChatAreaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const [localInput, setLocalInput] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
  const [justSentMessage, setJustSentMessage] = useState(false);
  const lastUserMessageRef = useRef<HTMLDivElement>(null);
  
  // === MODE STATE ===
  const [currentMode, setCurrentMode] = useState<AgentMode>('agent');
  const [modeMenuOpen, setModeMenuOpen] = useState(false);
  const modeMenuRef = useRef<HTMLDivElement>(null);
  
  // Close mode menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modeMenuRef.current && !modeMenuRef.current.contains(e.target as Node)) {
        setModeMenuOpen(false);
      }
    };
    if (modeMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [modeMenuOpen]);
  
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === '.') {
        e.preventDefault();
        setModeMenuOpen(o => !o);
      }
      if ((e.metaKey || e.ctrlKey) && ['1', '2', '3'].includes(e.key)) {
        e.preventDefault();
        const modes: AgentMode[] = ['agent', 'ask', 'plan'];
        setCurrentMode(modes[parseInt(e.key) - 1]);
        setModeMenuOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  // useChat - using session ID as key
  const {
    messages: chatMessages,
    sendMessage,
    stop,
    status,
    setMessages,
  } = useChat({
    id: `chat-${sessionId}`,  // Unique per session
    transport: new DefaultChatTransport({
      api: apiUrl,
      body: { session_id: sessionId },
    }),
    onError: (err) => {
      console.error('[MinimalChatArea] Error:', err);
    },
  });
  
  // Derive loading state
  const isLoading = status === 'submitted' || status === 'streaming';
  const isActuallyStreaming = status === 'streaming';

  // Refs for tracking
  const prevMessageCountRef = useRef(0);
  
  // Track session changes and load messages
  const prevSessionIdRef = useRef(sessionId);
  useEffect(() => {
    // When session changes, load the new session's messages
    if (prevSessionIdRef.current !== sessionId) {
      prevSessionIdRef.current = sessionId;
      prevMessageCountRef.current = 0;  // Reset save counter
      
      // Load initial messages for new session
      if (initialMessages.length > 0) {
        const formatted = initialMessages.map(m => ({
          id: m.id,
          role: m.role,
          content: m.content,
          parts: m.parts,
        }));
        setMessages(formatted as any);
      } else {
        setMessages([]);
      }
    }
  }, [sessionId, initialMessages, setMessages]);
  
  // Also load on initial mount if we have messages
  const hasLoadedInitial = useRef(false);
  useEffect(() => {
    if (!hasLoadedInitial.current && initialMessages.length > 0) {
      hasLoadedInitial.current = true;
      const formatted = initialMessages.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        parts: m.parts,
      }));
      setMessages(formatted as any);
    }
  }, [initialMessages, setMessages]);

  // Combine messages: prefer chatMessages if they exist, otherwise use initialMessages
  const messages = useMemo(() => {
    // If we have chat messages from useChat, use them
    if (chatMessages.length > 0) {
      return chatMessages.map(m => ({
        ...m,
        isHistory: m.id.startsWith('loaded-'),
      }));
    }
    // Otherwise use initial messages
    return initialMessages.map(m => ({
      ...m,
      isHistory: true,
    }));
  }, [chatMessages, initialMessages]);

  // Save messages when they change (debounced) - use ref to avoid dependency issues
  const saveTimeoutRef = useRef<NodeJS.Timeout>();
  const onMessagesChangeRef = useRef(onMessagesChange);
  const chatMessagesRef = useRef(chatMessages);
  useEffect(() => { onMessagesChangeRef.current = onMessagesChange; }, [onMessagesChange]);
  useEffect(() => { chatMessagesRef.current = chatMessages; }, [chatMessages]);
  
  // Helper to prepare messages for saving
  const prepareMessagesForSave = useCallback((msgs: typeof chatMessages) => {
    return msgs.map(m => {
      // Extract content from parts if needed
      let content = m.content || '';
      if (!content && m.parts) {
        content = m.parts
          .filter((p: any) => p.type === 'text')
          .map((p: any) => p.text || '')
          .join('');
      }
      return {
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content,
        parts: m.parts,
      };
    });
  }, []);

  // Save immediately before session switch
  useEffect(() => {
    const prevId = prevSessionIdRef.current;
    if (prevId && prevId !== sessionId && chatMessagesRef.current.length > 0) {
      // Session is changing - save current messages immediately
      if (onMessagesChangeRef.current) {
        const toSave = prepareMessagesForSave(chatMessagesRef.current);
        if (toSave.length > 0) {
          onMessagesChangeRef.current(toSave);
        }
      }
    }
    prevSessionIdRef.current = sessionId;
  }, [sessionId, prepareMessagesForSave]);
  
  useEffect(() => {
    // Save when message count changes - don't wait for status to be 'ready'
    // This ensures sidebar updates immediately when user sends a message
    if (chatMessages.length > 0 && chatMessages.length !== prevMessageCountRef.current) {
      prevMessageCountRef.current = chatMessages.length;
      
      // Clear previous timeout
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
      // Debounce save
      saveTimeoutRef.current = setTimeout(() => {
        if (onMessagesChangeRef.current) {
          const toSave = prepareMessagesForSave(chatMessages)
            // Filter out empty assistant messages (streaming not complete) for regular saves
            .filter(m => m.role === 'user' || (m.content && m.content.trim().length > 0));
          
          // Only save if we have valid messages
          if (toSave.length > 0) {
            onMessagesChangeRef.current(toSave);
          }
        }
      }, 500);
    }
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [chatMessages, status, prepareMessagesForSave]);

  // Update session title when first message is sent
  useEffect(() => {
    if (onSessionUpdate && chatMessages.length > 0) {
      const firstUserMsg = chatMessages.find(m => m.role === 'user');
      if (firstUserMsg) {
        const title = (firstUserMsg.content || '').slice(0, 30) || 'New Session';
        const preview = (firstUserMsg.content || '').slice(0, 100) || '';
        onSessionUpdate(title, preview);
      }
    }
  }, [chatMessages, onSessionUpdate]);

  // Scroll handling
  const handleScroll = useCallback(() => {
    const container = chatContainerRef.current;
    if (!container) return;
    
    const { scrollTop, scrollHeight, clientHeight } = container;
    const distFromBottom = scrollHeight - scrollTop - clientHeight;
    
    setUserScrolledUp(prev => {
      if (prev) return distFromBottom < 20 ? false : true;
      return distFromBottom > 100;
    });
  }, []);

  // Reset scroll lock when streaming ends
  useEffect(() => {
    if (!isActuallyStreaming) {
      setUserScrolledUp(false);
    }
  }, [isActuallyStreaming]);

  // Auto scroll - only for new messages, not when loading history
  useEffect(() => {
    if (userScrolledUp) return;
    
    // Don't auto-scroll if all messages are history (loaded from backend)
    const hasNewMessages = messages.some(m => !m.isHistory && !m.id.startsWith('loaded-'));
    if (!hasNewMessages && messages.length > 0) return;
    
    if (justSentMessage) {
      setTimeout(() => {
        lastUserMessageRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        setJustSentMessage(false);
      }, 100);
    } else if (hasNewMessages) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, userScrolledUp, justSentMessage]);

  // Streaming scroll
  useEffect(() => {
    if (isActuallyStreaming && !userScrolledUp) {
      const scrollInterval = setInterval(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 300);
      return () => clearInterval(scrollInterval);
    }
  }, [isActuallyStreaming, userScrolledUp]);

  // Auto resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [localInput]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setLocalInput(e.target.value);
  }, []);

  const onSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (localInput.trim() && !isLoading) {
      const messageText = localInput.trim();
      
      setUserScrolledUp(false);
      setJustSentMessage(true);
      setLocalInput('');
      
      try {
        await sendMessage({ text: messageText });
      } catch (err) {
        console.error('[MinimalChatArea] Error:', err);
      }
    }
  }, [localInput, isLoading, sendMessage]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit(e as unknown as React.FormEvent);
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div className={cn('minimal-main', className)} style={style}>
      <div className="minimal-grain-overlay" aria-hidden="true" />
      
      <div 
        className="minimal-chat"
        ref={chatContainerRef}
        onScroll={handleScroll}
      >
        <div className="minimal-chat-inner">
          <AnimatePresence mode="wait">
            {isEmpty ? (
              <WelcomeScreen key="welcome" onExample={setLocalInput} />
            ) : (
              <motion.div
                key="messages"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2 }}
              >
                <AnimatePresence initial={false}>
                  {messages.map((message, index) => {
                    const isLastUserMessage = message.role === 'user' && 
                      messages.slice(index + 1).every(m => m.role !== 'user');
                    
                    // Skip animation for historical messages
                    const skipAnimation = message.isHistory || message.id.startsWith('loaded-');
                    
                    return (
                      <motion.div
                        key={message.id}
                        ref={isLastUserMessage ? lastUserMessageRef : undefined}
                        initial={skipAnimation ? false : { opacity: 0, y: 15, filter: 'blur(4px)' }}
                        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                        transition={skipAnimation ? { duration: 0 } : { duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
                        style={{ willChange: skipAnimation ? undefined : 'transform, opacity, filter' }}
                      >
                        <MinimalMessage
                          role={message.role}
                          content={message.content}
                          parts={message.parts}
                          isStreaming={isActuallyStreaming && index === messages.length - 1 && message.role === 'assistant'}
                          skipAnimation={skipAnimation}
                        />
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
                <div ref={messagesEndRef} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <motion.div 
        className="minimal-input-area"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...springs.smooth, delay: 0.1 }}
      >
        <div className="minimal-input-container">
          <form onSubmit={onSubmit}>
            <motion.div 
              className="minimal-input-box"
              animate={{
                boxShadow: isFocused 
                  ? '0 0 0 1px rgba(255,255,255,0.15), 0 4px 20px rgba(0,0,0,0.3)' 
                  : '0 0 0 1px rgba(255,255,255,0.06), 0 2px 8px rgba(0,0,0,0.2)',
              }}
              transition={{ duration: 0.2 }}
              style={{ willChange: 'box-shadow' }}
            >
              {/* Mode Selector */}
              <div className="minimal-mode-selector" ref={modeMenuRef}>
                <motion.button
                  type="button"
                  className="minimal-mode-btn"
                  onClick={() => setModeMenuOpen(o => !o)}
                  whileHover={{ backgroundColor: 'rgba(255,255,255,0.08)' }}
                  whileTap={{ scale: 0.98 }}
                  style={{ color: MODE_CONFIG[currentMode].color }}
                >
                  {(() => {
                    const Icon = MODE_CONFIG[currentMode].icon;
                    return <Icon className="w-4 h-4" />;
                  })()}
                  <span className="minimal-mode-label">{MODE_CONFIG[currentMode].label}</span>
                  <ChevronRight className={cn("w-3 h-3 transition-transform", modeMenuOpen && "rotate-90")} />
                </motion.button>
                
                <AnimatePresence>
                  {modeMenuOpen && (
                    <motion.div
                      className="minimal-mode-menu"
                      initial={{ opacity: 0, y: 8, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 8, scale: 0.95 }}
                      transition={{ duration: 0.15 }}
                    >
                      {(Object.keys(MODE_CONFIG) as AgentMode[]).map((mode, i) => {
                        const config = MODE_CONFIG[mode];
                        const Icon = config.icon;
                        return (
                          <motion.button
                            key={mode}
                            type="button"
                            className={cn("minimal-mode-option", currentMode === mode && "active")}
                            onClick={() => { setCurrentMode(mode); setModeMenuOpen(false); }}
                            whileHover={{ backgroundColor: 'rgba(255,255,255,0.08)' }}
                          >
                            <Icon className="w-4 h-4" style={{ color: config.color }} />
                            <div className="minimal-mode-option-text">
                              <span className="minimal-mode-option-label">{config.label}</span>
                              <span className="minimal-mode-option-desc">{config.desc}</span>
                            </div>
                            <kbd className="minimal-mode-kbd">⌘{i + 1}</kbd>
                          </motion.button>
                        );
                      })}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
              
              <textarea
                ref={textareaRef}
                value={localInput}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                onFocus={() => setIsFocused(true)}
                onBlur={() => setIsFocused(false)}
                placeholder="Message NogicOS..."
                rows={1}
                disabled={isLoading}
                className="minimal-textarea"
              />
              <AnimatePresence mode="wait">
                {isLoading ? (
                  <StopButton key="stop" onClick={stop} />
                ) : (
                  <SendButton key="send" disabled={!localInput.trim()} />
                )}
              </AnimatePresence>
            </motion.div>
          </form>
          <motion.div 
            className="minimal-input-meta"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2, duration: 0.3 }}
          >
            <span className="minimal-input-hint">
              <kbd>Enter</kbd> to send · <kbd>⌘.</kbd> switch mode
            </span>
            <span className="minimal-model-badge" style={{ color: MODE_CONFIG[currentMode].color }}>
              <motion.span 
                className="minimal-status-dot"
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                style={{ backgroundColor: MODE_CONFIG[currentMode].color }}
              />
              {MODE_CONFIG[currentMode].label}
            </span>
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}

// === ANIMATED COMPONENTS ===

function LoadingDots() {
  return (
    <div className="minimal-loading">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="minimal-loading-dot"
          animate={{ y: [0, -6, 0], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15, ease: 'easeInOut' }}
          style={{ willChange: 'transform, opacity' }}
        />
      ))}
    </div>
  );
}

function SendButton({ disabled }: { disabled: boolean }) {
  return (
    <motion.button
      type="submit"
      disabled={disabled}
      className="minimal-send-btn"
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0.8, opacity: 0 }}
      whileHover={{ scale: disabled ? 1 : 1.05 }}
      whileTap={{ scale: disabled ? 1 : 0.92 }}
      transition={springs.micro}
      style={{ willChange: 'transform' }}
    >
      <motion.div animate={{ y: disabled ? 0 : [0, -1, 0] }} transition={{ duration: 0.3 }}>
        <ArrowUp className="w-4 h-4" />
      </motion.div>
    </motion.button>
  );
}

function StopButton({ onClick }: { onClick: () => void }) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      className="minimal-send-btn minimal-send-btn--stop"
      initial={{ scale: 0.8, opacity: 0, rotate: -90 }}
      animate={{ scale: 1, opacity: 1, rotate: 0 }}
      exit={{ scale: 0.8, opacity: 0, rotate: 90 }}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.92 }}
      transition={springs.micro}
      style={{ background: 'var(--m-gray-700)', willChange: 'transform' }}
    >
      <motion.div animate={{ scale: [1, 1.1, 1] }} transition={{ duration: 1.5, repeat: Infinity }}>
        <Square className="w-3 h-3" fill="currentColor" />
      </motion.div>
    </motion.button>
  );
}

function WelcomeScreen({ onExample }: { onExample: (text: string) => void }) {
  const examples = [
    { text: 'Organize desktop', full: 'Organize my desktop files' },
    { text: 'Find recent files', full: 'Search recently modified files' },
    { text: 'Open Hacker News', full: 'Open Hacker News' },
    { text: 'Run git status', full: 'Run git status' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.4 }}
      className="minimal-welcome-v2"
    >
      <div className="minimal-hero">
        <motion.h1 
          className="minimal-hero-title"
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          NogicOS
        </motion.h1>
        <motion.p 
          className="minimal-hero-subtitle"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          AI that lives in your computer
        </motion.p>
      </div>

      <motion.div 
        className="minimal-quick-actions"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.35 }}
      >
        <span className="minimal-quick-label">Try</span>
        <div className="minimal-pills">
          {examples.map((example, i) => (
            <motion.button
              key={example.text}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3, delay: 0.4 + i * 0.05 }}
              whileHover={{ scale: 1.02, backgroundColor: 'rgba(255,255,255,0.08)' }}
              whileTap={{ scale: 0.98 }}
              onClick={() => onExample(example.full)}
              className="minimal-pill"
            >
              {example.text}
            </motion.button>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}

// === MESSAGE COMPONENTS ===

interface MinimalMessageProps {
  role: 'user' | 'assistant';
  content?: string;
  parts?: any[];
  isStreaming?: boolean;
  skipAnimation?: boolean;
}

function StreamingText({ text, isStreaming, onComplete }: { text: string; isStreaming: boolean; onComplete?: () => void }) {
  const containerRef = useRef<HTMLSpanElement>(null);
  const displayedRef = useRef(0);
  const textRef = useRef(text);
  const timeoutRef = useRef<NodeJS.Timeout>();
  const completedRef = useRef(false);
  const isStreamingRef = useRef(isStreaming);
  const onCompleteRef = useRef(onComplete);

  textRef.current = text;
  isStreamingRef.current = isStreaming;
  onCompleteRef.current = onComplete;

  const updateDisplay = (length: number) => {
    if (!containerRef.current) return;
    containerRef.current.textContent = textRef.current.slice(0, length);
  };

  useEffect(() => {
    const tick = () => {
      const target = textRef.current;
      const current = displayedRef.current;
      
      if (current >= target.length) {
        if (!isStreamingRef.current && !completedRef.current) {
          completedRef.current = true;
          onCompleteRef.current?.();
        } else {
          timeoutRef.current = setTimeout(tick, 50);
        }
        return;
      }

      displayedRef.current = current + 1;
      updateDisplay(current + 1);

      const char = target[current];
      const isCJK = /[\u4e00-\u9fff\u3400-\u4dbf\uac00-\ud7af\u3040-\u309f\u30a0-\u30ff]/.test(char);
      let delay = isCJK ? 35 : 12;

      timeoutRef.current = setTimeout(tick, delay);
    };

    tick();

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return <span ref={containerRef} className="whitespace-pre-wrap" />;
}

interface ToolWidgetProps {
  tool: {
    type: string;
    toolCallId: string;
    toolName?: string;
    state: string;
    input?: Record<string, any>;
    output?: any;
    errorText?: string;
  };
}

const ToolWidget = memo(function ToolWidget({ tool }: ToolWidgetProps) {
  const [expanded, setExpanded] = useState(false);
  
  const toolName = tool.toolName || tool.type?.replace(/^tool-/, '') || 'unknown';
  const isComplete = tool.state === 'output-available';
  const isError = tool.state === 'error' || !!tool.errorText;
  const isRunning = tool.state === 'input-streaming' || tool.state === 'input-available';
  
  const displayName = toolName.replace(/_/g, ' ');
  const mainArg = tool.input ? Object.values(tool.input)[0] : '';
  const argPreview = typeof mainArg === 'string' ? mainArg.length > 50 ? mainArg.slice(-50) : mainArg : '';

  return (
    <motion.div 
      className="tool-chip"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="tool-chip-main" onClick={() => tool.output && setExpanded(e => !e)}>
        <span className="tool-chip-icon">
          {isComplete ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
           : isError ? <AlertCircle className="w-3.5 h-3.5 text-red-400" />
           : isRunning ? <Loader2 className="w-3.5 h-3.5 text-neutral-500 animate-spin" />
           : <Terminal className="w-3.5 h-3.5 text-neutral-600" />}
        </span>
        <span className="tool-chip-name">{displayName}</span>
        {argPreview && <span className="tool-chip-arg">{argPreview}</span>}
        {tool.output && (
          <span className={`tool-chip-chevron ${expanded ? 'open' : ''}`}>
            <ChevronRight className="w-3 h-3" />
          </span>
        )}
      </div>
      
      <AnimatePresence>
        {expanded && tool.output && (
          <motion.div 
            className="tool-chip-output"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
          >
            <pre>{typeof tool.output === 'string' ? tool.output : JSON.stringify(tool.output, null, 2)}</pre>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
});

const MinimalMessage = memo(function MinimalMessage({ role, content, parts, isStreaming, skipAnimation }: MinimalMessageProps) {
  const [thinkingOpen, setThinkingOpen] = useState(true);
  const [thinkingComplete, setThinkingComplete] = useState(skipAnimation ? true : false);
  const [thinkingAnimationDone, setThinkingAnimationDone] = useState(skipAnimation ? true : false);
  const [roleVisible, setRoleVisible] = useState(skipAnimation ? true : false);
  const thinkingStartTime = useRef<number | null>(null);
  const isUser = role === 'user';

  const textContent = useMemo(() => 
    parts?.filter((p: any) => p.type === 'text').map((p: any) => p.text).join('') || content || '',
    [parts, content]
  );

  const reasoningText = useMemo(() => 
    parts?.filter((p: any) => p.type === 'reasoning').map((p: any) => p.text).join('') || '',
    [parts]
  );

  const toolInvocations = useMemo(() => 
    parts?.filter((p: any) => p.type?.startsWith('tool-') || p.type === 'dynamic-tool') || [],
    [parts]
  );

  const hasReasoning = reasoningText.length > 0;
  const hasTools = toolInvocations.length > 0;
  const showPlanning = isStreaming && !hasReasoning && !textContent;
  
  useEffect(() => {
    if (isUser || skipAnimation) {
      setRoleVisible(true);
    } else if (!showPlanning && !roleVisible) {
      const timer = setTimeout(() => setRoleVisible(true), 450);
      return () => clearTimeout(timer);
    }
  }, [isUser, showPlanning, roleVisible, skipAnimation]);
  
  useEffect(() => {
    if (hasReasoning && thinkingStartTime.current === null) {
      thinkingStartTime.current = Date.now();
    }
  }, [hasReasoning]);
  
  const showText = !hasReasoning || thinkingComplete;
  const showRole = isUser ? true : roleVisible;

  return (
    <div className="minimal-message">
      <motion.div 
        className="minimal-message-role"
        initial={skipAnimation ? false : { opacity: isUser ? 0 : 0, x: -8 }}
        animate={{ opacity: showRole ? 1 : 0, x: showRole ? 0 : -8 }}
        transition={skipAnimation ? { duration: 0 } : { duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      >
        {isUser ? 'You' : 'NogicOS'}
      </motion.div>
      
      <div className={`minimal-message-content ${isStreaming ? 'streaming' : ''}`}>
        <AnimatePresence mode="wait">
          {showPlanning ? (
            <motion.div
              key="planning"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35, delay: 0.7, ease: [0.4, 0, 0.2, 1] }}
              className="minimal-planning"
            >
              <LoadingDots />
              <span className="minimal-planning-text">Planning next moves</span>
            </motion.div>
          ) : hasReasoning ? (
            <motion.div
              key="thinking"
              className={cn("minimal-thinking", isStreaming && !textContent && "thinking-active")}
              initial={skipAnimation ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={skipAnimation ? { duration: 0 } : { duration: 0.35, delay: 0.35, ease: [0.4, 0, 0.2, 1] }}
            >
              <div className="minimal-thinking-header" onClick={() => setThinkingOpen(o => !o)}>
                <span className={`minimal-thinking-chevron ${thinkingOpen ? 'open' : ''}`}>
                  <ChevronRight className="w-3 h-3" />
                </span>
                <span className="minimal-thinking-status">
                  {isStreaming && !textContent ? 'Planning next moves' : 'Thought process'}
                </span>
              </div>
              <AnimatePresence>
                {thinkingOpen && (
                  <motion.div 
                    className="minimal-thinking-content"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
                  >
                    {thinkingAnimationDone || skipAnimation ? (
                      <span className="whitespace-pre-wrap">{reasoningText}</span>
                    ) : (
                      <StreamingText 
                        text={reasoningText} 
                        isStreaming={isStreaming && !textContent}
                        onComplete={() => {
                          setThinkingAnimationDone(true);
                          const startTime = thinkingStartTime.current || Date.now();
                          const elapsed = Date.now() - startTime;
                          const minDisplayTime = 1500;
                          const remainingTime = Math.max(0, minDisplayTime - elapsed);
                          setTimeout(() => setThinkingComplete(true), remainingTime + 300);
                        }}
                      />
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ) : null}
        </AnimatePresence>

        <AnimatePresence>
          {hasTools && (
            <motion.div
              className="minimal-tools"
              initial={skipAnimation ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={skipAnimation ? { duration: 0 } : { duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
            >
              {toolInvocations.map((tool: any, index: number) => (
                <ToolWidget key={tool.toolCallId || index} tool={tool} />
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {textContent && showText && (
            <motion.div 
              className="minimal-prose"
              initial={skipAnimation ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={skipAnimation ? { duration: 0 } : { duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
            >
              <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ children }) => <h1 className="text-xl font-semibold text-white mt-4 mb-2">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-lg font-semibold text-white mt-3 mb-2">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-base font-medium text-white mt-2 mb-1">{children}</h3>,
                  p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc list-inside mb-3 space-y-1">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal list-inside mb-3 space-y-1">{children}</ol>,
                  li: ({ children }) => <li className="text-neutral-300">{children}</li>,
                  strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                  em: ({ children }) => <em className="italic text-neutral-200">{children}</em>,
                  code: ({ className, children }) => {
                    const isBlock = className?.includes('language-');
                    return isBlock ? (
                      <pre className="bg-neutral-900 rounded-lg p-4 my-3 overflow-x-auto">
                        <code className="text-sm font-mono text-neutral-200">{children}</code>
                      </pre>
                    ) : (
                      <code className="bg-neutral-800 px-1.5 py-0.5 rounded text-sm font-mono text-neutral-200">{children}</code>
                    );
                  },
                  pre: ({ children }) => <>{children}</>,
                  a: ({ href, children }) => (
                    <a href={href} className="text-white underline underline-offset-2 hover:text-neutral-300" target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-neutral-700 pl-4 my-3 text-neutral-400 italic">{children}</blockquote>
                  ),
                  hr: () => <hr className="border-neutral-800 my-4" />,
                  table: ({ children }) => (
                    <div className="my-3 overflow-x-auto">
                      <table className="w-full text-sm border-collapse">{children}</table>
                    </div>
                  ),
                  thead: ({ children }) => <thead className="border-b border-neutral-700">{children}</thead>,
                  tbody: ({ children }) => <tbody>{children}</tbody>,
                  tr: ({ children }) => <tr className="border-b border-neutral-800 last:border-0">{children}</tr>,
                  th: ({ children }) => <th className="text-left py-2 px-3 font-medium text-neutral-300">{children}</th>,
                  td: ({ children }) => <td className="py-2 px-3 text-neutral-400">{children}</td>,
                }}
              >
                {textContent}
              </ReactMarkdown>
              {isStreaming && <span className="minimal-cursor" />}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
});
