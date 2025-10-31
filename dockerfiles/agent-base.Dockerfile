# Base Dockerfile for all agent containers
FROM python:3.11-slim as agent-base

# Set environment variables for better Python behavior in containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd -r agentuser && useradd -r -g agentuser agentuser

# Install system dependencies required for git operations and agent execution
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /agent

# Copy requirements and install Python dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e .

# Create necessary directories with proper permissions
RUN mkdir -p /agent/workspace /agent/logs /agent/results && \
    chown -R agentuser:agentuser /agent

# Copy agent execution framework
COPY app/ ./app/
COPY prompts/ ./prompts/
COPY workers/ ./workers/

# Copy agent runner script
COPY scripts/agent_runner.py ./
COPY scripts/agent_entrypoint.sh ./

# Make scripts executable
RUN chmod +x agent_entrypoint.sh && \
    chown -R agentuser:agentuser /agent

# Switch to non-root user
USER agentuser

# Health check for agent readiness
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command (to be overridden by specific agents)
CMD ["./agent_entrypoint.sh"]
