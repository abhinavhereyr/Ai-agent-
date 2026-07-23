"""Android device control via ADB."""
import json
import os
import re
import subprocess
import time

from core.config import config


class AndroidController:
    """Control Android devices via ADB (Android Debug Bridge)."""

    def __init__(self):
        self.adb_path = config.get("android", "adb_path", default="adb")
        self._check_adb()

    def _check_adb(self):
        """Check if ADB is available."""
        try:
            subprocess.run([self.adb_path, "version"], capture_output=True, text=True)
            self.available = True
        except FileNotFoundError:
            self.available = False

    def _adb(self, *args, timeout=30):
        """Run an ADB command.

        Args:
            timeout: Command timeout in seconds (default 30).
        """
        if not self.available:
            return {"error": "ADB not found. Install it: apt install adb"}
        try:
            result = subprocess.run(
                [self.adb_path] + list(args),
                capture_output=True, text=True, timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        except subprocess.TimeoutExpired:
            return {"error": "command timed out"}
        except Exception as e:
            return {"error": str(e)}

    def _termux(self, *args):
        """Run a termux-api command on the device, checking availability first."""
        cmd = " ".join(shlex_quote(a) for a in args)
        check = self._adb("shell", f"command -v {args[0]}")
        if check.get("stdout", "").strip() == "":
            return {"error": f"{args[0]} not found on device. Install Termux:API add-on."}
        return self._adb("shell", cmd)

    def devices(self):
        """List connected devices."""
        result = self._adb("devices")
        if "error" in result:
            return result
        devices = []
        for line in result.get("stdout", "").split("\n")[1:]:
            if line.strip() and "device" in line and "offline" not in line:
                parts = line.split()
                if len(parts) >= 2:
                    devices.append({"id": parts[0], "status": parts[1]})
        return devices

    def shell(self, command):
        """Run a shell command on the device."""
        result = self._adb("shell", command)
        return result

    def tap(self, x, y):
        """Tap at coordinates."""
        return self._adb("shell", f"input tap {x} {y}")

    def swipe(self, x1, y1, x2, y2, duration_ms=300):
        """Swipe from (x1,y1) to (x2,y2)."""
        return self._adb("shell", f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def text(self, text):
        """Type text on the device."""
        escaped = text.replace(" ", "%s").replace("'", "\\'")
        return self._adb("shell", f"input text '{escaped}'")

    def keyevent(self, keycode):
        """Send a key event (e.g., 3=HOME, 4=BACK, 26=POWER)."""
        return self._adb("shell", f"input keyevent {keycode}")

    def screenshot(self, path=None):
        """Take a screenshot of the device."""
        if not path:
            path = f"/sdcard/screenshot_{int(time.time())}.png"
        self._adb("shell", f"screencap -p {path}")
        return path

    def pull_screenshot(self, local_path=None):
        """Take screenshot and pull to local machine."""
        if not local_path:
            local_path = os.path.expanduser(f"~/android_screenshot_{int(time.time())}.png")
        remote = f"/sdcard/screen_{int(time.time())}.png"
        self._adb("shell", f"screencap -p {remote}")
        result = self._adb("pull", remote, local_path)
        self._adb("shell", f"rm {remote}")
        return {"path": local_path, "success": result.get("success", False)}

    def install(self, apk_path):
        """Install an APK."""
        return self._adb("install", apk_path)

    def uninstall(self, package):
        """Uninstall a package."""
        return self._adb("uninstall", package)

    def list_packages(self, filter_str=None):
        """List installed packages."""
        cmd = "pm list packages"
        if filter_str:
            cmd += f" | grep {filter_str}"
        result = self._adb("shell", cmd)
        if "error" in result:
            return result
        packages = re.findall(r"package:([\w.]+)", result.get("stdout", ""))
        return packages

    def launch_app(self, package, activity=None):
        """Launch an app by package name."""
        if activity:
            return self._adb("shell", f"am start -n {package}/{activity}")
        # Try to launch the main activity
        return self._adb("shell", f"monkey -p {package} -c android.intent.category.LAUNCHER 1")

    def force_stop(self, package):
        """Force stop an app."""
        return self._adb("shell", f"am force-stop {package}")

    def get_power_state(self):
        """Check if device screen is on."""
        result = self._adb("shell", "dumpsys power | grep 'mWakefulness'")
        if "error" in result:
            return result
        return result.get("stdout", "")

    def wake_up(self):
        """Wake up the device."""
        return self._adb("shell", "input keyevent KEYCODE_WAKEUP")

    def is_connected(self):
        """Check if any device is connected."""
        devices = self.devices()
        return isinstance(devices, list) and len(devices) > 0

    def get_device_info(self):
        """Get device information."""
        info = {}
        props = [
            ("model", "ro.product.model"),
            ("manufacturer", "ro.product.manufacturer"),
            ("android_version", "ro.build.version.release"),
            ("sdk", "ro.build.version.sdk"),
        ]
        for key, prop in props:
            result = self._adb("shell", f"getprop {prop}")
            if "stdout" in result:
                info[key] = result["stdout"]
        return info

    # ---------------------------------------------------------------------------
    # Enhanced capabilities
    # ---------------------------------------------------------------------------

    def send_sms(self, phone_number, message):
        """Send an SMS message via ADB intent.

        Args:
            phone_number: Recipient phone number.
            message: SMS text body.

        Returns:
            dict with success/error status.
        """
        safe_message = message.replace("'", "\\'").replace('"', '\\"')
        return self._adb(
            "shell",
            f"am start -a android.intent.action.SENDTO -d sms:{phone_number} "
            f"--es sms_body '{safe_message}' --ez exit_on_sent true",
        )

    def make_call(self, phone_number):
        """Make a phone call via ACTION_CALL intent.

        Args:
            phone_number: Phone number to call.

        Returns:
            dict with success/error status.
        """
        return self._adb(
            "shell",
            f"am start -a android.intent.action.CALL -d tel:{phone_number}",
        )

    def get_location(self):
        """Get GPS coordinates using termux-location or dumpsys location.

        Tries termux-location first for fine-grained coordinates, falls back
        to parsing dumpsys location for network-based location.

        Returns:
            dict with keys: latitude, longitude, altitude, accuracy, provider
            or an error dict.
        """
        # Try termux-location first
        termux_check = self._adb("shell", "command -v termux-location")
        if termux_check.get("stdout", "").strip():
            result = self._adb("shell", "termux-location -p provider")
            if result.get("success") and result.get("stdout"):
                try:
                    data = json.loads(result["stdout"])
                    return {
                        "latitude": data.get("latitude"),
                        "longitude": data.get("longitude"),
                        "altitude": data.get("altitude"),
                        "accuracy": data.get("accuracy"),
                        "provider": data.get("provider"),
                    }
                except (json.JSONDecodeError, KeyError):
                    pass

        # Fallback: dumpsys location
        result = self._adb("shell", "dumpsys location | grep -E 'gps|network|Location\\['")
        if "error" in result:
            return result
        output = result.get("stdout", "")
        coords = re.findall(r"[-+]?\d+\.\d+", output)
        if len(coords) >= 2:
            return {
                "latitude": float(coords[0]),
                "longitude": float(coords[1]),
                "source": "dumpsys (network)",
            }
        return {"error": "location not available", "raw": output}

    def take_photo(self, camera_id="0"):
        """Take a photo using termux-camera-photo or am broadcast.

        Args:
            camera_id: Camera ID (0=back, 1=front).

        Returns:
            dict with photo path or error.
        """
        photo_path = f"/sdcard/photo_{int(time.time())}.jpg"
        termux_check = self._adb("shell", "command -v termux-camera-photo")
        if termux_check.get("stdout", "").strip():
            result = self._adb("shell", f"termux-camera-photo -c {camera_id} {photo_path}")
            if result.get("success"):
                return {"path": photo_path, "method": "termux-camera-photo"}
            return {"error": result.get("stderr", "failed to take photo")}

        # Fallback: try using am broadcast with camera intent
        result = self._adb(
            "shell",
            f"am broadcast -a android.intent.action.STILL_IMAGE_CAMERA --ei camera_id {camera_id}",
        )
        # Wait briefly then pull from DCIM
        time.sleep(2)
        dcim_result = self._adb("shell", "ls -t /sdcard/DCIM/Camera/ 2>/dev/null | head -1")
        if dcim_result.get("stdout"):
            newest = f"/sdcard/DCIM/Camera/{dcim_result['stdout'].strip()}"
            return {"path": newest, "method": "camera_intent"}
        return {"error": "could not take photo", "raw": result}

    def get_clipboard(self):
        """Get clipboard text via ADB service call.

        Returns:
            dict with 'text' key containing clipboard content, or error.
        """
        # Android 10+ approach via service call clipboard
        result = self._adb("shell", "service call clipboard 2 2>/dev/null")
        # Try newer API (Android 12+)
        if not result.get("stdout") or "Parcel" not in result.get("stdout", ""):
            result = self._adb("shell", "service call clipboard 2 i32 1 i32 0 2>/dev/null")
        if not result.get("stdout") or "Parcel" not in result.get("stdout", ""):
            result = self._adb(
                "shell", "content query --uri content://clipboard 2>/dev/null"
            )
        if result.get("stdout"):
            # Parse Parcel output for text
            text = result["stdout"]
            # Try to extract text between single quotes in Parcel output
            matches = re.findall(r"'([^']{2,})'", text)
            if matches:
                return {"text": matches[0]}
            # Try extracting after 'text:' or 'value:' markers
            matches = re.findall(r"(?:text|value)=['\"]?(.+?)['\"]?\s", text)
            if matches:
                return {"text": matches[0]}
            return {"text": text.strip()}
        return {"error": "clipboard not accessible", "raw": result.get("stdout", "")}

    def set_clipboard(self, text):
        """Set clipboard text via ADB.

        Args:
            text: Text to copy to clipboard.

        Returns:
            dict with success/error status.
        """
        safe_text = text.replace("'", "\\'").replace('"', '\\"')
        # Modern approach: am broadcast with clipboard content
        result = self._adb(
            "shell",
            f'am broadcast -a android.intent.action.CLIPBOARD_CHANGED '
            f'--es key "{safe_text}" 2>/dev/null',
        )
        # Try content insert method
        result2 = self._adb(
            "shell",
            f"content insert --uri content://clipboard "
            f"--bind text:s:'{safe_text}' 2>/dev/null",
        )
        # Also try service call method (older API)
        result3 = self._adb(
            "shell",
            f"service call clipboard 1 i32 1 i32 0 s16 str '{safe_text}' 2>/dev/null",
        )
        success = (
            (result.get("success") and "Broadcast" in result.get("stdout", ""))
            or (result2.get("success") and result2.get("stdout", "") != "")
            or (result3.get("success") and "Result" in result3.get("stdout", ""))
        )
        if success:
            return {"success": True, "text": text}
        # If everyone fails but at least one didn't error outright
        return {"success": False, "error": "could not set clipboard", "text": text}

    def scan_wifi_networks(self):
        """Scan nearby Wi-Fi access points using termux-wifi-scaninfo.

        Returns:
            dict with list of nearby Wi-Fi networks (SSID, BSSID, RSSI,
            frequency, capabilities) or error.
        """
        termux_check = self._adb("shell", "command -v termux-wifi-scaninfo")
        if termux_check.get("stdout", "").strip():
            result = self._adb("shell", "termux-wifi-scaninfo")
            if result.get("success") and result.get("stdout"):
                try:
                    networks = json.loads(result["stdout"])
                    return {"networks": networks, "count": len(networks)}
                except json.JSONDecodeError as e:
                    return {"error": f"failed to parse Wi-Fi scan: {e}"}

        # Fallback: dumpsys wifi
        result = self._adb("shell", "dumpsys wifi | grep -E 'SSID|BSSID|RSSI|Frequency' | head -60")
        if "error" in result:
            return result
        return {"networks": "raw", "raw": result.get("stdout", "no wifi data")}

    def dump_ui_layout(self):
        """Dump current screen UI XML layout and parse it for visible text/buttons.

        Uses uiautomator dump to capture the current view hierarchy, then
        extracts clickable elements and text labels.

        Returns:
            dict with 'elements' list and 'raw_xml' string, or error.
        """
        dump_path = f"/sdcard/ui_dump_{int(time.time())}.xml"
        result = self._adb("shell", f"uiautomator dump {dump_path}")
        if not result.get("success"):
            return {"error": "uiautomator dump failed", "raw": result}

        pull_result = self._adb("pull", dump_path, "/tmp/android_ui_dump.xml")
        self._adb("shell", f"rm {dump_path}")

        try:
            with open("/tmp/android_ui_dump.xml", "r", encoding="utf-8") as f:
                raw_xml = f.read()
        except (FileNotFoundError, IOError) as e:
            return {"error": f"could not read UI dump: {e}"}
        finally:
            # Clean up temp file
            try:
                os.remove("/tmp/android_ui_dump.xml")
            except OSError:
                pass

        # Parse the XML for text and clickable elements
        elements = []
        # Find all node elements with text
        for match in re.finditer(
            r'<node\s[^>]*?text="([^"]*)"[^>]*?class="([^"]*)"[^>]*?'
            r'clickable="([^"]*)"[^>]*?bounds="([^"]*)"[^>]*?/>',
            raw_xml,
        ):
            text, cls, clickable, bounds = match.groups()
            if text.strip():
                elements.append(
                    {
                        "text": text,
                        "class": cls,
                        "clickable": clickable == "true",
                        "bounds": bounds,
                    }
                )

        # Also catch multiline nodes (not self-closing)
        for match in re.finditer(
            r'<node\s[^>]*?text="([^"]*)"[^>]*?class="([^"]*)"[^>]*?'
            r'clickable="([^"]*)"[^>]*?bounds="([^"]*)"[^>]*?>',
            raw_xml,
        ):
            text, cls, clickable, bounds = match.groups()
            if text.strip() and not any(e["text"] == text for e in elements):
                elements.append(
                    {
                        "text": text,
                        "class": cls,
                        "clickable": clickable == "true",
                        "bounds": bounds,
                    }
                )

        return {
            "elements": elements,
            "count": len(elements),
            "raw_xml": raw_xml,
        }

    def list_contacts(self, search_query=""):
        """List contacts via termux-contact-list.

        Args:
            search_query: Optional filter string to search contacts by name or number.

        Returns:
            dict with list of contacts (name, phone number) or error.
        """
        termux_check = self._adb("shell", "command -v termux-contact-list")
        if not termux_check.get("stdout", "").strip():
            return {"error": "termux-contact-list not available. Install Termux:API."}

        result = self._adb("shell", "termux-contact-list")
        if not result.get("success") or not result.get("stdout"):
            return {"error": "failed to list contacts", "raw": result}

        try:
            contacts = json.loads(result["stdout"])
        except json.JSONDecodeError as e:
            return {"error": f"failed to parse contacts: {e}"}

        if search_query:
            q = search_query.lower()
            filtered = []
            for c in contacts:
                name = c.get("name", "").lower()
                number = c.get("number", "").lower()
                if q in name or q in number:
                    filtered.append(c)
            contacts = filtered

        return {"contacts": contacts, "count": len(contacts)}

    def audit_sms_inbox(self, limit=10):
        """List recent SMS messages using content provider.

        Args:
            limit: Maximum number of SMS messages to return (default 10).

        Returns:
            dict with list of SMS messages (address, body, date, type) or error.
        """
        result = self._adb(
            "shell",
            f"content query --uri content://sms/inbox --sort 'date DESC' --limit {limit}",
        )
        if "error" in result:
            # Try alternative URI
            result = self._adb(
                "shell",
                f"content query --uri content://sms --sort 'date DESC' --limit {limit}",
            )
        if "error" in result:
            return result
        if not result.get("stdout"):
            return {"messages": [], "count": 0}

        messages = []
        current = {}
        for line in result["stdout"].split("\n"):
            line = line.strip()
            if not line:
                if current:
                    messages.append(current)
                    current = {}
                continue
            # Parse Row: X field=value
            match = re.match(r"Row:\s+\d+\s+(.+)", line)
            if match:
                if current:
                    messages.append(current)
                current = {}
                # Parse key=value pairs in the row
                for kv in re.findall(r"(\w+)=(.+?)(?:\s+\w+=|$)", match.group(1) + " "):
                    key, val = kv[0], kv[1].strip()
                    if val:
                        current[key] = val
                continue
            # Also support multi-line format
            pair = re.match(r"(\w+)=(.+)", line)
            if pair:
                current[pair.group(1)] = pair.group(2).strip()

        if current:
            messages.append(current)

        # If the above parsing yielded nothing useful, try raw
        if not messages:
            messages = [{"raw": result["stdout"]}]

        return {"messages": messages[:limit], "count": min(len(messages), limit)}

    def set_brightness(self, level):
        """Set screen brightness level.

        Args:
            level: Brightness value 0-255 (0=minimum, 255=maximum).

        Returns:
            dict with success/error status.
        """
        if not isinstance(level, int) or level < 0 or level > 255:
            return {"error": "brightness level must be an integer between 0 and 255"}
        result = self._adb(
            "shell",
            f"settings put system screen_brightness {level}",
        )
        if result.get("success"):
            return {"success": True, "level": level}
        return {"error": "failed to set brightness", "raw": result}

    def set_volume(self, stream, level):
        """Set volume level for a given audio stream.

        Args:
            stream: Audio stream name ('music', 'ring', 'alarm',
                    'notification', 'system', 'call').
            level: Volume level (0 to max for that stream, typically 0-15 or 0-7).

        Returns:
            dict with success/error status.
        """
        stream_map = {
            "music": "MUSIC",
            "ring": "RING",
            "alarm": "ALARM",
            "notification": "NOTIFICATION",
            "system": "SYSTEM",
            "call": "VOICE_CALL",
            "dtmf": "DTMF",
            "accessibility": "ACCESSIBILITY",
        }
        stream_upper = stream_map.get(stream.lower())
        if not stream_upper:
            return {
                "error": f"unknown stream '{stream}'. Valid: {', '.join(stream_map.keys())}",
            }
        if not isinstance(level, int) or level < 0:
            return {"error": "level must be a non-negative integer"}
        result = self._adb(
            "shell",
            f"media volume --stream {stream_upper} --set {level}",
        )
        if result.get("success"):
            return {"success": True, "stream": stream, "level": level}
        # Fallback: use service call audio
        result2 = self._adb(
            "shell",
            f"service call audio 7 i32 {level} i32 {['MUSIC', 'RING', 'ALARM', 'NOTIFICATION', 'SYSTEM', 'VOICE_CALL'].index(stream_upper) if stream_upper in ['MUSIC', 'RING', 'ALARM', 'NOTIFICATION', 'SYSTEM', 'VOICE_CALL'] else 0}",
        )
        if result2.get("success"):
            return {"success": True, "stream": stream, "level": level, "method": "service_call"}
        return {"error": "failed to set volume", "raw": result}

    def send_notification(self, title, message):
        """Send an Android notification via termux-notification.

        Args:
            title: Notification title.
            message: Notification body text.

        Returns:
            dict with success/error status.
        """
        safe_title = title.replace("'", "\\'")
        safe_msg = message.replace("'", "\\'")
        termux_check = self._adb("shell", "command -v termux-notification")
        if not termux_check.get("stdout", "").strip():
            return {
                "error": "termux-notification not available. Install Termux:API.",
            }
        result = self._adb(
            "shell",
            f"termux-notification -t '{safe_title}' -c '{safe_msg}'",
        )
        if result.get("success"):
            return {"success": True, "title": title, "message": message}
        return {"error": "failed to send notification", "raw": result}

    def vibrate(self, duration_ms=500):
        """Vibrate the device via termux-vibrate.

        Args:
            duration_ms: Vibration duration in milliseconds (default 500).

        Returns:
            dict with success/error status.
        """
        if not isinstance(duration_ms, (int, float)) or duration_ms < 0:
            return {"error": "duration_ms must be a non-negative number"}
        termux_check = self._adb("shell", "command -v termux-vibrate")
        if not termux_check.get("stdout", "").strip():
            return {"error": "termux-vibrate not available. Install Termux:API."}
        result = self._adb("shell", f"termux-vibrate -d {int(duration_ms)}")
        if result.get("success"):
            return {"success": True, "duration_ms": int(duration_ms)}
        return {"error": "failed to vibrate", "raw": result}

    def control_system(self, action, target=""):
        """Control various device system functions.

        Supported actions:
            - flashlight_on / flashlight_off : Toggle camera flashlight.
            - wifi_on / wifi_off : Enable/disable Wi-Fi.
            - bluetooth_on / bluetooth_off : Enable/disable Bluetooth.
            - mobile_data_on / mobile_data_off : Toggle mobile data.
            - airplane_on / airplane_off : Toggle airplane mode.
            - nfc_on / nfc_off : Toggle NFC.
            - location_on / location_off : Toggle GPS/location.
            - auto_rotate_on / auto_rotate_off : Toggle auto-rotation.
            - wifi_hotspot_on / wifi_hotspot_off : Toggle Wi-Fi hotspot.
            - silent / vibrate / normal : Set ringer mode.

        Args:
            action: One of the supported action strings.
            target: Optional target (unused currently, reserved for future use).

        Returns:
            dict with success/error status.
        """
        action_map = {
            "flashlight_on": "settings put secure torch_state 1",
            "flashlight_off": "settings put secure torch_state 0",
            "wifi_on": "svc wifi enable",
            "wifi_off": "svc wifi disable",
            "bluetooth_on": "svc bluetooth enable",
            "bluetooth_off": "svc bluetooth disable",
            "mobile_data_on": "svc data enable",
            "mobile_data_off": "svc data disable",
            "airplane_on": "settings put global airplane_mode_on 1 && am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true",
            "airplane_off": "settings put global airplane_mode_on 0 && am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false",
            "nfc_on": "svc nfc enable 2>/dev/null || settings put global nfc_on 1",
            "nfc_off": "svc nfc disable 2>/dev/null || settings put global nfc_on 0",
            "location_on": "settings put secure location_providers_allowed +gps,+network",
            "location_off": "settings put secure location_providers_allowed -gps,-network",
            "auto_rotate_on": "settings put system accelerometer_rotation 1",
            "auto_rotate_off": "settings put system accelerometer_rotation 0",
            "silent": "settings put global zen_mode 2",
            "vibrate": "settings put global zen_mode 1",
            "normal": "settings put global zen_mode 0",
        }

        cmd = action_map.get(action.lower())
        if cmd is None:
            return {
                "error": f"unknown action '{action}'. Supported: {', '.join(action_map.keys())}",
            }

        result = self._adb("shell", cmd)
        if result.get("success") or result.get("stdout", "").strip() == "":
            return {"success": True, "action": action}
        return {"error": f"failed to execute {action}", "raw": result}

    def screen_record(self, duration_sec=5):
        """Record the device screen as a video.

        Args:
            duration_sec: Recording duration in seconds (default 5, max 180).

        Returns:
            dict with video file path or error.
        """
        duration_sec = min(max(1, int(duration_sec)), 180)
        video_path = f"/sdcard/screenrecord_{int(time.time())}.mp4"
        # Start recording in background, wait, then stop
        result = self._adb(
            "shell",
            f"screenrecord --time-limit {duration_sec} --verbose {video_path}",
            timeout=duration_sec + 15,
        )
        if result.get("success"):
            return {"path": video_path, "duration_sec": duration_sec}
        # Check if file was created anyway
        check = self._adb("shell", f"ls -l {video_path} 2>/dev/null")
        if check.get("success") and "No such" not in check.get("stdout", ""):
            return {"path": video_path, "duration_sec": duration_sec}
        return {"error": "screen recording failed", "raw": result}

    def detect_arp_spoofing(self):
        """Check the device ARP cache for signs of ARP spoofing (MITM).

        Retrieves the ARP table via ADB and analyzes it for multiple IPs
        sharing the same MAC address (a common spoofing indicator).

        Returns:
            dict with analysis results including suspicious entries.
        """
        result = self._adb("shell", "cat /proc/net/arp 2>/dev/null || ip neigh 2>/dev/null")
        if "error" in result:
            return result
        output = result.get("stdout", "").strip()
        if not output:
            return {"error": "no ARP data available"}

        entries = []
        mac_to_ips = {}
        for line in output.split("\n"):
            # Skip header
            if line.startswith("IP") or "lladdr" in line:
                continue
            parts = line.split()
            if len(parts) >= 4:
                ip = parts[0]
                mac = parts[3] if parts[3] != "(incomplete)" else None
                flags = parts[2] if len(parts) > 2 else "?"
                if mac and re.match(r"([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", mac):
                    entries.append({"ip": ip, "mac": mac, "flags": flags})
                    mac_to_ips.setdefault(mac, []).append(ip)

        suspicious = []
        for mac, ips in mac_to_ips.items():
            if len(ips) > 1:
                suspicious.append({"mac": mac, "ips": ips})

        return {
            "entries": entries,
            "count": len(entries),
            "suspicious": suspicious,
            "spoofing_detected": len(suspicious) > 0,
        }

    def get_system_stats(self):
        """Retrieve battery, charging, RAM, and storage status.

        Returns:
            dict with battery stats, RAM info, and storage info.
        """
        stats = {}

        # Battery
        batt = self._adb("shell", "dumpsys battery")
        if batt.get("stdout"):
            level_match = re.search(r"level:\s*(\d+)", batt["stdout"])
            temp_match = re.search(r"temperature:\s*(\d+)", batt["stdout"])
            voltage_match = re.search(r"voltage:\s*(\d+)", batt["stdout"])
            ac_match = re.search(r"AC powered:\s*(true|false)", batt["stdout"])
            usb_match = re.search(r"USB powered:\s*(true|false)", batt["stdout"])
            wireless_match = re.search(r"Wireless powered:\s*(true|false)", batt["stdout"])
            status_match = re.search(r"status:\s*(\d+)", batt["stdout"])
            health_match = re.search(r"health:\s*(\d+)", batt["stdout"])

            status_map = {
                "1": "unknown",
                "2": "charging",
                "3": "discharging",
                "4": "not_charging",
                "5": "full",
            }
            health_map = {
                "1": "unknown",
                "2": "good",
                "3": "overheat",
                "4": "dead",
                "5": "over_voltage",
                "6": "unspecified_failure",
                "7": "cold",
            }

            stats["battery"] = {
                "level": int(level_match.group(1)) if level_match else None,
                "temperature_celsius": (
                    int(temp_match.group(1)) / 10.0 if temp_match else None
                ),
                "voltage_mv": int(voltage_match.group(1)) if voltage_match else None,
                "charging": (
                    ac_match.group(1) == "true"
                    or usb_match.group(1) == "true"
                    or wireless_match.group(1) == "true"
                ),
                "ac_powered": ac_match.group(1) == "true" if ac_match else False,
                "usb_powered": usb_match.group(1) == "true" if usb_match else False,
                "wireless_powered": wireless_match.group(1) == "true" if wireless_match else False,
                "status": status_map.get(status_match.group(1), "unknown") if status_match else None,
                "health": health_map.get(health_match.group(1), "unknown") if health_match else None,
            }

        # RAM
        meminfo = self._adb("shell", "cat /proc/meminfo 2>/dev/null | grep -E 'MemTotal|MemFree|MemAvailable'")
        if meminfo.get("stdout"):
            total_match = re.search(r"MemTotal:\s*(\d+)", meminfo["stdout"])
            free_match = re.search(r"MemFree:\s*(\d+)", meminfo["stdout"])
            avail_match = re.search(r"MemAvailable:\s*(\d+)", meminfo["stdout"])
            total_kb = int(total_match.group(1)) if total_match else 0
            free_kb = int(free_match.group(1)) if free_match else 0
            avail_kb = int(avail_match.group(1)) if avail_match else 0
            stats["ram"] = {
                "total_kb": total_kb,
                "free_kb": free_kb,
                "available_kb": avail_kb,
                "used_kb": total_kb - free_kb,
                "usage_percent": (
                    round((total_kb - free_kb) / total_kb * 100, 1) if total_kb else 0
                ),
            }

        # Storage
        storage = self._adb("shell", "df -h /sdcard 2>/dev/null || df /sdcard 2>/dev/null")
        if storage.get("stdout"):
            lines = storage["stdout"].strip().split("\n")
            if len(lines) >= 2:
                parts = lines[-1].split()
                if len(parts) >= 4:
                    stats["storage"] = {
                        "filesystem": parts[0],
                        "size": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "use_percent": parts[4] if len(parts) > 4 else None,
                    }

        return stats

    def local_port_scan(self, target_ip, ports):
        """Scan TCP ports on a target IP using /dev/tcp (bash-based port scan).

        Performs a sequential TCP connection test against the specified ports
        without requiring nmap. Useful for local network reconnaissance.

        Args:
            target_ip: Target IP address to scan.
            ports: Single port, comma-separated list (e.g., '22,80,443'),
                   or range (e.g., '1-1024').

        Returns:
            dict with list of open ports or error.
        """
        # Parse ports argument
        if isinstance(ports, int):
            port_list = [ports]
        elif isinstance(ports, str):
            if "-" in ports:
                parts = ports.split("-", 1)
                try:
                    start, end = int(parts[0]), int(parts[1])
                    port_list = list(range(start, end + 1))
                except (ValueError, IndexError):
                    return {"error": f"invalid port range: {ports}"}
            elif "," in ports:
                try:
                    port_list = [int(p.strip()) for p in ports.split(",")]
                except ValueError:
                    return {"error": f"invalid port list: {ports}"}
            else:
                try:
                    port_list = [int(ports)]
                except ValueError:
                    return {"error": f"invalid port: {ports}"}
        elif isinstance(ports, list):
            port_list = [int(p) for p in ports]
        else:
            return {"error": "ports must be int, str, or list"}

        port_list = [p for p in port_list if 1 <= p <= 65535]

        if not port_list:
            return {"error": "no valid ports to scan"}

        # Try nmap first if available on host
        try:
            nmap_result = subprocess.run(
                ["nmap", "-n", "--host-timeout", "5", "-p", ",".join(str(p) for p in port_list), target_ip],
                capture_output=True, text=True, timeout=120,
            )
            if nmap_result.returncode == 0:
                open_ports = re.findall(r"^(\d+)/tcp\s+open", nmap_result.stdout, re.MULTILINE)
                return {
                    "target": target_ip,
                    "open_ports": [int(p) for p in open_ports],
                    "scanned": len(port_list),
                    "method": "nmap",
                }
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: bash /dev/tcp scan via ADB shell (requires bash)
        open_ports = []
        # Scan in batches to avoid long commands
        batch_size = 50
        for i in range(0, len(port_list), batch_size):
            batch = port_list[i : i + batch_size]
            bash_cmd = "for p in " + " ".join(str(p) for p in batch) + f"; do if (</dev/tcp/{target_ip}/$p) 2>/dev/null; then echo OPEN:$p; fi; done 2>/dev/null"
            result = self._adb("shell", bash_cmd)
            if result.get("stdout"):
                for line in result["stdout"].split("\n"):
                    if line.startswith("OPEN:"):
                        try:
                            open_ports.append(int(line.split(":", 1)[1]))
                        except (ValueError, IndexError):
                            pass

        return {
            "target": target_ip,
            "open_ports": open_ports,
            "scanned": len(port_list),
            "method": "dev_tcp",
        }

    def read_sensors(self, sensor_name=""):
        """Read phone sensors via termux-sensor.

        Args:
            sensor_name: Optional sensor name to read (e.g., 'Accelerometer',
                        'Gyroscope', 'Light'). If empty, lists available sensors.

        Returns:
            dict with sensor data or list of available sensors.
        """
        termux_check = self._adb("shell", "command -v termux-sensor")
        if not termux_check.get("stdout", "").strip():
            return {"error": "termux-sensor not available. Install Termux:API."}

        if not sensor_name:
            # List available sensors
            result = self._adb("shell", "termux-sensor -l")
            if result.get("success") and result.get("stdout"):
                try:
                    sensors = json.loads(result["stdout"])
                    return {"sensors": sensors, "count": len(sensors)}
                except json.JSONDecodeError as e:
                    return {"error": f"failed to parse sensor list: {e}"}
            return {"error": "failed to list sensors", "raw": result}

        # Read specific sensor
        safe_sensor = sensor_name.replace("'", "\\'")
        result = self._adb("shell", f"termux-sensor -s '{safe_sensor}' -n 1")
        if not result.get("success") or not result.get("stdout"):
            return {"error": f"failed to read sensor '{sensor_name}'", "raw": result}

        try:
            data = json.loads(result["stdout"])
            return {"sensor": sensor_name, "data": data}
        except json.JSONDecodeError as e:
            return {"error": f"failed to parse sensor data: {e}", "raw": result["stdout"]}


def shlex_quote(s):
    """Simple shell quoting for a single argument (no external dep)."""
    if not s:
        return "''"
    if re.match(r'^[a-zA-Z0-9_./-]+$', s):
        return s
    return "'" + s.replace("'", "'\\''") + "'"


android = AndroidController()
