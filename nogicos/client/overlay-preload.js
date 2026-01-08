/**
 * Overlay Preload Script
 * Phase 7: 安全地暴露 IPC 事件监听给 Overlay 渲染进程
 * 
 * 遵循 Electron 安全最佳实践：
 * - nodeIntegration: false
 * - contextIsolation: true
 * - 只暴露必要的、受限的 API
 */

const { contextBridge, ipcRenderer } = require('electron');

// 允许的预览事件频道（白名单）
const ALLOWED_PREVIEW_CHANNELS = [
  'preview:click',
  'preview:target',
  'preview:typing',
  'preview:shortcut',
  'preview:scroll',
  'preview:mouse-trajectory',
  'preview:window-action',
  'preview:clear',
];

// 允许的焦点事件频道
const ALLOWED_FOCUS_CHANNELS = [
  'focus:active',
  'focus:inactive',
];

/**
 * 安全地暴露 Overlay API
 */
contextBridge.exposeInMainWorld('overlayAPI', {
  /**
   * 订阅预览事件
   * @param {string} channel - 频道名（必须在白名单中）
   * @param {function} callback - 回调函数（只接收 data，不暴露 event 对象）
   * @returns {function} 取消订阅函数
   */
  onPreview: (channel, callback) => {
    // 验证频道是否在白名单中
    if (!ALLOWED_PREVIEW_CHANNELS.includes(channel)) {
      console.warn(`[OverlayPreload] Blocked subscription to unauthorized channel: ${channel}`);
      return () => {};
    }
    
    // 包装回调，只传递 data，不暴露 event 对象
    const wrappedCallback = (_event, data) => {
      try {
        callback(data);
      } catch (e) {
        console.error(`[OverlayPreload] Callback error for ${channel}:`, e);
      }
    };
    
    ipcRenderer.on(channel, wrappedCallback);
    
    // 返回取消订阅函数
    return () => {
      ipcRenderer.removeListener(channel, wrappedCallback);
    };
  },
  
  /**
   * 订阅焦点事件
   * @param {string} channel - 频道名（focus:active 或 focus:inactive）
   * @param {function} callback - 回调函数
   * @returns {function} 取消订阅函数
   */
  onFocus: (channel, callback) => {
    if (!ALLOWED_FOCUS_CHANNELS.includes(channel)) {
      console.warn(`[OverlayPreload] Blocked subscription to unauthorized focus channel: ${channel}`);
      return () => {};
    }
    
    const wrappedCallback = () => {
      try {
        callback();
      } catch (e) {
        console.error(`[OverlayPreload] Focus callback error for ${channel}:`, e);
      }
    };
    
    ipcRenderer.on(channel, wrappedCallback);
    
    return () => {
      ipcRenderer.removeListener(channel, wrappedCallback);
    };
  },
  
  /**
   * 一次性订阅所有预览事件（便捷方法）
   * @param {object} handlers - { click, target, typing, shortcut, scroll, mouseTrajectory, windowAction, clear }
   * @returns {function} 取消所有订阅的函数
   */
  onAllPreviews: (handlers) => {
    const unsubscribes = [];
    
    const channelMap = {
      'preview:click': handlers.click,
      'preview:target': handlers.target,
      'preview:typing': handlers.typing,
      'preview:shortcut': handlers.shortcut,
      'preview:scroll': handlers.scroll,
      'preview:mouse-trajectory': handlers.mouseTrajectory,
      'preview:window-action': handlers.windowAction,
      'preview:clear': handlers.clear,
    };
    
    for (const [channel, handler] of Object.entries(channelMap)) {
      if (typeof handler === 'function') {
        const wrappedCallback = (_event, data) => {
          try {
            handler(data);
          } catch (e) {
            console.error(`[OverlayPreload] Handler error for ${channel}:`, e);
          }
        };
        ipcRenderer.on(channel, wrappedCallback);
        unsubscribes.push(() => ipcRenderer.removeListener(channel, wrappedCallback));
      }
    }
    
    return () => unsubscribes.forEach(unsub => unsub());
  },
});

console.log('[OverlayPreload] Initialized with secure IPC bridge');
