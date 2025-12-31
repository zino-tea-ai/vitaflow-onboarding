/**
 * NogicOS System Chat Area
 * 极致专业的系统级 AI 工具界面
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import type { KeyboardEvent } from 'react';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Plus, Send, Paperclip, Image, Mic, Terminal, 
  ChevronDown, ChevronRight, Bot, User, 
  Cpu, Activity, Wifi, Clock,
  FileText, Folder, MoreHorizontal
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { StreamingText } from './StreamingText';
import './styles/system-theme.css';

interface SystemChatAreaProps {
  apiUrl?: string;
  sessionId?: string;
  className?: string;
}

// 模拟文件预览数据
const mockFiles = [
  { id: 1, type: 'image', preview: '/api/placeholder/60/60' },
  { id: 2, type: 'folder', name: 'Documents' },
  { id: 3, type: 'image', preview: '/api/placeholder/60/60' },
  { id: 4, type: 'file', name: 'report.pdf' },
  { id: 5, type: 'image', preview: '/api/placeholder/60/60' },
  { id: 6, type: 'folder', name: 'Downloads' },
  { id: 7, type: 'image', preview: '/api/placeholder/60/60' },
  { id: 8, type: 'file', name: 'data.csv' },
];

// 模拟会话数据
const mockSessions = [
  { id: '1', title: '你好', time: '刚刚', active: true },
  { id: '2', title: 'New Chat', time: '5分钟前' },
  { id: '3', title: '你好', time: '1小时前' },
  { id: '4', title: '帮我整理一下桌面', time: '2小时前' },
];

export function SystemChatArea({
  apiUrl = 'http://localhost:8080/api/chat',
  sessionId = 'default',
  className,
}: SystemChatAreaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [localInput, setLocalInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [agentMode, setAgentMode] = useState(true);
  const [systemStats, setSystemStats] = useState({
    fps: 'N/A',
    gpu: '23%',
    cpu: '14%',
    latency: 'N/A'
  });

  const {
    messages,
    sendMessage,
    stop,
  } = useChat({
    transport: new DefaultChatTransport({
      api: apiUrl,
      body: { session_id: sessionId },
    }),
    onError: (err) => {
      console.error('[SystemChatArea] Error:', err);
      setIsLoading(false);
    },
  });

  // Auto scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [localInput]);

  // Track loading state
  useEffect(() => {
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      setIsLoading(lastMessage.role === 'user' || (lastMessage as any).isStreaming);
    } else {
      setIsLoading(false);
    }
  }, [messages]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setLocalInput(e.target.value);
  }, []);

  const onSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (localInput.trim() && !isLoading) {
      setIsLoading(true);
      try {
        await sendMessage({ text: localInput.trim() });
        setLocalInput('');
      } catch (err) {
        console.error('[SystemChatArea] Error:', err);
      }
    }
  }, [localInput, isLoading, sendMessage]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit(e as unknown as React.FormEvent);
    }
  };

  return (
    <div className={cn('sys-layout', className)}>
      {/* Sidebar */}
      <aside className="sys-sidebar">
        {/* File Preview Grid */}
        <div className="sys-file-preview">
          {mockFiles.map((file) => (
            <motion.div
              key={file.id}
              className="sys-file-thumb"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.98 }}
            >
              {file.type === 'image' ? (
                <div className="w-full h-full bg-gradient-to-br from-zinc-700 to-zinc-800" />
              ) : file.type === 'folder' ? (
                <div className="w-full h-full flex items-center justify-center bg-amber-500/10">
                  <Folder className="w-5 h-5 text-amber-500" />
                </div>
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <FileText className="w-5 h-5 text-zinc-500" />
                </div>
              )}
            </motion.div>
          ))}
        </div>

        {/* Session List */}
        <div className="sys-session-list">
          {mockSessions.map((session) => (
            <motion.div
              key={session.id}
              className={cn('sys-session-item', session.active && 'active')}
              whileHover={{ x: 2 }}
            >
              <Terminal className="w-4 h-4 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="truncate text-sm">{session.title}</div>
                <div className="text-[10px] text-zinc-500">{session.time}</div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* New Chat Button */}
        <motion.button
          className="sys-new-chat-btn"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <Plus className="w-4 h-4" />
          <span>New Chat</span>
        </motion.button>
      </aside>

      {/* Main Content */}
      <main className="sys-main">
        {/* Status Bar */}
        <header className="sys-status-bar">
          <div className="sys-status-item">
            <Activity className="w-3 h-3" />
            <span className="sys-status-label">FPS</span>
            <span className="sys-status-value">{systemStats.fps}</span>
          </div>
          <div className="sys-status-item">
            <Cpu className="w-3 h-3" />
            <span className="sys-status-label">GPU</span>
            <span className="sys-status-value good">{systemStats.gpu}</span>
          </div>
          <div className="sys-status-item">
            <Cpu className="w-3 h-3" />
            <span className="sys-status-label">CPU</span>
            <span className="sys-status-value good">{systemStats.cpu}</span>
          </div>
          <div className="sys-status-item">
            <Clock className="w-3 h-3" />
            <span className="sys-status-label">延迟</span>
            <span className="sys-status-value">{systemStats.latency}</span>
          </div>
        </header>

        {/* Chat Area */}
        <div className="sys-chat-area">
          <AnimatePresence mode="popLayout">
            {messages.length === 0 ? (
              <WelcomeScreen key="welcome" onExample={setLocalInput} />
            ) : (
              <motion.div
                key="messages"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                {messages.map((message, index) => (
                  <SystemMessage
                    key={message.id}
                    id={message.id}
                    role={message.role as 'user' | 'assistant'}
                    content={message.content}
                    parts={message.parts as any}
                    isStreaming={isLoading && index === messages.length - 1 && message.role === 'assistant'}
                  />
                ))}

                {/* Loading indicator */}
                {isLoading && messages[messages.length - 1]?.role === 'user' && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="sys-message"
                  >
                    <div className="sys-message-header">
                      <div className="sys-message-avatar ai">
                        <Bot className="w-3 h-3 text-white" />
                      </div>
                      <span>NogicOS</span>
                    </div>
                    <div className="sys-message-content">
                      <div className="sys-typing-indicator">
                        <span className="sys-typing-dot" />
                        <span className="sys-typing-dot" />
                        <span className="sys-typing-dot" />
                      </div>
                    </div>
                  </motion.div>
                )}

                <div ref={messagesEndRef} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Input Area */}
        <div className="sys-input-area">
          <form onSubmit={onSubmit}>
            <div className="sys-input-container">
              <div className="sys-input-main">
                <textarea
                  ref={textareaRef}
                  value={localInput}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  placeholder="直接告诉我你想做什么，我会立即行动..."
                  rows={1}
                  disabled={isLoading}
                  className="sys-textarea"
                />
              </div>
              
              <div className="sys-input-toolbar">
                <div className="sys-toolbar-left">
                  <button type="button" className="sys-toolbar-btn">
                    <Paperclip className="w-4 h-4" />
                  </button>
                  <button type="button" className="sys-toolbar-btn">
                    <Image className="w-4 h-4" />
                  </button>
                  <button type="button" className="sys-toolbar-btn">
                    <Mic className="w-4 h-4" />
                  </button>
                </div>

                <div className="sys-toolbar-right">
                  <button
                    type="button"
                    className={cn('sys-agent-toggle', agentMode && 'active')}
                    onClick={() => setAgentMode(!agentMode)}
                  >
                    <span className="sys-agent-dot" />
                    <span>Agent</span>
                  </button>
                  
                  {isLoading ? (
                    <button
                      type="button"
                      onClick={stop}
                      className="sys-send-btn"
                      style={{ background: 'var(--sys-accent-red)' }}
                    >
                      停止
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={!localInput.trim()}
                      className="sys-send-btn"
                    >
                      <Send className="w-3 h-3" />
                      发送
                    </button>
                  )}
                </div>
              </div>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}

// Welcome Screen Component
function WelcomeScreen({ onExample }: { onExample: (text: string) => void }) {
  const examples = [
    '整理桌面文件',
    '浏览网页',
    '查找文件',
    '执行任务',
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="flex flex-col items-center justify-center min-h-[50vh] text-center"
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="mb-8"
      >
        <h1 className="text-4xl font-light tracking-tight text-white mb-2">
          NogicOS
        </h1>
        <p className="text-sm text-zinc-500">
          AI Browser - The more you use, the faster it gets
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="w-full max-w-md"
      >
        <p className="text-xs text-zinc-600 mb-4">有什么需要我帮你做的吗？比如：</p>
        <div className="space-y-2">
          {examples.map((example, i) => (
            <motion.button
              key={example}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 + i * 0.1 }}
              onClick={() => onExample(example)}
              className="w-full text-left px-4 py-3 text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 rounded-lg transition-all flex items-center gap-3 group"
            >
              <span className="text-zinc-600 group-hover:text-blue-500 transition-colors">・</span>
              {example}
            </motion.button>
          ))}
        </div>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="mt-6 text-xs text-zinc-600"
        >
          直接告诉我你想做什么，我会立即行动！
        </motion.p>
      </motion.div>
    </motion.div>
  );
}

// System Message Component
interface SystemMessageProps {
  id: string;
  role: 'user' | 'assistant';
  content?: string;
  parts?: any[];
  isStreaming?: boolean;
}

function SystemMessage({ id, role, content, parts, isStreaming }: SystemMessageProps) {
  const [thinkingExpanded, setThinkingExpanded] = useState(false);
  const isUser = role === 'user';

  const textContent = parts
    ?.filter((p: any) => p.type === 'text')
    .map((p: any) => p.text)
    .join('') || content || '';

  const reasoningParts = parts?.filter((p: any) => p.type === 'reasoning') || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="sys-message"
    >
      <div className="sys-message-header">
        <div className={cn('sys-message-avatar', isUser ? 'user' : 'ai')}>
          {isUser ? (
            <User className="w-3 h-3" />
          ) : (
            <Bot className="w-3 h-3 text-white" />
          )}
        </div>
        <span>{isUser ? 'You' : 'NogicOS'}</span>
      </div>

      <div className="sys-message-content">
        {/* Thinking Block */}
        {reasoningParts.length > 0 && (
          <div className="sys-thinking">
            <div
              className="sys-thinking-header"
              onClick={() => setThinkingExpanded(!thinkingExpanded)}
            >
              {thinkingExpanded ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
              <span>Thinking...</span>
            </div>
            <AnimatePresence>
              {thinkingExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="sys-thinking-content overflow-hidden"
                >
                  {reasoningParts.map((p: any, i: number) => (
                    <p key={i}>{p.text}</p>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Main Content */}
        {textContent && (
          <StreamingText
            content={textContent}
            isStreaming={isStreaming}
          />
        )}
      </div>
    </motion.div>
  );
}


