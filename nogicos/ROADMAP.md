# NogicOS 开发路线图

## 目标
- **截止日期**：2025年1月10日提交 YC
- **核心叙事**："用的人越多，所有人越快"

---

## 关键决策（已确认，不可更改）

| 问题 | 决策 | 理由 |
|------|------|------|
| 开发优先级 | Python 引擎优先 | 核心价值验证优先 |
| Electron | 并行做最简壳子 | Demo 需要可视化 |
| 被动学习 | 默认开启 + 透明控制 | 网络效应是核心 |
| 云端同步 | 先本地，接口预留 | 降低复杂度，Demo 用模拟 |

---

## 时间表

### Week 1 (12/27 - 1/2): 核心引擎

| 日期 | 任务 | 产出 |
|------|------|------|
| 12/27 | LangGraph Agent 重写 | `engine/hive/graph.py` |
| 12/28 | Memory persistence | InMemorySaver + InMemoryStore |
| 12/29 | Browser CDP 控制 | Playwright connect_over_cdp |
| 12/30 | Knowledge 模块完善 | 向量搜索 + 本地存储 |
| 12/31 | Router 智能路由 | 快速路径 vs 正常路径 |
| 1/1 | 被动学习 Recorder | CDP 事件捕获 |
| 1/2 | 集成测试 | 端到端流程验证 |

### Week 2 (1/3 - 1/9): 客户端 + Demo

| 日期 | 任务 | 产出 |
|------|------|------|
| 1/3 | Electron 最简壳子 | webview + 状态栏 |
| 1/4 | CDP 桥接 | Electron ↔ Playwright |
| 1/5 | Demo 场景准备 | 预置 trajectory 数据 |
| 1/6 | Demo 视频录制 | 60秒产品视频 |
| 1/7 | YC 申请表填写 | 全部问题回答 |
| 1/8 | 创始人视频 | 1分钟介绍 |
| 1/9 | 最终检查 + 提交 | - |

---

## 模块状态

| 模块 | 状态 | 负责文件 |
|------|------|----------|
| Hive Agent | 🔴 需重构 | `engine/hive/graph.py` |
| Knowledge | 🟡 基础完成 | `engine/knowledge/store.py` |
| Router | 🟢 已完成 | `engine/router.py` |
| Browser | 🟡 需 CDP 增强 | `engine/browser/session.py` |
| Recorder | 🔴 未开始 | `engine/browser/recorder.py` |
| Electron | 🔴 未开始 | `client/` |

状态说明：🔴 未开始/需重构 | 🟡 进行中 | 🟢 已完成

---

## Demo 视频脚本 (60秒)

```
[0:00-0:15] 第一次执行
"帮我在 Hacker News 搜索 AI"
→ 30秒完成（展示 AI 思考过程）

[0:15-0:30] 再次执行（快）
"再搜一次 Machine Learning"
→ 5秒完成
"它已经学会了"

[0:30-0:45] 换电脑（也快）
→ 同样 5秒（用预置数据模拟）
"知识是共享的"

[0:45-0:60] 价值主张
"用的人越多，所有人越快"
→ NogicOS logo
```

---

## 风险和应对

| 风险 | 概率 | 应对 |
|------|------|------|
| LangGraph 学习成本高 | 中 | 已有文档，Context7 辅助 |
| CDP 桥接复杂 | 中 | browser-use 有参考代码 |
| Demo 时间不够 | 低 | 可用屏幕录制 + 剪辑 |
| 被动学习误识别 | 中 | 先做最简规则，后期优化 |

---

## 每日检查

开始工作前：
1. 读 `ROADMAP.md` 确认今日任务
2. 读 `.cursorrules` 确认开发规范
3. 跑 `python -m health.checks` 确认系统状态

结束工作时：
1. 更新模块状态
2. 提交代码
3. 记录遇到的问题

