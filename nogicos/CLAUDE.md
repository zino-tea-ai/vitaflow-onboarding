# NogicOS 项目上下文

## 这是什么
NogicOS 是一个 AI 浏览器，让 AI 自动执行网页任务，并通过共享知识库实现网络效应。

## 核心价值
**"用的人越多，所有人越快"**

- 第一次执行任务：AI 学习并保存 trajectory
- 再次执行：直接回放，速度提升 10x
- 知识共享：一个用户学会的，所有用户都能用

---

## 协作协议

> 基于 Anthropic Skills + Google Agent 白皮书 (Nov 2025)

### 角色定义
- **你 (Zino)** = Orchestration Layer（定目标、管节奏、做决策）
- **我** = Model + Tools（扫描、思考、执行、汇报）

### 任务执行流程
```
Mission → Scan → Think → Act → Observe
```

### 关键文件优先级
| P0 | `PROGRESS.md` - 当前状态 |
| P0 | `WORKFLOW.md` - 协作协议 |
| P1 | `CHANGELOG.md` - 变更记录 |
| P1 | `.cursorrules` - 开发规则 |

**详见 `WORKFLOW.md`**

---

## 技术架构

```
Electron Client (React)
        ↓ WebSocket
Python Engine (Hive)
├── Router (任务路由)
├── Agent (LangGraph 状态机)
├── Knowledge (本地向量库)
└── Browser (Playwright + CDP)
        ↓
    Claude Opus 4.5
```

## 当前阶段
**Phase 2: 客户端集成 + Demo 准备** (2024/12/27 - 2025/1/10)

重点任务：
1. M7: Demo Ready (1/6)
2. M8: YC 提交 (1/10)

## 关键决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 开发优先级 | Python 引擎优先 | 核心价值验证 |
| 被动学习 | 默认开启 | 网络效应需要 |
| 云端同步 | 先本地 | 降低复杂度 |

## 目录结构

```
nogicos/
├── engine/          # Python 后端（重点）
│   ├── hive/        # LangGraph Agent
│   ├── browser/     # Playwright 控制
│   ├── knowledge/   # 知识存储
│   └── server/      # WebSocket 服务
├── client/          # Electron 前端（最简）
├── contracts/       # Pydantic 契约
├── health/          # 健康检查
├── tests/           # 测试
├── WORKFLOW.md      # 协作协议（新增）
├── PROGRESS.md      # 进度追踪
├── ROADMAP.md       # 时间表
└── CHANGELOG.md     # 变更日志
```

## 命令速查

```bash
# 健康检查
python -m health.checks

# 运行引擎
cd engine && python server.py

# 运行测试
pytest tests/ -v

# 快速验证
python quick_test.py
```

## YC 申请
- 截止：2025年2月9日
- 目标提交：2025年1月10日
- Demo：60秒视频展示网络效应

## 禁止事项

1. ❌ 不要改云端同步相关的代码（还没到时候）
2. ❌ 不要在 Electron 上花太多时间（最简即可）
3. ❌ 不要用中文注释（编码问题）
4. ❌ 不要跳过测试说完成

## 遇到问题时

### 技术问题
1. 先跑 `python -m health.checks` 定位模块
2. 看 `logs/` 目录的追踪日志
3. 跑对应模块的契约测试
4. 实在不行，问用户

### 进度问题
**30 分钟规则**：
- 能解决 → 解决，一句话汇报
- 不能解决 → 停下来，汇报选项，等用户决定

**调整原则**：
- YC 1/10 不能动
- 砍功能 > 降质量
- Demo 最优先

---

## 每次开始工作必读

1. `PROGRESS.md` - 当前在哪，今天做什么
2. `WORKFLOW.md` - 协作协议
3. `.cursorrules` - 开发规范
