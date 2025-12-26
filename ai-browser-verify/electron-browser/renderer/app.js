/**
 * NogicOS - 渲染进程应用逻辑
 */

// 状态管理
const state = {
    isPanelVisible: false,
    isConnected: false,
    isExecuting: false,
    isLearning: false,
    currentTab: 'execution',
    currentTask: null,
    currentModel: 'gpt-5.2',
    steps: [],
    skills: [],
    startTime: null,
};

// DOM 元素
const elements = {
    urlInput: document.getElementById('url-input'),
    loadingIndicator: document.getElementById('loading-indicator'),
    connectionStatus: document.getElementById('connection-status'),
    aiPanel: document.getElementById('ai-panel'),
    aiToggleBtn: document.getElementById('ai-toggle-btn'),
    panelCloseBtn: document.getElementById('panel-close-btn'),
    tabBtns: document.querySelectorAll('.tab-btn'),
    tabContents: document.querySelectorAll('.tab-content'),
    taskInput: document.getElementById('task-input'),
    executeBtn: document.getElementById('execute-btn'),
    stopBtn: document.getElementById('stop-btn'),
    executionStatus: document.getElementById('execution-status'),
    statusTime: document.getElementById('status-time'),
    stepsContainer: document.getElementById('steps-container'),
    learnBtn: document.getElementById('learn-btn'),
    learnProgress: document.getElementById('learn-progress'),
    progressFill: document.getElementById('progress-fill'),
    discoveredSkillsList: document.getElementById('discovered-skills-list'),
    skillsLibrary: document.getElementById('skills-library'),
    skillModal: document.getElementById('skill-modal'),
    skillModalTitle: document.getElementById('skill-modal-title'),
    skillModalBody: document.getElementById('skill-modal-body'),
    modalCloseBtn: document.getElementById('modal-close-btn'),
    webview: document.getElementById('browser-view'),
    modelSelect: document.getElementById('model-select'),
};

// 初始化
async function init() {
    console.log('[NogicOS] 初始化...');
    setupEventListeners();
    setupWebviewListeners();
    setupAPIListeners();
    updateConnectionStatus(false);
    
    // 初始化模型选择器
    await initModelSelector();
}

// 初始化模型选择器
async function initModelSelector() {
    if (!elements.modelSelect) return;
    
    try {
        const models = await window.nogicos.getModels();
        state.currentModel = models.current;
        elements.modelSelect.value = models.current;
        console.log('[NogicOS] 当前模型:', models.current);
    } catch (e) {
        console.error('[NogicOS] 获取模型失败:', e);
    }
    
    // 模型切换事件
    elements.modelSelect.addEventListener('change', async (e) => {
        const model = e.target.value;
        try {
            const result = await window.nogicos.setModel(model);
            if (result.success) {
                state.currentModel = model;
                console.log('[NogicOS] 模型切换为:', model);
            }
        } catch (err) {
            console.error('[NogicOS] 模型切换失败:', err);
        }
    });
}

// 设置 webview 事件监听
function setupWebviewListeners() {
    if (!elements.webview) return;
    
    elements.webview.addEventListener('did-navigate', (e) => {
        elements.urlInput.value = e.url;
    });
    
    elements.webview.addEventListener('did-navigate-in-page', (e) => {
        elements.urlInput.value = e.url;
    });
    
    elements.webview.addEventListener('did-start-loading', () => {
        elements.loadingIndicator.classList.add('active');
    });
    
    elements.webview.addEventListener('did-stop-loading', () => {
        elements.loadingIndicator.classList.remove('active');
    });
    
    elements.webview.addEventListener('page-title-updated', (e) => {
        document.title = `${e.title} - NogicOS`;
    });
}

// 设置事件监听
function setupEventListeners() {
    // URL 输入
    elements.urlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            navigateTo(elements.urlInput.value);
        }
    });

    // 导航按钮
    document.getElementById('btn-back').addEventListener('click', () => {
        if (elements.webview && elements.webview.canGoBack()) {
            elements.webview.goBack();
        }
    });
    document.getElementById('btn-forward').addEventListener('click', () => {
        if (elements.webview && elements.webview.canGoForward()) {
            elements.webview.goForward();
        }
    });
    document.getElementById('btn-refresh').addEventListener('click', () => {
        if (elements.webview) {
            elements.webview.reload();
        }
    });

    // AI 面板
    elements.aiToggleBtn.addEventListener('click', togglePanel);
    elements.panelCloseBtn.addEventListener('click', () => togglePanel(false));

    // Tab 切换
    elements.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // 执行任务
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:setupEventListeners',message:'Binding execute button',data:{btnExists:!!elements.executeBtn},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    elements.executeBtn.addEventListener('click', () => {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:executeBtn.click',message:'Execute button clicked',data:{},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A'})}).catch(()=>{});
        // #endregion
        executeTask();
    });
    elements.stopBtn.addEventListener('click', stopTask);

    // 学习
    elements.learnBtn.addEventListener('click', startLearning);

    // 弹窗关闭
    elements.modalCloseBtn.addEventListener('click', closeModal);
    elements.skillModal.addEventListener('click', (e) => {
        if (e.target === elements.skillModal) closeModal();
    });
}

// 设置 API 监听
function setupAPIListeners() {
    // 连接状态
    window.nogicos.onConnectionStatus((status) => {
        updateConnectionStatus(status.connected);
    });

    // 页面事件
    window.nogicos.onUrlChange((url) => {
        elements.urlInput.value = url;
    });

    window.nogicos.onLoadingChange((isLoading) => {
        elements.loadingIndicator.classList.toggle('active', isLoading);
    });

    // 任务事件 - 同时通知 AI Overlay
    window.nogicos.onTaskStart((data) => {
        handleTaskStart(data);
        // 通知 AI Overlay 开始任务
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'task_start', data });
        }
    });

    window.nogicos.onTaskComplete((data) => {
        handleTaskComplete(data);
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'task_complete', data });
        }
    });

    window.nogicos.onTaskError((data) => {
        handleTaskError(data);
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'task_error', data });
        }
    });

    // 步骤事件 - 同时更新 AI Overlay
    window.nogicos.onStepStart((data) => {
        handleStepStart(data);
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'step_start', data });
        }
    });

    window.nogicos.onStepThinking((data) => {
        handleStepThinking(data);
    });

    window.nogicos.onStepAction((data) => {
        handleStepAction(data);
        // 如果有坐标信息，移动光标
        if (window.aiOverlay && data.coordinates) {
            window.aiOverlay.handleMessage({ 
                type: 'cursor_move', 
                data: { x: data.coordinates.x, y: data.coordinates.y + 80 } // 80px 为工具栏高度
            });
        }
    });

    window.nogicos.onStepResult((data) => {
        handleStepResult(data);
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'step_complete', data: { step: data.step, success: data.success } });
        }
    });

    window.nogicos.onStepComplete((data) => {
        handleStepComplete(data);
    });

    // 技能事件
    window.nogicos.onSkillMatched((data) => {
        handleSkillMatched(data);
    });

    // 学习事件
    window.nogicos.onLearnStart((data) => {
        handleLearnStart(data);
    });

    window.nogicos.onLearnProgress((data) => {
        handleLearnProgress(data);
    });

    window.nogicos.onSkillDiscovered((data) => {
        handleSkillDiscovered(data);
    });

    window.nogicos.onLearnComplete((data) => {
        handleLearnComplete(data);
    });

    // AI 可视化动画事件（直接转发到 AI Overlay）
    window.nogicos.onCursorMove((data) => {
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'cursor_move', data });
        }
    });

    window.nogicos.onCursorClick((data) => {
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'cursor_click', data });
        }
    });

    window.nogicos.onCursorType((data) => {
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'cursor_type', data });
        }
    });

    window.nogicos.onCursorStopType((data) => {
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'cursor_stop_type', data });
        }
    });

    window.nogicos.onHighlight((data) => {
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'highlight', data });
        }
    });

    window.nogicos.onHighlightHide((data) => {
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'highlight_hide', data });
        }
    });

    window.nogicos.onScreenGlow((data) => {
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'screen_glow', data });
        }
    });

    window.nogicos.onScreenGlowStop((data) => {
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'screen_glow_stop', data });
        }
    });

    window.nogicos.onScreenPulse((data) => {
        if (window.aiOverlay) {
            window.aiOverlay.handleMessage({ type: 'screen_pulse', data });
        }
    });
}

// 导航
async function navigateTo(url) {
    if (!url) return;
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url;
    }
    elements.loadingIndicator.classList.add('active');
    if (elements.webview) {
        elements.webview.loadURL(url);
    }
}

// 更新连接状态
function updateConnectionStatus(connected) {
    state.isConnected = connected;
    const statusDot = elements.connectionStatus.querySelector('.status-dot');
    const statusText = elements.connectionStatus.querySelector('span');
    
    statusDot.classList.toggle('connected', connected);
    statusDot.classList.toggle('disconnected', !connected);
    statusText.textContent = connected ? '已连接' : '未连接';
}

// 切换面板
function togglePanel(show) {
    if (typeof show === 'boolean') {
        state.isPanelVisible = show;
    } else {
        state.isPanelVisible = !state.isPanelVisible;
    }
    elements.aiPanel.classList.toggle('visible', state.isPanelVisible);
}

// 切换 Tab
function switchTab(tabId) {
    state.currentTab = tabId;
    
    elements.tabBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    
    elements.tabContents.forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabId}`);
    });
}

// 执行任务
async function executeTask() {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:executeTask:entry',message:'executeTask called',data:{},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    
    const task = elements.taskInput.value.trim();
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:executeTask:taskValue',message:'Task value',data:{task,isEmpty:!task},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    if (!task) return;
    
    state.isExecuting = true;
    state.currentTask = task;
    state.steps = [];
    state.startTime = Date.now();
    
    // 获取当前选择的模型
    const model = elements.modelSelect?.value || state.currentModel;
    console.log('[NogicOS] 执行任务:', task, '模型:', model);
    
    elements.executeBtn.disabled = true;
    elements.stopBtn.disabled = false;
    elements.stepsContainer.innerHTML = '';
    
    updateExecutionStatus('正在执行任务...', true);
    
    // 获取 webview 当前 URL
    const url = elements.webview ? elements.webview.getURL() : 'https://news.ycombinator.com';
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:executeTask:beforeIPC',message:'Before IPC call',data:{task,url,model},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    
    try {
        const model = elements.modelSelect?.value || state.currentModel;
        await window.nogicos.executeTask(task, url, model);
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:executeTask:afterIPC',message:'IPC call succeeded',data:{},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
    } catch (e) {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/1146cc51-3fe3-46a3-9e1a-4801e1a50de0',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:executeTask:error',message:'IPC call failed',data:{error:e.message},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
        console.error('[NogicOS] Task execution failed:', e);
        handleTaskError({ error: e.message });
    }
}

// 停止任务
async function stopTask() {
    await window.nogicos.stopTask();
    state.isExecuting = false;
    elements.executeBtn.disabled = false;
    elements.stopBtn.disabled = true;
    updateExecutionStatus('任务已停止', false);
}

// 更新执行状态
function updateExecutionStatus(message, showTime = false) {
    const statusTitle = elements.executionStatus.querySelector('.status-title');
    statusTitle.textContent = message;
    
    if (showTime && state.startTime) {
        updateTimer();
    }
}

// 更新计时器
function updateTimer() {
    if (!state.isExecuting) return;
    
    const elapsed = Math.floor((Date.now() - state.startTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    elements.statusTime.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    
    requestAnimationFrame(updateTimer);
}

// 任务开始
function handleTaskStart(data) {
    console.log('Task started:', data);
    updateExecutionStatus(`任务: ${data.task}`, true);
}

// 任务完成
function handleTaskComplete(data) {
    state.isExecuting = false;
    elements.executeBtn.disabled = false;
    elements.stopBtn.disabled = true;
    
    const statusMsg = data.success ? '✓ 任务完成' : '✗ 任务失败';
    updateExecutionStatus(`${statusMsg} (${data.duration?.toFixed(1)}s)`);
}

// 任务错误
function handleTaskError(data) {
    state.isExecuting = false;
    elements.executeBtn.disabled = false;
    elements.stopBtn.disabled = true;
    updateExecutionStatus(`✗ 错误: ${data.error}`);
}

// 步骤开始
function handleStepStart(data) {
    const stepCard = createStepCard(data.step, data.max_steps);
    elements.stepsContainer.appendChild(stepCard);
    state.steps.push({ step: data.step, element: stepCard });
}

// 步骤思考
function handleStepThinking(data) {
    const stepData = state.steps.find(s => s.step === data.step);
    if (stepData) {
        const thinkingEl = stepData.element.querySelector('.step-thinking');
        if (thinkingEl) {
            thinkingEl.textContent = data.reasoning;
        }
    }
}

// 步骤动作
function handleStepAction(data) {
    const stepData = state.steps.find(s => s.step === data.step);
    if (stepData) {
        const actionEl = stepData.element.querySelector('.step-action');
        if (actionEl) {
            actionEl.textContent = data.code || data.action_type;
        }
    }
}

// 步骤结果
function handleStepResult(data) {
    const stepData = state.steps.find(s => s.step === data.step);
    if (stepData) {
        const contentEl = stepData.element.querySelector('.step-content');
        const resultEl = document.createElement('div');
        resultEl.className = `step-result ${data.success ? 'success' : 'error'}`;
        resultEl.textContent = data.success ? (data.result || '成功') : (data.error || '失败');
        contentEl.appendChild(resultEl);
        
        stepData.element.classList.remove('active');
        stepData.element.classList.add(data.success ? 'success' : 'error');
    }
}

// 步骤完成
function handleStepComplete(data) {
    const stepData = state.steps.find(s => s.step === data.step);
    if (stepData) {
        const durationEl = stepData.element.querySelector('.step-duration');
        if (durationEl) {
            durationEl.textContent = `${data.duration?.toFixed(1)}s`;
        }
    }
}

// 技能匹配
function handleSkillMatched(data) {
    const stepData = state.steps[state.steps.length - 1];
    if (stepData) {
        const headerEl = stepData.element.querySelector('.step-header');
        const badge = document.createElement('span');
        badge.className = 'skill-badge';
        badge.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg> ${data.skill_name}`;
        headerEl.appendChild(badge);
    }
}

// 创建步骤卡片
function createStepCard(stepNum, maxSteps) {
    const card = document.createElement('div');
    card.className = 'step-card active pulse-glow';
    card.innerHTML = `
        <div class="step-header">
            <span class="step-number">${stepNum + 1}</span>
            <span class="step-title">步骤 ${stepNum + 1} / ${maxSteps}</span>
            <span class="step-duration">-</span>
        </div>
        <div class="step-content">
            <div class="step-thinking">正在思考...</div>
            <div class="step-action"></div>
        </div>
    `;
    return card;
}

// 开始学习
async function startLearning() {
    state.isLearning = true;
    elements.learnBtn.disabled = true;
    elements.learnBtn.textContent = '学习中...';
    elements.discoveredSkillsList.innerHTML = '';
    elements.progressFill.style.width = '0%';
    
    // 获取 webview 当前 URL
    const url = elements.webview ? elements.webview.getURL() : 'https://news.ycombinator.com';
    const model = elements.modelSelect?.value || state.currentModel;
    
    console.log('[NogicOS] 开始学习:', url, '模型:', model);
    
    try {
        await window.nogicos.learnWebsite(url, model);
    } catch (e) {
        console.error('[NogicOS] Learning failed:', e);
        handleLearnComplete({ success: false });
    }
}

// 学习开始
function handleLearnStart(data) {
    const progressText = elements.learnProgress.querySelector('.progress-text');
    progressText.textContent = `正在学习: ${data.url}`;
}

// 学习进度
function handleLearnProgress(data) {
    const progressText = elements.learnProgress.querySelector('.progress-text');
    const progressCount = elements.learnProgress.querySelector('.progress-count');
    
    progressText.textContent = data.message || '学习中...';
    progressCount.textContent = `${data.current} / ${data.total}`;
    
    const percent = (data.current / data.total) * 100;
    elements.progressFill.style.width = `${percent}%`;
}

// 发现技能
function handleSkillDiscovered(data) {
    const item = document.createElement('div');
    item.className = 'discovered-skill-item';
    item.innerHTML = `
        <div class="skill-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
        </div>
        <div class="skill-info">
            <div class="skill-name">${data.skill_name}</div>
            <div class="skill-desc">${data.description || '新发现的技能'}</div>
        </div>
    `;
    elements.discoveredSkillsList.appendChild(item);
}

// 学习完成
function handleLearnComplete(data) {
    state.isLearning = false;
    elements.learnBtn.disabled = false;
    elements.learnBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2zM22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/>
        </svg>
        开始学习
    `;
    
    const progressText = elements.learnProgress.querySelector('.progress-text');
    progressText.textContent = data.success 
        ? `✓ 学习完成，发现 ${data.skills_count || 0} 个技能`
        : '✗ 学习失败';
    
    elements.progressFill.style.width = '100%';
}

// 关闭弹窗
function closeModal() {
    elements.skillModal.classList.remove('visible');
}

// 初始化应用
document.addEventListener('DOMContentLoaded', init);
