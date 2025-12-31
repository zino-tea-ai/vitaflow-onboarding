/**
 * ChatKitArea - OpenAI ChatKit 集成组件
 * 
 * 使用 OpenAI 官方 ChatKit 框架，提供 ChatGPT 级别的聊天体验
 * 支持流式响应、客户端工具、主题定制等高级功能
 */

import { ChatKit, useChatKit } from '@openai/chatkit-react';
import { useEffect } from 'react';

interface ChatKitAreaProps {
  /** 触发显示可视化面板 */
  onShowVisualization?: () => void;
  /** 触发高亮动画 */
  onHighlight?: (params: { x: number; y: number; width: number; height: number; label?: string }) => void;
  /** 触发光标移动 */
  onCursorMove?: (params: { x: number; y: number }) => void;
  /** API 基础 URL */
  apiUrl?: string;
  /** 自定义类名 */
  className?: string;
}

export function ChatKitArea({ 
  onShowVisualization, 
  onHighlight,
  onCursorMove,
  apiUrl = 'http://localhost:8080/chatkit',
  className = '',
}: ChatKitAreaProps) {
  const { control } = useChatKit({
    api: {
      url: apiUrl,
      domainKey: 'nogicos',
    },
    
    // ========================================
    // 极致主题配置 - 匹配 NogicOS 深色风格
    // ========================================
    theme: {
      colorScheme: 'dark',
      density: 'normal',
      radius: 'round',
      color: {
        grayscale: { hue: 220, tint: 6, shade: -1 },
        accent: { primary: '#8B5CF6', level: 2 },  // 紫色强调色，与 NogicOS 一致
      },
    },
    
    // ========================================
    // 头部配置
    // ========================================
    header: {
      enabled: false,  // 使用 NogicOS 自己的 TitleBar
    },
    
    // ========================================
    // 智能开始屏幕
    // ========================================
    startScreen: {
      greeting: 'Welcome to NogicOS',
      prompts: [
        { 
          label: '打开淘宝搜索', 
          prompt: '帮我打开淘宝搜索 iPhone 16', 
          icon: 'globe',
        },
        { 
          label: '整理桌面文件', 
          prompt: '帮我整理桌面上的文件，按类型分类', 
          icon: 'lightbulb',  // 'folder' 不是有效图标，改用 lightbulb
        },
        { 
          label: '搜索 AI 新闻', 
          prompt: '搜索最新的 AI 新闻并总结', 
          icon: 'search',
        },
        { 
          label: '系统信息', 
          prompt: '显示我的系统信息', 
          icon: 'lifesaver',  // 'monitor' 不是有效图标，改用 lifesaver
        },
      ],
    },
    
    // ========================================
    // 输入框配置
    // ========================================
    composer: {
      placeholder: '告诉我你想做什么...',
      // 暂时禁用附件，后续可开启
      // attachments: { enabled: true, maxCount: 5 },
    },
    
    // ========================================
    // 消息操作
    // ========================================
    threadItemActions: {
      feedback: true,   // 👍👎 反馈按钮
      retry: true,      // 重试按钮
    },
    
    // ========================================
    // 历史记录
    // ========================================
    history: {
      enabled: true,
      showDelete: true,
      showRename: true,
    },
    
    // ========================================
    // 客户端工具 - AI 可以触发前端动作
    // ========================================
    onClientTool: async (invocation) => {
      console.log('[ChatKit] Client tool invoked:', invocation.name, invocation.params);
      
      // 显示可视化面板
      if (invocation.name === 'show_visualization') {
        onShowVisualization?.();
        return { success: true };
      }
      
      // 高亮元素
      if (invocation.name === 'highlight_element') {
        const params = invocation.params as { 
          x: number; 
          y: number; 
          width: number; 
          height: number; 
          label?: string;
        };
        onHighlight?.(params);
        return { success: true };
      }
      
      // 移动光标
      if (invocation.name === 'move_cursor') {
        const params = invocation.params as { x: number; y: number };
        onCursorMove?.(params);
        return { success: true };
      }
      
      // 播放提示音
      if (invocation.name === 'play_sound') {
        const soundType = (invocation.params as { type?: string })?.type || 'complete';
        try {
          // 使用 Web Audio API 播放简单提示音
          const audioContext = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
          const oscillator = audioContext.createOscillator();
          const gainNode = audioContext.createGain();
          
          oscillator.connect(gainNode);
          gainNode.connect(audioContext.destination);
          
          oscillator.frequency.value = soundType === 'error' ? 200 : 800;
          oscillator.type = 'sine';
          gainNode.gain.value = 0.1;
          
          oscillator.start();
          oscillator.stop(audioContext.currentTime + 0.1);
          
          return { success: true };
        } catch {
          console.warn('[ChatKit] Failed to play sound');
          return { success: false };
        }
      }
      
      // 未知工具
      console.warn('[ChatKit] Unknown client tool:', invocation.name);
      return { success: false };
    },
    
    // ========================================
    // 错误处理
    // ========================================
    onError: ({ error }) => {
      console.error('[ChatKit] Error:', error);
    },
  });

  return (
    <ChatKit 
      control={control} 
      className={`flex-1 h-full ${className}`}
    />
  );
}

export default ChatKitArea;

