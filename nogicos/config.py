# -*- coding: utf-8 -*-
"""
NogicOS Configuration
"""

import os

# Default LLM Model
DEFAULT_MODEL = "claude-opus-4-5-20251101"

# Browser Settings
BROWSER_HEADLESS = False
BROWSER_SLOW_MO = 100
BROWSER_WIDTH = 1280
BROWSER_HEIGHT = 720
BROWSER_TIMEOUT = 15000
BROWSER_NAVIGATION_TIMEOUT = 30000

# Knowledge Base Settings
KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(__file__), "knowledge", "data")
KNOWLEDGE_MATCH_THRESHOLD = 0.8

# Logging
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_LEVEL = "INFO"

# Ensure directories exist
os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

