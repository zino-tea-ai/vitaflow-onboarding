/**
 * 敏感操作类型定义
 * Phase 7.4: 敏感操作确认（重新设计）
 */

// 风险等级
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

// 敏感操作接口
export interface SensitiveAction {
  id: string;
  taskId: string;
  toolName: string;
  description: string;
  humanReadable: string;        // 人类可读描述
  risk: RiskLevel;
  timeout: number;              // 超时自动拒绝（秒）
  params: Record<string, unknown>;
  screenshot?: string;          // 截图 base64
  coordinates?: { x: number; y: number };
  windowName?: string;
  impact?: string;              // 操作影响说明
  createdAt: number;
}

// 敏感操作分级配置
export const SENSITIVE_TOOLS: Record<string, RiskLevel> = {
  'delete_file': 'critical',
  'execute_command': 'critical',
  'send_message': 'high',
  'window_type': 'medium',      // 密码输入时动态升级为 high
  'window_click': 'low',
  'keyboard_shortcut': 'medium',
  'open_application': 'medium',
  'close_window': 'high',
};

// 超时配置（秒）
export const TIMEOUT_BY_RISK: Record<RiskLevel, number> = {
  'low': 30,
  'medium': 20,
  'high': 15,
  'critical': 10,
};

// 风险等级颜色
export const RISK_COLORS: Record<RiskLevel, string> = {
  'low': '#10b981',      // green
  'medium': '#f59e0b',   // yellow
  'high': '#ef4444',     // red
  'critical': '#dc2626', // dark red
};

// 风险等级标签
export const RISK_LABELS: Record<RiskLevel, string> = {
  'low': '低风险',
  'medium': '中风险',
  'high': '高风险',
  'critical': '危险操作',
};

// 确认结果
export interface ConfirmationResult {
  actionId: string;
  taskId: string;
  approved: boolean;
  timestamp: number;
}
