"""Utility tools - calculator, weather, system info, network, and more.

Free, no API keys needed tools for the AI Agent Beast.
"""
import json
import os
import platform
import random
import socket
import string
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path


# ===========================================================================
# Weather
# ===========================================================================

def weather_get(location: str = "auto") -> str:
    """Get current weather for a location using wttr.in (free, no API key).

    Args:
        location: City name or "auto" for IP-based location

    Returns:
        Weather report as formatted text
    """
    try:
        import requests
        url = f"https://wttr.in/{location}?format=%C+%t+%h+%w+%p"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            text = resp.text.strip()
            return f"🌤️ Weather for {location if location != 'auto' else 'your location'}: {text}"
        return f"Weather API returned status {resp.status_code}"
    except Exception as e:
        return f"Weather error: {e}"


def weather_detailed(location: str = "auto") -> str:
    """Get detailed 3-day weather forecast.

    Args:
        location: City name or "auto"

    Returns:
        Detailed weather forecast
    """
    try:
        import requests
        url = f"https://wttr.in/{location}?0T&lang=en"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.text[:3000]
        return f"Weather API error: {resp.status_code}"
    except Exception as e:
        return f"Weather error: {e}"


# ===========================================================================
# Calculator
# ===========================================================================

def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely.

    Args:
        expression: Math expression to evaluate (e.g., "2 + 2", "sqrt(16)")

    Returns:
        Calculation result
    """
    import math

    # Safe math functions available
    safe_dict = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "pow": pow,
        "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
        "tan": math.tan, "log": math.log, "log10": math.log10,
        "pi": math.pi, "e": math.e, "floor": math.floor,
        "ceil": math.ceil, "radians": math.radians,
        "degrees": math.degrees, "factorial": math.factorial,
    }

    # Block dangerous patterns
    blocked = ["__", "import", "os.", "subprocess", "eval", "exec", "open",
               "getattr", "setattr", "delattr"]
    for b in blocked:
        if b in expression:
            return f"⚠️ Blocked: '{b}' not allowed"

    try:
        # Use the safe math functions
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return f"🧮 {expression} = {result}"
    except Exception as e:
        return f"❌ Calculation error: {e}"


# ===========================================================================
# System Information
# ===========================================================================

def system_info() -> dict:
    """Get comprehensive system information.

    Returns:
        Dict with CPU, memory, disk, network, and OS info
    """
    info = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "hostname": socket.gethostname(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "boot_time": "unknown",
    }

    # Boot time
    try:
        import psutil
        boot_ts = psutil.boot_time()
        info["boot_time"] = datetime.fromtimestamp(boot_ts).isoformat()
    except Exception:
        try:
            with open("/proc/stat") as f:
                for line in f:
                    if line.startswith("btime"):
                        info["boot_time"] = datetime.fromtimestamp(int(line.split()[1])).isoformat()
                        break
        except Exception:
            pass

    # CPU
    try:
        import psutil
        info["cpu_count"] = psutil.cpu_count()
        info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        try:
            freq = psutil.cpu_freq()
            info["cpu_freq"] = f"{freq.current:.0f}MHz" if freq else "N/A"
        except Exception:
            info["cpu_freq"] = "N/A"
    except ImportError:
        try:
            info["cpu_count"] = os.cpu_count()
            # Parse /proc/loadavg
            with open("/proc/loadavg") as f:
                info["load_avg"] = f.read().strip().split()[:3]
        except Exception:
            info["cpu_count"] = os.cpu_count()

    # Memory
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["memory"] = {
            "total_gb": round(mem.total / (1024**3), 1),
            "available_gb": round(mem.available / (1024**3), 1),
            "percent_used": mem.percent,
        }
    except ImportError:
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
                total = int([l for l in lines if "MemTotal" in l][0].split()[1])
                avail = int([l for l in lines if "MemAvailable" in l][0].split()[1])
                info["memory"] = {
                    "total_gb": round(total / (1024**2), 1),
                    "available_gb": round(avail / (1024**2), 1),
                    "percent_used": round(100 - (avail / total * 100), 1),
                }
        except Exception:
            info["memory"] = "N/A"

    # Disk
    try:
        import psutil
        disks = []
        try:
            partitions = psutil.disk_partitions()
        except Exception:
            partitions = []
        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "mount": part.mountpoint,
                    "total_gb": round(usage.total / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent": usage.percent,
                })
            except Exception:
                pass
        info["disks"] = disks
    except ImportError:
        try:
            stat = os.statvfs("/")
            info["disk"] = {
                "total_gb": round((stat.f_frsize * stat.f_blocks) / (1024**3), 1),
                "free_gb": round((stat.f_frsize * stat.f_bavail) / (1024**3), 1),
            }
        except Exception:
            info["disk"] = "N/A"

    # Network
    try:
        hostname = socket.gethostname()
        info["ip_local"] = socket.gethostbyname(hostname)
    except Exception:
        info["ip_local"] = "N/A"

    # Uptime
    try:
        with open("/proc/uptime") as f:
            uptime_seconds = float(f.read().split()[0])
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            mins = int((uptime_seconds % 3600) // 60)
            info["uptime"] = f"{days}d {hours}h {mins}m"
    except Exception:
        info["uptime"] = "N/A"

    return info


def system_info_str() -> str:
    """Get system info as formatted string."""
    info = system_info()
    lines = [
        "🖥️ **System Information**",
        f"  Platform: {info.get('platform', 'N/A')}",
        f"  Hostname: {info.get('hostname', 'N/A')}",
        f"  Architecture: {info.get('architecture', 'N/A')}",
        f"  Python: {info.get('python', 'N/A')}",
        f"  Uptime: {info.get('uptime', 'N/A')}",
        f"  IP: {info.get('ip_local', 'N/A')}",
    ]

    cpu = info.get("cpu_count", "N/A")
    lines.append(f"  CPU: {cpu} cores")

    mem = info.get("memory", {})
    if isinstance(mem, dict):
        lines.append(f"  Memory: {mem.get('used_gb', mem.get('percent_used', '?'))}% used "
                     f"({mem.get('available_gb', '?')}GB free / {mem.get('total_gb', '?')}GB total)")

    disks = info.get("disks", [])
    for d in disks:
        lines.append(f"  Disk ({d['mount']}): {d['percent']}% used "
                     f"({d['free_gb']}GB free)")

    return "\n".join(lines)


# ===========================================================================
# Process Management
# ===========================================================================

def process_list(filter_str: str = None) -> str:
    """List running processes.

    Args:
        filter_str: Optional filter to match process names

    Returns:
        Formatted process list
    """
    try:
        import psutil
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                pinfo = proc.info
                if filter_str and filter_str.lower() not in pinfo["name"].lower():
                    continue
                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        processes = sorted(processes, key=lambda p: p.get("cpu_percent", 0) or 0, reverse=True)[:30]

        if not processes:
            return f"No processes found matching '{filter_str}'" if filter_str else "No processes found"

        lines = ["📋 **Running Processes** (top 30 by CPU)"]
        lines.append(f"  {'PID':>7} {'CPU%':>6} {'MEM%':>6}  Name")
        lines.append(f"  {'-'*7} {'-'*6} {'-'*6}  {'-'*20}")
        for p in processes:
            pid = p.get("pid", "?")
            cpu = f"{p.get('cpu_percent', 0) or 0:.1f}"
            mem = f"{p.get('memory_percent', 0) or 0:.1f}"
            name = p.get("name", "?")[:30]
            lines.append(f"  {pid:>7} {cpu:>6} {mem:>6}  {name}")

        return "\n".join(lines)
    except ImportError:
        # Fallback to ps command
        try:
            cmd = "ps aux --sort=-%cpu | head -31"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            return f"📋 **Running Processes**\n```\n{result.stdout[:3000]}\n```"
        except Exception as e:
            return f"Process list error: {e}"


def process_kill(pid: int) -> str:
    """Kill a process by PID.

    Args:
        pid: Process ID to kill

    Returns:
        Success/error message
    """
    try:
        import psutil
        p = psutil.Process(pid)
        name = p.name()
        p.terminate()
        return f"✅ Terminated process {pid} ({name})"
    except ImportError:
        try:
            subprocess.run(["kill", str(pid)], check=True, timeout=5)
            return f"✅ Killed process {pid}"
        except subprocess.CalledProcessError as e:
            return f"❌ Failed to kill process {pid}: {e}"
        except Exception as e:
            return f"❌ Error: {e}"
    except psutil.NoSuchProcess:
        return f"❌ No such process: {pid}"
    except Exception as e:
        return f"❌ Error: {e}"


# ===========================================================================
# Network Tools
# ===========================================================================

def network_info() -> str:
    """Get network information (IP, interfaces, connectivity)."""
    import requests
    info = {}

    # Local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["local_ip"] = s.getsockname()[0]
        s.close()
    except Exception:
        info["local_ip"] = "N/A"

    # Public IP
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=5)
        info["public_ip"] = r.json().get("ip", "N/A")
    except Exception:
        info["public_ip"] = "N/A"

    # DNS
    try:
        socket.gethostbyname("google.com")
        info["dns"] = "Working"
    except Exception:
        info["dns"] = "Not resolving"

    # Default gateway
    try:
        r = subprocess.run(["ip", "route", "show", "default"],
                          capture_output=True, text=True, timeout=3)
        if r.stdout:
            info["gateway"] = r.stdout.split()[2]
        else:
            info["gateway"] = "N/A"
    except Exception:
        info["gateway"] = "N/A"

    lines = [
        "🌐 **Network Information**",
        f"  Local IP: {info.get('local_ip', 'N/A')}",
        f"  Public IP: {info.get('public_ip', 'N/A')}",
        f"  Gateway: {info.get('gateway', 'N/A')}",
        f"  DNS: {info.get('dns', 'N/A')}",
    ]
    return "\n".join(lines)


def network_speed_test() -> str:
    """Perform a simple network speed test (download test)."""
    import requests
    import time
    try:
        # Download a small file to test speed
        url = "https://httpbin.org/bytes/102400"  # 100KB
        start = time.time()
        r = requests.get(url, timeout=10)
        elapsed = time.time() - start
        size_kb = len(r.content) / 1024
        speed = size_kb / elapsed  # KB/s
        return f"📶 Download speed: {speed:.0f} KB/s ({size_kb:.0f} KB in {elapsed:.1f}s)"
    except Exception as e:
        return f"Speed test error: {e}"


# ===========================================================================
# Random Generators
# ===========================================================================

def random_number(min_val: int = 0, max_val: int = 100) -> str:
    """Generate a random number within range.

    Args:
        min_val: Minimum value (default: 0)
        max_val: Maximum value (default: 100)

    Returns:
        Random number
    """
    result = random.randint(min_val, max_val)
    return f"🎲 Random number ({min_val}–{max_val}): **{result}**"


def random_password(length: int = 16) -> str:
    """Generate a secure random password.

    Args:
        length: Password length (default: 16)

    Returns:
        Generated password
    """
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    password = "".join(random.choice(chars) for _ in range(length))
    return f"🔑 Password ({length} chars): `{password}`"


def random_uuid() -> str:
    """Generate a random UUID (v4)."""
    return f"🆔 UUID: `{uuid.uuid4()}`"


# ===========================================================================
# URL Tools
# ===========================================================================

def url_shorten(url: str) -> str:
    """Shorten a URL using TinyURL (free, no API key).

    Args:
        url: The URL to shorten

    Returns:
        Shortened URL
    """
    try:
        import requests
        resp = requests.get(f"https://tinyurl.com/api-create.php?url={url}", timeout=10)
        if resp.status_code == 200:
            short = resp.text.strip()
            return f"🔗 Short URL: {short}"
        return f"URL shortener error: {resp.status_code}"
    except Exception as e:
        return f"URL shortener error: {e}"


# ===========================================================================
# Translation
# ===========================================================================

def translate_text(text: str, target: str = "en", source: str = "auto") -> str:
    """Translate text using a free API.

    Args:
        text: Text to translate
        target: Target language code (default: en)
        source: Source language code (default: auto-detect)

    Returns:
        Translated text
    """
    try:
        import requests
        # Using MyMemory (free, no API key, generous limits)
        # MyMemory does not support auto-detection in langpair, default to 'en'
        src = source if source != "auto" else "en"
        url = "https://api.mymemory.translated.net/get"
        resp = requests.get(url, params={"q": text, "langpair": f"{src}|{target}"}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            translation = data.get("responseData", {}).get("translatedText", "")
            return f"Translation ({source}→{target}):\n{translation}"
        return f"Translation API error: {resp.status_code}"
    except Exception as e:
        return f"Translation error: {e}"


# ===========================================================================
# Notes (quick memory-based notes)
# ===========================================================================

def note_add(title: str, content: str = "") -> str:
    """Add a quick note to memory.

    Args:
        title: Note title/key
        content: Note content

    Returns:
        Confirmation message
    """
    from memory.store import memory
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    value = f"[{timestamp}] {content}" if content else f"[{timestamp}]"
    memory.remember(f"note:{title}", value, category="notes")
    return f"📝 Note saved: '{title}'"


def note_get(title: str) -> str:
    """Retrieve a note from memory.

    Args:
        title: Note title/key

    Returns:
        Note content
    """
    from memory.store import memory
    val = memory.recall(f"note:{title}")
    if val:
        return f"📝 **{title}**: {val}"
    return f"No note found for '{title}'"


def note_list() -> str:
    """List all saved notes."""
    from memory.store import memory
    notes = memory.recall_by_category("notes")
    if not notes:
        return "No notes saved."
    lines = ["📝 **Saved Notes**"]
    for key, val in sorted(notes.items()):
        name = key.replace("note:", "", 1)
        preview = val[:60] + "..." if len(val) > 60 else val
        lines.append(f"  • **{name}**: {preview}")
    return "\n".join(lines)


# ===========================================================================
# QR Code
# ===========================================================================

def qr_generate(data: str) -> str:
    """Generate a QR code as text (ASCII art).

    Args:
        data: Data to encode in QR code

    Returns:
        QR code ASCII representation or URL
    """
    try:
        # Use a public QR code API to generate
        import requests
        encoded = requests.utils.quote(data)
        # Return a URL to a QR image service
        return (
            f"📱 QR Code for: {data}\n"
            f"  https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={encoded}\n"
            f"  (Open the URL to view the QR code)"
        )
    except Exception as e:
        return f"QR code error: {e}"


# ===========================================================================
# Text Utilities
# ===========================================================================

def text_count(text: str) -> str:
    """Count characters, words, and lines in text.

    Args:
        text: Text to analyze

    Returns:
        Text statistics
    """
    chars = len(text)
    words = len(text.split())
    lines = text.count("\n") + 1
    return (
        f"📊 **Text Statistics**\n"
        f"  Characters: {chars}\n"
        f"  Words: {words}\n"
        f"  Lines: {lines}\n"
        f"  Avg word length: {chars / max(words, 1):.1f} chars"
    )


# ===========================================================================
# Base64 / Encoding
# ===========================================================================

def encode_base64(text: str, decode: bool = False) -> str:
    """Encode or decode Base64 text.

    Args:
        text: Text to encode/decode
        decode: If True, decode instead of encode

    Returns:
        Encoded or decoded text
    """
    import base64
    try:
        if decode:
            decoded = base64.b64decode(text).decode("utf-8")
            return f"Decoded: {decoded}"
        else:
            encoded = base64.b64encode(text.encode()).decode()
            return f"Base64: {encoded}"
    except Exception as e:
        return f"Base64 error: {e}"
