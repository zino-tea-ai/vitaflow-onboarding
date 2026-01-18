# VitaFlow Onboarding 文案 Review 指南

> **线上预览**: https://vitaflow-onboarding.vercel.app/onboarding-demo/mobile  
> **最后更新**: 2026-01-18  
> **负责人**: 运营团队

---

## 📋 文案风格说明

我们提供 **3 种文案风格**，可在代码中切换：

| 风格 | 代号 | 特点 | 适用场景 |
|------|------|------|---------|
| 俏皮风趣 | `witty` | 幽默、有个性、年轻化 | **当前使用** ✅ |
| 温暖鼓励 | `warm` | 亲切、正能量、安全感 | 女性用户为主时 |
| 数据驱动 | `data` | 专业、精准、理性 | 科技用户为主时 |

---

## 📱 完整 20 页文案

### ═══════════════════════════════════════
### Phase 1: 品牌建立 (第 1-3 页)
### ═══════════════════════════════════════

---

### 📄 第 1 页 - 启动页 (Launch)

| 元素 | 内容 |
|------|------|
| **标题** | VitaFlow |
| **副标题** | Your AI Nutrition Companion |
| **交互** | 自动跳转（2秒） |
| **动效** | 粒子动画 |

**角色状态**: greeting (挥手问候)

---

### 📄 第 2 页 - 角色介绍 (Introduction)

| 元素 | 内容 |
|------|------|
| **标题** | Meet Vita |
| **副标题** | Your AI nutrition companion |
| **跳过按钮** | ✅ 显示 |

**角色对话** (序列播放，共 3 句):

| # | Witty 风格 | Warm 风格 | Data 风格 |
|---|-----------|----------|-----------|
| 1 | Hey there! 👋 | Hi! I'm Vita 👋 | Hello! I'm Vita. |
| 2 | I'm Vita, your AI nutrition sidekick. | I'll be with you every step of the way on your health journey. | Your AI-powered nutrition assistant. |
| 3 | Think of me as your pocket nutritionist... minus the boring lectures. | Let's make this fun and simple! | Let's analyze your goals and build a personalized plan. |

**开始按钮**:

| Witty | Warm | Data |
|-------|------|------|
| Let's do this! 💪 | Let's Get Started! | Start Analysis |

---

### 📄 第 3 页 - AI 扫描介绍 (Welcome)

| 元素 | 内容 |
|------|------|
| **标题** | AI Photo Scan |
| **副标题** | Snap a photo. Get instant nutrition insights powered by AI. |
| **社会证明** | ✅ 显示 (500K+ users) |

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| Let's build a health path just for you. | Let's start your health journey! | AI-powered nutrition tracking begins |

---

### ═══════════════════════════════════════
### Phase 2: 轻松开始 (第 4-6 页)
### ═══════════════════════════════════════

---

### 📄 第 4 页 - 输入名字 (Text Input)

| 元素 | 内容 |
|------|------|
| **标题** | What's your name? |
| **副标题** | We'll use this to personalize your experience |
| **输入框占位符** | Enter your name |
| **最大长度** | 30 字符 |

**角色状态**: listening (倾听)

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| What should I call you? | What's your name? | Enter your name to personalize |

**错误提示** (名字为空时):

| Witty | Warm | Data |
|-------|------|------|
| I need something to call you! | Please enter your name | Name field cannot be empty |

---

### 📄 第 5 页 - 选择目标 (Goal Selection)

| 元素 | 内容 |
|------|------|
| **标题** | Nice to meet you, {{name}}! |
| **副标题** | Choose your main goal |
| **个性化** | ✅ 使用用户名字 |

**选项**:

| ID | 图标 | 标题 | 副标题 |
|----|------|------|--------|
| lose_weight | TrendingDown | Lose Weight | Burn fat, get lighter |
| build_muscle | Dumbbell | Build Muscle | Gain strength and muscle |
| maintain | Scale | Maintain | Keep current weight |

**角色状态**: happy (开心)

**角色对话** (选项选择后):

| Witty | Warm | Data |
|-------|------|------|
| What's your top goal? | Choose the goal you want to achieve | Select goal to optimize recommendations |

**选择后反馈**:

| 选择 | Witty | Warm | Data |
|------|-------|------|------|
| 减肥 | Watch out, fat. Here comes trouble. 💪 | Great choice! Weight loss is a great start | Expected: lose 5-8kg in 12 weeks |
| 增肌 | Future you is already flexing. 🏆 | Great goal! Let's get stronger together | Expected: gain 0.5-1kg muscle per month |
| 保持 | Balance is a superpower. Respect. ⚖️ | Maintaining is awesome too! | Maintain mode: stay within ±1kg range |

---

### 📄 第 6 页 - 价值页 A: AI 扫描

| 元素 | 内容 |
|------|------|
| **标题** | Snap & Know in Seconds |
| **副标题** | Our AI instantly analyzes any meal photo for calories, macros, and ingredients. |
| **价值类型** | ai_scan |

**角色状态**: excited (兴奋)

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| Point. Shoot. Know everything. Magic? Nope, just AI. | Taking a photo is all it takes! I'll handle the rest. | 98% accuracy. 0.3s scan time. 500K+ meals logged daily. |

---

### ═══════════════════════════════════════
### Phase 3: 了解你 (第 7-12 页)
### ═══════════════════════════════════════

---

### 📄 第 7 页 - 选择性别 (Gender)

| 元素 | 内容 |
|------|------|
| **标题** | What's your gender? |
| **副标题** | This helps us calculate more accurately |
| **跳过按钮** | ✅ 显示 |
| **即时洞察** | ✅ 显示 |
| **自动跳转** | ✅ 选择后自动 |

**选项**:

| ID | 图标 | 标题 |
|----|------|------|
| male | User | Male |
| female | User | Female |
| other | Users | Other |

**角色状态**: listening (倾听)

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| Quick question for the algorithm... | This helps us understand you better | Gender affects metabolism calculation |

**选择后反馈**:

| 选择 | Witty | Warm | Data |
|------|-------|------|------|
| 男性 | Got it! That affects the math. | Got it! | Male avg BMR: 1600-1800 kcal |
| 女性 | Noted! Adjusting calculations... | Understood! | Female avg BMR: 1200-1400 kcal |
| 其他 | All good! We'll make it work. | No problem! | Using neutral metabolism formula |

---

### 📄 第 8 页 - 输入年龄 (Age)

| 元素 | 内容 |
|------|------|
| **标题** | How old are you? |
| **副标题** | This helps us calculate your basal metabolic rate |
| **数值范围** | 16 - 80 岁 |
| **默认值** | 25 |
| **单位** | years |

**角色状态**: listening (倾听)

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| How many trips around the sun? | How old are you? | Age is used to calculate BMR |

**输入后反馈** (根据年龄动态变化):

| 年龄段 | Witty | Warm | Data |
|--------|-------|------|------|
| < 25 | Youth is on your side! | Youth is your advantage! | Age X: BMR is higher |
| 25-39 | Prime time for change! | Perfect time for change! | Age X: BMR is moderate |
| 40+ | Experience is a superpower! | It's never too late to start! | Age X: BMR needs attention |

---

### 📄 第 9 页 - 身高体重 (Height & Weight)

| 元素 | 内容 |
|------|------|
| **标题** | Your height and weight |
| **副标题** | We need this to calculate your BMI |
| **隐私徽章** | ✅ 显示 |

**身高配置**:
- 范围: 140 - 220 cm
- 默认: 170 cm
- 步进: 1

**体重配置**:
- 范围: 40 - 150 kg
- 默认: 70 kg
- 步进: 0.5

**角色状态**: listening (倾听)

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| Time for the numbers. No judgment here. | Let's get your body measurements | Height & weight for BMI and TDEE |

**输入后反馈**:

| 数据 | Witty | Warm | Data |
|------|-------|------|------|
| 身高 > 180 | Looking up to you already! | Recorded! | Height Xcm: ideal weight X-Xkg |
| 身高 165-180 | Perfect height for greatness! | Recorded! | Height Xcm: ideal weight X-Xkg |
| 身高 < 165 | Good things come in all sizes! | Recorded! | Height Xcm: ideal weight X-Xkg |
| 体重 | Brave move. The scale is just a number. | Thanks for trusting us, let's do this together | Current weight Xkg recorded |

---

### 📄 第 10 页 - 价值页 B: 个性化

| 元素 | 内容 |
|------|------|
| **标题** | Personalized Just for You |
| **副标题** | Smart recommendations based on your goals, preferences, and progress. |
| **社会证明** | ✅ 显示 |
| **价值类型** | personalized |

**角色状态**: explaining (解释)

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| I'm like a nutritionist... but I never sleep. And I'm free! | Every suggestion is tailored to your unique goals. | Personalized plans show 2x higher goal completion rates. |

---

### 📄 第 11 页 - 活动量 (Activity Level)

| 元素 | 内容 |
|------|------|
| **标题** | How active are you? |
| **副标题** | This helps us calculate your daily calorie needs |
| **自动跳转** | ✅ 选择后自动 |

**选项**:

| ID | 图标 | 标题 | 副标题 |
|----|------|------|--------|
| sedentary | Sofa | Not Very Active | Little or no exercise |
| moderate | Walk | Moderately Active | 2-4 days/week |
| active | Flame | Very Active | 5+ days/week |

**角色状态**: listening (倾听)

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| How much do you move? Be honest! 😅 | This helps us personalize your calorie needs. | Activity level affects TDEE calculation by 20-40%. |

**选择后反馈**:

| 选择 | Witty | Warm | Data |
|------|-------|------|------|
| 久坐 | Desk life? We'll account for that. | Desk job? We'll adjust for you | Activity factor: 1.2 (sedentary) |
| 适度 | Active lifestyle detected. Nice! | Your exercise habits are healthy! | Activity factor: 1.55 (moderate) |
| 活跃 | Athlete mode activated! 🔥 | Fitness pro! Amazing! | Activity factor: 1.725 (active) |

---

### 📄 第 12 页 - 目标体重 (Target Weight)

| 元素 | 内容 |
|------|------|
| **标题** | What's your target weight? |
| **副标题** | Set a healthy achievable goal |
| **数值范围** | 40 - 150 kg |
| **默认值** | 65 kg |
| **步进** | 0.5 |
| **即时洞察** | ✅ 显示 |

**角色状态**: encouraging (鼓励)

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| Where do you want to be? | Set a healthy, achievable goal | Target weight determines calorie deficit |

**输入后反馈**:

| Witty | Warm | Data |
|-------|------|------|
| Got it! I'll build your plan around this. | Great goal! We'll get there together. | Target set. Calculating your plan. |

---

### ═══════════════════════════════════════
### Phase 4: 价值交付 (第 13-14 页)
### ═══════════════════════════════════════

---

### 📄 第 13 页 - 加载页 (Loading)

| 元素 | 内容 |
|------|------|
| **标题** | Analyzing your data... |
| **副标题** | (无) |
| **自动跳转** | ✅ 3秒后 |
| **个性化** | ✅ 使用用户数据 |

**角色状态**: thinking (思考)

**加载过程文案** (序列显示):

| 阶段 | Witty | Warm | Data |
|------|-------|------|------|
| 计算中 | Crunching the numbers... This is exciting! | Creating your personalized plan... | Processing data, ~3 seconds |
| 分析中 | Your data is telling a story... | Analyzing your data... | AI model analyzing |
| 生成计划 | Crafting your personalized journey... | Creating your custom plan... | Generating personalized plan |
| 快完成 | Almost there... Good things take time! | Almost done! | 95% complete |
| 完成 | Boom! Your plan is ready! | Done! Your plan is ready! | Plan generation complete |

---

### 📄 第 14 页 - 结果页 (Result)

| 元素 | 内容 |
|------|------|
| **标题** | {{name}}'s Personal Plan |
| **副标题** | Based on your data, we've created this plan for you |
| **个性化** | ✅ 使用用户名字 |
| **损失厌恶** | ✅ 显示对比 |
| **动效** | 交错动画 |

**角色状态**: proud (自豪)

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| You'll fit right in. | Your personalized plan is ready! | Here's your data analysis |

---

### ═══════════════════════════════════════
### Phase 5: 体验启动 (第 15-16 页)
### ═══════════════════════════════════════

---

### 📄 第 15 页 - AI 扫描游戏 (Scan Game)

| 元素 | 内容 |
|------|------|
| **标题** | Try AI Scan |
| **副标题** | Hold to scan the food below, experience AI magic |
| **交互** | 长按扫描食物图片 |

**角色状态**: excited (兴奋)

**扫描完成反馈**:

| Witty | Warm | Data |
|-------|------|------|
| First scan in the books! You're a natural! | First scan success! You're a quick learner! | First AI scan complete, improving accuracy |

---

### 📄 第 16 页 - 价值页 C: 进度追踪

| 元素 | 内容 |
|------|------|
| **标题** | Track your progress |
| **副标题** | Watch your journey unfold with beautiful charts and insights. |
| **价值类型** | progress_tracking |

**角色状态**: proud (自豪)

---

### ═══════════════════════════════════════
### Phase 6: 权限申请 (第 17-18 页)
### ═══════════════════════════════════════

---

### 📄 第 17 页 - 通知权限 (Permission)

| 元素 | 内容 |
|------|------|
| **标题** | Stay on Track |
| **副标题** | Get gentle reminders to log meals and celebrate your wins |
| **跳过按钮** | ✅ 显示 |
| **权限类型** | notification |

**权限好处列表**:

| 图标 | 文案 |
|------|------|
| ⏰ | Meal reminders at your preferred times |
| 🎯 | Weekly progress summaries |
| 💪 | Motivational nudges when you need them |

**角色状态**: encouraging (鼓励)

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| I promise not to spam! Just helpful nudges when you need them. | Gentle reminders to keep you on track. | Users with notifications enabled reach goals 67% faster. |

---

### 📄 第 18 页 - 价值页 D: 隐私安全

| 元素 | 内容 |
|------|------|
| **标题** | Your data stays private |
| **副标题** | Your health data is encrypted and never shared. |
| **价值类型** | privacy |

**角色状态**: explaining (解释)

---

### ═══════════════════════════════════════
### Phase 7: 完成 (第 19-20 页)
### ═══════════════════════════════════════

---

### 📄 第 19 页 - 完成过渡页 (Transition)

| 元素 | 内容 |
|------|------|
| **标题** | You're All Set! |
| **副标题** | Ready to start your health journey with VitaFlow |
| **个性化** | ✅ 使用用户数据 |

**角色状态**: happy (开心)

**角色对话**:

| Witty | Warm | Data |
|-------|------|------|
| You're officially ready to crush it! 🚀 | You're all set! Let's start your journey! | Setup complete. Ready to begin tracking. |

---

### 📄 第 20 页 - 注册账号 (Account)

| 元素 | 内容 |
|------|------|
| **标题** | Create your account |
| **副标题** | Sign in to sync your data across devices |

**角色状态**: encouraging (鼓励)

---

## 🔧 修改文案的方法

### 方法 1: 直接修改代码文件

**主流程文案**: `data/screens-config-production.ts`
- 修改 `title` 和 `subtitle` 字段
- 修改 `options` 数组中的选项文案

**对话反馈文案**: `data/feedback-copy.ts`
- 找到对应的 key（如 `goal_lose_weight`）
- 修改 `witty`、`warm`、`data` 三个版本

### 方法 2: 本地预览

```bash
cd "C:\Users\WIN\Desktop\Cursor Project\pm-tool-v2\frontend"
npm run dev
# 打开 http://localhost:3001/onboarding-demo/mobile
```

### 方法 3: 提交修改

```bash
git add -A
git commit -m "docs: update onboarding copy"
git push
# Vercel 自动部署到 https://vitaflow-onboarding.vercel.app
```

---

## ✅ Review 检查清单

- [ ] 所有英文文案语法正确
- [ ] 文案风格统一（当前用 witty 风格）
- [ ] 个性化变量 `{{name}}` 使用正确
- [ ] 数值单位正确（kg/cm/years）
- [ ] Emoji 使用适度，不过多
- [ ] 所有选项的文案清晰易懂
- [ ] 错误提示友好不吓人
- [ ] 价值主张有吸引力
- [ ] CTA 按钮文案有行动力

---

## 📞 问题反馈

如有文案问题，请直接在此文档标注或联系产品负责人。
