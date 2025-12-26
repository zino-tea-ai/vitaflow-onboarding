/**
 * NogicOS WebSocket Client
 * 连接到 AI 引擎服务器，接收实时执行状态
 */

const WebSocket = require('ws');
const { EventEmitter } = require('events');

class NogicOSWebSocketClient extends EventEmitter {
    constructor(url = 'ws://127.0.0.1:8765') {
        super();
        this.url = url;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 3000;
        this.isConnected = false;
    }

    connect() {
        console.log(`[WebSocket] Connecting to ${this.url}...`);
        
        try {
            this.ws = new WebSocket(this.url);
            
            this.ws.on('open', () => {
                console.log('[WebSocket] Connected to NogicOS AI Engine');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.emit('connected');
            });

            this.ws.on('message', (data) => {
                try {
                    const message = JSON.parse(data.toString());
                    this.handleMessage(message);
                } catch (e) {
                    console.error('[WebSocket] Failed to parse message:', e);
                }
            });

            this.ws.on('close', () => {
                console.log('[WebSocket] Connection closed');
                this.isConnected = false;
                this.emit('disconnected');
                this.scheduleReconnect();
            });

            this.ws.on('error', (error) => {
                console.error('[WebSocket] Error:', error.message);
                this.emit('error', error);
            });
        } catch (error) {
            console.error('[WebSocket] Connection failed:', error);
            this.scheduleReconnect();
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`[WebSocket] Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            setTimeout(() => this.connect(), this.reconnectDelay);
        } else {
            console.log('[WebSocket] Max reconnect attempts reached');
            this.emit('maxReconnectReached');
        }
    }

    handleMessage(message) {
        const { type, data } = message;
        console.log(`[WebSocket] ${type}:`, data);

        switch (type) {
            case 'connected':
                this.emit('serverConnected', data);
                break;
            case 'task_start':
                this.emit('taskStart', data);
                break;
            case 'task_complete':
                this.emit('taskComplete', data);
                break;
            case 'task_error':
                this.emit('taskError', data);
                break;
            case 'step_start':
                this.emit('stepStart', data);
                break;
            case 'step_thinking':
                this.emit('stepThinking', data);
                break;
            case 'step_action':
                this.emit('stepAction', data);
                break;
            case 'step_result':
                this.emit('stepResult', data);
                break;
            case 'step_complete':
                this.emit('stepComplete', data);
                break;
            case 'skill_matched':
                this.emit('skillMatched', data);
                break;
            case 'skill_executing':
                this.emit('skillExecuting', data);
                break;
            case 'skill_result':
                this.emit('skillResult', data);
                break;
            case 'learn_start':
                this.emit('learnStart', data);
                break;
            case 'learn_progress':
                this.emit('learnProgress', data);
                break;
            case 'skill_discovered':
                this.emit('skillDiscovered', data);
                break;
            case 'learn_complete':
                this.emit('learnComplete', data);
                break;
            case 'kb_loaded':
                this.emit('kbLoaded', data);
                break;
            case 'skill_list':
                this.emit('skillList', data);
                break;
            // AI 可视化动画消息（NogicOS Atlas 体验）
            case 'cursor_move':
                this.emit('cursorMove', data);
                break;
            case 'cursor_click':
                this.emit('cursorClick', data);
                break;
            case 'cursor_type':
                this.emit('cursorType', data);
                break;
            case 'cursor_stop_type':
                this.emit('cursorStopType', data);
                break;
            case 'highlight':
                this.emit('highlight', data);
                break;
            case 'highlight_hide':
                this.emit('highlightHide', data);
                break;
            case 'screen_glow':
                this.emit('screenGlow', data);
                break;
            case 'screen_glow_stop':
                this.emit('screenGlowStop', data);
                break;
            case 'screen_pulse':
                this.emit('screenPulse', data);
                break;
            default:
                console.log(`[WebSocket] Unknown message type: ${type}`);
        }
    }

    send(type, data) {
        if (this.ws && this.isConnected) {
            this.ws.send(JSON.stringify({ type, data }));
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    getConnectionStatus() {
        return this.isConnected;
    }
}

module.exports = { NogicOSWebSocketClient };
