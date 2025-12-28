/**
 * CDP Bridge - Electron internal browser control layer
 * 
 * Uses webContents.debugger API to control WebContentsView via CDP protocol
 * This is the core module for Option A-lite, doesn't affect existing screenshot stream solution
 * 
 * Features:
 * - Click elements (dispatchMouseEvent)
 * - Input text (insertText)
 * - Navigation (Page.navigate)
 * - Screenshot (Page.captureScreenshot)
 * - Get DOM (DOM.getDocument, DOM.querySelector)
 */

class CDPBridge {
  /**
   * @param {Electron.WebContents} webContents - WebContents instance to control
   */
  constructor(webContents) {
    this.wc = webContents;
    this.attached = false;
    this.messageHandlers = new Map();
    this._requestId = 0;
    this._inputEnabled = false; // Safety: keyboard/mouse input disabled by default
    this._destroyed = false;
  }
  
  /**
   * Enable keyboard/mouse input (call only when window is focused and ready)
   */
  enableInput() {
    this._inputEnabled = true;
    console.log('[CDPBridge] Input enabled');
  }
  
  /**
   * Disable keyboard/mouse input (call before switching windows or on blur)
   */
  disableInput() {
    this._inputEnabled = false;
    console.log('[CDPBridge] Input disabled');
  }
  
  /**
   * Check if input operations are safe to perform
   */
  _checkInputSafety(operation) {
    if (this._destroyed) {
      console.warn(`[CDPBridge] Blocked ${operation}: Bridge destroyed`);
      return false;
    }
    if (!this._inputEnabled) {
      console.warn(`[CDPBridge] Blocked ${operation}: Input not enabled`);
      return false;
    }
    if (!this.attached) {
      console.warn(`[CDPBridge] Blocked ${operation}: Not attached`);
      return false;
    }
    return true;
  }
  
  /**
   * Cleanup and destroy bridge - MUST call before app exit
   */
  destroy() {
    console.log('[CDPBridge] Destroying bridge...');
    this._destroyed = true;
    this._inputEnabled = false;
    this.messageHandlers.clear();
    
    if (this.attached) {
      try {
        this.wc.debugger.detach();
      } catch (e) {
        // Ignore detach errors during cleanup
      }
      this.attached = false;
    }
    console.log('[CDPBridge] Bridge destroyed');
  }

  /**
   * Attach debugger
   * @param {string} version - CDP protocol version, default '1.3'
   */
  async attach(version = '1.3') {
    // If already attached, return success directly
    if (this.attached) {
      console.log('[CDPBridge] Already attached, skipping');
      return true;
    }

    try {
      // Check if already attached (via try-catch)
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

      // Listen for detach event (register only once)
      if (!this._detachHandlerRegistered) {
        this.wc.debugger.on('detach', (event, reason) => {
          console.log('[CDPBridge] Debugger detached:', reason);
          this.attached = false;
        });
        this._detachHandlerRegistered = true;
      }

      // Listen for CDP messages (register only once)
      if (!this._messageHandlerRegistered) {
        this.wc.debugger.on('message', (event, method, params) => {
          const handler = this.messageHandlers.get(method);
          if (handler) {
            handler(params);
          }
        });
        this._messageHandlerRegistered = true;
      }

      // Enable necessary CDP domains
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
   * Detach debugger
   */
  detach() {
    if (this.attached) {
      try {
        this.wc.debugger.detach();
      } catch (e) {
        // Ignore detach errors
      }
      this.attached = false;
    }
  }

  /**
   * Send CDP command
   * @param {string} method - CDP method name
   * @param {object} params - Parameters
   * @returns {Promise<any>}
   */
  async sendCommand(method, params = {}) {
    if (!this.attached) {
      throw new Error('Debugger not attached');
    }
    return this.wc.debugger.sendCommand(method, params);
  }

  /**
   * Register CDP event handler
   * @param {string} method - Event method name
   * @param {function} handler - Handler function
   */
  on(method, handler) {
    this.messageHandlers.set(method, handler);
  }

  // ============================================================
  // Navigation Control
  // ============================================================

  /**
   * Navigate to URL
   * @param {string} url - Target URL
   */
  async navigate(url) {
    const result = await this.sendCommand('Page.navigate', { url });
    // Wait for page load to complete
    await this.waitForLoad();
    return result;
  }

  /**
   * Wait for page load to complete
   * @param {number} timeout - Timeout in milliseconds
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
   * Reload page
   */
  async reload() {
    await this.sendCommand('Page.reload');
    await this.waitForLoad();
  }

  // ============================================================
  // Mouse Control
  // ============================================================

  /**
   * Click at specified coordinates
   * @param {number} x - X coordinate
   * @param {number} y - Y coordinate
   * @param {object} options - Options
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

    // Short delay to simulate real click
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
   * Double click at specified coordinates
   */
  async doubleClick(x, y) {
    await this.click(x, y, { clickCount: 2 });
  }

  /**
   * Move mouse to specified position
   */
  async moveMouse(x, y) {
    await this.sendCommand('Input.dispatchMouseEvent', {
      type: 'mouseMoved',
      x,
      y,
    });
  }

  // ============================================================
  // Keyboard Control
  // ============================================================

  /**
   * Type text
   * @param {string} text - Text to input
   */
  async type(text) {
    await this.sendCommand('Input.insertText', { text });
  }

  /**
   * Press key
   * @param {string} key - Key name (e.g. 'Enter', 'Tab', 'Escape')
   */
  async pressKey(key) {
    // Safety check - prevent accidental keyboard input
    if (!this._checkInputSafety('pressKey')) {
      return { error: 'Input blocked for safety' };
    }
    
    // Special key mapping
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

    // For Enter key, also need to send rawKeyDown and trigger form submission
    if (key === 'Enter') {
      // Try to trigger form submission via JavaScript
      await this.evaluate(`
        (function() {
          const activeEl = document.activeElement;
          if (activeEl && activeEl.form) {
            activeEl.form.submit();
          } else if (activeEl) {
            // Trigger keydown and keypress events
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
  // DOM Operations
  // ============================================================

  /**
   * Get document root node
   */
  async getDocument() {
    const result = await this.sendCommand('DOM.getDocument');
    return result.root;
  }

  /**
   * Find element using CSS selector
   * @param {string} selector - CSS selector
   * @returns {Promise<number|null>} - Node ID
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
   * Get element bounding box
   * @param {number} nodeId - Node ID
   * @returns {Promise<{x, y, width, height}|null>}
   */
  async getBoundingBox(nodeId) {
    try {
      const result = await this.sendCommand('DOM.getBoxModel', { nodeId });
      if (result.model) {
        const quad = result.model.content;
        // quad is 8 numbers: [x1,y1, x2,y2, x3,y3, x4,y4]
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
   * Click element matching selector
   * @param {string} selector - CSS selector
   */
  async clickSelector(selector) {
    // Safety check - prevent accidental mouse input
    if (!this._checkInputSafety('clickSelector')) {
      return { error: 'Input blocked for safety' };
    }
    
    // Support text= selector
    if (selector.startsWith('text=')) {
      const text = selector.slice(5);
      return this.clickByText(text);
    }
    
    // Support xpath= prefix selector
    if (selector.startsWith('xpath=')) {
      const xpath = selector.slice(6);
      return this.clickByXPath(xpath);
    }
    
    // Support direct XPath selectors
    if (selector.startsWith('//') || selector.startsWith('/')) {
      return this.clickByXPath(selector);
    }
    
    // Support :has-text() pseudo-selector (Playwright specific)
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

    // Click element center
    const centerX = box.x + box.width / 2;
    const centerY = box.y + box.height / 2;

    // If element is not in viewport, scroll to element first
    const viewportHeight = await this.evaluate('window.innerHeight');
    if (centerY > viewportHeight || centerY < 0) {
      // Scroll to element position (center element in view)
      const scrollY = Math.max(0, centerY - viewportHeight / 2);
      await this.evaluate(`window.scrollTo(0, ${scrollY})`);
      await this._sleep(100); // Wait for scroll to complete
      
      // Re-get element position (coordinates change after scroll)
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
   * Click element by text content
   * @param {string} text - Text to match
   */
  async clickByText(text) {
    // Use JavaScript to find element containing text
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
   * Click element by XPath
   * @param {string} xpath - XPath expression
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
   * Click element by base selector and text content
   * @param {string} baseSelector - CSS selector
   * @param {string} text - Text to match
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
   * Type text into element matching selector
   * @param {string} selector - CSS selector
   * @param {string} text - Text to input
   */
  async typeInSelector(selector, text) {
    // Safety check - prevent accidental keyboard input
    if (!this._checkInputSafety('typeInSelector')) {
      return { error: 'Input blocked for safety' };
    }
    
    // Support text=, xpath= and XPath selectors
    if (selector.startsWith('text=') || selector.startsWith('xpath=') || selector.startsWith('//') || selector.startsWith('/')) {
      // For text/XPath selectors, use JavaScript direct manipulation
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
  // Screenshot
  // ============================================================

  /**
   * Take page screenshot
   * @param {object} options - Options
   * @returns {Promise<string>} - Base64 encoded image
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
      // Get full page dimensions
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
  // JavaScript Execution
  // ============================================================

  /**
   * Execute JavaScript code
   * @param {string} expression - JavaScript expression
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
   * Get page title
   */
  async getTitle() {
    return this.evaluate('document.title');
  }

  /**
   * Get current URL
   */
  async getURL() {
    return this.evaluate('window.location.href');
  }

  // ============================================================
  // Helper Methods
  // ============================================================

  _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Get debugger status
   */
  getStatus() {
    return {
      attached: this.attached,
      url: this.wc.getURL(),
    };
  }
}

module.exports = { CDPBridge };

