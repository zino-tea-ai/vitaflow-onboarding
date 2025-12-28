/**
 * NogicOS Electron Client - Main Process
 * 
 * Architecture (fixed, Electron 28 compatible):
 * - BrowserWindow as main container, loads index.html
 * - BrowserView: AI operation view, controlled by CDP Bridge
 * 
 * Note: BrowserView is deprecated in newer Electron but still supported in Electron 28
 * 
 * Features:
 * - Auto-start Python hive_server.py
 * - CDP support for Python control (controls aiView without affecting UI)
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
const { executeTool } = require('./tools');

// ============================================================
// Performance Optimizations (inspired by Zen Browser's fastfox)
// ============================================================

// Enable GPU acceleration flags before app ready
app.commandLine.appendSwitch('enable-gpu-rasterization');
app.commandLine.appendSwitch('enable-zero-copy');
app.commandLine.appendSwitch('enable-hardware-overlays', 'single-fullscreen,single-on-top,underlay');
app.commandLine.appendSwitch('enable-features', 'VaapiVideoDecoder,VaapiVideoEncoder,CanvasOopRasterization');

// Smooth scrolling - same physics as Zen Browser
app.commandLine.appendSwitch('smooth-scrolling');

// Memory optimization
app.commandLine.appendSwitch('js-flags', '--max-old-space-size=4096'); // Limit V8 heap

// Prevent EPIPE errors from crashing the app (can happen when IDE updates or restarts)
process.stdout.on('error', (err) => {
  if (err.code === 'EPIPE') return; // Ignore broken pipe errors
  console.error('stdout error:', err);
});
process.stderr.on('error', (err) => {
  if (err.code === 'EPIPE') return;
});

// ============================================================
// Single Instance Lock - Prevent multiple instances
// ============================================================
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  console.log('[App] Another instance is running. Exiting...');
  app.quit();
} else {
  app.on('second-instance', () => {
    // Someone tried to run a second instance, focus our window
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

// Safe logging functions
function safeLog(...args) {
  try {
    console.log(...args);
  } catch (e) {
    // Ignore EPIPE errors
  }
}

function safeError(...args) {
  try {
    console.error(...args);
  } catch (e) {
    // Ignore EPIPE errors
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
let aiView = null;      // AI operation view (BrowserView, CDP control target)
let pythonProcess = null;
let wsClient = null;
let wsReconnectTimer = null;
let wsConnected = false;
let cdpBridge = null;   // CDP Bridge instance (controls aiView)
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
  // Main window loads NogicOS UI (index.html)
  // Glassmorphism: Transparent window with system blur effect
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: 'NogicOS',
    // === Transparent Window Settings ===
    transparent: true,              // Enable transparency
    frame: false,                   // Remove system title bar (custom title bar in HTML)
    backgroundColor: '#00000000',   // Fully transparent background
    roundedCorners: true,           // Windows 11 native rounded corners
    // Note: On Windows 11 22H2+, we'll apply Acrylic/Mica effect
    // On macOS, we'll apply vibrancy
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webviewTag: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // === Apply System Blur Effects ===
  // Windows 11 22H2+: Acrylic effect (frosted glass with desktop blur)
  if (process.platform === 'win32') {
    try {
      mainWindow.setBackgroundMaterial('acrylic');
      console.log('[Window] Applied Windows Acrylic effect');
    } catch (e) {
      console.log('[Window] Acrylic not available (requires Windows 11 22H2+)');
    }
  }
  
  // macOS: Vibrancy effect
  if (process.platform === 'darwin') {
    try {
      mainWindow.setVibrancy('window');
      console.log('[Window] Applied macOS vibrancy effect');
    } catch (e) {
      console.log('[Window] Vibrancy not available');
    }
  }

  // Load UI
  mainWindow.loadFile('index.html');
  
  // Development mode: Open DevTools (uncomment when needed)
  // mainWindow.webContents.openDevTools({ mode: 'detach' });

  // ============================================================
  // Create AI operation view (BrowserView, CDP control target)
  // ============================================================
  aiView = new BrowserView({
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
      // === Performance Optimizations ===
      backgroundThrottling: false,    // Don't throttle background tabs (AI needs to run)
      enableBlinkFeatures: 'CSSScrollSnapV2',  // Smooth scroll snap
      // V8 code caching for faster page loads
      v8CacheOptions: 'bypassHeatCheck',
    },
  });

  // Initial load blank page (but don't add to window to avoid covering main content)
  aiView.webContents.loadURL('about:blank');
  
  // Note: Don't add aiView initially, wait until we need to show it
  // mainWindow.addBrowserView(aiView); // Don't add here!

  // Listen for window resize
  mainWindow.on('resize', () => {
    updateAiViewBounds();
  });
  
  // Listen for maximize/unmaximize to update title bar button
  mainWindow.on('maximize', () => {
    mainWindow.webContents.send('window-maximize-change', true);
  });
  
  mainWindow.on('unmaximize', () => {
    mainWindow.webContents.send('window-maximize-change', false);
  });

  // Initialization after UI is loaded
  mainWindow.webContents.on('did-finish-load', async () => {
    console.log('[NogicOS] Main window ready');
    console.log(`[NogicOS] CDP: http://localhost:${CDP_PORT}`);
    console.log(`[NogicOS] API: ${HTTP_URL}`);
    console.log(`[NogicOS] WS:  ${WS_URL}`);
    
    // Send initial status
    mainWindow.webContents.send('ws-connection', wsConnected);
    mainWindow.webContents.send('python-status', { running: !!pythonProcess });
    
    // Note: Don't initialize CDP Bridge here, aiView is not yet added to window
    // CDP Bridge will be initialized in setAiViewVisible(true)
    console.log('[CDP] Bridge will be initialized when AI view is shown');
  });

  // Cleanup when window is closed
  mainWindow.on('closed', () => {
    mainWindow = null;
    aiView = null;
  });
}

/**
 * Update AI view position and size (only called when visible)
 * 
 * New three-column layout:
 * ┌──────────┬─────────────────────────┬───────────────────┐
 * │          │                          │  Preview Panel    │
 * │ Sidebar  │        Chat Area         │   (400px)        │
 * │ (240px)  │                          │                   │
 * │          │                          │  BrowserView      │
 * │          │                          │  Render here      │
 * │          │                          │                   │
 * └──────────┴──────────────────────────┴───────────────────┘
 */
const TITLEBAR_HEIGHT = 32;
const SIDEBAR_WIDTH = 240;
const PREVIEW_WIDTH = 400;
const STATUSBAR_HEIGHT = 28;
const PREVIEW_HEADER_HEIGHT = 48;   // Tabs + close button
const BROWSER_URLBAR_HEIGHT = 48;   // URL input bar

function updateAiViewBounds() {
  if (!mainWindow || !aiView || !aiViewVisible) return;

  const views = mainWindow.getBrowserViews();
  if (!views.includes(aiView)) return;

  const [width, height] = mainWindow.getContentSize();
  
  // BrowserView shown inside preview panel (right side)
  // Position: below preview header and URL bar
  const aiX = width - PREVIEW_WIDTH;
  const aiY = TITLEBAR_HEIGHT + PREVIEW_HEADER_HEIGHT + BROWSER_URLBAR_HEIGHT;
  const aiWidth = PREVIEW_WIDTH;
  const aiHeight = height - TITLEBAR_HEIGHT - STATUSBAR_HEIGHT - PREVIEW_HEADER_HEIGHT - BROWSER_URLBAR_HEIGHT;
  
  aiView.setBounds({ 
    x: aiX, 
    y: aiY, 
    width: aiWidth, 
    height: aiHeight > 0 ? aiHeight : 100
  });
  console.log(`[Layout] AI View bounds: x=${aiX}, y=${aiY}, ${aiWidth}x${aiHeight}px`);
}

/**
 * Show/hide AI view
 * Key: Control visibility by adding/removing BrowserView, not by setting bounds
 * 
 * In the new layout, BrowserView is embedded inside the Preview Panel (right side)
 * @param {boolean} visible - Whether to show
 */
async function setAiViewVisible(visible) {
  if (!mainWindow || !aiView) return;

  aiViewVisible = visible;
  
  if (visible) {
    // Add BrowserView to window (if not already added)
    const views = mainWindow.getBrowserViews();
    if (!views.includes(aiView)) {
      mainWindow.addBrowserView(aiView);
      console.log('[Layout] AI View added to window (inside preview panel)');
      
      // Initialize CDP Bridge on first add
      if (!cdpBridge) {
        await initCDPBridge();
      }
    }
    
    // Calculate bounds for preview panel position
    const [width, height] = mainWindow.getContentSize();
    const aiX = width - PREVIEW_WIDTH;
    const aiY = TITLEBAR_HEIGHT + PREVIEW_HEADER_HEIGHT + BROWSER_URLBAR_HEIGHT;
    const aiWidth = PREVIEW_WIDTH;
    const aiHeight = height - TITLEBAR_HEIGHT - STATUSBAR_HEIGHT - PREVIEW_HEADER_HEIGHT - BROWSER_URLBAR_HEIGHT;
    
    aiView.setBounds({ 
      x: aiX, 
      y: aiY, 
      width: aiWidth, 
      height: aiHeight > 0 ? aiHeight : 100
    });
    
    // Notify UI to expand preview panel and switch to browser tab
    mainWindow.webContents.send('ai-view-visible', { visible: true });
    console.log(`[Layout] AI View shown in preview panel: x=${aiX}, y=${aiY}, ${aiWidth}x${aiHeight}px`);
  } else {
    // Remove BrowserView from window (completely hidden)
    const views = mainWindow.getBrowserViews();
    if (views.includes(aiView)) {
      mainWindow.removeBrowserView(aiView);
      console.log('[Layout] AI View removed from window');
    }
    
    // Notify UI
    mainWindow.webContents.send('ai-view-visible', { visible: false });
    console.log('[Layout] AI View hidden');
  }
}

/**
 * Initialize CDP Bridge
 * Key fix: Control aiView instead of main window!
 */
async function initCDPBridge() {
  if (!aiView) return;
  
  try {
    // ✅ Correct: CDP Bridge controls aiView's webContents
    cdpBridge = new CDPBridge(aiView.webContents);
    const attached = await cdpBridge.attach();
    
    if (attached) {
      console.log('[CDP] Bridge initialized - controlling aiView (BrowserView)');
      
      // Safety: Input is disabled by default, only enable when executing tasks
      // cdpBridge.enableInput() will be called only during task execution
      console.log('[CDP] Input disabled by default for safety');
      
      // Notify Python server that CDP Bridge is ready
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
        const raw = data.toString();
        console.log('[WS] Raw message:', raw.substring(0, 200));
        const message = JSON.parse(raw);
        console.log('[WS] Parsed message type:', message.type);
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
      const { state, progress } = data.agent;  // Python uses 'state', not 'status'
      
      if (state === 'thinking' || state === 'acting') {
        mainWindow.setProgressBar(progress || 0.5);
      } else if (state === 'done' || state === 'idle') {
        mainWindow.setProgressBar(-1);
      } else if (state === 'error') {
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
  
  // Option B: Forward screenshot frames to renderer
  else if (type === 'frame' && mainWindow) {
    mainWindow.webContents.send('ai-frame', data);
  }
  
  // ============================================================
  // CDP Command Processing (controls aiView)
  // ============================================================
  else if (type === 'cdp_command') {
    handleCDPCommand(data);
  }
  
  // ============================================================
  // Tool Call Processing (file system, terminal, etc.)
  // ============================================================
  else if (type === 'tool_call') {
    console.log('[WS] Received tool_call message:', JSON.stringify(message));
    // Message format: { type, call_id, tool_name, args } (from Python)
    // Need to extract from top level, not data
    handleToolCall({
      call_id: message.call_id,
      tool_name: message.tool_name,
      args: message.args
    });
  }
  
  // Log unknown message types
  else {
    console.log('[WS] Unknown message type:', type, message);
  }
}

/**
 * Handle tool calls from Python
 * @param {object} data - { call_id, tool_name, args }
 */
async function handleToolCall(data) {
  const { call_id, tool_name, args } = data;
  
  console.log(`[Tool] Executing: ${tool_name}`, args);
  
  try {
    const result = await executeTool(tool_name, args);
    
    // Send success response
    const response = {
      type: 'tool_response',
      call_id,
      result,
      error: null,
    };
    console.log(`[Tool] Sending response for ${tool_name}:`, call_id);
    const sent = sendToServer(response);
    console.log(`[Tool] Response sent: ${sent}`);
    
    console.log(`[Tool] ${tool_name} completed successfully`);
  } catch (err) {
    // Send error response
    sendToServer({
      type: 'tool_response',
      call_id,
      result: null,
      error: err.message,
    });
    
    console.error(`[Tool] ${tool_name} failed:`, err.message);
  }
}

/**
 * Handle CDP commands from Python
 * @param {object} data - { requestId, method, params }
 */
async function handleCDPCommand(data) {
  const { requestId, method, params = {} } = data;
  
  try {
    let result = null;
    
    // Special handling: these commands initialize cdpBridge, so handle them first
    if (method === 'navigate' || method === 'showAiView') {
      // Show AI view and initialize CDP Bridge (if needed)
      await setAiViewVisible(true);
      
      if (method === 'showAiView') {
        sendCDPResponse(requestId, { success: true }, null);
        return;
      }
    }
    
    // Check if cdpBridge is initialized
    if (!cdpBridge) {
      sendCDPResponse(requestId, null, 'CDP Bridge not initialized');
      return;
    }
    
    // Enable input for commands that need keyboard/mouse interaction
    const inputCommands = ['click', 'type', 'pressKey', 'clickSelector', 'typeInSelector'];
    const needsInput = inputCommands.includes(method);
    
    if (needsInput && cdpBridge) {
      cdpBridge.enableInput();
    }
    
    try {
      // Route to corresponding CDP Bridge method
      switch (method) {
        case 'navigate':
          // cdpBridge is already initialized above
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
        
      // showAiView is handled specially above
        
      case 'hideAiView':
        await setAiViewVisible(false);
        result = { success: true };
        break;
        
      default:
        // Forward directly to CDP
        result = await cdpBridge.sendCommand(method, params);
    }
    
    sendCDPResponse(requestId, result, null);
    } finally {
      // Always disable input after command completes (safety)
      if (needsInput && cdpBridge) {
        cdpBridge.disableInput();
      }
    }
  } catch (err) {
    console.error(`[CDP] Command ${method} failed:`, err.message);
    sendCDPResponse(requestId, null, err.message);
    // Ensure input is disabled on error too
    if (cdpBridge) {
      cdpBridge.disableInput();
    }
  }
}

/**
 * Send CDP command response back to Python
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
  // Navigate AI view
  if (aiView) {
    await setAiViewVisible(true);
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

// AI View Control
ipcMain.handle('show-ai-view', async () => {
  await setAiViewVisible(true);
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
// Window Control (for custom title bar)
// ============================================================

ipcMain.handle('window-minimize', () => {
  if (mainWindow) {
    mainWindow.minimize();
  }
});

ipcMain.handle('window-maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
});

ipcMain.handle('window-close', () => {
  if (mainWindow) {
    mainWindow.close();
  }
});

ipcMain.handle('window-is-maximized', () => {
  return mainWindow ? mainWindow.isMaximized() : false;
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
  // Cleanup CDP Bridge first - prevent any accidental input
  if (cdpBridge) {
    console.log('[App] Cleaning up CDP Bridge...');
    cdpBridge.destroy();
    cdpBridge = null;
  }
  
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
  // Cleanup CDP Bridge to prevent keyboard/mouse events
  if (cdpBridge) {
    cdpBridge.destroy();
    cdpBridge = null;
  }
  stopPythonServer();
});

console.log('[NogicOS] Main process initialized - BrowserView architecture');
