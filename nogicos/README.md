# NogicOS

> **The AI that works where you work**
> 
> Browser. Files. Desktop. One AI, complete context. Gets faster every time.

---

## What is NogicOS?

NogicOS is the first AI that works across your browser, files, and desktop as one unified workspace.

**The Problem:**
- ChatGPT only sees what you paste
- Claude only sees what you upload
- Cursor only sees your code
- Browser agents only see one webpage

**Our Solution:**
NogicOS sees your complete work environment—and takes action directly in it.

---

## Key Features

### 🌐 Unified Workspace
- Browse the web and extract data
- Read and write local files
- Understand desktop state
- Execute shell commands

### 🚀 Gets Faster Every Time
```
First time:  Normal Path (30-60s) → Full AI reasoning
Second time: Fast Path (1-5s)     → Replay optimized trajectory
After that:  Skill Path (<1s)     → Instant execution
```

### 🤝 Collective Learning
- Knowledge Store captures task trajectories
- More users = richer skill library = faster for everyone

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron Client                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Chat UI    │  │  AI Panel   │  │  Status Bar │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└───────────────────────────┬─────────────────────────────────┘
                            │ WebSocket + HTTP
┌───────────────────────────▼─────────────────────────────────┐
│                    Python Backend                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              ReAct Agent + Smart Router              │    │
│  │       Think → Act → Observe → Learn → Repeat        │    │
│  └─────────────────────────────────────────────────────┘    │
│                            │                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │Browser Tools │  │ Local Tools  │  │Desktop Tools │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Anthropic API key

### Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Electron dependencies
cd client && npm install && cd ..

# Set up API keys
cp api_keys.example.py api_keys.py
# Edit api_keys.py with your Anthropic API key
```

### Running

```bash
# Start backend
python hive_server.py

# In another terminal, start frontend
cd nogicos-ui && npm run dev
```

---

## Available Tools

### Browser Tools
| Tool | Description |
|------|-------------|
| `browser_navigate` | Navigate to URL |
| `browser_click` | Click element |
| `browser_type` | Type text |
| `browser_scroll` | Scroll page |
| `browser_screenshot` | Take screenshot |
| `browser_extract` | Extract page content |

### Local Tools
| Tool | Description |
|------|-------------|
| `read_file` | Read file content |
| `write_file` | Write to file |
| `list_directory` | List directory |
| `create_directory` | Create folder |
| `move_file` | Move/rename file |
| `shell_execute` | Run shell command |
| `glob_search` | Search by pattern |
| `grep_search` | Search contents |

---

## Example Tasks

```
"Analyze this competitor's website and save key features to Excel"
→ Agent opens website → extracts data → creates Excel file

"Organize my desktop by file type"
→ Agent lists files → categorizes → creates folders → moves files

"Find all TODO comments in this project"
→ Agent searches files → aggregates results → generates report
```

---

## Project Structure

```
nogicos/
├── hive_server.py           # Backend entry point
├── engine/
│   ├── agent/               # ReAct Agent + Planner
│   ├── tools/               # Browser/Local/Desktop tools
│   ├── knowledge/           # Knowledge Store
│   └── server/              # WebSocket service
├── client/                  # Electron client
├── nogicos-ui/              # React frontend
├── PRODUCT_SPEC.md          # Product specification
├── ARCHITECTURE.md          # Technical architecture
├── PITCH_CONTEXT.md         # Team pitch context
└── CHANGELOG.md             # Version history
```

---

## Documentation

- [PRODUCT_SPEC.md](./PRODUCT_SPEC.md) - Product definition and standards
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Technical architecture details
- [PITCH_CONTEXT.md](./PITCH_CONTEXT.md) - Pitch and collaboration guide
- [CHANGELOG.md](./CHANGELOG.md) - Version history

---

## Tech Stack

- **Frontend**: Electron + React + Tailwind
- **Backend**: Python + FastAPI + WebSocket
- **AI**: Claude 3.5 Sonnet + ReAct Loop
- **Browser**: Playwright
- **Design**: Vision Pro inspired glassmorphism

---

## License

MIT License

---

## Team

Building the AI work partner for everyone.
