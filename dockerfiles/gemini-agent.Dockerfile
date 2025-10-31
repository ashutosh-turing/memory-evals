# Gemini Agent Container - Isolated execution environment
FROM dockerfiles/agent-base.Dockerfile as gemini-agent

# Set agent-specific environment variables
ENV AGENT_TYPE=gemini \
    AGENT_NAME=gemini \
    AGENT_PORT=8082 \
    MAX_MEMORY=3g \
    MAX_EXECUTION_TIME=1800

# Install Gemini-specific dependencies
RUN pip install --no-cache-dir \
    google-generativeai \
    google-auth \
    google-auth-oauthlib \
    tiktoken

# Copy Gemini-specific configuration and prompts
COPY prompts/gemini/ ./prompts/gemini/
COPY app/agents/gemini_agent.py ./agents/

# Create Gemini workspace with proper isolation
RUN mkdir -p /agent/workspace/gemini /agent/logs/gemini /agent/results/gemini && \
    chown -R agentuser:agentuser /agent/workspace/gemini /agent/logs/gemini /agent/results/gemini

# Expose port for health checks and communication
EXPOSE 8082

# Set resource limits through cgroups (if available)
LABEL memory="3g" \
      cpu="2000m" \
      agent.type="gemini" \
      agent.version="latest"

# Override entrypoint for Gemini-specific execution
CMD ["python", "agent_runner.py", "--agent=gemini"]
