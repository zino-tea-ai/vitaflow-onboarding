# NogicOS

**Your AI Work Partner, living in your computer.**

> "Input your need, get the finished product."

## What is NogicOS?

NogicOS is an AI control center that bridges the internet and your local environment. Unlike traditional AI assistants that only chat, NogicOS **executes** tasks end-to-end:

- Browse the web and extract data
- Analyze information and find patterns
- Generate reports and save files
- Learn from every interaction to get faster

## Core Philosophy

```
Input: "需求" (Your Need)
    ↓
NogicOS: 数据采集 → 整理 → 分析 → 生成
    ↓
Output: "成品" (Finished Product)
```

## Features

- 🎯 **End-to-End Execution**: From task to deliverable, not just answers
- 🧠 **Ask/Plan/Agent Modes**: Choose your interaction style
- ⚡ **Smart Routing**: Instant for learned tasks, full AI for new ones
- 🔗 **CDP + Tools**: Browser control + file system + terminal
- 📚 **Collective Learning**: Every user makes it smarter for everyone
- 🎨 **Glassmorphism UI**: Modern, transparent design

## Architecture

```
┌─────────────────────────────────────────┐
│           Electron Client               │
│  ┌─────────────┐  ┌─────────────┐       │
│  │  User View  │  │  AI Panel   │       │
│  └─────────────┘  └─────────────┘       │
└─────────────────────┬───────────────────┘
                      │ WebSocket + HTTP
┌─────────────────────▼───────────────────┐
│           Python Backend                │
│  ┌────────┐  ┌────────┐  ┌──────────┐  │
│  │ Router │→ │ Agent  │→ │Knowledge │  │
│  └────────┘  └────────┘  └──────────┘  │
└─────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Anthropic API key

### Installation

```bash
# Clone the repository
git clone https://github.com/zino-tea-ai/nogicos.git
cd nogicos

# Install Python dependencies
pip install -r requirements.txt

# Install Electron dependencies
cd client
npm install
cd ..

# Set up API keys
cp api_keys.example.py api_keys.py
# Edit api_keys.py with your Anthropic API key
```

### Running

```bash
# Start the application (from client directory)
cd client
npm start
```

This will:
1. Start the Python backend server (port 8080)
2. Launch the Electron application
3. Connect via WebSocket for real-time updates

### Usage

1. Select mode: **Ask** (Q&A), **Plan** (confirm first), or **Agent** (execute directly)
2. Enter a URL in the address bar
3. Type your task
4. Click **Execute**
5. Watch the AI work and receive your deliverable

## Demo Scenario: YC Analysis

**Try this:** "Analyze YC AI companies and find application best practices"

NogicOS will:
1. 📊 Navigate to YC company directory
2. 🔍 Extract AI company data (founders, funding, tags)
3. 📈 Analyze patterns and trends
4. 📝 Generate `analysis.md` report
5. 💡 Create `recommendations.md` with actionable insights
6. 💾 Save everything to `~/yc_research/`

**Output:**
```
~/yc_research/
├── raw_data.json      # Extracted company data
├── analysis.md        # Pattern analysis report
└── recommendations.md # YC application tips
```

## How It Works

1. **First Time**: AI agent analyzes the page and executes actions (30-60s)
2. **Second Time**: Replays learned trajectory (seconds)
3. **With Skills**: Executes generalized procedure (sub-second)

## Tech Stack

- **Frontend**: Electron + BrowserView
- **Backend**: Python + FastAPI + WebSocket
- **AI**: Claude Opus 4.5 + LangGraph
- **Browser Control**: Chrome DevTools Protocol (CDP)

## License

MIT License
