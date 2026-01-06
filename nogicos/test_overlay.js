/**
 * 快速测试 Overlay 功能
 * 在 Electron 主进程控制台运行
 */

const { BrowserWindow } = require('electron');

// 导入 overlay 控制器
const overlayController = require('./client/overlay-controller');

async function testOverlay() {
  console.log('=== Testing Overlay ===');
  
  const manager = overlayController.getOverlayManager();
  console.log('Overlay available:', manager.isAvailable);
  
  if (manager.isAvailable) {
    // 尝试附加到 Notepad
    console.log('Attaching to Notepad...');
    const result = manager.attach('Notepad', 'desktop');
    console.log('Result:', result);
  }
}

testOverlay();
