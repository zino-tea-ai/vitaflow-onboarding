/**
 * NogicOS Preload Script
 * 安全地暴露 API 给渲染进程
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('nogicos', {
    // 导航
    navigate: (url) => ipcRenderer.invoke('navigate', url),
    goBack: () => ipcRenderer.invoke('go-back'),
    goForward: () => ipcRenderer.invoke('go-forward'),
    refresh: () => ipcRenderer.invoke('refresh'),
    
    // AI 操作
    executeTask: (task, url, model) => ipcRenderer.invoke('execute-task', task, url, model),
    learnWebsite: (url, model) => ipcRenderer.invoke('learn-website', url, model),
    stopTask: () => ipcRenderer.invoke('stop-task'),
    
    // 模型管理
    setModel: (model) => ipcRenderer.invoke('set-model', model),
    getModels: () => ipcRenderer.invoke('get-models'),
    
    // 技能库
    getSkillLibrary: () => ipcRenderer.invoke('get-skill-library'),
    getSkillDetail: (skillName) => ipcRenderer.invoke('get-skill-detail', skillName),
    
    // 事件监听 - WebSocket 状态
    onConnectionStatus: (callback) => {
        ipcRenderer.on('ws:connectionStatus', (_, status) => callback(status));
    },
    
    // 事件监听 - 任务执行
    onTaskStart: (callback) => {
        ipcRenderer.on('ai:taskStart', (_, data) => callback(data));
    },
    onTaskComplete: (callback) => {
        ipcRenderer.on('ai:taskComplete', (_, data) => callback(data));
    },
    onTaskError: (callback) => {
        ipcRenderer.on('ai:taskError', (_, data) => callback(data));
    },
    
    // 事件监听 - 步骤执行
    onStepStart: (callback) => {
        ipcRenderer.on('ai:stepStart', (_, data) => callback(data));
    },
    onStepThinking: (callback) => {
        ipcRenderer.on('ai:stepThinking', (_, data) => callback(data));
    },
    onStepAction: (callback) => {
        ipcRenderer.on('ai:stepAction', (_, data) => callback(data));
    },
    onStepResult: (callback) => {
        ipcRenderer.on('ai:stepResult', (_, data) => callback(data));
    },
    onStepComplete: (callback) => {
        ipcRenderer.on('ai:stepComplete', (_, data) => callback(data));
    },
    
    // 事件监听 - 技能匹配
    onSkillMatched: (callback) => {
        ipcRenderer.on('ai:skillMatched', (_, data) => callback(data));
    },
    onSkillExecuting: (callback) => {
        ipcRenderer.on('ai:skillExecuting', (_, data) => callback(data));
    },
    onSkillResult: (callback) => {
        ipcRenderer.on('ai:skillResult', (_, data) => callback(data));
    },
    
    // 事件监听 - 学习过程
    onLearnStart: (callback) => {
        ipcRenderer.on('ai:learnStart', (_, data) => callback(data));
    },
    onLearnProgress: (callback) => {
        ipcRenderer.on('ai:learnProgress', (_, data) => callback(data));
    },
    onSkillDiscovered: (callback) => {
        ipcRenderer.on('ai:skillDiscovered', (_, data) => callback(data));
    },
    onLearnComplete: (callback) => {
        ipcRenderer.on('ai:learnComplete', (_, data) => callback(data));
    },
    
    // 事件监听 - 知识库
    onKBLoaded: (callback) => {
        ipcRenderer.on('ai:kbLoaded', (_, data) => callback(data));
    },
    onSkillList: (callback) => {
        ipcRenderer.on('ai:skillList', (_, data) => callback(data));
    },
    
    // 事件监听 - AI 可视化动画（NogicOS Atlas 体验）
    onCursorMove: (callback) => {
        ipcRenderer.on('ai:cursorMove', (_, data) => callback(data));
    },
    onCursorClick: (callback) => {
        ipcRenderer.on('ai:cursorClick', (_, data) => callback(data));
    },
    onCursorType: (callback) => {
        ipcRenderer.on('ai:cursorType', (_, data) => callback(data));
    },
    onCursorStopType: (callback) => {
        ipcRenderer.on('ai:cursorStopType', (_, data) => callback(data));
    },
    onHighlight: (callback) => {
        ipcRenderer.on('ai:highlight', (_, data) => callback(data));
    },
    onHighlightHide: (callback) => {
        ipcRenderer.on('ai:highlightHide', (_, data) => callback(data));
    },
    onScreenGlow: (callback) => {
        ipcRenderer.on('ai:screenGlow', (_, data) => callback(data));
    },
    onScreenGlowStop: (callback) => {
        ipcRenderer.on('ai:screenGlowStop', (_, data) => callback(data));
    },
    onScreenPulse: (callback) => {
        ipcRenderer.on('ai:screenPulse', (_, data) => callback(data));
    },
    
    // 页面事件
    onUrlChange: (callback) => {
        ipcRenderer.on('url-changed', (_, url) => callback(url));
    },
    onPageTitle: (callback) => {
        ipcRenderer.on('page-title', (_, title) => callback(title));
    },
    onLoadingChange: (callback) => {
        ipcRenderer.on('loading-changed', (_, isLoading) => callback(isLoading));
    },

    // WebSocket API
    wsAPI: {
        getStatus: () => ipcRenderer.invoke('ws:getStatus'),
        reconnect: () => ipcRenderer.invoke('ws:reconnect'),
    }
});
