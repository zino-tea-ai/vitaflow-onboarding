# -*- coding: utf-8 -*-
"""Debug encoding issues - trace agent import"""
import os
import sys

# Force UTF-8 on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, "SkillWeaver")

print("Tracing agent.py import...")

# Try each import from agent.py
imports = [
    "import asyncio",
    "import os",
    "import traceback",
    "from pathlib import Path",
    "from typing import Optional",
    "from aioconsole import aprint",
    "from skillweaver.environment import Browser, State",
    "from skillweaver.lm import LM",
    "from skillweaver.trajectory import Step",
    "from skillweaver.templates import *",
]

for imp in imports:
    try:
        exec(imp)
        print(f"[OK] {imp}")
    except Exception as e:
        print(f"[FAIL] {imp}: {e}")
        break
