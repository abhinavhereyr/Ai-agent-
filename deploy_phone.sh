#!/bin/bash
"""":"
# ===========================================================================
# Android/Termux Deployment Script for AI Agent Beast v3.0
# ===========================================================================
# Run this on your Android phone after installing Termux:
#   pkg install curl git -y
#   curl -sL https://github.com/abhinavhereyr/Ai-agent-/raw/main/deploy_phone.sh | bash
#
# Or copy this file to your phone and run:
#   bash deploy_phone.sh [--web] [--auto] [--all] [--telegram]
# ===========================================================================

set -e

MODE="${1:---web}"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   AI AGENT BEAST v3.0 — PHONE DEPLOY   ║"
echo "║   For Android (Termux)                  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Verify we're in Termux
if [ ! -d "/data/data/com.termux" ] && [ -z "$TERMUX_VERSION" ]; then
    echo "⚠  This script is designed for Termux on Android."
    echo "   Continuing anyway (may still work on Linux)..."
fi

# 1. Update packages
echo "[1/8] 📦 Updating Termux packages..."
pkg update -y
pkg upgrade -y

# 2. Install core dependencies
echo "[2/8] 📦 Installing Python and tools..."
pkg install -y python python-pip git openssl curl wget

# 3. Install audio support (for voice features)
echo "[3/8] 🔇 Installing audio support..."
pkg install -y espeak termux-api python-numpy

# 4. Optional: ADB for device control
echo "[4/8] 🔌 Optional: Install ADB for Android device control? (y/n)"
read -r opt_adb
if [[ "$opt_adb" == "y" ]]; then
    echo "   Installing Android tools..."
    pkg install -y android-tools
fi

# 5. Clone repository
echo "[5/8] 📂 Cloning AI Agent Beast repository..."
AGENT_DIR="$HOME/agent_beast"
if [ -d "$AGENT_DIR/.git" ]; then
    echo "   Repository exists, pulling latest..."
    cd "$AGENT_DIR" && git pull
else
    git clone https://github.com/abhinavhereyr/Ai-agent-.git "$AGENT_DIR"
    cd "$AGENT_DIR"
fi

# 6. Create virtual environment
echo "[6/8] 🐍 Creating Python environment..."
python -m venv venv
source venv/bin/activate

# 7. Install Python packages
echo "[7/8] 📚 Installing Python packages..."
pip install --upgrade pip -q

# Core packages
pip install fastapi uvicorn requests httpx beautifulsoup4 -q

# DuckDuckGo search
pip install duckduckgo-search -q

# Audio (optional)
pip install sounddevice numpy pillow -q

echo "   ✅ Python packages installed"

# 8. Install Ollama for Android
echo "[8/8] 🤖 Installing Ollama (local LLM)..."
if command -v ollama &>/dev/null; then
    echo "   ✅ Ollama already installed"
else
    pkg install -y ollama 2>/dev/null || {
        echo "   ⚠  Could not install Ollama via pkg"
        echo "      Try: pkg install ollama"
        echo "      Or use a remote API endpoint"
    }
fi

# ---- Configuration ----------------------------------------------------------
echo ""
echo "   Configuring agent..."
if [ ! -f "$AGENT_DIR/config.json" ]; then
    cat > "$AGENT_DIR/config.json" <<'CONFIGEOF'
{
    "llm": {
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model": "qwen2.5:1.5b",
        "temperature": 0.7
    },
    "telegram": {
        "bot_token": "",
        "allowed_chat_ids": [],
        "enabled": false
    },
    "web": {
        "port": 8765,
        "host": "0.0.0.0"
    },
    "username": "Abhinav"
}
CONFIGEOF
    echo "   ⚠  Edit config.json to set your Ollama model & Telegram token."
fi

# ---- Create launcher -------------------------------------------------------
cat > "$PREFIX/bin/agent-beast" << 'EOF'
#!/bin/bash
cd "$HOME/agent_beast"
source venv/bin/activate 2>/dev/null
python main.py "$@"
EOF
chmod +x "$PREFIX/bin/agent-beast"

cat > "$AGENT_DIR/start_phone.sh" << 'EOF'
#!/bin/bash
cd "$HOME/agent_beast"
source venv/bin/activate 2>/dev/null

# Start Ollama if available
if command -v ollama &>/dev/null; then
    ollama serve > /dev/null 2>&1 &
    sleep 2
    ollama pull qwen2.5:1.5b 2>/dev/null || true
fi

# Start web UI
echo "🚀 Starting AI Agent Beast v3.0..."
echo "🌐 Web UI:    http://localhost:8765"
echo "📡 API:       http://localhost:8000"
echo "📱 Telegram:  Enabled if configured"
echo "🧠 Auto-Memory: Active"
echo ""
python main.py --web --host 0.0.0.0 --port 8765
EOF
chmod +x "$AGENT_DIR/start_phone.sh"

# Summary
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   ✅  PHONE DEPLOYMENT COMPLETE!         ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "   📂 Agent location: $AGENT_DIR"
echo "   🧠 Auto-evolving memory: Active"
echo "   🤖 39 Android ADB tools: Ready"
echo "   📱 Telegram bot: Configurable"
echo ""
echo "   🚀 Quick start:"
echo "      agent-beast --web"
echo ""
echo "   🚀 Full system:"
echo "      cd $AGENT_DIR && bash start_phone.sh"
echo ""
echo "   🌐 Web UI: http://localhost:8765"
echo ""
echo "   💡 For external internet access (Live HTTPS):"
echo "      npx localtunnel --port 8765"
echo "      # or install ngrok: pkg install ngrok"
echo ""
