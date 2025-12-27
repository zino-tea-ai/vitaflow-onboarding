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
});

console.log('[NogicOS] Preload script loaded');
