"""Screen overlay - floating overlay for commands and status."""
import subprocess
import json
import os
import time
import threading

from core.config import config

OVERLAY_HTML = """<!DOCTYPE html>
<html>
<head>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: system-ui, -apple-system, sans-serif;
    background: transparent;
    overflow: hidden;
    user-select: none;
  }
  #overlay {
    position: fixed;
    top: 0; left: 0; right: 0;
    background: rgba(13, 17, 23, 0.85);
    color: #c9d1d9;
    padding: 8px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 14px;
    backdrop-filter: blur(8px);
    border-bottom: 1px solid rgba(48, 54, 61, 0.5);
    z-index: 999999;
  }
  #status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
  }
  .online { background: #3fb950; }
  .offline { background: #f85149; }
  .listening { background: #d29922; animation: pulse 1s infinite; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
  #status-text { color: #8b949e; font-size: 12px; }
  #command-display { flex: 1; margin: 0 16px; text-align: center; font-size: 13px; }
  #response-display { color: #3fb950; font-size: 12px; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #close-btn { background: none; border: none; color: #8b949e; cursor: pointer; font-size: 18px; padding: 0 4px; }
  #close-btn:hover { color: #f85149; }
  .mic-btn {
    background: rgba(56, 139, 253, 0.2);
    border: 1px solid #58a6ff;
    border-radius: 50%;
    width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; color: #58a6ff; font-size: 14px;
    margin-right: 8px;
  }
  .mic-btn:hover { background: rgba(56, 139, 253, 0.4); }
  .mic-btn.active { background: #d29922; border-color: #d29922; color: #fff; }
</style>
</head>
<body>
<div id="overlay">
  <div style="display:flex;align-items:center;">
    <span id="status-dot" class="offline"></span>
    <span id="status-text">Initializing...</span>
  </div>
  <button class="mic-btn" id="mic-btn" onclick="toggleMic()">🎤</button>
  <div id="command-display">Say "hey agent" or type a command</div>
  <div id="response-display"></div>
  <button id="close-btn" onclick="closeOverlay()">&times;</button>
</div>
<script>
  // Listen for messages from the parent process
  window.addEventListener('message', (event) => {
    const data = event.data;
    if (data.type === 'status') {
      const dot = document.getElementById('status-dot');
      dot.className = data.ollama_running ? 'online' : 'offline';
      document.getElementById('status-text').textContent = data.ollama_running ? 'Online' : 'Ollama Offline';
    } else if (data.type === 'command') {
      document.getElementById('command-display').textContent = data.text;
    } else if (data.type === 'response') {
      document.getElementById('response-display').textContent = data.text;
      setTimeout(() => document.getElementById('response-display').textContent = '', 5000);
    }
  });
  function toggleMic() {
    const btn = document.getElementById('mic-btn');
    btn.classList.toggle('active');
    window.parent.postMessage({type: 'toggle_mic', active: btn.classList.contains('active')}, '*');
  }
  function closeOverlay() {
    window.parent.postMessage({type: 'close_overlay'}, '*');
  }
  // Ping parent
  setInterval(() => window.parent.postMessage({type: 'ping'}, '*'), 5000);
</script>
</body>
</html>"""


class ScreenOverlay:
    """Floating overlay that shows agent status on screen."""

    def __init__(self):
        self.process = None
        self.running = False

    def start(self):
        """Launch the overlay in a small browser window."""
        if self.running:
            return

        # Write the HTML to a temp file
        html_path = "/tmp/agent_overlay.html"
        with open(html_path, "w") as f:
            f.write(OVERLAY_HTML)

        # Try to open with a browser in app mode
        try:
            # Try chromium/kiosk mode
            browsers = [
                ["chromium-browser", f"--app=file://{html_path}", "--window-size=800,40", "--window-position=0,0"],
                ["google-chrome", f"--app=file://{html_path}", "--window-size=800,40", "--window-position=0,0"],
                ["firefox", "--new-window", f"file://{html_path}"],
            ]
            for browser_cmd in browsers:
                try:
                    self.process = subprocess.Popen(
                        browser_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self.running = True
                    print(f"[Overlay] Started with {browser_cmd[0]}")
                    return
                except FileNotFoundError:
                    continue

            print("[Overlay] No suitable browser found for overlay. Use the web UI instead.")
        except Exception as e:
            print(f"[Overlay] Failed: {e}")

    def stop(self):
        """Close the overlay."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        self.running = False
        print("[Overlay] Stopped")

    def update_status(self, status_data):
        """Update the overlay with new status (via file polling or websocket)."""
        # For simplicity, the overlay uses postMessage
        pass


overlay = ScreenOverlay()
