# Memory-Break Orchestrator

A comprehensive evaluation system for testing AI agent performance under memory compression scenarios. The orchestrator automatically tests multiple AI agents (Claude, Gemini, iFlow) against GitHub PRs and evaluates their ability to maintain understanding after memory compression events.

## Features

- **Multi-Agent Testing**: Simultaneously evaluate Claude, Gemini, and iFlow agents
- **Memory Compression Detection**: Automatically detects when agents hit context limits
- **Real-time Monitoring**: Live progress tracking and logging via web dashboard
- **LLM-based Judging**: Uses GPT-4o for intelligent evaluation of agent performance
- **Comprehensive Scoring**: Evaluates across 4 dimensions (AR, TTL, LRU, SF)
- **Immediate Results**: Agents are judged as soon as they complete (no waiting for batch processing)
- **Artifact Management**: Complete transcript and result archival

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Dashboard │    │   API Server    │    │   Worker Pool   │
│   (Frontend)    │◄──►│   (FastAPI)     │◄──►│   (RQ/Redis)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   PostgreSQL    │    │  Agent Runners  │
                       │   (Database)    │    │ Claude/Gemini/  │
                       └─────────────────┘    │     iFlow       │
                                              └─────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.11+ (avoid 3.13 due to asyncpg compatibility)
- PostgreSQL database
- Redis server
- Agent CLIs: iFlow, Claude, Gemini

### Installation

```bash
# 1. Clone and setup environment
git clone <repository>
cd cli-eval-poc/tools
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -e .

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys and database settings

# 4. Setup database
alembic upgrade head

# 5. Start services
# Terminal 1: Redis
redis-server

# Terminal 2: API Server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 3: Worker
python worker.py

# 6. Open dashboard
open http://localhost:8000
```

## Configuration

### Required Environment Variables

#### Database & Redis
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/memory_break_db
REDIS_URL=redis://localhost:6379/0
```

#### API Keys
```bash
# For LLM Judge and Prompt Generation
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# For iFlow Agent (Required)
IFLOW_API_KEY=your_iflow_api_key_here
```

#### Agent Configuration
```bash
# Model Selection
CLAUDE_MODEL=claude-sonnet-4-5-20250929
GEMINI_MODEL=gemini-2.5-pro
IFLOW_MODEL_NAME=qwen3-coder-plus

# Judge Configuration
DEFAULT_JUDGE=llm
JUDGE_MODEL=gpt-4o

# Prompt Generation
PROMPT_MODEL=gpt-4o
PROMPT_TEMPERATURE=1.0
```

### Optional Configuration

#### Performance Tuning
```bash
# Task Processing
TASK_TIMEOUT_SECONDS=7200        # 2 hours max per task
AGENT_SESSION_TIMEOUT=3600       # 1 hour max per agent
MAX_CONTEXT_TOKENS=200000        # Token limit for fair comparison
MAX_TURNS=100                    # Maximum deep-dive iterations

# Compression Detection
COMPRESSION_THRESHOLD_LOW=30     # Threshold for detecting compression
COMPRESSION_JUMP_THRESHOLD=30    # Jump threshold for compression events
```

## Usage

### Web Dashboard

1. **Navigate** to http://localhost:8000
2. **Enter** a GitHub PR URL (e.g., `https://github.com/owner/repo/pull/123`)
3. **Select** agents to test (Claude, Gemini, iFlow)
4. **Configure** evaluation parameters
5. **Start** the evaluation task
6. **Monitor** real-time progress and logs
7. **Download** complete results when finished

### API Usage

```python
import requests

# Create evaluation task
response = requests.post("http://localhost:8000/api/v1/tasks", json={
    "pr_url": "https://github.com/owner/repo/pull/123",
    "agents": ["claude", "gemini", "iflow"],
    "rubric": ["AR", "TTL", "LRU", "SF"],
    "max_files": 10
})

task_id = response.json()["id"]

# Start task
requests.post(f"http://localhost:8000/api/v1/tasks/{task_id}/start")

# Monitor progress
status = requests.get(f"http://localhost:8000/api/v1/tasks/{task_id}")
```

## Evaluation Process

### 1. PR Analysis
- Clones GitHub repository
- Analyzes changed files and diff
- Generates context-aware prompts

### 2. Agent Execution
- **Pre-compression Phase**: Detailed analysis with full context
- **Deep-dive Phase**: Iterative exploration until compression detected
- **Memory-only Phase**: Evaluation using compressed memory only
- **Evaluation Phase**: Structured Q&A assessment

### 3. Immediate Judging
- Each agent is judged as soon as it completes
- Uses LLM judge (GPT-4o) for intelligent evaluation
- Scores across 4 dimensions: AR, TTL, LRU, SF
- Generates detailed rationale and scoring

### 4. Results & Artifacts
- Complete transcripts and logs
- Performance metrics and token usage
- Downloadable ZIP bundles
- Real-time leaderboard updates

## Scoring Dimensions

- **AR (Accurate Retrieval)**: How well can the agent recall specific details?
- **TTL (Test-Time Learning)**: How well can the agent adapt to new scenarios?
- **LRU (Long-Range Understanding)**: How well does the agent understand broader context?
- **SF (Selective Forgetting)**: How well can the agent update/modify understanding?

Each dimension is scored 0.0-1.0, with an overall average determining pass/fail status.

## Development

### Project Structure
```
├── app/
│   ├── agents/          # Agent adapters (Claude, Gemini, iFlow)
│   ├── domain/          # Core entities and models
│   ├── infrastructure/  # Database, queue, external services
│   ├── presentation/    # API routes and middleware
│   └── services/        # Business logic (judge, prompt, PR analysis)
├── workers/             # Background task processors
├── static/              # Web dashboard assets
├── prompts/             # Evaluation prompt templates
└── storage/             # Task artifacts and results
```

### Adding New Agents

1. Create agent adapter in `app/agents/`
2. Implement `AgentAdapter` interface
3. Register in `app/agents/registry.py`
4. Add configuration in `app/config.py`

### Extending Evaluation

1. Modify rubric dimensions in `app/domain/entities.py`
2. Update judge prompts in `app/services/judge_service.py`
3. Enhance evaluation logic in `workers/simple_worker.py`

## Troubleshooting

### Common Issues

**Database Connection Errors**
```bash
# Check PostgreSQL is running
pg_ctl status

# Verify connection string
psql "postgresql://user:password@localhost:5432/memory_break_db"
```

**Redis Connection Errors**
```bash
# Check Redis is running
redis-cli ping

# Should return: PONG
```

**Agent CLI Issues**
```bash
# Verify agent installations
iflow --version
claude --version
gemini --version
```

**API Key Issues**
- Ensure all required API keys are set in `.env`
- Check key permissions and quotas
- Verify model access (GPT-4o, Claude Sonnet, etc.)

### Logs

- **API Server**: Check console output or logs/
- **Worker**: Check worker.log
- **Task Logs**: Available via web dashboard or API
- **Agent Transcripts**: Stored in storage/{task_id}/

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[License information here]