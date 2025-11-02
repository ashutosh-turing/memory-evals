#!/bin/bash
# Agent Container Entrypoint Script
# Handles agent container initialization and execution

set -euo pipefail

# Configuration
AGENT_TYPE="${AGENT_TYPE:-unknown}"
AGENT_PORT="${AGENT_PORT:-8080}"
TASK_DATA_FILE="${TASK_DATA_FILE:-/agent/task_data.json}"
ORCHESTRATOR_URL="${ORCHESTRATOR_URL:-http://host.docker.internal:8000}"

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [$AGENT_TYPE] $1"
}

# Error handler
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Health check endpoint (simple HTTP server for container health)
start_health_server() {
    log "Starting health check server on port $AGENT_PORT"
    python3 -c "
import http.server
import socketserver
import json
from datetime import datetime

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': 'healthy',
                'agent_type': '$AGENT_TYPE',
                'timestamp': datetime.utcnow().isoformat(),
                'port': $AGENT_PORT
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

with socketserver.TCPServer(('', $AGENT_PORT), HealthHandler) as httpd:
    httpd.serve_forever()
" &
    HEALTH_PID=$!
    log "Health server started with PID: $HEALTH_PID"
}

# Wait for task data
wait_for_task_data() {
    local timeout=300  # 5 minutes timeout
    local elapsed=0
    
    log "Waiting for task data at $TASK_DATA_FILE"
    
    while [ ! -f "$TASK_DATA_FILE" ] && [ $elapsed -lt $timeout ]; do
        sleep 5
        elapsed=$((elapsed + 5))
        log "Still waiting for task data... (${elapsed}s elapsed)"
    done
    
    if [ ! -f "$TASK_DATA_FILE" ]; then
        error_exit "Task data file not found after ${timeout}s timeout"
    fi
    
    # Validate task data JSON
    if ! python3 -c "import json; json.load(open('$TASK_DATA_FILE'))" 2>/dev/null; then
        error_exit "Invalid JSON in task data file"
    fi
    
    log "Task data received and validated"
}

# Cleanup function
cleanup() {
    log "Performing cleanup..."
    
    # Kill health server if running
    if [ -n "${HEALTH_PID:-}" ]; then
        kill $HEALTH_PID 2>/dev/null || true
    fi
    
    # Clean up temporary files
    rm -rf /tmp/* 2>/dev/null || true
    
    # Report container shutdown
    python3 -c "
import json
import sys
import requests
from datetime import datetime

try:
    with open('$TASK_DATA_FILE', 'r') as f:
        task_data = json.load(f)
    
    task_id = task_data.get('task_id')
    if task_id:
        payload = {
            'task_id': task_id,
            'agent_type': '$AGENT_TYPE',
            'status': 'CONTAINER_SHUTDOWN',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        requests.post(
            f'$ORCHESTRATOR_URL/api/v1/tasks/{task_id}/status',
            json=payload,
            timeout=5
        )
except Exception as e:
    print(f'Failed to report shutdown: {e}', file=sys.stderr)
" || true

    log "Cleanup completed"
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Main execution
main() {
    log "Starting agent container: $AGENT_TYPE"
    log "Container configuration:"
    log "  - Agent Type: $AGENT_TYPE"
    log "  - Agent Port: $AGENT_PORT"  
    log "  - Orchestrator: $ORCHESTRATOR_URL"
    log "  - Max Memory: ${MAX_MEMORY:-3g}"
    log "  - Max Execution Time: ${MAX_EXECUTION_TIME:-1800}s"
    
    # Verify agent type
    if [ "$AGENT_TYPE" = "unknown" ]; then
        error_exit "AGENT_TYPE environment variable not set"
    fi
    
    # Start health check server
    start_health_server
    
    # Wait for task data
    wait_for_task_data
    
    # Parse task data for logging
    TASK_ID=$(python3 -c "import json; data=json.load(open('$TASK_DATA_FILE')); print(data.get('task_id', 'unknown'))")
    PR_URL=$(python3 -c "import json; data=json.load(open('$TASK_DATA_FILE')); print(data.get('pr_url', 'unknown'))")
    
    log "Task Details:"
    log "  - Task ID: $TASK_ID"
    log "  - PR URL: $PR_URL"
    
    # Create necessary directories
    mkdir -p "/agent/workspace/$AGENT_TYPE"
    mkdir -p "/agent/logs/$AGENT_TYPE" 
    mkdir -p "/agent/results/$AGENT_TYPE"
    
    # Set up logging for agent execution
    exec 1> >(tee -a "/agent/logs/$AGENT_TYPE/container.log")
    exec 2> >(tee -a "/agent/logs/$AGENT_TYPE/container.log" >&2)
    
    log "Starting agent runner..."
    
    # Execute the agent runner with proper error handling
    if python3 agent_runner.py --agent="$AGENT_TYPE"; then
        log "Agent execution completed successfully"
        exit 0
    else
        error_exit "Agent execution failed"
    fi
}

# Execute main function
main "$@"
