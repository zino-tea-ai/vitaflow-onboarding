/**
 * AI Browser - 渲染进程脚本
 */

// DOM 元素
const elements = {
  urlInput: document.getElementById('url-input'),
  welcomeUrl: document.getElementById('welcome-url'),
  welcome: document.getElementById('welcome'),
  webviewContainer: document.getElementById('webview-container'),
  aiPanel: document.getElementById('ai-panel'),
  aiMessages: document.getElementById('ai-messages'),
  aiTaskInput: document.getElementById('ai-task-input'),
  statusIndicator: document.getElementById('status-indicator'),
  statusText: document.getElementById('status-text'),
  btnBack: document.getElementById('btn-back'),
  btnForward: document.getElementById('btn-forward'),
  btnRefresh: document.getElementById('btn-refresh'),
  btnAi: document.getElementById('btn-ai'),
  btnClosePanel: document.getElementById('btn-close-panel'),
  btnLearn: document.getElementById('btn-learn'),
  btnExecute: document.getElementById('btn-execute')
};

// 当前 webview
let webview = null;
let currentUrl = '';

/**
 * 初始化
 */
function init() {
  // URL 输入事件
  elements.urlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      navigate(elements.urlInput.value);
    }
  });

  elements.welcomeUrl.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      navigate(elements.welcomeUrl.value);
    }
  });

  // 导航按钮
  elements.btnBack.addEventListener('click', () => webview?.goBack());
  elements.btnForward.addEventListener('click', () => webview?.goForward());
  elements.btnRefresh.addEventListener('click', () => webview?.reload());

  // AI 面板
  elements.btnAi.addEventListener('click', toggleAiPanel);
  elements.btnClosePanel.addEventListener('click', () => {
    elements.aiPanel.classList.remove('visible');
  });

  // AI 操作
  elements.btnLearn.addEventListener('click', learnCurrentPage);
  elements.btnExecute.addEventListener('click', executeTask);

  elements.aiTaskInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      executeTask();
    }
  });

  // 监听 AI 命令
  if (window.aiAPI) {
    window.aiAPI.onLearnCommand(learnCurrentPage);
    window.aiAPI.onExecuteCommand(() => {
      elements.aiPanel.classList.add('visible');
      elements.aiTaskInput.focus();
    });
    window.aiAPI.onLearnProgress((data) => {
      addAiMessage(`📚 ${data}`, 'info');
    });
  }

  console.log('[AI Browser] 初始化完成');
}

/**
 * 导航到 URL
 */
function navigate(url) {
  if (!url) return;

  // 补全 URL
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    if (url.includes('.') && !url.includes(' ')) {
      url = 'https://' + url;
    } else {
      url = 'https://www.google.com/search?q=' + encodeURIComponent(url);
    }
  }

  currentUrl = url;
  elements.urlInput.value = url;

  // 隐藏欢迎页
  elements.welcome.style.display = 'none';

  // 创建或更新 webview
  if (!webview) {
    createWebview(url);
  } else {
    webview.src = url;
  }
}

/**
 * 创建 Webview
 */
function createWebview(url) {
  webview = document.createElement('webview');
  webview.src = url;
  webview.style.width = '100%';
  webview.style.height = '100%';
  
  // 事件监听
  webview.addEventListener('did-start-loading', () => {
    setStatus('加载中...', 'busy');
  });

  webview.addEventListener('did-stop-loading', () => {
    setStatus('AI 就绪', 'ready');
    updateNavButtons();
  });

  webview.addEventListener('did-navigate', (e) => {
    currentUrl = e.url;
    elements.urlInput.value = e.url;
    updateNavButtons();
  });

  webview.addEventListener('did-navigate-in-page', (e) => {
    currentUrl = e.url;
    elements.urlInput.value = e.url;
  });

  webview.addEventListener('page-title-updated', (e) => {
    document.title = `${e.title} - AI Browser`;
  });

  elements.webviewContainer.appendChild(webview);
}

/**
 * 更新导航按钮状态
 */
function updateNavButtons() {
  if (webview) {
    elements.btnBack.disabled = !webview.canGoBack();
    elements.btnForward.disabled = !webview.canGoForward();
  }
}

/**
 * 切换 AI 面板
 */
function toggleAiPanel() {
  elements.aiPanel.classList.toggle('visible');
  if (elements.aiPanel.classList.contains('visible')) {
    elements.aiTaskInput.focus();
  }
}

/**
 * 设置状态
 */
function setStatus(text, state) {
  elements.statusText.textContent = text;
  elements.statusIndicator.className = `status-indicator ${state}`;
}

/**
 * 添加 AI 消息
 */
function addAiMessage(text, type = 'info') {
  const msg = document.createElement('div');
  msg.className = `ai-message ${type}`;
  msg.innerHTML = text;
  elements.aiMessages.appendChild(msg);
  elements.aiMessages.scrollTop = elements.aiMessages.scrollHeight;
}

/**
 * 学习当前页面
 */
async function learnCurrentPage() {
  if (!currentUrl) {
    addAiMessage('⚠️ 请先打开一个网页', 'error');
    return;
  }

  setStatus('学习中...', 'busy');
  addAiMessage(`🔄 开始学习: ${currentUrl}`, 'info');

  try {
    if (window.aiAPI) {
      const result = await window.aiAPI.learnWebsite(currentUrl, 10);
      
      if (result.success) {
        addAiMessage(`✅ 学习完成！知识库已保存`, 'success');
      } else {
        addAiMessage(`❌ 学习失败: ${result.error}`, 'error');
      }
    } else {
      // 模拟模式
      await new Promise(r => setTimeout(r, 2000));
      addAiMessage('✅ [模拟] 学习完成！', 'success');
    }
  } catch (error) {
    addAiMessage(`❌ 错误: ${error.message}`, 'error');
  }

  setStatus('AI 就绪', 'ready');
}

/**
 * 执行任务
 */
async function executeTask() {
  const task = elements.aiTaskInput.value.trim();
  
  if (!task) {
    addAiMessage('⚠️ 请输入任务描述', 'error');
    return;
  }

  if (!currentUrl) {
    addAiMessage('⚠️ 请先打开一个网页', 'error');
    return;
  }

  setStatus('执行中...', 'busy');
  addAiMessage(`🎯 执行任务: ${task}`, 'info');
  elements.aiTaskInput.value = '';

  const startTime = Date.now();

  try {
    if (window.aiAPI) {
      const result = await window.aiAPI.executeTask(task, currentUrl, true);
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
      
      if (result.success) {
        addAiMessage(`✅ 任务完成！耗时 ${elapsed}s`, 'success');
      } else {
        addAiMessage(`❌ 任务失败: ${result.error}`, 'error');
      }
    } else {
      // 模拟模式
      await new Promise(r => setTimeout(r, 1500));
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
      addAiMessage(`✅ [模拟] 任务完成！耗时 ${elapsed}s`, 'success');
    }
  } catch (error) {
    addAiMessage(`❌ 错误: ${error.message}`, 'error');
  }

  setStatus('AI 就绪', 'ready');
}

// 初始化
document.addEventListener('DOMContentLoaded', init);
