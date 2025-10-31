# Quick Start Guide - Memory-Break Orchestrator with uv

## Prerequisites
- Python 3.9+
- Redis
- uv (Astral's Python package installer)
- Agent CLIs: iFlow, Claude, Gemini

## Setup with uv

```bash
# 1. Create and activate virtual environment (Python 3.11 or 3.12)
uv venv --python 3.11  # Avoid Python 3.13 due to asyncpg compatibility
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install project in development mode
uv pip install -e . --verbose

# 3. Setup configuration
cp .env.example .env
# Edit .env with your settings

# 4. Start Redis (in separate terminal)
redis-server

# 5. Start API server with uvicorn (in separate terminal with venv activated)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 6. Start worker (in separate terminal with venv activated)
python worker.py

# 7. Open web dashboard
open http://localhost:8000
```

## Using the Web Dashboard

1. **Open** http://localhost:8000 in your browser
2. **Paste** any GitHub PR URL (e.g., `https://github.com/owner/repo/pull/123`)
3. **Select** agents to test (iFlow, Claude, Gemini)
4. **Click** "Create Task" then "Start Task" 
5. **Monitor** progress in real-time
6. **Download** ZIP bundle with all results when complete

## Testing Memory-Break with iFlow

Perfect for testing PRs that might break iFlow's memory:
- System automatically clones the GitHub repo
- Extracts changed files and creates context-aware prompts
- Runs iFlow through compression detection (monitors "% context left")
- Switches to memory-only mode when compression detected
- Evaluates performance across AR/TTL/LRU/SF dimensions
- Provides downloadable transcripts and detailed scoring

This makes it extremely easy to test different PRs and analyze how they affect agent memory compression!
