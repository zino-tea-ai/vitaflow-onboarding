/**
 * CDP Bridge - Electron 内部浏览器控制层
 * 
 * 使用 webContents.debugger API 通过 CDP 协议控制 WebContentsView
 * 这是方案 A-lite 的核心模块，不影响现有的截图流方案
 * 
 * 功能：
 * - 点击元素 (dispatchMouseEvent)
 * - 输入文本 (insertText)
 * - 导航 (Page.navigate)
 * - 截图 (Page.captureScreenshot)
 * - 获取 DOM (DOM.getDocument, DOM.querySelector)
 */

class CDPBridge {
  /**
   * @param {Electron.WebContents} webContents - 要控制的 WebContents 实例
   */
  constructor(webContents) {
    this.wc = webContents;
    this.attached = false;
    this.messageHandlers = new Map();
    this._requestId = 0;
  }

  /**
   * 附加调试器
   * @param {string} version - CDP 协议版本，默认 '1.3'
   */
  async attach(version = '1.3') {
    // 如果已经附加，直接返回成功
    if (this.attached) {
      console.log('[CDPBridge] Already attached, skipping');
      return true;
    }

    try {
      // 检查是否已经附加（通过 try-catch）
      try {
        this.wc.debugger.attach(version);
      } catch (attachErr) {
        if (attachErr.message.includes('already attached')) {
          console.log('[CDPBridge] Debugger was already attached, reusing');
          this.attached = true;
          return true;
        }
        throw attachErr;
      }
      
      this.attached = true;
      console.log('[CDPBridge] Debugger attached');

      // 监听分离事件（只注册一次）
      if (!this._detachHandlerRegistered) {
        this.wc.debugger.on('detach', (event, reason) => {
          console.log('[CDPBridge] Debugger detached:', reason);
          this.attached = false;
        });
        this._detachHandlerRegistered = true;
      }

      // 监听 CDP 消息（只注册一次）
      if (!this._messageHandlerRegistered) {
        this.wc.debugger.on('message', (event, method, params) => {
          const handler = this.messageHandlers.get(method);
          if (handler) {
            handler(params);
          }
        });
        this._messageHandlerRegistered = true;
      }

      // 启用必要的 CDP 域
      await this.sendCommand('DOM.enable');
      await this.sendCommand('Page.enable');
      await this.sendCommand('Runtime.enable');
      
      return true;
    } catch (err) {
      console.error('[CDPBridge] Attach failed:', err.message);
      return false;
    }
  }

  /**
   * 分离调试器
   */
  detach() {
    if (this.attached) {
      try {
        this.wc.debugger.detach();
      } catch (e) {
        // 忽略分离错误
      }
      this.attached = false;
    }
  }

  /**
   * 发送 CDP 命令
   * @param {string} method - CDP 方法名
   * @param {object} params - 参数
   * @returns {Promise<any>}
   */
  async sendCommand(method, params = {}) {
    if (!this.attached) {
      throw new Error('Debugger not attached');
    }
    return this.wc.debugger.sendCommand(method, params);
  }

  /**
   * 注册 CDP 事件处理器
   * @param {string} method - 事件方法名
   * @param {function} handler - 处理函数
   */
  on(method, handler) {
    this.messageHandlers.set(method, handler);
  }

  // ============================================================
  // 导航控制
  // ============================================================

  /**
   * 导航到 URL
   * @param {string} url - 目标 URL
   */
  async navigate(url) {
    const result = await this.sendCommand('Page.navigate', { url });
    // 等待页面加载完成
    await this.waitForLoad();
    return result;
  }

  /**
   * 等待页面加载完成
   * @param {number} timeout - 超时时间（毫秒）
   */
  async waitForLoad(timeout = 30000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error('Page load timeout'));
      }, timeout);

      const handler = () => {
        clearTimeout(timer);
        this.wc.off('did-finish-load', handler);
        resolve();
      };

      this.wc.on('did-finish-load', handler);
    });
  }

  /**
   * 刷新页面
   */
  async reload() {
    await this.sendCommand('Page.reload');
    await this.waitForLoad();
  }

  // ============================================================
  // 鼠标控制
  // ============================================================

  /**
   * 点击指定坐标
   * @param {number} x - X 坐标
   * @param {number} y - Y 坐标
   * @param {object} options - 选项
   */
  async click(x, y, options = {}) {
    const { button = 'left', clickCount = 1, delay = 50 } = options;

    // Mouse down
    await this.sendCommand('Input.dispatchMouseEvent', {
      type: 'mousePressed',
      x,
      y,
      button,
      clickCount,
    });

    // 短暂延迟模拟真实点击
    await this._sleep(delay);

    // Mouse up
    await this.sendCommand('Input.dispatchMouseEvent', {
      type: 'mouseReleased',
      x,
      y,
      button,
      clickCount,
    });
  }

  /**
   * 双击指定坐标
   */
  async doubleClick(x, y) {
    await this.click(x, y, { clickCount: 2 });
  }

  /**
   * 移动鼠标到指定位置
   */
  async moveMouse(x, y) {
    await this.sendCommand('Input.dispatchMouseEvent', {
      type: 'mouseMoved',
      x,
      y,
    });
  }

  // ============================================================
  // 键盘控制
  // ============================================================

  /**
   * 输入文本
   * @param {string} text - 要输入的文本
   */
  async type(text) {
    await this.sendCommand('Input.insertText', { text });
  }

  /**
   * 按下按键
   * @param {string} key - 按键名称（如 'Enter', 'Tab', 'Escape'）
   */
  async pressKey(key) {
    // 特殊按键映射
    const keyMap = {
      'Enter': { keyCode: 13, key: 'Enter', code: 'Enter', text: '\r' },
      'Tab': { keyCode: 9, key: 'Tab', code: 'Tab' },
      'Escape': { keyCode: 27, key: 'Escape', code: 'Escape' },
      'Backspace': { keyCode: 8, key: 'Backspace', code: 'Backspace' },
      'ArrowUp': { keyCode: 38, key: 'ArrowUp', code: 'ArrowUp' },
      'ArrowDown': { keyCode: 40, key: 'ArrowDown', code: 'ArrowDown' },
      'ArrowLeft': { keyCode: 37, key: 'ArrowLeft', code: 'ArrowLeft' },
      'ArrowRight': { keyCode: 39, key: 'ArrowRight', code: 'ArrowRight' },
    };

    const keyInfo = keyMap[key] || { key, code: key };
    const { text, ...keyParams } = keyInfo;

    // keyDown
    await this.sendCommand('Input.dispatchKeyEvent', {
      type: 'keyDown',
      ...keyParams,
    });

    // 对于 Enter 键，还需要发送 rawKeyDown 和触发表单提交
    if (key === 'Enter') {
      // 尝试通过 JavaScript 触发表单提交
      await this.evaluate(`
        (function() {
          const activeEl = document.activeElement;
          if (activeEl && activeEl.form) {
            activeEl.form.submit();
          } else if (activeEl) {
            // 触发 keydown 和 keypress 事件
            const keydownEvent = new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true });
            const keypressEvent = new KeyboardEvent('keypress', { key: 'Enter', keyCode: 13, bubbles: true });
            activeEl.dispatchEvent(keydownEvent);
            activeEl.dispatchEvent(keypressEvent);
          }
        })()
      `);
    }

    // keyUp
    await this.sendCommand('Input.dispatchKeyEvent', {
      type: 'keyUp',
      ...keyParams,
    });
  }

  // ============================================================
  // DOM 操作
  // ============================================================

  /**
   * 获取文档根节点
   */
  async getDocument() {
    const result = await this.sendCommand('DOM.getDocument');
    return result.root;
  }

  /**
   * 使用 CSS 选择器查找元素
   * @param {string} selector - CSS 选择器
   * @returns {Promise<number|null>} - 节点 ID
   */
  async querySelector(selector) {
    const doc = await this.getDocument();
    try {
      const result = await this.sendCommand('DOM.querySelector', {
        nodeId: doc.nodeId,
        selector,
      });
      return result.nodeId || null;
    } catch (e) {
      return null;
    }
  }

  /**
   * 获取元素的边界框
   * @param {number} nodeId - 节点 ID
   * @returns {Promise<{x, y, width, height}|null>}
   */
  async getBoundingBox(nodeId) {
    try {
      const result = await this.sendCommand('DOM.getBoxModel', { nodeId });
      if (result.model) {
        const quad = result.model.content;
        // quad 是 8 个数字：[x1,y1, x2,y2, x3,y3, x4,y4]
        const x = quad[0];
        const y = quad[1];
        const width = quad[2] - quad[0];
        const height = quad[5] - quad[1];
        return { x, y, width, height };
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  /**
   * 点击选择器匹配的元素
   * @param {string} selector - CSS 选择器
   */
  async clickSelector(selector) {
    
    // 支持 text= 选择器
    if (selector.startsWith('text=')) {
      const text = selector.slice(5);
      return this.clickByText(text);
    }
    
    // 支持 xpath= 前缀的选择器
    if (selector.startsWith('xpath=')) {
      const xpath = selector.slice(6);
      return this.clickByXPath(xpath);
    }
    
    // 支持直接的 XPath 选择器
    if (selector.startsWith('//') || selector.startsWith('/')) {
      return this.clickByXPath(selector);
    }
    
    // 支持 :has-text() 伪选择器 (Playwright 特有)
    if (selector.includes(':has-text(')) {
      const match = selector.match(/(.+):has-text\("(.+)"\)/);
      if (match) {
        const baseSelector = match[1];
        const text = match[2];
        return this.clickByTextInElement(baseSelector, text);
      }
    }
    
    const nodeId = await this.querySelector(selector);
    if (!nodeId) {
      throw new Error(`Element not found: ${selector}`);
    }

    const box = await this.getBoundingBox(nodeId);
    if (!box) {
      throw new Error(`Cannot get bounding box: ${selector}`);
    }

    // 点击元素中心
    const centerX = box.x + box.width / 2;
    const centerY = box.y + box.height / 2;

    // 如果元素不在视口内，先滚动到元素位置
    const viewportHeight = await this.evaluate('window.innerHeight');
    if (centerY > viewportHeight || centerY < 0) {
      // 滚动到元素位置（元素居中显示）
      const scrollY = Math.max(0, centerY - viewportHeight / 2);
      await this.evaluate(`window.scrollTo(0, ${scrollY})`);
      await this._sleep(100); // 等待滚动完成
      
      // 重新获取元素位置（滚动后坐标会变化）
      const newBox = await this.getBoundingBox(nodeId);
      if (newBox) {
        const newCenterX = newBox.x + newBox.width / 2;
        const newCenterY = newBox.y + newBox.height / 2;
        await this.click(newCenterX, newCenterY);
        return;
      }
    }

    await this.click(centerX, centerY);
  }

  /**
   * 通过文本内容点击元素
   * @param {string} text - 要匹配的文本
   */
  async clickByText(text) {
    // 使用 JavaScript 查找包含文本的元素
    const result = await this.evaluate(`
      (function() {
        const xpath = "//*[contains(text(), '${text.replace(/'/g, "\\'")}')]";
        const element = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        if (!element) return null;
        const rect = element.getBoundingClientRect();
        return {
          x: rect.x + rect.width / 2,
          y: rect.y + rect.height / 2
        };
      })()
    `);
    
    if (!result || !result.x) {
      throw new Error(`Element with text not found: ${text}`);
    }
    
    await this.click(result.x, result.y);
  }

  /**
   * 通过 XPath 点击元素
   * @param {string} xpath - XPath 表达式
   */
  async clickByXPath(xpath) {
    const result = await this.evaluate(`
      (function() {
        const element = document.evaluate("${xpath.replace(/"/g, '\\"')}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        if (!element) return null;
        const rect = element.getBoundingClientRect();
        return {
          x: rect.x + rect.width / 2,
          y: rect.y + rect.height / 2
        };
      })()
    `);
    
    if (!result || !result.x) {
      throw new Error(`Element not found by XPath: ${xpath}`);
    }
    
    await this.click(result.x, result.y);
  }

  /**
   * 通过基础选择器和文本内容点击元素
   * @param {string} baseSelector - CSS 选择器
   * @param {string} text - 要匹配的文本
   */
  async clickByTextInElement(baseSelector, text) {
    const result = await this.evaluate(`
      (function() {
        const elements = document.querySelectorAll("${baseSelector.replace(/"/g, '\\"')}");
        for (const el of elements) {
          if (el.textContent.includes("${text.replace(/"/g, '\\"')}")) {
            const rect = el.getBoundingClientRect();
            return {
              x: rect.x + rect.width / 2,
              y: rect.y + rect.height / 2
            };
          }
        }
        return null;
      })()
    `);
    
    if (!result || !result.x) {
      throw new Error(`Element not found: ${baseSelector}:has-text("${text}")`);
    }
    
    await this.click(result.x, result.y);
  }

  /**
   * 在选择器匹配的元素中输入文本
   * @param {string} selector - CSS 选择器
   * @param {string} text - 要输入的文本
   */
  async typeInSelector(selector, text) {
    // 支持 text=, xpath= 和 XPath 选择器
    if (selector.startsWith('text=') || selector.startsWith('xpath=') || selector.startsWith('//') || selector.startsWith('/')) {
      // 对于文本/XPath 选择器，使用 JavaScript 直接操作
      const escapedSelector = selector.replace(/'/g, "\\'").replace(/"/g, '\\"');
      const escapedText = text.replace(/'/g, "\\'").replace(/"/g, '\\"');
      
      let jsCode;
      if (selector.startsWith('text=')) {
        const searchText = selector.slice(5);
        jsCode = `
          (function() {
            const xpath = "//*[contains(text(), '${searchText.replace(/'/g, "\\'")}')]";
            const element = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (element && (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA')) {
              element.focus();
              element.value = '${escapedText}';
              element.dispatchEvent(new Event('input', { bubbles: true }));
              return true;
            }
            return false;
          })()
        `;
      } else {
        jsCode = `
          (function() {
            const element = document.evaluate("${selector.replace(/"/g, '\\"')}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (element && (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA')) {
              element.focus();
              element.value = '${escapedText}';
              element.dispatchEvent(new Event('input', { bubbles: true }));
              return true;
            }
            return false;
          })()
        `;
      }
      
      const result = await this.evaluate(jsCode);
      if (!result) {
        throw new Error(`Cannot type into element: ${selector}`);
      }
      return;
    }
    
    await this.clickSelector(selector);
    await this._sleep(100);
    await this.type(text);
  }

  // ============================================================
  // 截图
  // ============================================================

  /**
   * 截取页面截图
   * @param {object} options - 选项
   * @returns {Promise<string>} - Base64 编码的图片
   */
  async screenshot(options = {}) {
    const { format = 'jpeg', quality = 70, fullPage = false } = options;

    const params = {
      format,
    };

    if (format === 'jpeg') {
      params.quality = quality;
    }

    if (fullPage) {
      // 获取完整页面尺寸
      const metrics = await this.sendCommand('Page.getLayoutMetrics');
      params.clip = {
        x: 0,
        y: 0,
        width: metrics.contentSize.width,
        height: metrics.contentSize.height,
        scale: 1,
      };
    }

    const result = await this.sendCommand('Page.captureScreenshot', params);
    return result.data; // Base64
  }

  // ============================================================
  // JavaScript 执行
  // ============================================================

  /**
   * 执行 JavaScript 代码
   * @param {string} expression - JavaScript 表达式
   * @returns {Promise<any>}
   */
  async evaluate(expression) {
    const result = await this.sendCommand('Runtime.evaluate', {
      expression,
      returnByValue: true,
    });
    
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.text);
    }
    
    return result.result.value;
  }

  /**
   * 获取页面标题
   */
  async getTitle() {
    return this.evaluate('document.title');
  }

  /**
   * 获取当前 URL
   */
  async getURL() {
    return this.evaluate('window.location.href');
  }

  // ============================================================
  // 辅助方法
  // ============================================================

  _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * 获取调试器状态
   */
  getStatus() {
    return {
      attached: this.attached,
      url: this.wc.getURL(),
    };
  }
}

module.exports = { CDPBridge };

