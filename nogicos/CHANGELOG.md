# NogicOS 变更日志

## 2025-12-27 方案 A 架构修复

### 问题
- CDP Bridge 错误地控制了主窗口 (`mainWindow.webContents`)
- 当 Python 发送 `navigate` 命令时，整个 NogicOS UI 被替换成目标网页

### 修复
1. **架构重构**：使用 `BrowserWindow` + `BrowserView` (Electron 28 兼容)
   - 主窗口加载 `index.html` (NogicOS UI)
   - `aiView` (BrowserView) 作为 CDP 控制目标

2. **CDP Bridge 目标修正**：
   - 从 `mainWindow.webContents` → `aiView.webContents`
   - AI 操作在 `aiView` 中进行，不影响主 UI

3. **双视图布局**：
   - UI 占据整个窗口
   - 执行任务时，`aiView` 自动显示在右侧 50%
   - 通过 `setAiViewVisible()` 控制显示/隐藏

### 新增功能
- 模式切换按钮：在状态栏点击 `CDP` / `Stream` 切换方案
- IPC 通信：`show-ai-view`, `hide-ai-view` 控制 AI 视图

> 记录计划调整、问题应对、决策变更

---

## 变更类型说明

| 类型 | 说明 | 示例 |
|------|------|------|
| 🔄 PIVOT | 方向性调整 | 技术选型变更 |
| ⏰ RESCHEDULE | 时间调整 | 检查点延期/提前 |
| ➕ ADD | 新增任务 | 发现必要的新工作 |
| ➖ CUT | 砍掉任务 | 范围缩减 |
| 🐛 BLOCK | 阻塞问题 | 需要解决才能继续 |
| 💡 LEARN | 经验教训 | 以后要注意的 |

---

## 变更记录

### 2024-12-27 (方案 A: CDP Bridge)

**[➕ ADD] Electron 内部 CDP 控制层**

背景：
- 方案 B（截图流）已完成并验证通过
- 用户要求 A/B 测试，验证纯 Electron 控制是否更优
- 关键约束：不影响现有功能

实现方案 A-lite（混合方案）：
1. **CDP Bridge 模块** (`client/cdp-bridge.js`)
   - 使用 `webContents.debugger` API
   - 支持 CDP 命令：点击、输入、导航、截图、DOM 查询
   - 独立模块，不修改现有代码

2. **IPC 通道** (`client/main.js` 扩展)
   - WebSocket 消息类型：`cdp_command`, `cdp_response`, `cdp_ready`
   - 支持异步命令-响应模式

3. **Python CDP 客户端** (`engine/browser/cdp_client.py`)
   - `CDPClient` 类：封装 CDP 命令发送
   - 支持：navigate, click, type, screenshot, evaluate 等
   - 高级操作：fill_form, wait_for_selector

4. **测试脚本** (`tests/test_cdp_bridge.py`)
   - 验证 Python → WebSocket → Electron → CDP 链路

文件变更：
- `client/cdp-bridge.js` - 新建 CDP Bridge 模块
- `client/main.js` - 添加 CDP 命令处理
- `engine/browser/cdp_client.py` - 新建 Python CDP 客户端
- `tests/test_cdp_bridge.py` - 新建测试脚本

测试结果（2024-12-27）：
- ✓ WebSocket 连接成功
- ✓ CDP Bridge 就绪
- ✓ get_url: 获取当前 URL
- ✓ get_title: 获取页面标题 "NogicOS"
- ✓ evaluate: JavaScript 执行 (1+1=2)
- ✓ screenshot: 截图 (64KB base64)
- ✓ query_selector: DOM 查询 (body nodeId: 5)

状态：✅ 测试通过 5/5

### CDP 模式端到端测试（2024-12-27）

测试内容：使用 `use_cdp=True` 执行完整任务

结果：
- ✓ 任务执行成功
- ✓ 路径: normal (CDP 模式)
- ✓ 步数: 1
- ✓ 耗时: 7.95s

修复问题：
1. CDP 双向通信：添加 `send_cdp_command` 方法实现 Python → Electron 命令-响应
2. Debugger 重复附加：修复页面导航时的 "already attached" 错误

---

### 2024-12-27 (方案 B: 截图流 - 已完成)

**[✓ DONE] Playwright + 截图流方案**

问题修复：
1. **Chrome 窗口问题** - `headless=True` 修复
2. **AI Panel 不显示** - CSP 添加 `img-src data:` 修复

验证结果：
- ✓ 无外部 Chrome 窗口
- ✓ AI Panel 实时显示截图流
- ✓ 不影响用户操作

---

### 2024-12-27 (双屏可视化升级)

**[➕ ADD] 双 Webview 分屏布局 + Motion 动效**

需求：
- Demo 不够强，需要展示 AI 操作过程
- 用户要求"不干扰操作权"的可视化方案
- 要求顶级动效设计

实现方案：
1. **双 Webview 分屏**
   - 左侧：用户浏览区（可独立操作）
   - 右侧：AI 操作区（实时显示 AI 操作）
   - 可拖动分割线
   - 默认收起，执行任务时自动展开

2. **Motion 动效系统** (`engine/browser/visual.py`)
   - Spring 边角高亮（元素聚焦）
   - 点击涟漪效果（3 层动画叠加）
   - 输入指示器
   - 学习通知

3. **Agent 流程集成** (`engine/hive/nodes.py`)
   - `_extract_visual_info()`: 解析代码中的操作类型和目标
   - 执行前高亮目标元素
   - 执行后显示点击涟漪

文件变更：
- `client/index.html` - 双 webview 布局
- `engine/browser/visual.py` - Motion 动效模块（新增）
- `engine/browser/session.py` - 集成视觉反馈重置
- `engine/hive/nodes.py` - act_node 集成动效

---

### 2024-12-27 (后续 - 匹配精度修复)

**[🐛 FIX] Fast Path 匹配精度问题**

问题：
- "Search for Python news" 错误匹配到 "Search for AI news" 缓存
- 返回 AI 相关结果而非 Python 相关结果

根因：
1. 搜索阈值过低（0.5）
2. 关键词提取过滤掉了 "AI"（因为 len("ai") == 2）
3. 域名加成过高（+15%）

修复：
- `_extract_key_terms()` 添加 `important_short_terms` 白名单：`{'ai', 'ml', 'ux', 'ui', 'js', 'py', 'db', 'api'}`
- 提高搜索阈值：0.5 → 0.7
- 降低域名加成：15% → 5%
- 添加关键词匹配检查：key_score < 0.5 时惩罚 70%

验证：
```
Task: "Search for Python news" vs "Search for AI news"
Before: similarity=0.76, path=fast (错误)
After:  similarity=0.26, path=normal (正确)
```

文件变更：
- `engine/knowledge/store.py`

---

### 2024-12-27 (深夜 - 架构重构 R1-R5)

**[🔄 REFACTOR] 模块化重构**

#### R1: 清理废弃文件 ✅

删除的文件：
- `main.py` - 废弃入口文件
- `run.py` - 废弃入口文件
- `convert_to_word.py` - 一次性脚本
- `engine/router.py` - 被 SmartRouter 替代

#### R2: 建立 core/ 统一契约层 ✅

新增：
- `core/__init__.py` - 统一导出点
  - `TaskRequest`, `TaskResponse` - 统一请求/响应模型
  - `HealthStatus` - 健康状态模型
  - 重导出 config 和 contracts

#### R3: 集成 Observability ✅

修改：
- `hive_server.py` - 使用 `engine.observability.setup_logging()`
- `engine/observability/__init__.py` - 添加防重复初始化

效果：
- 日志写入文件：`logs/nogicos_*.log`
- 统一格式：`时间 | 模块 | 级别 | 消息`

#### R4: 集成 Health 模块 ✅

新增端点：
- `GET /health/detailed` - 模块级健康检查

响应示例：
```json
{
  "overall": "healthy",
  "server": {"engine": true, "executing": false, "uptime_seconds": 6.4},
  "modules": {
    "hive": {"status": "healthy"},
    "browser": {"status": "healthy"},
    "knowledge": {"status": "healthy"}
  }
}
```

#### R5: 文档更新 ✅

更新：
- `CHANGELOG.md` - 本记录
- `PROGRESS.md` - 进度更新

---

### 2024-12-27 (晚上 - M7.5 Production Testing)

**[✅ DONE] Production-Level 测试和修复**

触发原因：
- 需要确保 NogicOS 达到 Production Ready 状态
- 发现 Python 3.14 与 Pydantic V1 兼容性警告
- 缺少全局超时保护和增强监控

实现内容：

1. **环境验证** (M1)
   - Python 3.14.2 + 核心依赖验证
   - API Keys 配置检查
   - Playwright 浏览器安装验证

2. **服务器稳定性** (M2)
   - 警告过滤：Pydantic V1, ForwardRef, websockets
   - websocket.py 移除弃用 API 使用
   - hive_server.py 添加 warnings.filterwarnings

3. **核心路径测试** (M3)
   - Normal Path: AI Agent 执行新任务 (5.8s)
   - Skill Path: 使用学习技能 (39s)
   - Fast Path: 轨迹重放 (0.001s, ~4900x 加速)

4. **边缘情况处理** (M4)
   - 无效域名: 3次重试后优雅失败
   - 空任务: AI 智能响应
   - 无效 JSON: FastAPI 验证拦截

5. **错误恢复验证** (M5)
   - 重试机制: max_retries=2, 共 3 次
   - 指数退避: 2^attempt 秒
   - Skill → Normal fallback 代码验证

6. **Watchdog 增强** (M6)
   - 全局请求超时: 120s asyncio.wait_for
   - 增强 /health: uptime_seconds, memory_mb, executing, current_task
   - 安装 psutil 进程监控
   - server_start_time 记录

修复文件：
- `hive_server.py`: 警告过滤 + 全局超时 + 增强 Health
- `engine/server/websocket.py`: 移除弃用 WebSocketServerProtocol 导入

测试结果：
```
CP1 环境验证      ✅ 通过
CP2 服务器启动    ✅ 通过 (无警告)
CP3 核心路径      ✅ 3/3 路径工作
CP4 边缘情况      ✅ 4/4 测试通过
CP5 错误恢复      ✅ 机制验证
CP6 Production    ✅ 监控增强
```

---

### 2024-12-27 (凌晨 - M1-M6 链路修复)

**[FIX] 完整链路串联 - 让"第二次真的快"**

触发原因：
- Review 发现 M1-M6 组件存在但没有完整串联
- SmartRouter 和 ReplayExecutor 没有被调用
- HiveAgent 保存 trajectory 到 `data/trajectories/`，但 SmartRouter 查询 `data/knowledge/`
- main.py 引用已删除的旧代码

修复内容：

1. **统一存储** (graph.py)
   - HiveAgent 添加 `knowledge_store` 参数
   - `_save_trajectory()` 改为保存到 KnowledgeStore
   - 成功的 AI 执行会自动保存，供下次复用

2. **新入口文件** (run.py)
   - `NogicOS` 类：集成完整链路
   - 执行前先查询 SmartRouter
   - Fast path (confidence >= 0.7) -> ReplayExecutor
   - Normal path -> HiveAgent -> 保存到 KnowledgeStore

3. **接口统一** (session.py)
   - 添加 `page` 属性（`active_page` 别名）
   - 添加 `stop()` 方法（`close()` 别名）
   - 与 CDPBrowser 接口保持一致

4. **验证脚本** (verify_fast_path.py)
   - 测试完整链路
   - 验证"第一次慢，第二次快"

测试结果：
```
[PASS] Test 1: First time -> Normal path
[PASS] Test 2: Second time -> Fast path (100% confidence)
[PASS] Test 3: Similar task -> normal path (52%)
[PASS] Test 4: Unrelated -> Normal path
Result: 4/4 tests passed
```

架构修复后：
```
Task Input
    |
    v
SmartRouter.route(task, url)
    |
    +-> confidence >= 0.7 -> ReplayExecutor.execute() -> Done (2-3s)
    |
    +-> confidence < 0.7 -> HiveAgent.run() -> Success -> KnowledgeStore.save()
                                                             |
                                                             v
                                                    Next time -> Fast path
```

---

### 2024-12-26 (晚上 - M6 Electron UI)

**[✅ DONE] M6 Electron 客户端完善**

实现内容（基于 Context7 Electron IPC + WebSocket）：

1. **engine/server/websocket.py** - WebSocket 状态广播服务器
   - `StatusServer`: 管理客户端连接和消息广播
   - `AgentStatus`, `LearningStatus`, `KnowledgeStats`: 状态数据类
   - 支持多客户端同时连接
   - 心跳检测 (ping/pong)

2. **client/main.js** - Electron 主进程升级
   - WebSocket 客户端，自动重连
   - IPC 桥接 Python ↔ Renderer
   - 进度条集成 `win.setProgressBar()`
   - 状态转发到 renderer

3. **client/preload.js** - 安全 API 暴露
   - `window.nogicos.onStatusUpdate()`: 状态回调
   - `window.nogicos.sendCommand()`: 发送命令
   - `window.nogicos.onConnectionChange()`: 连接状态

4. **client/index.html** - UI 升级
   - AI 状态指示器（idle/thinking/acting/done/error）
   - 被动学习录制按钮
   - 知识库统计显示
   - 连接状态显示
   - CSS 动画效果

架构：
```
┌─────────────────────────────────────────────────────────────┐
│  Electron Client                                            │
│  ┌─────────────────┐  IPC  ┌─────────────────────────────┐ │
│  │  main.js        │◄─────►│  renderer (index.html)      │ │
│  │  (WebSocket     │       │  • AI 状态指示器            │ │
│  │   client)       │       │  • 录制按钮                 │ │
│  └────────┬────────┘       │  • 知识库统计               │ │
│           │                └─────────────────────────────┘ │
└───────────│─────────────────────────────────────────────────┘
            │ WebSocket
            ▼
┌─────────────────────────────────────────────────────────────┐
│  Python Engine                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  StatusServer (ws://localhost:8765)                 │   │
│  │  • 广播 agent_status, learning_status, knowledge    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

测试结果：
- test_server.py: 6/6 通过
- quick_test.py: 7/7 通过

---

### 2024-12-26 (晚上 - M5 被动学习)

**[✅ DONE] M5 被动学习系统**

实现内容（基于 Context7 + DeepWiki 2025 最佳实践）：

1. **engine/browser/recorder.py** - 动作录制器
   - `RecordedAction`: 单个动作数据类
   - `RecordedTrajectory`: 动作序列，可生成 Playwright 脚本
   - `Recorder`: 通过 CDP 事件 + JS 注入捕获用户操作
   - `AutoRecorder`: 自动录制，idle 检测

2. **engine/knowledge/store.py** - 知识库升级
   - 语义搜索（关键词匹配 fallback）
   - 域名命名空间隔离
   - Replay 代码生成
   - 统计和监控

3. **engine/learning/passive.py** - 被动学习系统
   - `PassiveLearningSystem`: 协调 Recorder + KnowledgeStore
   - `SmartRouter`: 决定 fast path (replay) vs normal path (agent)
   - `ReplayExecutor`: 执行 replay 代码

测试结果：
- test_passive_learning.py: 5/5 通过
- quick_test.py: 6/6 通过（新增 SmartRouter 测试）

架构：
```
User Actions → Recorder → KnowledgeStore
                              │
Future Tasks → SmartRouter ───┤
               │              │
               ├─ fast path ◄─┘ (replay)
               │
               └─ normal path → HiveAgent
```

---

### 2024-12-26 (晚上 - M4 CDP)

**[✅ DONE] M4 CDP 控制**

实现内容：

1. **engine/browser/cdp.py** - CDP 桥接模块
   - `CDPBrowser` 类：通过 CDP 连接外部浏览器
   - `connect_over_cdp()` 连接 Electron/Chrome
   - 支持重试逻辑（指数退避）
   - 兼容 `BrowserSession` 接口（可直接传给 HiveAgent）

2. **client/** - Electron 最简客户端
   - `main.js`：主进程，启动时开启 CDP 端口 9222
   - `index.html`：简洁 UI，工具栏 + webview + 状态栏
   - `package.json`：`npm start` 自动带 CDP 参数

3. **测试验证**
   - `test_cdp.py`: 5/5 通过（CDP 模块测试）
   - `test_cdp_integration.py`: 3/3 通过（完整集成测试）
   - HiveAgent 成功通过 CDP 控制 Electron 内的页面

架构：
```
Electron App (Port 9222)    Python Engine
┌──────────────────┐        ┌──────────────────┐
│ main.js          │◄──────►│ CDPBrowser       │
│ <webview>        │  CDP   │ HiveAgent        │
│ index.html       │  WS    │ Playwright       │
└──────────────────┘        └──────────────────┘
```

---

### 2024-12-26 (晚上 - Review 修复)

**[✅ DONE] 基于 2025 最佳实践的 Review 修复**

修复内容（基于 Context7 + DeepWiki + Anthropic 最佳实践）：

1. **Error 分类处理** (nodes.py)
   - 添加 `APIConnectionError` 处理：指数退避重试
   - 添加 `RateLimitError` 处理：等待 30s 重试
   - 添加 `APIStatusError` 处理：4xx 不重试，5xx 重试
   - 最大重试次数：3 次

2. **Context 动态截断** (nodes.py)
   - 新增 `estimate_tokens()` 函数
   - 新增 `truncate_axtree()` 智能截断
   - 保留页面顶部 + 交互元素（button, link, textbox）
   - 避免硬编码 `[:8000]`

3. **Verbose 日志** (graph.py)
   - HiveAgent 添加 `verbose` 参数
   - `verbose=True` 时启用 DEBUG 级别日志
   - 记录 LLM 调用、Token 估算、决策过程

测试结果：
- test_improvements.py: 4/4 通过
- test_agent_basic.py: 5/5 通过
- quick_test.py: 全部通过

---

### 2024-12-26 (晚上)

**[✅ DONE] M3 Memory 持久化**

实现内容：
- InMemorySaver 用于会话内记忆持久化
- Trajectory 文件存储（JSON 格式保存到 data/trajectories/）
- HiveAgent 延迟初始化 LLM（无 API key 也能创建实例）
- get_history() 获取 checkpoint 历史
- get_threads() 列出会话线程

测试结果：
- test_persistence.py: 5/5 通过
- test_persistence_e2e.py: 通过（实际运行 HN 任务）
- quick_test.py: 5/5 通过

遗留问题：
- SQLite 跨重启持久化需要异步上下文管理，复杂度高
- 决定在 M7 阶段处理，当前用 InMemorySaver 足够 Demo

---

### 2024-12-26 (下午)

**[🔄 PIVOT] 目录结构重构**

触发原因：
- Review 发现有两套重复模块（顶层 + engine/）
- 导入混乱，容易出错

影响范围：
- 删除顶层 browser/, hive/, knowledge/, contracts/, health/, observability/
- 统一使用 engine/ 下的模块

应对措施：
- 重建 engine/contracts, engine/health, engine/observability, engine/knowledge
- 更新所有 import 路径
- 更新 quick_test.py 和 tests/

经验教训：
- 项目初期就要统一目录结构
- 迁移代码时不要保留旧文件

---

**[➕ ADD] 代码执行安全检查**

触发原因：
- Review 发现 exec() 直接执行 AI 生成代码有安全风险

应对措施：
- 添加危险模式黑名单检测
- 限制 __builtins__ 只允许安全函数
- 添加 30 秒执行超时
- 添加 SecurityError 异常类

---

**测试结果：**
- quick_test.py: 5/5 通过
- test_agent_basic.py: 5/5 通过（新增安全测试）

---

### 2024-12-26 (上午)

**初始化**
- 项目结构创建完成
- 开发文档体系建立
- 检查点 M1 完成
- 检查点 M2 完成（LangGraph Agent）

---

## 变更模板

```markdown
### YYYY-MM-DD

**[类型] 变更标题**

触发原因：
- 

影响范围：
- 

应对措施：
- 

调整后计划：
- 

经验教训：
- 
```

---

## 决策记录 (ADR)

### ADR-001: 开发优先级
- **日期**：2024-12-26
- **决策**：Python 引擎优先，Electron 最简壳并行
- **原因**：核心价值验证 > UI 展示
- **状态**：✅ 已确认

### ADR-002: 被动学习默认开启
- **日期**：2024-12-26
- **决策**：默认开启 + 透明提示 + 可关闭
- **原因**：网络效应是核心叙事
- **状态**：✅ 已确认

### ADR-003: 云端同步延后
- **日期**：2024-12-26
- **决策**：先本地，Demo 用模拟数据
- **原因**：降低复杂度，聚焦核心
- **状态**：✅ 已确认

---

## 问题追踪

| ID | 问题 | 发现日期 | 状态 | 解决方案 |
|----|------|----------|------|----------|
| - | - | - | - | - |

---

## 回顾问题清单

每次遇到阻塞时，问自己：

1. **这个问题会影响哪个检查点？**
2. **能否绕过？成本是什么？**
3. **需要调整时间表吗？**
4. **需要砍掉某些功能吗？**
5. **有什么经验教训要记录？**

