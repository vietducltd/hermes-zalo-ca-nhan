"""Trạng thái vận hành lưu trong SQLite của profile.

Chỉ lưu ID và mốc thời gian: chống xử lý trùng, danh bạ đã thấy, ai đang tạm dừng,
tin nào do bot gửi. Không lưu nội dung tin nhắn hay cookie.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

KEEP_SECONDS = 7 * 24 * 60 * 60
EVERYONE = "*"

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (msg_id TEXT PRIMARY KEY, at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sent (msg_id TEXT PRIMARY KEY, at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS contacts (
    thread_id TEXT NOT NULL, kind TEXT NOT NULL, user_id TEXT NOT NULL,
    name TEXT NOT NULL, at INTEGER NOT NULL,
    PRIMARY KEY (thread_id, user_id)
);
CREATE TABLE IF NOT EXISTS pauses (
    thread_id TEXT NOT NULL, user_id TEXT NOT NULL, until INTEGER NOT NULL,
    PRIMARY KEY (thread_id, user_id)
);
"""


class StateDB:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self._prune()

    def _prune(self) -> None:
        now = int(time.time())
        self.db.execute("DELETE FROM seen WHERE at < ?", (now - KEEP_SECONDS,))
        self.db.execute("DELETE FROM sent WHERE at < ?", (now - KEEP_SECONDS,))
        self.db.execute("DELETE FROM pauses WHERE until <= ?", (now,))
        self.db.commit()

    def first_time(self, msg_id: str) -> bool:
        """True nếu tin này chưa từng được xử lý (Zalo đôi khi phát lại cùng một tin)."""
        if not msg_id:
            return True
        cursor = self.db.execute("INSERT OR IGNORE INTO seen (msg_id, at) VALUES (?, ?)", (msg_id, int(time.time())))
        self.db.commit()
        return cursor.rowcount == 1

    def mark_sent(self, msg_id: str) -> None:
        if msg_id:
            self.db.execute("INSERT OR REPLACE INTO sent (msg_id, at) VALUES (?, ?)", (msg_id, int(time.time())))
            self.db.commit()

    def was_sent(self, msg_id: str) -> bool:
        return bool(msg_id) and self.db.execute("SELECT 1 FROM sent WHERE msg_id = ?", (msg_id,)).fetchone() is not None

    def remember_contact(self, thread_id: str, kind: str, user_id: str, name: str) -> None:
        self.db.execute(
            "INSERT INTO contacts (thread_id, kind, user_id, name, at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (thread_id, user_id) DO UPDATE SET kind = excluded.kind, name = excluded.name, at = excluded.at",
            (thread_id, kind, user_id, name or "(không rõ)", int(time.time())),
        )
        self.db.commit()

    def contacts(self) -> list[tuple[str, str, str, str, int]]:
        return self.db.execute("SELECT thread_id, kind, user_id, name, at FROM contacts ORDER BY at DESC").fetchall()

    def kind_of(self, thread_id: str) -> str | None:
        row = self.db.execute("SELECT kind FROM contacts WHERE thread_id = ? LIMIT 1", (thread_id,)).fetchone()
        return row[0] if row else None

    def pause(self, thread_id: str, user_id: str, seconds: int) -> None:
        self.db.execute(
            "INSERT INTO pauses (thread_id, user_id, until) VALUES (?, ?, ?) "
            "ON CONFLICT (thread_id, user_id) DO UPDATE SET until = excluded.until",
            (thread_id, user_id, int(time.time()) + int(seconds)),
        )
        self.db.commit()

    def is_paused(self, thread_id: str, user_id: str) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM pauses WHERE thread_id = ? AND user_id IN (?, ?) AND until > ? LIMIT 1",
            (thread_id, user_id, EVERYONE, int(time.time())),
        ).fetchone()
        return row is not None

    def resume(self, thread_id: str, user_id: str) -> None:
        self.db.execute("DELETE FROM pauses WHERE thread_id = ? AND user_id IN (?, ?)", (thread_id, user_id, EVERYONE))
        self.db.commit()

    def close(self) -> None:
        self.db.close()
