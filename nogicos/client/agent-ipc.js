/**
 * Agent IPC Handlers
 * Phase 7.12: Main 进程 IPC Handlers
 * 
 * 处理 Agent 相关的 IPC 通信，包含严格的参数验证
 */

const { ipcMain } = require('electron');
const { IPCBatcher } = require('./ipc-batcher');

// UUID 验证正则
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// 后端 API 基础 URL
const API_BASE = process.env.NOGICOS_API_URL || 'http://localhost:8000';

/**
 * 验证 UUID 格式
 * @param {string} str 
 * @returns {boolean}
 */
function isValidUUID(str) {
  return typeof str === 'string' && UUID_REGEX.test(str);
}

/**
 * 验证任务文本
 * @param {string} task 
 * @returns {{valid: boolean, error?: string}}
 */
function validateTask(task) {
  if (!task || typeof task !== 'string') {
    return { valid: false, error: 'Invalid task: must be a non-empty string' };
  }
  if (task.length > 5000) {
    return { valid: false, error: 'Task too long: max 5000 characters' };
  }
  // 基本的 XSS 防护（虽然主要靠 CSP）
  if (/<script|javascript:|on\w+=/i.test(task)) {
    return { valid: false, error: 'Invalid task: contains suspicious content' };
  }
  return { valid: true };
}

/**
 * 验证窗口句柄数组
 * 
 * Phase 8 修复: 允许空数组，支持 HostAgent 自动检测前景窗口功能。
 * 当 targetHwnds 为空时，后端会调用 _detect_target_windows() 自动检测。
 * 
 * @param {number[]} hwnds 
 * @returns {{valid: boolean, error?: string}}
 */
function validateHwnds(hwnds) {
  if (!Array.isArray(hwnds)) {
    return { valid: false, error: 'Invalid targetHwnds: must be an array' };
  }
  // Phase 8 修复: 允许空数组，后端会自动检测前景窗口
  // if (hwnds.length === 0) {
  //   return { valid: false, error: 'Invalid targetHwnds: array cannot be empty' };
  // }
  if (hwnds.length > 10) {
    return { valid: false, error: 'Invalid targetHwnds: max 10 windows' };
  }
  // 只有非空时才验证元素
  if (hwnds.length > 0 && !hwnds.every(h => typeof h === 'number' && h > 0 && Number.isInteger(h))) {
    return { valid: false, error: 'Invalid targetHwnds: must contain positive integers' };
  }
  return { valid: true };
}

/**
 * 安全的 fetch 包装
 * @param {string} url 
 * @param {RequestInit} options 
 */
async function safeFetch(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000); // 30秒超时
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API error (${response.status}): ${errorText}`);
    }
    
    return response.json();
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * 注册 Agent IPC Handlers
 * @param {Electron.BrowserWindow} mainWindow 
 * @param {object} [options] - 可选配置
 * @param {object} [options.multiOverlayManager] - 多窗口 Overlay 管理器（用于动作预览）
 */
function registerAgentIpcHandlers(mainWindow, options = {}) {
  let agentWs = null;
  let batcher = null;
  const { multiOverlayManager } = options;

  // ============== Agent 控制 Handlers ==============

  /**
   * 启动任务
   */
  ipcMain.handle('agent:start', async (event, { task, targetHwnds }) => {
    // 参数验证
    const taskValidation = validateTask(task);
    if (!taskValidation.valid) {
      throw new Error(taskValidation.error);
    }
    
    const hwndsValidation = validateHwnds(targetHwnds);
    if (!hwndsValidation.valid) {
      throw new Error(hwndsValidation.error);
    }
    
    console.log(`[Agent] Starting task with ${targetHwnds.length} target windows`);
    
    const result = await safeFetch(`${API_BASE}/api/agent/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, target_hwnds: targetHwnds }),
    });
    
    // 连接 WebSocket 以接收实时事件
    if (result.taskId) {
      connectAgentWebSocket(result.taskId);
    }
    
    return result;
  });

  /**
   * 停止任务
   */
  ipcMain.handle('agent:stop', async (event, { taskId }) => {
    if (!taskId || !isValidUUID(taskId)) {
      throw new Error('Invalid taskId: must be a valid UUID');
    }
    
    console.log(`[Agent] Stopping task: ${taskId}`);
    
    // 断开 WebSocket
    disconnectAgentWebSocket();
    
    return safeFetch(`${API_BASE}/api/agent/stop?task_id=${taskId}`, {
      method: 'POST',
    });
  });

  /**
   * 恢复任务
   */
  ipcMain.handle('agent:resume', async (event, { taskId }) => {
    if (!taskId || !isValidUUID(taskId)) {
      throw new Error('Invalid taskId: must be a valid UUID');
    }
    
    console.log(`[Agent] Resuming task: ${taskId}`);
    
    const result = await safeFetch(`${API_BASE}/api/agent/resume?task_id=${taskId}`, {
      method: 'POST',
    });
    
    // 重新连接 WebSocket
    connectAgentWebSocket(taskId);
    
    return result;
  });

  /**
   * 确认敏感操作
   */
  ipcMain.handle('agent:confirm', async (event, { taskId, actionId, approved }) => {
    // 严格验证
    if (!taskId || !isValidUUID(taskId)) {
      throw new Error('Invalid taskId: must be a valid UUID');
    }
    if (!actionId || typeof actionId !== 'string' || actionId.length > 100) {
      throw new Error('Invalid actionId: must be a non-empty string');
    }
    if (typeof approved !== 'boolean') {
      throw new Error('Invalid approved: must be boolean');
    }
    
    // 记录审计日志
    const auditLog = {
      timestamp: new Date().toISOString(),
      taskId,
      actionId,
      decision: approved ? 'APPROVED' : 'REJECTED',
    };
    console.log(`[Audit] Sensitive action: ${JSON.stringify(auditLog)}`);
    
    return safeFetch(`${API_BASE}/api/agent/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: taskId, action_id: actionId, approved }),
    });
  });

  /**
   * 获取任务状态
   */
  ipcMain.handle('agent:status', async (event, { taskId }) => {
    if (!taskId || !isValidUUID(taskId)) {
      throw new Error('Invalid taskId: must be a valid UUID');
    }
    
    return safeFetch(`${API_BASE}/api/agent/status/${taskId}`);
  });

  /**
   * 获取所有活跃任务
   */
  ipcMain.handle('agent:active-tasks', async () => {
    return safeFetch(`${API_BASE}/api/agent/active`);
  });

  // ============== WebSocket 桥接 ==============

  /**
   * 连接 Agent WebSocket
   * @param {string} taskId 
   */
  function connectAgentWebSocket(taskId) {
    // 先断开现有连接
    disconnectAgentWebSocket();
    
    const wsUrl = API_BASE.replace('http', 'ws');
    
    try {
      // Node.js 环境可能需要 ws 库
      const WebSocket = require('ws');
      agentWs = new WebSocket(`${wsUrl}/ws/agent/${taskId}`);
      
      // 创建批处理器
      if (mainWindow && !mainWindow.isDestroyed()) {
        batcher = new IPCBatcher(mainWindow.webContents);
      }
      
      agentWs.on('open', () => {
        console.log('[Agent WS] Connected');
      });
      
      agentWs.on('message', (rawData) => {
        try {
          const data = JSON.parse(rawData.toString());
          
          // 转发到渲染进程
          if (batcher && !batcher.isDestroyed()) {
            batcher.send('agent:event', data);
          }
          
          // Phase 7: 动作预览转发到 Overlay（传入 mainWindow 用于无 hwnd 时的通知）
          if (multiOverlayManager && data.type === 'tool') {
            handleToolEventForPreview(data, multiOverlayManager, mainWindow);
          }
          
          // Phase 7: 初始化活跃窗口（首次收到工具事件时）
          if (multiOverlayManager && multiOverlayManager.initializeActiveIfNeeded) {
            multiOverlayManager.initializeActiveIfNeeded();
          }
          
          // Phase 7: 多窗口焦点管理
          if (multiOverlayManager && data.type === 'focus' && data.data?.hwnd) {
            multiOverlayManager.setActiveWindow(data.data.hwnd);
          }
          
        } catch (e) {
          console.error('[Agent WS] Failed to parse message:', e);
        }
      });
      
      agentWs.on('error', (error) => {
        console.error('[Agent WS] Error:', error.message);
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('agent:event', {
            type: 'error',
            data: { 
              type: 'connection_error',
              message: error.message,
              recoverable: true,
            },
          });
        }
      });
      
      agentWs.on('close', (code, reason) => {
        console.log(`[Agent WS] Closed (${code}): ${reason}`);
        cleanup();
      });
      
    } catch (error) {
      console.error('[Agent WS] Failed to create WebSocket:', error);
      // WebSocket 连接失败不应该阻止其他功能
    }
  }

  /**
   * 断开 Agent WebSocket
   */
  function disconnectAgentWebSocket() {
    if (agentWs) {
      try {
        agentWs.close();
      } catch (e) {
        // 忽略关闭错误
      }
      agentWs = null;
    }
    cleanup();
  }

  /**
   * 清理资源
   */
  function cleanup() {
    if (batcher) {
      batcher.destroy();
      batcher = null;
    }
  }

  // 返回控制函数供外部使用
  return {
    connectAgentWebSocket,
    disconnectAgentWebSocket,
    cleanup,
  };
}

/**
 * 注销所有 Agent IPC Handlers
 */
function unregisterAgentIpcHandlers() {
  const channels = [
    'agent:start',
    'agent:stop',
    'agent:resume',
    'agent:confirm',
    'agent:status',
    'agent:active-tasks',
  ];
  
  channels.forEach(channel => {
    ipcMain.removeHandler(channel);
  });
  
  console.log('[Agent] IPC handlers unregistered');
}

/**
 * 需要可视预览的工具列表（用于默认提示）
 */
const TOOLS_WITH_PREVIEW = new Set([
  'window_click', 'click', 'double_click', 'right_click',
  'window_type', 'type', 'input_text',
  'keyboard_shortcut', 'hotkey', 'key_press',
  'scroll', 'scroll_to',
  'drag', 'drag_and_drop',
  'window_move', 'window_resize', 'window_close', 'window_maximize', 'window_minimize',
  'open_application', 'open_file', 'open_url',
  'copy', 'paste', 'cut', 'select_all',
]);

/**
 * 工具名到人类可读描述的映射
 */
const TOOL_LABELS = {
  'window_click': '点击',
  'click': '点击',
  'double_click': '双击',
  'right_click': '右键点击',
  'window_type': '输入文字',
  'type': '输入文字',
  'input_text': '输入文字',
  'keyboard_shortcut': '快捷键',
  'hotkey': '快捷键',
  'key_press': '按键',
  'scroll': '滚动',
  'scroll_to': '滚动到',
  'drag': '拖拽',
  'drag_and_drop': '拖放',
  'window_move': '移动窗口',
  'window_resize': '调整大小',
  'window_close': '关闭窗口',
  'window_maximize': '最大化',
  'window_minimize': '最小化',
  'open_application': '打开应用',
  'open_file': '打开文件',
  'open_url': '打开链接',
  'copy': '复制',
  'paste': '粘贴',
  'cut': '剪切',
  'select_all': '全选',
};

/**
 * 处理工具事件并转发动作预览到 Overlay
 * @param {object} event - 工具事件
 * @param {object} manager - MultiOverlayManager 实例
 * @param {Electron.BrowserWindow} [mainWindow] - 主窗口（用于无 hwnd 时发送通知）
 */
function handleToolEventForPreview(event, manager, mainWindow = null) {
  const { data } = event;
  if (!data) return;
  
  const { tool_name, args, hwnd, coordinates, element_name } = data;
  
  // 参数校验
  if (!tool_name || typeof tool_name !== 'string') {
    console.warn('[Preview] Invalid tool_name:', tool_name);
    return;
  }
  
  // hwnd 校验（可选，某些工具可能不需要）
  const validHwnd = typeof hwnd === 'number' && hwnd > 0;
  
  // 辅助函数：为无 hwnd 的操作发送 renderer 侧提示
  const sendRendererToast = (message) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('agent:event', {
        type: 'toast',
        data: {
          message,
          tool_name,
          timestamp: Date.now(),
        },
      });
    }
  };
  
  // 根据工具类型发送不同的预览
  switch (tool_name) {
    case 'window_click':
    case 'click':
    case 'double_click':
    case 'right_click':
      if (validHwnd && coordinates) {
        const clickType = tool_name === 'double_click' ? 'double-click' 
                        : tool_name === 'right_click' ? 'right-click' 
                        : 'click';
        manager.sendActionPreview(hwnd, 'target', {
          x: coordinates.x,
          y: coordinates.y,
          label: `即将${TOOL_LABELS[tool_name] || '点击'}: ${element_name || ''}`,
        });
        // 短暂延迟后显示点击效果
        setTimeout(() => {
          manager.sendActionPreview(hwnd, 'click', {
            x: coordinates.x,
            y: coordinates.y,
            type: clickType,
          });
        }, 500);
      }
      break;
      
    case 'window_type':
    case 'type':
    case 'input_text':
      if (validHwnd && args?.text) {
        manager.sendActionPreview(hwnd, 'typing', {
          text: args.text,
          isPassword: args.is_password || false,
        });
      }
      break;
      
    case 'keyboard_shortcut':
    case 'hotkey':
    case 'key_press':
      if (validHwnd) {
        const shortcut = args?.shortcut || args?.key || args?.keys;
        if (shortcut) {
          manager.sendActionPreview(hwnd, 'shortcut', {
            shortcut: Array.isArray(shortcut) ? shortcut.join('+') : shortcut,
          });
        }
      }
      break;
      
    case 'scroll':
    case 'scroll_to':
      if (validHwnd) {
        manager.sendActionPreview(hwnd, 'scroll', {
          direction: args?.direction || 'down',
          amount: args?.amount || args?.distance || 100,
        });
      }
      break;
      
    case 'drag':
    case 'drag_and_drop':
      if (validHwnd && args) {
        const from = args.from || args.start || coordinates;
        const to = args.to || args.end;
        if (from && to) {
          // 显示拖拽轨迹
          manager.sendActionPreview(hwnd, 'mouse-trajectory', {
            from: { x: from.x, y: from.y },
            to: { x: to.x, y: to.y },
          });
        }
      }
      break;
      
    case 'window_move':
    case 'window_resize':
    case 'window_close':
    case 'window_maximize':
    case 'window_minimize':
      if (validHwnd) {
        manager.sendActionPreview(hwnd, 'window-action', {
          action: tool_name.replace('window_', ''),
          label: TOOL_LABELS[tool_name] || tool_name,
        });
      }
      break;
      
    case 'open_application':
    case 'open_file':
    case 'open_url':
      // 这些操作可能没有 hwnd
      if (validHwnd) {
        manager.sendActionPreview(hwnd, 'window-action', {
          action: 'open',
          label: `${TOOL_LABELS[tool_name]}: ${args?.path || args?.url || args?.name || ''}`,
        });
      } else {
        // 无 hwnd：发送 renderer 侧提示
        const target = args?.path || args?.url || args?.name || '';
        sendRendererToast(`${TOOL_LABELS[tool_name]}: ${target}`);
      }
      break;
      
    case 'copy':
    case 'paste':
    case 'cut':
    case 'select_all':
      if (validHwnd) {
        manager.sendActionPreview(hwnd, 'shortcut', {
          shortcut: `Ctrl+${tool_name === 'copy' ? 'C' : tool_name === 'paste' ? 'V' : tool_name === 'cut' ? 'X' : 'A'}`,
        });
      }
      break;
      
    default:
      // 未知但可能需要预览的工具：发送默认提示
      if (TOOLS_WITH_PREVIEW.has(tool_name)) {
        console.warn(`[Preview] Unhandled preview tool: ${tool_name}`);
      }
      // 对于有 hwnd 的未知工具，发送通用操作提示
      if (validHwnd) {
        manager.sendActionPreview(hwnd, 'window-action', {
          action: 'generic',
          label: `执行: ${TOOL_LABELS[tool_name] || tool_name}`,
        });
      } else {
        // 无 hwnd 的未知工具：发送 renderer 侧提示
        sendRendererToast(`执行: ${TOOL_LABELS[tool_name] || tool_name}`);
      }
      break;
  }
}

/**
 * 预览类型白名单说明（维护指南）
 * ========================================
 * 当新增预览类型时，需同步更新以下位置：
 * 
 * 1. multi-overlay-manager.js:
 *    - MultiOverlayManager.ALLOWED_PREVIEW_TYPES (静态集合)
 * 
 * 2. multi-overlay-manager.js (_generateOverlayHTML):
 *    - ipcRenderer.on('preview:新类型', ...) 事件监听
 *    - 对应的 create*Preview() 渲染函数
 *    - 相关 CSS 动画样式
 * 
 * 3. agent-ipc.js (handleToolEventForPreview):
 *    - switch case 中添加对应工具名处理
 *    - 调用 manager.sendActionPreview(hwnd, '新类型', data)
 * 
 * 当前支持的预览类型：
 * - mouse-trajectory: 鼠标移动轨迹（虚线）
 * - click: 点击涟漪效果
 * - typing: 输入文字预览
 * - target: 目标位置指示器
 * - scroll: 滚动方向指示
 * - shortcut: 快捷键显示
 * - window-action: 窗口操作提示
 * - clear: 清除所有预览
 */

module.exports = {
  registerAgentIpcHandlers,
  unregisterAgentIpcHandlers,
  isValidUUID,
  validateTask,
  validateHwnds,
  handleToolEventForPreview,
};
