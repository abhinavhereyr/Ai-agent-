"""Browser automation module."""
import os
import subprocess
import time
import json

from core.config import config


class BrowserController:
    """Control web browsers - open URLs, run JS, take screenshots."""

    def __init__(self):
        self.browsers = self._detect_browsers()

    def _detect_browsers(self):
        """Detect installed browsers."""
        browsers = {}
        checks = [
            ("chrome", ["google-chrome", "google-chrome-stable"]),
            ("chromium", ["chromium-browser", "chromium"]),
            ("firefox", ["firefox"]),
            ("brave", ["brave-browser"]),
            ("opera", ["opera"]),
            ("edge", ["microsoft-edge"]),
        ]
        for name, cmds in checks:
            for cmd in cmds:
                try:
                    subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
                    browsers[name] = cmd
                    break
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
        return browsers

    def open(self, url, browser=None):
        """Open URL in specified or default browser."""
        if browser and browser in self.browsers:
            cmd = self.browsers[browser]
            subprocess.Popen([cmd, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"success": True, "browser": browser, "url": url}

        # Use xdg-open as fallback
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "browser": "default", "url": url}

    def search(self, query, engine="google", browser=None):
        """Search the web."""
        search_urls = {
            "google": f"https://www.google.com/search?q={query.replace(' ', '+')}",
            "duckduckgo": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
            "bing": f"https://www.bing.com/search?q={query.replace(' ', '+')}",
            "youtube": f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
        }
        url = search_urls.get(engine.lower(), search_urls["google"])
        return self.open(url, browser)

    def available_browsers(self):
        """List available browsers."""
        return self.browsers


browser = BrowserController()
