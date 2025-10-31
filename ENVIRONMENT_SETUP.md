# Environment Setup Guide

## Required Environment Variables

Create a `.env` file in the project root with the following variables:

### Database Configuration
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/memory_break_db
REDIS_URL=redis://localhost:6379/0
```

### API Server
```bash
HOST=127.0.0.1
PORT=8000
DEBUG=False
```

### iFlow Configuration (REQUIRED for iFlow agent)

The iFlow CLI requires authentication to connect to the iFlow service. You must provide your API key:

```bash
IFLOW_API_KEY=sk-your-api-key-here
IFLOW_BASE_URL=https://apis.iflow.cn/v1
IFLOW_MODEL_NAME=qwen3-coder-plus
```

### Claude Configuration

```bash
CLAUDE_MODEL=claude-3-5-sonnet-20241022
```

### Gemini Configuration

```bash
GEMINI_MODEL=gemini-1.5-pro
```

**How to get your iFlow API key:**
1. Register for an iFlow account at https://cloud.iflow.cn
2. Go to your profile settings: https://cloud.iflow.cn/user/settings
3. Click "Reset" in the API key dialog to generate a new key
4. Copy the key and paste it as `IFLOW_API_KEY` in your `.env` file

### API Keys for LLM Judge
```bash
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
GOOGLE_API_KEY=your-google-api-key
```

### Task Processing Timeouts
```bash
TASK_TIMEOUT_SECONDS=7200  # 2 hours - increased for memory compression detection
AGENT_SESSION_TIMEOUT=3600  # 1 hour - increased for full compression cycle
```

### Agent Token Limits (for fair comparison)
```bash
MAX_CONTEXT_TOKENS=200000  # Token limit for all agents (fair comparison)
```

### Other Configuration
```bash
RUN_ROOT=storage
MAX_FILES_PER_TASK=50
COMPRESSION_THRESHOLD_LOW=30
COMPRESSION_JUMP_THRESHOLD=30
DEFAULT_JUDGE=heuristic
JUDGE_MODEL=gpt-4o
USE_GPT_PROMPTS=True
PROMPT_MODEL=gpt-4o
PROMPT_TEMPERATURE=1.0
```

## How Authentication Works

When the iFlow agent container starts:
1. The `IFLOW_API_KEY` is passed as an environment variable to the container
2. The `agent_runner.py` script creates `~/.iflow/settings.json` inside the container
3. This mimics the `/auth` command you would run locally
4. The iFlow CLI then authenticates automatically when it starts

## Testing the Setup

After setting up your `.env` file:

1. Rebuild the Docker images:
```bash
docker build -f dockerfiles/agent-base.Dockerfile -t agent-base:latest .
docker build -f dockerfiles/iflow-agent.Dockerfile -t iflow-agent:latest .
```

2. Run a test task through the API to verify iFlow connects properly

3. Check the container logs at `storage/{task_id}/agents/iflow/container_stdout.log`
   - You should see "100% context left" instead of "Disconnected"
   - The agent should successfully initialize and accept prompts

