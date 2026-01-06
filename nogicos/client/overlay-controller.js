/**
 * NogicOS Overlay Controller
 * 
 * 使用 electron-overlay-window 实现流畅的窗口追踪 Overlay
 * 核心体验：连接时在目标应用上显示状态条
 */

const { BrowserWindow, ipcMain } = require('electron');
const path = require('path');

// 尝试加载 electron-overlay-window
let OverlayController = null;
let OVERLAY_WINDOW_OPTS = {};

try {
  const overlayLib = require('electron-overlay-window');
  OverlayController = overlayLib.OverlayController;
  OVERLAY_WINDOW_OPTS = overlayLib.OVERLAY_WINDOW_OPTS;
  console.log('[OverlayController] electron-overlay-window loaded successfully');
} catch (e) {
  console.warn('[OverlayController] electron-overlay-window not available:', e.message);
}

/**
 * Overlay 状态
 */
const OverlayState = {
  IDLE: 'idle',
  ATTACHING: 'attaching',
  ATTACHED: 'attached',
  ERROR: 'error',
};

/**
 * NogicOS Overlay Manager
 * 管理连接到外部应用的 Overlay 窗口
 */
class NogicOSOverlayManager {
  constructor() {
    this._overlayWindow = null;
    this._state = OverlayState.IDLE;
    this._targetTitle = null;
    this._hookType = null;
    this._eventListeners = [];
  }

  /**
   * 获取当前状态
   */
  get state() {
    return this._state;
  }

  /**
   * 检查 overlay 功能是否可用
   */
  get isAvailable() {
    return OverlayController !== null;
  }

  /**
   * 创建并附加 Overlay 到目标窗口
   * @param {string} targetTitle - 目标窗口标题（精确匹配）
   * @param {string} hookType - Hook 类型 (browser, desktop, file)
   * @param {object} options - 配置选项
   */
  attach(targetTitle, hookType, options = {}) {
    if (!this.isAvailable) {
      console.error('[OverlayManager] electron-overlay-window not available');
      return { success: false, error: 'Overlay library not available' };
    }

    // 【关键修复】electron-overlay-window 只能初始化一次
    // 如果已经初始化，只显示现有窗口而不重新 attach
    // 【修复 #2】检查 isInitialized 是否为 null
    if (OverlayController && OverlayController.isInitialized) {
      console.log('[OverlayManager] Already initialized, reusing existing overlay');
      // [P0 FIX Round 2] Removed hardcoded debug log - security risk
      
      if (this._overlayWindow && !this._overlayWindow.isDestroyed()) {
        // 恢复 overlay 状态（之前 detach 时隐藏了）
        this._hookType = hookType;
        this._targetTitle = targetTitle;
        
        // 1. 恢复透明度
        this._overlayWindow.setOpacity(1);
        
        // 2. 获取当前位置（诊断用）
        const currentBounds = this._overlayWindow.getBounds();
        // [P0 FIX Round 2] Removed hardcoded debug log
        
        // 3. 重新加载 overlay 内容
        const overlayHTML = this._generateOverlayHTML(hookType, targetTitle);
        this._overlayWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(overlayHTML)}`);
        
        // 4. 显示窗口（位置由 electron-overlay-window 自动同步）
        this._overlayWindow.showInactive();
        
        this._state = OverlayState.ATTACHED;
        // 音效会在 HTML 加载后自动播放
        console.log('[OverlayManager] Overlay reused, bounds:', currentBounds);
        return { success: true, reused: true };
      } else {
        console.warn('[OverlayManager] Overlay window destroyed, cannot reattach');
        return { success: false, error: 'Overlay window destroyed, restart app to reconnect' };
      }
    }

    this._state = OverlayState.ATTACHING;
    this._targetTitle = targetTitle;
    this._hookType = hookType;
    this._hasPlayedSound = false; // 重置音效标志

    try {
      // 创建 Overlay 窗口
      this._overlayWindow = new BrowserWindow({
        width: 400,
        height: 36,
        webPreferences: {
          nodeIntegration: false,
          contextIsolation: true,
        },
        ...OVERLAY_WINDOW_OPTS,
      });

      // 加载 Overlay UI
      const overlayHTML = this._generateOverlayHTML(hookType, targetTitle);
      this._overlayWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(overlayHTML)}`);
      
      // 【方案 B】阻止 Overlay 在失去焦点时隐藏
      // 覆盖 hide 方法，让它什么都不做
      const originalHide = this._overlayWindow.hide.bind(this._overlayWindow);
      this._overlayWindow.hide = () => {
        // 不隐藏，保持始终可见
        console.log('[OverlayManager] Blocked hide() - keeping overlay visible');
      };
      // 保存原始方法，用于真正需要隐藏时（如 detach）
      this._overlayWindow._originalHide = originalHide;

      // 【修复 #1】保存 detach 方法用于恢复
      this._overlayWindow._restoreHide = () => {
        this._overlayWindow.hide = originalHide;
      };

      // 附加到目标窗口
      OverlayController.attachByTitle(this._overlayWindow, targetTitle, {
        hasTitleBarOnMac: true,
      });

      // 监听事件
      this._setupEventListeners();

      console.log(`[OverlayManager] Attaching to "${targetTitle}" for ${hookType}`);
      
      // 【修复】立即显示 Overlay 并播放音效，不等待 focus 事件
      setTimeout(() => {
        if (this._overlayWindow && !this._overlayWindow.isDestroyed()) {
          this._overlayWindow.showInactive();
          this.playSound('connect');
          console.log('[OverlayManager] Overlay shown and sound played after attach');
        }
      }, 100);
      
      return { success: true };
    } catch (e) {
      console.error('[OverlayManager] Failed to attach:', e);
      this._state = OverlayState.ERROR;
      return { success: false, error: e.message };
    }
  }

  /**
   * 分离 Overlay（隐藏但不销毁，因为 electron-overlay-window 只能初始化一次）
   */
  detach() {
    // [P0 FIX Round 2] Removed hardcoded debug log path

    if (this._overlayWindow && !this._overlayWindow.isDestroyed()) {
      try {
        // 【重要】不能销毁窗口！electron-overlay-window 的 native 代码会崩溃
        // 解决方案：只设置透明，不移动位置（保持位置同步）

        // 1. 设置窗口完全透明（隐藏但保持位置追踪）
        this._overlayWindow.setOpacity(0);
        
        // 2. 清空 HTML 内容（视觉上消失）
        this._overlayWindow.webContents.executeJavaScript(`
          document.body.innerHTML = '';
          document.body.style.background = 'transparent';
        `).catch(() => {});
        
        // 3. 播放断开音效
        this.playSound('disconnect');
        
        // 【关键】不移动位置！让 electron-overlay-window 继续追踪目标窗口
        // 这样重新连接时位置仍然正确
        
      } catch (e) {
        console.warn('[OverlayManager] Error hiding overlay:', e);
      }
    }
    
    this._state = OverlayState.IDLE;
    // 不清除 targetTitle，保留以便库继续追踪（避免崩溃）
    this._hookType = null;
    this._hasPlayedSound = false;
    // 不移除事件监听器（避免崩溃）
    
    console.log('[OverlayManager] Detached (overlay hidden, not destroyed)');
    return { success: true };
  }

  /**
   * 更新 Overlay 显示内容
   * @param {string} message - 显示的消息
   * @param {string} status - 状态 (connected, working, error)
   */
  updateContent(message, status = 'connected') {
    if (!this._overlayWindow) return;

    this._overlayWindow.webContents.executeJavaScript(`
      updateOverlay("${message}", "${status}");
    `).catch(() => {});
  }

  /**
   * 播放音效
   * @param {string} soundType - 音效类型 (connect, disconnect, action)
   */
  playSound(soundType = 'connect') {
    if (!this._overlayWindow) return;

    this._overlayWindow.webContents.executeJavaScript(`
      playSound("${soundType}");
    `).catch(() => {});
  }

  /**
   * 设置事件监听器
   */
  _setupEventListeners() {
    if (!OverlayController) return;

    const onAttach = (e) => {
      console.log('[OverlayManager] Attached to target window, bounds:', e);
      this._state = OverlayState.ATTACHED;
      
      // 检查 bounds 是否有效
      if (e && e.width > 0 && e.height > 0) {
        console.log('[OverlayManager] Valid bounds received, overlay positioned correctly');
      } else {
        console.log('[OverlayManager] Invalid bounds, target window position unknown');
      }
      
      // 音效在 attach() 方法中播放，这里不重复播放
    };

    const onDetach = () => {
      console.log('[OverlayManager] Detached from target window');
      this._state = OverlayState.IDLE;
    };

    const onBlur = () => {
      console.log('[OverlayManager] Target window lost focus (overlay stays visible)');
      // hide() 已被覆盖，不需要额外处理
    };

    const onFocus = () => {
      console.log('[OverlayManager] Target window gained focus');
    };

    OverlayController.events.on('attach', onAttach);
    OverlayController.events.on('detach', onDetach);
    OverlayController.events.on('blur', onBlur);
    OverlayController.events.on('focus', onFocus);

    this._eventListeners = [
      { event: 'attach', handler: onAttach },
      { event: 'detach', handler: onDetach },
      { event: 'blur', handler: onBlur },
      { event: 'focus', handler: onFocus },
    ];
  }

  /**
   * 移除事件监听器
   */
  _removeEventListeners() {
    if (!OverlayController) return;

    this._eventListeners.forEach(({ event, handler }) => {
      OverlayController.events.removeListener(event, handler);
    });
    this._eventListeners = [];
  }

  /**
   * 生成 Overlay HTML
   */
  _generateOverlayHTML(hookType, targetTitle) {
    const icons = {
      browser: '🌐',
      desktop: '🖥️',
      file: '📁',
    };

    const colors = {
      connected: '#10b981',  // emerald-500
      working: '#f59e0b',    // amber-500
      error: '#ef4444',      // red-500
    };

    return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    html, body {
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: transparent;
      -webkit-app-region: no-drag;
    }
    
    .overlay-container {
      position: absolute;
      top: 0;
      left: 8px;
      right: 8px;
      height: 32px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 12px;
      background: rgba(16, 185, 129, 0.95);
      border-radius: 0 0 8px 8px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 12px;
      color: #fff;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      transform: translateY(-100%);
      animation: slideIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
    }
    
    @keyframes slideIn {
      from {
        transform: translateY(-100%);
        opacity: 0;
      }
      to {
        transform: translateY(0);
        opacity: 1;
      }
    }
    
    @keyframes slideOut {
      from {
        transform: translateY(0);
        opacity: 1;
      }
      to {
        transform: translateY(-100%);
        opacity: 0;
      }
    }
    
    .overlay-container.hiding {
      animation: slideOut 0.2s ease-in forwards;
    }
    
    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #fff;
      animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.7; transform: scale(0.9); }
    }
    
    .status-indicator.working {
      animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    
    .icon {
      font-size: 14px;
    }
    
    .label {
      font-weight: 500;
      letter-spacing: 0.3px;
      flex: 1;
    }
    
    .logo {
      font-weight: 700;
      font-size: 11px;
      opacity: 0.8;
    }
    
    /* 状态颜色 */
    .overlay-container.connected { background: rgba(16, 185, 129, 0.95); }
    .overlay-container.working { background: rgba(245, 158, 11, 0.95); }
    .overlay-container.error { background: rgba(239, 68, 68, 0.95); }
  </style>
</head>
<body>
  <div id="overlay" class="overlay-container connected">
    <div class="status-indicator"></div>
    <span class="icon">${icons[hookType] || '🔗'}</span>
    <span class="label" id="message">NogicOS Connected</span>
    <span class="logo">NogicOS</span>
  </div>
  
  <script>
    // 音效 (Web Audio API)
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
    function playSound(type) {
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      if (type === 'connect') {
        // 连接音效：上升音调
        oscillator.frequency.setValueAtTime(400, audioContext.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(800, audioContext.currentTime + 0.1);
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.15);
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.15);
      } else if (type === 'disconnect') {
        // 断开音效：下降音调
        oscillator.frequency.setValueAtTime(600, audioContext.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(300, audioContext.currentTime + 0.15);
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.2);
      } else if (type === 'action') {
        // 操作音效：短促点击
        oscillator.frequency.setValueAtTime(1000, audioContext.currentTime);
        gainNode.gain.setValueAtTime(0.2, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.05);
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.05);
      }
    }
    
    function updateOverlay(message, status) {
      const overlay = document.getElementById('overlay');
      const messageEl = document.getElementById('message');
      
      messageEl.textContent = message;
      overlay.className = 'overlay-container ' + status;
      
      // 更新 indicator 动画
      const indicator = overlay.querySelector('.status-indicator');
      if (status === 'working') {
        indicator.classList.add('working');
      } else {
        indicator.classList.remove('working');
      }
    }
    
    function hideOverlay() {
      const overlay = document.getElementById('overlay');
      overlay.classList.add('hiding');
    }
    
    // 初始化时播放连接音效
    setTimeout(() => playSound('connect'), 300);
  </script>
</body>
</html>
    `;
  }
}

// 单例实例
let overlayManager = null;

/**
 * 获取 OverlayManager 单例
 */
function getOverlayManager() {
  if (!overlayManager) {
    overlayManager = new NogicOSOverlayManager();
  }
  return overlayManager;
}

/**
 * 设置 Overlay IPC handlers
 */
function setupOverlayIPC() {
  // 附加 overlay 到目标窗口
  ipcMain.handle('overlay:attach', async (event, { targetTitle, hookType }) => {
    const manager = getOverlayManager();
    return manager.attach(targetTitle, hookType);
  });

  // 分离 overlay
  ipcMain.handle('overlay:detach', async () => {
    const manager = getOverlayManager();
    return manager.detach();
  });

  // 更新 overlay 内容
  ipcMain.handle('overlay:update', async (event, { message, status }) => {
    const manager = getOverlayManager();
    manager.updateContent(message, status);
    return { success: true };
  });

  // 播放音效
  ipcMain.handle('overlay:sound', async (event, { soundType }) => {
    const manager = getOverlayManager();
    manager.playSound(soundType);
    return { success: true };
  });

  // 获取状态
  ipcMain.handle('overlay:status', async () => {
    const manager = getOverlayManager();
    return {
      available: manager.isAvailable,
      state: manager.state,
      targetTitle: manager._targetTitle,
      hookType: manager._hookType,
    };
  });

  console.log('[OverlayController] IPC handlers registered');
}

module.exports = {
  NogicOSOverlayManager,
  getOverlayManager,
  setupOverlayIPC,
  OverlayState,
};

