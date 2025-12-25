/**
 * AI Browser - 预加载脚本
 * 安全地暴露 API 给渲染进程
 */
const { contextBridge, ipcRenderer } = require('electron');

// 暴露 AI API 到渲染进程
contextBridge.exposeInMainWorld('aiAPI', {
  /**
   * 执行 AI 任务
   * @param {string} task - 任务描述
   * @param {string} url - 目标 URL
   * @param {boolean} useKnowledgeBase - 是否使用知识库
   */
  executeTask: (task, url, useKnowledgeBase = true) => {
    return ipcRenderer.invoke('ai:executeTask', { task, url, useKnowledgeBase });
  },

  /**
   * 学习网站操作
   * @param {string} url - 目标 URL
   * @param {number} iterations - 迭代次数
   */
  learnWebsite: (url, iterations = 10) => {
    return ipcRenderer.invoke('ai:learnWebsite', { url, iterations });
  },

  /**
   * 获取 AI 引擎状态
   */
  getStatus: () => {
    return ipcRenderer.invoke('ai:getStatus');
  },

  /**
   * 监听学习进度
   */
  onLearnProgress: (callback) => {
    ipcRenderer.on('ai:learnProgress', (event, data) => callback(data));
  },

  /**
   * 监听学习命令
   */
  onLearnCommand: (callback) => {
    ipcRenderer.on('ai:learn', () => callback());
  },

  /**
   * 监听执行命令
   */
  onExecuteCommand: (callback) => {
    ipcRenderer.on('ai:execute', () => callback());
  }
});

// 暴露版本信息
contextBridge.exposeInMainWorld('versions', {
  node: process.versions.node,
  chrome: process.versions.chrome,
  electron: process.versions.electron
});

console.log('[Preload] AI API 已暴露');
