/**
 * NogicOS Preload Script
 * 
 * 安全地暴露 Electron API 给渲染进程
 */

const { contextBridge, ipcRenderer } = require('electron');

// 暴露窗口控制 API
contextBridge.exposeInMainWorld('electronAPI', {
  // 窗口控制
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  
  // 平台信息
  platform: process.platform,
  
  // 检测是否在 Electron 中运行
  isElectron: true,
});

console.log('[NogicOS] Preload script loaded');
