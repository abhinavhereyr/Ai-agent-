# 🤖 AI Agent Beast

<div align="center">

**A free, unlimited, fully local AI agent for desktop automation, Android control, web interaction, code execution, and more.**

[![GitHub](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-brightgreen.svg)]()
[![Ollama](https://img.shields.io/badge/ollama-powered-8A2BE2.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)]()

<p align="center">
  ⚡ Desktop Automation &nbsp;•&nbsp; 📱 Android Control &nbsp;•&nbsp; 🎤 Voice Commands<br>
  🌐 Web Search & Scraping &nbsp;•&nbsp; 💻 Code Execution &nbsp;•&nbsp; 🧠 Persistent Memory<br>
  🖥️ Web Dashboard &nbsp;•&nbsp; 🔌 REST API &nbsp;•&nbsp; 🤖 Autonomous Mode
</p>

</div>

---

## ✨ Features

### 🖥️ Desktop Automation
- **Mouse control** — move, click, drag, scroll with pixel precision
- **Keyboard control** — type text, press hotkeys, clipboard operations
- **Screen capture** — screenshots with multiple fallback methods
- **Window management** — list, focus, and control application windows
- **App launcher** — open applications and URLs instantly

### 📱 Android Device Control
- **ADB integration** — connect and control Android devices
- **Screen mirroring** — view device screen on desktop
- **Tap & swipe** — interact with device touchscreen
- **App management** — install, launch, and manage apps
- **File transfer** — push and pull files from device

### 🎤 Voice Control
- **Speech-to-text** — voice commands using offline recognition
- **Text-to-speech** — natural voice responses
- **Wake word detection** — hands-free activation
- **Continuous listening** — always-on voice interaction

### 🌐 Web Tools
- **Web search** — DuckDuckGo search (free, no API key)
- **Web scraping** — extract content from any webpage
- **News search** — latest news from around the web
- **URL shortener** — create short links instantly
- **Weather** — current conditions and forecasts

### 💻 Code Execution
- **Python sandbox** — safe, isolated Python execution
- **Shell commands** — run system commands securely
- **Code analysis** — lint and analyze Python code
- **Base64 encode/decode** — quick encoding utilities

### 🗄️ File Operations
- **Read, write, edit** — full file manipulation
- **Directory listing** — browse file system
- **Search & grep** — find text in files
- **File download** — fetch files from URLs

### 🧠 Persistent Memory
- **SQLite-backed** — survives restarts
- **Fact storage** — remember things across sessions
- **Conversation history** — context-aware responses
- **Note system** — quick save/recall notes

### 🖥️ Web Dashboard
- **Real-time chat** — interact with the AI via browser
- **Tool browser** — discover all available capabilities
- **File manager** — browse and edit files from browser
- **Health monitor** — system status at a glance
- **Mobile responsive** — works on phones and tablets

### 🔌 REST API
- **Full API** — all capabilities accessible via HTTP
- **JSON responses** — machine-friendly output
- **Session management** — multi-user support
- **WebSocket** — real-time streaming responses

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.8+ required
python3 --version

# Install Ollama (for local LLM)
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model (1.5B is fast, 7B is smarter)
ollama pull qwen2.5:1.5b
# or: ollama pull qwen2.5:7b
```

### Installation

```bash
# Clone or navigate to the project
cd AI-Agent-Beast/

# Install dependencies
pip install -r requirements.txt

# Run the agent
python3 main.py
```

### Running Modes

```bash
# Interactive CLI shell (default)
python3 main.py

# Web Dashboard (open browser to http://localhost:8765)
python3 main.py --web

# Chat-style interface
python3 main.py --interactive

# Voice control mode
python3 main.py --voice

# REST API server (port 8000)
python3 main.py --server

# Autonomous mode (5 iterations)
python3 main.py --auto

# Health check
python3 main.py --health

# Self-repair
python3 main.py --heal

# Everything at once
python3 main.py --all
```

### 🌐 Public Access

To access your agent from anywhere, start the web server and create a tunnel:

```bash
# 1. Start the web UI
python3 main.py --web

# 2. Create a public tunnel (in another terminal)
./keep_alive.sh --daemon

# 3. Get your public URL
./keep_alive.sh --url
```

---

## 📋 Usage Examples

### Desktop Control
```
beast> screenshot
beast> mouse position
beast> open firefox
beast> type Hello World
```

### Web Search & Information
```
beast> search latest AI news
beast> weather London
beast> calc sqrt(144) + 25
beast> translate Hello to fr
```

### System Management
```
beast> system info
beast> network info
beast> process list
beast> health
```

### File Operations
```
beast> list files in /home
beast> read /path/to/file.txt
beast> save note my_idea: build something cool
beast> show my_idea
```

### Utilities
```
beast> random password 20
beast> shorten https://example.com
beast> qr https://my-site.com
beast> encode hello in base64
```

---

## 📡 API Reference

### Chat
```bash
POST /api/chat
{
    "message": "Hello, what can you do?"
}
```

### Tools
```bash
GET  /api/tools          # List all tools
GET  /api/tools/:name     # Get tool details
POST /api/tools/:name/call
{
    "params": {"arg1": "value"}
}
```

### System
```bash
GET  /api/health          # Health check
GET  /api/status          # Agent status
POST /api/heal            # Self-repair
```

### WebSocket
```
ws://host:8765/ws
```
Send JSON messages and receive real-time responses.

---

## 🏗️ Architecture

```
agent/
├── main.py              # Entry point & CLI shell
├── core/
│   ├── engine.py        # Main agent engine & action router
│   ├── config.py        # Configuration manager
│   ├── llm.py           # Ollama LLM integration
│   └── self_improve.py  # Health checks & auto-repair
├── modules/
│   ├── automation.py    # Desktop automation (mouse, keyboard, screen)
│   ├── android.py       # Android device control (ADB)
│   ├── code_tools.py    # Python sandbox & shell execution
│   ├── file_tools.py    # File read/write/edit/search
│   ├── web_tools.py     # Web search & scraping (DuckDuckGo)
│   ├── utility_tools.py # Weather, calc, system info, notes, etc.
│   ├── voice.py         # Speech-to-text & text-to-speech
│   ├── browser.py       # Browser automation
│   └── tool_registry.py # Tool discovery & registration
├── memory/
│   └── store.py         # SQLite persistent memory
├── web/
│   ├── app.py           # FastAPI web dashboard
│   └── api_server.py    # REST API server
├── tasks/
│   └── scheduler.py     # Background task scheduler
├── keep_alive.sh        # Auto-reconnecting public tunnel
├── README.md            # This file
└── requirements.txt     # Python dependencies
```

---

## 🧰 Tech Stack

| Component | Technology |
|-----------|-----------|
| **Language** | Python 3.8+ |
| **LLM Runtime** | Ollama (local) |
| **Models** | Qwen 2.5, TinyLlama, Llama 3+ |
| **Web Framework** | FastAPI + Uvicorn |
| **Database** | SQLite (persistent memory) |
| **Desktop Automation** | PyAutoGUI, MSS, PIL |
| **Web Scraping** | BeautifulSoup, Requests |
| **Search** | DuckDuckGo (free, no API key) |
| **Voice** | SpeechRecognition, pyttsx3 |
| **Tunnel** | localhost.run (free SSH tunnel) |
| **Android** | ADB (Android Debug Bridge) |

---

## 🔧 Configuration

Edit `~/.agent_config.json`:

```json
{
  "llm": {
    "model": "qwen2.5:1.5b",
    "ollama_host": "http://localhost:11434",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "memory": {
    "db_path": "~/.agent_memory.db",
    "max_history": 100
  },
  "automation": {
    "screenshot_dir": "~/screenshots",
    "click_duration": 0.2
  }
}
```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is **free and open source**. You can use, modify, and distribute it freely.

Built with ❤️ for the open-source community.

---

## 🙏 Acknowledgments

- [Ollama](https://ollama.com/) — Local LLM runtime
- [FastAPI](https://fastapi.tiangolo.com/) — Web framework
- [PyAutoGUI](https://pyautogui.readthedocs.io/) — Desktop automation
- [DuckDuckGo Search](https://pypi.org/project/duckduckgo-search/) — Free web search
- [localhost.run](https://localhost.run/) — Free SSH tunneling
- All the open-source projects that made this possible
