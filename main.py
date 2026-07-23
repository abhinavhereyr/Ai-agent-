#!/usr/bin/env python3
"""AI Agent Beast - Merged from Desktop Agent + OpenHermes + NEO-AGENT.

A free, unlimited, fully local AI agent with:
  - Desktop automation (mouse, keyboard, screenshot)
  - Android device control (via ADB)
  - Voice control (speech-to-text, text-to-speech)
  - Web search & scraping (DuckDuckGo, free)
  - File operations (read, write, edit)
  - Code execution (Python sandbox, shell)
  - Web UI dashboard (FastAPI)
  - REST API for remote access
  - Health checks & self-repair
  - Autonomous mode
  - Persistent memory (SQLite)

Usage:
  python3 main.py                    # Interactive CLI
  python3 main.py --web              # Web UI server (default port 8765)
  python3 main.py --voice            # Voice interaction loop
  python3 main.py --server           # REST API server (port 8000)
  python3 main.py --auto             # Autonomous mode
  python3 main.py --health           # Run health check and exit
  python3 main.py --heal             # Run self-repair and exit
  python3 main.py --interactive      # Interactive chat-like CLI
  python3 main.py --all              # Run everything (web + engine)
"""
import argparse
import cmd
import os
import shutil
import subprocess
import sys
import textwrap
import time
import threading

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import config
from core.engine import engine
from core.llm import is_running, list_models, chat, pull_model
from core.self_improve import health, healer, improver
from memory.store import memory
from modules.automation import automation
from modules.android import android
from modules.voice import stt, tts
from modules.tool_registry import registry


# ===========================================================================
# Interactive Shell
# ===========================================================================

class AgentShell(cmd.Cmd):
    """Interactive command-line interface for the agent."""

    intro = textwrap.dedent("""
    ╔══════════════════════════════════════════╗
    ║       AI AGENT BEAST - v2.0             ║
    ║  Free  •  Unlimited  •  Private          ║
    ║  Desktop + Android + Web + Code          ║
    ╚══════════════════════════════════════════╝
    Type 'help' for commands, 'exit' to quit.
    """)
    prompt = "beast> "

    def __init__(self):
        super().__init__()
        engine.start()
        self._check_ollama()

    def _check_ollama(self):
        if not is_running():
            print("⚠️  Ollama is not running. Starting...")
            subprocess.Popen(["ollama", "serve"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)

    def default(self, line):
        """Process any input through the engine."""
        response = engine.process_text(line)
        if response:
            print(response)

    def do_screenshot(self, arg):
        """Take a screenshot"""
        result = automation.screenshot()
        print(f"📸 Saved to {result.get('path', '?')}")

    def do_search(self, arg):
        """Search the web: search <query>"""
        if not arg:
            print("Usage: search <query>")
            return
        from modules.web_tools import web_search
        print(web_search(arg))

    def do_health(self, arg):
        """Run health check"""
        print(health.summary())

    def do_heal(self, arg):
        """Run self-repair"""
        fixes = healer.heal_all()
        if fixes:
            for f in fixes:
                print(f"  🔧 {f}")
        else:
            print("✅ Everything looks good!")

    def do_tools(self, arg):
        """List all available tools"""
        tools = registry.list_tools()
        cats = {}
        for t in tools:
            cats.setdefault(t["category"], []).append(t["name"])
        print("Available tools:")
        for cat, names in sorted(cats.items()):
            print(f"  📦 {cat}: {', '.join(names)}")

    def do_python(self, arg):
        """Run Python code: python <code>"""
        if not arg:
            print("Usage: python <code>")
            return
        from modules.code_tools import run_python
        print(run_python(arg))

    def do_shell(self, arg):
        """Run shell command: shell <command>"""
        if not arg:
            print("Usage: shell <command>")
            return
        from modules.code_tools import run_shell
        print(run_shell(arg))

    def do_memory(self, arg):
        """Show recent memory"""
        msgs = memory.get_history(limit=10)
        for m in msgs:
            role = m.get("role", "?")
            content = m.get("content", "")[:100]
            print(f"  [{role}] {content}")

    def do_web(self, arg):
        """Start web UI in background"""
        from web.app import run_in_background
        run_in_background()
        print("🌐 Web UI started at http://localhost:8765")

    def do_exit(self, arg):
        """Exit the agent"""
        engine.stop()
        print("Goodbye!")
        return True

    def do_EOF(self, arg):
        return self.do_exit(arg)

    def emptyline(self):
        pass


# ===========================================================================
# Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="AI Agent Beast - Free, unlimited, local AI agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
Examples:
  python3 main.py                    Interactive CLI shell
  python3 main.py --web              Start web UI dashboard
  python3 main.py --server           Start REST API server
  python3 main.py --voice            Voice interaction loop
  python3 main.py --auto             Autonomous mode (5 iterations)
  python3 main.py --health           Quick health check
  python3 main.py --interactive      Chat-style interface
  python3 main.py --web --voice      Run web + voice together
        """))

    parser.add_argument("--web", action="store_true", help="Start web UI")
    parser.add_argument("--voice", action="store_true", help="Voice interaction loop")
    parser.add_argument("--server", action="store_true", help="Start REST API server")
    parser.add_argument("--auto", type=int, nargs="?", const=5, help="Autonomous mode (iterations)")
    parser.add_argument("--health", action="store_true", help="Run health check and exit")
    parser.add_argument("--heal", action="store_true", help="Run self-repair and exit")
    parser.add_argument("--interactive", action="store_true", help="Interactive chat mode")
    parser.add_argument("--all", action="store_true", help="Run everything")
    parser.add_argument("--telegram", action="store_true", help="Start Telegram bot")
    parser.add_argument("--port", type=int, default=None, help="Web UI port")
    parser.add_argument("--host", type=str, default=None, help="Web UI host (default: 0.0.0.0)")

    args = parser.parse_args()

    # Single-shot modes
    if args.health:
        engine.start()
        print(health.summary())
        sys.exit(0)

    if args.heal:
        engine.start()
        fixes = healer.heal_all()
        for f in fixes:
            print(f"  🔧 {f}")
        if not fixes:
            print("✅ All systems healthy!")
        sys.exit(0)

    if args.auto:
        engine.start()
        engine.autonomous_loop(iterations=args.auto)
        return

    # Start engine
    engine.start()

    # Web UI
    if args.web or args.all:
        from web.app import run_in_background
        port = args.port or config.get("web", "port")
        host = args.host or "0.0.0.0"
        run_in_background(host=host, port=port)
        print(f"🌐 Web UI at http://localhost:{port}")

    # REST API server
    if args.server or args.all:
        from web.api_server import start_api_server
        port = args.port or 8000
        host = args.host or "0.0.0.0"
        threading.Thread(target=start_api_server, args=(host, port), daemon=True).start()
        print(f"🔌 API server at http://localhost:{port}")

    # Telegram bot
    telegram_bot = None
    if args.telegram or (args.web or args.all):
        from modules.telegram_bot import TelegramBot
        telegram_bot = TelegramBot()
        telegram_bot.start()

    # Voice loop
    if args.voice or args.all:
        engine.voice_loop(wake_word=True)
        if telegram_bot:
            telegram_bot.stop()
        return

    # Daemon mode: if --web or --server given without interactive, keep alive
    if (args.web or args.server) and not args.interactive:
        print("🔄 Server mode. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            if telegram_bot:
                telegram_bot.stop()
            engine.stop()
            return

    # Interactive chat mode
    if args.interactive:
        print("Interactive chat mode. Type 'exit' to quit.")
        print("=" * 50)
        while True:
            try:
                user_input = input("you> ")
                if user_input.lower() in ("exit", "quit"):
                    break
                response = engine.process_text(user_input)
                if response:
                    print(f"agent> {response}")
            except (KeyboardInterrupt, EOFError):
                break
            except Exception as e:
                print(f"Error: {e}")
        return

    # Default: interactive shell
    shell = AgentShell()
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        engine.stop()


if __name__ == "__main__":
    main()
