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
});

console.log('[NogicOS] Preload script loaded');
