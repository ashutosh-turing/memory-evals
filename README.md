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
- Docker and Docker Compose (for PostgreSQL and Redis)
- PostgreSQL database (or use Docker)
- Redis server (or use Docker)
- Agent CLIs: iFlow, Claude, Gemini

### Installation

```bash
# 1. Clone and setup environment
git clone <repository>
cd memory-evals
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install --upgrade pip
pip install -e .

# 3. Configure environment
# Create .env file with your API keys and database settings
# See Configuration section below for required variables

# 4. Start PostgreSQL and Redis with Docker
# Start PostgreSQL container
docker run -d --name cli_eval_postgres \
  -e POSTGRES_USER=erashu212 \
  -e POSTGRES_PASSWORD='Enter123_' \
  -e POSTGRES_DB=cli_eval_db \
  -p 5432:5432 \
  postgres:latest

# Start Redis container
docker run -d --name redis \
  -p 6379:6379 \
  redis:latest

# Wait a few seconds for databases to initialize
sleep 5

# 5. Setup database migrations
alembic upgrade head

# 6. Start services (Option A: Using startup script - Recommended)
./scripts/run.sh

# OR start services manually (Option B)
# Terminal 1: API Server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Worker
python worker.py

# 7. Open dashboard
open http://localhost:8000
```

### Quick Start with Docker (Alternative)

If you prefer to use Docker for everything, you can also start PostgreSQL and Redis containers as needed:

```bash
# Stop containers (if already running)
docker stop cli_eval_postgres redis 2>/dev/null || true
docker rm cli_eval_postgres redis 2>/dev/null || true

# Start PostgreSQL
docker run -d --name cli_eval_postgres \
  -e POSTGRES_USER=your_username \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=cli_eval_db \
  -p 5432:5432 \
  postgres:latest

# Start Redis
docker run -d --name redis \
  -p 6379:6379 \
  redis:latest

# Verify containers are running
docker ps
```

## Configuration

### Required Environment Variables

#### Database & Redis
```bash
# Note: DATABASE_URL should use psycopg2 driver for SQLAlchemy
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/cli_eval_db
REDIS_URL=redis://localhost:6379/0

# Example with Docker containers:
# DATABASE_URL=postgresql+psycopg2://erashu212:Enter123_@localhost:5432/cli_eval_db
# REDIS_URL=redis://localhost:6379/0
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
# Check PostgreSQL Docker container is running
docker ps --filter "name=cli_eval_postgres"

# Check container logs if there are issues
docker logs cli_eval_postgres

# Verify connection (if using Docker)
docker exec -it cli_eval_postgres psql -U erashu212 -d cli_eval_db

# Or verify with psql client
psql "postgresql://user:password@localhost:5432/cli_eval_db"

# If container is not running, start it:
docker start cli_eval_postgres

# If container doesn't exist, create it:
docker run -d --name cli_eval_postgres \
  -e POSTGRES_USER=erashu212 \
  -e POSTGRES_PASSWORD='Enter123_' \
  -e POSTGRES_DB=cli_eval_db \
  -p 5432:5432 \
  postgres:latest
```

**Redis Connection Errors**
```bash
# Check Redis Docker container is running
docker ps --filter "name=redis"

# Check container logs if there are issues
docker logs redis

# Verify Redis is responding
redis-cli ping
# Should return: PONG

# If container is not running, start it:
docker start redis

# If container doesn't exist, create it:
docker run -d --name redis -p 6379:6379 redis:latest
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

- **API Server**: Check console output or `logs/api.log`
- **Worker**: Check `logs/worker.log` or console output
- **Task Logs**: Available via web dashboard or API
- **Agent Transcripts**: Stored in `storage/{task_id}/`
- **Docker Containers**:
  ```bash
  docker logs cli_eval_postgres  # PostgreSQL logs
  docker logs redis               # Redis logs
  ```

### Service Management

**Using the startup script:**
```bash
# Start all services
./scripts/run.sh

# Stop all services
./scripts/stop.sh
```

**Manual service management:**
```bash
# Start PostgreSQL
docker start cli_eval_postgres

# Start Redis
docker start redis

# Stop PostgreSQL
docker stop cli_eval_postgres

# Stop Redis
docker stop redis

# Remove containers (⚠️ This will delete data)
docker rm -f cli_eval_postgres redis
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[License information here]
