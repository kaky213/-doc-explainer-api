#!/bin/bash
# DocTranslate App Management Script
# Simple start/stop/status/logs management for the FastAPI app

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="DocTranslate"
LOG_FILE="$APP_DIR/app.log"
PID_FILE="$APP_DIR/app.pid"
PORT=8000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[$APP_NAME]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

check_requirements() {
    if [ ! -f "$APP_DIR/requirements.txt" ]; then
        print_error "requirements.txt not found in $APP_DIR"
        exit 1
    fi
    
    if [ ! -d "$APP_DIR/.venv" ]; then
        print_warning "Virtual environment (.venv) not found"
        print_status "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
}

get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE" 2>/dev/null
    else
        echo ""
    fi
}

is_running() {
    local pid=$(get_pid)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

check_port() {
    if lsof -i :$PORT >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

start_app() {
    print_status "Starting $APP_NAME..."
    
    if is_running; then
        print_warning "$APP_NAME is already running (PID: $(get_pid))"
        return 0
    fi
    
    if check_port; then
        print_error "Port $PORT is already in use by another process"
        print_status "Check with: lsof -i :$PORT"
        return 1
    fi
    
    check_requirements
    
    # Start the app in background
    cd "$APP_DIR"
    nohup .venv/bin/uvicorn app:app --host 0.0.0.0 --port $PORT > "$LOG_FILE" 2>&1 &
    local pid=$!
    
    echo $pid > "$PID_FILE"
    
    # Wait a moment for startup
    sleep 2
    
    if is_running; then
        print_success "$APP_NAME started successfully (PID: $pid)"
        print_status "Logs: $LOG_FILE"
        print_status "URL: http://localhost:$PORT/static/index.html"
    else
        print_error "Failed to start $APP_NAME"
        print_status "Check logs: tail -f $LOG_FILE"
        return 1
    fi
}

stop_app() {
    print_status "Stopping $APP_NAME..."
    
    if ! is_running; then
        print_warning "$APP_NAME is not running"
        # Clean up PID file if it exists
        if [ -f "$PID_FILE" ]; then
            rm "$PID_FILE"
        fi
        return 0
    fi
    
    local pid=$(get_pid)
    kill "$pid" 2>/dev/null
    
    # Wait for process to stop
    for i in {1..10}; do
        if ! is_running; then
            break
        fi
        sleep 1
    done
    
    if is_running; then
        print_warning "Process did not stop gracefully, forcing..."
        kill -9 "$pid" 2>/dev/null
    fi
    
    if [ -f "$PID_FILE" ]; then
        rm "$PID_FILE"
    fi
    
    print_success "$APP_NAME stopped"
}

restart_app() {
    print_status "Restarting $APP_NAME..."
    stop_app
    sleep 2
    start_app
}

status_app() {
    print_status "$APP_NAME Status"
    echo "========================"
    
    if is_running; then
        local pid=$(get_pid)
        print_success "RUNNING (PID: $pid)"
        
        # Get process info
        if ps -p "$pid" >/dev/null 2>&1; then
            echo "Process: $(ps -p "$pid" -o cmd=)"
            echo "Uptime: $(ps -p "$pid" -o etime=)"
        fi
        
        # Check port
        if check_port; then
            print_success "Port $PORT: LISTENING"
        else
            print_error "Port $PORT: NOT LISTENING"
        fi
        
        # Check health endpoint
        if curl -s http://localhost:$PORT/health >/dev/null 2>&1; then
            print_success "Health endpoint: RESPONDING"
        else
            print_error "Health endpoint: NOT RESPONDING"
        fi
        
        echo ""
        print_status "Frontend: http://localhost:$PORT/static/index.html"
        print_status "Frontend: http://localhost:$PORT/static/index.html"
        
    else
        print_error "NOT RUNNING"
        
        if [ -f "$PID_FILE" ]; then
            print_warning "Stale PID file found: $PID_FILE"
        fi
        
        if check_port; then
            print_warning "Port $PORT is in use by another process"
        fi
    fi
    
    echo "========================"
}

show_logs() {
    print_status "Showing logs (tail -f $LOG_FILE)"
    echo "========================"
    
    if [ ! -f "$LOG_FILE" ]; then
        print_error "Log file not found: $LOG_FILE"
        return 1
    fi
    
    if [ "$1" = "follow" ]; then
        tail -f "$LOG_FILE"
    else
        tail -100 "$LOG_FILE"
    fi
}

show_help() {
    echo "DocTranslate App Management Script"
    echo "Usage: $0 {start|stop|restart|status|logs|help}"
    echo ""
    echo "Commands:"
    echo "  start     - Start the application"
    echo "  stop      - Stop the application"
    echo "  restart   - Restart the application"
    echo "  status    - Show application status"
    echo "  logs      - Show recent logs (last 100 lines)"
    echo "  logs follow - Follow logs in real-time"
    echo "  test      - Run all tests (pass extra args like -k test_name)
  help      - Show this help message"
    echo ""
    echo "Paths:"
    echo "  App dir:   $APP_DIR"
    echo "  Log file:  $LOG_FILE"
    echo "  PID file:  $PID_FILE"
    echo "  Port:      $PORT"
}

case "$1" in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        restart_app
        ;;
    status)
        status_app
        ;;
    logs)
        if [ "$2" = "follow" ]; then
            show_logs follow
        else
            show_logs
        fi
        ;;
    help|--help|-h)
        show_help
        ;;
    test)
        shift
        .venv/bin/pytest tests/ "$@"
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac