#!/bin/bash

# Memory-Break Orchestrator Production Startup Script
# Starts all services needed for containerized worker architecture

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_PORT=8000
API_HOST="127.0.0.1"
PYTHON_CMD="python"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🚀 Memory-Break Orchestrator Startup${NC}"
echo -e "${BLUE}Container-Managed Worker Architecture${NC}"
echo -e "${BLUE}========================================${NC}"

# Function to print colored status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to kill processes on port
kill_port_processes() {
    local port=$1
    echo -e "${YELLOW}🔍 Checking for processes on port $port...${NC}"
    
    # Find processes using the port
    PIDS=$(lsof -ti:$port 2>/dev/null || true)
    
    if [ ! -z "$PIDS" ]; then
        echo -e "${YELLOW}🔪 Killing processes on port $port: $PIDS${NC}"
        echo $PIDS | xargs kill -9 2>/dev/null || true
        sleep 2
    else
        echo -e "${GREEN}✅ Port $port is free${NC}"
    fi
}

# Function to check if service is responding
check_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}🔍 Waiting for $service_name to be ready...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            print_status "$service_name is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    
    print_error "$service_name failed to start after $max_attempts attempts"
    return 1
}

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}🔍 Checking prerequisites...${NC}"
    
    # Check Python
    if ! command -v python &> /dev/null; then
        print_error "Python not found"
        exit 1
    fi
    print_status "Python available: $(python --version)"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found"
        exit 1
    fi
    print_status "Docker available: $(docker --version | cut -d' ' -f3)"
    
    # Check if .env exists
    if [ ! -f ".env" ]; then
        print_warning ".env file not found, using defaults"
    else
        print_status ".env file found"
    fi
    
    # Check PostgreSQL connection
    if python -c "
import psycopg2
try:
    conn = psycopg2.connect('postgresql://erashu212:Enter123_@localhost:5432/cli_eval_db')
    conn.close()
    print('PostgreSQL connection successful')
except Exception as e:
    print(f'PostgreSQL connection failed: {e}')
    exit(1)
" 2>/dev/null; then
        print_status "PostgreSQL connection verified"
    else
        print_error "PostgreSQL connection failed"
        exit 1
    fi
    
    # Check Redis connection
    if python -c "
import redis
try:
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.ping()
    print('Redis connection successful')
except Exception as e:
    print(f'Redis connection failed: {e}')
    exit(1)
" 2>/dev/null; then
        print_status "Redis connection verified"
    else
        print_error "Redis connection failed"
        exit 1
    fi
}

# Function to start API server
start_api_server() {
    echo -e "${BLUE}🚀 Starting API server...${NC}"
    
    # Kill any existing processes on the API port
    kill_port_processes $API_PORT
    
    # Start the API server in the background
    nohup $PYTHON_CMD -m uvicorn app.main:app \
        --host $API_HOST \
        --port $API_PORT \
        --log-level info \
        > logs/api.log 2>&1 &
    
    API_PID=$!
    echo $API_PID > logs/api.pid
    print_status "API server started (PID: $API_PID)"
    
    # Check if API server is responding
    if check_service "http://$API_HOST:$API_PORT/health/" "API Server"; then
        print_status "API server health check passed"
    else
        print_error "API server health check failed"
        return 1
    fi
}

# Function to start worker
start_worker() {
    echo -e "${BLUE}👷 Starting worker process...${NC}"
    
    # Start the worker in the background
    nohup $PYTHON_CMD worker.py > logs/worker.log 2>&1 &
    
    WORKER_PID=$!
    echo $WORKER_PID > logs/worker.pid
    print_status "Worker started (PID: $WORKER_PID)"
    
    # Give worker time to initialize
    sleep 3
}

# Function to verify Docker images
verify_docker_images() {
    echo -e "${BLUE}🐳 Verifying Docker images...${NC}"
    
    # Check if base agent image exists
    if docker image inspect agent-base:latest > /dev/null 2>&1; then
        print_status "agent-base:latest image found"
    else
        print_warning "agent-base:latest image not found, building..."
        docker build -f dockerfiles/agent-base.Dockerfile -t agent-base:latest .
    fi
    
    # Check if iflow agent image exists
    if docker image inspect iflow-agent:latest > /dev/null 2>&1; then
        print_status "iflow-agent:latest image found"
    else
        print_warning "iflow-agent:latest image not found, building..."
        docker build -f dockerfiles/iflow-agent.Dockerfile -t iflow-agent:latest .
    fi
}

# Function to create log directory
setup_logging() {
    echo -e "${BLUE}📋 Setting up logging...${NC}"
    mkdir -p logs
    print_status "Log directory created: logs/"
}

# Function to display running services
show_services() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}🎉 All services started successfully!${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}Services running:${NC}"
    echo -e "  • API Server: http://$API_HOST:$API_PORT"
    echo -e "  • Health Check: http://$API_HOST:$API_PORT/health/"
    echo -e "  • API Documentation: http://$API_HOST:$API_PORT/docs"
    echo -e "  • Worker: Background process"
    echo
    echo -e "${YELLOW}Log files:${NC}"
    echo -e "  • API Server: logs/api.log"
    echo -e "  • Worker: logs/worker.log"
    echo
    echo -e "${YELLOW}PID files:${NC}"
    echo -e "  • API Server: logs/api.pid"
    echo -e "  • Worker: logs/worker.pid"
    echo
    echo -e "${GREEN}To run the end-to-end test:${NC}"
    echo -e "  ${BLUE}python test_automated_e2e.py${NC}"
    echo
    echo -e "${GREEN}To stop services:${NC}"
    echo -e "  ${BLUE}./scripts/stop.sh${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Cleanup function for graceful shutdown
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down services...${NC}"
    
    if [ -f logs/api.pid ]; then
        API_PID=$(cat logs/api.pid)
        if kill -0 $API_PID 2>/dev/null; then
            kill $API_PID
            print_status "API server stopped"
        fi
        rm -f logs/api.pid
    fi
    
    if [ -f logs/worker.pid ]; then
        WORKER_PID=$(cat logs/worker.pid)
        if kill -0 $WORKER_PID 2>/dev/null; then
            kill $WORKER_PID
            print_status "Worker stopped"
        fi
        rm -f logs/worker.pid
    fi
    
    echo -e "${GREEN}✅ Cleanup complete${NC}"
    exit 0
}

# Set trap for graceful shutdown
trap cleanup SIGINT SIGTERM

# Main execution
main() {
    # Setup
    setup_logging
    check_prerequisites
    verify_docker_images
    
    # Start services
    start_api_server
    start_worker
    
    # Show status
    show_services
    
    # Keep script running to handle signals
    echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
    while true; do
        sleep 1
    done
}

# Run main function
main "$@"
