/**
 * Drag Connector - 拖拽连接器模块
 * 
 * 实现拖拽连接器功能：
 * 1. 创建全屏透明 Overlay
 * 2. 追踪鼠标位置，获取鼠标下的窗口
 * 3. 高亮目标窗口
 * 4. 松开时返回目标窗口信息
 */

const { BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');

let dragOverlayWindow = null;
let isActive = false;
let targetWindowInfo = null;
let pollInterval = null;

// Windows API（通过 koffi）
let koffi = null;
let user32 = null;
let WindowFromPoint = null;
let GetWindowTextW = null;
let GetWindowRect = null;
let GetCursorPos = null;
let GetAsyncKeyState = null;
let GetAncestor = null;

// 常量
const VK_LBUTTON = 0x01; // 鼠标左键
const GA_ROOT = 2; // GetAncestor: 获取根窗口

try {
  koffi = require('koffi');
  user32 = koffi.load('user32.dll');
  
  // 定义类型
  const POINT = koffi.struct('POINT', {
    x: 'long',
    y: 'long',
  });
  
  const RECT = koffi.struct('RECT', {
    left: 'long',
    top: 'long',
    right: 'long',
    bottom: 'long',
  });
  
  // 绑定函数
  // 注意：用 'int' 代替 'void*' 以获取数值类型的 HWND
  WindowFromPoint = user32.func('WindowFromPoint', 'int', [POINT]);
  GetWindowTextW = user32.func('GetWindowTextW', 'int', ['int', 'str16', 'int']);
  GetWindowRect = user32.func('GetWindowRect', 'bool', ['int', koffi.out(koffi.pointer(RECT))]);
  GetCursorPos = user32.func('GetCursorPos', 'bool', [koffi.out(koffi.pointer(POINT))]);
  GetAsyncKeyState = user32.func('GetAsyncKeyState', 'short', ['int']);
  GetAncestor = user32.func('GetAncestor', 'int', ['int', 'uint']);
  
  console.log('[DragConnector] koffi loaded, Windows API available');
} catch (e) {
  console.log('[DragConnector] koffi not available:', e.message);
}

/**
 * 检测鼠标左键是否按下
 */
function isMouseButtonDown() {
  if (!GetAsyncKeyState) return true; // 如果 API 不可用，假设按下
  try {
    const state = GetAsyncKeyState(VK_LBUTTON);
    // 如果最高位为 1，表示按键当前被按下
    return (state & 0x8000) !== 0;
  } catch (e) {
    return true;
  }
}

// 获取所有显示器的总尺寸（用于过滤）
function getTotalScreenSize() {
  const displays = screen.getAllDisplays();
  let totalWidth = 0, totalHeight = 0;
  for (const d of displays) {
    totalWidth += d.bounds.width;
    totalHeight = Math.max(totalHeight, d.bounds.height);
  }
  return { totalWidth, totalHeight };
}

/**
 * 获取鼠标位置下的窗口信息
 */
function getWindowUnderCursor() {
  if (!WindowFromPoint || !GetCursorPos) {
    return null;
  }
  
  try {
    // 获取鼠标位置
    const point = { x: 0, y: 0 };
    GetCursorPos(point);
    
    // 获取该位置的窗口句柄
    let hwnd = WindowFromPoint(point);
    if (!hwnd || hwnd === 0) return null;
    
    // 获取根窗口（避免获取到子窗口如 "Chrome Legacy Window"）
    if (GetAncestor) {
      const rootHwnd = GetAncestor(hwnd, GA_ROOT);
      if (rootHwnd && rootHwnd !== 0) {
        hwnd = rootHwnd;
      }
    }
    
    // 获取窗口标题
    const buffer = Buffer.alloc(512);
    const length = GetWindowTextW(hwnd, buffer, 256);
    const title = buffer.toString('utf16le', 0, length * 2);
    
    if (!title || title.length < 2) return null;
    
    // 获取窗口位置
    const rect = { left: 0, top: 0, right: 0, bottom: 0 };
    GetWindowRect(hwnd, rect);
    
    const width = rect.right - rect.left;
    const height = rect.bottom - rect.top;
    
    // 过滤掉明显不是应用窗口的窗口
    const { totalWidth, totalHeight } = getTotalScreenSize();
    
    // 排除：覆盖整个屏幕的窗口（可能是桌面或隐藏窗口）
    if (width >= totalWidth * 0.95 && height >= totalHeight * 0.95) {
      return null;
    }
    
    // 排除：太小的窗口
    if (width < 100 || height < 50) {
      return null;
    }
    
    // 排除：系统窗口
    const lowerTitle = title.toLowerCase();
    if (lowerTitle === 'program manager' || 
        lowerTitle.includes('taskbar') ||
        lowerTitle.includes('start menu')) {
      return null;
    }
    
    return {
      hwnd: hwnd,
      title,
      x: rect.left,
      y: rect.top,
      width: width,
      height: height,
      cursorX: point.x,
      cursorY: point.y,
    };
  } catch (e) {
    console.error('[DragConnector] Error getting window:', e);
    return null;
  }
}

// 当前 overlay 覆盖的显示器
let currentDisplay = null;

/**
 * 创建或更新拖拽 Overlay 窗口（动态跟随鼠标所在的显示器）
 */
function createDragOverlay() {
  // 获取鼠标所在的显示器
  const cursorPoint = screen.getCursorScreenPoint();
  const display = screen.getDisplayNearestPoint(cursorPoint);
  
  // 如果已有窗口且在同一显示器，直接返回
  if (dragOverlayWindow && !dragOverlayWindow.isDestroyed() && currentDisplay === display.id) {
    return dragOverlayWindow;
  }
  
  // 如果切换了显示器，销毁旧窗口
  if (dragOverlayWindow && !dragOverlayWindow.isDestroyed()) {
    dragOverlayWindow.close();
    dragOverlayWindow = null;
  }
  
  currentDisplay = display.id;
  
  // 使用显示器的边界（逻辑像素）
  const { x, y, width, height } = display.bounds;
  
  console.log('[DragConnector] Creating overlay on display:', {
    id: display.id,
    bounds: display.bounds,
    scaleFactor: display.scaleFactor,
  });
  
  dragOverlayWindow = new BrowserWindow({
    x: x,
    y: y,
    width: width,
    height: height,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: false,
    resizable: false,
    movable: false,
    hasShadow: false,
    type: 'toolbar',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });
  
  // 设置为最顶层
  dragOverlayWindow.setAlwaysOnTop(true, 'screen-saver');
  
  // 允许鼠标穿透
  dragOverlayWindow.setIgnoreMouseEvents(true);
  
  // 加载 Overlay 内容
  dragOverlayWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(generateOverlayHTML())}`);
  
  return dragOverlayWindow;
}

/**
 * 生成 Overlay HTML - Premium 视觉效果
 */
function generateOverlayHTML() {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    body { 
      background: rgba(0, 0, 0, 0.6); 
      overflow: hidden; 
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      backdrop-filter: blur(2px);
    }
    
    /* ============== 扫描线背景效果 ============== */
    .scan-effect {
      position: fixed;
      inset: 0;
      background: 
        repeating-linear-gradient(
          0deg,
          transparent,
          transparent 2px,
          rgba(16, 185, 129, 0.03) 2px,
          rgba(16, 185, 129, 0.03) 4px
        );
      pointer-events: none;
      animation: scanMove 8s linear infinite;
    }
    
    @keyframes scanMove {
      0% { transform: translateY(0); }
      100% { transform: translateY(100px); }
    }
    
    /* ============== 高亮框 - Premium 样式 ============== */
    #highlight {
      position: fixed;
      pointer-events: none;
      display: none;
      /* 不使用 border，用伪元素做角标 */
    }
    
    /* 四角 L 形标记 */
    .corner {
      position: absolute;
      width: 32px;
      height: 32px;
      pointer-events: none;
    }
    .corner::before, .corner::after {
      content: '';
      position: absolute;
      background: #10b981;
      box-shadow: 0 0 12px rgba(16, 185, 129, 0.8), 0 0 24px rgba(16, 185, 129, 0.4);
    }
    .corner::before { height: 4px; width: 32px; }
    .corner::after { width: 4px; height: 32px; }
    
    .corner-tl { top: 0; left: 0; }
    .corner-tl::before { top: 0; left: 0; }
    .corner-tl::after { top: 0; left: 0; }
    
    .corner-tr { top: 0; right: 0; }
    .corner-tr::before { top: 0; right: 0; }
    .corner-tr::after { top: 0; right: 0; }
    
    .corner-bl { bottom: 0; left: 0; }
    .corner-bl::before { bottom: 0; left: 0; }
    .corner-bl::after { bottom: 0; left: 0; }
    
    .corner-br { bottom: 0; right: 0; }
    .corner-br::before { bottom: 0; right: 0; }
    .corner-br::after { bottom: 0; right: 0; }
    
    /* 边框发光效果 */
    .glow-border {
      position: absolute;
      inset: 0;
      border: 2px solid rgba(16, 185, 129, 0.4);
      border-radius: 8px;
      box-shadow: 
        inset 0 0 30px rgba(16, 185, 129, 0.1),
        0 0 20px rgba(16, 185, 129, 0.3);
      animation: borderPulse 2s ease-in-out infinite;
    }
    
    @keyframes borderPulse {
      0%, 100% { opacity: 0.6; box-shadow: inset 0 0 30px rgba(16, 185, 129, 0.1), 0 0 20px rgba(16, 185, 129, 0.3); }
      50% { opacity: 1; box-shadow: inset 0 0 40px rgba(16, 185, 129, 0.15), 0 0 40px rgba(16, 185, 129, 0.5); }
    }
    
    /* 扫描线动画 */
    .highlight-scan {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, transparent, #10b981, transparent);
      box-shadow: 0 0 20px #10b981;
      animation: highlightScan 1.5s ease-in-out infinite;
    }
    
    @keyframes highlightScan {
      0% { top: 0; opacity: 1; }
      100% { top: 100%; opacity: 0.3; }
    }
    
    /* ============== 光标图标 - Premium ============== */
    #cursor {
      position: fixed;
      width: 56px;
      height: 56px;
      pointer-events: none;
      transform: translate(-50%, -50%);
      transition: transform 0.1s ease;
    }
    
    .cursor-ring {
      position: absolute;
      inset: 0;
      border: 3px solid #10b981;
      border-radius: 50%;
      box-shadow: 0 0 20px rgba(16, 185, 129, 0.6);
      animation: cursorPulse 1.5s ease-in-out infinite;
    }
    
    @keyframes cursorPulse {
      0%, 100% { transform: scale(1); opacity: 1; }
      50% { transform: scale(1.1); opacity: 0.8; }
    }
    
    .cursor-inner {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, #10b981, #059669);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }
    
    .cursor-inner::before, .cursor-inner::after {
      content: '';
      position: absolute;
      background: white;
      border-radius: 2px;
    }
    .cursor-inner::before { width: 16px; height: 3px; }
    .cursor-inner::after { width: 3px; height: 16px; }
    
    #cursor.on-target {
      transform: translate(-50%, -50%) scale(1.2);
    }
    #cursor.on-target .cursor-ring {
      border-color: #22c55e;
      box-shadow: 0 0 30px rgba(34, 197, 94, 0.8);
    }
    
    /* ============== Tooltip - Premium ============== */
    #tooltip {
      position: fixed;
      pointer-events: none;
      display: none;
      transform: translateY(8px);
      opacity: 0;
      transition: all 0.2s ease;
    }
    
    #tooltip.active {
      display: block;
      transform: translateY(0);
      opacity: 1;
    }
    
    .tooltip-card {
      background: rgba(10, 10, 10, 0.95);
      backdrop-filter: blur(20px);
      border: 1px solid rgba(16, 185, 129, 0.3);
      border-radius: 12px;
      padding: 12px 18px;
      box-shadow: 
        0 8px 32px rgba(0, 0, 0, 0.4),
        0 0 20px rgba(16, 185, 129, 0.2);
    }
    
    .tooltip-label {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #10b981;
      margin-bottom: 4px;
    }
    
    .tooltip-title {
      font-size: 14px;
      font-weight: 600;
      color: white;
      max-width: 250px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    
    /* ============== 底部提示 - Premium ============== */
    #hint {
      position: fixed;
      bottom: 60px;
      left: 50%;
      transform: translateX(-50%);
      animation: hintFloat 3s ease-in-out infinite;
    }
    
    @keyframes hintFloat {
      0%, 100% { transform: translateX(-50%) translateY(0); }
      50% { transform: translateX(-50%) translateY(-8px); }
    }
    
    .hint-card {
      background: rgba(10, 10, 10, 0.9);
      backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 16px;
      padding: 16px 28px;
      display: flex;
      align-items: center;
      gap: 14px;
      box-shadow: 0 8px 40px rgba(0, 0, 0, 0.4);
    }
    
    .hint-icon {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, #10b981, #059669);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }
    
    .hint-icon svg {
      width: 22px;
      height: 22px;
      stroke: white;
      stroke-width: 2.5;
      fill: none;
    }
    
    .hint-text {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    
    .hint-main {
      font-size: 14px;
      font-weight: 600;
      color: white;
    }
    
    .hint-sub {
      font-size: 12px;
      color: rgba(255, 255, 255, 0.5);
    }
    
    /* ============== 入场动画 ============== */
    body {
      animation: fadeIn 0.3s ease;
    }
    
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    
    #hint {
      animation: hintFloat 3s ease-in-out infinite, slideUp 0.4s ease 0.1s both;
    }
    
    @keyframes slideUp {
      from { opacity: 0; transform: translateX(-50%) translateY(20px); }
      to { opacity: 1; transform: translateX(-50%) translateY(0); }
    }
  </style>
</head>
<body>
  <div class="scan-effect"></div>
  
  <div id="highlight">
    <div class="glow-border"></div>
    <div class="highlight-scan"></div>
    <div class="corner corner-tl"></div>
    <div class="corner corner-tr"></div>
    <div class="corner corner-bl"></div>
    <div class="corner corner-br"></div>
  </div>
  
  <div id="cursor">
    <div class="cursor-ring"></div>
    <div class="cursor-inner"></div>
  </div>
  
  <div id="tooltip">
    <div class="tooltip-card">
      <div class="tooltip-label">Connect to</div>
      <div class="tooltip-title" id="tooltipTitle"></div>
    </div>
  </div>
  
  <div id="hint">
    <div class="hint-card">
      <div class="hint-icon">
        <svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 8v8M8 12h8"/>
        </svg>
      </div>
      <div class="hint-text">
        <span class="hint-main">Release to connect</span>
        <span class="hint-sub">Move cursor to target window</span>
      </div>
    </div>
  </div>
  
  <script>
    const highlight = document.getElementById('highlight');
    const tooltip = document.getElementById('tooltip');
    const tooltipTitle = document.getElementById('tooltipTitle');
    const cursor = document.getElementById('cursor');
    
    window.updateCursor = function(x, y) {
      cursor.style.left = x + 'px';
      cursor.style.top = y + 'px';
    };
    
    window.showHighlight = function(x, y, w, h, title, cx, cy) {
      highlight.style.display = 'block';
      highlight.style.left = x + 'px';
      highlight.style.top = y + 'px';
      highlight.style.width = w + 'px';
      highlight.style.height = h + 'px';
      
      cursor.classList.add('on-target');
      
      tooltip.classList.add('active');
      tooltipTitle.textContent = title;
      tooltip.style.left = (cx + 30) + 'px';
      tooltip.style.top = (cy + 30) + 'px';
    };
    
    window.hideHighlight = function() {
      highlight.style.display = 'none';
      cursor.classList.remove('on-target');
      tooltip.classList.remove('active');
    };
    
    // 入场音效
    try {
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 800;
      gain.gain.setValueAtTime(0.1, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    } catch(e) {}
    
    console.log('[DragOverlay] Premium mode ready');
  </script>
</body>
</html>`;
}

// 存储 mainWindow 引用
let mainWindowRef = null;

/**
 * 启动拖拽模式
 */
function startDragMode(mainWindow) {
  if (isActive) return { success: false, reason: 'Already active' };
  
  isActive = true;
  targetWindowInfo = null;
  mainWindowRef = mainWindow;
  
  // 创建 Overlay
  createDragOverlay();
  dragOverlayWindow.show();
  
  // 等待页面加载完成
  dragOverlayWindow.webContents.on('did-finish-load', () => {
    console.log('[DragConnector] Overlay page loaded');
  });
  
  // 开始轮询鼠标位置 + 检测鼠标释放
  let lastHwnd = 0;
  let mouseWasDown = true; // 开始时鼠标是按下的
  
  pollInterval = setInterval(() => {
    // 检测鼠标是否释放
    const mouseDown = isMouseButtonDown();
    
    if (mouseWasDown && !mouseDown) {
      // 鼠标刚刚释放！使用最后有效的目标窗口
      console.log('[DragConnector] Mouse released, using last valid target:', targetWindowInfo?.title);
      
      // 直接使用已保存的 targetWindowInfo，不要再检测
      const finalTarget = targetWindowInfo ? {
        hwnd: targetWindowInfo.hwnd,
        title: targetWindowInfo.title,
      } : null;
      
      // 结束拖拽模式
      endDragMode();
      
      // 通知渲染进程连接完成
      if (mainWindowRef && !mainWindowRef.isDestroyed() && finalTarget) {
        console.log('[DragConnector] Sending complete event with target:', finalTarget);
        mainWindowRef.webContents.send('drag-connector:complete', finalTarget);
      }
      return;
    }
    mouseWasDown = mouseDown;
    
    // 检查是否需要切换显示器（鼠标移到另一个显示器）
    const cursorScreenPoint = screen.getCursorScreenPoint();
    const currentDisplayNow = screen.getDisplayNearestPoint(cursorScreenPoint);
    
    if (currentDisplay !== currentDisplayNow.id) {
      // 鼠标移到了另一个显示器，重新创建 overlay
      console.log('[DragConnector] Mouse moved to different display, recreating overlay');
      if (dragOverlayWindow && !dragOverlayWindow.isDestroyed()) {
        dragOverlayWindow.close();
        dragOverlayWindow = null;
      }
      createDragOverlay();
      // 加载 HTML
      dragOverlayWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(generateOverlayHTML())}`);
    }
    
    // 获取当前鼠标位置
    let cursorX = 0, cursorY = 0;
    
    if (GetCursorPos && dragOverlayWindow && !dragOverlayWindow.isDestroyed()) {
      const point = { x: 0, y: 0 };
      GetCursorPos(point);
      
      // 获取当前显示器信息
      const display = screen.getDisplayNearestPoint({ x: point.x, y: point.y });
      const scaleFactor = display.scaleFactor || 1;
      
      // 获取 overlay 窗口边界（逻辑像素）
      const overlayBounds = dragOverlayWindow.getBounds();
      
      // 转换：物理像素 -> 相对于 overlay 的逻辑像素
      // Windows API 返回物理像素，需要除以 scaleFactor 转换为逻辑像素
      cursorX = Math.round((point.x / scaleFactor) - overlayBounds.x);
      cursorY = Math.round((point.y / scaleFactor) - overlayBounds.y);
      
      // 更新光标图标位置
      dragOverlayWindow.webContents.executeJavaScript(`window.updateCursor(${cursorX}, ${cursorY})`).catch(() => {});
    }
    
    // 窗口检测
    const windowInfo = getWindowUnderCursor();
    
    if (windowInfo) {
      // 获取当前显示器的 DPI 缩放
      const display = screen.getDisplayNearestPoint({ x: windowInfo.x + 10, y: windowInfo.y + 10 });
      const scaleFactor = display.scaleFactor || 1;
      
      // 获取 overlay 窗口边界（逻辑像素）
      const overlayBounds = dragOverlayWindow ? dragOverlayWindow.getBounds() : { x: 0, y: 0 };
      
      // 转换：物理像素 -> 相对于 overlay 的逻辑像素
      const relX = Math.round((windowInfo.x / scaleFactor) - overlayBounds.x);
      const relY = Math.round((windowInfo.y / scaleFactor) - overlayBounds.y);
      const relW = Math.round(windowInfo.width / scaleFactor);
      const relH = Math.round(windowInfo.height / scaleFactor);
      
      // 始终更新 targetWindowInfo
      targetWindowInfo = windowInfo;
      
      if (windowInfo.hwnd !== lastHwnd) {
        lastHwnd = windowInfo.hwnd;
        console.log('[DragConnector] Target window:', windowInfo.title, 'at', { relX, relY, relW, relH });
      }
      
      // 更新高亮
      // 【修复 #4】添加异常处理，防止窗口销毁时的调用错误
      // [P0-6 FIX] 使用安全的参数传递，避免 XSS 注入
      if (dragOverlayWindow && !dragOverlayWindow.isDestroyed()) {
        try {
          // [P0-6 FIX] 使用 JSON.stringify 安全转义字符串，防止 XSS
          const safeParams = JSON.stringify({
            x: relX,
            y: relY,
            w: relW,
            h: relH,
            title: windowInfo.title,  // JSON.stringify 会自动转义特殊字符
            cx: cursorX,
            cy: cursorY
          });
          dragOverlayWindow.webContents.executeJavaScript(
            `(function() { const p = ${safeParams}; window.showHighlight(p.x, p.y, p.w, p.h, p.title, p.cx, p.cy); })()`
          ).catch((err) => {
            console.debug('[DragConnector] executeJavaScript error:', err.message);
          });
        } catch (err) {
          console.debug('[DragConnector] Overlay update error:', err.message);
        }
      }
      
      // 通知渲染进程
      if (mainWindowRef && !mainWindowRef.isDestroyed()) {
        mainWindowRef.webContents.send('drag-connector:update', windowInfo);
      }
    } else {
      // 没有检测到有效窗口，但保留最后的 targetWindowInfo
      // 只隐藏高亮，不清除目标
      if (lastHwnd !== 0) {
        console.log('[DragConnector] No target window (keeping last valid)');
        lastHwnd = 0;
      }
      if (dragOverlayWindow && !dragOverlayWindow.isDestroyed()) {
        dragOverlayWindow.webContents.executeJavaScript(`window.hideHighlight()`).catch(() => {});
      }
    }
  }, 16); // ~60 FPS，更流畅的视觉反馈
  
  console.log('[DragConnector] Drag mode started');
  return { success: true };
}

/**
 * 结束拖拽模式
 */
function endDragMode() {
  if (!isActive) return { success: false, target: null };
  
  isActive = false;
  
  // 停止轮询
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
  
  // 关闭 Overlay
  if (dragOverlayWindow && !dragOverlayWindow.isDestroyed()) {
    dragOverlayWindow.close();
    dragOverlayWindow = null;
  }
  
  const result = {
    success: true,
    target: targetWindowInfo ? {
      hwnd: targetWindowInfo.hwnd,
      title: targetWindowInfo.title,
    } : null,
  };
  
  targetWindowInfo = null;
  
  console.log('[DragConnector] Drag mode ended, target:', result.target);
  return result;
}

/**
 * 设置 IPC 处理器
 */
function setupDragConnectorIPC(mainWindow) {
  ipcMain.handle('drag-connector:start', async () => {
    return startDragMode(mainWindow);
  });
  
  ipcMain.handle('drag-connector:end', async () => {
    return endDragMode();
  });
  
  console.log('[DragConnector] IPC handlers registered');
}

module.exports = {
  setupDragConnectorIPC,
  startDragMode,
  endDragMode,
  isActive: () => isActive,
};

