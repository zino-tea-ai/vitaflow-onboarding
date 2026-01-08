/**
 * NogicOS Preload Script
 * 
 * 安全地暴露 Electron API 给渲染进程
 * 遵循 contextIsolation 最佳实践
 * 
 * Phase 7: 添加 agentAPI 支持
 */

const { contextBridge, ipcRenderer } = require('electron');

// ============================================================================
// electronAPI - 基础窗口控制 API
// ============================================================================
contextBridge.exposeInMainWorld('electronAPI', {
  // ============== 窗口控制 ==============
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  
  // ============== 平台信息 ==============
  platform: process.platform,
  isElectron: true,
  
  // ============== 事件监听 ==============
  // 监听新建会话
  onNewSession: (callback) => {
    ipcRenderer.on('new-session', () => callback());
    // 返回清理函数
    return () => ipcRenderer.removeAllListeners('new-session');
  },
  
  // 监听命令面板切换
  onToggleCommandPalette: (callback) => {
    ipcRenderer.on('toggle-command-palette', () => callback());
    return () => ipcRenderer.removeAllListeners('toggle-command-palette');
  },
  
  // ============== 主进程通信 ==============
  // 触发命令面板
  toggleCommandPalette: () => ipcRenderer.send('toggle-command-palette'),
  
  // ============== Overlay 控制 (新版 electron-overlay-window) ==============
  // 显示连接状态 overlay（优先追踪目标窗口，回退系统通知）
  showConnectionOverlay: (hookType, target, hwnd = 0) => 
    ipcRenderer.invoke('overlay:show-connection', { hookType, target, targetHwnd: hwnd }),
  
  // 隐藏连接状态 overlay
  hideConnectionOverlay: (hookType) => 
    ipcRenderer.invoke('overlay:hide-connection', { hookType }),
  
  // 显示连接通知（仅通知，不追踪）
  showConnectionNotification: (hookType, target) =>
    ipcRenderer.invoke('notification:show', { 
      title: `NogicOS Connected`, 
      body: `Now monitoring: ${hookType} (${target})` 
    }),
  
  // ============== 新版 Overlay API ==============
  // 附加 overlay 到目标窗口（通过标题匹配）
  attachOverlay: (targetTitle, hookType) =>
    ipcRenderer.invoke('overlay:attach', { targetTitle, hookType }),
  
  // 分离 overlay
  detachOverlay: () =>
    ipcRenderer.invoke('overlay:detach'),
  
  // 更新 overlay 内容
  updateOverlay: (message, status) =>
    ipcRenderer.invoke('overlay:update', { message, status }),
  
  // 播放音效
  playOverlaySound: (soundType) =>
    ipcRenderer.invoke('overlay:sound', { soundType }),
  
  // 获取 overlay 状态
  getOverlayStatus: () =>
    ipcRenderer.invoke('overlay:status'),
  
  // ============== 拖拽连接器 API ==============
  // 开始拖拽连接器模式
  startDragConnector: () =>
    ipcRenderer.invoke('drag-connector:start'),
  
  // 结束拖拽连接器模式（返回目标窗口信息）
  endDragConnector: () =>
    ipcRenderer.invoke('drag-connector:end'),
  
  // 监听拖拽过程中的窗口信息更新
  onDragConnectorUpdate: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('drag-connector:update', handler);
    return () => ipcRenderer.removeListener('drag-connector:update', handler);
  },
  
  // 监听拖拽完成事件（鼠标释放时自动触发）
  onDragConnectorComplete: (callback) => {
    const handler = (event, target) => callback(target);
    ipcRenderer.on('drag-connector:complete', handler);
    return () => ipcRenderer.removeListener('drag-connector:complete', handler);
  },
  
  // ============== 多窗口 Overlay API (新版) ==============
  // 创建 Overlay（支持多窗口）
  createMultiOverlay: (hwnd, hookType, targetTitle) =>
    ipcRenderer.invoke('multi-overlay:create', { hwnd, hookType, targetTitle }),
  
  // 显示指定 Overlay
  showMultiOverlay: (hwnd) =>
    ipcRenderer.invoke('multi-overlay:show', { hwnd }),
  
  // 隐藏指定 Overlay
  hideMultiOverlay: (hwnd) =>
    ipcRenderer.invoke('multi-overlay:hide', { hwnd }),
  
  // 销毁指定 Overlay
  destroyMultiOverlay: (hwnd) =>
    ipcRenderer.invoke('multi-overlay:destroy', { hwnd }),
  
  // 销毁所有 Overlay
  destroyAllMultiOverlays: () =>
    ipcRenderer.invoke('multi-overlay:destroy-all'),
  
  // 获取指定 Overlay 状态
  getMultiOverlayStatus: (hwnd) =>
    ipcRenderer.invoke('multi-overlay:status', { hwnd }),
  
  // 列出所有活跃的 Overlay
  listMultiOverlays: () =>
    ipcRenderer.invoke('multi-overlay:list'),
  
  // Phase 2: 开始位置跟踪
  startMultiOverlayTracking: (hwnd) =>
    ipcRenderer.invoke('multi-overlay:start-tracking', { hwnd }),
  
  // Phase 2: 停止位置跟踪
  stopMultiOverlayTracking: (hwnd) =>
    ipcRenderer.invoke('multi-overlay:stop-tracking', { hwnd }),

  // Phase 7: 设置活跃窗口（多窗口焦点管理）
  setActiveOverlay: (hwnd) =>
    ipcRenderer.invoke('multi-overlay:set-active', { hwnd }),

  // Phase 7: 循环切换活跃窗口
  cycleActiveOverlay: () =>
    ipcRenderer.invoke('multi-overlay:cycle-active'),

  // Phase 7: 发送动作预览到指定 Overlay
  sendOverlayPreview: (hwnd, previewType, data) =>
    ipcRenderer.invoke('multi-overlay:preview', { hwnd, previewType, data }),

  // Phase 7: 清除所有动作预览
  clearOverlayPreviews: () =>
    ipcRenderer.invoke('multi-overlay:clear-previews'),
});

// ============================================================================
// agentAPI - Agent 控制 API (Phase 7)
// ⚠️ 安全要求：使用 contextBridge 包装，永不直接暴露 ipcRenderer
// ============================================================================
contextBridge.exposeInMainWorld('agentAPI', {
  // ============== Agent 控制 ==============
  
  /**
   * 启动任务
   * @param {string} task - 任务描述
   * @param {number[]} targetHwnds - 目标窗口句柄数组
   * @returns {Promise<{taskId: string}>}
   */
  startTask: (task, targetHwnds) => 
    ipcRenderer.invoke('agent:start', { task, targetHwnds }),
  
  /**
   * 停止任务
   * @param {string} taskId - 任务 ID
   */
  stopTask: (taskId) => 
    ipcRenderer.invoke('agent:stop', { taskId }),
  
  /**
   * 恢复任务
   * @param {string} taskId - 任务 ID
   */
  resumeTask: (taskId) => 
    ipcRenderer.invoke('agent:resume', { taskId }),

  // ============== 状态订阅 ==============
  
  /**
   * 订阅 Agent 事件（安全的单向推送）
   * @param {Function} callback - 事件回调
   * @returns {Function} 取消订阅函数
   */
  onAgentEvent: (callback) => {
    // ⚠️ 重要：不传递原始 event 对象，只传递 data
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('agent:event', handler);
    return () => ipcRenderer.removeListener('agent:event', handler);
  },
  
  /**
   * 订阅批量事件（性能优化）
   * @param {Function} callback - 批量事件回调
   * @returns {Function} 取消订阅函数
   */
  onBatchEvents: (callback) => {
    const handler = (_event, events) => callback(events);
    ipcRenderer.on('agent:event:batch', handler);
    return () => ipcRenderer.removeListener('agent:event:batch', handler);
  },

  // ============== 用户确认 ==============
  
  /**
   * 响应敏感操作确认
   * @param {string} taskId - 任务 ID
   * @param {string} actionId - 操作 ID
   * @param {boolean} approved - 是否批准
   */
  confirmSensitiveAction: (taskId, actionId, approved) =>
    ipcRenderer.invoke('agent:confirm', { taskId, actionId, approved }),

  // ============== 状态查询 ==============
  
  /**
   * 获取任务状态
   * @param {string} taskId - 任务 ID
   */
  getTaskStatus: (taskId) =>
    ipcRenderer.invoke('agent:status', { taskId }),
  
  /**
   * 获取所有活跃任务
   */
  getActiveTasks: () =>
    ipcRenderer.invoke('agent:active-tasks'),

  // ============== Overlay 动作预览 ==============
  
  /**
   * 订阅动作预览事件
   * @param {Function} callback - 预览事件回调
   * @returns {Function} 取消订阅函数
   */
  onActionPreview: (callback) => {
    const channels = [
      'preview:mouse-trajectory',
      'preview:click',
      'preview:typing',
      'preview:target',
      'preview:scroll',
      'preview:shortcut',
      'preview:window-action',
      'preview:clear',
    ];
    
    const handlers = channels.map(channel => {
      const handler = (_event, data) => callback({ type: channel, data });
      ipcRenderer.on(channel, handler);
      return { channel, handler };
    });
    
    return () => {
      handlers.forEach(({ channel, handler }) => {
        ipcRenderer.removeListener(channel, handler);
      });
    };
  },

  // ============== 窗口焦点管理 ==============
  
  /**
   * 订阅窗口焦点变化
   * @param {Function} callback - 焦点变化回调
   * @returns {Function} 取消订阅函数
   */
  onFocusChange: (callback) => {
    const activeHandler = (_event) => callback({ active: true });
    const inactiveHandler = (_event) => callback({ active: false });
    
    ipcRenderer.on('focus:active', activeHandler);
    ipcRenderer.on('focus:inactive', inactiveHandler);
    
    return () => {
      ipcRenderer.removeListener('focus:active', activeHandler);
      ipcRenderer.removeListener('focus:inactive', inactiveHandler);
    };
  },
});
