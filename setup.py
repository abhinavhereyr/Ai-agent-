#!/usr/bin/env bash
""""
: ; # -*- mode: shell; -*-
# Setup script for Local AI Agent
# This is a hybrid Python/bash script - it works when run with bash
echo "========================================="
echo "  Local AI Agent - Setup"
echo "========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required"
    exit 1
fi
echo "✅ Python $(python3 --version 2>&1 | cut -d' ' -f2)"

# Install system dependencies
echo ""
echo "📦 Installing system dependencies..."
if command -v apt &> /dev/null; then
    sudo apt update -qq && sudo apt install -y -qq \
        python3-pip python3-dev python3-venv \
        espeak-ng \
        adb \
        wmctrl \
        xclip \
        ffmpeg \
        2>&1 | tail -3
    echo "✅ System packages installed"
elif command -v pacman &> /dev/null; then
    sudo pacman -Sy --noconfirm \
        python-pip espeak-ng android-tools wmctrl xclip ffmpeg \
        2>&1 | tail -3
elif command -v dnf &> /dev/null; then
    sudo dnf install -y \
        python3-pip espeak-ng android-tools wmctrl xclip ffmpeg \
        2>&1 | tail -3
else
    echo "⚠️  Could not install system packages. Please install manually:"
    echo "   python3-pip, espeak-ng, adb, wmctrl, xclip, ffmpeg"
fi

# Install Python packages
echo ""
echo "📦 Installing Python packages..."
pip3 install --quiet --upgrade pip 2>&1 | tail -1
pip3 install --quiet \
    pyautogui \
    pynput \
    pyperclip \
    sounddevice \
    soundfile \
    numpy \
    scipy \
    pillow \
    opencv-python-headless \
    fastapi \
    uvicorn \
    websockets \
    psutil \
    2>&1 | tail -3
echo "✅ Python packages installed"

# Optional: STT with transformers (Whisper)
echo ""
echo "📦 Installing speech recognition (Whisper)..."
pip3 install --quiet transformers sentencepiece 2>&1 | tail -3
echo "✅ Speech recognition packages installed"

# Check Ollama
echo ""
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is installed"
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama server is running"
        # Check for models
        MODELS=$(ollama list 2>/dev/null | tail -n +2 | head -5)
        if [ -z "$MODELS" ]; then
            echo ""
            echo "📥 No LLM models found. Pulling llama3.2 (2GB)..."
            echo "   This will take a while on first run."
            echo ""
            ollama pull llama3.2 2>&1
            echo "✅ Model pulled!"
        else
            echo "✅ Available models:"
            echo "$MODELS"
        fi
    else
        echo "⚠️  Ollama server not running."
        echo "   Start it with: ollama serve"
        echo "   Then run: ollama pull llama3.2"
    fi
else
    echo "📥 Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "✅ Ollama installed!"
    echo ""
    echo "📥 Pulling default model (llama3.2)..."
    ollama serve &
    sleep 2
    ollama pull llama3.2
fi

# Setup ADB
echo ""
if command -v adb &> /dev/null; then
    echo "✅ ADB installed"
    echo "   To connect Android: enable USB debugging and run: adb devices"
else
    echo "⚠️  ADB not found. Install: sudo apt install adb"
fi

# Create directories
echo ""
echo "📁 Creating directories..."
mkdir -p ~/agent_screenshots
mkdir -p ~/.agent_data
echo "✅ Directories created"

# Done
echo ""
echo "========================================="
echo "  ✅ Setup Complete!"
echo "========================================="
echo ""
echo "Start the agent:"
echo "  cd agent && python3 main.py"
echo ""
echo "Or with web UI:"
echo "  python3 main.py --web"
echo ""
echo "Or voice mode:"
echo "  python3 main.py --voice"
echo ""
echo "Web UI will be at: http://localhost:8765"
echo ""
exit 0
""""
# Python entry point for "python3 setup.py"
import subprocess
import sys

def run_setup():
    """Run the setup process."""
    # Re-run self with bash if invoked via python
    import os
    script = os.path.abspath(__file__)
    os.execvp("bash", ["bash", script])

if __name__ == "__main__":
    run_setup()
