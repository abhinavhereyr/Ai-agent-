"""Task scheduler - run tasks on a schedule or trigger."""
import asyncio
import datetime
import json
import threading
import time
import re

from memory.store import memory


class TaskScheduler:
    """Simple task scheduler for the agent."""

    def __init__(self):
        self._tasks = {}
        self._running = False
        self._thread = None

    def add_recurring(self, name, interval_seconds, callback, description=""):
        """Add a recurring task."""
        self._tasks[name] = {
            "type": "recurring",
            "interval": interval_seconds,
            "callback": callback,
            "description": description,
            "last_run": None,
            "next_run": time.time() + interval_seconds,
        }
        return name

    def add_scheduled(self, name, run_at_timestamp, callback, description=""):
        """Add a one-time scheduled task."""
        self._tasks[name] = {
            "type": "scheduled",
            "run_at": run_at_timestamp,
            "callback": callback,
            "description": description,
            "last_run": None,
        }
        return name

    def add_cron(self, name, cron_expression, callback, description=""):
        """Add a cron-like task (minute granularity)."""
        self._tasks[name] = {
            "type": "cron",
            "cron": cron_expression,
            "callback": callback,
            "description": description,
            "last_run": None,
        }
        return name

    def remove(self, name):
        """Remove a task."""
        return self._tasks.pop(name, None)

    def list_tasks(self):
        """List all scheduled tasks."""
        result = {}
        for name, task in self._tasks.items():
            info = {
                "type": task["type"],
                "description": task["description"],
                "last_run": task.get("last_run"),
            }
            if task["type"] == "recurring":
                info["interval"] = task["interval"]
                info["next_run"] = task.get("next_run")
            elif task["type"] == "scheduled":
                info["run_at"] = task.get("run_at")
            elif task["type"] == "cron":
                info["cron"] = task.get("cron")
            result[name] = info
        return result

    def _matches_cron(self, cron_expr, now):
        """Simple cron matching (minute hour day month weekday)."""
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return False

        minute, hour, day, month, weekday = parts
        t = time.localtime(now)

        def match_field(field, value):
            if field == "*":
                return True
            if "," in field:
                return value in [int(x) for x in field.split(",")]
            if "-" in field:
                a, b = [int(x) for x in field.split("-")]
                return a <= value <= b
            return int(field) == value

        return (match_field(minute, t.tm_min) and
                match_field(hour, t.tm_hour) and
                match_field(day, t.tm_mday) and
                match_field(month, t.tm_mon) and
                match_field(weekday, t.tm_wday))

    def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            now = time.time()
            for name, task in list(self._tasks.items()):
                should_run = False

                if task["type"] == "recurring":
                    if task.get("next_run") and now >= task["next_run"]:
                        should_run = True
                        task["next_run"] = now + task["interval"]

                elif task["type"] == "scheduled":
                    if task.get("run_at") and now >= task["run_at"]:
                        should_run = True
                        # One-shot: remove after run
                        self.remove(name)

                elif task["type"] == "cron":
                    should_run = self._matches_cron(task["cron"], now)

                if should_run:
                    try:
                        task["callback"]()
                        task["last_run"] = now
                    except Exception as e:
                        print(f"[Scheduler] Task '{name}' failed: {e}")

            time.sleep(30)  # Check every 30 seconds

    def start(self):
        """Start the scheduler."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"[Scheduler] Started with {len(self._tasks)} tasks")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[Scheduler] Stopped")


scheduler = TaskScheduler()
