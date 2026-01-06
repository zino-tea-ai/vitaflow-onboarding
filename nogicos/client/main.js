/**
 * NogicOS Desktop Client
 * 
 * 加载 nogicos-ui React 前端作为桌面应用
 * 支持开发模式（Vite dev server）和生产模式（dist 文件）
 * 
 * Features:
 * - 全局快捷键唤醒 (Cmd/Ctrl+Space)
 * - 系统托盘
 * - 单实例锁定
 * - 窗口状态记忆
 */

const { app, BrowserWindow, ipcMain, globalShortcut, Tray, Menu, nativeImage, session } = require('electron');
const path = require('path');
const fs = require('fs');

// Overlay Manager (新版 - 使用 electron-overlay-window)
let overlayController = null;
try {
  overlayController = require('./overlay-controller');
  console.log('[Main] OverlayController loaded');
} catch (e) {
  console.log('[Main] OverlayController not available:', e.message);
}

// 旧版 Overlay (兼容)
let overlayModule = null;
try {
  overlayModule = require('./overlay');
} catch (e) {
  // 旧版可选
}

// 拖拽连接器模块
let dragConnector = null;
try {
  dragConnector = require('./drag-connector');
  console.log('[Main] DragConnector loaded');
} catch (e) {
  console.log('[Main] DragConnector not available:', e.message);
}

// 多窗口 Overlay 管理器（新版）
let multiOverlayManager = null;
try {
  multiOverlayManager = require('./multi-overlay-manager');
  console.log('[Main] MultiOverlayManager loaded');
} catch (e) {
  console.log('[Main] MultiOverlayManager not available:', e.message);
}

// 配置
const DEV_SERVER_URL = process.env.DEV_SERVER_URL || 'http://localhost:5173';
const IS_DEV = process.env.NODE_ENV === 'development' || !app.isPackaged;
const CONFIG_PATH = path.join(app.getPath('userData'), 'window-state.json');

let mainWindow = null;
let tray = null; // 必须全局变量，否则会被 GC

// ============== 单实例锁定 ==============
const gotLock = app.requestSingleInstanceLock();

if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    // 第二个实例启动时，聚焦已有窗口
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// ============== 窗口状态记忆 ==============
function loadWindowState() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
    }
  } catch (e) {
    // Silently ignore load errors
  }
  return { width: 1400, height: 900 };
}

function saveWindowState() {
  if (!mainWindow) return;
  try {
    const bounds = mainWindow.getBounds();
    const isMaximized = mainWindow.isMaximized();
    fs.writeFileSync(CONFIG_PATH, JSON.stringify({ ...bounds, isMaximized }));
  } catch (e) {
    // Silently ignore save errors
  }
}

// ============== Node.js 版本检查 ==============
function checkNodeVersion() {
  const [major] = process.versions.node.split('.').map(Number);
  const MIN_NODE_VERSION = 18;
  if (major < MIN_NODE_VERSION) {
    console.error(`[Main] Node.js ${MIN_NODE_VERSION}+ required, found ${process.versions.node}`);
    return false;
  }
  return true;
}

// 启动时检查 Node.js 版本
if (!checkNodeVersion()) {
  app.quit();
}

// ============== 检查开发服务器 ==============
async function checkDevServer() {
  try {
    const response = await fetch(DEV_SERVER_URL, { method: 'HEAD' });
    return response.ok;
  } catch {
    return false;
  }
}

// ============== 创建托盘图标 ==============
function createTray() {
  // 尝试加载自定义图标，如果没有则使用默认
  const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');
  if (fs.existsSync(iconPath)) {
    tray = new Tray(iconPath);
  } else {
    // 创建一个简单的图标
    tray = new Tray(nativeImage.createFromDataURL(
      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAABhSURBVDiNY2AYBaNgGAAGBgaG/1D8H4ofMDAwSFCi+T8U/4fi/wwMDEzkanZiYGD4D8X/GRgYJBkYGP5TMgZNLzoYLIb8p8CAQWkI/KPAgEEdAsOGqiEwbKgaAsOGqiEDAACiHRH0tC9lSgAAAABJRU5ErkJggg=='
    ));
  }

  const contextMenu = Menu.buildFromTemplate([
    { 
      label: 'Show NogicOS', 
      click: () => {
        mainWindow?.show();
        mainWindow?.focus();
      }
    },
    { 
      label: 'New Session', 
      click: () => {
        mainWindow?.show();
        mainWindow?.focus();
        mainWindow?.webContents.send('new-session');
      }
    },
    { type: 'separator' },
    { 
      label: 'Quit', 
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('NogicOS - AI Desktop Assistant');
  tray.setContextMenu(contextMenu);

  // 点击托盘图标切换显示/隐藏
  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.focus();
      }
    }
  });

}

// ============== 注册全局快捷键 ==============
function registerGlobalShortcuts() {
  // Alt+N: 唤醒/隐藏窗口 (N for NogicOS, 避免与输入法切换 Ctrl+Space 冲突)
  const toggleRegistered = globalShortcut.register('Alt+N', () => {
    if (mainWindow) {
      if (mainWindow.isVisible() && mainWindow.isFocused()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.focus();
      }
    }
  });

  // Alt+N registered (or failed if in use)

  // Cmd/Ctrl+Shift+N: 新建会话
  const newSessionRegistered = globalShortcut.register('CommandOrControl+Shift+N', () => {
    mainWindow?.show();
    mainWindow?.focus();
    mainWindow?.webContents.send('new-session');
  });

}

// ============== 创建主窗口 ==============
async function createWindow() {
  const windowState = loadWindowState();

  mainWindow = new BrowserWindow({
    width: windowState.width,
    height: windowState.height,
    x: windowState.x,
    y: windowState.y,
    minWidth: 1000,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
    titleBarStyle: 'hidden',
    frame: false,
    backgroundColor: '#0a0a0a',
    show: false,
  });

  // 恢复最大化状态
  if (windowState.isMaximized) {
    mainWindow.maximize();
  }

  // 优雅显示窗口
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // 加载 UI
  if (IS_DEV) {
    const devServerRunning = await checkDevServer();
    
    if (devServerRunning) {
      mainWindow.loadURL(DEV_SERVER_URL);
      
      // 开发模式：多种方式打开 DevTools
      mainWindow.webContents.on('before-input-event', (event, input) => {
        // F12 或 Ctrl+Shift+I 打开 DevTools
        if (input.key === 'F12' || 
            (input.control && input.shift && input.key.toLowerCase() === 'i')) {
          mainWindow.webContents.toggleDevTools();
        }
      });
      
      // DevTools: 使用 F12 或 Ctrl+Shift+I 手动打开
      // mainWindow.webContents.openDevTools();
    } else {
      loadFromDist();
    }
  } else {
    loadFromDist();
  }

  // 关闭时隐藏到托盘而非退出
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  // 保存窗口状态
  mainWindow.on('resize', saveWindowState);
  mainWindow.on('move', saveWindowState);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// 从构建文件加载
function loadFromDist() {
  const distPath = path.join(__dirname, '..', 'nogicos-ui', 'dist', 'index.html');
  mainWindow.loadFile(distPath);
}

// ============== IPC 处理 ==============
ipcMain.on('window-minimize', () => {
  mainWindow?.minimize();
});

ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});

ipcMain.on('window-close', () => {
  mainWindow?.hide(); // 隐藏而非关闭
});

// 新增：切换命令面板
ipcMain.on('toggle-command-palette', () => {
  mainWindow?.webContents.send('toggle-command-palette');
});

// ============== 应用生命周期 ==============

// [P0 FIX Round 1] IPC sender validation helper
function isValidSender(event) {
  return event.sender === mainWindow?.webContents;
}

app.whenReady().then(() => {
  // [P0 FIX Round 1] Add Content Security Policy
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'; " +
          "script-src 'self' 'unsafe-inline' 'unsafe-eval'; " +  // Required for React/Vite
          "style-src 'self' 'unsafe-inline'; " +
          "img-src 'self' data: https:; " +
          "font-src 'self' data:; " +
          "connect-src 'self' ws://localhost:* http://localhost:* https:; " +
          "frame-src 'none';"
        ]
      }
    });
  });

  createWindow();
  createTray();
  registerGlobalShortcuts();
  
  // ============== 新版 Overlay (electron-overlay-window) ==============
  if (overlayController && overlayController.setupOverlayIPC) {
    overlayController.setupOverlayIPC();
    console.log('[Main] New OverlayController IPC handlers registered');
  }
  
  // Setup old overlay IPC handlers (fallback)
  if (overlayModule && overlayModule.setupOverlayIPC) {
    overlayModule.setupOverlayIPC(ipcMain);
    console.log('[Main] Legacy Overlay IPC handlers registered');
  }
  
  // Setup drag connector IPC handlers
  // 【修复 #3】确保 mainWindow 已初始化
  if (dragConnector && dragConnector.setupDragConnectorIPC && mainWindow) {
    dragConnector.setupDragConnectorIPC(mainWindow);
    console.log('[Main] DragConnector IPC handlers registered');
  } else if (dragConnector && dragConnector.setupDragConnectorIPC) {
    console.warn('[Main] DragConnector IPC handlers deferred - mainWindow not ready');
  }
  
  // Setup multi-overlay manager IPC handlers (新版多窗口 Overlay)
  if (multiOverlayManager && multiOverlayManager.setupMultiOverlayIPC) {
    multiOverlayManager.setupMultiOverlayIPC();
    console.log('[Main] MultiOverlayManager IPC handlers registered');
  }
  
  // ============== 连接状态 Overlay / 通知 ==============
  ipcMain.handle('overlay:show-connection', async (event, { hookType, target, targetHwnd }) => {
    // [P0 FIX Round 1] Validate IPC sender
    if (!isValidSender(event)) {
      console.warn('[Main] Unauthorized IPC call to overlay:show-connection');
      return { success: false, error: 'Unauthorized' };
    }

    // [P0 FIX Round 1] Validate parameters
    const validHookTypes = ['browser', 'desktop', 'file', 'terminal'];
    if (!validHookTypes.includes(hookType)) {
      console.warn(`[Main] Invalid hookType: ${hookType}`);
      return { success: false, error: 'Invalid hook type' };
    }
    if (typeof target !== 'string' || target.length > 256) {
      console.warn('[Main] Invalid target parameter');
      return { success: false, error: 'Invalid target' };
    }

    console.log(`[Main] Show connection: ${hookType} -> ${target} (HWND: ${targetHwnd})`);

    let overlayResult = { success: false };
    
    // 【核心】调用 OverlayController 显示 Overlay
    if (overlayController) {
      const manager = overlayController.getOverlayManager();
      if (manager.isAvailable && target) {
        console.log(`[Main] Calling OverlayManager.attach("${target}", "${hookType}")`);
        overlayResult = manager.attach(target, hookType);
        console.log(`[Main] OverlayManager.attach result:`, overlayResult);
      } else {
        console.log(`[Main] OverlayManager not available or no target`);
      }
    }
    
    // 备用：系统通知（如果 Overlay 不可用）
    if (!overlayResult.success) {
      const { Notification } = require('electron');
      if (Notification.isSupported()) {
        const notification = new Notification({
          title: '✅ NogicOS Connected',
          body: `Now monitoring: ${hookType}\n${target || 'system'}`,
          silent: false,
          urgency: 'normal',
        });
        notification.show();
        console.log(`[Main] Fallback: System notification shown for ${hookType}`);
      }
    }
    
    // 闪烁任务栏图标
    if (mainWindow && !mainWindow.isFocused()) {
      mainWindow.flashFrame(true);
      setTimeout(() => mainWindow.flashFrame(false), 2000);
    }
    
    return { success: true, method: overlayResult.success ? 'overlay' : 'notification', target };
  });
  
  ipcMain.handle('overlay:hide-connection', async (event, { hookType }) => {
    console.log(`[Main] Hide connection overlay: ${hookType}`);
    
    // 新版 overlay
    if (overlayController) {
      const manager = overlayController.getOverlayManager();
      manager.detach();
    }
    
    // 旧版 overlay
    if (overlayModule) {
      try {
        const manager = overlayModule.getOverlayManager();
        manager.removeAllOverlays();
      } catch (e) {}
    }
    return { success: true };
  });
  
  ipcMain.handle('notification:show', async (event, { title, body }) => {
    const { Notification } = require('electron');
    if (Notification.isSupported()) {
      new Notification({ title, body, silent: true }).show();
    }
    return { success: true };
  });
});

// 退出前清理
app.on('will-quit', () => {
  // 注销所有全局快捷键
  globalShortcut.unregisterAll();
});

app.on('before-quit', () => {
  app.isQuitting = true;
});

// macOS: 点击 dock 图标时显示窗口
app.on('activate', () => {
  if (mainWindow) {
    mainWindow.show();
  } else {
    createWindow();
  }
});

// 所有窗口关闭时不退出（因为有托盘）
app.on('window-all-closed', () => {
  // 不退出，保持在托盘
});
