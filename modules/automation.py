"""Desktop automation - mouse, keyboard, screen, window control."""
import os
import subprocess
import time
from pathlib import Path

from core.config import config

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    HAS_PYAUTOGUI = True
except Exception:
    # Headless/serverless boxes (e.g. Vercel) have no X display. pyautogui's
    # transitive imports (mouseinfo -> Xlib) fail at import time there with
    # KeyError/OSError/XauthError -- not ImportError -- so a broad catch is
    # required or the whole process crashes on import.
    HAS_PYAUTOGUI = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False


class DesktopAutomation:
    """Control mouse, keyboard, and screen."""

    def __init__(self):
        self.screenshot_dir = Path(config.get("automation", "screenshot_dir"))
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    # --- Mouse ---
    def mouse_move(self, x, y, duration=None):
        """Move mouse to absolute coordinates."""
        if not HAS_PYAUTOGUI:
            return {"error": "pyautogui not installed"}
        pyautogui.moveTo(x, y, duration=duration or config.get("automation", "click_duration"))

    def mouse_click(self, x=None, y=None, button="left", clicks=1):
        """Click at current position or specified coordinates."""
        if not HAS_PYAUTOGUI:
            return {"error": "pyautogui not installed"}
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button, clicks=clicks)
        else:
            pyautogui.click(button=button, clicks=clicks)
        return {"success": True}

    def mouse_drag(self, x, y, duration=0.5):
        """Drag mouse to coordinates."""
        if not HAS_PYAUTOGUI:
            return {"error": "pyautogui not installed"}
        pyautogui.dragTo(x, y, duration=duration)
        return {"success": True}

    def mouse_scroll(self, amount):
        """Scroll vertically (positive=up, negative=down)."""
        if not HAS_PYAUTOGUI:
            return {"error": "pyautogui not installed"}
        pyautogui.scroll(amount)
        return {"success": True}

    def mouse_position(self):
        """Get current mouse position."""
        if not HAS_PYAUTOGUI:
            return {"error": "pyautogui not installed"}
        x, y = pyautogui.position()
        return {"x": x, "y": y}

    # --- Keyboard ---
    def keyboard_type(self, text, interval=0.01):
        """Type text at current cursor position."""
        if not HAS_PYAUTOGUI:
            return {"error": "pyautogui not installed"}
        pyautogui.typewrite(text, interval=interval)
        return {"success": True, "chars": len(text)}

    def keyboard_hotkey(self, *keys):
        """Press a hotkey combination (e.g., 'ctrl', 'c')."""
        if not HAS_PYAUTOGUI:
            return {"error": "pyautogui not installed"}
        pyautogui.hotkey(*keys)
        return {"success": True}

    def keyboard_press(self, key):
        """Press a single key."""
        if not HAS_PYAUTOGUI:
            return {"error": "pyautogui not installed"}
        pyautogui.press(key)
        return {"success": True}

    # --- Screen ---
    def screenshot(self, filename=None):
        """Take a screenshot and save it."""
        if not filename:
            filename = f"screenshot_{int(time.time())}.png"
        path = str(self.screenshot_dir / filename)

        # Try pyautogui first
        if HAS_PYAUTOGUI:
            try:
                im = pyautogui.screenshot(path)
                return {"path": path, "size": im.size}
            except Exception:
                pass

        # Fallback: mss
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct.output = str(path)
                sct.shot(mon=-1, output=path)
            from PIL import Image
            im = Image.open(path)
            return {"path": path, "size": im.size}
        except ImportError:
            pass

        # Fallback: xwd + convert
        try:
            import subprocess
            subprocess.run(
                f"xwd -root -out {path}.xwd 2>/dev/null && "
                f"convert {path}.xwd {path} 2>/dev/null && "
                f"rm -f {path}.xwd",
                shell=True, timeout=10,
            )
            if os.path.exists(path):
                from PIL import Image
                im = Image.open(path)
                return {"path": path, "size": im.size}
        except Exception:
            pass

        return {"error": "No screenshot method available. Install: pip install mss pillow"}

    def screenshot_bytes(self):
        """Take screenshot and return as bytes."""
        if not HAS_PYAUTOGUI:
            return None
        im = pyautogui.screenshot()
        import io
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()

    def get_screen_size(self):
        """Get screen resolution."""
        if not HAS_PYAUTOGUI:
            return {"error": "pyautogui not installed"}
        return {"width": pyautogui.size().width, "height": pyautogui.size().height}

    def locate_on_screen(self, image_path, confidence=0.9):
        """Find an image on screen and return its coordinates."""
        if not HAS_PYAUTOGUI:
            return {"error": "pyautogui not installed"}
        try:
            pos = pyautogui.locateOnScreen(image_path, confidence=confidence)
            if pos:
                return {"x": pos.left, "y": pos.top, "width": pos.width, "height": pos.height}
            return None
        except Exception as e:
            return {"error": str(e)}

    def click_image(self, image_path, confidence=0.9):
        """Find and click an image on screen."""
        pos = self.locate_on_screen(image_path, confidence)
        if pos and "x" in pos:
            self.mouse_click(pos["x"] + pos["width"] // 2, pos["y"] + pos["height"] // 2)
            return {"success": True, "position": pos}
        return {"success": False, "error": "image not found"}

    # --- Clipboard ---
    def clipboard_get(self):
        """Get text from clipboard."""
        if HAS_CLIPBOARD:
            try:
                return pyperclip.paste()
            except Exception:
                pass
        # Fallback via xclip
        try:
            return subprocess.check_output("xclip -selection clipboard -o 2>/dev/null || pbpaste 2>/dev/null", shell=True).decode()
        except Exception:
            return None

    def clipboard_set(self, text):
        """Set clipboard text."""
        if HAS_CLIPBOARD:
            try:
                pyperclip.copy(text)
                return True
            except Exception:
                pass
        try:
            proc = subprocess.Popen("xclip -selection clipboard", shell=True, stdin=subprocess.PIPE)
            proc.communicate(text.encode())
            return True
        except Exception:
            return False

    # --- Window Control (Linux/X11) ---
    def get_windows(self):
        """List open windows (Linux with wmctrl)."""
        try:
            out = subprocess.check_output(["wmctrl", "-l"], stderr=subprocess.DEVNULL).decode()
            windows = []
            for line in out.strip().split("\n"):
                if line:
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        windows.append({"id": parts[0], "desktop": parts[1], "title": parts[3]})
            return windows
        except (FileNotFoundError, subprocess.CalledProcessError):
            return []

    def focus_window(self, title_contains):
        """Focus a window by title substring."""
        windows = self.get_windows()
        for w in windows:
            if title_contains.lower() in w["title"].lower():
                subprocess.run(["wmctrl", "-ia", w["id"]], capture_output=True)
                return {"success": True, "window": w["title"]}
        return {"success": False, "error": f'window containing "{title_contains}" not found'}

    # --- Run command ---
    def run_command(self, cmd, shell=True, timeout=30):
        """Run a shell command and return output."""
        try:
            result = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_app(self, app_name):
        """Open an application."""
        return self.run_command(f"xdg-open {app_name} 2>/dev/null || {app_name} &")

    def open_url(self, url):
        """Open a URL in browser."""
        return self.run_command(f"xdg-open '{url}'")


automation = DesktopAutomation()
