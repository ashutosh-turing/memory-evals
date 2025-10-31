#!/bin/bash

# Memory-Break Orchestrator Stop Script
# Cleanly shuts down all services

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_PORT=8000

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🛑 Memory-Break Orchestrator Shutdown${NC}"
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

# Function to kill processes by PID file
kill_service_by_pid() {
    local service_name=$1
    local pid_file=$2
    
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if kill -0 $PID 2>/dev/null; then
            echo -e "${YELLOW}🔪 Stopping $service_name (PID: $PID)...${NC}"
            kill $PID
            
            # Wait for graceful shutdown
            local count=0
            while kill -0 $PID 2>/dev/null && [ $count -lt 10 ]; do
                sleep 1
                count=$((count + 1))
            done
            
            # Force kill if still running
            if kill -0 $PID 2>/dev/null; then
                print_warning "Force killing $service_name..."
                kill -9 $PID 2>/dev/null || true
            fi
            
            print_status "$service_name stopped"
        else
            print_warning "$service_name was not running"
        fi
        rm -f "$pid_file"
    else
        print_warning "No PID file found for $service_name"
    fi
}

# Function to kill processes on port
kill_port_processes() {
    local port=$1
    local service_name=$2
    
    echo -e "${YELLOW}🔍 Checking for processes on port $port...${NC}"
    
    # Find processes using the port
    PIDS=$(lsof -ti:$port 2>/dev/null || true)
    
    if [ ! -z "$PIDS" ]; then
        echo -e "${YELLOW}🔪 Killing $service_name processes on port $port: $PIDS${NC}"
        echo $PIDS | xargs kill -9 2>/dev/null || true
        print_status "$service_name processes on port $port stopped"
    else
        print_status "No processes found on port $port"
    fi
}

# Function to cleanup Docker containers
cleanup_containers() {
    echo -e "${BLUE}🐳 Cleaning up Docker containers...${NC}"
    
    # Stop any running agent containers
    RUNNING_CONTAINERS=$(docker ps -q --filter "label=agent.type" 2>/dev/null || true)
    
    if [ ! -z "$RUNNING_CONTAINERS" ]; then
        echo -e "${YELLOW}🔪 Stopping agent containers...${NC}"
        echo $RUNNING_CONTAINERS | xargs docker stop 2>/dev/null || true
        echo $RUNNING_CONTAINERS | xargs docker rm 2>/dev/null || true
        print_status "Agent containers cleaned up"
    else
        print_status "No agent containers running"
    fi
}

# Main shutdown function
main() {
    echo -e "${BLUE}🛑 Shutting down services...${NC}"
    
    # Stop services by PID files
    kill_service_by_pid "Worker" "logs/worker.pid"
    kill_service_by_pid "API Server" "logs/api.pid"
    
    # Kill any remaining processes on API port
    kill_port_processes $API_PORT "API Server"
    
    # Cleanup Docker containers
    cleanup_containers
    
    # Remove log files if requested
    if [ "$1" = "--clean-logs" ]; then
        echo -e "${BLUE}🧹 Cleaning log files...${NC}"
        rm -f logs/*.log 2>/dev/null || true
        print_status "Log files cleaned"
    fi
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}✅ All services stopped successfully!${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    if [ "$1" != "--clean-logs" ]; then
        echo -e "${YELLOW}Log files preserved in logs/ directory${NC}"
        echo -e "${YELLOW}Use: ./scripts/stop.sh --clean-logs to remove them${NC}"
    fi
}

# Run main function
main "$@"
