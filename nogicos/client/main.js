/**
 * NogicOS Desktop Client
 * 
 * 加载 nogicos-ui React 前端作为桌面应用
 * 支持开发模式（Vite dev server）和生产模式（dist 文件）
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

// 配置
const DEV_SERVER_URL = 'http://localhost:5173';
const IS_DEV = process.env.NODE_ENV === 'development' || !app.isPackaged;

let mainWindow;

// 检查开发服务器是否运行
async function checkDevServer() {
  try {
    const response = await fetch(DEV_SERVER_URL, { method: 'HEAD' });
    return response.ok;
  } catch {
    return false;
  }
}

// 创建主窗口
async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    titleBarStyle: 'hidden',
    frame: false,
    backgroundColor: '#0a0a0a',
    show: false, // 等待加载完成再显示
  });

  // 优雅显示窗口
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // 加载 UI
  if (IS_DEV) {
    const devServerRunning = await checkDevServer();
    
    if (devServerRunning) {
      console.log('[NogicOS] Loading from dev server:', DEV_SERVER_URL);
      mainWindow.loadURL(DEV_SERVER_URL);
      
      // 开发模式打开 DevTools
      mainWindow.webContents.openDevTools({ mode: 'detach' });
    } else {
      console.log('[NogicOS] Dev server not running, loading from dist');
      loadFromDist();
    }
  } else {
    loadFromDist();
  }

  // 窗口关闭事件
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// 从构建文件加载
function loadFromDist() {
  const distPath = path.join(__dirname, '..', 'nogicos-ui', 'dist', 'index.html');
  console.log('[NogicOS] Loading from dist:', distPath);
  mainWindow.loadFile(distPath);
}

// IPC: 窗口控制
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
  mainWindow?.close();
});

// 应用就绪
app.whenReady().then(createWindow);

// macOS: 点击 dock 图标时重新创建窗口
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// 所有窗口关闭时退出（macOS 除外）
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

console.log('[NogicOS] Desktop client starting...');
console.log('[NogicOS] Mode:', IS_DEV ? 'development' : 'production');
