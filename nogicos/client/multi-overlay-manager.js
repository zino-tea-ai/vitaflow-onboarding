/**
 * NogicOS Multi-Overlay Manager
 * 
 * Phase 1: 基础 Overlay 窗口（创建/销毁/显示/隐藏）
 * Phase 2: 位置跟踪（跟随目标窗口移动）
 * 
 * 这是一个纯 Electron 实现，不依赖 electron-overlay-window
 * 支持多窗口同时管理
 * 
 * @author NogicOS Team
 * @version 2.0.0 - Phase 2
 */

const { BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');

// ============== Windows API (via koffi) ==============
let koffi = null;
let user32 = null;
let GetWindowRect = null;
let IsIconic = null;
let IsWindowVisible = null;
let GetForegroundWindow = null;

try {
  koffi = require('koffi');
  user32 = koffi.load('user32.dll');
  
  // 定义 RECT 结构
  const RECT = koffi.struct('RECT_OVERLAY', {
    left: 'long',
    top: 'long',
    right: 'long',
    bottom: 'long',
  });
  
  // 绑定 Windows API 函数
  GetWindowRect = user32.func('GetWindowRect', 'bool', ['void*', koffi.out(koffi.pointer(RECT))]);
  IsIconic = user32.func('IsIconic', 'bool', ['void*']);
  IsWindowVisible = user32.func('IsWindowVisible', 'bool', ['void*']);
  // 用 'long' 返回 HWND，直接得到数字（而不是 void* 指针对象）
  GetForegroundWindow = user32.func('GetForegroundWindow', 'long', []);
  
  console.log('[MultiOverlay] koffi loaded, Windows API available');
} catch (e) {
  console.log('[MultiOverlay] koffi not available:', e.message);
}

// 轮询间隔（30fps = 33ms）
const POLL_INTERVAL_MS = 8; // ~120fps for smoother tracking

/**
 * Overlay 实例状态
 */
const OverlayState = {
  IDLE: 'idle',
  ATTACHED: 'attached',
  HIDDEN: 'hidden',
  ERROR: 'error',
};

/**
 * 检查目标窗口的完整状态
 * @param {number} hwnd - 窗口句柄
 * @returns {{
 *   isMinimized: boolean,
 *   isVisible: boolean,
 *   isForeground: boolean,
 *   isFullyCovered: boolean,
 *   shouldShowOverlay: boolean
 * }}
 */
function getWindowState(hwnd) {
  const state = {
    isMinimized: false,
    isVisible: true,
    isForeground: false,
    isFullyCovered: false,
    shouldShowOverlay: false,
  };
  
  // 检查最小化
  state.isMinimized = isWindowMinimized(hwnd);
  if (state.isMinimized) {
    return state;
  }
  
  // 检查可见性
  state.isVisible = isWindowVisibleNative(hwnd);
  if (!state.isVisible) {
    return state;
  }
  
  // 检查是否是前台窗口
  state.isForeground = isWindowForeground(hwnd);
  if (state.isForeground) {
    state.shouldShowOverlay = true;
    return state;
  }
  
  // 不是前台窗口，检查是否被完全覆盖
  const targetBounds = getWindowBounds(hwnd);
  const fgHwnd = GetForegroundWindow ? GetForegroundWindow() : 0;
  
  if (targetBounds && fgHwnd && fgHwnd !== hwnd) {
    const fgBounds = getWindowBounds(fgHwnd);
    if (fgBounds) {
      // 检查前台窗口是否完全覆盖目标窗口
      state.isFullyCovered = (
        fgBounds.x <= targetBounds.x &&
        fgBounds.y <= targetBounds.y &&
        fgBounds.x + fgBounds.width >= targetBounds.x + targetBounds.width &&
        fgBounds.y + fgBounds.height >= targetBounds.y + targetBounds.height
      );
    }
  }
  
  // 如果没有被完全覆盖，显示 Overlay
  state.shouldShowOverlay = !state.isFullyCovered;
  
  return state;
}

/**
 * 获取目标窗口的位置和大小
 * @param {number} hwnd - 窗口句柄
 * @returns {{x: number, y: number, width: number, height: number} | null}
 */
function getWindowBounds(hwnd) {
  if (!GetWindowRect) {
    return null;
  }

  try {
    const rect = { left: 0, top: 0, right: 0, bottom: 0 };

    // 直接传数字，koffi 会自动处理 void* 转换
    const success = GetWindowRect(hwnd, rect);
    if (!success) {
      return null;
    }

    const width = rect.right - rect.left;
    const height = rect.bottom - rect.top;

    // 【修复 #5】多显示器窗口过滤 - 过滤掉无效或超大窗口
    const displays = screen.getAllDisplays();
    let totalWidth = 0, totalHeight = 0;
    for (const d of displays) {
      totalWidth += d.bounds.width;
      totalHeight = Math.max(totalHeight, d.bounds.height);
    }

    // 过滤掉覆盖整个屏幕或无效尺寸的窗口
    if (width <= 0 || height <= 0) {
      return null;
    }
    if (width >= totalWidth * 0.99 && height >= totalHeight * 0.99) {
      return null;
    }

    return {
      x: rect.left,
      y: rect.top,
      width: width,
      height: height,
    };
  } catch (e) {
    console.error('[MultiOverlay] GetWindowRect error:', e.message);
    return null;
  }
}

/**
 * 检查窗口是否最小化
 * @param {number} hwnd
 * @returns {boolean}
 */
function isWindowMinimized(hwnd) {
  if (!IsIconic) {
    return false;
  }
  
  try {
    // 直接传数字
    return IsIconic(hwnd);
  } catch (e) {
    return false;
  }
}

/**
 * 检查窗口是否可见
 * @param {number} hwnd
 * @returns {boolean}
 */
function isWindowVisibleNative(hwnd) {
  if (!IsWindowVisible) {
    return true; // 默认可见
  }
  
  try {
    // 直接传数字
    return IsWindowVisible(hwnd);
  } catch (e) {
    return true;
  }
}

/**
 * 检查窗口是否在前台（未被遮挡）
 * @param {number} hwnd
 * @returns {boolean}
 */
function isWindowForeground(hwnd) {
  if (!GetForegroundWindow) {
    return true; // 默认前台
  }
  
  try {
    // GetForegroundWindow 现在返回 long（数字），可以直接比较
    const foregroundHwnd = GetForegroundWindow();
    return foregroundHwnd === hwnd;
  } catch (e) {
    console.error('[MultiOverlay] isWindowForeground error:', e.message);
    return true;
  }
}

/**
 * 单个 Overlay 实例
 */
class OverlayInstance {
  constructor(hwnd, hookType) {
    this.hwnd = hwnd;
    this.hookType = hookType;
    this.window = null;
    this.state = OverlayState.IDLE;
    this.pollInterval = null;
    this.lastBounds = null;
    this.isTracking = false;
  }

  /**
   * 检查实例是否存活
   */
  isAlive() {
    return this.window && !this.window.isDestroyed();
  }
}

/**
 * Multi-Overlay Manager
 * 管理多个 Overlay 窗口实例
 */
class MultiOverlayManager {
  constructor() {
    /** @type {Map<number, OverlayInstance>} hwnd -> OverlayInstance */
    this._overlays = new Map();
    this._isAvailable = true;
  }

  /**
   * 检查功能是否可用
   */
  get isAvailable() {
    return this._isAvailable;
  }

  /**
   * 获取当前活跃的 Overlay 数量
   */
  get activeCount() {
    return this._overlays.size;
  }

  /**
   * 创建 Overlay 窗口（Phase 1 核心）
   * @param {number} hwnd - 目标窗口句柄
   * @param {string} hookType - Hook 类型 (browser, desktop)
   * @param {string} targetTitle - 目标窗口标题
   * @returns {{success: boolean, error?: string}}
   */
  createOverlay(hwnd, hookType, targetTitle = '') {
    console.log(`[MultiOverlay] Creating overlay for HWND: ${hwnd}, type: ${hookType}`);
    
    // 检查是否已存在
    if (this._overlays.has(hwnd)) {
      const existing = this._overlays.get(hwnd);
      if (existing.isAlive()) {
        console.log(`[MultiOverlay] Overlay already exists for HWND: ${hwnd}`);
        return { success: true, reused: true };
      } else {
        // 清理死亡实例
        this._overlays.delete(hwnd);
      }
    }

    try {
      // 创建实例
      const instance = new OverlayInstance(hwnd, hookType);

      // 创建 BrowserWindow
      instance.window = new BrowserWindow({
        width: 400,
        height: 36,
        x: 100,  // 初始位置（Phase 2 会动态更新）
        y: 100,
        
        // 关键配置
        transparent: true,
        frame: false,
        alwaysOnTop: true,
        skipTaskbar: true,
        focusable: false,  // 不抢焦点
        resizable: false,
        movable: false,
        hasShadow: false,
        
        // Windows 特殊设置
        type: 'toolbar',  // 工具窗口类型
        
        webPreferences: {
          nodeIntegration: false,
          contextIsolation: true,
        },
      });

      // 鼠标穿透
      instance.window.setIgnoreMouseEvents(true);
      
      // 置顶级别
      instance.window.setAlwaysOnTop(true, 'screen-saver');

      // 加载 HTML
      const html = this._generateOverlayHTML(hookType, targetTitle);
      instance.window.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);

      // 监听窗口关闭
      instance.window.on('closed', () => {
        console.log(`[MultiOverlay] Window closed for HWND: ${hwnd}`);
        this._overlays.delete(hwnd);
      });

      // 保存实例
      instance.state = OverlayState.ATTACHED;
      this._overlays.set(hwnd, instance);

      // Phase 2: 自动开始位置跟踪
      this.startTracking(hwnd);

      console.log(`[MultiOverlay] Overlay created successfully for HWND: ${hwnd}`);
      return { success: true };

    } catch (e) {
      console.error(`[MultiOverlay] Failed to create overlay:`, e);
      return { success: false, error: e.message };
    }
  }

  /**
   * 显示 Overlay
   * @param {number} hwnd - 目标窗口句柄
   */
  showOverlay(hwnd) {
    const instance = this._overlays.get(hwnd);
    if (!instance || !instance.isAlive()) {
      console.warn(`[MultiOverlay] No overlay found for HWND: ${hwnd}`);
      return { success: false, error: 'Overlay not found' };
    }

    instance.window.showInactive();
    instance.state = OverlayState.ATTACHED;
    console.log(`[MultiOverlay] Overlay shown for HWND: ${hwnd}`);
    return { success: true };
  }

  /**
   * 隐藏 Overlay
   * @param {number} hwnd - 目标窗口句柄
   */
  hideOverlay(hwnd) {
    const instance = this._overlays.get(hwnd);
    if (!instance || !instance.isAlive()) {
      console.warn(`[MultiOverlay] No overlay found for HWND: ${hwnd}`);
      return { success: false, error: 'Overlay not found' };
    }

    instance.window.hide();
    instance.state = OverlayState.HIDDEN;
    console.log(`[MultiOverlay] Overlay hidden for HWND: ${hwnd}`);
    return { success: true };
  }

  /**
   * 销毁 Overlay
   * @param {number} hwnd - 目标窗口句柄
   */
  destroyOverlay(hwnd) {
    const instance = this._overlays.get(hwnd);
    if (!instance) {
      console.warn(`[MultiOverlay] No overlay found for HWND: ${hwnd}`);
      return { success: false, error: 'Overlay not found' };
    }

    // 停止轮询（Phase 2）
    if (instance.pollInterval) {
      clearInterval(instance.pollInterval);
      instance.pollInterval = null;
    }

    // 销毁窗口
    if (instance.isAlive()) {
      instance.window.destroy();
    }

    // 移除实例
    this._overlays.delete(hwnd);
    console.log(`[MultiOverlay] Overlay destroyed for HWND: ${hwnd}`);
    return { success: true };
  }

  /**
   * 销毁所有 Overlay
   */
  destroyAll() {
    const hwnds = Array.from(this._overlays.keys());
    hwnds.forEach(hwnd => this.destroyOverlay(hwnd));
    console.log(`[MultiOverlay] All overlays destroyed, count: ${hwnds.length}`);
    return { success: true, count: hwnds.length };
  }

  /**
   * 开始跟踪目标窗口位置（Phase 2）
   * @param {number} hwnd - 目标窗口句柄
   */
  startTracking(hwnd) {
    const instance = this._overlays.get(hwnd);
    if (!instance || !instance.isAlive()) {
      console.warn(`[MultiOverlay] Cannot start tracking, overlay not found: ${hwnd}`);
      return { success: false, error: 'Overlay not found' };
    }

    // 如果已经在跟踪，先停止
    if (instance.pollInterval) {
      clearInterval(instance.pollInterval);
    }

    console.log(`[MultiOverlay] Starting position tracking for HWND: ${hwnd}`);

    // 立即同步一次位置
    this._syncPosition(instance);

    // 开始轮询（30fps）
    instance.pollInterval = setInterval(() => {
      this._syncPosition(instance);
    }, POLL_INTERVAL_MS);

    instance.isTracking = true;
    return { success: true };
  }

  /**
   * 停止跟踪目标窗口位置
   * @param {number} hwnd - 目标窗口句柄
   */
  stopTracking(hwnd) {
    const instance = this._overlays.get(hwnd);
    if (!instance) {
      return { success: false, error: 'Overlay not found' };
    }

    if (instance.pollInterval) {
      clearInterval(instance.pollInterval);
      instance.pollInterval = null;
    }

    instance.isTracking = false;
    console.log(`[MultiOverlay] Stopped tracking for HWND: ${hwnd}`);
    return { success: true };
  }

  /**
   * 同步 Overlay 位置到目标窗口（私有方法）
   * @private
   * @param {OverlayInstance} instance
   */
  _syncPosition(instance) {
    if (!instance.isAlive()) {
      this.stopTracking(instance.hwnd);
      return;
    }

    // 获取窗口完整状态
    const windowState = getWindowState(instance.hwnd);
    
    /*
     * 状态逻辑：
     * - 最小化 → 隐藏
     * - 不可见 → 隐藏  
     * - 前台窗口 → 显示
     * - 不是前台但没被完全覆盖 → 显示
     * - 被完全覆盖 → 隐藏
     */
    
    if (!windowState.shouldShowOverlay) {
      if (instance.state !== OverlayState.HIDDEN) {
        instance.window.hide();
        instance.state = OverlayState.HIDDEN;
      }
      return;
    }

    // 获取目标窗口位置（物理像素）
    const physicalBounds = getWindowBounds(instance.hwnd);
    if (!physicalBounds) {
      // 窗口可能已关闭
      console.warn(`[MultiOverlay] Cannot get bounds for HWND: ${instance.hwnd}`);
      return;
    }

    // 如果之前隐藏了，恢复显示
    if (instance.state === OverlayState.HIDDEN) {
      instance.window.showInactive();
      instance.state = OverlayState.ATTACHED;
      console.log(`[MultiOverlay] Target restored, showing overlay: ${instance.hwnd}`);
    }

    // DPI 转换：物理像素 → 逻辑像素（DIP）
    // 找到目标窗口所在的显示器
    const targetPoint = { x: physicalBounds.x + 10, y: physicalBounds.y + 10 };
    const display = screen.getDisplayNearestPoint(targetPoint);
    const scaleFactor = display.scaleFactor || 1;

    // 转换坐标
    const dipBounds = {
      x: Math.round(physicalBounds.x / scaleFactor),
      y: Math.round(physicalBounds.y / scaleFactor),
      width: Math.round(physicalBounds.width / scaleFactor),
      height: Math.round(physicalBounds.height / scaleFactor),
    };

    // Overlay 覆盖整个窗口（用于入场时的全窗口边框效果）
    // 常驻时只显示顶部条+四角标记，其余区域透明
    const currentBounds = instance.window.getBounds();
    if (currentBounds.x !== dipBounds.x || 
        currentBounds.y !== dipBounds.y ||
        currentBounds.width !== dipBounds.width ||
        currentBounds.height !== dipBounds.height) {
      instance.window.setBounds({
        x: dipBounds.x,
        y: dipBounds.y,
        width: dipBounds.width,
        height: dipBounds.height,
      });
    }
  }

  /**
   * 获取所有活跃的 HWND 列表
   */
  getActiveHwnds() {
    return Array.from(this._overlays.keys());
  }

  /**
   * 获取指定 Overlay 的状态
   * @param {number} hwnd
   */
  getStatus(hwnd) {
    const instance = this._overlays.get(hwnd);
    if (!instance) {
      return { exists: false };
    }
    return {
      exists: true,
      hwnd: instance.hwnd,
      hookType: instance.hookType,
      state: instance.state,
      isAlive: instance.isAlive(),
    };
  }

  /**
   * 生成 Overlay HTML - NogicOS 深色风格（Premium版）
   * 设计理念：全窗口入场冲击 → 低调常驻 | 顶级视觉品质
   * @private
   */
  _generateOverlayHTML(hookType, targetTitle) {
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
    
    /* ============== 全窗口边框闪光（入场时） ============== */
    .border-flash {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      pointer-events: none;
      border: 3px solid rgba(16, 185, 129, 0);
      border-radius: 8px;
      animation: borderFlashIn 1.2s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }
    
    @keyframes borderFlashIn {
      0% { 
        border-color: rgba(16, 185, 129, 0);
        box-shadow: 
          inset 0 0 0 rgba(16, 185, 129, 0),
          0 0 0 rgba(16, 185, 129, 0);
      }
      15% { 
        border-color: rgba(16, 185, 129, 0.8);
        box-shadow: 
          inset 0 0 60px rgba(16, 185, 129, 0.15),
          0 0 30px rgba(16, 185, 129, 0.5);
      }
      40% {
        border-color: rgba(16, 185, 129, 0.4);
        box-shadow: 
          inset 0 0 30px rgba(16, 185, 129, 0.08),
          0 0 20px rgba(16, 185, 129, 0.3);
      }
      100% { 
        border-color: rgba(16, 185, 129, 0);
        box-shadow: 
          inset 0 0 0 rgba(16, 185, 129, 0),
          0 0 0 rgba(16, 185, 129, 0);
      }
    }
    
    /* ============== 四角 L 形标记（精确对齐 + 统一粗细） ============== */
    .corner {
      position: fixed;
      width: 24px;
      height: 24px;
      pointer-events: none;
    }
    
    .corner::before,
    .corner::after {
      content: '';
      position: absolute;
      background: #10b981;
      /* 统一粗细：3px */
    }
    
    /* 左上角 */
    .corner-tl { top: 0; left: 0; }
    .corner-tl::before { width: 24px; height: 3px; top: 0; left: 0; }
    .corner-tl::after { width: 3px; height: 24px; top: 0; left: 0; }
    
    /* 右上角 */
    .corner-tr { top: 0; right: 0; }
    .corner-tr::before { width: 24px; height: 3px; top: 0; right: 0; }
    .corner-tr::after { width: 3px; height: 24px; top: 0; right: 0; }
    
    /* 左下角 */
    .corner-bl { bottom: 0; left: 0; }
    .corner-bl::before { width: 24px; height: 3px; bottom: 0; left: 0; }
    .corner-bl::after { width: 3px; height: 24px; bottom: 0; left: 0; }
    
    /* 右下角 */
    .corner-br { bottom: 0; right: 0; }
    .corner-br::before { width: 24px; height: 3px; bottom: 0; right: 0; }
    .corner-br::after { width: 3px; height: 24px; bottom: 0; right: 0; }
    
    /* 四角入场动画：依次闪亮 */
    .corner { opacity: 0; }
    .corner::before, .corner::after {
      box-shadow: 0 0 10px rgba(16, 185, 129, 0.8);
    }
    
    .corner-tl { animation: cornerFlash 1.5s ease-out 0.1s forwards; }
    .corner-tr { animation: cornerFlash 1.5s ease-out 0.2s forwards; }
    .corner-br { animation: cornerFlash 1.5s ease-out 0.3s forwards; }
    .corner-bl { animation: cornerFlash 1.5s ease-out 0.4s forwards; }
    
    @keyframes cornerFlash {
      0% { 
        opacity: 0; 
        transform: scale(0.5);
      }
      20% { 
        opacity: 1; 
        transform: scale(1.1);
      }
      40% {
        opacity: 1;
        transform: scale(1);
      }
      100% { 
        opacity: 0.3;  /* 常驻：微弱但可见 */
        transform: scale(1);
      }
    }
    
    /* 常驻时四角微弱发光 */
    .corner::before, .corner::after {
      transition: box-shadow 0.5s ease;
    }
    
    /* ============== 扫描线（入场强 + 常驻弱循环） ============== */
    .scan-line {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 100%;
      pointer-events: none;
      background: linear-gradient(180deg,
        rgba(16, 185, 129, 0.4) 0%,
        rgba(16, 185, 129, 0.15) 1.5%,
        transparent 4%
      );
      opacity: 0;
      /* 入场强扫描 + 常驻弱循环 */
      animation: 
        scanFirst 0.8s ease-out 0.1s forwards,
        scanLoop 6s linear 2s infinite;
    }
    
    /* 入场：强烈的首次扫描 */
    @keyframes scanFirst {
      0% { 
        opacity: 1;
        transform: translateY(-100%);
      }
      100% { 
        opacity: 0;
        transform: translateY(100%);
      }
    }
    
    /* 常驻：微弱的循环扫描 */
    @keyframes scanLoop {
      0% { 
        opacity: 0;
        transform: translateY(-100%);
      }
      5% {
        opacity: 0.15;
      }
      95% {
        opacity: 0.15;
      }
      100% { 
        opacity: 0;
        transform: translateY(100%);
      }
    }
    
    /* ============== 顶部状态条 - Premium ============== */
    .overlay-container {
      position: fixed;
      top: 0;
      left: 50%;
      transform: translateX(-50%) translateY(-100%);
      width: 280px;
      height: 32px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 14px;
      
      /* Premium 毛玻璃背景 */
      background: 
        linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(6, 78, 59, 0.1) 100%),
        rgba(8, 8, 8, 0.85);
      
      border: 1px solid transparent;
      border-top: none;
      border-radius: 0 0 12px 12px;
      
      /* 高级毛玻璃 */
      backdrop-filter: blur(24px) saturate(180%);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      
      /* Premium 字体 */
      font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.2px;
      color: rgba(255, 255, 255, 0.95);
      
      /* 多层阴影 */
      box-shadow: 
        0 8px 32px rgba(16, 185, 129, 0.3),
        0 4px 16px rgba(0, 0, 0, 0.5),
        0 0 0 1px rgba(16, 185, 129, 0.4),
        inset 0 1px 0 rgba(255, 255, 255, 0.15);
      
      opacity: 0;
      
      /* 延迟入场，在边框闪光之后 */
      animation: 
        barSlideIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) 0.3s forwards,
        barSettleDown 1s ease-out 2s forwards;
    }
    
    /* 渐变边框 */
    .overlay-container::before {
      content: '';
      position: absolute;
      inset: -1px;
      border-radius: 0 0 13px 13px;
      padding: 1px;
      background: linear-gradient(180deg, 
        rgba(16, 185, 129, 0.6) 0%, 
        rgba(16, 185, 129, 0.2) 50%,
        rgba(16, 185, 129, 0.05) 100%
      );
      -webkit-mask: 
        linear-gradient(#fff 0 0) content-box, 
        linear-gradient(#fff 0 0);
      -webkit-mask-composite: xor;
      mask-composite: exclude;
      pointer-events: none;
      animation: borderFadeBar 1s ease-out 2s forwards;
    }
    
    @keyframes borderFadeBar {
      to {
        background: linear-gradient(180deg, 
          rgba(255, 255, 255, 0.1) 0%, 
          rgba(255, 255, 255, 0.03) 100%
        );
      }
    }
    
    @keyframes barSlideIn {
      0% { 
        transform: translateX(-50%) translateY(-100%) scale(0.9); 
        opacity: 0;
        filter: blur(4px);
      }
      60% { 
        transform: translateX(-50%) translateY(4px) scale(1.02); 
        opacity: 1;
        filter: blur(0);
      }
      100% { 
        transform: translateX(-50%) translateY(0) scale(1); 
        opacity: 1;
        filter: blur(0);
      }
    }
    
    /* 常驻：优雅低调 */
    @keyframes barSettleDown {
      to {
        background: 
          linear-gradient(135deg, rgba(255, 255, 255, 0.03) 0%, rgba(0, 0, 0, 0.1) 100%),
          rgba(12, 12, 12, 0.92);
        box-shadow: 
          0 4px 16px rgba(0, 0, 0, 0.4),
          0 0 0 1px rgba(255, 255, 255, 0.05),
          inset 0 1px 0 rgba(255, 255, 255, 0.08);
      }
    }
    
    /* 噪点纹理 */
    .overlay-container::after {
      content: '';
      position: absolute;
      inset: 0;
      border-radius: 0 0 12px 12px;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%' height='100%' filter='url(%23noise)'/%3E%3C/svg%3E");
      opacity: 0.03;
      mix-blend-mode: overlay;
      pointer-events: none;
    }
    
    /* ============== 状态指示器 ============== */
    .status-indicator {
      position: relative;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: radial-gradient(circle at 30% 30%, #34d399 0%, #10b981 50%, #059669 100%);
      box-shadow: 
        0 0 0 2px rgba(16, 185, 129, 0.2),
        0 0 12px rgba(16, 185, 129, 0.8),
        0 0 24px rgba(16, 185, 129, 0.4);
      animation: 
        indicatorFlash 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.4s forwards,
        indicatorPulse 4s ease-in-out 2.5s infinite;
      transform: scale(0);
    }
    
    .status-indicator::after {
      content: '';
      position: absolute;
      top: 1px;
      left: 2px;
      width: 3px;
      height: 2px;
      background: rgba(255, 255, 255, 0.6);
      border-radius: 50%;
      filter: blur(0.5px);
    }
    
    @keyframes indicatorFlash {
      0% { transform: scale(0); }
      50% { 
        transform: scale(2);
        box-shadow: 
          0 0 0 4px rgba(16, 185, 129, 0.3),
          0 0 30px rgba(16, 185, 129, 1),
          0 0 60px rgba(16, 185, 129, 0.6);
      }
      100% { 
        transform: scale(1);
        box-shadow: 
          0 0 0 2px rgba(16, 185, 129, 0.15),
          0 0 8px rgba(16, 185, 129, 0.5);
      }
    }
    
    @keyframes indicatorPulse {
      0%, 100% { 
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.1), 0 0 6px rgba(16, 185, 129, 0.4);
      }
      50% { 
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15), 0 0 10px rgba(16, 185, 129, 0.5);
      }
    }
    
    /* ============== Logo ============== */
    .logo-icon {
      width: 18px;
      height: 18px;
      border-radius: 5px;
      background: 
        linear-gradient(135deg, rgba(255,255,255,0.25) 0%, transparent 50%),
        linear-gradient(135deg, #34d399 0%, #10b981 50%, #059669 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      font-weight: 800;
      color: #fff;
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
      box-shadow: 
        0 2px 4px rgba(0, 0, 0, 0.3),
        0 4px 8px rgba(16, 185, 129, 0.3),
        inset 0 1px 0 rgba(255, 255, 255, 0.3);
      animation: logoFlash 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.35s forwards;
      transform: scale(0) rotate(-180deg);
    }
    
    @keyframes logoFlash {
      0% { transform: scale(0) rotate(-180deg); filter: brightness(0.5); }
      60% { transform: scale(1.2) rotate(10deg); filter: brightness(1.3); }
      100% { transform: scale(1) rotate(0deg); filter: brightness(1); }
    }
    
    /* ============== 其他元素 ============== */
    .divider {
      width: 1px;
      height: 14px;
      background: linear-gradient(180deg, transparent 0%, rgba(255,255,255,0.2) 50%, transparent 100%);
      opacity: 0;
      animation: fadeIn 0.4s ease-out 0.5s forwards;
    }
    
    .label {
      font-weight: 600;
      font-size: 11px;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      background: linear-gradient(90deg, #34d399 0%, #10b981 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      opacity: 0;
      animation: 
        labelIn 0.4s ease-out 0.45s forwards,
        labelSettle 1s ease-out 2s forwards;
    }
    
    @keyframes fadeIn { to { opacity: 1; } }
    @keyframes labelIn {
      0% { opacity: 0; transform: translateX(-8px); }
      100% { opacity: 1; transform: translateX(0); }
    }
    @keyframes labelSettle {
      to { 
        background: linear-gradient(90deg, rgba(52,211,153,0.7) 0%, rgba(16,185,129,0.6) 100%);
        -webkit-background-clip: text;
      }
    }
    
    .app-name {
      font-size: 10px;
      font-weight: 500;
      color: rgba(255, 255, 255, 0.5);
      max-width: 80px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      opacity: 0;
      animation: appIn 0.4s ease-out 0.55s forwards;
    }
    
    @keyframes appIn {
      0% { opacity: 0; transform: translateX(8px); }
      100% { opacity: 1; transform: translateX(0); }
    }
  </style>
</head>
<body>
  <!-- 全窗口边框闪光 -->
  <div class="border-flash"></div>
  
  <!-- 扫描线效果 -->
  <div class="scan-line"></div>
  
  <!-- 四角 L 形标记 -->
  <div class="corner corner-tl"></div>
  <div class="corner corner-tr"></div>
  <div class="corner corner-bl"></div>
  <div class="corner corner-br"></div>
  
  <!-- 顶部状态条 -->
  <div id="overlay" class="overlay-container">
    <div class="logo-icon">N</div>
    <div class="divider"></div>
    <div class="status-indicator"></div>
    <span class="label">Connected</span>
    <span class="app-name">${targetTitle || ''}</span>
  </div>
  
  <script>
    // Premium 音效 - 精致的连接音（类似 macOS 系统音效）
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
    function playPremiumConnectSound() {
      const now = audioContext.currentTime;
      
      // 主音：柔和的上升和弦
      const frequencies = [880, 1108.73, 1318.51]; // A5, C#6, E6 (A major chord)
      
      frequencies.forEach((freq, i) => {
        const osc = audioContext.createOscillator();
        const gain = audioContext.createGain();
        const filter = audioContext.createBiquadFilter();
        
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(2000, now);
        filter.frequency.exponentialRampToValueAtTime(4000, now + 0.1);
        filter.Q.value = 1;
        
        osc.connect(filter);
        filter.connect(gain);
        gain.connect(audioContext.destination);
        
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq * 0.5, now);
        osc.frequency.exponentialRampToValueAtTime(freq, now + 0.08);
        
        // 渐入渐出
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(0.06 - i * 0.015, now + 0.05);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
        
        osc.start(now + i * 0.03); // 错开时间，形成琶音效果
        osc.stop(now + 0.3);
      });
      
      // 泛音层：增加空气感
      const shimmer = audioContext.createOscillator();
      const shimmerGain = audioContext.createGain();
      shimmer.connect(shimmerGain);
      shimmerGain.connect(audioContext.destination);
      shimmer.type = 'triangle';
      shimmer.frequency.setValueAtTime(2637, now + 0.05); // E7
      shimmerGain.gain.setValueAtTime(0.02, now + 0.05);
      shimmerGain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
      shimmer.start(now + 0.05);
      shimmer.stop(now + 0.25);
    }
    
    // 延迟播放，配合视觉动画
    setTimeout(() => playPremiumConnectSound(), 180);
  </script>
</body>
</html>
    `;
  }
}

// ============== 单例管理 ==============
let multiOverlayManager = null;

function getMultiOverlayManager() {
  if (!multiOverlayManager) {
    multiOverlayManager = new MultiOverlayManager();
  }
  return multiOverlayManager;
}

// ============== IPC Handlers ==============
function setupMultiOverlayIPC() {
  const manager = getMultiOverlayManager();

  // 创建 Overlay
  ipcMain.handle('multi-overlay:create', async (event, { hwnd, hookType, targetTitle }) => {
    return manager.createOverlay(hwnd, hookType, targetTitle);
  });

  // 显示 Overlay
  ipcMain.handle('multi-overlay:show', async (event, { hwnd }) => {
    return manager.showOverlay(hwnd);
  });

  // 隐藏 Overlay
  ipcMain.handle('multi-overlay:hide', async (event, { hwnd }) => {
    return manager.hideOverlay(hwnd);
  });

  // 销毁 Overlay
  ipcMain.handle('multi-overlay:destroy', async (event, { hwnd }) => {
    return manager.destroyOverlay(hwnd);
  });

  // 销毁所有
  ipcMain.handle('multi-overlay:destroy-all', async () => {
    return manager.destroyAll();
  });

  // 获取状态
  ipcMain.handle('multi-overlay:status', async (event, { hwnd }) => {
    return manager.getStatus(hwnd);
  });

  // 获取所有活跃的 HWND
  ipcMain.handle('multi-overlay:list', async () => {
    return { hwnds: manager.getActiveHwnds(), count: manager.activeCount };
  });

  // Phase 2: 开始跟踪
  ipcMain.handle('multi-overlay:start-tracking', async (event, { hwnd }) => {
    return manager.startTracking(hwnd);
  });

  // Phase 2: 停止跟踪
  ipcMain.handle('multi-overlay:stop-tracking', async (event, { hwnd }) => {
    return manager.stopTracking(hwnd);
  });

  console.log('[MultiOverlayManager] IPC handlers registered (Phase 2)');
}

// ============== 导出 ==============
module.exports = {
  MultiOverlayManager,
  OverlayInstance,
  OverlayState,
  getMultiOverlayManager,
  setupMultiOverlayIPC,
};

