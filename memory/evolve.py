"""Auto-evolving memory system -- inspired by PocketStrike-AI self-evolution.

After each conversation the system reflects on recent turns and persists
learned facts into three markdown files under ~/agent_memory/:
  - user.md    -- User profile (name, preferences, skills, interests)
  - memory.md  -- Long-term memories, facts, project context
  - agent.md   -- Agent behaviour directives, soul, habits
"""

from __future__ import annotations

import json
import os
import re
import threading
import time

from core.config import config
from core.llm import chat

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MEMORY_DIR = os.path.expanduser("~/agent_memory")
MEMORY_FILES = {
    "user": "user.md",
    "memory": "memory.md",
    "agent": "agent.md",
}

_DEFAULT_CONTENT = {
    "user": """# User Profile

<!-- Preferences, name, skills and interests learned over time -->

""",
    "memory": """# Long-term Memory

<!-- Facts, project context and important details -->

""",
    "agent": """# Agent Directives

<!-- Behaviour rules, soul, habits and style preferences -->

""",
}

# ---------------------------------------------------------------------------
# EvolvingMemory
# ---------------------------------------------------------------------------


class EvolvingMemory:
    """Background thread that periodically reviews conversations and updates
    persistent markdown memory files via an LLM."""

    def __init__(self, evolution_interval: int = 5):
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._evolution_interval = evolution_interval
        self._turn_count = 0
        # Ring-buffer of recent (user, assistant) turns
        self._recent_turns: list[dict[str, str]] = []

        os.makedirs(MEMORY_DIR, exist_ok=True)
        for key in MEMORY_FILES:
            self._ensure_file(key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_turn(self, user_input: str, assistant_response: str) -> None:
        """Log a conversation turn and trigger evolution when enough
        turns have accumulated."""
        with self._lock:
            self._recent_turns.append(
                {"user": user_input, "assistant": assistant_response}
            )
            # Keep a manageable window
            if len(self._recent_turns) > 20:
                self._recent_turns = self._recent_turns[-20:]

            self._turn_count += 1
            if self._turn_count >= self._evolution_interval:
                self._turn_count = 0
                # Spawn evolution in a daemon thread so it never blocks
                # the main conversation flow.
                if self._running:
                    threading.Thread(
                        target=self._run_evolution, daemon=True
                    ).start()

    def start(self) -> None:
        """Start the background keeper thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._evolve_loop, daemon=True)
        self._thread.start()
        print("[Evolve] Background evolution started.")

    def stop(self) -> None:
        """Stop the background keeper thread."""
        self._running = False
        print("[Evolve] Background evolution stopped.")

    def get_system_prompt_extra(self) -> str:
        """Return assembled content of all three memory files, suitable for
        appending to the agent's system prompt."""
        sections: list[str] = []
        for key in ("user", "memory", "agent"):
            content = self._read_file(key).strip()
            if content:
                sections.append(content)
        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Evolution logic
    # ------------------------------------------------------------------

    def _run_evolution(self) -> None:
        """Snapshot the last 4 turns and call evolve_conversation."""
        try:
            with self._lock:
                recent = self._recent_turns[-4:]
            if recent:
                self.evolve_conversation(recent)
        except Exception as exc:
            print(f"[Evolve] Evolution error: {exc}")

    def evolve_conversation(
        self, conversation_history: list[dict[str, str]]
    ) -> None:
        """Take the last N conversation turns, ask the LLM to reflect,
        and merge any changes into the three markdown files."""
        current_user = self._read_file("user")
        current_memory = self._read_file("memory")
        current_agent = self._read_file("agent")

        prompt = self._build_evolution_prompt(
            conversation_history, current_user, current_memory, current_agent
        )

        model = config.get("llm", "model")
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a memory evolution system. Analyse conversations "
                    "and update memory files. Always respond with valid JSON "
                    "only, wrapped in ```json ... ```."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        raw = chat(messages, model=model)
        if isinstance(raw, dict):
            content = raw.get("message", {}).get("content", "")
        else:
            content = str(raw)

        updates = self._parse_json_response(content)

        if "user" in updates:
            self._merge_update("user", updates["user"])
        if "memory" in updates:
            self._merge_update("memory", updates["memory"])
        if "agent" in updates:
            self._merge_update("agent", updates["agent"])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_file(self, key: str) -> None:
        path = os.path.join(MEMORY_DIR, MEMORY_FILES[key])
        if not os.path.exists(path):
            with open(path, "w") as fh:
                fh.write(_DEFAULT_CONTENT[key])

    def _read_file(self, key: str) -> str:
        path = os.path.join(MEMORY_DIR, MEMORY_FILES[key])
        with open(path) as fh:
            return fh.read()

    def _write_file(self, key: str, content: str) -> None:
        path = os.path.join(MEMORY_DIR, MEMORY_FILES[key])
        with open(path, "w") as fh:
            fh.write(content)

    @staticmethod
    def _build_evolution_prompt(
        history: list[dict[str, str]],
        current_user: str,
        current_memory: str,
        current_agent: str,
    ) -> str:
        turns_text = "\n".join(
            f"User: {t['user']}\nAssistant: {t['assistant']}"
            for t in history
        )

        return f"""Analyse the recent conversation and determine whether the three memory files need updating.

RECENT CONVERSATION:
{turns_text}

--- CURRENT user.md ---
{current_user}

--- CURRENT memory.md ---
{current_memory}

--- CURRENT agent.md ---
{current_agent}

Based *only* on the conversation above, decide if anything changed about the user, new facts were discovered, or behaviour directives should be adjusted.

Respond **exclusively** with a JSON object wrapped in ```json ... ```. Only include keys for files that need changes. Never remove existing information unless the conversation explicitly contradicts it. Add new information as natural markdown.

Format:
```json
{{
    "user": {{
        "append": "New markdown content to add to user.md\\n"
    }},
    "memory": {{
        "append": "New markdown content to add to memory.md\\n"
    }},
    "agent": {{
        "append": "New markdown content to add to agent.md\\n"
    }}
}}
```

If nothing changed, respond with an empty JSON object: {{}}"""

    @staticmethod
    def _parse_json_response(content: str) -> dict:
        """Extract a JSON object from the LLM output, tolerating
        ```json fences and stray text."""
        # 1) Try to find ```json ... ``` block
        m = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL
        )
        if m:
            content = m.group(1)

        content = content.strip()

        # 2) Direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 3) Fallback: locate outermost { ... }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                pass

        print(f"[Evolve] Could not parse JSON from LLM:\n{content[:500]}")
        return {}

    def _merge_update(self, key: str, update: dict | str) -> None:
        """Merge a partial update into the on-disk markdown file.

        *update* can be:
        - ``{"append": "..."}``  -- text appended after existing content
        - ``{"replace": "..."}`` -- full replacement
        - a plain string         -- treated as append
        """
        current = self._read_file(key)

        if isinstance(update, dict):
            if "append" in update:
                addition = update["append"].strip()
                if addition:
                    current = current.rstrip() + "\n\n" + addition + "\n"
            if "replace" in update:
                current = update["replace"]
        elif isinstance(update, str):
            addition = update.strip()
            if addition:
                current = current.rstrip() + "\n\n" + addition + "\n"

        self._write_file(key, current)

    # ------------------------------------------------------------------
    # Background loop (keeper)
    # ------------------------------------------------------------------

    def _evolve_loop(self) -> None:
        """Low-frequency keeper thread.  The actual evolution is triggered
        from ``record_turn``, so this loop mainly exists to keep the
        thread alive and provide a heartbeat."""
        while self._running:
            time.sleep(30)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

evolving_memory = EvolvingMemory()
