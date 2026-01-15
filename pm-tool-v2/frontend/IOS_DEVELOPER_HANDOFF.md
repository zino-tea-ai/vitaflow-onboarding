# VitaFlow Onboarding - iOS 开发交接文档

> **目标**：iOS 开发参考此 Web Demo 实现原生 Onboarding 流程  
> **Demo 地址**：https://vitaflow-onboarding.vercel.app/onboarding-demo/mobile  
> **分支**：`onboarding-ios-handoff-2026-01`

---

## 🚀 快速开始

### 1. Clone 并运行 Demo

```bash
# Clone 仓库
git clone https://github.com/zino-tea-ai/vitaflow-onboarding.git
cd vitaflow-onboarding

# 切换到交接分支
git checkout onboarding-ios-handoff-2026-01

# 进入前端目录
cd pm-tool-v2/frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 打开浏览器
# http://localhost:3000/onboarding-demo/mobile
```

### 2. 在线预览

直接访问：https://vitaflow-onboarding.vercel.app/onboarding-demo/mobile

---

## 📁 代码结构

```
pm-tool-v2/frontend/src/app/onboarding-demo/
├── mobile/                    # ⭐ iOS 参考的主入口
│   ├── page.tsx              # 主页面（PROD 版本配置）
│   └── layout.tsx            # 布局
├── components/
│   ├── screens/              # ⭐ 各类型屏幕组件
│   │   ├── LaunchScreen.tsx
│   │   ├── WelcomeScreen.tsx
│   │   ├── QuestionScreen.tsx
│   │   ├── NumberInputScreen.tsx
│   │   ├── TextInputScreen.tsx
│   │   ├── LoadingScreen.tsx
│   │   ├── ResultScreen.tsx
│   │   └── ...
│   ├── ui/                   # UI 组件（按钮、卡片等）
│   ├── motion/               # 动画组件
│   └── effects/              # 特效（粒子、Confetti）
├── data/
│   └── screens-config-production.ts  # ⭐ 20 页流程配置
├── lib/
│   └── design-tokens.ts      # ⭐ 设计规范（颜色、字体、间距）
└── store/
    └── onboarding-store.ts   # 状态管理（用户数据）
```

---

## 🎨 Design Tokens（设计规范）

### 颜色系统

```swift
// iOS 实现参考

// Slate 色阶 - 主色系统
struct Colors {
    // 主色
    static let slate900 = Color(hex: "#0F172A")  // 按钮、标题、选中态
    static let slate800 = Color(hex: "#1E293B")
    static let slate700 = Color(hex: "#334155")
    static let slate500 = Color(hex: "#64748B")  // 次要文字
    static let slate400 = Color(hex: "#94A3B8")  // Placeholder
    static let slate200 = Color(hex: "#E2E8F0")  // 分割线
    static let slate100 = Color(hex: "#F1F5F9")  // 容器背景
    static let slate50  = Color(hex: "#F8FAFC")  // 页面背景
    
    // 点缀色
    static let accent   = Color(hex: "#61E0BD")  // 薄荷绿 - 进度、成功
    static let accentLight = Color(hex: "#A7F3D0")
    
    // 语义色
    static let success  = Color(hex: "#61E0BD")
    static let error    = Color(hex: "#EF4444")
    static let warning  = Color(hex: "#F59E0B")
    
    // 基础色
    static let white    = Color(hex: "#FFFFFF")
    static let background = Color(hex: "#F8FAFC")
}
```

### 字体

```swift
// 字体：Outfit
// 字重：Regular (400) / Medium (500)
// 注意：最重只用 Medium，不用 Bold

struct Typography {
    static let display = Font.custom("Outfit", size: 48).weight(.medium)   // 大数字
    static let heading = Font.custom("Outfit", size: 28).weight(.medium)   // 页面标题
    static let title   = Font.custom("Outfit", size: 20).weight(.medium)   // 小标题
    static let body    = Font.custom("Outfit", size: 14).weight(.medium)   // 正文强调
    static let bodyRegular = Font.custom("Outfit", size: 14).weight(.regular) // 正文
    static let caption = Font.custom("Outfit", size: 12).weight(.regular)  // 辅助
    static let label   = Font.custom("Outfit", size: 10).weight(.medium)   // 标签
}
```

### 圆角

```swift
struct Radius {
    static let sm   = 6.0   // Tab 内部
    static let md   = 8.0   // Tab 容器
    static let lg   = 12.0  // 卡片、输入框
    static let xl   = 16.0  // 底部面板
    static let xxl  = 24.0  // 底部导航
    static let full = 1000.0 // 按钮、Pills
}
```

### 阴影

```swift
struct Shadows {
    // 小阴影 - 按钮、Pill
    static let sm = Shadow(
        color: Color(hex: "#0F172A").opacity(0.04),
        radius: 2,
        x: 0,
        y: 1
    )
    
    // 中阴影 - 卡片
    static let md = Shadow(
        color: Color(hex: "#0F172A").opacity(0.08),
        radius: 6,
        x: 0,
        y: 2
    )
    
    // 大阴影 - 弹窗
    static let lg = Shadow(
        color: Color(hex: "#0F172A").opacity(0.15),
        radius: 12,
        x: 0,
        y: 4
    )
    
    // CTA 按钮阴影
    static let cta = Shadow(
        color: Color(hex: "#0F172A").opacity(0.15),
        radius: 4,
        x: 0,
        y: 2
    )
}
```

---

## 📱 Onboarding 流程（20 页）

| # | 类型 | 标题 | 收集数据 | 说明 |
|---|------|------|----------|------|
| 1 | `launch` | VitaFlow | - | 启动页，自动前进 |
| 2 | `introduction` | Meet Vita | - | 角色介绍 |
| 3 | `welcome` | AI Photo Scan | - | 价值展示 |
| 4 | `text_input` | What's your name? | `name` | 姓名输入 |
| 5 | `combined_welcome_goal` | Nice to meet you | `goal` | 目标选择 |
| 6 | `value_prop` | Snap & Know | - | AI 扫描价值页 |
| 7 | `question_single` | What's your gender? | `gender` | 性别选择 |
| 8 | `number_input` | How old are you? | `age` | 年龄输入 |
| 9 | `combined_height_weight` | Height and weight | `height`, `currentWeight` | 身高体重 |
| 10 | `value_prop` | Personalized | - | 个性化价值页 |
| 11 | `question_single` | How active? | `activityLevel` | 活动量 |
| 12 | `number_input` | Target weight? | `targetWeight` | 目标体重 |
| 13 | `loading` | Analyzing... | - | 加载动画 |
| 14 | `result` | Your Plan | - | 结果展示 |
| 15 | `game_scan` | Try AI Scan | - | 扫描体验 |
| 16 | `value_prop` | Track progress | - | 进度追踪价值页 |
| 17 | `permission` | Stay on Track | `notificationEnabled` | 通知权限 |
| 18 | `value_prop` | Privacy | - | 隐私价值页 |
| 19 | `transition` | You're All Set! | - | 完成过渡 |
| 20 | `account` | Create account | - | 注册账号 |

---

## 🎬 关键交互

### 1. 页面切换动画

```swift
// 推荐：从右滑入，向左滑出
// 时长：0.3s
// 缓动：easeInOut
```

### 2. 按钮反馈

```swift
// 点击时：scale 0.98 + 轻微变暗
// 时长：0.1s
```

### 3. 选项卡选中

```swift
// 未选中：白色背景 + slate-200 边框
// 选中：白色背景 + slate-900 边框 (2px)
```

### 4. 数字输入（滚轮选择器）

```swift
// 使用 iOS 原生 Picker
// 显示当前值 + 单位
// 字号 48px，字重 Medium
```

### 5. 进度条

```swift
// 颜色：薄荷绿 #61E0BD
// 背景：slate-200
// 高度：4px
// 圆角：full
```

---

## ⚡ iOS 实现建议

### 状态管理

```swift
// 使用 @Observable 或 ObservableObject
class OnboardingStore: ObservableObject {
    @Published var currentStep = 1
    @Published var userData = UserData()
    
    struct UserData {
        var name: String = ""
        var goal: String = ""
        var gender: String = ""
        var age: Int = 25
        var height: Int = 170
        var currentWeight: Double = 70.0
        var targetWeight: Double = 65.0
        var activityLevel: String = ""
        var notificationEnabled: Bool = false
    }
}
```

### 页面路由

```swift
// 不需要 NavigationStack，用状态切换 View
// 根据 currentStep 显示对应 Screen

struct OnboardingFlow: View {
    @StateObject var store = OnboardingStore()
    
    var body: some View {
        Group {
            switch store.currentStep {
            case 1: LaunchScreen()
            case 2: IntroductionScreen()
            case 3: WelcomeScreen()
            // ...
            default: EmptyView()
            }
        }
        .environmentObject(store)
    }
}
```

---

## 📞 联系方式

如有问题，请联系 PM。

---

## 📎 参考文件

| 文件 | 说明 |
|------|------|
| `data/screens-config-production.ts` | 完整流程配置 |
| `lib/design-tokens.ts` | 设计规范 |
| `components/screens/*.tsx` | 各页面实现参考 |
| `components/ui/*.tsx` | UI 组件参考 |

---

*最后更新：2026/01/15*
