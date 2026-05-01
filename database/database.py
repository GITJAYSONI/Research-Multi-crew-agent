import json
import sqlite3
from pathlib import Path
from typing import Any


class ResearchDatabase:
    """SQLite persistence for users, threads, messages, sources, reports, and claim checks."""

    def __init__(self, path: str | Path = "research_memory.db"):
        self.path = Path(path)
        self._memory_connection: sqlite3.Connection | None = None
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        if str(self.path) == ":memory:":
            if self._memory_connection is None:
                self._memory_connection = sqlite3.connect(":memory:")
                self._memory_connection.row_factory = sqlite3.Row
                self._memory_connection.execute("PRAGMA foreign_keys = ON")
            return self._memory_connection

        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def init_db(self) -> None:
        try:
            with self.connect() as db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE,
                        password_hash TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS threads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        title TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    );

                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        thread_id INTEGER NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (thread_id) REFERENCES threads(id)
                    );

                    CREATE TABLE IF NOT EXISTS sources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        thread_id INTEGER NOT NULL,
                        title TEXT,
                        url TEXT,
                        publisher TEXT,
                        trust_score REAL,
                        snippet TEXT,
                        FOREIGN KEY (thread_id) REFERENCES threads(id)
                    );

                    CREATE TABLE IF NOT EXISTS reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        thread_id INTEGER NOT NULL,
                        final_answer TEXT NOT NULL,
                        quality_score INTEGER,
                        confidence TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (thread_id) REFERENCES threads(id)
                    );

                    CREATE TABLE IF NOT EXISTS claim_checks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        report_id INTEGER NOT NULL,
                        claim TEXT,
                        status TEXT,
                        citations TEXT,
                        support_ratio REAL,
                        FOREIGN KEY (report_id) REFERENCES reports(id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id);
                    CREATE INDEX IF NOT EXISTS idx_threads_user_id ON threads(user_id);
                    CREATE INDEX IF NOT EXISTS idx_sources_thread_id ON sources(thread_id);
                    CREATE INDEX IF NOT EXISTS idx_reports_thread_id ON reports(thread_id);
                    CREATE INDEX IF NOT EXISTS idx_claim_checks_report_id ON claim_checks(report_id);
                    """
                )
        except sqlite3.Error as exc:
            print(f"Database initialization failed: {exc}")

    def create_user(self, email: str, password_hash: str = "") -> int | None:
        try:
            with self.connect() as db:
                cursor = db.execute(
                    "INSERT OR IGNORE INTO users (email, password_hash) VALUES (?, ?)",
                    (email, password_hash),
                )
                if cursor.lastrowid:
                    return int(cursor.lastrowid)
                row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                return int(row["id"]) if row else None
        except sqlite3.Error as exc:
            print(f"Could not create user: {exc}")
            return None

    def create_thread(self, user_id: int, title: str) -> int | None:
        try:
            with self.connect() as db:
                cursor = db.execute(
                    "INSERT INTO threads (user_id, title) VALUES (?, ?)",
                    (user_id, title[:120] or "New research thread"),
                )
                return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            print(f"Could not create thread: {exc}")
            return None

    def touch_thread(self, thread_id: int) -> None:
        try:
            with self.connect() as db:
                db.execute(
                    "UPDATE threads SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (thread_id,),
                )
        except sqlite3.Error as exc:
            print(f"Could not update thread timestamp: {exc}")

    def save_message(self, thread_id: int, role: str, content: str) -> bool:
        try:
            with self.connect() as db:
                db.execute(
                    "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
                    (thread_id, role, content),
                )
            self.touch_thread(thread_id)
            return True
        except sqlite3.Error as exc:
            print(f"Could not save message: {exc}")
            return False

    def load_messages(self, thread_id: int, limit: int = 50) -> list[dict[str, str]]:
        try:
            with self.connect() as db:
                rows = db.execute(
                    """
                    SELECT role, content
                    FROM messages
                    WHERE thread_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (thread_id, limit),
                ).fetchall()
            return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
        except sqlite3.Error as exc:
            print(f"Could not load messages: {exc}")
            return []

    def list_threads(self, user_id: int) -> list[dict[str, Any]]:
        try:
            with self.connect() as db:
                rows = db.execute(
                    "SELECT * FROM threads WHERE user_id = ? ORDER BY updated_at DESC",
                    (user_id,),
                ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            print(f"Could not list threads: {exc}")
            return []

    def thread_belongs_to_user(self, thread_id: int, user_id: int) -> bool:
        try:
            with self.connect() as db:
                row = db.execute(
                    "SELECT 1 FROM threads WHERE id = ? AND user_id = ?",
                    (thread_id, user_id),
                ).fetchone()
            return row is not None
        except sqlite3.Error as exc:
            print(f"Could not verify thread ownership: {exc}")
            return False

    def save_sources(self, thread_id: int, source_cards: list[dict]) -> bool:
        try:
            with self.connect() as db:
                for source in source_cards:
                    snippets = source.get("exact_snippets", [])
                    db.execute(
                        """
                        INSERT INTO sources
                            (thread_id, title, url, publisher, trust_score, snippet)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            thread_id,
                            source.get("title", ""),
                            source.get("url", ""),
                            source.get("publisher", ""),
                            source.get("trust_score", 0),
                            snippets[0] if snippets else "",
                        ),
                    )
            return True
        except sqlite3.Error as exc:
            print(f"Could not save sources: {exc}")
            return False

    def save_report(
        self,
        thread_id: int,
        final_answer: str,
        quality_score: int | None,
        confidence: str,
    ) -> int | None:
        try:
            with self.connect() as db:
                cursor = db.execute(
                    """
                    INSERT INTO reports
                        (thread_id, final_answer, quality_score, confidence)
                    VALUES (?, ?, ?, ?)
                    """,
                    (thread_id, final_answer, quality_score, confidence),
                )
                return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            print(f"Could not save report: {exc}")
            return None

    def save_claim_checks(self, report_id: int, claims: list[dict]) -> bool:
        try:
            with self.connect() as db:
                for claim in claims:
                    db.execute(
                        """
                        INSERT INTO claim_checks
                            (report_id, claim, status, citations, support_ratio)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            report_id,
                            claim.get("claim", ""),
                            claim.get("status", ""),
                            json.dumps(claim.get("citations", [])),
                            claim.get("support_ratio", 0),
                        ),
                    )
            return True
        except sqlite3.Error as exc:
            print(f"Could not save claim checks: {exc}")
            return False
