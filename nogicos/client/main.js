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

const { app, BrowserWindow, ipcMain, globalShortcut, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');

// 配置
const DEV_SERVER_URL = 'http://localhost:5173';
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
      
      // 开发模式：按 F12 手动打开 DevTools
      mainWindow.webContents.on('before-input-event', (event, input) => {
        if (input.key === 'F12') {
          mainWindow.webContents.toggleDevTools();
        }
      });
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
app.whenReady().then(() => {
  createWindow();
  createTray();
  registerGlobalShortcuts();
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
