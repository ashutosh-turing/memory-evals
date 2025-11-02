# Memory-Break Orchestrator

A production-grade evaluation system for testing AI agent performance under memory compression scenarios. The orchestrator automatically tests multiple AI agents (Claude, Gemini, iFlow) against GitHub PRs and evaluates their ability to maintain understanding after memory compression events.

## 🚀 Key Features

### Core Capabilities
- **Multi-Agent Testing**: Simultaneously evaluate Claude, Gemini, and iFlow agents
- **Memory Compression Detection**: Automatically detects when agents hit context limits
- **Real-time Monitoring**: Live progress tracking and logging via modern React dashboard
- **LLM-based Judging**: Uses GPT-4o for intelligent evaluation of agent performance
- **Comprehensive Scoring**: Evaluates across 4 dimensions (AR, TTL, LRU, SF)
- **Immediate Results**: Agents are judged as soon as they complete
- **Artifact Management**: Complete transcript and result archival

### Production Features
- **SSO Authentication**: Integrated with APAC Atlas Guard Service
- **Multi-Tenancy**: Organization, team, and project-level isolation
- **Scalable Architecture**: Cloud Tasks + Pub/Sub for 1000+ RPS
- **Modern UI**: React + Vite + Tailwind CSS with dark mode
- **API Versioning**: RESTful API with `/api/v1/` prefix
- **Real-time Updates**: Server-Sent Events (SSE) for live logs

## 🏗️ Architecture

### High-Level Overview
```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   React UI       │───▶│  SSO Gateway     │───▶│   FastAPI        │
│  (Vite + React)  │    │  (Auth Guard)    │    │   (Backend)      │
└──────────────────┘    └──────────────────┘    └──────────────────┘
                                                          │
                                                          ▼
                        ┌─────────────────────────────────────────┐
                        │         Cloud Tasks + Pub/Sub           │
                        │  (Async Task Processing - 1000+ RPS)    │
                        └─────────────────────────────────────────┘
                                          │
                                          ▼
                        ┌─────────────────────────────────────────┐
                        │      Workers (Auto-scaling)             │
                        │   Pull from Pub/Sub → Process Tasks     │
                        └─────────────────────────────────────────┘
                                          │
                        ┌─────────────────┴─────────────────┐
                        ▼                                   ▼
                ┌──────────────┐                  ┌──────────────┐
                │  PostgreSQL  │                  │   Storage    │
                │  (Database)  │                  │  (Artifacts) │
                └──────────────┘                  └──────────────┘
```

### Request Flow (< 1s Response Time)
```
POST /api/v1/tasks
    ↓ (< 100ms)
Create task in DB (status: QUEUED)
    ↓
Enqueue to Cloud Tasks
    ↓
Return 202 Accepted
    ↓
Cloud Task calls /internal/tasks/{id}/process
    ↓
Publish to Pub/Sub
    ↓
Workers pull and process (5-30 min)
    ↓
Real-time updates via SSE
```

## Project Structure

```
tools/
├── backend/          # Backend API and worker services
│   ├── app/         # FastAPI application
│   ├── alembic/     # Database migrations
│   ├── workers/     # Background task workers
│   ├── scripts/     # Deployment scripts
│   └── storage/     # Task artifacts and data
├── ui/              # React + Vite frontend
│   └── src/         # UI source code
└── docs/            # Documentation
```

## Quick Start

### Prerequisites
- Python 3.11+ (avoid 3.13 due to asyncpg compatibility)
- Node.js 18+ and pnpm (for UI)
- PostgreSQL database
- Redis server (optional)
- Agent CLIs: iFlow, Claude, Gemini

### Backend Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -e .

# 4. Configure environment
cp .env.example .env
# Edit .env with your configuration

# 5. Setup database
alembic upgrade head

# 6. Start services (API + Worker)
./scripts/run.sh
```

### UI Setup

```bash
# 1. Navigate to UI directory
cd ui

# 2. Install dependencies
pnpm install

# 3. Configure environment
cp .env.example .env.local
# Edit .env.local with your SSO configuration

# 4. Start development server
pnpm dev
```

### Access the Application

- **UI**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs
- **SSO Gateway** (if running locally): http://localhost:8000

## 📱 UI Features

### Pages
- **Dashboard**: View all tasks with stats, search, and filtering
- **Task Detail**: Real-time logs, leaderboard, and agent progress
- **Leaderboards**: Global agent performance rankings
- **Settings**: User profile and preferences
- **Login**: SSO authentication via APAC Atlas Guard

### Features
- **Dark Mode**: Toggle between light and dark themes
- **Real-time Updates**: Live task status and log streaming
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Multi-tenant**: Filter tasks by user, team, or organization
- **Search & Filter**: Find tasks quickly with advanced filtering

## Configuration

### Backend Configuration (`backend/env.template`)

Key configuration options:

```bash
# Database
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/cli_eval_db

# SSO (APAC Atlas Guard)
SSO_ENABLED=true
SSO_SERVICE_URL=https://apac-atlas-guard-svc.run.app/v1

# Google Cloud (uses ADC - Application Default Credentials)
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
QUEUE_ENABLED=true
CLOUD_TASKS_QUEUE=pr-evaluation-queue
PUBSUB_TOPIC=pr-evaluation-tasks
PUBSUB_SUBSCRIPTION=pr-evaluation-tasks-sub

# Agent API Keys
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
GITHUB_TOKEN=ghp_...
```

### UI Configuration (`ui/.env.example`)

```bash
# SSO Configuration
VITE_SSO_SERVICE_URL=http://localhost:8000/v1
VITE_TEAM_ID=your-team-id
VITE_REDIRECT_URI=http://localhost:3000/auth/callback

# Service Configuration
VITE_SERVICE_PREFIX=cli-eval
```

For detailed configuration options, refer to:
- Backend: `backend/env.template` or `backend/README.md`
- UI: `ui/.env.example`

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

## 🚀 Deployment

### Google Cloud Run (Recommended)

#### Prerequisites
1. Google Cloud Project with billing enabled
2. Cloud Tasks, Pub/Sub, and Cloud Run APIs enabled
3. Service account with appropriate permissions

#### Deploy Backend
```bash
cd backend

# Build and deploy
gcloud run deploy memory-break-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="SSO_ENABLED=true,QUEUE_ENABLED=true"
```

#### Deploy Worker
```bash
cd backend

# Build worker image
docker build -f Dockerfile.worker -t gcr.io/PROJECT_ID/memory-break-worker .

# Push to GCR
docker push gcr.io/PROJECT_ID/memory-break-worker

# Deploy to Cloud Run Jobs or GKE
gcloud run jobs create memory-break-worker \
  --image gcr.io/PROJECT_ID/memory-break-worker \
  --region us-central1
```

#### Deploy UI
```bash
cd ui

# Build production bundle
pnpm build

# Deploy to Cloud Storage + Cloud CDN or Cloud Run
gcloud run deploy memory-break-ui \
  --source . \
  --region us-central1
```

#### Setup Cloud Tasks & Pub/Sub
```bash
# Create Cloud Tasks queue
gcloud tasks queues create pr-evaluation-queue \
  --location=us-central1

# Create Pub/Sub topic
gcloud pubsub topics create pr-evaluation-tasks

# Create Pub/Sub subscription
gcloud pubsub subscriptions create pr-evaluation-tasks-sub \
  --topic=pr-evaluation-tasks \
  --ack-deadline=600
```

### Local Development with Cloud Services

```bash
# Authenticate with Google Cloud
gcloud auth application-default login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Run backend (will use ADC)
cd backend
./scripts/run.sh

# Run worker (will use ADC)
python workers/cloud_worker.py

# Run UI
cd ui
pnpm dev
```

## 📊 Monitoring & Observability

### Logs
- **Backend API**: Cloud Logging or `backend/logs/api.log`
- **Worker**: Cloud Logging or `backend/logs/cloud_worker.log`
- **Task Logs**: Available via API `/api/v1/logs/{task_id}/stream`

### Metrics
- Task creation rate (RPS)
- Task completion time
- Agent success/failure rates
- Queue depth and latency

### Health Checks
- **Backend**: `GET /health`
- **Internal**: `GET /internal/health`

## 🐛 Troubleshooting

### SSO Authentication Issues
```bash
# Check SSO service is accessible
curl https://apac-atlas-guard-svc.run.app/v1/health

# Verify headers are being sent
# Check backend logs for "RAW HEADERS DICT"
```

### Cloud Tasks Not Working
```bash
# Verify queue exists
gcloud tasks queues describe pr-evaluation-queue --location=us-central1

# Check service URL is correct
echo $CLOUD_TASKS_SERVICE_URL

# Verify /internal endpoint is accessible (not behind SSO)
curl http://localhost:8001/internal/health
```

### Pub/Sub Issues
```bash
# Check topic exists
gcloud pubsub topics describe pr-evaluation-tasks

# Check subscription exists
gcloud pubsub subscriptions describe pr-evaluation-tasks-sub

# Pull messages manually (for debugging)
gcloud pubsub subscriptions pull pr-evaluation-tasks-sub --limit=5
```

### Worker Not Processing Tasks
```bash
# Check worker logs
tail -f backend/logs/cloud_worker.log

# Verify ADC is configured
gcloud auth application-default print-access-token

# Test Pub/Sub subscription
python -c "from app.infrastructure.cloud_queue import pubsub_manager; print(pubsub_manager.subscriber)"
```

## 📚 Additional Documentation

- **Backend API**: See `backend/README.md`
- **UI Development**: See `ui/README.md`
- **Architecture Details**: See `docs/ARCHITECTURE.md` (if available)
- **API Reference**: http://localhost:8001/docs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

[License information here]

## 🙏 Acknowledgments

- APAC Atlas Guard Service for SSO
- Google Cloud Platform for infrastructure
- Anthropic, Google, and iFlow for AI agents