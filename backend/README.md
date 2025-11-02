# Memory-Break Orchestrator - Backend

Backend service for the Memory-Break Orchestrator, an AI agent evaluation platform that tests memory compression capabilities across iFlow, Claude, and Gemini agents.

## Architecture

The backend is built with:
- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Primary database for task and agent run storage
- **Redis** - Optional caching layer
- **Alembic** - Database migrations
- **SQLModel** - ORM for database interactions
- **Celery/RQ** - Background task processing

## Directory Structure

```
backend/
├── app/                    # Main application code
│   ├── agents/            # Agent implementations (iFlow, Claude, Gemini)
│   ├── domain/            # Domain entities and models
│   ├── infrastructure/    # Database, queue, external services
│   ├── presentation/      # API routes, middleware
│   ├── services/          # Business logic services
│   ├── config.py          # Application configuration
│   └── main.py            # FastAPI application entry point
├── alembic/               # Database migrations
├── workers/               # Background worker implementations
├── scripts/               # Deployment and utility scripts
├── prompts/               # LLM prompts for evaluation
├── storage/               # Task artifacts and logs
├── logs/                  # Application logs
├── worker.py              # Worker process entry point
├── pyproject.toml         # Python dependencies
└── .env.example           # Environment variables template
```

## Setup

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Redis (optional, for caching)
- Agent CLIs: iFlow, Claude, Gemini (for agent execution)

### Installation

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -e .
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

### Running the Application

#### Development Mode

Start all services (API + Worker):
```bash
./scripts/run.sh
```

Or start services individually:

**API Server**:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Worker**:
```bash
python worker.py
```

#### Production Mode

Use the provided scripts:
```bash
./scripts/run.sh
```

Stop services:
```bash
./scripts/stop.sh
```

## Configuration

All configuration is done via environment variables. See `.env.example` for all available options.

### Key Configuration Options

- **DATABASE_URL**: PostgreSQL connection string
- **REDIS_URL**: Redis connection string (optional)
- **SSO_ENABLED**: Enable/disable SSO authentication
- **SSO_SERVICE_URL**: APAC Atlas Guard Service URL
- **QUEUE_ENABLED**: Enable Cloud Tasks queue
- **STORAGE_DIR**: Directory for task artifacts

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Main Endpoints

- `POST /api/v1/tasks` - Create new evaluation task
- `GET /api/v1/tasks` - List tasks with filtering
- `GET /api/v1/tasks/{task_id}` - Get task details
- `GET /api/v1/tasks/{task_id}/agents` - Get agent runs
- `GET /api/v1/tasks/{task_id}/leaderboard` - Get evaluation scores
- `GET /api/v1/logs/{task_id}/stream` - Stream task logs (SSE)

## Authentication

The backend supports SSO authentication via APAC Atlas Guard Service:

1. Service runs behind SSO Gateway
2. Gateway validates JWT tokens
3. Gateway injects user context into headers:
   - `X-User-ID`
   - `X-User-Email`
   - `X-Org-ID`
   - `X-Team-ID`
   - `X-User-Role`

For local development, set `SSO_ENABLED=false` to bypass authentication.

## Database Migrations

### Create a new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

### Apply migrations:
```bash
alembic upgrade head
```

### Rollback migration:
```bash
alembic downgrade -1
```

## Testing

Run tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app --cov-report=html
```

## Monitoring

### Logs

- **API logs**: `logs/api.log`
- **Worker logs**: `logs/worker.log`
- **Task logs**: `storage/{task_id}/task.log`

### Health Check

```bash
curl http://localhost:8000/health/
```

## Deployment

### Docker

Build the image:
```bash
docker build -t memory-break-backend .
```

Run the container:
```bash
docker run -p 8000:8000 --env-file .env memory-break-backend
```

### Cloud Run

Deploy to Google Cloud Run:
```bash
gcloud run deploy memory-break-backend \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## Troubleshooting

### Database Connection Issues

1. Verify PostgreSQL is running
2. Check DATABASE_URL in .env
3. Ensure database exists: `createdb memorybreak`

### Agent CLI Issues

1. Verify agent CLIs are installed and in PATH
2. Check agent configuration in .env
3. Test agent CLIs manually: `iflow --version`

### Worker Not Processing Tasks

1. Check worker logs: `tail -f logs/worker.log`
2. Verify Redis connection (if using)
3. Restart worker: `./scripts/stop.sh && ./scripts/run.sh`

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## License

Proprietary - Turing Platform Team

