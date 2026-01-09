/**
 * NogicOS Enhanced Overlay HTML Generator
 * 
 * 升级版 Overlay 视觉效果：
 * - 动态状态指示
 * - 数据流动动画
 * - 进度条显示
 * - 操作描述
 * 
 * 视觉风格继承自 ConnectorPanel:
 * - emerald 主题色 (#10b981)
 * - 扫描线效果
 * - 脉冲动画
 */

/**
 * Overlay 状态类型
 */
const OverlayStatus = {
  IDLE: 'idle',
  READING: 'reading',
  WRITING: 'writing',
  PROCESSING: 'processing',
  ERROR: 'error',
};

/**
 * 颜色配置 - 继承自 ConnectorPanel
 */
const COLORS = {
  emerald: {
    primary: '#10b981',
    light: '#34d399',
    dark: '#059669',
    glow: 'rgba(16, 185, 129, 0.4)',
    bg: 'rgba(16, 185, 129, 0.1)',
  },
  amber: {
    primary: '#f59e0b',
    light: '#fbbf24',
    glow: 'rgba(245, 158, 11, 0.4)',
  },
  red: {
    primary: '#ef4444',
    glow: 'rgba(239, 68, 68, 0.4)',
  },
  neutral: {
    bg: 'rgba(10, 10, 10, 0.95)',
    border: 'rgba(255, 255, 255, 0.1)',
    text: '#ffffff',
    textMuted: '#737373',
  },
};

/**
 * HTML 转义
 */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * 生成增强版 Overlay HTML
 * 
 * @param {Object} state - Overlay 状态
 * @param {string} state.status - 状态: idle, reading, writing, processing, error
 * @param {string} state.appName - 应用名称
 * @param {string} [state.action] - 当前操作描述
 * @param {number} [state.progress] - 进度 0-100
 * @param {boolean} [state.expanded] - 是否展开显示详情
 * @returns {string} HTML 内容
 */
function generateEnhancedOverlayHTML(state) {
  const {
    status = OverlayStatus.IDLE,
    appName = 'App',
    action = '',
    progress,
    expanded = false,
  } = state;

  const safeAppName = escapeHtml(appName);
  const safeAction = escapeHtml(action);

  // 根据状态选择颜色
  const statusColor = {
    [OverlayStatus.IDLE]: COLORS.emerald,
    [OverlayStatus.READING]: COLORS.emerald,
    [OverlayStatus.WRITING]: COLORS.amber,
    [OverlayStatus.PROCESSING]: COLORS.emerald,
    [OverlayStatus.ERROR]: COLORS.red,
  }[status] || COLORS.emerald;

  // 状态文本
  const statusText = {
    [OverlayStatus.IDLE]: 'Connected',
    [OverlayStatus.READING]: 'Reading',
    [OverlayStatus.WRITING]: 'Writing',
    [OverlayStatus.PROCESSING]: 'Processing',
    [OverlayStatus.ERROR]: 'Error',
  }[status] || 'Connected';

  // 是否显示数据流动动画
  const showDataFlow = status === OverlayStatus.READING || status === OverlayStatus.WRITING;
  const flowDirection = status === OverlayStatus.READING ? 'left' : 'right';

  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * { 
      margin: 0; 
      padding: 0; 
      box-sizing: border-box; 
    }
    
    html, body {
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: transparent;
      font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      -webkit-app-region: no-drag;
    }
    
    /* ========== 主面板 ========== */
    .overlay-panel {
      position: absolute;
      top: 0;
      left: 8px;
      right: 8px;
      background: ${COLORS.neutral.bg};
      border: 1px solid ${COLORS.neutral.border};
      border-top: none;
      border-radius: 0 0 12px 12px;
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      overflow: hidden;
      transition: all 0.3s ease;
    }
    
    /* ========== 状态条 ========== */
    .status-bar {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
      background: linear-gradient(90deg, 
        ${statusColor.bg} 0%, 
        transparent 60%);
      border-bottom: 1px solid ${COLORS.neutral.border};
    }
    
    /* 状态指示器 */
    .status-indicator {
      position: relative;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: ${statusColor.primary};
      flex-shrink: 0;
    }
    
    .status-indicator::after {
      content: '';
      position: absolute;
      inset: -2px;
      border-radius: 50%;
      animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
      0%, 100% { 
        box-shadow: 0 0 0 0 ${statusColor.glow}; 
      }
      50% { 
        box-shadow: 0 0 0 6px transparent; 
      }
    }
    
    /* 活跃状态 - 更快的脉冲 */
    .status-indicator.active {
      animation: glow 0.8s infinite alternate;
    }
    
    @keyframes glow {
      from { box-shadow: 0 0 5px ${statusColor.primary}; }
      to { box-shadow: 0 0 15px ${statusColor.primary}, 0 0 25px ${statusColor.glow}; }
    }
    
    /* 品牌标识 */
    .brand {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    
    .brand-text {
      font-size: 12px;
      font-weight: 600;
      color: ${COLORS.neutral.text};
      letter-spacing: 0.3px;
    }
    
    .status-text {
      font-size: 11px;
      color: ${statusColor.primary};
      font-weight: 500;
    }
    
    /* 分隔线 */
    .divider {
      width: 1px;
      height: 14px;
      background: ${COLORS.neutral.border};
    }
    
    /* ========== 数据流动动画 ========== */
    .data-flow {
      display: flex;
      align-items: center;
      gap: 3px;
      margin-left: auto;
      padding: 4px 8px;
      background: rgba(255, 255, 255, 0.03);
      border-radius: 4px;
    }
    
    .flow-particle {
      width: 4px;
      height: 4px;
      background: ${statusColor.light};
      border-radius: 50%;
      animation: flowParticle 1.2s infinite;
      opacity: 0;
    }
    
    .flow-particle:nth-child(1) { animation-delay: 0s; }
    .flow-particle:nth-child(2) { animation-delay: 0.2s; }
    .flow-particle:nth-child(3) { animation-delay: 0.4s; }
    .flow-particle:nth-child(4) { animation-delay: 0.6s; }
    .flow-particle:nth-child(5) { animation-delay: 0.8s; }
    
    @keyframes flowParticle {
      0% { 
        opacity: 0; 
        transform: translateX(${flowDirection === 'left' ? '10px' : '-10px'}); 
      }
      20% { opacity: 1; }
      80% { opacity: 1; }
      100% { 
        opacity: 0; 
        transform: translateX(${flowDirection === 'left' ? '-10px' : '10px'}); 
      }
    }
    
    .flow-direction {
      font-size: 10px;
      color: ${statusColor.primary};
      margin: 0 4px;
    }
    
    /* ========== 操作详情区 ========== */
    .action-detail {
      padding: 10px 14px;
      border-top: 1px solid ${COLORS.neutral.border};
    }
    
    .action-text {
      font-size: 11px;
      color: rgba(255, 255, 255, 0.7);
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    
    .action-icon {
      font-size: 12px;
    }
    
    /* ========== 进度条 ========== */
    .progress-container {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .progress-bar {
      flex: 1;
      height: 4px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 2px;
      overflow: hidden;
    }
    
    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, ${statusColor.dark}, ${statusColor.light});
      border-radius: 2px;
      transition: width 0.3s ease;
      position: relative;
    }
    
    .progress-fill::after {
      content: '';
      position: absolute;
      top: 0;
      right: 0;
      width: 20px;
      height: 100%;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3));
      animation: shimmer 1s infinite;
    }
    
    @keyframes shimmer {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(100%); }
    }
    
    .progress-text {
      font-size: 10px;
      color: ${COLORS.neutral.textMuted};
      min-width: 32px;
      text-align: right;
    }
    
    /* ========== 四角标记 - 继承自 ConnectorPanel ========== */
    .corner-mark {
      position: absolute;
      width: 6px;
      height: 6px;
      border-color: ${statusColor.primary};
      opacity: 0.6;
    }
    
    .corner-mark.tl { top: 0; left: 0; border-left: 2px solid; border-top: 2px solid; border-radius: 4px 0 0 0; }
    .corner-mark.tr { top: 0; right: 0; border-right: 2px solid; border-top: 2px solid; border-radius: 0 4px 0 0; }
    .corner-mark.bl { bottom: 0; left: 0; border-left: 2px solid; border-bottom: 2px solid; border-radius: 0 0 0 4px; }
    .corner-mark.br { bottom: 0; right: 0; border-right: 2px solid; border-bottom: 2px solid; border-radius: 0 0 4px 0; }
    
    /* ========== 扫描线效果 ========== */
    .scan-line {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 100%;
      background: linear-gradient(90deg, 
        transparent 0%, 
        ${statusColor.primary}20 50%, 
        transparent 100%);
      animation: scan 2s linear infinite;
      pointer-events: none;
      opacity: ${showDataFlow ? 1 : 0};
    }
    
    @keyframes scan {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(100%); }
    }
  </style>
</head>
<body>
  <div class="overlay-panel">
    <!-- 四角标记 -->
    <div class="corner-mark tl"></div>
    <div class="corner-mark tr"></div>
    <div class="corner-mark bl"></div>
    <div class="corner-mark br"></div>
    
    <!-- 扫描线 -->
    <div class="scan-line"></div>
    
    <!-- 状态条 -->
    <div class="status-bar">
      <div class="status-indicator ${showDataFlow ? 'active' : ''}"></div>
      
      <div class="brand">
        <span class="brand-text">NogicOS</span>
        <span class="status-text">${statusText}</span>
      </div>
      
      <div class="divider"></div>
      
      ${showDataFlow ? `
        <div class="data-flow">
          ${status === OverlayStatus.READING ? '<span class="flow-direction">◀</span>' : ''}
          <div class="flow-particle"></div>
          <div class="flow-particle"></div>
          <div class="flow-particle"></div>
          <div class="flow-particle"></div>
          <div class="flow-particle"></div>
          ${status === OverlayStatus.WRITING ? '<span class="flow-direction">▶</span>' : ''}
        </div>
      ` : ''}
    </div>
    
    <!-- 操作详情 -->
    ${safeAction || progress !== undefined ? `
      <div class="action-detail">
        ${safeAction ? `
          <div class="action-text">
            <span class="action-icon">${status === OverlayStatus.READING ? '📖' : status === OverlayStatus.WRITING ? '✍️' : '⚡'}</span>
            ${safeAction}
          </div>
        ` : ''}
        
        ${progress !== undefined ? `
          <div class="progress-container">
            <div class="progress-bar">
              <div class="progress-fill" style="width: ${progress}%"></div>
            </div>
            <span class="progress-text">${progress}%</span>
          </div>
        ` : ''}
      </div>
    ` : ''}
  </div>
</body>
</html>
  `;
}

/**
 * 生成最小化 Overlay HTML (单行模式)
 */
function generateMinimalOverlayHTML(state) {
  const {
    status = OverlayStatus.IDLE,
    action = '',
  } = state;

  const safeAction = escapeHtml(action);

  const statusColor = {
    [OverlayStatus.IDLE]: COLORS.emerald,
    [OverlayStatus.READING]: COLORS.emerald,
    [OverlayStatus.WRITING]: COLORS.amber,
    [OverlayStatus.PROCESSING]: COLORS.emerald,
    [OverlayStatus.ERROR]: COLORS.red,
  }[status] || COLORS.emerald;

  const showDataFlow = status === OverlayStatus.READING || status === OverlayStatus.WRITING;

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
      font-family: 'SF Pro Display', -apple-system, sans-serif;
    }
    
    .overlay-bar {
      position: absolute;
      top: 0;
      left: 8px;
      right: 8px;
      height: 28px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 12px;
      background: ${COLORS.neutral.bg};
      border: 1px solid ${COLORS.neutral.border};
      border-top: none;
      border-radius: 0 0 8px 8px;
      backdrop-filter: blur(20px);
    }
    
    .status-dot {
      width: 8px;
      height: 8px;
      background: ${statusColor.primary};
      border-radius: 50%;
      animation: ${showDataFlow ? 'glow 0.8s infinite alternate' : 'pulse 2s infinite'};
    }
    
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
    
    @keyframes glow {
      from { box-shadow: 0 0 3px ${statusColor.primary}; }
      to { box-shadow: 0 0 10px ${statusColor.primary}; }
    }
    
    .label {
      font-size: 11px;
      font-weight: 500;
      color: ${COLORS.neutral.text};
    }
    
    .action {
      font-size: 10px;
      color: ${COLORS.neutral.textMuted};
      margin-left: auto;
      max-width: 200px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    
    .data-particles {
      display: flex;
      gap: 2px;
      margin-left: 8px;
    }
    
    .particle {
      width: 3px;
      height: 3px;
      background: ${statusColor.light};
      border-radius: 50%;
      animation: move 1s infinite;
    }
    
    .particle:nth-child(2) { animation-delay: 0.15s; }
    .particle:nth-child(3) { animation-delay: 0.3s; }
    
    @keyframes move {
      0%, 100% { opacity: 0.3; transform: scale(0.8); }
      50% { opacity: 1; transform: scale(1.2); }
    }
  </style>
</head>
<body>
  <div class="overlay-bar">
    <div class="status-dot"></div>
    <span class="label">NogicOS</span>
    ${showDataFlow ? `
      <div class="data-particles">
        <div class="particle"></div>
        <div class="particle"></div>
        <div class="particle"></div>
      </div>
    ` : ''}
    ${safeAction ? `<span class="action">${safeAction}</span>` : ''}
  </div>
</body>
</html>
  `;
}

module.exports = {
  OverlayStatus,
  COLORS,
  generateEnhancedOverlayHTML,
  generateMinimalOverlayHTML,
  escapeHtml,
};
