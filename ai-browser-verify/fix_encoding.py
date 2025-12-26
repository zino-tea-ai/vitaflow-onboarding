# -*- coding: utf-8 -*-
"""Fix non-ASCII characters in Python files"""
import os
import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Common Chinese to English translations for comments
    replacements = {
        # Common patterns
        '已配置': 'configured',
        '未配置': 'not configured',
        '初始化': 'initialize',
        '连接': 'connect',
        '断开': 'disconnect',
        '成功': 'success',
        '失败': 'failed',
        '错误': 'error',
        '警告': 'warning',
        '开始': 'start',
        '结束': 'end',
        '完成': 'completed',
        '执行': 'execute',
        '运行': 'run',
        '测试': 'test',
        '调试': 'debug',
        '日志': 'log',
        '配置': 'config',
        '参数': 'parameter',
        '返回': 'return',
        '函数': 'function',
        '方法': 'method',
        '类': 'class',
        '模块': 'module',
        '导入': 'import',
        '导出': 'export',
        '创建': 'create',
        '删除': 'delete',
        '更新': 'update',
        '读取': 'read',
        '写入': 'write',
        '发送': 'send',
        '接收': 'receive',
        '请求': 'request',
        '响应': 'response',
        '状态': 'status',
        '消息': 'message',
        '数据': 'data',
        '文件': 'file',
        '目录': 'directory',
        '路径': 'path',
        '名称': 'name',
        '类型': 'type',
        '值': 'value',
        '键': 'key',
        '索引': 'index',
        '长度': 'length',
        '大小': 'size',
        '时间': 'time',
        '日期': 'date',
        '用户': 'user',
        '密码': 'password',
        '浏览器': 'browser',
        '页面': 'page',
        '元素': 'element',
        '选择器': 'selector',
        '等待': 'wait',
        '超时': 'timeout',
        '重试': 'retry',
        '跳过': 'skip',
        '忽略': 'ignore',
        '异常': 'exception',
        '处理': 'handle',
        '验证': 'verify',
        '检查': 'check',
        '清理': 'cleanup',
        '环境': 'environment',
        '变量': 'variable',
        '常量': 'constant',
        '客户端': 'client',
        '服务器': 'server',
        '端口': 'port',
        '地址': 'address',
        '协议': 'protocol',
        '版本': 'version',
        '实例': 'instance',
        '对象': 'object',
        '属性': 'property',
        '结果': 'result',
        '输出': 'output',
        '输入': 'input',
        '格式': 'format',
        '编码': 'encoding',
        '解码': 'decode',
        '加载': 'load',
        '保存': 'save',
        '缓存': 'cache',
        '队列': 'queue',
        '任务': 'task',
        '步骤': 'step',
        '阶段': 'phase',
        '模式': 'mode',
        '选项': 'option',
        '默认': 'default',
        '必须': 'must',
        '可选': 'optional',
        '启用': 'enable',
        '禁用': 'disable',
        '打开': 'open',
        '关闭': 'close',
        '添加': 'add',
        '移除': 'remove',
        '获取': 'get',
        '设置': 'set',
        '查找': 'find',
        '搜索': 'search',
        '替换': 'replace',
        '复制': 'copy',
        '粘贴': 'paste',
        '剪切': 'cut',
        '撤销': 'undo',
        '重做': 'redo',
        '确认': 'confirm',
        '取消': 'cancel',
        '继续': 'continue',
        '停止': 'stop',
        '暂停': 'pause',
        '恢复': 'resume',
        '重启': 'restart',
        '刷新': 'refresh',
        '同步': 'sync',
        '异步': 'async',
        '回调': 'callback',
        '事件': 'event',
        '监听': 'listen',
        '触发': 'trigger',
        '广播': 'broadcast',
        '订阅': 'subscribe',
        '取消订阅': 'unsubscribe',
        '知识库': 'knowledge base',
        '轨迹': 'trajectory',
        '技能': 'skill',
        '学习': 'learning',
        '探索': 'exploration',
        '模型': 'model',
        '代理': 'agent',
        '生成': 'generate',
        '解析': 'parse',
        '分析': 'analyze',
        '评估': 'evaluate',
        '优化': 'optimize',
        '提取': 'extract',
        '转换': 'convert',
        '映射': 'map',
        '过滤': 'filter',
        '排序': 'sort',
        '分组': 'group',
        '合并': 'merge',
        '拆分': 'split',
        '截图': 'screenshot',
        '快照': 'snapshot',
        '视口': 'viewport',
        '窗口': 'window',
        '标签页': 'tab',
        '导航': 'navigate',
        '点击': 'click',
        '填写': 'fill',
        '提交': 'submit',
        '选择': 'select',
        '拖拽': 'drag',
        '滚动': 'scroll',
        '聚焦': 'focus',
        '模糊': 'blur',
        '按键': 'key',
        '鼠标': 'mouse',
        '触摸': 'touch',
        '手势': 'gesture',
    }
    
    for zh, en in replacements.items():
        content = content.replace(zh, en)
    
    # Remove any remaining non-ASCII characters in comments
    lines = content.split('\n')
    fixed_lines = []
    for line in lines:
        if '#' in line:
            # Find comment part
            code_part = line.split('#')[0]
            comment_parts = line.split('#')[1:]
            comment = '#'.join(comment_parts)
            # Remove non-ASCII from comment
            comment = comment.encode('ascii', 'ignore').decode('ascii')
            line = code_part + '#' + comment if comment_parts else code_part
        
        # Also check docstrings - but keep structure
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    # Add UTF-8 declaration if not present
    if not content.startswith('# -*- coding'):
        content = '# -*- coding: utf-8 -*-\n' + content
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

# Fix all Python files
files_to_fix = [
    'SkillWeaver/skillweaver/attempt_task.py',
    'SkillWeaver/skillweaver/attempt_task_with_ws.py',
    'SkillWeaver/skillweaver/explore_with_ws.py',
    'SkillWeaver/skillweaver/lm.py',
    'SkillWeaver/skillweaver/websocket_server.py',
    'SkillWeaver/skillweaver/evaluation/evaluate_benchmark.py',
    'SkillWeaver/skillweaver/knowledge_base/type_checking.py',
]

for filepath in files_to_fix:
    if os.path.exists(filepath):
        if fix_file(filepath):
            print(f'Fixed: {filepath}')
        else:
            print(f'No changes: {filepath}')
    else:
        print(f'Not found: {filepath}')

print('\nDone!')

