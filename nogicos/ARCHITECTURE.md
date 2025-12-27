# NogicOS Architecture

## Overview

NogicOS is an AI browser with collective learning. Core thesis: "The more people use it, the faster it gets for everyone."

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron Client                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Webview   │  │  AI Panel   │  │  Status Bar │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└───────────────────────────┬─────────────────────────────────┘
                            │ WebSocket + HTTP
┌───────────────────────────▼─────────────────────────────────┐
│                    Python Backend                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   HiveEngine                         │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │    │
│  │  │  Router  │─▶│  Agent   │─▶│ Knowledge Store  │   │    │
│  │  └──────────┘  └──────────┘  └──────────────────┘   │    │
│  └─────────────────────────────────────────────────────┘    │
│                            │                                 │
│  ┌─────────────────────────▼─────────────────────────────┐  │
│  │              Browser Control (CDP)                     │  │
│  │  Navigation │ Click │ Type │ Screenshot │ A11y Tree   │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Smart Router
Routes tasks to the optimal execution path:
- **Skill Path**: Executes learned skills (sub-second)
- **Fast Path**: Replays cached trajectories (seconds)
- **Normal Path**: Full AI agent execution (30-60s)

### 2. Hive Agent (LangGraph)
State machine-based AI agent:
- `observe` → Capture page state (screenshot + accessibility tree)
- `think` → LLM reasoning and action planning
- `act` → Execute browser actions via CDP
- `terminate` → Return result

### 3. Knowledge Store
Stores and retrieves operation knowledge:
- Trajectories: Step-by-step action recordings
- Skills: Generalized reusable procedures

### 4. CDP Bridge
Chrome DevTools Protocol integration for browser control:
- Direct control of Electron BrowserView
- No external browser dependency
- Real-time action execution

## Data Flow

```
User Task → Router → [Skill/Fast/Normal Path] → Result
                           │
                           ▼
                    Knowledge Store
                    (Learning Loop)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/execute` | POST | Execute AI task |
| `/stats` | GET | Knowledge base statistics |
| `/health` | GET | Health check |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_MODEL` | claude-opus-4-5 | LLM model |
| `HTTP_PORT` | 8080 | API server port |
| `WS_PORT` | 8765 | WebSocket port |
