/**
 * NogicOS Preload Script
 * 
 * Secure bridge between Electron renderer and main process.
 * Exposes safe APIs to the renderer via contextBridge.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose safe APIs to renderer
contextBridge.exposeInMainWorld('nogicos', {
  // Version info
  version: '1.0.0',
  
  // === Window Control (for custom title bar) ===
  windowMinimize: () => ipcRenderer.invoke('window-minimize'),
  windowMaximize: () => ipcRenderer.invoke('window-maximize'),
  windowClose: () => ipcRenderer.invoke('window-close'),
  windowIsMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  
  // Listen for maximize state changes
  onWindowMaximizeChange: (callback) => {
    ipcRenderer.on('window-maximize-change', (_event, isMaximized) => callback(isMaximized));
  },
  
  // Status updates from Python via WebSocket
  onStatusUpdate: (callback) => {
    ipcRenderer.on('status-update', (_event, data) => callback(data));
  },
  
  // Remove status listener
  offStatusUpdate: () => {
    ipcRenderer.removeAllListeners('status-update');
  },
  
  // Send command to Python
  sendCommand: (command, args) => {
    return ipcRenderer.invoke('send-command', { command, args });
  },
  
  // Get current status
  getStatus: () => {
    return ipcRenderer.invoke('get-status');
  },
  
  // Navigate webview
  navigate: (url) => {
    return ipcRenderer.invoke('navigate', url);
  },
  
  // WebSocket connection status
  onConnectionChange: (callback) => {
    ipcRenderer.on('ws-connection', (_event, connected) => callback(connected));
  },
  
  // Knowledge store stats
  onKnowledgeUpdate: (callback) => {
    ipcRenderer.on('knowledge-update', (_event, stats) => callback(stats));
  },
  
  // === Task Execution ===
  
  // Execute AI task
  executeTask: (task, url, options = {}) => {
    return ipcRenderer.invoke('execute-task', { task, url, ...options });
  },
  
  // Get stats
  getStats: () => {
    return ipcRenderer.invoke('get-stats');
  },
  
  // === AI View Control ===
  
  // Show AI view (in preview panel)
  showAiView: () => {
    return ipcRenderer.invoke('show-ai-view');
  },
  
  // Hide AI view
  hideAiView: () => {
    return ipcRenderer.invoke('hide-ai-view');
  },
  
  // Get current AI view URL
  getAiViewUrl: () => {
    return ipcRenderer.invoke('get-ai-view-url');
  },
  
  // Listen for AI view visibility changes
  onAiViewVisibleChange: (callback) => {
    ipcRenderer.on('ai-view-visible', (_event, data) => callback(data));
  },
  
  // === Screenshot Stream (Option B) ===
  
  // Receive AI operation frames
  onAiFrame: (callback) => {
    ipcRenderer.on('ai-frame', (_event, data) => callback(data));
  },
  
  // Stop receiving AI frames
  offAiFrame: () => {
    ipcRenderer.removeAllListeners('ai-frame');
  },
  
  // === Python Process ===
  
  // Python log output
  onPythonLog: (callback) => {
    ipcRenderer.on('python-log', (_event, log) => callback(log));
  },
  
  // Python status
  onPythonStatus: (callback) => {
    ipcRenderer.on('python-status', (_event, status) => callback(status));
  },
});

console.log('[NogicOS] Preload script loaded - API v2.0');
