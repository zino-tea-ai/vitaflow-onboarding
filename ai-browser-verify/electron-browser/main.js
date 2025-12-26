/**
 * NogicOS - AI 原生浏览器
 * 主进程
 */

// 加载环境变量
require('dotenv').config();

const { app, BrowserWindow, BrowserView, ipcMain, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const { NogicOSWebSocketClient } = require('./websocket-client');

// ========================================
// NogicOS 配置
// ========================================
console.log(`[NogicOS] 启动中...`);

let mainWindow;
let browserView;  // 使用 BrowserView 替代 webview 以支持 CDP
let wsClient;
let pythonProcess;
let currentModel = process.env.DEFAULT_MODEL || 'gpt-5.2';
let webviewDebuggerPort = null;  // webview 的独立调试端口

// 模型配置 - 2025年12月最新模型
const MODEL_CONFIG = {
    'gpt-5.2': { name: 'GPT-5.2 Thinking', provider: 'openai' },
    'gpt-5.2-pro': { name: 'GPT-5.2 Pro', provider: 'openai' },
    'gpt-5.2-chat-latest': { name: 'GPT-5.2 Instant', provider: 'openai' },
    'claude-opus-4-5-20251101': { name: 'Claude Opus 4.5', provider: 'anthropic' },
    'gemini-2.0-flash-exp': { name: 'Gemini 2.0 Flash', provider: 'google' }
};

// 创建主窗口
function createWindow() {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:createWindow',message:'Creating main window',data:{},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1000,
        minHeight: 700,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            webviewTag: true,  // 启用 webview 标签
        },
        titleBarStyle: 'hidden',
        frame: false,
        backgroundColor: '#0a0a0f',
    });

    // 加载 UI
    const htmlPath = path.join(__dirname, 'renderer', 'index.html');
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:loadFile',message:'Loading HTML file',data:{htmlPath},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    mainWindow.loadFile(htmlPath);

    // 监听主窗口加载完成
    mainWindow.webContents.on('did-finish-load', () => {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:didFinishLoad',message:'Main window HTML finished loading',data:{url:mainWindow.webContents.getURL()},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A'})}).catch(()=>{});
        // #endregion
        
        // 延迟获取 webview 的 webContents（等待 webview 初始化）
        setTimeout(() => {
            setupWebviewMonitor();
        }, 2000);
    });
    
    mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:didFailLoad',message:'Main window failed to load',data:{errorCode,errorDescription},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'E'})}).catch(()=>{});
        // #endregion
    });

    // 初始化 WebSocket 客户端
    initWebSocket();
    
    // 创建菜单
    createMenu();
}

// ========================================
// Webview 监控（用于状态同步）
// ========================================
function setupWebviewMonitor() {
    const { webContents } = require('electron');
    const allContents = webContents.getAllWebContents();
    
    console.log(`[NogicOS] Searching for webview among ${allContents.length} webContents...`);
    
    const webviewContents = allContents.find(wc => wc.getType() === 'webview');
    
    if (webviewContents) {
        const webviewUrl = webviewContents.getURL();
        console.log('[NogicOS] Found webview:');
        console.log(`  - URL: ${webviewUrl}`);
        
        // 监听 webview URL 变化
        webviewContents.on('did-navigate', (event, url) => {
            console.log(`[NogicOS] Webview navigated to: ${url}`);
        });
    } else {
        console.log('[NogicOS] Webview not found, retrying...');
        setTimeout(setupWebviewMonitor, 1000);
    }
}

// 初始化 WebSocket 连接
function initWebSocket() {
    wsClient = new NogicOSWebSocketClient('ws://127.0.0.1:8765');
    
    wsClient.on('connected', () => {
        mainWindow.webContents.send('ws:connectionStatus', { connected: true });
    });
    
    wsClient.on('disconnected', () => {
        mainWindow.webContents.send('ws:connectionStatus', { connected: false });
    });
    
    wsClient.on('serverConnected', (data) => {
        console.log('[WebSocket] connected:', data);
    });
    
    // 任务事件
    wsClient.on('taskStart', (data) => {
        mainWindow.webContents.send('ai:taskStart', data);
    });
    
    wsClient.on('taskComplete', (data) => {
        mainWindow.webContents.send('ai:taskComplete', data);
    });
    
    wsClient.on('taskError', (data) => {
        mainWindow.webContents.send('ai:taskError', data);
    });
    
    // 步骤事件
    wsClient.on('stepStart', (data) => {
        mainWindow.webContents.send('ai:stepStart', data);
    });
    
    wsClient.on('stepThinking', (data) => {
        mainWindow.webContents.send('ai:stepThinking', data);
    });
    
    wsClient.on('stepAction', (data) => {
        mainWindow.webContents.send('ai:stepAction', data);
    });
    
    wsClient.on('stepResult', (data) => {
        mainWindow.webContents.send('ai:stepResult', data);
    });
    
    wsClient.on('stepComplete', (data) => {
        mainWindow.webContents.send('ai:stepComplete', data);
    });
    
    // 技能事件
    wsClient.on('skillMatched', (data) => {
        mainWindow.webContents.send('ai:skillMatched', data);
    });
    
    wsClient.on('skillExecuting', (data) => {
        mainWindow.webContents.send('ai:skillExecuting', data);
    });
    
    wsClient.on('skillResult', (data) => {
        mainWindow.webContents.send('ai:skillResult', data);
    });
    
    // 学习事件
    wsClient.on('learnStart', (data) => {
        mainWindow.webContents.send('ai:learnStart', data);
    });
    
    wsClient.on('learnProgress', (data) => {
        mainWindow.webContents.send('ai:learnProgress', data);
    });
    
    wsClient.on('skillDiscovered', (data) => {
        mainWindow.webContents.send('ai:skillDiscovered', data);
    });
    
    wsClient.on('learnComplete', (data) => {
        mainWindow.webContents.send('ai:learnComplete', data);
    });
    
    // 知识库事件
    wsClient.on('kbLoaded', (data) => {
        mainWindow.webContents.send('ai:kbLoaded', data);
    });
    
    wsClient.on('skillList', (data) => {
        mainWindow.webContents.send('ai:skillList', data);
    });
    
    // AI 可视化动画事件（NogicOS Atlas 体验）
    wsClient.on('cursorMove', (data) => {
        mainWindow.webContents.send('ai:cursorMove', data);
    });
    
    wsClient.on('cursorClick', (data) => {
        mainWindow.webContents.send('ai:cursorClick', data);
    });
    
    wsClient.on('cursorType', (data) => {
        mainWindow.webContents.send('ai:cursorType', data);
    });
    
    wsClient.on('cursorStopType', (data) => {
        mainWindow.webContents.send('ai:cursorStopType', data);
    });
    
    wsClient.on('highlight', (data) => {
        mainWindow.webContents.send('ai:highlight', data);
    });
    
    wsClient.on('highlightHide', (data) => {
        mainWindow.webContents.send('ai:highlightHide', data);
    });
    
    wsClient.on('screenGlow', (data) => {
        mainWindow.webContents.send('ai:screenGlow', data);
    });
    
    wsClient.on('screenGlowStop', (data) => {
        mainWindow.webContents.send('ai:screenGlowStop', data);
    });
    
    wsClient.on('screenPulse', (data) => {
        mainWindow.webContents.send('ai:screenPulse', data);
    });
    
    wsClient.connect();
}

// 创建菜单
function createMenu() {
    const template = [
        {
            label: 'SkillFlow',
            submenu: [
                { role: 'about' },
                { type: 'separator' },
                { role: 'quit' }
            ]
        },
        {
            label: '视图',
            submenu: [
                { role: 'reload' },
                { role: 'toggleDevTools' },
                { type: 'separator' },
                { role: 'resetZoom' },
                { role: 'zoomIn' },
                { role: 'zoomOut' },
            ]
        }
    ];
    
    Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// IPC 处理器 - 设置模型
ipcMain.handle('set-model', async (_, model) => {
    if (MODEL_CONFIG[model]) {
        currentModel = model;
        console.log('[AI] 模型切换为:', MODEL_CONFIG[model].name);
        return { success: true, model: currentModel };
    }
    return { success: false, error: '未知模型' };
});

ipcMain.handle('get-models', async () => {
    return {
        current: currentModel,
        available: MODEL_CONFIG
    };
});

// IPC 处理器 - AI 任务
ipcMain.handle('execute-task', async (_, task, url, model) => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:execute-task:entry',message:'IPC handler called',data:{task,url,model},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'D'})}).catch(()=>{});
    // #endregion
    
    const useModel = model || currentModel;
    console.log('[AI] 执行任务:', task);
    console.log('[AI] URL:', url);
    console.log('[AI] 模型:', MODEL_CONFIG[useModel]?.name || useModel);
    
    const cwd = path.join(__dirname, '..', 'SkillWeaver');
    const env = { 
        ...process.env,
        PYTHONIOENCODING: 'utf-8',  // 修复 Windows 终端 emoji 编码问题
        PYTHONUTF8: '1'
    };
    
    // 简化的命令参数 - 使用 headless 模式 + WebSocket 同步
    const args = [
        '-m', 'skillweaver.attempt_task_with_ws',
        url,
        task,
        '--agent-lm-name', useModel,
        '--max-steps', '15'
    ];
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:execute-task:spawn',message:'About to spawn Python',data:{cwd,args},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'E'})}).catch(()=>{});
    // #endregion
    
    // 启动 AI 任务（headless 模式，通过 WebSocket 同步状态到 NogicOS）
    pythonProcess = spawn('python', args, { 
        cwd,
        env,
        windowsHide: true
    });
    
    pythonProcess.stdout.on('data', (data) => {
        console.log('[AI stdout]', data.toString());
    });
    
    pythonProcess.stderr.on('data', (data) => {
        console.log('[AI stderr]', data.toString());
    });
    
    pythonProcess.on('close', (code) => {
        console.log('[AI] 进程结束，退出码:', code);
        pythonProcess = null;
        if (mainWindow) {
            mainWindow.webContents.send('ai:processExit', { code });
        }
    });
    
    return { started: true, model: useModel };
});

ipcMain.handle('learn-website', async (_, url, model) => {
    const useModel = model || currentModel;
    console.log('[AI] 学习网站:', url);
    console.log('[AI] 模型:', MODEL_CONFIG[useModel]?.name || useModel);
    
    const cwd = path.join(__dirname, '..', 'SkillWeaver');
    const env = { 
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUTF8: '1'
    };
    
    pythonProcess = spawn('python', [
        '-m', 'skillweaver.explore_with_ws',
        url || 'https://news.ycombinator.com',
        './learn_output',
        '--iterations', '5',
        '--agent-lm-name', useModel
    ], { 
        cwd,
        env,
        windowsHide: true
    });
    
    pythonProcess.stdout.on('data', (data) => {
        console.log('[Learn stdout]', data.toString());
    });
    
    pythonProcess.stderr.on('data', (data) => {
        console.log('[Learn stderr]', data.toString());
    });
    
    pythonProcess.on('close', (code) => {
        console.log('[Learn] 进程结束，退出码:', code);
        pythonProcess = null;
        if (mainWindow) {
            mainWindow.webContents.send('ai:processExit', { code });
        }
    });
    
    return { started: true, model: useModel };
});

ipcMain.handle('stop-task', () => {
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
        return { stopped: true };
    }
    return { stopped: false };
});

// IPC 处理器 - 技能库
ipcMain.handle('get-skill-library', async () => {
    // 从知识库读取技能列表
    return [];
});

ipcMain.handle('get-skill-detail', async (_, skillName) => {
    return null;
});

// IPC 处理器 - WebSocket
ipcMain.handle('ws:getStatus', () => {
    return wsClient ? wsClient.getConnectionStatus() : false;
});

ipcMain.handle('ws:reconnect', () => {
    if (wsClient) {
        wsClient.disconnect();
        wsClient.connect();
    }
});

// 启动 Python WebSocket 服务器
function startPythonWebSocketServer() {
    const cwd = path.join(__dirname, '..', 'SkillWeaver');
    
    const serverProcess = spawn('python', [
        '-m', 'skillweaver.websocket_server'
    ], { cwd, windowsHide: true });
    
    serverProcess.stdout.on('data', (data) => {
        console.log('[WS Server]', data.toString());
    });
    
    serverProcess.stderr.on('data', (data) => {
        console.log('[WS Server Error]', data.toString());
    });
    
    return serverProcess;
}

// 应用启动
app.whenReady().then(() => {
    console.log('[NogicOS] 启动中...');
    
    // 启动 WebSocket 服务器
    // startPythonWebSocketServer();
    
    createWindow();
    
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (wsClient) {
        wsClient.disconnect();
    }
    if (pythonProcess) {
        pythonProcess.kill();
    }
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
