# NogicOS 架构文档

> 最后更新：2024-12-28

## 概述

NogicOS 是一个 AI 浏览器，核心叙事："用的人越多，所有人越快"。

## 目录结构

```
nogicos/
├── 📁 core/                    # 统一导出层 (R2)
│   └── __init__.py             # TaskRequest, TaskResponse, HealthStatus
│
├── 📁 engine/                  # 核心引擎
│   ├── browser/                # 浏览器控制
│   │   ├── session.py          # BrowserSession (Playwright)
│   │   ├── cdp.py              # CDPBrowser (Electron 模式)
│   │   └── recorder.py         # 动作录制器
│   │
│   ├── hive/                   # AI Agent (LangGraph)
│   │   ├── graph.py            # HiveAgent 状态图
│   │   ├── nodes.py            # 节点实现
│   │   └── state.py            # 状态定义
│   │
│   ├── knowledge/              # 知识存储
│   │   └── store.py            # KnowledgeStore + Skill
│   │
│   ├── learning/               # 学习系统
│   │   └── passive.py          # SmartRouter + ReplayExecutor
│   │
│   ├── skill/                  # SkillWeaver 集成
│   │   ├── synthesizer.py      # 技能合成
│   │   ├── executor.py         # 技能执行
│   │   └── extractor.py        # 参数提取
│   │
│   ├── server/                 # 服务组件
│   │   └── websocket.py        # StatusServer
│   │
│   ├── contracts/              # Pydantic 契约
│   ├── health/                 # 健康检查 (R4)
│   └── observability/          # 日志和追踪 (R3)
│
├── 📁 client/                  # Electron 客户端
│   ├── main.js                 # 主进程
│   ├── preload.js              # API 暴露
│   └── index.html              # UI
│
├── hive_server.py              # 主入口（HTTP + WebSocket）
├── api_keys.py                 # API 密钥
├── config.py                   # 配置
└── start_demo.bat              # 启动脚本
```

## 数据流

```
用户任务输入
    │
    ▼
hive_server.py (/execute)
    │
    ▼
SmartRouter.route(task, url)
    │
    ├─► Skill Path (confidence ≥ 0.7, skill exists)
    │       └─► SkillExecutor.execute() → Done (秒级)
    │
    ├─► Fast Path (confidence ≥ 0.7, trajectory exists)
    │       └─► 返回缓存结果 → Done (毫秒级)
    │
    └─► Normal Path (新任务)
            └─► HiveAgent.run()
                    │
                    ├─► 成功 → KnowledgeStore.save()
                    │           └─► SkillSynthesizer.synthesize()
                    │
                    └─► 失败 → 返回错误
```

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/execute` | POST | 执行 AI 任务 |
| `/stats` | GET | 知识库统计 |
| `/health` | GET | 基础健康检查 |
| `/health/detailed` | GET | 详细模块健康 |

## 关键模块

### SmartRouter

决定任务走哪条路径：
- **Skill Path**: 有匹配的学习技能
- **Fast Path**: 有匹配的轨迹缓存
- **Normal Path**: AI Agent 执行

### HiveAgent (LangGraph)

状态机实现的 AI Agent：
- `observe` → 获取页面状态
- `think` → LLM 决策
- `act` → 执行动作
- `evaluate` → 评估结果

### KnowledgeStore

知识存储：
- `data/knowledge/trajectories/` - 轨迹文件
- `data/knowledge/skills/` - 技能文件

## 配置

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `DEFAULT_MODEL` | claude-opus-4-5-20251101 | LLM 模型 |
| `BROWSER_HEADLESS` | False | 无头模式 |
| `BROWSER_TIMEOUT` | 15000 | 超时(ms) |

## 部署

```bash
# 开发模式
python hive_server.py

# 或使用启动脚本
start_demo.bat
```

## 版本历史

- **M7.5** (2024-12-27): Production Testing 完成
- **R1-R5** (2024-12-28): 架构重构完成

