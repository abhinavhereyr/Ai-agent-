"""Telegram bot for remote AI Agent control via polling.

Uses manual polling (no webhooks, no python-telegram-bot dependency).
All methods are safe no-ops when bot_token is empty or "disabled".
"""
import logging
import threading
import time

import requests

from core.config import config
from core.engine import engine

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramBot:
    """Telegram bot for remote agent control.

    Reads configuration from config section ``telegram``:
        bot_token (str): Telegram Bot API token.
        allowed_chat_ids (list[int], optional): Whitelist of chat IDs.
            Empty list means all chats are allowed.

    Runs a background polling thread that forwards every incoming text
    message to ``engine.process_text()`` and sends the reply back.
    """

    def __init__(self, config_section=None):
        """Initialise bot from *config_section* (default: config["telegram"])."""
        self.cfg = config.get("telegram", default={}) if config_section is None else config_section
        self.bot_token = self.cfg.get("bot_token", "") or ""
        self.allowed_chat_ids = self.cfg.get("allowed_chat_ids", []) or []
        self.last_update_id = 0
        self._thread: threading.Thread | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _enabled(self) -> bool:
        """Return True when a real token is configured."""
        token = self.bot_token.strip()
        return bool(token) and token.lower() != "disabled"

    def _api_url(self, method: str) -> str:
        """Full URL for a Telegram API *method* (e.g. ``getUpdates``)."""
        return f"{_API_BASE.format(token=self.bot_token)}/{method}"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start bot polling in a daemon background thread."""
        if not self._enabled:
            logger.info("Telegram bot disabled (bot_token empty or 'disabled')")
            return
        if self._running:
            logger.warning("Telegram bot already running")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="telegram-bot",
        )
        self._thread.start()
        logger.info("Telegram bot polling started")

    def stop(self):
        """Signal the polling thread to exit (non-blocking)."""
        self._running = False
        logger.info("Telegram bot stopping")

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def _poll_loop(self):
        """Background loop: long-poll ``getUpdates`` and handle messages."""
        while self._running:
            try:
                url = self._api_url("getUpdates")
                params = {
                    "timeout": 30,
                    "offset": self.last_update_id + 1,
                }
                resp = requests.get(url, params=params, timeout=35)
                if resp.status_code != 200:
                    logger.warning(
                        "Telegram API returned HTTP %d: %s",
                        resp.status_code,
                        resp.text[:200],
                    )
                    time.sleep(5)
                    continue

                data = resp.json()
                if not data.get("ok"):
                    logger.warning("Telegram API error: %s", data.get("description", "unknown"))
                    time.sleep(5)
                    continue

                for update in data.get("result", []):
                    self.last_update_id = max(
                        self.last_update_id,
                        update.get("update_id", 0),
                    )
                    if "message" in update:
                        self._handle_message(update["message"])

            except requests.exceptions.Timeout:
                # Long-poll timeouts are expected -- just loop again.
                continue
            except requests.exceptions.ConnectionError:
                logger.warning("Telegram: connection refused, retrying in 5 s")
                time.sleep(5)
            except Exception:
                logger.exception("Telegram: unexpected error in poll loop")
                time.sleep(2)

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    def _handle_message(self, message: dict):
        """Process a single Telegram message.

        * Checks ``chat_id`` against the allowlist.
        * Forwards ``text`` to ``engine.process_text()``.
        * Sends the reply back via ``send_message``.
        """
        chat_id = (message.get("chat") or {}).get("id")
        text = (message.get("text") or "").strip()

        if not chat_id:
            return

        # --- Authorisation --------------------------------------------
        if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
            logger.warning("Rejected message from unauthorized chat_id %s", chat_id)
            self.send_message(
                chat_id,
                "Unauhorized. You are not allowed to control this agent.",
            )
            return

        # Skip non-text messages (stickers, photos, etc.)
        if not text:
            return

        logger.info("Telegram message from %s: %.80s", chat_id, text)
        self.send_action(chat_id, "typing")

        # --- Process ------------------------------------------------
        try:
            response = engine.process_text(text)
            reply = str(response) if response is not None else "Done."
        except Exception:
            logger.exception("Telegram: engine.process_text() failed")
            reply = "Sorry, an internal error occurred while processing your message."

        self.send_message(chat_id, reply)

    # ------------------------------------------------------------------
    # Outgoing API calls
    # ------------------------------------------------------------------

    def send_message(self, chat_id: int, text: str):
        """Send a text message via ``sendMessage``."""
        if not self._enabled:
            return
        try:
            url = self._api_url("sendMessage")
            payload = {
                "chat_id": chat_id,
                "text": str(text),
                "parse_mode": "Markdown",
            }
            requests.post(url, json=payload, timeout=10)
        except Exception:
            logger.exception("Telegram: send_message failed")

    def send_action(self, chat_id: int, action: str = "typing"):
        """Send a chat action (typing, upload_photo, etc.)."""
        if not self._enabled:
            return
        try:
            url = self._api_url("sendChatAction")
            payload = {
                "chat_id": chat_id,
                "action": action,
            }
            requests.post(url, json=payload, timeout=5)
        except Exception:
            logger.exception("Telegram: send_action failed")
