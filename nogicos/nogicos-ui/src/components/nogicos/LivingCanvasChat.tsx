/**
 * LivingCanvasChat - 集成 useChat 的 Living Canvas
 * 
 * 这个组件将 LivingCanvas 的视觉体验与 useChat 的消息处理结合起来
 */

import { useState, useRef, useEffect, useCallback, useMemo, memo } from 'react';
import type { KeyboardEvent } from 'react';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { motion, AnimatePresence } from 'motion/react';
import {
  Globe,
  Code2,
  FileText,
  AppWindow,
  Zap,
  Brain,
  Eye,
  Pencil,
  Sparkles,
  ArrowUp,
  Square,
  Check,
  Loader2,
  AlertCircle,
  Terminal,
  Search,
  Folder,
  Code,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

interface ConnectedApp {
  hwnd: number;
  title: string;
  app_name: string;
  app_display_name: string;
  is_browser: boolean;
  connected_at: string;
}

type AIState = 'idle' | 'reading' | 'thinking' | 'acting' | 'success';

interface DataFlowState {
  sourceHwnd: number | null;
  targetHwnd: number | null;
  direction: 'in' | 'out';
  action?: string;
}

interface MessagePart {
  type: string;
  text?: string;
  [key: string]: unknown;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  parts?: MessagePart[];
  isHistory?: boolean;
}

interface LivingCanvasChatProps {
  apiUrl?: string;
  sessionId: string;
  // Hook 相关
  connectedApps: ConnectedApp[];
  dataFlow?: DataFlowState;
  // 初始消息
  initialMessages?: ChatMessage[];
  // 回调
  onSessionUpdate?: (title: string, preview: string) => void;
  onMessagesChange?: (messages: ChatMessage[]) => void;
  // 样式
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

const SPRING = {
  gentle: { type: 'spring' as const, stiffness: 120, damping: 14 },
  snappy: { type: 'spring' as const, stiffness: 400, damping: 25 },
  smooth: { type: 'spring' as const, stiffness: 200, damping: 20 },
  micro: { type: 'spring' as const, stiffness: 500, damping: 35 },
};

const COLORS = {
  emerald: {
    primary: '#10b981',
    light: '#34d399',
    dark: '#059669',
    glow: 'rgba(16, 185, 129, 0.3)',
  },
  sky: {
    primary: '#0ea5e9',
    light: '#38bdf8',
    glow: 'rgba(14, 165, 233, 0.3)',
  },
  violet: {
    primary: '#8b5cf6',
    light: '#a78bfa',
    glow: 'rgba(139, 92, 246, 0.3)',
  },
  amber: {
    primary: '#f59e0b',
    light: '#fbbf24',
    glow: 'rgba(245, 158, 11, 0.3)',
  },
};

const STATE_CONFIG = {
  idle: { color: COLORS.emerald, icon: Zap, label: 'Ready' },
  reading: { color: COLORS.sky, icon: Eye, label: 'Reading' },
  thinking: { color: COLORS.violet, icon: Brain, label: 'Thinking' },
  acting: { color: COLORS.amber, icon: Pencil, label: 'Acting' },
  success: { color: COLORS.emerald, icon: Sparkles, label: 'Done' },
};

// App icon mapping
const APP_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  'Google Chrome': Globe,
  'Chrome': Globe,
  'Mozilla Firefox': Globe,
  'Microsoft Edge': Globe,
  'VS Code': Code2,
  'Cursor': Code2,
  'File Explorer': FileText,
  'Finder': FileText,
  'Figma': AppWindow,
};

function getAppIcon(appName: string) {
  if (APP_ICONS[appName]) return APP_ICONS[appName];
  for (const [key, icon] of Object.entries(APP_ICONS)) {
    if (appName.toLowerCase().includes(key.toLowerCase())) return icon;
  }
  return AppWindow;
}

// ============================================================================
// Neural Background
// ============================================================================

const NeuralBackground = memo(function NeuralBackground({
  connectedApps,
  dataFlow,
  aiState = 'idle',
  dimensions,
}: {
  connectedApps: ConnectedApp[];
  dataFlow?: DataFlowState;
  aiState: AIState;
  dimensions: { width: number; height: number };
}) {
  const config = STATE_CONFIG[aiState];
  
  const centerX = dimensions.width / 2;
  const centerY = dimensions.height * 0.45; // 调整到区域中心偏下
  const radius = Math.min(dimensions.width * 0.20, 100); // 缩小半径适应固定高度

  const nodePositions = useMemo(() => {
    return connectedApps.map((app, index) => {
      const startAngle = -Math.PI / 2;
      const angle = startAngle + (2 * Math.PI * index) / Math.max(connectedApps.length, 1);
      return {
        app,
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
        angle,
      };
    });
  }, [connectedApps, centerX, centerY, radius]);

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden">
      {/* 微妙的网格背景 */}
      <div 
        className="absolute inset-0 opacity-[0.015]"
        style={{
          backgroundImage: `
            radial-gradient(circle at 50% 30%, ${config.color.glow} 0%, transparent 50%),
            linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)
          `,
          backgroundSize: '100% 100%, 60px 60px, 60px 60px',
        }}
      />

      {/* SVG 连接线 */}
      <svg 
        className="absolute inset-0" 
        width={dimensions.width} 
        height={dimensions.height}
        style={{ overflow: 'visible' }}
      >
        {nodePositions.map(({ app, x, y }, index) => {
          const isActive = dataFlow?.sourceHwnd === app.hwnd;
          const flowColor = dataFlow?.direction === 'out' ? COLORS.amber : COLORS.sky;
          
          const midX = (x + centerX) / 2;
          const midY = (y + centerY) / 2;
          const dx = centerX - x;
          const dy = centerY - y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const offset = dist * 0.12;
          const perpX = -dy / dist * offset;
          const perpY = dx / dist * offset;
          const ctrlX = midX + perpX;
          const ctrlY = midY + perpY;
          const pathD = `M ${x} ${y} Q ${ctrlX} ${ctrlY} ${centerX} ${centerY}`;

          return (
            <g key={app.hwnd}>
              <motion.path
                d={pathD}
                fill="none"
                stroke={isActive ? flowColor.primary : 'rgba(16, 185, 129, 0.3)'}
                strokeWidth={isActive ? 2 : 1}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 0.8, delay: index * 0.1 }}
              />

              {isActive && (
                <motion.path
                  d={pathD}
                  fill="none"
                  stroke={flowColor.light}
                  strokeWidth={3}
                  style={{ filter: 'blur(3px)' }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: [0.2, 0.4, 0.2] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
              )}

              {isActive && dataFlow?.direction && (
                <>
                  {[0, 1, 2].map((i) => (
                    <circle
                      key={i}
                      r={3}
                      fill={flowColor.light}
                      style={{ filter: `drop-shadow(0 0 4px ${flowColor.primary})` }}
                    >
                      <animate
                        attributeName="cx"
                        values={dataFlow.direction === 'in' 
                          ? `${x};${ctrlX};${centerX}` 
                          : `${centerX};${ctrlX};${x}`
                        }
                        keyTimes="0;0.5;1"
                        dur="1.2s"
                        repeatCount="indefinite"
                        begin={`${i * 0.4}s`}
                      />
                      <animate
                        attributeName="cy"
                        values={dataFlow.direction === 'in' 
                          ? `${y};${ctrlY};${centerY}` 
                          : `${centerY};${ctrlY};${y}`
                        }
                        keyTimes="0;0.5;1"
                        dur="1.2s"
                        repeatCount="indefinite"
                        begin={`${i * 0.4}s`}
                      />
                      <animate
                        attributeName="opacity"
                        values="0;1;1;0"
                        keyTimes="0;0.1;0.9;1"
                        dur="1.2s"
                        repeatCount="indefinite"
                        begin={`${i * 0.4}s`}
                      />
                    </circle>
                  ))}
                </>
              )}
            </g>
          );
        })}
      </svg>

      {/* 应用节点 */}
      <AnimatePresence>
        {nodePositions.map(({ app, x, y }, index) => {
          const Icon = getAppIcon(app.app_display_name);
          const isActive = dataFlow?.sourceHwnd === app.hwnd;
          
          return (
            <motion.div
              key={app.hwnd}
              className="absolute pointer-events-auto"
              style={{ left: x, top: y, transform: 'translate(-50%, -50%)' }}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              transition={{ ...SPRING.snappy, delay: index * 0.08 }}
            >
              <div
                className={cn(
                  "w-9 h-9 rounded-full flex items-center justify-center",
                  "border transition-all duration-300",
                  isActive 
                    ? "border-white/30 bg-white/10" 
                    : "border-white/10 bg-black/40 hover:border-white/20"
                )}
              >
                <Icon className={cn(
                  "w-4 h-4 transition-colors",
                  isActive ? "text-white" : "text-white/40"
                )} />
              </div>
              
              <div className="absolute top-full mt-1 left-1/2 -translate-x-1/2 whitespace-nowrap">
                <span className={cn(
                  "text-[10px] transition-colors",
                  isActive ? "text-white/80" : "text-white/30"
                )}>
                  {app.app_display_name}
                </span>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>

      {/* 中心 AI 节点 */}
      <motion.div
        className="absolute"
        style={{ left: centerX, top: centerY, transform: 'translate(-50%, -50%)' }}
        animate={{ scale: aiState === 'thinking' ? [1, 1.02, 1] : 1 }}
        transition={{ duration: 2, repeat: aiState === 'thinking' ? Infinity : 0 }}
      >
        {aiState === 'thinking' && (
          <>
            {[1, 2, 3].map((i) => (
              <motion.div
                key={i}
                className="absolute rounded-full border"
                style={{
                  width: 48, height: 48,
                  left: '50%', top: '50%',
                  x: '-50%', y: '-50%',
                  borderColor: config.color.primary,
                }}
                initial={{ scale: 1, opacity: 0.4 }}
                animate={{ scale: 2.5, opacity: 0 }}
                transition={{ duration: 2, repeat: Infinity, delay: i * 0.6 }}
              />
            ))}
          </>
        )}

        <motion.div
          className="absolute rounded-full"
          style={{
            width: 64, height: 64,
            left: '50%', top: '50%',
            x: '-50%', y: '-50%',
            background: `radial-gradient(circle, ${config.color.glow} 0%, transparent 70%)`,
          }}
          animate={{
            scale: aiState === 'idle' ? [1, 1.1, 1] : [1, 1.15, 1],
            opacity: aiState === 'idle' ? 0.3 : 0.5,
          }}
          transition={{ duration: aiState === 'idle' ? 4 : 2, repeat: Infinity }}
        />

        <motion.div
          className="relative w-12 h-12 rounded-full flex items-center justify-center overflow-hidden"
          style={{
            background: `linear-gradient(135deg, ${'dark' in config.color ? config.color.dark : config.color.primary} 0%, ${config.color.primary} 50%, ${config.color.light} 100%)`,
            boxShadow: `0 0 25px ${config.color.glow}`,
          }}
        >
          <motion.div
            className="absolute inset-0"
            animate={{ rotate: 360 }}
            transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
          >
            <div 
              className="absolute top-0 left-1/2 w-1/2 h-full origin-left"
              style={{ background: `linear-gradient(90deg, transparent 0%, ${config.color.light}20 100%)` }}
            />
          </motion.div>

          <motion.div
            key={aiState}
            initial={{ scale: 0, rotate: -180 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={SPRING.snappy}
          >
            {(() => {
              const StateIcon = config.icon;
              return <StateIcon className="w-5 h-5 text-white relative z-10" />;
            })()}
          </motion.div>
        </motion.div>

        <motion.div 
          className="absolute top-full mt-2 left-1/2 -translate-x-1/2 text-center whitespace-nowrap"
          key={aiState}
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="text-xs font-medium text-white/80">NogicOS</div>
          <div className="text-[10px]" style={{ color: config.color.light }}>
            {connectedApps.length > 0 
              ? `${connectedApps.length} connected` 
              : 'Ready'}
          </div>
          {/* 空状态提示 - 放在标签下方避免重叠 */}
          {connectedApps.length === 0 && (
            <div className="mt-4 text-white/20 text-[10px]">
              Connect apps to see the magic
            </div>
          )}
        </motion.div>
      </motion.div>
    </div>
  );
});

// ============================================================================
// Status Bar
// ============================================================================

const StatusBar = memo(function StatusBar({
  aiState,
  currentAction,
}: {
  aiState: AIState;
  currentAction?: string;
}) {
  const config = STATE_CONFIG[aiState];

  if (aiState === 'idle' && !currentAction) {
    return null;
  }

  return (
    <motion.div
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06]"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={SPRING.snappy}
    >
      <motion.div
        className="w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: config.color.primary }}
        animate={{ scale: aiState !== 'idle' ? [1, 1.3, 1] : 1 }}
        transition={{ duration: 1, repeat: aiState !== 'idle' ? Infinity : 0 }}
      />

      <span className="text-[11px] text-white/60">
        {currentAction || config.label}
      </span>
    </motion.div>
  );
});

// ============================================================================
// Tool Display Helpers
// ============================================================================

interface ToolInfo {
  type: string;
  toolCallId: string;
  toolName?: string;
  state: string;
  input?: Record<string, unknown>;
  output?: unknown;
}

function getFileName(path: string): string {
  if (!path) return '';
  return path.split(/[/\\]/).pop() || path;
}

function formatToolDisplay(toolName: string, input: Record<string, unknown> | undefined) {
  const name = toolName.toLowerCase().replace(/^tool-/, '');
  const str = (v: unknown) => typeof v === 'string' ? v : '';
  
  switch (name) {
    case 'read_file':
      return { icon: <FileText className="w-3 h-3" />, label: `Read ${getFileName(str(input?.target_file))}` };
    case 'list_dir':
      return { icon: <Folder className="w-3 h-3" />, label: `Listed ${getFileName(str(input?.target_directory))}` };
    case 'codebase_search':
      return { icon: <Search className="w-3 h-3" />, label: `Searched "${str(input?.query).slice(0, 25)}..."` };
    case 'grep':
      return { icon: <Code className="w-3 h-3" />, label: `Grep ${str(input?.pattern)}` };
    case 'browser_navigate':
    case 'browser_click':
    case 'browser_type':
      return { icon: <Globe className="w-3 h-3" />, label: name.replace('browser_', '') };
    case 'run_terminal_cmd':
      return { icon: <Terminal className="w-3 h-3" />, label: `Run ${str(input?.command).slice(0, 30)}...` };
    default:
      return { icon: <Terminal className="w-3 h-3" />, label: name.replace(/_/g, ' ') };
  }
}

const ToolItem = memo(function ToolItem({ tool }: { tool: ToolInfo }) {
  const toolName = tool.toolName || tool.type?.replace(/^tool-/, '') || 'unknown';
  const display = formatToolDisplay(toolName, tool.input);
  const isError = tool.state === 'error';
  const isRunning = tool.state === 'input-streaming' || tool.state === 'input-available';
  
  return (
    <motion.div 
      className="flex items-center gap-2 text-[11px]"
      initial={{ opacity: 0, x: -5 }}
      animate={{ opacity: 1, x: 0 }}
    >
      <span className="text-white/40">
        {isError ? <AlertCircle className="w-3 h-3 text-red-400" />
         : isRunning ? <Loader2 className="w-3 h-3 animate-spin" />
         : <Check className="w-3 h-3 text-emerald-400" />}
      </span>
      <span className="text-white/30">{display.icon}</span>
      <span className="text-white/50">{display.label}</span>
    </motion.div>
  );
});

// ============================================================================
// Message Bubble
// ============================================================================

const MessageBubble = memo(function MessageBubble({
  message,
  isStreaming,
  toolInvocations,
}: {
  message: { role: 'user' | 'assistant'; content: string; isHistory?: boolean };
  isStreaming?: boolean;
  toolInvocations?: ToolInfo[];
}) {
  const isUser = message.role === 'user';
  const hasTools = toolInvocations && toolInvocations.length > 0;

  return (
    <motion.div
      className={cn(
        "max-w-[85%] rounded-2xl px-4 py-3",
        "backdrop-blur-md",
        isUser 
          ? "ml-auto bg-emerald-500/15 border border-emerald-500/20" 
          : "mr-auto bg-white/[0.03] border border-white/[0.06]"
      )}
      initial={message.isHistory ? false : { opacity: 0, y: 15, filter: 'blur(4px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      transition={message.isHistory ? { duration: 0 } : { duration: 0.35 }}
    >
      <div className={cn(
        "text-[10px] font-medium mb-1",
        isUser ? "text-emerald-400/80" : "text-white/40"
      )}>
        {isUser ? 'You' : 'NogicOS'}
      </div>

      {hasTools && (
        <div className="mb-2 space-y-1 pb-2 border-b border-white/5">
          {toolInvocations.map((tool, i) => (
            <ToolItem key={tool.toolCallId || i} tool={tool} />
          ))}
        </div>
      )}

      <div className={cn(
        "text-sm leading-relaxed",
        isUser ? "text-white" : "text-white/90"
      )}>
        {!isUser ? (
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
              code: ({ className, children }) => {
                const match = /language-(\w+)/.exec(className || '');
                return match ? (
                  <SyntaxHighlighter
                    style={oneDark as Record<string, React.CSSProperties>}
                    language={match[1]}
                    PreTag="div"
                    customStyle={{ margin: 0, padding: '0.75rem', borderRadius: '0.5rem', fontSize: '0.8rem' }}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (
                  <code className="bg-neutral-800 px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>
                );
              },
              a: ({ href, children }) => {
                const isSafe = href && (href.startsWith('http://') || href.startsWith('https://') || href.startsWith('#'));
                if (!isSafe) return <span className="text-neutral-400">{children}</span>;
                return <a href={href} className="text-white underline hover:text-neutral-300" target="_blank" rel="noopener noreferrer">{children}</a>;
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        ) : (
          <span className="whitespace-pre-wrap">{message.content}</span>
        )}
        {isStreaming && (
          <motion.span
            className="inline-block w-2 h-4 ml-0.5 bg-white/60 rounded-sm"
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 0.8, repeat: Infinity }}
          />
        )}
      </div>
    </motion.div>
  );
});

// ============================================================================
// Main Component
// ============================================================================

export function LivingCanvasChat({
  apiUrl = 'http://localhost:8080/api/chat',
  sessionId,
  connectedApps,
  dataFlow,
  initialMessages = [],
  onSessionUpdate,
  onMessagesChange,
  className,
}: LivingCanvasChatProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [localInput, setLocalInput] = useState('');
  const [isFocused, setIsFocused] = useState(false);

  // Chat transport
  const chatTransport = useMemo(() => new DefaultChatTransport({
    api: apiUrl,
    body: { session_id: sessionId },
  }), [apiUrl, sessionId]);

  // useChat
  const {
    messages: chatMessages,
    sendMessage,
    stop,
    status,
    setMessages,
  } = useChat({
    id: `living-${sessionId}`,
    transport: chatTransport,
    onError: (err) => {
      console.error('[LivingCanvasChat] Error:', err);
    },
  });

  const isLoading = status === 'submitted' || status === 'streaming';

  // Derive AI state from status and messages
  const aiState: AIState = useMemo(() => {
    if (status === 'submitted') return 'thinking';
    if (status === 'streaming') {
      const lastMsg = chatMessages[chatMessages.length - 1];
      if (lastMsg && lastMsg.parts) {
        const hasTool = lastMsg.parts.some((p: MessagePart) => 
          p.type?.startsWith('tool-') || p.type === 'dynamic-tool'
        );
        if (hasTool) return 'acting';
      }
      return 'thinking';
    }
    return 'idle';
  }, [status, chatMessages]);

  // Current action for status bar
  const currentAction = useMemo(() => {
    if (!isLoading) return undefined;
    const lastMsg = chatMessages[chatMessages.length - 1];
    if (lastMsg?.parts) {
      const toolPart = lastMsg.parts.find((p: MessagePart) => 
        p.type?.startsWith('tool-') && (p as { state?: string }).state !== 'output-available'
      );
      if (toolPart) {
        const toolName = (toolPart as { toolName?: string }).toolName || '';
        return `Running ${toolName.replace(/_/g, ' ')}...`;
      }
    }
    return status === 'submitted' ? 'Processing...' : 'Generating...';
  }, [isLoading, chatMessages, status]);

  // Load initial messages
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
      setMessages(formatted as Parameters<typeof setMessages>[0]);
    }
  }, [initialMessages, setMessages]);

  // Update dimensions
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({ width: rect.width, height: rect.height });
      }
    };
    updateDimensions();
    const resizeObserver = new ResizeObserver(updateDimensions);
    if (containerRef.current) resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  // Auto resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  }, [localInput]);

  // Auto scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Save messages callback
  const onMessagesChangeRef = useRef(onMessagesChange);
  useEffect(() => { onMessagesChangeRef.current = onMessagesChange; }, [onMessagesChange]);
  
  useEffect(() => {
    if (chatMessages.length > 0 && onMessagesChangeRef.current) {
      const toSave = chatMessages.map(m => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: (m as unknown as { content?: string }).content || '',
        parts: m.parts,
      }));
      onMessagesChangeRef.current(toSave);
    }
  }, [chatMessages]);

  // Update session title
  useEffect(() => {
    if (onSessionUpdate && chatMessages.length > 0) {
      const firstUserMsg = chatMessages.find(m => m.role === 'user');
      if (firstUserMsg) {
        const content = (firstUserMsg as unknown as { content?: string }).content || '';
        onSessionUpdate(content.slice(0, 30), content.slice(0, 100));
      }
    }
  }, [chatMessages, onSessionUpdate]);

  // Submit handler
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (localInput.trim() && !isLoading) {
      const text = localInput.trim();
      setLocalInput('');
      await sendMessage({ text });
    }
  }, [localInput, isLoading, sendMessage]);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  }, [handleSubmit]);

  // Format messages for display
  const displayMessages = useMemo(() => {
    return chatMessages.map(m => {
      const msgAny = m as unknown as { content?: string; parts?: MessagePart[] };
      const toolInvocations: ToolInfo[] = (m.parts || [])
        .filter((p: MessagePart) => p.type?.startsWith('tool-'))
        .map((p: MessagePart) => {
          const part = p as MessagePart & { toolCallId?: string; toolName?: string; state?: string; input?: Record<string, unknown>; output?: unknown };
          return {
            type: part.type,
            toolCallId: part.toolCallId || '',
            toolName: part.toolName,
            state: part.state || 'pending',
            input: part.input,
            output: part.output,
          };
        });
      
      return {
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: msgAny.content || '',
        isHistory: m.id.startsWith('loaded-'),
        toolInvocations,
      };
    });
  }, [chatMessages]);

  const isEmpty = displayMessages.length === 0;

  return (
    <div 
      ref={containerRef}
      className={cn(
        "relative w-full h-full flex flex-col overflow-hidden",
        "bg-[#0a0a0a]",
        className
      )}
    >
      {/* 神经网络区域 - 固定高度 */}
      <div className="relative w-full h-[240px] flex-shrink-0">
        <NeuralBackground
          connectedApps={connectedApps}
          dataFlow={dataFlow}
          aiState={aiState}
          dimensions={{ width: dimensions.width, height: 240 }}
        />
      </div>

      {/* 内容层 - 对话区域 */}
      <div className="relative flex-1 flex flex-col overflow-hidden">
        {/* 消息区域 */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          <div className="max-w-2xl mx-auto">
            <AnimatePresence mode="popLayout">
              {isEmpty ? (
                <motion.div
                  key="welcome"
                  className="flex flex-col items-center justify-center py-12"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <motion.p 
                    className="text-white/40 text-sm"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 }}
                  >
                    Start a conversation...
                  </motion.p>
                </motion.div>
              ) : (
                <div className="space-y-4">
                  {displayMessages.map((message, index) => (
                    <MessageBubble
                      key={message.id || index}
                      message={message}
                      isStreaming={isLoading && index === displayMessages.length - 1 && message.role === 'assistant'}
                      toolInvocations={message.toolInvocations}
                    />
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* 控制层 */}
        <div className="px-4 pb-4">
          <div className="max-w-2xl mx-auto space-y-3">
            {/* 状态条 */}
            <div className="flex justify-center">
              <StatusBar aiState={aiState} currentAction={currentAction} />
            </div>

            {/* 输入框 */}
            <form onSubmit={handleSubmit}>
              <motion.div
                className={cn(
                  "flex items-end gap-2 p-2 rounded-xl",
                  "bg-white/[0.03] border transition-all duration-200",
                  isFocused ? "border-white/20" : "border-white/[0.08]"
                )}
                animate={{
                  boxShadow: isFocused 
                    ? '0 0 0 1px rgba(255,255,255,0.1), 0 4px 20px rgba(0,0,0,0.3)' 
                    : '0 2px 8px rgba(0,0,0,0.2)',
                }}
              >
                <textarea
                  ref={textareaRef}
                  value={localInput}
                  onChange={(e) => setLocalInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  placeholder="Message NogicOS..."
                  rows={1}
                  disabled={isLoading}
                  className={cn(
                    "flex-1 bg-transparent border-0 outline-none resize-none",
                    "text-sm text-white placeholder:text-white/30",
                    "py-2 px-2 max-h-[150px]"
                  )}
                />

                <AnimatePresence mode="wait">
                  {isLoading ? (
                    <motion.button
                      key="stop"
                      type="button"
                      onClick={stop}
                      className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/15 flex items-center justify-center"
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.8, opacity: 0 }}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      <Square className="w-3.5 h-3.5 text-white" fill="currentColor" />
                    </motion.button>
                  ) : (
                    <motion.button
                      key="send"
                      type="submit"
                      disabled={!localInput.trim()}
                      className={cn(
                        "w-8 h-8 rounded-lg flex items-center justify-center transition-all",
                        localInput.trim() 
                          ? "bg-emerald-500 hover:bg-emerald-400 text-white" 
                          : "bg-white/5 text-white/30"
                      )}
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.8, opacity: 0 }}
                      whileHover={localInput.trim() ? { scale: 1.05 } : undefined}
                      whileTap={localInput.trim() ? { scale: 0.95 } : undefined}
                    >
                      <ArrowUp className="w-4 h-4" />
                    </motion.button>
                  )}
                </AnimatePresence>
              </motion.div>
            </form>

            {/* Hints */}
            <div className="flex items-center justify-between px-1">
              <span className="text-[10px] text-white/20">
                <kbd className="px-1 py-0.5 rounded bg-white/5">Enter</kbd> to send
              </span>
              <motion.span 
                className="text-[10px] flex items-center gap-1"
                style={{ color: STATE_CONFIG[aiState].color.light }}
              >
                <motion.span 
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ backgroundColor: STATE_CONFIG[aiState].color.primary }}
                  animate={{ scale: aiState !== 'idle' ? [1, 1.3, 1] : [1, 1.2, 1] }}
                  transition={{ duration: aiState !== 'idle' ? 1 : 2, repeat: Infinity }}
                />
                {STATE_CONFIG[aiState].label}
              </motion.span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LivingCanvasChat;
