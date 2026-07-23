#!/bin/bash
"""":"
# ===========================================================================
# Deploy AI Agent Beast on any Linux/Android (Termux) device
# ===========================================================================
# Usage: curl -sL https://raw.githubusercontent.com/your/repo/main/deploy.sh | bash
#
# Or run locally:
#   chmod +x deploy.sh && ./deploy.sh
#
# This script installs everything needed to run the agent on:
#   - Linux (Ubuntu/Debian)
#   - Android (via Termux)
#   - Any POSIX system with Python 3.8+
# ===========================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║     AI AGENT BEAST - INSTALLER          ║"
echo "║  Free  •  Unlimited  •  Private          ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# Detect environment
IS_TERMUX=false
IS_ROOT=false
if [ -d "/data/data/com.termux" ] || [ -n "$TERMUX_VERSION" ]; then
    IS_TERMUX=true
    echo -e "${YELLOW}📱 Detected Termux (Android)${NC}"
fi

if [ "$(id -u)" = "0" ]; then
    IS_ROOT=true
fi

# 1. Install system dependencies
echo -e "\n${BLUE}[1/6] Installing system dependencies...${NC}"

if $IS_TERMUX; then
    pkg update -y
    pkg install -y python python-pip git espeak alsa-utils
elif command -v apt-get &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv espeak adb wget curl unzip
elif command -v pacman &>/dev/null; then
    pacman -Sy --noconfirm python python-pip espeak adb wget
else
    echo -e "${YELLOW}⚠️  Unknown package manager. Installing Python deps only.${NC}"
fi

# 2. Clone or copy agent files
echo -e "\n${BLUE}[2/6] Setting up agent files...${NC}"

AGENT_DIR="$HOME/agent_beast"
if [ ! -d "$AGENT_DIR" ]; then
    mkdir -p "$AGENT_DIR"
fi

# If running from within the repo, copy files
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/main.py" ]; then
    echo "📂 Copying files from $SCRIPT_DIR..."
    cp -r "$SCRIPT_DIR"/* "$AGENT_DIR/" 2>/dev/null || cp -r "$SCRIPT_DIR"/. "$AGENT_DIR/"
else
    echo "📥 Need to get source files..."
    # Try to clone from repo
    if command -v git &>/dev/null; then
        git clone https://github.com/your/agent-beast.git "$AGENT_DIR/tmp" 2>/dev/null || true
        if [ -d "$AGENT_DIR/tmp" ]; then
            cp -r "$AGENT_DIR/tmp"/* "$AGENT_DIR/"
            rm -rf "$AGENT_DIR/tmp"
        fi
    fi
fi

cd "$AGENT_DIR"

# 3. Create virtual environment
echo -e "\n${BLUE}[3/6] Creating Python virtual environment...${NC}"
python3 -m venv venv 2>/dev/null || python -m venv venv 2>/dev/null || {
    echo -e "${YELLOW}⚠️  venv not available, installing globally${NC}"
    VENV_DIR=""
}

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    VENV_DIR="venv"
    echo "✅ Virtual environment created"
fi

PYTHON_BIN="python3"
if [ -f "venv/bin/python" ]; then
    PYTHON_BIN="venv/bin/python"
fi

# 4. Install Python dependencies
echo -e "\n${BLUE}[4/6] Installing Python packages...${NC}"

PACKAGES=(
    "fastapi"
    "uvicorn[standard]"
    "pyautogui"
    "pillow"
    "pyperclip"
    "requests"
    "httpx"
    "beautifulsoup4"
    "duckduckgo-search"
    "numpy"
    "sounddevice"
)

# Install transformers separately (big download)
echo "   Installing core packages..."
$PYTHON_BIN -m pip install -q "${PACKAGES[@]}" 2>/dev/null

echo "   Installing ML packages (this may take a while)..."
$PYTHON_BIN -m pip install -q "transformers" "torch" --extra-index-url https://download.pytorch.org/whl/cpu 2>/dev/null || true

# Install sentence-transformers for semantic memory
$PYTHON_BIN -m pip install -q "sentence-transformers" 2>/dev/null || true

echo "✅ Python dependencies installed"

# 5. Install Ollama (for LLM)
echo -e "\n${BLUE}[5/6] Setting up Ollama (local LLM)...${NC}"

if command -v ollama &>/dev/null; then
    echo "✅ Ollama already installed"
else
    if $IS_TERMUX; then
        echo "📱 Installing Ollama for Termux..."
        pkg install -y ollama 2>/dev/null || echo "⚠️  Install ollama manually: pkg install ollama"
    else
        echo "📥 Installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null || {
            echo -e "${YELLOW}⚠️  Could not install Ollama automatically${NC}"
            echo "   Install manually from https://ollama.com"
        }
    fi
fi

# Start Ollama if not running
if command -v ollama &>/dev/null; then
    if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "🔄 Starting Ollama server..."
        ollama serve &
        sleep 3
    fi
    # Pull tiny model for fast responses
    echo "📦 Pulling light model (qwen2.5:1.5b)..."
    ollama pull qwen2.5:1.5b 2>/dev/null || true
fi

# 6. Create launcher script
echo -e "\n${BLUE}[6/6] Creating launcher...${NC}"

cat > "$PREFIX/bin/agent-beast" 2>/dev/null || cat > "$AGENT_DIR/agent-beast.sh" << 'LAUNCHER'
#!/bin/bash
cd "$HOME/agent_beast"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi
python3 main.py "$@"
LAUNCHER

if [ -f "$PREFIX/bin/agent-beast" ]; then
    chmod +x "$PREFIX/bin/agent-beast"
    echo "✅ Launcher installed: agent-beast"
else
    chmod +x "$AGENT_DIR/agent-beast.sh"
    echo "✅ Launcher script at $AGENT_DIR/agent-beast.sh"
fi

# Summary
echo -e "\n${GREEN}"
echo "╔══════════════════════════════════════════╗"
echo "║        INSTALLATION COMPLETE!            ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo "📂 Agent location: $AGENT_DIR"
echo ""
echo "🚀 Quick start:"
echo "   cd $AGENT_DIR"
if [ -n "$VENV_DIR" ]; then
    echo "   source $VENV_DIR/bin/activate"
fi
echo ""
echo "   # Interactive mode:"
echo "   python3 main.py"
echo ""
echo "   # Web UI (access from browser):"
echo "   python3 main.py --web"
echo ""
echo "   # REST API server:"
echo "   python3 main.py --server"
echo ""
echo "   # Voice control:"
echo "   python3 main.py --voice"
echo ""
echo "   # Everything at once:"
echo "   python3 main.py --all"
echo ""
echo "🌐 Web UI: http://localhost:8765"
echo "🔌 API:     http://localhost:8000"
echo "📖 Docs:    http://localhost:8765/docs"
echo ""

# Ask to start
echo -e "${BLUE}Start the agent now? [Y/n]${NC}"
read -r response
if [ "$response" != "n" ] && [ "$response" != "N" ]; then
    cd "$AGENT_DIR"
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi
    echo "🚀 Starting agent in web mode..."
    python3 main.py --web --server
fi

""
