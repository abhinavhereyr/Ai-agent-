"""Self-improvement, health checks, and autonomous repair.

Merged from NEO-AGENT self_improve.py + health check system.
"""
import ast
import importlib
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path


class HealthCheck:
    """Run health checks on all agent systems."""

    def __init__(self):
        self.results = []

    def _check(self, name, ok, detail=""):
        self.results.append({
            "name": name,
            "ok": ok,
            "detail": detail,
            "timestamp": time.time(),
        })
        return ok

    def check_all(self):
        """Run all health checks and return results."""
        self.results = []

        # 1. Python version
        py_ok = sys.version_info >= (3, 8)
        self._check("python_version", py_ok, sys.version)

        # 2. Ollama
        try:
            import urllib.request
            r = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
            ollama_ok = r.status == 200
            models = []
            if ollama_ok:
                data = json.loads(r.read())
                models = [m["name"] for m in data.get("models", [])]
            self._check("ollama", ollama_ok,
                        f"{len(models)} models: {', '.join(models[:5])}")
        except Exception as e:
            self._check("ollama", False, str(e))

        # 3. pyautogui / screenshot
        try:
            import pyautogui
            screen_ok = True
            size = pyautogui.size()
            self._check("screenshot", True, f"Screen: {size.width}x{size.height}")
        except Exception as e:
            self._check("screenshot", False, str(e))

        # 4. ADB
        adb_ok = False
        try:
            r = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
            adb_ok = r.returncode == 0
            self._check("adb", adb_ok, r.stdout.split("\n")[0] if adb_ok else "not found")
        except Exception:
            self._check("adb", False, "not installed")

        # 5. Android devices
        if adb_ok:
            try:
                r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
                lines = [l for l in r.stdout.strip().split("\n")[1:] if l.strip()]
                self._check("android_devices", len(lines) > 0,
                            f"{len(lines)} device(s): {lines}" if lines else "none connected")
            except Exception as e:
                self._check("android_devices", False, str(e))
        else:
            self._check("android_devices", False, "ADB not available")

        # 6. Disk space
        try:
            stat = os.statvfs("/")
            free_gb = (stat.f_frsize * stat.f_bavail) / (1024**3)
            self._check("disk_space", free_gb > 0.5, f"{free_gb:.1f}GB free")
        except Exception as e:
            self._check("disk_space", False, str(e))

        # 7. Memory (SQLite)
        try:
            from memory.store import memory
            memory.get_history(limit=1)
            self._check("memory_db", True, "SQLite accessible")
        except Exception as e:
            self._check("memory_db", False, str(e))

        # 8. Voice (STT)
        try:
            from modules.voice import stt
            self._check("stt_engine", True, "STT engine loadable")
        except Exception as e:
            self._check("stt_engine", False, str(e))

        # 9. TTS
        try:
            from modules.voice import tts
            self._check("tts_engine", True, f"Backend: {tts.backend}")
        except Exception as e:
            self._check("tts_engine", False, str(e))

        # 10. Tool Registry Health
        try:
            from modules.tool_registry import registry
            tools = registry.list_tools()
            self._check("tool_registry", True, f"{len(tools)} tools registered")
        except Exception as e:
            self._check("tool_registry", False, str(e))

        # 11. Action Registry Health
        try:
            from core.engine import actions
            acts = actions.list_actions()
            self._check("action_registry", True, f"{len(acts)} actions registered")
        except Exception as e:
            self._check("action_registry", False, str(e))

        # 12. Profile
        try:
            from memory.store import memory
            prof = memory.recall("profile:abhinav")
            self._check("user_profile", bool(prof), "Abhinav profile" if prof else "no profile")
        except Exception as e:
            self._check("user_profile", False, str(e))

        # 13. Git health
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            branch = r.stdout.strip() if r.returncode == 0 else "unknown"
            self._check("git", r.returncode == 0, f"Branch: {branch}")
        except Exception as e:
            self._check("git", False, str(e))

        # 14. Web server
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("127.0.0.1", 8765))
            sock.close()
            self._check("web_server", result == 0, "Port 8765" if result == 0 else "Not listening")
        except Exception as e:
            self._check("web_server", False, str(e))

        return self.results

    def summary(self):
        """Get a human-readable summary."""
        if not self.results:
            self.check_all()
        ok = sum(1 for r in self.results if r["ok"])
        total = len(self.results)
        lines = [f"Health: {ok}/{total} checks passed"]
        for r in self.results:
            icon = "✓" if r["ok"] else "✗"
            lines.append(f"  {icon} {r['name']}: {r['detail'][:80]}")
        return "\n".join(lines)

    def json_report(self):
        """Get full JSON report."""
        if not self.results:
            self.check_all()
        return {
            "timestamp": time.time(),
            "passed": sum(1 for r in self.results if r["ok"]),
            "total": len(self.results),
            "checks": self.results,
        }


class SelfHeal:
    """Attempt to automatically fix common issues."""

    def __init__(self):
        self.fixes = []

    def heal_all(self):
        """Run all self-heal procedures."""
        self.fixes = []
        self._fix_pip_packages()
        self._fix_adb()
        self._fix_screenshot()
        self._fix_ollama()
        self._fix_directories()
        self._fix_server()
        self._fix_tools()
        self._fix_git()
        return self.fixes

    def _fix_pip_packages(self):
        """Install missing critical packages."""
        required = [
            "pyautogui", "pillow", "pyperclip",
            "httpx", "requests", "beautifulsoup4",
        ]
        for pkg in required:
            try:
                importlib.import_module(pkg)
            except ImportError:
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", pkg, "-q"],
                        capture_output=True, timeout=60,
                    )
                    self.fixes.append(f"Installed pip package: {pkg}")
                except Exception as e:
                    self.fixes.append(f"Failed to install {pkg}: {e}")

    def _fix_adb(self):
        """Try to install ADB."""
        if os.system("which adb 2>/dev/null") != 0:
            try:
                subprocess.run(
                    ["apt-get", "install", "-y", "-qq", "android-tools-adb"],
                    capture_output=True, timeout=120,
                )
                self.fixes.append("Installed ADB via apt")
            except Exception as e:
                self.fixes.append(f"Failed to install ADB: {e}")

    def _fix_screenshot(self):
        """Fix screenshot capability."""
        try:
            import pyautogui
            pyautogui.screenshot()
        except Exception:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "pyscreeze", "mss", "-q"],
                    capture_output=True, timeout=60,
                )
                self.fixes.append("Installed screenshot libraries (pyscreeze, mss)")
            except Exception as e:
                self.fixes.append(f"Failed to fix screenshot: {e}")

    def _fix_ollama(self):
        """Check Ollama is running."""
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        except Exception:
            # Try to start ollama
            try:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self.fixes.append("Started Ollama server")
                time.sleep(2)
            except Exception as e:
                self.fixes.append(f"Could not start Ollama: {e}")

    def _fix_directories(self):
        """Ensure required directories exist."""
        dirs = [
            os.path.expanduser("~/agent_screenshots"),
            os.path.expanduser("~/.agent_memory"),
        ]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)
        self.fixes.append(f"Verified {len(dirs)} directories exist")

    def _fix_server(self):
        """Auto-detect and restart the web server if down."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(("127.0.0.1", 8765))
            sock.close()
            self.fixes.append("Web server is running (port 8765)")
        except Exception:
            sock.close()
            # Try to restart
            try:
                subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "web.app:app",
                     "--host", "0.0.0.0", "--port", "8765"],
                    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self.fixes.append("🔄 Auto-restarted web server on port 8765")
                time.sleep(2)
            except Exception as e:
                self.fixes.append(f"Failed to restart server: {e}")

    def _fix_tools(self):
        """Check tool API endpoints and auto-fix issues."""
        import importlib

        # Try to verify tool_registry loads
        try:
            from modules.tool_registry import registry
            tool_count = len(registry.list_tools())
            self.fixes.append(f"Tool registry OK: {tool_count} tools loaded")
        except Exception as e:
            self.fixes.append(f"Tool registry issue: {e}")
            try:
                importlib.reload(importlib.import_module("modules.tool_registry"))
                self.fixes.append("🔄 Reloaded tool registry")
            except Exception as e2:
                self.fixes.append(f"Could not reload tool registry: {e2}")

        # Try to verify action registry loads
        try:
            from core.engine import actions
            action_count = len(actions.list_actions())
            self.fixes.append(f"Action registry OK: {action_count} actions loaded")
        except Exception:
            try:
                importlib.reload(importlib.import_module("core.engine"))
                self.fixes.append("🔄 Reloaded engine module")
            except Exception as e:
                self.fixes.append(f"Engine reload failed: {e}")

        # Try to verify all API endpoints respond
        try:
            import requests
            endpoints = [
                "http://localhost:8765/api/health",
                "http://localhost:8765/api/system/info",
                "http://localhost:8765/api/tools",
            ]
            for ep in endpoints:
                try:
                    r = requests.get(ep, timeout=5)
                    if r.status_code == 200:
                        self.fixes.append(f"✅ API OK: {ep.split('/')[-1]}")
                    else:
                        self.fixes.append(f"⚠️ API {ep.split('/')[-1]}: status {r.status_code}")
                except requests.exceptions.ConnectionError:
                    self.fixes.append(f"❌ API unreachable: {ep.split('/')[-1]}")
        except ImportError:
            self.fixes.append("requests not available for API checks")

    def _fix_git(self):
        """Check git status and auto-fix common issues."""
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            # Check if .git exists
            git_dir = os.path.join(repo_dir, ".git")
            if os.path.exists(git_dir):
                # Check git status
                r = subprocess.run(
                    ["git", "-C", repo_dir, "status", "--short"],
                    capture_output=True, text=True, timeout=10,
                )
                if r.returncode == 0:
                    changes = r.stdout.strip()
                    if changes:
                        self.fixes.append(f"Git: {len(changes.split(chr(10)))} uncommitted file(s)")
                    else:
                        self.fixes.append("Git: clean working tree")
                self.fixes.append("Git repository OK")
            else:
                self.fixes.append("⚠️ Not a git repository")
        except Exception as e:
            self.fixes.append(f"Git check failed: {e}")


# ---------------------------------------------------------------------------
# Autonomous Improvement
# ---------------------------------------------------------------------------

class SelfImprover:
    """Analyze and suggest improvements to the codebase."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def analyze_imports(self):
        """Find missing imports across all Python files."""
        missing = []
        for pyfile in Path(self.base_dir).rglob("*.py"):
            with open(pyfile) as f:
                try:
                    tree = compile(f.read(), pyfile.name, "exec", ast.PyCF_ONLY_AST)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                try:
                                    importlib.import_module(alias.name)
                                except ImportError:
                                    missing.append((str(pyfile), alias.name))
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                try:
                                    importlib.import_module(node.module)
                                except ImportError:
                                    missing.append((str(pyfile), node.module))
                except SyntaxError:
                    continue
        return missing

    def suggest_optimizations(self):
        """Suggest performance optimizations."""
        suggestions = []
        py_files = list(Path(self.base_dir).rglob("*.py"))

        for pyfile in py_files:
            with open(pyfile) as f:
                content = f.read()

            # Check for module-level heavy imports
            if "from transformers import" in content and "__name__" not in content:
                suggestions.append(
                    f"{pyfile}: Move 'from transformers import' inside a function "
                    "for lazy loading"
                )

            # Check for sync sleep in async code
            if "import asyncio" in content and "time.sleep" in content:
                suggestions.append(
                    f"{pyfile}: Uses both asyncio and time.sleep - "
                    "consider using asyncio.sleep"
                )

        return suggestions

    def analyze_file_sizes(self):
        """Analyze file sizes and flag unusually large files."""
        reports = []
        py_files = list(Path(self.base_dir).rglob("*.py"))
        for pyfile in py_files:
            size = pyfile.stat().st_size
            if size > 50000:  # > 50KB
                reports.append({
                    "file": str(pyfile),
                    "size_kb": round(size / 1024, 1),
                    "severity": "warning",
                    "suggestion": "Consider splitting into smaller modules"
                })
            elif size > 20000:  # > 20KB
                reports.append({
                    "file": str(pyfile),
                    "size_kb": round(size / 1024, 1),
                    "severity": "info",
                })
        return reports

    def analyze_tool_coverage(self):
        """Analyze which tools have API endpoints vs. which don't."""
        try:
            from modules.tool_registry import registry
            import requests

            tools = registry.list_tools()
            # Check if tools have matching API endpoints
            try:
                r = requests.get("http://localhost:8765/api/tools", timeout=5)
                api_tools = r.json().get("tools", []) if r.status_code == 200 else []
            except Exception:
                api_tools = []

            missing = []
            for t in tools:
                name = t.get("name", t) if isinstance(t, dict) else t
                if name not in [a.get("name", a) if isinstance(a, dict) else a for a in api_tools]:
                    missing.append(name)
            return {"total": len(tools), "in_api": len(api_tools), "missing_endpoints": missing}
        except Exception:
            return {"error": "Could not analyze tool coverage"}

    def analyze_overall(self):
        """Run all analyses and produce a combined report."""
        return {
            "missing_imports": self.analyze_imports(),
            "optimizations": self.suggest_optimizations(),
            "file_sizes": self.analyze_file_sizes(),
            "tool_coverage": self.analyze_tool_coverage(),
        }


# ---------------------------------------------------------------------------
# Profile Manager
# ---------------------------------------------------------------------------

class ProfileManager:
    """Manage user profiles with preferences and history."""

    def save_profile(self, name: str, data: dict = None) -> dict:
        """Save a user profile to persistent memory.

        Args:
            name: Profile name (e.g., 'abhinav')
            data: Profile data dict

        Returns:
            Dict with {success, key}
        """
        from memory.store import memory
        import json

        profile_data = data or {}
        profile_data.setdefault("name", name)
        profile_data.setdefault("version", "2.5")
        profile_data.setdefault("created", time.time())

        key = f"profile:{name.lower()}"
        memory.remember(key, json.dumps(profile_data), category="profile")
        return {"success": True, "key": key}

    def load_profile(self, name: str) -> dict:
        """Load a user profile from memory.

        Args:
            name: Profile name

        Returns:
            Profile data dict or None
        """
        from memory.store import memory
        import json

        key = f"profile:{name.lower()}"
        raw = memory.recall(key)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"name": name, "raw": raw}
        return None

    def list_profiles(self) -> list:
        """List all saved profiles."""
        from memory.store import memory
        import json

        notes = memory.recall_by_category("profile") or {}
        profiles = []
        for key, val in notes.items():
            name = key.replace("profile:", "", 1)
            try:
                data = json.loads(val)
                profiles.append({"name": name, "data": data})
            except json.JSONDecodeError:
                profiles.append({"name": name, "raw": val[:100]})
        return profiles


# Singleton
health = HealthCheck()
healer = SelfHeal()
improver = SelfImprover()
profile_manager = ProfileManager()
