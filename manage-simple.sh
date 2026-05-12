#!/bin/bash
# DocTranslate Simple Management Script
# No colors, minimal dependencies

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="DocTranslate"
LOG_FILE="$APP_DIR/app.log"
PID_FILE="$APP_DIR/app.pid"
PORT=8000

echo_info() {
    echo "[$APP_NAME] $1"
}

echo_success() {
    echo "[OK] $1"
}

echo_error() {
    echo "[ERROR] $1"
}

echo_warning() {
    echo "[WARN] $1"
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

start() {
    echo_info "Starting $APP_NAME..."
    
    if is_running; then
        echo_warning "$APP_NAME is already running (PID: $(get_pid))"
        return 0
    fi
    
    if lsof -i :$PORT >/dev/null 2>&1; then
        echo_error "Port $PORT is already in use"
        return 1
    fi
    
    cd "$APP_DIR"
    nohup .venv/bin/uvicorn app:app --host 0.0.0.0 --port $PORT > "$LOG_FILE" 2>&1 &
    local pid=$!
    
    echo $pid > "$PID_FILE"
    sleep 2
    
    if is_running; then
        echo_success "Started (PID: $pid)"
        echo_info "URL: http://localhost:$PORT/static/index.html"
        echo_info "Logs: $LOG_FILE"
    else
        echo_error "Failed to start"
        return 1
    fi
}

stop() {
    echo_info "Stopping $APP_NAME..."
    
    if ! is_running; then
        echo_warning "Not running"
        [ -f "$PID_FILE" ] && rm "$PID_FILE"
        return 0
    fi
    
    local pid=$(get_pid)
    kill "$pid" 2>/dev/null
    
    for i in {1..5}; do
        if ! is_running; then
            break
        fi
        sleep 1
    done
    
    if is_running; then
        echo_warning "Force stopping..."
        kill -9 "$pid" 2>/dev/null
    fi
    
    [ -f "$PID_FILE" ] && rm "$PID_FILE"
    echo_success "Stopped"
}

restart() {
    stop
    sleep 1
    start
}

status() {
    echo_info "Status:"
    echo "--------"
    
    if is_running; then
        local pid=$(get_pid)
        echo_success "Running (PID: $pid)"
        
        if ps -p "$pid" >/dev/null 2>&1; then
            echo "Uptime: $(ps -p "$pid" -o etime=)"
        fi
        
        if curl -s http://localhost:$PORT/health >/dev/null 2>&1; then
            echo_success "Health: OK"
        else
            echo_error "Health: FAILED"
        fi
        
        echo "URL: http://localhost:$PORT/static/index.html"
    else
        echo_error "Not running"
    fi
    echo "--------"
}

logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo_error "Log file not found"
        return 1
    fi
    
    if [ "$1" = "follow" ]; then
        tail -f "$LOG_FILE"
    else
        tail -50 "$LOG_FILE"
    fi
}

help() {
    echo "DocTranslate Management"
    echo "Usage: $0 {start|stop|restart|status|logs|help}"
    echo ""
    echo "Commands:"
    echo "  start   - Start app"
    echo "  stop    - Stop app"
    echo "  restart - Restart app"
    echo "  status  - Show status"
    echo "  logs    - Show logs"
    echo "  help    - This help"
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) restart ;;
    status) status ;;
    logs) logs "$2" ;;
    help|--help|-h) help ;;
    *) 
        echo_error "Unknown command: $1"
        echo ""
        help
        exit 1
        ;;
esac