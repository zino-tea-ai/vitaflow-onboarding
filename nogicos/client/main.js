/**
 * NogicOS Electron Client - Main Process
 * 
 * 架构 (修复后，Electron 28 兼容):
 * - BrowserWindow 作为主容器，加载 index.html
 * - BrowserView: AI 操作视图，CDP Bridge 控制此视图
 * 
 * 注意：BrowserView 在新版 Electron 中已废弃，但 Electron 28 仍支持
 * 
 * Features:
 * - Auto-start Python hive_server.py
 * - CDP support for Python control (控制 aiView，不影响 UI)
 * - WebSocket client for status updates
 * - IPC bridge for renderer communication
 * 
 * Start with: npm start
 */

const { app, BrowserWindow, BrowserView, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const WebSocket = require('ws');
const { CDPBridge } = require('./cdp-bridge');

// 防止 EPIPE 错误导致应用崩溃（当 IDE 更新或重启时可能发生）
process.stdout.on('error', (err) => {
  if (err.code === 'EPIPE') return; // 忽略管道断开错误
  console.error('stdout error:', err);
});
process.stderr.on('error', (err) => {
  if (err.code === 'EPIPE') return;
});

// 安全的日志函数
function safeLog(...args) {
  try {
    console.log(...args);
  } catch (e) {
    // 忽略 EPIPE 错误
  }
}

function safeError(...args) {
  try {
    console.error(...args);
  } catch (e) {
    // 忽略 EPIPE 错误
  }
}

// Configuration
const CDP_PORT = process.argv.find(arg => arg.startsWith('--remote-debugging-port='))
  ?.split('=')[1] || '9222';
const HTTP_PORT = 8080;
const WS_PORT = 8765;
const WS_URL = `ws://localhost:${WS_PORT}`;
const HTTP_URL = `http://localhost:${HTTP_PORT}`;

let mainWindow = null;
let aiView = null;      // AI 操作视图 (BrowserView, CDP 控制目标)
let pythonProcess = null;
let wsClient = null;
let wsReconnectTimer = null;
let wsConnected = false;
let cdpBridge = null;   // CDP Bridge 实例（控制 aiView）
let aiViewVisible = false;

// ============================================================
// Python Process Management
// ============================================================

function startPythonServer() {
  const serverScript = path.join(__dirname, '..', 'hive_server.py');
  
  console.log('[Python] Starting hive_server.py...');
  
  pythonProcess = spawn('python', [serverScript], {
    cwd: path.join(__dirname, '..'),
    env: { 
      ...process.env, 
      PYTHONUNBUFFERED: '1',
      PYTHONIOENCODING: 'utf-8',
    },
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  pythonProcess.stdout.on('data', (data) => {
    const lines = data.toString().trim().split('\n');
    lines.forEach(line => {
      safeLog(`[Python] ${line}`);
      
      // Forward to renderer for debug panel
      if (mainWindow) {
        mainWindow.webContents.send('python-log', line);
      }
    });
  });

  pythonProcess.stderr.on('data', (data) => {
    const lines = data.toString().trim().split('\n');
    lines.forEach(line => {
      // Filter out common warnings
      if (line.includes('UserWarning') || line.includes('Pydantic')) return;
      safeError(`[Python:ERR] ${line}`);
    });
  });

  pythonProcess.on('exit', (code) => {
    safeLog(`[Python] Process exited with code ${code}`);
    pythonProcess = null;
    
    // Notify renderer
    if (mainWindow) {
      mainWindow.webContents.send('python-status', { running: false, code });
    }
  });

  pythonProcess.on('error', (err) => {
    console.error('[Python] Failed to start:', err.message);
  });

  return pythonProcess;
}

function stopPythonServer() {
  if (pythonProcess) {
    console.log('[Python] Stopping server...');
    
    // Try graceful shutdown first
    pythonProcess.kill('SIGTERM');
    
    // Force kill after 3 seconds
    setTimeout(() => {
      if (pythonProcess) {
        pythonProcess.kill('SIGKILL');
      }
    }, 3000);
  }
}

async function waitForServer(url, maxAttempts = 30) {
  console.log(`[Startup] Waiting for server at ${url}...`);
  
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const response = await fetch(`${url}/health`);
      if (response.ok) {
        console.log('[Startup] Server is ready!');
        return true;
      }
    } catch (e) {
      // Server not ready yet
    }
    
    // Wait 500ms before retry
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Show progress
    if (i % 4 === 0) {
      console.log(`[Startup] Waiting... (${i * 0.5}s)`);
    }
  }
  
  console.error('[Startup] Server did not start in time');
  return false;
}

// ============================================================
// Window Management (BrowserWindow + BrowserView for Electron 28)
// ============================================================

function createWindow() {
  // 主窗口加载 NogicOS UI (index.html)
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: 'NogicOS',
    backgroundColor: '#0a0a0a',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webviewTag: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // 加载 UI
  mainWindow.loadFile('index.html');
  
  // 开发模式：打开 DevTools（需要时取消注释）
  // mainWindow.webContents.openDevTools({ mode: 'detach' });

  // ============================================================
  // 创建 AI 操作视图 (BrowserView, CDP 控制目标)
  // ============================================================
  aiView = new BrowserView({
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
    },
  });

  // 初始加载空白页（但不添加到窗口，避免覆盖主内容）
  aiView.webContents.loadURL('about:blank');
  
  // 注意：初始时不添加 aiView，等需要显示时再添加
  // mainWindow.addBrowserView(aiView); // 不在这里添加！

  // 监听窗口大小变化
  mainWindow.on('resize', () => {
    updateAiViewBounds();
  });

  // UI 加载完成后的初始化
  mainWindow.webContents.on('did-finish-load', async () => {
    console.log('[NogicOS] Main window ready');
    console.log(`[NogicOS] CDP: http://localhost:${CDP_PORT}`);
    console.log(`[NogicOS] API: ${HTTP_URL}`);
    console.log(`[NogicOS] WS:  ${WS_URL}`);
    
    // Send initial status
    mainWindow.webContents.send('ws-connection', wsConnected);
    mainWindow.webContents.send('python-status', { running: !!pythonProcess });
    
    // 注意：不在这里初始化 CDP Bridge，因为 aiView 还没有添加到窗口
    // CDP Bridge 会在 setAiViewVisible(true) 时初始化
    console.log('[CDP] Bridge will be initialized when AI view is shown');
  });

  // 窗口关闭时清理
  mainWindow.on('closed', () => {
    mainWindow = null;
    aiView = null;
  });
}

/**
 * 更新 AI 视图的位置和大小（仅在显示时调用）
 */
// 工具栏 + 结果面板的大约高度
const TOOLBAR_HEIGHT = 180;

function updateAiViewBounds() {
  if (!mainWindow || !aiView || !aiViewVisible) return;

  const views = mainWindow.getBrowserViews();
  if (!views.includes(aiView)) return;

  const [width, height] = mainWindow.getContentSize();
  
  // AI 视图显示在右侧 50%，从工具栏下方开始
  const aiWidth = Math.floor(width * 0.5);
  const aiHeight = height - TOOLBAR_HEIGHT;
  aiView.setBounds({ 
    x: width - aiWidth, 
    y: TOOLBAR_HEIGHT, 
    width: aiWidth, 
    height: aiHeight > 0 ? aiHeight : 100
  });
  console.log(`[Layout] AI View resized: ${aiWidth}x${aiHeight}px at y=${TOOLBAR_HEIGHT}`);
}

/**
 * 显示/隐藏 AI 视图
 * 关键：通过添加/移除 BrowserView 来控制显示，而不是设置 bounds
 * @param {boolean} visible - 是否显示
 * @param {number} widthPercent - AI 视图宽度占比 (0-100)
 */
async function setAiViewVisible(visible, widthPercent = 50) {
  if (!mainWindow || !aiView) return;

  aiViewVisible = visible;
  
  if (visible) {
    // 添加 BrowserView 到窗口（如果还没添加）
    const views = mainWindow.getBrowserViews();
    if (!views.includes(aiView)) {
      mainWindow.addBrowserView(aiView);
      console.log('[Layout] AI View added to window');
      
      // 首次添加时初始化 CDP Bridge
      if (!cdpBridge) {
        await initCDPBridge();
      }
    }
    
    const [width, height] = mainWindow.getContentSize();
    const aiWidth = Math.floor(width * widthPercent / 100);
    const aiHeight = height - TOOLBAR_HEIGHT;
    
    aiView.setBounds({ 
      x: width - aiWidth, 
      y: TOOLBAR_HEIGHT, 
      width: aiWidth, 
      height: aiHeight > 0 ? aiHeight : 100
    });
    
    // 通知 UI 调整布局
    mainWindow.webContents.send('ai-view-visible', { visible: true, widthPercent });
    console.log(`[Layout] AI View shown: ${aiWidth}x${aiHeight}px at y=${TOOLBAR_HEIGHT}`);
  } else {
    // 从窗口中移除 BrowserView（完全隐藏，不覆盖主内容）
    const views = mainWindow.getBrowserViews();
    if (views.includes(aiView)) {
      mainWindow.removeBrowserView(aiView);
      console.log('[Layout] AI View removed from window');
    }
    
    // 通知 UI 调整布局
    mainWindow.webContents.send('ai-view-visible', { visible: false });
    console.log('[Layout] AI View hidden');
  }
}

/**
 * 初始化 CDP Bridge
 * 关键修复：控制 aiView 而不是主窗口！
 */
async function initCDPBridge() {
  if (!aiView) return;
  
  try {
    // ✅ 正确：CDP Bridge 控制 aiView 的 webContents
    cdpBridge = new CDPBridge(aiView.webContents);
    const attached = await cdpBridge.attach();
    
    if (attached) {
      console.log('[CDP] Bridge initialized - controlling aiView (BrowserView)');
      
      // 通知 Python 服务器 CDP Bridge 已就绪
      sendToServer({
        type: 'cdp_ready',
        data: { attached: true },
      });
    } else {
      console.warn('[CDP] Bridge failed to attach');
    }
  } catch (err) {
    console.error('[CDP] Bridge initialization error:', err.message);
  }
}

// ============================================================
// WebSocket Client (connects to Python server)
// ============================================================

function connectWebSocket() {
  if (wsClient && wsClient.readyState === WebSocket.OPEN) {
    return;
  }

  console.log(`[WS] Connecting to ${WS_URL}...`);

  try {
    wsClient = new WebSocket(WS_URL);

    wsClient.on('open', () => {
      console.log('[WS] Connected to Python server');
      wsConnected = true;
      
      if (mainWindow) {
        mainWindow.webContents.send('ws-connection', true);
      }
      
      // Clear reconnect timer
      if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
      }
      
      // Request initial status
      wsClient.send(JSON.stringify({ type: 'get_status' }));
    });

    wsClient.on('message', (data) => {
      try {
        const message = JSON.parse(data.toString());
        handleWsMessage(message);
      } catch (e) {
        console.error('[WS] Parse error:', e);
      }
    });

    wsClient.on('close', () => {
      console.log('[WS] Disconnected');
      wsConnected = false;
      
      if (mainWindow) {
        mainWindow.webContents.send('ws-connection', false);
      }
      
      // Schedule reconnect
      scheduleReconnect();
    });

    wsClient.on('error', (err) => {
      // Suppress connection refused errors during startup
      if (!err.message.includes('ECONNREFUSED')) {
        console.error('[WS] Error:', err.message);
      }
      wsConnected = false;
    });

  } catch (e) {
    console.error('[WS] Connection failed:', e);
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (wsReconnectTimer) return;
  
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null;
    connectWebSocket();
  }, 2000);  // Retry every 2 seconds
}

function handleWsMessage(message) {
  const { type, data } = message;

  if (type === 'status' && mainWindow) {
    // Forward status to renderer
    mainWindow.webContents.send('status-update', data);
    
    // Update progress bar based on agent state
    if (data.agent) {
      const { status, progress } = data.agent;
      
      if (status === 'thinking' || status === 'acting') {
        mainWindow.setProgressBar(progress || 0.5);
      } else if (status === 'done' || status === 'idle') {
        mainWindow.setProgressBar(-1);
      } else if (status === 'error') {
        mainWindow.setProgressBar(1, { mode: 'error' });
        setTimeout(() => mainWindow.setProgressBar(-1), 2000);
      }
    }
    
    // Forward knowledge stats
    if (data.knowledge) {
      mainWindow.webContents.send('knowledge-update', data.knowledge);
    }
  }
  
  else if (type === 'pong') {
    // Heartbeat response
  }
  
  // 方案 B: 转发截图帧到 renderer
  else if (type === 'frame' && mainWindow) {
    mainWindow.webContents.send('ai-frame', data);
  }
  
  // ============================================================
  // CDP 命令处理（控制 aiView）
  // ============================================================
  else if (type === 'cdp_command') {
    handleCDPCommand(data);
  }
}

/**
 * 处理来自 Python 的 CDP 命令
 * @param {object} data - { requestId, method, params }
 */
async function handleCDPCommand(data) {
  const { requestId, method, params = {} } = data;
  
  try {
    let result = null;
    
    // 特殊处理：这些命令会初始化 cdpBridge，所以要先处理
    if (method === 'navigate' || method === 'showAiView') {
      // 显示 AI 视图并初始化 CDP Bridge（如果需要）
      await setAiViewVisible(true, params.widthPercent || 50);
      
      if (method === 'showAiView') {
        sendCDPResponse(requestId, { success: true }, null);
        return;
      }
    }
    
    // 检查 cdpBridge 是否已初始化
    if (!cdpBridge) {
      sendCDPResponse(requestId, null, 'CDP Bridge not initialized');
      return;
    }
    
    // 路由到对应的 CDP Bridge 方法
    switch (method) {
      case 'navigate':
        // cdpBridge 已经在上面初始化了
        await cdpBridge.navigate(params.url);
        result = { success: true, url: params.url };
        break;
        
      case 'click':
        await cdpBridge.click(params.x, params.y, params.options);
        result = { success: true };
        break;
        
      case 'clickSelector':
        await cdpBridge.clickSelector(params.selector);
        result = { success: true };
        break;
        
      case 'type':
        await cdpBridge.type(params.text);
        result = { success: true };
        break;
        
      case 'typeInSelector':
        await cdpBridge.typeInSelector(params.selector, params.text);
        result = { success: true };
        break;
        
      case 'pressKey':
        await cdpBridge.pressKey(params.key);
        result = { success: true };
        break;
        
      case 'screenshot':
        const imageData = await cdpBridge.screenshot(params.options);
        result = { success: true, data: imageData };
        break;
        
      case 'evaluate':
        const evalResult = await cdpBridge.evaluate(params.expression);
        result = { success: true, value: evalResult };
        break;
        
      case 'getTitle':
        const title = await cdpBridge.getTitle();
        result = { success: true, title };
        break;
        
      case 'getURL':
        const url = await cdpBridge.getURL();
        result = { success: true, url };
        break;
        
      case 'querySelector':
        const nodeId = await cdpBridge.querySelector(params.selector);
        result = { success: true, nodeId };
        break;
        
      case 'getBoundingBox':
        const box = await cdpBridge.getBoundingBox(params.nodeId);
        result = { success: true, box };
        break;
        
      // showAiView 在上面特殊处理了
        
      case 'hideAiView':
        await setAiViewVisible(false);
        result = { success: true };
        break;
        
      default:
        // 直接转发到 CDP
        result = await cdpBridge.sendCommand(method, params);
    }
    
    sendCDPResponse(requestId, result, null);
  } catch (err) {
    console.error(`[CDP] Command ${method} failed:`, err.message);
    sendCDPResponse(requestId, null, err.message);
  }
}

/**
 * 发送 CDP 命令响应回 Python
 */
function sendCDPResponse(requestId, result, error) {
  sendToServer({
    type: 'cdp_response',
    requestId,
    result,
    error,
  });
}

function sendToServer(message) {
  if (wsClient && wsClient.readyState === WebSocket.OPEN) {
    wsClient.send(JSON.stringify(message));
    return true;
  }
  return false;
}

// ============================================================
// IPC Handlers
// ============================================================

ipcMain.handle('get-status', () => {
  return {
    ready: true,
    cdpPort: CDP_PORT,
    httpPort: HTTP_PORT,
    wsPort: WS_PORT,
    wsConnected: wsConnected,
    pythonRunning: !!pythonProcess,
    windowId: mainWindow?.id,
  };
});

ipcMain.handle('navigate', async (event, url) => {
  // 导航 AI 视图
  if (aiView) {
    await setAiViewVisible(true, 50);
    await aiView.webContents.loadURL(url);
    return { success: true, url };
  }
  return { success: false, error: 'No AI view' };
});

ipcMain.handle('send-command', async (event, { command, args }) => {
  const success = sendToServer({
    type: 'command',
    command: command,
    args: args,
  });
  return { success, sent: success };
});

ipcMain.handle('execute-task', async (event, { task, url }) => {
  // Send task to HTTP server
  try {
    const response = await fetch(`${HTTP_URL}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, url }),
    });
    return await response.json();
  } catch (e) {
    return { success: false, error: e.message };
  }
});

ipcMain.handle('get-stats', async () => {
  try {
    const response = await fetch(`${HTTP_URL}/stats`);
    return await response.json();
  } catch (e) {
    return { error: e.message };
  }
});

// AI 视图控制
ipcMain.handle('show-ai-view', async (event, widthPercent = 50) => {
  await setAiViewVisible(true, widthPercent);
  return { success: true };
});

ipcMain.handle('hide-ai-view', async () => {
  await setAiViewVisible(false);
  return { success: true };
});

ipcMain.handle('get-ai-view-url', () => {
  if (aiView) {
    return { url: aiView.webContents.getURL() };
  }
  return { url: null };
});

// ============================================================
// App Lifecycle
// ============================================================

app.whenReady().then(async () => {
  console.log('='.repeat(50));
  console.log('NogicOS Starting...');
  console.log('Architecture: BrowserWindow + BrowserView (Electron 28)');
  console.log('='.repeat(50));
  
  // Step 1: Start Python server
  startPythonServer();
  
  // Step 2: Wait for server to be ready
  const serverReady = await waitForServer(HTTP_URL);
  
  if (!serverReady) {
    console.error('[Startup] Failed to start Python server');
    // Continue anyway, let user see the error
  }
  
  // Step 3: Create window
  createWindow();
  
  // Step 4: Connect WebSocket
  setTimeout(connectWebSocket, 500);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  // Close WebSocket
  if (wsClient) {
    wsClient.close();
    wsClient = null;
  }
  
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer);
  }
  
  // Stop Python server
  stopPythonServer();
  
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopPythonServer();
});

console.log('[NogicOS] Main process initialized - BrowserView architecture');
