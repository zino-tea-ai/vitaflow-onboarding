/**
 * Content Security Policy 配置
 * Phase 7.13: Content Security Policy 配置
 * 
 * 防止 XSS 攻击和未授权资源加载
 */

const { session } = require('electron');

/**
 * CSP 策略定义
 */
const CSP_DIRECTIVES = {
  // 默认只允许同源
  'default-src': ["'self'"],
  
  // 脚本只允许同源（禁止 eval 和 inline）
  // 注意：如果需要支持开发模式的热更新，可能需要调整
  'script-src': ["'self'"],
  
  // 样式允许内联（Motion 动画需要）+ Google Fonts CSS
  'style-src': ["'self'", "'unsafe-inline'", 'https://fonts.googleapis.com'],
  
  // 图片允许同源 + data URL（截图）+ blob
  'img-src': ["'self'", 'data:', 'blob:'],
  
  // 连接只允许本地后端 + Google Fonts
  'connect-src': [
    "'self'",
    'ws://localhost:*',
    'http://localhost:*',
    'ws://127.0.0.1:*',
    'http://127.0.0.1:*',
    'https://fonts.googleapis.com',
    'https://fonts.gstatic.com',
  ],
  
  // 字体允许同源 + Google Fonts
  'font-src': ["'self'", 'data:', 'https://fonts.gstatic.com'],
  
  // 禁止嵌入框架
  'frame-ancestors': ["'none'"],
  
  // 禁止对象（Flash 等）
  'object-src': ["'none'"],
  
  // 禁止 base URI 修改
  'base-uri': ["'self'"],
  
  // 表单只能提交到同源
  'form-action': ["'self'"],
  
  // 媒体只允许同源
  'media-src': ["'self'", 'blob:'],
  
  // Worker 脚本
  'worker-src': ["'self'", 'blob:'],
};

/**
 * 将 CSP 指令对象转换为字符串
 */
function buildCSPString(directives) {
  return Object.entries(directives)
    .map(([key, values]) => `${key} ${values.join(' ')}`)
    .join('; ');
}

/**
 * 设置 Content Security Policy
 */
function setupCSP() {
  const cspString = buildCSPString(CSP_DIRECTIVES);
  
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [cspString],
      },
    });
  });
  
  console.log('[Security] CSP configured');
}

/**
 * 额外的安全头配置
 */
const SECURITY_HEADERS = {
  // 禁止 MIME 类型嗅探
  'X-Content-Type-Options': 'nosniff',
  
  // 禁止在 iframe 中加载
  'X-Frame-Options': 'DENY',
  
  // XSS 保护（虽然现代浏览器已弃用，但作为额外保护）
  'X-XSS-Protection': '1; mode=block',
  
  // 严格的引用策略
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  
  // 权限策略：禁用不需要的功能
  'Permissions-Policy': [
    'camera=()',
    'microphone=()',
    'geolocation=()',
    'payment=()',
  ].join(', '),
};

/**
 * 设置额外的安全头
 */
function setupSecurityHeaders() {
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const newHeaders = { ...details.responseHeaders };
    
    for (const [header, value] of Object.entries(SECURITY_HEADERS)) {
      newHeaders[header] = [value];
    }
    
    callback({ responseHeaders: newHeaders });
  });
  
  console.log('[Security] Security headers configured');
}

/**
 * 设置所有安全配置
 */
function setupAllSecurity() {
  setupCSP();
  setupSecurityHeaders();
}

/**
 * 开发模式的宽松 CSP（仅用于开发）
 */
function setupDevCSP() {
  const devDirectives = {
    ...CSP_DIRECTIVES,
    // 开发模式允许 eval（用于 HMR）
    'script-src': ["'self'", "'unsafe-eval'", "'unsafe-inline'"],
    // 允许 WebSocket 热更新
    'connect-src': [
      ...CSP_DIRECTIVES['connect-src'],
      'ws://*:*',
      'http://*:*',
    ],
  };
  
  const cspString = buildCSPString(devDirectives);
  
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [cspString],
      },
    });
  });
  
  console.log('[Security] Development CSP configured (less strict)');
}

module.exports = {
  setupCSP,
  setupSecurityHeaders,
  setupAllSecurity,
  setupDevCSP,
  CSP_DIRECTIVES,
  SECURITY_HEADERS,
  buildCSPString,
};
