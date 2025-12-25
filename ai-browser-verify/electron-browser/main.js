/**
 * AI Browser - 主进程
 * 能学习网站操作的智能浏览器
 */
const { app, BrowserWindow, ipcMain, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// 开发模式
const isDev = process.argv.includes('--dev');

// 主窗口
let mainWindow = null;

// AI 引擎状态
let aiEngineStatus = {
  ready: false,
  lastTask: null,
  knowledgeBase: {}
};

/**
 * 创建主窗口
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webviewTag: true  // 启用 webview
    },
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: 15, y: 15 },
    backgroundColor: '#0a0a0a'
  });

  // 加载主页面
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  // 开发模式打开 DevTools
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  // 设置菜单
  createMenu();

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * 创建菜单
 */
function createMenu() {
  const template = [
    {
      label: 'AI Browser',
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
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'AI',
      submenu: [
        {
          label: '学习当前页面',
          accelerator: 'CmdOrCtrl+L',
          click: () => mainWindow?.webContents.send('ai:learn')
        },
        {
          label: '执行任务',
          accelerator: 'CmdOrCtrl+E',
          click: () => mainWindow?.webContents.send('ai:execute')
        },
        { type: 'separator' },
        {
          label: '查看知识库',
          click: () => mainWindow?.webContents.send('ai:showKnowledgeBase')
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

/**
 * 执行 AI 任务
 */
async function executeAITask(task, url, useKnowledgeBase = true) {
  return new Promise((resolve, reject) => {
    const args = [
      '-m', 'skillweaver.attempt_task',
      url,
      task,
      '--agent-lm-name', 'gemini-3-flash',
      '--max-steps', '10'
    ];

    if (useKnowledgeBase) {
      const kbPath = path.join(__dirname, '..', 'knowledge_base', 'general_kb');
      args.push('--knowledge-base-path-prefix', kbPath);
    }

    console.log('[AI] 执行任务:', task);
    console.log('[AI] 命令:', 'python', args.join(' '));

    const startTime = Date.now();

    const process = spawn('python', args, {
      cwd: path.join(__dirname, '..', 'SkillWeaver'),
      env: { ...process.env }
    });

    let output = '';
    let error = '';

    process.stdout.on('data', (data) => {
      output += data.toString();
      console.log('[AI stdout]', data.toString());
    });

    process.stderr.on('data', (data) => {
      error += data.toString();
      console.error('[AI stderr]', data.toString());
    });

    process.on('close', (code) => {
      const elapsed = (Date.now() - startTime) / 1000;
      
      if (code === 0) {
        resolve({
          success: true,
          output,
          time: elapsed,
          task
        });
      } else {
        reject({
          success: false,
          error: error || `Process exited with code ${code}`,
          time: elapsed,
          task
        });
      }
    });

    process.on('error', (err) => {
      reject({
        success: false,
        error: err.message,
        task
      });
    });
  });
}

/**
 * 学习网站操作
 */
async function learnWebsite(url, iterations = 10) {
  return new Promise((resolve, reject) => {
    const siteName = new URL(url).hostname.replace(/\./g, '_');
    const outputDir = path.join(__dirname, '..', 'knowledge_base', siteName);

    const args = [
      '-m', 'skillweaver.explore',
      url,
      outputDir,
      '--agent-lm-name', 'claude-opus-4-5-20251124',
      '--iterations', iterations.toString()
    ];

    console.log('[AI] 学习网站:', url);

    const process = spawn('python', args, {
      cwd: path.join(__dirname, '..', 'SkillWeaver'),
      env: { ...process.env }
    });

    let output = '';

    process.stdout.on('data', (data) => {
      output += data.toString();
      // 发送进度到渲染进程
      mainWindow?.webContents.send('ai:learnProgress', data.toString());
    });

    process.on('close', (code) => {
      if (code === 0) {
        resolve({
          success: true,
          knowledgeBasePath: outputDir,
          output
        });
      } else {
        reject({
          success: false,
          error: `Learning failed with code ${code}`
        });
      }
    });
  });
}

// IPC 处理
ipcMain.handle('ai:executeTask', async (event, { task, url, useKnowledgeBase }) => {
  try {
    const result = await executeAITask(task, url, useKnowledgeBase);
    return result;
  } catch (error) {
    return error;
  }
});

ipcMain.handle('ai:learnWebsite', async (event, { url, iterations }) => {
  try {
    const result = await learnWebsite(url, iterations);
    return result;
  } catch (error) {
    return error;
  }
});

ipcMain.handle('ai:getStatus', () => {
  return aiEngineStatus;
});

// 应用生命周期
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

console.log('[AI Browser] 启动中...');
