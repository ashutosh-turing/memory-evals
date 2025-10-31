# Memory-Break Orchestrator

A production-ready system for evaluating AI agent memory compression capabilities following the VIBE (View, Isolation, Background, Evaluation) architecture. Test how well agents like iFlow, Claude, and Gemini handle memory breaks during long conversations.

## 🎯 Overview

The Memory-Break Orchestrator allows you to:
- **Input GitHub PR URLs** and automatically analyze changed files
- **Run memory-break tests** on iFlow, Claude, and Gemini agents
- **Detect compression events** using different strategies per agent
- **Evaluate performance** across AR/TTL/LRU/SF dimensions
- **Download comprehensive results** including transcripts and scores

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.11-3.12** (avoid 3.13 due to asyncpg compatibility)
- **Redis** (for task queue)
- **PostgreSQL** (optional, SQLite works for development)
- **Agent CLIs**: Install the agents you want to test

#### Agent CLI Installation

**iFlow** (Required - working out of the box):
```bash
# iFlow should already be available if you're testing memory-break scenarios
iflow --version  # Verify installation
```

**Claude CLI** (Optional):
```bash
# Install Anthropic's Claude CLI
pip install anthropic-cli
# OR follow official installation: https://github.com/anthropics/anthropic-cli
claude --version  # Verify installation
```

**Gemini CLI** (Optional):
```bash
# Install Google's Gemini CLI via gcloud
gcloud components install alpha
gcloud alpha ai models list  # Verify access
# OR install standalone Gemini CLI if available
```

**Note**: You can run the system with just iFlow if other agents aren't needed. The system will automatically detect which agents are available.

### 2. Installation

```bash
# Clone the repository
git clone <repository-url>
cd memory-break-orchestrator

# Create and activate virtual environment with uv (Python 3.11 or 3.12)
uv venv --python 3.11  # or 3.12, avoid 3.13 due to asyncpg compatibility
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies with uv from pyproject.toml
uv pip install -e . --verbose

# Copy environment configuration
cp .env.example .env
# Edit .env with your settings
```

### 3. Database Setup

#### For Development (SQLite)
```bash
# Use SQLite (no additional setup needed)
DATABASE_URL=sqlite:///./memory_break.db
```

#### For Production (PostgreSQL)
```bash
# 1. Install and start PostgreSQL
brew install postgresql  # macOS
# OR: sudo apt-get install postgresql postgresql-contrib  # Ubuntu

# 2. Create database and user
sudo -u postgres psql
CREATE DATABASE cli_eval_db;
CREATE USER your_username WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE cli_eval_db TO your_username;
\q

# 3. Update .env with your PostgreSQL connection
DATABASE_URL=postgresql+psycopg2://your_username:your_password@localhost:5432/cli_eval_db
```

### 4. Configuration

Edit `.env` file:

```bash
# Database - Use SQLite for development, PostgreSQL for production
DATABASE_URL=postgresql+psycopg2://your_username:your_password@localhost:5432/cli_eval_db
# OR for development: DATABASE_URL=sqlite:///./memory_break.db

# Redis
REDIS_URL=redis://localhost:6379/0

# Agent binaries (ensure these are in your PATH)
IFLOW_BIN=iflow
CLAUDE_BIN=claude
GEMINI_BIN=gemini

# Optional: API keys for LLM judge
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

### 5. Database Migration

**Important**: Run database migrations to create the proper schema:

```bash
# Initialize Alembic (first time only)
source .venv/bin/activate  # Activate your virtual environment
alembic init alembic

# Generate migration for current models
alembic revision --autogenerate -m "Initial migration"

# Apply migrations to database
alembic upgrade head

# Verify database schema is created
psql -d cli_eval_db -c "\dt"  # PostgreSQL
# OR check SQLite: sqlite3 memory_break.db ".tables"
```

### 6. Start the System

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start the API server with uvicorn
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 3: Start the worker process (if not auto-started)
python worker.py

# Access the web dashboard
open http://localhost:8000
```

## 🌐 Web Dashboard

The web dashboard provides an intuitive interface for memory-break testing:

### Features
- **GitHub PR Input**: Paste any GitHub PR URL to analyze
- **Agent Selection**: Choose iFlow, Claude, Gemini, or all three
- **Real-time Progress**: Monitor task execution with live updates
- **Result Downloads**: Get ZIP bundles with all artifacts
- **System Health**: Monitor agent availability and system status

### Usage Flow
1. Open http://localhost:8000
2. Paste a GitHub PR URL (e.g., `https://github.com/owner/repo/pull/123`)
3. Select which agents to test
4. Click "Create Task" then "Start Task"
5. Monitor progress in real-time
6. Download results when complete

## 📡 API Endpoints

### Task Management
```bash
# Create new task
POST /api/v1/tasks
{
  "pr_url": "https://github.com/owner/repo/pull/123",
  "agents": ["iflow", "claude", "gemini"],
  "max_files": 50
}

# Start task execution
POST /api/v1/tasks/{task_id}/run

# Get task status
GET /api/v1/tasks/{task_id}

# Get agent results
GET /api/v1/tasks/{task_id}/agents
```

### Artifact Downloads
```bash
# Download complete results bundle
GET /api/v1/artifacts/{task_id}/bundle

# Download specific agent artifact
GET /api/v1/artifacts/{task_id}/{agent}/{artifact_name}

# List all artifacts
GET /api/v1/artifacts/{task_id}/list
```

### Health Monitoring
```bash
# Basic health check
GET /health/

# Detailed system status
GET /health/detailed

# System metrics
GET /health/metrics
```

## 🔧 Architecture

### VIBE Components

**V - View (API Interface)**
- FastAPI REST API with OpenAPI documentation
- Vue.js single-page dashboard
- Secure file downloads with validation

**I - Isolation (Security & Boundaries)**
- Agent processes isolated with pexpect
- Task-specific filesystem sandboxes
- Input validation and sanitization
- Environment-based secret management

**B - Background (Reliable Processing)**
- Redis queue with RQ workers
- Comprehensive error handling and retries
- Artifact persistence and management
- Progress tracking and health monitoring

**E - Evaluation (Scoring Framework)**
- Heuristic judge with keyword analysis
- LLM judge with OpenAI/Anthropic integration
- AR/TTL/LRU/SF rubric scoring
- Pre/post compression A/B comparison

### System Flow

1. **PR Analysis**: Clone GitHub repo, extract changed files
2. **Prompt Generation**: Create context-aware prompts with file contents
3. **Agent Execution**: Run agents through compression phases
4. **Compression Detection**: Monitor context % (iFlow) or step-based (others)
5. **Memory-Only Mode**: Switch agents to memory-only evaluation
6. **Scoring**: Compare pre/post compression performance
7. **Artifact Storage**: Save transcripts, exports, and scores

## 🤖 Agent Integration

### iFlow Agent
- **CLI Integration**: `pexpect` with iFlow binary
- **Compression Detection**: Context percentage monitoring via `/stats`
- **Artifacts**: Transcript + JSON export via `/export`
- **Phases**: Init → Pre-compression → Deep-dive → Memory-only → Evaluation

### Claude Agent  
- **CLI Integration**: `claude chat` command
- **Compression Detection**: Step-based (after N deep-dive iterations)
- **Artifacts**: Session transcript
- **Phases**: Pre-compression → Deep-dive → Memory-only → Evaluation

### Gemini Agent
- **CLI Integration**: `gemini chat` command  
- **Compression Detection**: Step-based (configurable threshold)
- **Artifacts**: Session transcript
- **Phases**: Pre-compression → Deep-dive → Memory-only → Evaluation

## 📊 Evaluation Rubric

### AR - Accurate Retrieval
How well can the agent recall specific details and facts after compression?

### TTL - Test-Time Learning  
How well can the agent adapt and apply knowledge to new scenarios?

### LRU - Long-Range Understanding
How well can the agent understand connections and broader context?

### SF - Selective Forgetting
How well can the agent update/modify its understanding when needed?

## 🛠️ Development

### Project Structure
```
memory-break-orchestrator/
├── app/                        # Main application
│   ├── domain/                 # Business entities
│   ├── infrastructure/         # Database, queue, external
│   ├── agents/                 # Agent plugin system
│   ├── services/               # Business logic
│   ├── presentation/           # API routes, middleware
│   └── main.py                 # FastAPI application
├── workers/                    # Background tasks
├── static/                     # Web dashboard
├── prompts/                    # Jinja2 templates
├── .env                        # Environment config
└── worker.py                   # Worker startup
```

### Adding New Agents

1. **Create Agent Class**: Extend `AgentAdapter` in `app/agents/`
2. **Implement Methods**: `run_session()`, `validate_installation()`
3. **Add Metadata**: Define capabilities and requirements
4. **Register Agent**: Add to agent registry auto-discovery

### Database Schema

- **Tasks**: PR info, status, configuration
- **AgentRuns**: Individual agent execution records  
- **Artifacts**: File storage references
- **Scores**: Evaluation results and rationale

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app

# Integration tests
pytest tests/integration/

# Load testing
pytest tests/load/
```

## 📈 Monitoring

### Health Checks
- Database connectivity
- Redis queue status
- Agent binary availability
- System resource usage

### Logging
- Structured JSON logs
- Request/response tracing
- Error tracking with context
- Performance metrics

### Metrics
- Task completion rates
- Agent success/failure rates
- Processing times
- Queue depths

## 🔐 Security

### Input Validation
- GitHub PR URL format validation
- File path traversal prevention
- Maximum file size limits
- Agent CLI input sanitization

### Process Isolation
- Separate worker processes
- Task-specific directories
- Limited file system access
- Network access controls

### Authentication
- API key support for LLM judges
- Rate limiting per IP
- CORS configuration
- Security headers

## 🚨 Troubleshooting

### Common Issues

**"Agent not found" errors**
- Ensure agent CLIs are installed and in PATH
- Check binary paths in `.env` configuration
- Verify agent installation with `iflow --version` etc.

**Task stuck in "running" status**
- Check worker process is running
- Monitor Redis queue: `redis-cli monitor`
- Check worker logs for errors
- Restart worker if needed

**Database connection errors**
- Verify PostgreSQL is running (if using)
- Check DATABASE_URL format
- Ensure database exists and is accessible

**Memory/disk issues**
- Monitor RUN_ROOT directory size
- Clean up old task directories
- Adjust MAX_FILES_PER_TASK setting

### Debug Mode

Enable debug logging:
```bash
DEBUG=true python -m app.main
```

Check system health:
```bash
curl http://localhost:8000/health/detailed
```

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit pull request

## 📞 Support

For issues and questions:
- Create GitHub issues for bugs
- Use discussions for questions
- Check health endpoint for system status
