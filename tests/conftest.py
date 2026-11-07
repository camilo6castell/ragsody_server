"""Pytest configuration.

Sets safe dummy provider roles before test modules import application
code. src.config.settings creates a singleton at import time and requires
LLM_ROL_GENERATE and LLM_ROL_SUPPLEMENT to be in "backend,model" format,
so a clean checkout must not depend on local .env.providers files.
"""

from __future__ import annotations

import os

os.environ.setdefault("LLM_ROL_GENERATE", "ollama,test-model")
os.environ.setdefault("LLM_ROL_SUPPLEMENT", "ollama,test-model")
os.environ.setdefault("WEB_SEARCH_ENABLED", "false")
os.environ.setdefault("LLM_DEBUG_DUMP", "false")
