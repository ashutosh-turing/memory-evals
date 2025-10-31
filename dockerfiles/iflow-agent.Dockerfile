# iFlow Agent Container - Isolated execution environment
FROM agent-base:latest as iflow-agent

# Set agent-specific environment variables
ENV AGENT_TYPE=iflow \
    AGENT_NAME=iflow \
    AGENT_PORT=8080 \
    MAX_MEMORY=3g \
    MAX_EXECUTION_TIME=1800

# Switch to root to install Node.js and iFlow CLI
USER root

# Install Node.js if not already available and install iFlow CLI via npm
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g @iflow-ai/iflow-cli && \
    pip install --no-cache-dir anthropic tiktoken

# Create home directory for agentuser and iFlow workspace with proper isolation (as root)
RUN mkdir -p /home/agentuser /agent/workspace/iflow /agent/logs/iflow /agent/results/iflow && \
    chown -R agentuser:agentuser /home/agentuser /agent/workspace/iflow /agent/logs/iflow /agent/results/iflow

# Switch back to non-root user for security
USER agentuser

# Copy iFlow-specific configuration (agents already copied in base image)
# Agent files are already available from the base image

# Expose port for health checks and communication
EXPOSE 8080

# Set resource limits through cgroups (if available)
LABEL memory="3g" \
      cpu="2000m" \
      agent.type="iflow" \
      agent.version="0.3.11"

# Override entrypoint for iFlow-specific execution
CMD ["python", "agent_runner.py", "--agent=iflow"]
