# AI Agent Beast — Product Requirements Document

> **Version:** 3.0  
> **Status:** Active Development  
> **Architecture:** 100% Local, Zero-Cloud, Zero-API-Keys  

---

## 1. Executive Summary

AI Agent Beast is a **fully-local, zero-cloud-dependency AI agent ecosystem** that integrates desktop automation, Android device control, web search/scraping, voice interaction, code execution, and self-improvement capabilities into a single unified system. Inspired by Base44's universal access design, PocketStrike-AI's Android exploitation patterns, and a self-healing local agent architecture, the system runs entirely via Ollama (qwen2.5, llama3.2, mistral, etc.) — no API keys, no cloud dependency.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        main.py                               │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┐  │
│  │ CLI  │ Web  │Voice │Server│ Auto │Inter │  All │Health│  │
│  │      │ UI   │      │ REST │Tasks │active│ Modes│ Check│  │
│  └──┬───┴──┬───┴──┬───┴──┬───┴──┬───┴──┬───┴──┬───┴──┬───┘  │
│     │      │      │      │      │      │      │      │       │
└─────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼───────┘
      │      │      │      │      │      │      │      │
┌─────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴───────┐
│                        core/                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ engine.py│  │  llm.py  │  │ config.py│  │self_improve.py│  │
│  │Orchestr. │  │Ollama API│  │ Deep JSON│  │ Auto-heal &  │  │
│  │ + Parser │  │ Streaming│  │  Config  │  │ Self-Develop │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│                      modules/                                 │
│  ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌──────┐ │
│  │Automat.││Android ││ Voice  ││WebTools││CodeTool││File  │ │
│  │Desktop ││ ADB +  ││STT/TTS ││DuckDuck││Sandbox ││Ops   │ │
│  │Control ││Advanced││ Loop   ││Go+BS4  ││+Shell  ││      │ │
│  └────────┘└────────┘└────────┘└────────┘└────────┘└──────┘ │
│  ┌────────┐┌────────┐┌────────┐┌────────┐┌────────────────┐ │
│  │Utility ││Browser ││Telegram││Self-   ││  Tool Registry │ │
│  │Tools   ││Control ││  Bot   ││Developer││  50+ Tools    │ │
│  └────────┘└────────┘└────────┘└────────┘└────────────────┘ │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│         web/                    memory/        tasks/         │
│  ┌──────────┐              ┌──────────┐   ┌──────────┐      │
│  │  app.py  │              │ store.py │   │scheduler │      │
│  │  + API   │              │  SQLite  │   │   .py    │      │
│  │ Dashboard│              │   WAL    │   │ Cron-ish │      │
│  └──────────┘              └──────────┘   └──────────┘      │
└──────────────────────────────────────────────────────────────┘
```

### 2.1 Unified Launch System (`main.py`)

| Flag | Mode | Description |
|------|------|-------------|
| (none) | CLI Shell | Interactive shell with tab-completion |
| `--web` | Web Dashboard | Glassmorphism dark UI on port **8765** |
| `--voice` | Voice Loop | Hands-free STT/TTS with wake word |
| `--server` | REST API | JSON API on port **8000** |
| `--auto` | Auto Tasks | Self-directed task execution |
| `--interactive` | Chat CLI | Memory-aware interactive chat |
| `--all` | Full System | Web UI + Core Engine + Scheduler |
| `--health` | Diagnostics | 14 system health checks |
| `--heal` | Auto-Repair | Fix missing dependencies/services |

### 2.2 Core Engine (`core/`)

- **engine.py** — Threaded, non-blocking orchestrator with `ActionRegistry` + `process_text()` NLP parser. Routes user input to appropriate tool.
- **llm.py** — Ollama connector (`http://localhost:11434`) supporting streaming, model pulling, auto-fallbacks, and tool-calling JSON schemas.
- **config.py** — Deep-merge JSON configuration stored at `~/.agent_config.json`. Supports profile customization (default: "Abhinav").
- **self_improve.py** — Self-repair system with 14 health checks, auto-healing for missing packages/services, and self-development pipeline.

### 2.3 Tool Registry & Modules (50+ Tools)

#### A. Desktop Automation (`modules/automation.py`)
Mouse movement, clicks, drags, scrolls; keyboard typing, hotkeys; screenshots; clipboard; window management.

#### B. Android & Mobile (`modules/android.py`)
ADB integration: device discovery, shell commands, touch/swipe/text input, app management, screen capture, plus **advanced tools** (SMS, camera, GPS, calls, clipboard, Wi-Fi scanning, ARP spoofing, UI layout dump, face detection, sensor reading, screen recording).

#### C. Voice Engine (`modules/voice.py`)
Local Whisper STT with wake-word detection ("hey agent"). Async TTS via `espeak-ng`. Continuous listening with silence detection.

#### D. Web Tools (`modules/web_tools.py`)
Zero-API DuckDuckGo search & news. BeautifulSoup page scraping (sanitized, 10k char limit).

#### E. Code Sandbox (`modules/code_tools.py`)
AST-based Python sandbox blocking dangerous operations. Shell executor with 30s timeout and destructive command protection.

#### F. File Tools (`modules/file_tools.py`)
Read, write, edit, list, delete, grep, download files.

#### G. Utility Tools (`modules/utility_tools.py`)
Weather (`wttr.in`), math calculator, CPU/RAM metrics, process management, network speed tests, random generation, translation, QR codes, Base64.

#### H. Self-Developer (`modules/self_developer.py`)
NL-to-code pipeline: prompt → code generation → AST linting → dynamic registration → git commit → GitHub PR.

#### I. Browser Control (`modules/browser.py`)
Open URLs, search, detect available browsers.

#### J. Telegram Bot (`modules/telegram_bot.py`)
Remote control via Telegram messages. Execute tools, get responses, manage the agent.

### 2.4 Persistent Memory (`memory/store.py`)
SQLite with WAL mode storing conversations, facts, tasks, and commands. **Auto-evolving memory** via background reflection thread that updates `user.md`, `memory.md`, and `agent.md`.

### 2.5 Web Dashboard (`web/app.py`)
Dark glassmorphism-themed dashboard with:

| Tab | Feature |
|-----|---------|
| 💬 Chat | WebSocket real-time chat |
| 🔧 Tools | Searchable 50+ tool list |
| 🌤️ Weather | Live weather & forecast |
| 🧮 Utilities | Calculator, random gen, QR, Base64 |
| 📁 Files | File browser & editor |
| 🌐 Web | Search & scrape UI |
| 📝 Notes | Persistent markdown notes |
| ⚙️ System | CPU/RAM/process monitoring |
| 🤖 Self-Develop | Build tools from natural language |

### 2.6 Access Control (Base44-style)
Multi-user authentication via:
- Admin-generated API tokens
- Session-based auth for Web UI
- Role-based access control (admin, user, readonly)
- Token management dashboard

---

## 3. Security Model

### 3.1 Code Sandbox
- AST-parsed Python execution
- Dangerous builtins stripped: `exec`, `eval`, `__import__`, `open`
- Module blocking: `os`, `subprocess`, `shutil`, `socket`, `ctypes`
- Destructive pattern detection (rm -rf, mkfs, dd, etc.)
- 30s execution timeout

### 3.2 Shell Safety
- Destructive command protection
- Timeout enforcement
- No interactive shell execution

### 3.3 File System Safe Zones
- Read access: project root + workspace
- Write access: workspace only (project root read-only by policy)
- Workspace in Android internal storage or `~/agent_workspace`

### 3.4 Network Safety
- No beaconing / phone-home
- All calls are user-initiated
- Zero cloud dependencies — all APIs are local or use free public endpoints

---

## 4. Self-Improvement Pipeline

1. **User describes feature in natural language**
2. LLM generates Python module code
3. AST syntax verification & linting
4. Dynamic module loading & ToolRegistry registration
5. Auto-staging git commit
6. GitHub PR creation via `gh` CLI

### Auto-Evolving Memory
After each conversation turn, a background thread:
1. Reviews recent messages (last 4)
2. Extracts new user facts (name, preferences, skills)
3. Updates persistent `user.md`, `memory.md`, `agent.md`
4. Merges with existing content (no overwrites unless changed)

---

## 5. Deployment

### Requirements
- **OS:** Linux (Ubuntu/Debian, Arch), Termux (Android), macOS
- **Python:** 3.9+
- **LLM:** Ollama with any model (qwen2.5, llama3.2, mistral, etc.)
- **Optional:** ADB (Android), espeak-ng (voice), transformers (Whisper)

### Quick Start
```bash
chmod +x deploy.sh && ./deploy.sh
# Or manually:
pip install -r requirements.txt
python3 main.py --web    # Web UI on :8765
python3 main.py --server # API on :8000
python3 main.py          # Interactive CLI
```

---

## 6. Tool Inventory (50+ Tools)

### Desktop Automation
`mouse_move`, `mouse_click`, `mouse_drag`, `mouse_scroll`, `keyboard_type`, `keyboard_hotkey`, `keyboard_press`, `keyboard_write`, `screenshot`, `screenshot_region`, `get_pixel`, `locate_on_screen`, `clipboard_get`, `clipboard_set`, `window_list`, `window_activate`, `window_resize`, `window_move`

### Android (ADB)
`devices`, `shell`, `tap`, `swipe`, `text`, `keyevent`, `screenshot`, `screenrecord`, `list_packages`, `install`, `uninstall`, `launch_app`, `force_stop`, `push`, `pull`, `send_sms`, `make_call`, `get_location`, `take_photo`, `get_clipboard`, `set_clipboard`, `scan_wifi`, `dump_ui`, `detect_faces`, `read_sensors`, `list_contacts`, `audit_sms`, `set_brightness`, `set_volume`, `send_notification`, `vibrate`, `control_system`

### Web
`web_search`, `web_search_news`, `web_scrape`, `web_fetch_json`

### Code
`run_python`, `run_shell`, `analyze_code`, `format_code`

### File
`file_read`, `file_write`, `file_edit`, `file_list`, `file_delete`, `file_grep`, `file_download`, `file_search`

### Utility
`weather_get`, `weather_detailed`, `calculate`, `system_info`, `process_list`, `process_kill`, `network_info`, `network_speed_test`, `random_password`, `random_number`, `random_uuid`, `translate_text`, `note_add`, `note_get`, `note_list`, `qr_generate`, `encode_base64`, `text_count`

### Self-Developer
`build_from_prompt`, `generate_module_from_prompt`, `create_git_commit`, `create_github_pr`, `auto_register_module`, `analyze_code_quality`, `health_check`, `auto_heal`

---

## 7. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-Q1 | Initial CLI agent with basic automation |
| 2.0 | 2025-Q3 | Web dashboard, LLM integration, tool registry |
| 3.0 | 2026-Q3 | Android advanced tools, auto-evolving memory, Telegram bot, access control, 50+ tools |
