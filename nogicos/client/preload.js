/**
 * NogicOS Preload Script
 * 
 * 安全地暴露 Electron API 给渲染进程
 * 遵循 contextIsolation 最佳实践
 */

const { contextBridge, ipcRenderer } = require('electron');

// 暴露窗口控制 API
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
});
