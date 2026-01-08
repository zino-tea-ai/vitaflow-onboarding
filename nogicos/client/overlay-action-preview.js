/**
 * Overlay 动作预览管理器
 * Phase 7.5: Overlay 动作预览（重新设计）
 */

class ActionPreviewManager {
  constructor(overlay) {
    this.overlay = overlay;
    this._previewActive = false;
  }

  /**
   * 检查 overlay 是否可用
   */
  _isOverlayReady() {
    return this.overlay && 
           this.overlay.webContents && 
           !this.overlay.webContents.isDestroyed();
  }

  /**
   * 显示鼠标移动轨迹
   * @param {number} fromX - 起始 X 坐标
   * @param {number} fromY - 起始 Y 坐标
   * @param {number} toX - 目标 X 坐标
   * @param {number} toY - 目标 Y 坐标
   */
  showMouseTrajectory(fromX, fromY, toX, toY) {
    if (!this._isOverlayReady()) return;
    
    this.overlay.webContents.send('preview:mouse-trajectory', {
      from: { x: fromX, y: fromY },
      to: { x: toX, y: toY },
      duration: 300,
    });
  }

  /**
   * 显示点击位置闪烁效果
   * @param {number} x - X 坐标
   * @param {number} y - Y 坐标
   * @param {string} [type='click'] - 点击类型 (click/double-click/right-click)
   */
  showClickIndicator(x, y, type = 'click') {
    if (!this._isOverlayReady()) return;
    
    const animations = {
      'click': 'ripple',
      'double-click': 'double-ripple',
      'right-click': 'context-ripple',
    };

    this.overlay.webContents.send('preview:click', {
      x, 
      y,
      type,
      animation: animations[type] || 'ripple',
      duration: 500,
    });
  }

  /**
   * 显示即将输入的文字预览
   * @param {string} text - 要输入的文字
   * @param {object} [position] - 显示位置
   */
  showTypingPreview(text, position = null) {
    if (!this._isOverlayReady()) return;
    
    // 限制显示长度，避免界面混乱
    const displayText = text.length > 50 ? text.substring(0, 50) + '...' : text;
    
    // 检测是否是密码（隐藏内容）
    const isPassword = text.includes('password') || text.includes('secret');
    
    this.overlay.webContents.send('preview:typing', {
      text: isPassword ? '•'.repeat(Math.min(text.length, 20)) : displayText,
      isPassword,
      position,
      animation: 'typewriter',
    });
  }

  /**
   * 显示"即将点击这里"目标指示器
   * @param {number} x - X 坐标
   * @param {number} y - Y 坐标
   * @param {string} elementName - 元素名称
   */
  showTargetIndicator(x, y, elementName) {
    if (!this._isOverlayReady()) return;
    
    this.overlay.webContents.send('preview:target', {
      x, 
      y,
      label: `即将点击: ${elementName || '未知元素'}`,
      animation: 'pulse-ring',
    });
    
    this._previewActive = true;
  }

  /**
   * 显示滚动预览
   * @param {string} direction - 滚动方向 (up/down/left/right)
   * @param {number} amount - 滚动量
   */
  showScrollPreview(direction, amount) {
    if (!this._isOverlayReady()) return;
    
    this.overlay.webContents.send('preview:scroll', {
      direction,
      amount,
      animation: 'scroll-indicator',
    });
  }

  /**
   * 显示键盘快捷键预览
   * @param {string} shortcut - 快捷键组合 (e.g., "Ctrl+S")
   */
  showShortcutPreview(shortcut) {
    if (!this._isOverlayReady()) return;
    
    this.overlay.webContents.send('preview:shortcut', {
      shortcut,
      animation: 'key-press',
      duration: 800,
    });
  }

  /**
   * 显示窗口操作预览
   * @param {string} action - 窗口操作 (maximize/minimize/close/move/resize)
   */
  showWindowActionPreview(action) {
    if (!this._isOverlayReady()) return;
    
    const labels = {
      maximize: '最大化窗口',
      minimize: '最小化窗口',
      close: '关闭窗口',
      move: '移动窗口',
      resize: '调整大小',
    };

    this.overlay.webContents.send('preview:window-action', {
      action,
      label: labels[action] || action,
      animation: 'window-highlight',
    });
  }

  /**
   * 清除所有预览效果
   */
  clearPreview() {
    if (!this._isOverlayReady()) return;
    
    this.overlay.webContents.send('preview:clear');
    this._previewActive = false;
  }

  /**
   * 设置预览状态
   * @param {boolean} active 
   */
  setPreviewActive(active) {
    this._previewActive = active;
    if (!active) {
      this.clearPreview();
    }
  }

  /**
   * 检查预览是否激活
   */
  isPreviewActive() {
    return this._previewActive;
  }
}

// Overlay HTML 中的预览样式（供 overlay 页面使用）
const previewStyles = `
  /* 鼠标轨迹 */
  .mouse-trajectory {
    position: absolute;
    pointer-events: none;
    z-index: 1000;
  }
  
  .mouse-trajectory path {
    stroke: rgba(0, 255, 136, 0.8);
    stroke-width: 2;
    stroke-dasharray: 5, 5;
    fill: none;
    animation: dash-animation 0.3s linear forwards;
  }
  
  @keyframes dash-animation {
    from { stroke-dashoffset: 100; }
    to { stroke-dashoffset: 0; }
  }
  
  /* 点击指示器 */
  .click-indicator {
    position: absolute;
    width: 40px;
    height: 40px;
    border: 2px solid #00ff88;
    border-radius: 50%;
    transform: translate(-50%, -50%);
    pointer-events: none;
    z-index: 1001;
    animation: ripple 0.5s ease-out forwards;
  }
  
  .click-indicator.double-ripple {
    animation: double-ripple 0.6s ease-out forwards;
  }
  
  .click-indicator.context-ripple {
    border-color: #f59e0b;
    animation: ripple 0.5s ease-out forwards;
  }
  
  @keyframes ripple {
    0% { 
      transform: translate(-50%, -50%) scale(0.5); 
      opacity: 1; 
    }
    100% { 
      transform: translate(-50%, -50%) scale(2); 
      opacity: 0; 
    }
  }
  
  @keyframes double-ripple {
    0%, 50% { 
      transform: translate(-50%, -50%) scale(0.5); 
      opacity: 1; 
    }
    25% { 
      transform: translate(-50%, -50%) scale(1.5); 
      opacity: 0.5; 
    }
    75% { 
      transform: translate(-50%, -50%) scale(1.5); 
      opacity: 0.5; 
    }
    100% { 
      transform: translate(-50%, -50%) scale(2); 
      opacity: 0; 
    }
  }
  
  /* 目标指示器 */
  .target-indicator {
    position: absolute;
    transform: translate(-50%, -50%);
    pointer-events: none;
    z-index: 1000;
  }
  
  .target-indicator__ring {
    width: 60px;
    height: 60px;
    border: 2px solid #00ff88;
    border-radius: 50%;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    animation: pulse-ring 1.5s ease-out infinite;
  }
  
  .target-indicator__label {
    position: absolute;
    top: 40px;
    left: 50%;
    transform: translateX(-50%);
    padding: 4px 12px;
    background: rgba(0, 0, 0, 0.8);
    border: 1px solid #00ff88;
    border-radius: 4px;
    color: #00ff88;
    font-size: 12px;
    white-space: nowrap;
  }
  
  @keyframes pulse-ring {
    0% {
      transform: translate(-50%, -50%) scale(1);
      opacity: 0.8;
    }
    100% {
      transform: translate(-50%, -50%) scale(1.5);
      opacity: 0;
    }
  }
  
  /* 输入预览 */
  .typing-preview {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    padding: 8px 16px;
    background: rgba(0, 0, 0, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    color: white;
    font-family: monospace;
    font-size: 14px;
    z-index: 1002;
    animation: fade-in 0.2s ease-out;
  }
  
  .typing-preview.password {
    color: #f59e0b;
  }
  
  .typing-preview__cursor {
    display: inline-block;
    width: 2px;
    height: 1em;
    background: #00ff88;
    margin-left: 2px;
    animation: blink 0.8s step-end infinite;
  }
  
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }
  
  /* 快捷键预览 */
  .shortcut-preview {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    padding: 16px 32px;
    background: rgba(0, 0, 0, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 12px;
    display: flex;
    gap: 8px;
    z-index: 1003;
    animation: scale-in 0.2s ease-out;
  }
  
  .shortcut-preview kbd {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 40px;
    height: 40px;
    padding: 0 12px;
    background: linear-gradient(180deg, #444, #333);
    border: 1px solid #555;
    border-radius: 6px;
    color: white;
    font-family: system-ui;
    font-size: 16px;
    font-weight: 500;
    box-shadow: 0 2px 0 #222;
  }
  
  @keyframes scale-in {
    from { transform: translate(-50%, -50%) scale(0.8); opacity: 0; }
    to { transform: translate(-50%, -50%) scale(1); opacity: 1; }
  }
  
  @keyframes fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }
`;

module.exports = { ActionPreviewManager, previewStyles };
