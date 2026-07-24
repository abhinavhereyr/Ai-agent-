"""Main agent engine - orchestrates all modules with merged tool system."""
import datetime
import json
import re
import threading
import time
import traceback

from core.config import config
from core.llm import chat, generate, is_running, list_models, pull_model
from memory.store import memory
from memory.evolve import evolving_memory
from modules.automation import automation
from modules.android import android
from modules.voice import stt, tts

# Merged tool modules
from modules.tool_registry import registry
from modules.web_tools import web_search, web_scrape, web_fetch_json, web_search_news
from modules.file_tools import file_read, file_write, file_edit, file_list, file_delete, file_grep, file_download
from modules.code_tools import run_python, run_shell, analyze_code

# Utility tools (new expanded module)
from modules.utility_tools import (
    weather_get, weather_detailed, calculate, system_info_str, system_info,
    process_list, process_kill, network_info, network_speed_test,
    random_number, random_password, random_uuid,
    url_shorten, translate_text,
    note_add, note_get, note_list,
    qr_generate, text_count, encode_base64,
)

# Self-developer, self-repair, and profile modules
from modules.self_developer import (
    build_from_prompt, generate_module_from_prompt, create_git_commit, create_github_pr,
    auto_register_module, list_generated_modules, analyze_code_quality,
)
from core.self_improve import health, healer, improver, profile_manager

# Self-improvement
from core.self_improve import health, healer, improver


# ---------------------------------------------------------------------------
# Action Registry (kept for backward compatibility)
# ---------------------------------------------------------------------------

class ActionRegistry:
    """Registry of actions the agent can perform."""

    def __init__(self):
        self._actions = {}

    def register(self, name, handler, description=""):
        self._actions[name] = {"handler": handler, "description": description}

    def get(self, name):
        return self._actions.get(name)

    def list(self):
        return {k: v["description"] for k, v in self._actions.items()}

    def call(self, name, **kwargs):
        action = self.get(name)
        if not action:
            return {"error": f"Unknown action: {name}"}
        try:
            return action["handler"](**kwargs)
        except Exception as e:
            return {"error": str(e), "traceback": traceback.format_exc()}


# ---------------------------------------------------------------------------
# Agent Engine
# ---------------------------------------------------------------------------

class AgentEngine:
    """Main agent orchestrator with merged capabilities from all codebases."""

    def __init__(self):
        self.running = False
        self.start_time = None
        self.actions = ActionRegistry()
        self.session_id = f"session_{int(time.time())}"
        self._register_all_actions()
        self._register_ollama_tools()
        evolving_memory.start()

    def _register_all_actions(self):
        """Register ALL actions from all three merged codebases."""

        # --- Desktop Automation ---
        self.actions.register("click", lambda x, y, button="left": automation.mouse_click(x, y, button))
        self.actions.register("move_mouse", lambda x, y: automation.mouse_move(x, y))
        self.actions.register("type_text", lambda text: automation.keyboard_type(text))
        self.actions.register("press_key", lambda key: automation.keyboard_press(key))
        self.actions.register("hotkey", lambda keys: automation.keyboard_hotkey(*keys))
        self.actions.register("screenshot", lambda: automation.screenshot())
        self.actions.register("scroll", lambda amount: automation.mouse_scroll(amount))
        self.actions.register("run_command", lambda cmd, timeout=30: automation.run_command(cmd, timeout=timeout))
        self.actions.register("open_app", lambda app: automation.open_app(app))
        self.actions.register("open_url", lambda url: automation.open_url(url))
        self.actions.register("get_clipboard", lambda: {"text": automation.clipboard_get()})
        self.actions.register("set_clipboard", lambda text: automation.clipboard_set(text))
        self.actions.register("get_screen_size", lambda: automation.get_screen_size())
        self.actions.register("mouse_position", lambda: automation.mouse_position())
        self.actions.register("focus_window", lambda title: automation.focus_window(title))

        # --- Android ---
        self.actions.register("android_tap", lambda x, y: android.tap(x, y))
        self.actions.register("android_swipe", lambda x1, y1, x2, y2, d=300: android.swipe(x1, y1, x2, y2, d))
        self.actions.register("android_text", lambda text: android.text(text))
        self.actions.register("android_keyevent", lambda key: android.keyevent(key))
        self.actions.register("android_screenshot", lambda: android.pull_screenshot())
        self.actions.register("android_launch", lambda pkg, act=None: android.launch_app(pkg, act))
        self.actions.register("android_force_stop", lambda pkg: android.force_stop(pkg))
        self.actions.register("android_list_packages", lambda f=None: android.list_packages(f))
        self.actions.register("android_devices", lambda: android.devices())
        self.actions.register("android_wake", lambda: android.wake_up())

        # --- Voice ---
        self.actions.register("speak", lambda text: tts.say(text))
        self.actions.register("listen", lambda duration=5: {"text": stt.record_and_transcribe(duration=duration)})

        # --- Memory ---
        self.actions.register("remember", lambda key, value, category="general": memory.remember(key, value, category))
        self.actions.register("recall", lambda key: {"value": memory.recall(key)})
        self.actions.register("search_memory", lambda query: {"results": memory.search_facts(query)})
        self.actions.register("forget", lambda key: memory.forget(key))

        # --- Web Tools (merged from OpenHermes + NEO-AGENT) ---
        self.actions.register("web_search", lambda q, n=5: {"results": web_search(q, n)})
        self.actions.register("web_scrape", lambda url: {"content": web_scrape(url)})
        self.actions.register("web_fetch_json", lambda url: {"data": web_fetch_json(url)})
        self.actions.register("web_search_news", lambda q, n=5: {"results": web_search_news(q, n)})

        # --- File Tools (merged from OpenHermes) ---
        self.actions.register("file_read", lambda path: {"content": file_read(path)})
        self.actions.register("file_write", lambda path, content: {"result": file_write(path, content)})
        self.actions.register("file_edit", lambda path, old, new: {"result": file_edit(path, old, new)})
        self.actions.register("file_list", lambda path=".", pattern="*": {"listing": file_list(path, pattern)})
        self.actions.register("file_delete", lambda path: {"result": file_delete(path)})
        self.actions.register("file_grep", lambda path, pattern: {"matches": file_grep(path, pattern)})
        self.actions.register("file_download", lambda url, dest=None: {"result": file_download(url, dest)})

        # --- Code Tools (NEO-AGENT style) ---
        self.actions.register("run_python", lambda code: {"output": run_python(code)})
        self.actions.register("run_shell", lambda cmd, timeout=30: {"output": run_shell(cmd, timeout)})
        self.actions.register("analyze_code", lambda code: {"analysis": analyze_code(code)})

        # --- Health & Self-Improvement ---
        self.actions.register("health_check", lambda: health.json_report())
        self.actions.register("self_heal", lambda: {"fixes": healer.heal_all()})
        self.actions.register("self_improve_suggest", lambda: {"suggestions": improver.suggest_optimizations()})

        # --- Utility ---
        self.actions.register("datetime", lambda: {"now": datetime.datetime.now().isoformat()})
        self.actions.register("list_tools", lambda: {"tools": self.actions.list()})

        # --- New Utility Tools ---
        self.actions.register("weather", lambda loc="auto": {"weather": weather_get(loc)})
        self.actions.register("weather_detailed", lambda loc="auto": {"forecast": weather_detailed(loc)})
        self.actions.register("calculate", lambda expr: {"result": calculate(expr)})
        self.actions.register("system_info", lambda: {"info": system_info()})
        self.actions.register("system_status", lambda: {"status": system_info_str()})
        self.actions.register("process_list", lambda f=None: {"processes": process_list(f)})
        self.actions.register("process_kill", lambda pid: {"result": process_kill(pid)})
        self.actions.register("network_info", lambda: {"network": network_info()})
        self.actions.register("speed_test", lambda: {"speed": network_speed_test()})
        self.actions.register("random_number", lambda min_v=0, max_v=100: {"random": random_number(min_v, max_v)})
        self.actions.register("random_password", lambda length=16: {"password": random_password(length)})
        self.actions.register("random_uuid", lambda: {"uuid": random_uuid()})
        self.actions.register("url_shorten", lambda url: {"short_url": url_shorten(url)})
        self.actions.register("translate", lambda text, target="en", source="auto": {"translation": translate_text(text, target, source)})
        self.actions.register("note_add", lambda title, content="": {"result": note_add(title, content)})
        self.actions.register("note_get", lambda title: {"note": note_get(title)})
        self.actions.register("note_list", lambda: {"notes": note_list()})
        self.actions.register("qr_generate", lambda data: {"qr": qr_generate(data)})
        self.actions.register("text_count", lambda text: {"stats": text_count(text)})
        self.actions.register("encode_base64", lambda text, decode=False: {"result": encode_base64(text, decode)})

        # ===================================================================
        # Self-Developer, Self-Repair & Profile (Abhinav)
        # ===================================================================
        self.actions.register("build_feature", lambda prompt, module_name=None, create_pr=True: build_from_prompt(prompt, module_name, create_pr))
        self.actions.register("generate_code", lambda prompt, module_name=None: generate_module_from_prompt(prompt, module_name))
        self.actions.register("auto_register", lambda module_name: auto_register_module(module_name))
        self.actions.register("git_commit", lambda message, files=None: create_git_commit(message, files))
        self.actions.register("github_pr", lambda title, body=None: create_github_pr(title, body))
        self.actions.register("list_generated", lambda: {"modules": list_generated_modules()})
        self.actions.register("code_quality", lambda filepath: analyze_code_quality(filepath))
        self.actions.register("health_report", lambda: health.json_report())
        self.actions.register("self_heal", lambda: {"fixes": healer.heal_all()})
        self.actions.register("analyze_codebase", lambda: improver.analyze_overall())
        self.actions.register("profile_save", lambda name, data=None: profile_manager.save_profile(name, data))
        self.actions.register("profile_load", lambda name: profile_manager.load_profile(name))
        self.actions.register("profile_list", lambda: {"profiles": profile_manager.list_profiles()})

    def _register_ollama_tools(self):
        """Register ALL tools in the Ollama-compatible ToolRegistry."""
        # ===================================================================
        # Desktop
        # ===================================================================
        registry.register("click", "Click at screen coordinates", automation.mouse_click,
                         category="desktop", returns="dict")
        registry.register("screenshot", "Take a screenshot", lambda: automation.screenshot(),
                         category="desktop", returns="dict")
        registry.register("type_text", "Type text on keyboard", automation.keyboard_type,
                         category="desktop")
        registry.register("mouse_move", "Move mouse to coordinates", automation.mouse_move,
                         category="desktop")
        registry.register("mouse_position", "Get mouse cursor position", automation.mouse_position,
                         category="desktop", returns="dict")
        registry.register("scroll", "Scroll mouse wheel", automation.mouse_scroll,
                         category="desktop")
        registry.register("keyboard_press", "Press a key", automation.keyboard_press,
                         category="desktop")
        registry.register("hotkey", "Press a hotkey combination", automation.keyboard_hotkey,
                         category="desktop")
        registry.register("open_app", "Open an application", automation.open_app,
                         category="desktop")

        # ===================================================================
        # Web
        # ===================================================================
        registry.register("web_search", "Search the web using DuckDuckGo", web_search,
                         category="web", returns="string")
        registry.register("web_scrape", "Fetch and extract text from a webpage", web_scrape,
                         category="web", returns="string")
        registry.register("web_fetch_json", "Fetch JSON from an API", web_fetch_json,
                         category="web", returns="string")
        registry.register("web_search_news", "Search news using DuckDuckGo", web_search_news,
                         category="web", returns="string")
        registry.register("url_shorten", "Shorten a URL", url_shorten,
                         category="web", returns="string")

        # ===================================================================
        # Files
        # ===================================================================
        registry.register("file_read", "Read contents of a file with line numbers", file_read,
                         category="files", returns="string")
        registry.register("file_write", "Write content to a file", file_write,
                         category="files", returns="string")
        registry.register("file_list", "List files in a directory", file_list,
                         category="files", returns="string")
        registry.register("file_delete", "Delete a file or directory", file_delete,
                         category="files", returns="string")
        registry.register("file_grep", "Search for text in a file", file_grep,
                         category="files", returns="string")
        registry.register("file_download", "Download a file from URL", file_download,
                         category="files", returns="string")

        # ===================================================================
        # Code
        # ===================================================================
        registry.register("run_python", "Execute Python code in sandbox", run_python,
                         category="code", returns="string")
        registry.register("run_shell", "Run a shell command",
                         lambda cmd, timeout=30: run_shell(cmd, timeout),
                         category="code", returns="string")
        registry.register("analyze_code", "Analyze Python code for issues", analyze_code,
                         category="code", returns="string")

        # ===================================================================
        # System / Health
        # ===================================================================
        registry.register("health_check", "Run health checks on all systems",
                         lambda: health.json_report(),
                         category="system", returns="dict")
        registry.register("self_heal", "Auto-fix common issues",
                         lambda: {"fixes": healer.heal_all()},
                         category="system", returns="dict")
        registry.register("system_info", "Get system information (CPU, memory, disk)",
                         system_info_str,
                         category="system", returns="string")
        registry.register("process_list", "List running processes",
                         lambda f=None: process_list(f),
                         category="system", returns="string")
        registry.register("network_info", "Get network information",
                         network_info,
                         category="system", returns="string")

        # ===================================================================
        # Utilities
        # ===================================================================
        registry.register("weather", "Get weather for a location",
                         weather_get,
                         category="utilities", returns="string")
        registry.register("calculate", "Evaluate a mathematical expression",
                         calculate,
                         category="utilities", returns="string")
        registry.register("random_password", "Generate a random password",
                         random_password,
                         category="utilities", returns="string")
        registry.register("random_number", "Generate a random number",
                         random_number,
                         category="utilities", returns="string")
        registry.register("translate", "Translate text between languages",
                         translate_text,
                         category="utilities", returns="string")
        registry.register("text_count", "Count characters and words in text",
                         text_count,
                         category="utilities", returns="string")
        registry.register("encode_base64", "Encode or decode Base64",
                         lambda text, decode=False: encode_base64(text, decode),
                         category="utilities", returns="string")
        registry.register("note_add", "Save a note to memory",
                         note_add,
                         category="utilities", returns="string")
        registry.register("note_get", "Retrieve a note from memory",
                         note_get,
                         category="utilities", returns="string")
        registry.register("note_list", "List all saved notes",
                         note_list,
                         category="utilities", returns="string")
        registry.register("qr_generate", "Generate a QR code",
                         qr_generate,
                         category="utilities", returns="string")

        # ===================================================================
        # Android
        # ===================================================================
        registry.register("android_devices", "List connected Android devices",
                         lambda: android.devices(),
                         category="android", returns="list")

        # ===================================================================
        # Self-Developer & Profile (Abhinav Base44-style)
        # ===================================================================
        registry.register("build_feature", "Build a new feature from natural language description (Base44-style)",
                         lambda prompt, module_name=None, create_pr=True: build_from_prompt(prompt, module_name, create_pr),
                         category="self_develop", returns="dict",
                         params=[{"name": "prompt", "type": "str", "required": True, "description": "Describe what to build"},
                                 {"name": "module_name", "type": "str", "required": False, "description": "Custom module name"},
                                 {"name": "create_pr", "type": "bool", "required": False, "description": "Create GitHub PR"}]),
        registry.register("generate_code", "Generate Python code from a description using LLM",
                         lambda prompt, module_name=None: generate_module_from_prompt(prompt, module_name),
                         category="self_develop", returns="dict",
                         params=[{"name": "prompt", "type": "str", "required": True, "description": "Describe the code to generate"}]),
        registry.register("auto_register", "Auto-register a module's functions as tools",
                         lambda module_name: auto_register_module(module_name),
                         category="self_develop",
                         params=[{"name": "module_name", "type": "str", "required": True, "description": "Module name (no .py)"}]),
        registry.register("git_commit", "Create a git commit with changes",
                         lambda message, files=None: create_git_commit(message, files),
                         category="self_develop",
                         params=[{"name": "message", "type": "str", "required": True, "description": "Commit message"},
                                 {"name": "files", "type": "list", "required": False, "description": "Files to commit"}]),
        registry.register("github_pr", "Create a GitHub Pull Request",
                         lambda title, body=None: create_github_pr(title, body),
                         category="self_develop",
                         params=[{"name": "title", "type": "str", "required": True, "description": "PR title"},
                                 {"name": "body", "type": "str", "required": False, "description": "PR description"}]),
        registry.register("code_quality", "Analyze Python file for code quality issues",
                         lambda filepath: analyze_code_quality(filepath),
                         category="self_develop", returns="dict",
                         params=[{"name": "filepath", "type": "str", "required": True, "description": "Path to Python file"}]),
        registry.register("list_generated", "List all auto-generated modules",
                         lambda: {"modules": list_generated_modules()},
                         category="self_develop", returns="dict"),
        registry.register("health_report", "Get detailed health report of all systems",
                         lambda: health.json_report(),
                         category="self_repair", returns="dict"),
        registry.register("self_heal", "Auto-fix common issues (server, tools, git)",
                         lambda: {"fixes": healer.heal_all()},
                         category="self_repair", returns="dict"),
        registry.register("analyze_codebase", "Analyze codebase for issues and optimizations",
                         lambda: improver.analyze_overall(),
                         category="self_repair", returns="dict"),
        registry.register("profile_save", "Save a user profile to memory",
                         lambda name, data=None: profile_manager.save_profile(name, data),
                         category="profile",
                         params=[{"name": "name", "type": "str", "required": True, "description": "Profile name"},
                                 {"name": "data", "type": "dict", "required": False, "description": "Profile data"}]),
        registry.register("profile_load", "Load a user profile from memory",
                         lambda name: profile_manager.load_profile(name),
                         category="profile",
                         params=[{"name": "name", "type": "str", "required": True, "description": "Profile name"}]),
        registry.register("profile_list", "List all saved profiles",
                         lambda: {"profiles": profile_manager.list_profiles()},
                         category="profile", returns="dict")

    # -----------------------------------------------------------------------
    # Core processing
    # -----------------------------------------------------------------------

    def process_text(self, user_input, context=None):
        """Process a text command using fast-path keyword matching then LLM."""
        memory.add_message("user", user_input, self.session_id)

        # First try simple keyword matching (fast path)
        simple_result = self._simple_command_match(user_input)
        if simple_result:
            memory.add_message("assistant", simple_result, self.session_id)
            evolving_memory.record_turn(user_input, simple_result)
            return simple_result

        # Get conversation history
        history = memory.get_history(limit=5, session_id=self.session_id)

        system_prompt = """You are a powerful local AI agent with these capabilities:
- Desktop automation (mouse, keyboard, screenshot, clipboard)
- Android device control (via ADB)
- Web search & scraping (DuckDuckGo, free)
- File operations (read, write, edit, list, download)
- Python code execution (sandboxed)
- Shell commands (safe, read-only)
- Voice (speech-to-text, text-to-speech)
- Memory (remember, recall, search)
- Health checks & self-repair

Keep responses short and direct. When asked to DO something, confirm briefly.
When answering questions, be concise and accurate.

""" + evolving_memory.get_system_prompt_extra()

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        try:
            response = chat(messages)
            if isinstance(response, dict):
                content = response.get("message", {}).get("content", "")
                if content:
                    memory.add_message("assistant", content, self.session_id)
                    evolving_memory.record_turn(user_input, content)
                    return content
            return "I'm here and ready."
        except Exception as e:
            return f"I encountered an error: {e}"

    def _simple_command_match(self, text):
        """Fast keyword-based command matching (no LLM needed)."""
        text_lower = text.lower().strip()

        # --- Desktop ---
        if text_lower in ("screenshot", "capture screen", "take screenshot"):
            result = automation.screenshot()
            path = result.get("path", "unknown")
            return f"📸 Screenshot saved to {path}"

        if "mouse position" in text_lower or "cursor position" in text_lower:
            pos = automation.mouse_position()
            return f"🖱️ Mouse at ({pos.get('x', '?')}, {pos.get('y', '?')})"

        if "screen size" in text_lower or "screen resolution" in text_lower:
            size = automation.get_screen_size()
            return f"🖥️ Screen: {size.get('width', '?')}x{size.get('height', '?')}"

        # --- Commands ---
        if text_lower.startswith("run ") or text_lower.startswith("execute "):
            cmd = text[4:] if text_lower.startswith("run ") else text[8:]
            result = automation.run_command(cmd)
            if result.get("success"):
                return f"$ {cmd}\n{result.get('stdout', '')}"
            return f"Error: {result.get('stderr', '')}"

        # --- Open ---
        if text_lower.startswith("open "):
            target = text[5:]
            if "." in target and " " not in target:
                automation.open_url(target)
                return f"🔗 Opened: {target}"
            automation.open_app(target)
            return f"🚀 Opened: {target}"

        # --- Web Search ---
        if text_lower.startswith("search ") or text_lower.startswith("google "):
            query = text[7:] if text_lower.startswith("search ") else text[7:]
            results = web_search(query)
            return f"🔍 Search results for '{query}':\n{results}"

        # --- Recall ---
        if text_lower.startswith("remember ") or text_lower.startswith("recall "):
            key = text[9:] if text_lower.startswith("remember ") else text[7:]
            val = memory.recall(key)
            if val:
                return f"🧠 {key}: {val}"
            return f"No memory for '{key}'"

        # --- Android ---
        if android.available:
            if "list devices" in text_lower:
                devs = android.devices()
                if isinstance(devs, list):
                    return f"📱 Connected: {[d['id'] for d in devs]}"
                return str(devs)

        # --- Time ---
        if text_lower in ("time", "date", "what time is it", "what's the time",
                          "current time", "today's date"):
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"🕐 {now}"

        # --- Help ---
        if text_lower in ("help", "commands", "what can you do", "list commands"):
            actions = self.actions.list()
            lines = ["**Available commands:**"]
            for name, desc in sorted(actions.items()):
                if desc:
                    lines.append(f"  • `{name}` — {desc}")
            return "\n".join(lines[:50])

        # --- Weather ---
        if text_lower.startswith("weather") or text_lower.startswith("temperature"):
            loc = text[8:] if text_lower.startswith("weather ") else text[12:]
            loc = loc.strip() or "auto"
            return weather_get(loc)

        # --- Calculate ---
        if text_lower.startswith("calc ") or text_lower.startswith("calculate "):
            expr = text[5:] if text_lower.startswith("calc ") else text[10:]
            return calculate(expr)

        # --- System Info ---
        if text_lower in ("sysinfo", "system info", "system information", "specs"):
            return system_info_str()

        # --- Network ---
        if text_lower in ("network", "network info", "my ip", "ip address"):
            return network_info()

        # --- Random ---
        if text_lower.startswith("random number") or text_lower.startswith("roll"):
            parts = text_lower.split()
            if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
                return random_number(int(parts[-2]), int(parts[-1]))
            return random_number(1, 100)

        if text_lower.startswith("password") or text_lower.startswith("generate password"):
            parts = text_lower.split()
            length = 16
            for p in parts:
                if p.isdigit():
                    length = int(p)
                    break
            return random_password(length)

        if "uuid" in text_lower and ("generate" in text_lower or "random" in text_lower):
            return random_uuid()

        # --- Translate ---
        if text_lower.startswith("translate "):
            # Extract target language if specified
            rest = text[10:].strip()
            parts = rest.split(" to ", 1)
            if len(parts) == 2:
                text_to_translate = parts[0].strip()
                target_lang = parts[1].strip()[:2]
            else:
                text_to_translate = rest
                target_lang = "en"
            return translate_text(text_to_translate, target_lang)

        # --- Notes ---
        if text_lower.startswith("save note ") or text_lower.startswith("note add "):
            rest = text[10:] if text_lower.startswith("save note ") else text[9:]
            if ":" in rest:
                title, content = rest.split(":", 1)
                return note_add(title.strip(), content.strip())
            return note_add(rest.strip())

        if text_lower.startswith("get note ") or text_lower.startswith("show note "):
            title = text[9:] if text_lower.startswith("get note ") else text[10:]
            return note_get(title.strip())

        if text_lower in ("notes", "list notes", "my notes", "show notes"):
            return note_list()

        # --- QR Code ---
        if text_lower.startswith("qr ") or text_lower.startswith("qrcode "):
            data = text[3:] if text_lower.startswith("qr ") else text[7:]
            return qr_generate(data.strip())

        # --- URL Shorten ---
        if text_lower.startswith("shorten "):
            url = text[8:].strip()
            return url_shorten(url)

        # --- Text Count ---
        if text_lower.startswith("count ") or text_lower.startswith("word count"):
            target_text = text[6:] if text_lower.startswith("count ") else text[10:]
            if target_text:
                return text_count(target_text)

        # --- Base64 ---
        if text_lower.startswith("encode ") and "base64" in text_lower:
            rest = text[7:]
            rest = rest.replace("base64", "").replace("in", "").strip()
            if rest:
                return encode_base64(rest)
        if text_lower.startswith("decode ") and "base64" in text_lower:
            rest = text[7:]
            rest = rest.replace("base64", "").replace("from", "").strip()
            if rest:
                return encode_base64(rest, decode=True)

        # --- Health ---
        if text_lower in ("health", "status", "check"):
            return health.summary()

        # --- Tools list ---
        if text_lower == "tools" or text_lower == "list all tools":
            tools = registry.list_tools()
            cats = {}
            for t in tools:
                cats.setdefault(t["category"], []).append(t["name"])
            lines = ["**Available tool categories:**"]
            for cat, names in sorted(cats.items()):
                lines.append(f"  • **{cat}**: {', '.join(names)}")
            return "\n".join(lines)

        return None

    # -----------------------------------------------------------------------
    # Voice interaction
    # -----------------------------------------------------------------------

    def listen_and_respond(self, duration=5):
        """Listen, process, and speak response."""
        print("[Agent] Listening...")
        text = stt.record_and_transcribe(duration=duration)
        print(f"[Agent] Heard: {text}")
        if not text:
            return "I didn't catch that."
        response = self.process_text(text)
        if isinstance(response, str) and response:
            tts.say(response)
        return response

    def voice_loop(self, wake_word=True):
        """Continuous voice interaction loop."""
        print("[Agent] Voice loop started. Say 'hey agent' to activate. Press Ctrl+C to stop.")
        from modules.voice import WakeWordDetector
        detector = WakeWordDetector()

        self.running = True
        try:
            while self.running:
                if wake_word:
                    detected = detector.listen_for_wake_word(timeout=None)
                    if not detected:
                        continue
                    tts.say("Yes?")
                else:
                    tts.say("Listening...")

                text = stt.record_and_transcribe(duration=5)
                if not text:
                    continue

                print(f"[Agent] Command: {text}")

                if text.lower() in ["exit", "quit", "stop listening", "go to sleep"]:
                    tts.say("Going to sleep.")
                    self.running = False
                    break

                response = self.process_text(text)
                if response:
                    tts.say(response)

        except KeyboardInterrupt:
            print("\n[Agent] Voice loop ended.")
        finally:
            self.running = False

    # -----------------------------------------------------------------------
    # Autonomous mode (from NEO-AGENT)
    # -----------------------------------------------------------------------

    def autonomous_loop(self, iterations=5):
        """Autonomous goal-setting and execution loop."""
        from core.llm import generate

        print("[Agent] 🤖 Starting autonomous mode...")
        self.running = True

        for i in range(iterations):
            if not self.running:
                break

            print(f"\n[Auto] Iteration {i+1}/{iterations}")

            # Check system health
            health_report = health.json_report()
            health_ok = health_report["passed"] >= health_report["total"] // 2

            if not health_ok:
                print("[Auto] ⚠️ Health issues detected, running self-heal...")
                healer.heal_all()

            # Use LLM to decide next action
            prompt = (
                f"You are an autonomous AI agent. Iteration {i+1}/{iterations}.\n"
                f"System health: {health_report['passed']}/{health_report['total']} OK.\n"
                "Suggest ONE useful thing to do right now (check system, search web, "
                "interact with desktop, etc.). Keep it short and actionable.\n"
                "Format: ACTION: <brief description>"
            )

            try:
                suggestion = generate(prompt, system="You suggest actions for an AI agent.", max_tokens=100)
                if suggestion:
                    print(f"[Auto] Suggestion: {suggestion}")

                    # Try to execute the suggestion via keyword matching
                    if "ACTION:" in str(suggestion):
                        action_text = str(suggestion).split("ACTION:")[1].strip()
                        result = self.process_text(action_text)
                        print(f"[Auto] Result: {result[:200]}")
            except Exception as e:
                print(f"[Auto] Error: {e}")

            time.sleep(2)

        print("[Agent] Autonomous mode completed.")
        self.running = False

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def start(self):
        """Start the agent engine."""
        self.running = True
        self.start_time = time.time()
        memory.add_message("system", "Agent started", self.session_id)
        print("[Agent] Engine started.")
        return True

    def stop(self):
        """Stop the agent engine."""
        self.running = False
        evolving_memory.stop()
        memory.add_message("system", "Agent stopped", self.session_id)
        print("[Agent] Engine stopped.")
        return True

    def status(self):
        """Get comprehensive agent status."""
        uptime_secs = int(time.time() - self.start_time) if self.start_time else 0
        hours, rem = divmod(uptime_secs, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"
        return {
            "running": self.running,
            "uptime": uptime_str,
            "session_id": self.session_id,
            "ollama_running": is_running(),
            "ollama_models": list_models(),
            "android_available": android.available,
            "android_connected": android.is_connected() if android.available else False,
            "tools_loaded": len(registry),
            "actions_loaded": len(self.actions._actions),
            "memory_size": len(memory.get_history(limit=1000)),
        }

    def api_process(self, text):
        """Process input via API and return structured result."""
        try:
            response = self.process_text(text)
            return {
                "success": True,
                "input": text,
                "output": response,
                "session_id": self.session_id,
            }
        except Exception as e:
            return {
                "success": False,
                "input": text,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }


# Singleton
engine = AgentEngine()
