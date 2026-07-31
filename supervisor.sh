#!/usr/bin/env bash
# Supervisor - keep-alive loop for AI Agent Beast
#
# Monitors three components and restarts any that die:
#   1. Ollama      (LLM backend, port 11434)
#   2. Agent       (main.py --web, port 8765)
#   3. Tunnel      (keep_alive.sh -- localhost.run public URL, optional)
#
# All logs are written to ./logs/ so they survive reboots (no /tmp dependency).
#
# Usage:
#   ./supervisor.sh --start     # Daemonize (nohup background loop)
#   ./supervisor.sh --stop      # Stop supervisor + agent + tunnel (ollama left running)
#   ./supervisor.sh --restart   # Stop then start
#   ./supervisor.sh --status    # Show component health
#   ./supervisor.sh --foreground# Run loop in foreground (for debugging)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR"

AGENT_LOG="$LOGS_DIR/agent.log"
OLLAMA_LOG="$LOGS_DIR/ollama.log"
SUPERVISOR_LOG="$LOGS_DIR/supervisor.log"
TUNNEL_LOG="$LOGS_DIR/tunnel.log"
TUNNEL_URL_FILE="$LOGS_DIR/tunnel_url.txt"

SUPERVISOR_PID_FILE="$LOGS_DIR/supervisor.pid"
AGENT_PID_FILE="$LOGS_DIR/agent.pid"
OLLAMA_PID_FILE="$LOGS_DIR/ollama.pid"
TUNNEL_PID_FILE="$LOGS_DIR/tunnel.pid"

CHECK_INTERVAL=15

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$SUPERVISOR_LOG"; }

# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

ollama_up() {
    curl -sf -m 5 http://localhost:11434/api/tags > /dev/null 2>&1
}

agent_up() {
    curl -sf -m 5 http://localhost:8765/ -o /dev/null 2>&1
}

tunnel_up() {
    [ -f "$TUNNEL_URL_FILE" ] && [ -s "$TUNNEL_URL_FILE" ]
}

# ---------------------------------------------------------------------------
# Starters
# ---------------------------------------------------------------------------

start_ollama() {
    if ollama_up; then return 0; fi
    log "OLLAMA DOWN -> restarting"
    nohup ollama serve >> "$OLLAMA_LOG" 2>&1 &
    echo $! > "$OLLAMA_PID_FILE"
    # Wait up to 15s for it to come up
    for _ in $(seq 1 15); do
        ollama_up && { log "OLLAMA up (pid $(cat "$OLLAMA_PID_FILE"))"; return 0; }
        sleep 1
    done
    log "OLLAMA failed to start within 15s"
    return 1
}

start_agent() {
    if agent_up; then return 0; fi
    log "AGENT DOWN -> restarting"
    nohup python3 main.py --web >> "$AGENT_LOG" 2>&1 &
    echo $! > "$AGENT_PID_FILE"
    # Wait up to 30s (model + server boot can be slow)
    for _ in $(seq 1 30); do
        agent_up && { log "AGENT up (pid $(cat "$AGENT_PID_FILE"))"; return 0; }
        sleep 1
    done
    log "AGENT failed to start within 30s"
    return 1
}

start_tunnel() {
    if tunnel_up && [ -f "$TUNNEL_PID_FILE" ] && kill -0 "$(cat "$TUNNEL_PID_FILE")" 2>/dev/null; then
        return 0
    fi
    if ! command -v ssh > /dev/null 2>&1; then
        log "TUNNEL skipped (ssh not available)"
        return 0
    fi
    log "TUNNEL DOWN -> starting"
    LOG_FILE="$TUNNEL_LOG" TUNNEL_URL_FILE="$TUNNEL_URL_FILE" TUNNEL_PID_FILE="$TUNNEL_PID_FILE" \
        "$SCRIPT_DIR/keep_alive.sh" --daemon >> "$SUPERVISOR_LOG" 2>&1
    sleep 3
    if tunnel_up; then log "TUNNEL up: $(cat "$TUNNEL_URL_FILE")"; else log "TUNNEL not up yet (retrying next cycle)"; fi
}

# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

stop_all() {
    # Tunnel
    if [ -f "$TUNNEL_PID_FILE" ]; then
        pid=$(cat "$TUNNEL_PID_FILE")
        kill "$pid" 2>/dev/null || true
        rm -f "$TUNNEL_PID_FILE"
    fi
    pkill -f "ssh.*nokey@localhost.run" 2>/dev/null || true
    # Agent
    if [ -f "$AGENT_PID_FILE" ]; then
        pid=$(cat "$AGENT_PID_FILE")
        kill "$pid" 2>/dev/null || true
        rm -f "$AGENT_PID_FILE"
    fi
    pkill -f "python3 main.py --web" 2>/dev/null || true
    # Supervisor itself
    if [ -f "$SUPERVISOR_PID_FILE" ]; then
        pid=$(cat "$SUPERVISOR_PID_FILE")
        kill "$pid" 2>/dev/null || true
        rm -f "$SUPERVISOR_PID_FILE"
    fi
    log "All components stopped (ollama left running)"
}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

supervise() {
    log "Supervisor started (interval ${CHECK_INTERVAL}s)"
    start_ollama
    start_agent
    start_tunnel
    while true; do
        start_ollama || true
        start_agent || true
        start_tunnel || true
        sleep "$CHECK_INTERVAL"
    done
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

case "${1:-}" in
    --start)
        if [ -f "$SUPERVISOR_PID_FILE" ] && kill -0 "$(cat "$SUPERVISOR_PID_FILE")" 2>/dev/null; then
            echo "Supervisor already running (pid $(cat "$SUPERVISOR_PID_FILE"))"
            exit 0
        fi
        nohup "$0" --foreground > /dev/null 2>&1 &
        echo $! > "$SUPERVISOR_PID_FILE"
        echo "Supervisor started (pid $(cat "$SUPERVISOR_PID_FILE")). Logs: $LOGS_DIR"
        ;;
    --stop)
        stop_all
        echo "Supervisor stopped."
        ;;
    --restart)
        stop_all
        sleep 1
        exec "$0" --start
        ;;
    --status)
        printf "ollama : %s\n" "$(ollama_up && echo UP || echo DOWN)"
        printf "agent  : %s\n" "$(agent_up && echo UP || echo DOWN)"
        printf "tunnel : %s\n" "$(tunnel_up && echo "UP ($(cat "$TUNNEL_URL_FILE"))" || echo DOWN)"
        printf "logs   : %s\n" "$LOGS_DIR"
        exit 0
        ;;
    --foreground)
        supervise
        ;;
    *)
        echo "Usage: $0 {--start|--stop|--restart|--status|--foreground}"
        exit 1
        ;;
esac
