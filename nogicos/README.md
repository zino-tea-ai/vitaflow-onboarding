# NogicOS

**Your AI Work Partner, living in your computer.**

> "Cursor for Everyone" - The AI work partner that lives in your computer, not just your browser.

## What is NogicOS?

NogicOS is an AI control center that bridges the internet and your local environment. Unlike traditional AI assistants that only chat, NogicOS **executes** tasks end-to-end:

- Browse the web and extract data
- Organize files and manage your desktop
- Execute shell commands
- Intelligent decision-making with ReAct Agent

## Architecture (V2)

```
+-------------------------------------------------------------+
|                    Electron Client                           |
|  +----------------------+  +------------------------------+  |
|  |   Glass UI Panel     |  |     BrowserView / Tools      |  |
|  |   - Chat Interface   |  |     - Web Preview            |  |
|  |   - Tool Cards       |  |     - File Operations        |  |
|  |   - Real-time Stream |  |     - Shell Commands         |  |
|  +----------------------+  +------------------------------+  |
+--------------------------------+----------------------------+
                                 | WebSocket (8765) + HTTP (8080)
+--------------------------------v----------------------------+
|                    Python Backend                            |
|  +----------------------------------------------------------+
|  |                   ReAct Agent                             |
|  |   Think -> Act -> Observe -> Think -> Act -> ...         |
|  +----------------------------------------------------------+
|  +------------+  +------------+  +--------------------+      |
|  |   Tools    |  |  WebSocket |  |   Observability    |      |
|  | - Browser  |  |  - Stream  |  |   - Logging        |      |
|  | - Local    |  |  - Status  |  |   - Health Check   |      |
|  +------------+  +------------+  +--------------------+      |
+-------------------------------------------------------------+
```

## Engine Structure

```
engine/
├── agent/
│   └── react_agent.py    # Pure ReAct Agent (core)
├── tools/
│   ├── base.py           # Tool Registry & Definitions
│   ├── browser.py        # Browser automation tools
│   └── local.py          # File system & shell tools
├── server/
│   └── websocket.py      # Real-time status broadcasting
├── middleware/
│   ├── filesystem.py     # File operation safety
│   └── todo.py           # Task management
├── health/
│   └── __init__.py       # Health check system
└── observability/
    └── __init__.py       # Logging system
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server status |
| `/stats` | GET | Execution statistics |
| `/v2/execute` | POST | **Execute task with ReAct Agent** |
| `/v2/tools` | GET | List available tools |
| `/health` | GET | Health check |
| `/read_file` | GET | Read file content |

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Anthropic API key

### Installation

```bash
# Clone the repository
git clone https://github.com/example/nogicos.git
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
# Option 1: Start from client (auto-starts backend)
cd client
npm start

# Option 2: Start backend separately
python hive_server.py
# Then in another terminal:
cd client
npm start
```

## Available Tools

### Browser Tools
- `navigate` - Navigate to URL
- `click` - Click element
- `type` - Type text
- `scroll` - Scroll page
- `screenshot` - Take screenshot
- `get_page_content` - Extract page content

### Local Tools
- `read_file` - Read file content
- `write_file` - Write to file
- `list_directory` - List directory contents
- `create_directory` - Create directory
- `move_file` - Move/rename file
- `copy_file` - Copy file
- `delete_file` - Delete file
- `shell_execute` - Run shell command
- `glob_search` - Search files by pattern
- `grep_search` - Search file contents

## Example Tasks

```
"Organize my desktop"
-> Agent lists desktop, categorizes files, creates folders, moves files

"Save this webpage content to a file"
-> Agent navigates, extracts content, writes to file

"Find all files containing TODO in this project"
-> Agent uses grep_search to find matches
```

## Tech Stack

- **Frontend**: Electron + Glassmorphism UI
- **Backend**: Python + FastAPI + WebSocket
- **AI**: Claude 3.5 Sonnet + Pure ReAct Loop
- **Design**: Vision Pro inspired floating panels

## License

MIT License
