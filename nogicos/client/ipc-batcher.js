/**
 * IPC 批量发送器
 * Phase 7.14: IPC 批量优化
 * 
 * 将高频事件批量发送，减少 IPC 调用次数
 */

class IPCBatcher {
  /**
   * @param {Electron.WebContents} webContents - 目标 webContents
   * @param {number} interval - 批量发送间隔（毫秒），默认 50ms
   */
  constructor(webContents, interval = 50) {
    this.webContents = webContents;
    this.queue = [];
    this.interval = interval;
    this._timer = null;
    this._destroyed = false;
    
    // 定时刷新
    this._timer = setInterval(() => this.flush(), this.interval);
  }

  /**
   * 添加事件到队列
   * @param {string} channel - IPC 通道名
   * @param {*} data - 事件数据
   */
  send(channel, data) {
    if (this._destroyed) {
      console.warn('[IPCBatcher] Attempted to send after destroy');
      return;
    }
    
    this.queue.push({
      channel,
      data,
      timestamp: Date.now(),
    });
    
    // 如果队列过长，立即刷新
    if (this.queue.length >= 10) {
      this.flush();
    }
  }

  /**
   * 刷新队列，批量发送
   */
  flush() {
    if (this.queue.length === 0) return;
    if (this._destroyed) return;
    
    // 检查 webContents 是否仍然有效
    if (!this.webContents || this.webContents.isDestroyed()) {
      console.warn('[IPCBatcher] WebContents destroyed, clearing queue');
      this.queue = [];
      return;
    }
    
    // 按通道分组
    const grouped = this._groupByChannel(this.queue);
    
    // 发送批量事件
    for (const [channel, events] of Object.entries(grouped)) {
      if (events.length === 1) {
        // 单个事件直接发送
        this.webContents.send(channel, events[0].data);
      } else {
        // 多个事件批量发送
        this.webContents.send(`${channel}:batch`, events.map(e => e.data));
      }
    }
    
    // 清空队列
    this.queue = [];
  }

  /**
   * 按通道分组
   * @private
   */
  _groupByChannel(events) {
    return events.reduce((acc, event) => {
      if (!acc[event.channel]) {
        acc[event.channel] = [];
      }
      acc[event.channel].push(event);
      return acc;
    }, {});
  }

  /**
   * 获取队列长度
   */
  getQueueLength() {
    return this.queue.length;
  }

  /**
   * 清空队列（不发送）
   */
  clear() {
    this.queue = [];
  }

  /**
   * 销毁批处理器
   */
  destroy() {
    this._destroyed = true;
    
    // 最后一次刷新
    this.flush();
    
    // 清除定时器
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    
    this.queue = [];
    this.webContents = null;
  }

  /**
   * 检查是否已销毁
   */
  isDestroyed() {
    return this._destroyed;
  }
}

/**
 * 创建节流版本的 IPC 发送器
 * 用于非常高频的事件（如鼠标移动）
 * @param {Electron.WebContents} webContents 
 * @param {string} channel 
 * @param {number} minInterval - 最小发送间隔（毫秒）
 */
function createThrottledSender(webContents, channel, minInterval = 16) {
  let lastSendTime = 0;
  let pendingData = null;
  let timeoutId = null;

  return function send(data) {
    const now = Date.now();
    const timeSinceLastSend = now - lastSendTime;

    if (timeSinceLastSend >= minInterval) {
      // 可以立即发送
      if (!webContents.isDestroyed()) {
        webContents.send(channel, data);
        lastSendTime = now;
      }
    } else {
      // 存储数据，稍后发送
      pendingData = data;
      
      if (!timeoutId) {
        timeoutId = setTimeout(() => {
          if (!webContents.isDestroyed() && pendingData !== null) {
            webContents.send(channel, pendingData);
            lastSendTime = Date.now();
            pendingData = null;
          }
          timeoutId = null;
        }, minInterval - timeSinceLastSend);
      }
    }
  };
}

module.exports = { IPCBatcher, createThrottledSender };
