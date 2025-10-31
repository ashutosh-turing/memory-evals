# Claude Agent Container - Isolated execution environment
FROM dockerfiles/agent-base.Dockerfile as claude-agent

# Set agent-specific environment variables
ENV AGENT_TYPE=claude \
    AGENT_NAME=claude \
    AGENT_PORT=8081 \
    MAX_MEMORY=3g \
    MAX_EXECUTION_TIME=1800

# Install Claude-specific dependencies
RUN pip install --no-cache-dir \
    anthropic==0.28.0 \
    cline==2.0.30 \
    tiktoken

# Copy Claude-specific configuration and prompts
COPY prompts/claude/ ./prompts/claude/
COPY app/agents/claude_agent.py ./agents/

# Create Claude workspace with proper isolation
RUN mkdir -p /agent/workspace/claude /agent/logs/claude /agent/results/claude && \
    chown -R agentuser:agentuser /agent/workspace/claude /agent/logs/claude /agent/results/claude

# Expose port for health checks and communication
EXPOSE 8081

# Set resource limits through cgroups (if available)
LABEL memory="3g" \
      cpu="2000m" \
      agent.type="claude" \
      agent.version="2.0.30"

# Override entrypoint for Claude-specific execution
CMD ["python", "agent_runner.py", "--agent=claude"]
