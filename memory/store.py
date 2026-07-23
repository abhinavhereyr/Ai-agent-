"""Memory system - SQLite-based persistent storage."""
import json
import os
import sqlite3
import time
from pathlib import Path

from core.config import config


class MemoryStore:
    def __init__(self, db_path=None):
        raw = db_path or config.get("memory", "db_path")
        self.db_path = os.path.expanduser(raw)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                session_id TEXT
            );
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created REAL NOT NULL,
                updated REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                created REAL NOT NULL,
                completed REAL,
                result TEXT
            );
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voice_text TEXT NOT NULL,
                action TEXT,
                success INTEGER DEFAULT 0,
                timestamp REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS embeddings_cache (
                text_hash TEXT PRIMARY KEY,
                embedding BLOB,
                model TEXT,
                timestamp REAL
            );
        """)
        self.conn.commit()

    # --- Conversations ---
    def add_message(self, role, content, session_id=None):
        self.conn.execute(
            "INSERT INTO conversations (role, content, timestamp, session_id) VALUES (?,?,?,?)",
            (role, content, time.time(), session_id),
        )
        self.conn.commit()
        # Trim old history
        max_h = config.get("memory", "max_history")
        self.conn.execute(
            "DELETE FROM conversations WHERE id NOT IN (SELECT id FROM conversations ORDER BY id DESC LIMIT ?)",
            (max_h,),
        )
        self.conn.commit()

    def get_history(self, limit=50, session_id=None):
        if session_id:
            cur = self.conn.execute(
                "SELECT role, content FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            )
        else:
            cur = self.conn.execute(
                "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()[::-1]
        return [{"role": r[0], "content": r[1]} for r in rows]

    def clear_history(self, session_id=None):
        if session_id:
            self.conn.execute("DELETE FROM conversations WHERE session_id=?", (session_id,))
        else:
            self.conn.execute("DELETE FROM conversations")
        self.conn.commit()

    # --- Facts (persistent knowledge) ---
    def remember(self, key, value, category="general"):
        now = time.time()
        self.conn.execute(
            "INSERT INTO facts (key, value, category, created, updated) VALUES (?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, category=excluded.category, updated=excluded.updated",
            (key, value, category, now, now),
        )
        self.conn.commit()

    def recall(self, key):
        cur = self.conn.execute("SELECT value FROM facts WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def recall_by_category(self, category):
        cur = self.conn.execute(
            "SELECT key, value FROM facts WHERE category=? ORDER BY updated DESC", (category,)
        )
        return dict(cur.fetchall())

    def forget(self, key):
        self.conn.execute("DELETE FROM facts WHERE key=?", (key,))
        self.conn.commit()

    def search_facts(self, query):
        cur = self.conn.execute(
            "SELECT key, value, category FROM facts WHERE key LIKE ? OR value LIKE ? LIMIT 20",
            (f"%{query}%", f"%{query}%"),
        )
        return [{"key": r[0], "value": r[1], "category": r[2]} for r in cur.fetchall()]

    # --- Tasks ---
    def add_task(self, description, priority=0):
        c = self.conn.execute(
            "INSERT INTO tasks (description, priority, created) VALUES (?,?,?)",
            (description, priority, time.time()),
        )
        self.conn.commit()
        return c.lastrowid

    def update_task(self, task_id, status, result=None):
        now = time.time()
        if result:
            self.conn.execute(
                "UPDATE tasks SET status=?, result=?, completed=? WHERE id=?",
                (status, result, now if status == "completed" else None, task_id),
            )
        else:
            self.conn.execute(
                "UPDATE tasks SET status=?, completed=? WHERE id=?",
                (status, now if status == "completed" else None, task_id),
            )
        self.conn.commit()

    def get_pending_tasks(self):
        cur = self.conn.execute(
            "SELECT id, description, priority, created FROM tasks WHERE status='pending' ORDER BY priority DESC, created ASC"
        )
        return [{"id": r[0], "description": r[1], "priority": r[2], "created": r[3]} for r in cur.fetchall()]

    # --- Commands ---
    def log_command(self, voice_text, action=None, success=0):
        self.conn.execute(
            "INSERT INTO commands (voice_text, action, success, timestamp) VALUES (?,?,?,?)",
            (voice_text, action, success, time.time()),
        )
        self.conn.commit()

    # --- Close ---
    def close(self):
        self.conn.close()


memory = MemoryStore()
