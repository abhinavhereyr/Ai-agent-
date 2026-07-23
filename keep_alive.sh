#!/usr/bin/env bash
# Keep Alive Script - Auto-reconnecting SSH tunnel for AI Agent Beast
#
# Creates and maintains a public URL via localhost.run tunnel.
# Automatically reconnects if the tunnel drops.
# Saves the current URL to /tmp/tunnel_url.txt
#
# Usage:
#   ./keep_alive.sh                    # Interactive (shows connection status)
#   ./keep_alive.sh --daemon           # Background mode (logs to file)
#   ./keep_alive.sh --stop             # Kill the tunnel
#   ./keep_alive.sh --url              # Show current public URL

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TUNNEL_URL_FILE="/tmp/tunnel_url.txt"
TUNNEL_PID_FILE="/tmp/keep_alive.pid"
LOG_FILE="/tmp/tunnel.log"
LOCAL_PORT=8765
TUNNEL_SERVICE="nokey@localhost.run"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
ok() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERR]${NC} $1"; }

show_url() {
    if [ -f "$TUNNEL_URL_FILE" ]; then
        url=$(cat "$TUNNEL_URL_FILE")
        echo "$url"
    else
        echo "No tunnel URL found."
    fi
}

cleanup() {
    local pid
    if [ -f "$TUNNEL_PID_FILE" ]; then
        pid=$(cat "$TUNNEL_PID_FILE")
        kill "$pid" 2>/dev/null || true
        rm -f "$TUNNEL_PID_FILE"
    fi
    # Kill any lingering SSH tunnels
    pkill -f "ssh.*nokey@localhost.run" 2>/dev/null || true
    rm -f "$TUNNEL_URL_FILE"
    info "Tunnel cleaned up."
}

stop_tunnel() {
    info "Stopping tunnel..."
    cleanup
    ok "Tunnel stopped."
    exit 0
}

monitor_tunnel() {
    local pid=$1
    local logfile=$2

    # Wait for URL to appear in the log
    local wait_count=0
    while [ $wait_count -lt 30 ]; do
        if grep -q "lhr.life" "$logfile" 2>/dev/null; then
            url=$(grep -oP 'https?://[a-zA-Z0-9-]+\.lhr\.life' "$logfile" | head -1)
            if [ -n "$url" ]; then
                echo "$url" > "$TUNNEL_URL_FILE"
                ok "Tunnel URL: ${url}"
                return 0
            fi
        fi
        sleep 1
        ((wait_count++))
    done
    return 1
}

run_tunnel() {
    local logfile="$1"
    local retries=0
    local max_retries=9999

    while [ $retries -lt $max_retries ]; do
        info "Starting tunnel (attempt $((retries + 1)))..."
        echo "--- Tunnel attempt $(date) ---" >> "$logfile"

        # Start SSH tunnel, capture output to both log and pipe for real-time reading
        ssh -T -o StrictHostKeyChecking=no \
              -o ServerAliveInterval=15 \
              -o ServerAliveCountMax=3 \
              -o ExitOnForwardFailure=yes \
              -o TCPKeepAlive=yes \
              -R "80:localhost:${LOCAL_PORT}" \
              "$TUNNEL_SERVICE" 2>&1 | tee -a "$logfile" &

        SSH_PID=$!
        echo $SSH_PID > "$TUNNEL_PID_FILE"

        # Wait for URL or failure
        if monitor_tunnel $SSH_PID "$logfile"; then
            # Tunnel is up - wait for it to die
            wait $SSH_PID 2>/dev/null || true
            warn "Tunnel disconnected (was up for a while). Reconnecting..."
        else
            warn "Tunnel failed to establish within 30s. Retrying..."
            kill $SSH_PID 2>/dev/null || true
        fi

        ((retries++))
        sleep 3
    done
}

# --- Main ---
case "${1:-}" in
    --stop|-s|stop|kill)
        stop_tunnel
        ;;
    --url|-u|url)
        show_url
        exit 0
        ;;
    --daemon|-d|daemon)
        # Run in background, log to file
        info "Starting tunnel in daemon mode..."
        nohup "$SCRIPT_DIR/keep_alive.sh" --background > "$LOG_FILE" 2>&1 &
        DAEMON_PID=$!
        echo $DAEMON_PID > "$TUNNEL_PID_FILE"
        ok "Daemon started (PID: $DAEMON_PID)"
        info "Log: $LOG_FILE"
        # Wait for URL
        sleep 10
        url=$(show_url)
        if [ "$url" != "No tunnel URL found." ]; then
            ok "Public URL: $url"
        else
            warn "Still connecting... check $LOG_FILE"
        fi
        exit 0
        ;;
    --background|background)
        # Internal: actual tunnel loop
        run_tunnel "$LOG_FILE"
        ;;
    *)
        # Interactive: run in foreground
        info "Starting tunnel. Press Ctrl+C to stop."
        info "Local port: $LOCAL_PORT"
        info ""
        run_tunnel "/dev/stdout"
        ;;
esac
