/**
 * Agent 类型定义
 * Phase 7: 扩展状态系统
 */

// 10 种细粒度状态
export type AgentStatus =
  | 'idle'       // 空闲
  | 'queued'     // 排队中（并发限制）
  | 'thinking'   // AI 思考中
  | 'planning'   // 生成执行计划
  | 'executing'  // 执行工具
  | 'verifying'  // 截图验证中
  | 'waiting'    // 等待窗口响应
  | 'confirm'    // 等待用户确认
  | 'paused'     // 用户暂停
  | 'recovering' // 从错误恢复
  | 'completed'  // 完成
  | 'failed';    // 失败

// Agent 进度信息
export interface AgentProgress {
  iteration: number;        // 当前迭代
  maxIterations: number;    // 最大迭代
  toolCalls: number;        // 已执行工具数
  currentWindow: string;    // 当前操作窗口
  estimatedTime?: number;   // 预估剩余时间(秒)
}

// 状态显示配置
export interface StatusDisplay {
  icon: string;
  label: string;
  color: string;
  animation: AnimationType | null;
}

// 动画类型
export type AnimationType =
  | 'pulse'
  | 'spin'
  | 'bounce'
  | 'blink'
  | 'scan'
  | 'shake'
  | 'check';

// Agent 事件类型
export interface AgentEvent {
  type: 'status' | 'progress' | 'error' | 'confirm' | 'complete' | 'tool' | 'toast';
  taskId: string;
  data: unknown;
  timestamp: number;
}

// Agent 控制器接口
export interface AgentController {
  startTask: (task: string, targetHwnds: number[]) => Promise<{ taskId: string }>;
  stopTask: (taskId: string) => Promise<void>;
  resumeTask: (taskId: string) => Promise<void>;
  emergencyStop: () => void;
  togglePause: () => void;
  confirmPendingAction: () => void;
  cycleActiveWindow: () => void;
}

// Agent 任务状态
export interface AgentTask {
  id: string;
  task_text: string;
  status: AgentStatus;
  progress: AgentProgress;
  targetHwnds: number[];
  createdAt: number;
  updatedAt: number;
}

// 错误类型
export type AgentErrorType =
  | 'api_timeout'
  | 'window_lost'
  | 'tool_failed'
  | 'emergency_stop'
  | 'connection_error'
  | 'unknown';

// 错误信息
export interface AgentError {
  type: AgentErrorType;
  message: string;
  detail?: string;
  recoverable: boolean;
}
