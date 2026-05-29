from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StoreError(RuntimeError):
    """Raised when the local demo SQLite store cannot be read or written."""


class UnknownChildError(StoreError):
    """Raised when a request references a child id that does not exist."""


DEFAULT_SEED_PATH = Path(__file__).with_name("demo_seed.json")


class DemoStore:
    def __init__(self, path: Path, seed_path: Path = DEFAULT_SEED_PATH):
        self.path = path
        self.seed_path = seed_path
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            return {"children": self._load_children()}

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_schema()
            self._replace_with_seed()
            return {"children": self._load_children()}

    def get_child(self, child_id: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            child = self._load_child(child_id)
            if child is None:
                raise UnknownChildError(f"Unknown child id: {child_id}")
            return child

    def add_session(self, child_id: str, session: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            if self._load_child(child_id) is None:
                raise UnknownChildError(f"Unknown child id: {child_id}")

            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            saved = {
                "id": f"session-{uuid.uuid4().hex[:10]}",
                "created_at": now,
                "published_at": now,
                "status": "published",
                "transcript": session["transcript"],
                "what_we_did": session["what_we_did"],
                "what_changed": session["what_changed"],
                "home_practice": session["home_practice"],
            }
            try:
                with self._connection() as connection:
                    with connection:
                        connection.execute(
                            """
                            INSERT INTO sessions (
                                id, child_id, created_at, published_at, status,
                                transcript, what_we_did, what_changed, home_practice
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                saved["id"],
                                child_id,
                                saved["created_at"],
                                saved["published_at"],
                                saved["status"],
                                saved["transcript"],
                                saved["what_we_did"],
                                saved["what_changed"],
                                saved["home_practice"],
                            ),
                        )
                return saved
            except sqlite3.Error as exc:
                raise StoreError(f"Cannot write SQLite store: {self.path}") from exc

    def add_child(self, profile: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            display_name = str(profile.get("display_name", "")).strip()
            if not display_name:
                raise StoreError("Child display_name is required.")

            goals = profile.get("goals", [])
            if not isinstance(goals, list):
                goals = []
            cleaned_goals = [str(goal).strip() for goal in goals if str(goal).strip()]
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            child = {
                "id": f"child-{uuid.uuid4().hex[:10]}",
                "display_name": display_name,
                "parent_label": f"Родитель: {display_name}",
                "age_label": str(profile.get("age_label", "")).strip(),
                "focus": str(profile.get("focus", "")).strip(),
                "goals": cleaned_goals,
                "sessions": [],
            }
            try:
                with self._connection() as connection:
                    with connection:
                        connection.execute(
                            """
                            INSERT INTO children (
                                id, display_name, parent_label, age_label, focus, goals_json, created_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                child["id"],
                                child["display_name"],
                                child["parent_label"],
                                child["age_label"],
                                child["focus"],
                                json.dumps(child["goals"], ensure_ascii=False),
                                now,
                            ),
                        )
                return child
            except sqlite3.Error as exc:
                raise StoreError(f"Cannot write SQLite store: {self.path}") from exc

    def reset_child_sessions(self, child_id: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            if self._load_child(child_id) is None:
                raise UnknownChildError(f"Unknown child id: {child_id}")
            try:
                with self._connection() as connection:
                    with connection:
                        connection.execute("DELETE FROM sessions WHERE child_id = ?", (child_id,))
                return {"children": self._load_children()}
            except sqlite3.Error as exc:
                raise StoreError(f"Cannot reset child sessions: {self.path}") from exc

    def _ensure_database(self) -> None:
        self._ensure_schema()
        if self._is_empty():
            self._replace_with_seed()

    def _ensure_schema(self) -> None:
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.is_dir():
                    raise StoreError(f"SQLite store path is a directory: {self.path}")
                with self._connection() as connection:
                    with connection:
                        connection.executescript(
                            """
                            CREATE TABLE IF NOT EXISTS children (
                                id TEXT PRIMARY KEY,
                                display_name TEXT NOT NULL,
                                parent_label TEXT NOT NULL,
                                age_label TEXT NOT NULL,
                                focus TEXT NOT NULL,
                                goals_json TEXT NOT NULL,
                                created_at TEXT NOT NULL
                            );

                            CREATE TABLE IF NOT EXISTS sessions (
                                id TEXT PRIMARY KEY,
                                child_id TEXT NOT NULL,
                                created_at TEXT NOT NULL,
                                published_at TEXT NOT NULL,
                                status TEXT NOT NULL,
                                transcript TEXT NOT NULL,
                                what_we_did TEXT NOT NULL,
                                what_changed TEXT NOT NULL,
                                home_practice TEXT NOT NULL,
                                FOREIGN KEY (child_id) REFERENCES children(id) ON DELETE CASCADE
                            );

                            CREATE INDEX IF NOT EXISTS idx_sessions_child_created
                            ON sessions(child_id, created_at);
                            """
                        )
            except StoreError:
                raise
            except sqlite3.Error as exc:
                raise StoreError(f"Cannot initialize SQLite store: {self.path}") from exc

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(self.path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except sqlite3.Error as exc:
            raise StoreError(f"Cannot open SQLite store: {self.path}") from exc

    @contextmanager
    def _connection(self) -> sqlite3.Connection:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _is_empty(self) -> bool:
        try:
            with self._connection() as connection:
                row = connection.execute("SELECT COUNT(*) AS count FROM children").fetchone()
            return int(row["count"]) == 0
        except sqlite3.Error as exc:
            raise StoreError(f"Cannot read SQLite store: {self.path}") from exc

    def _replace_with_seed(self) -> None:
        seed = self._load_seed()
        try:
            with self._connection() as connection:
                with connection:
                    connection.execute("DELETE FROM sessions")
                    connection.execute("DELETE FROM children")
                    for child in seed.get("children", []):
                        connection.execute(
                            """
                            INSERT INTO children (
                                id, display_name, parent_label, age_label, focus, goals_json, created_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                child["id"],
                                child["display_name"],
                                child["parent_label"],
                                child["age_label"],
                                child["focus"],
                                json.dumps(child.get("goals", []), ensure_ascii=False),
                                child.get("created_at", "2026-05-01T00:00:00Z"),
                            ),
                        )
                        for session in child.get("sessions", []):
                            connection.execute(
                                """
                                INSERT INTO sessions (
                                    id, child_id, created_at, published_at, status,
                                    transcript, what_we_did, what_changed, home_practice
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    session["id"],
                                    child["id"],
                                    session["created_at"],
                                    session["published_at"],
                                    session["status"],
                                    session["transcript"],
                                    session["what_we_did"],
                                    session["what_changed"],
                                    session["home_practice"],
                                ),
                            )
        except sqlite3.Error as exc:
            raise StoreError(f"Cannot seed SQLite store: {self.path}") from exc

    def _load_seed(self) -> dict[str, Any]:
        try:
            seed = json.loads(self.seed_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"Cannot read demo seed: {self.seed_path}") from exc
        if not self._is_current_shape(seed):
            raise StoreError(f"Demo seed has invalid shape: {self.seed_path}")
        return seed

    def _load_children(self) -> list[dict[str, Any]]:
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT id, display_name, parent_label, age_label, focus, goals_json
                    FROM children
                    ORDER BY id
                    """
                ).fetchall()
            return [self._row_to_child(row) for row in rows]
        except sqlite3.Error as exc:
            raise StoreError(f"Cannot read SQLite store: {self.path}") from exc

    def _load_child(self, child_id: str) -> dict[str, Any] | None:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    SELECT id, display_name, parent_label, age_label, focus, goals_json
                    FROM children
                    WHERE id = ?
                    """,
                    (child_id,),
                ).fetchone()
            return self._row_to_child(row) if row is not None else None
        except sqlite3.Error as exc:
            raise StoreError(f"Cannot read SQLite store: {self.path}") from exc

    def _row_to_child(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            goals = json.loads(row["goals_json"])
        except json.JSONDecodeError as exc:
            raise StoreError(f"Stored goals are invalid JSON for child: {row['id']}") from exc
        return {
            "id": row["id"],
            "display_name": row["display_name"],
            "parent_label": row["parent_label"],
            "age_label": row["age_label"],
            "focus": row["focus"],
            "goals": goals,
            "sessions": self._load_sessions(row["id"]),
        }

    def _load_sessions(self, child_id: str) -> list[dict[str, Any]]:
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT id, created_at, published_at, status, transcript,
                           what_we_did, what_changed, home_practice
                    FROM sessions
                    WHERE child_id = ?
                    ORDER BY created_at, id
                    """,
                    (child_id,),
                ).fetchall()
            return [
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "published_at": row["published_at"],
                    "status": row["status"],
                    "transcript": row["transcript"],
                    "what_we_did": row["what_we_did"],
                    "what_changed": row["what_changed"],
                    "home_practice": row["home_practice"],
                }
                for row in rows
            ]
        except sqlite3.Error as exc:
            raise StoreError(f"Cannot read SQLite sessions: {self.path}") from exc

    def _is_current_shape(self, data: dict[str, Any]) -> bool:
        children = data.get("children", [])
        if not isinstance(children, list) or len(children) < 2:
            return False
        for child in children:
            if not child.get("parent_label"):
                return False
            if not isinstance(child.get("goals"), list):
                return False
            for session in child.get("sessions", []):
                if not all(session.get(field) for field in ("what_we_did", "what_changed", "home_practice")):
                    return False
        return True
