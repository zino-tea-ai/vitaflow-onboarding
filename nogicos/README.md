# NogicOS

AI Browser that gets smarter with every user.

## Core Value

"The more people use it, the faster it gets for everyone."

## Architecture

```
nogicos/
├── hive/           # AI Agent Core Engine (Hive)
├── knowledge/      # Knowledge Base System
├── browser/        # Browser Control (Playwright)
├── contracts/      # Module Contracts
├── health/         # Health Checks
├── observability/  # Logging & Tracing
└── tests/          # Test Suite
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Set up API keys
cp api_keys.example.py api_keys.py
# Edit api_keys.py with your keys

# Run health check
python -m health.checks

# Run demo
python main.py --task "Search for AI on Hacker News"
```

## Modules

### Hive (Core Engine)
AI decision-making and code generation engine.

### Knowledge
Stores and retrieves operation trajectories for faster execution.

### Browser
Playwright-based browser automation with robust error handling.

## License

MIT License

Based on open source software.

