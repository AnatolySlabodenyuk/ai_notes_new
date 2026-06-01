from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


class StoreError(RuntimeError):
    """Raised when the local demo SQLite store cannot be read or written."""


SCHEMA_VERSION = 3
DEFAULT_SEED_PATH = Path(__file__).with_name("demo_seed.json")
VISIT_STATUSES = {"scheduled", "completed", "partial", "cancelled", "absent", "rescheduled"}
GOAL_STATUSES = {"active", "progress", "achieved", "paused"}


class DemoStore:
    def __init__(self, path: Path, seed_path: Path = DEFAULT_SEED_PATH):
        self.path = path
        self.seed_path = seed_path
        self._lock = threading.RLock()

    def load_journal_data(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            try:
                with self._connection() as connection:
                    child = connection.execute(
                        "SELECT id, display_name, age_label, focus FROM children ORDER BY id LIMIT 1"
                    ).fetchone()
                    directions = connection.execute(
                        """
                        SELECT d.id, d.slug, d.title, d.color, d.sort_order
                        FROM directions d
                                 JOIN child_directions cd ON cd.direction_id = d.id
                        WHERE cd.child_id = ?
                        ORDER BY d.sort_order, d.id
                        """,
                        (child["id"],),
                    ).fetchall()
                    visits = connection.execute(
                        """
                        SELECT id,
                               child_id,
                               direction_id,
                               scheduled_start,
                               scheduled_end,
                               actual_start,
                               actual_end,
                               status,
                               reason_code,
                               rescheduled_to_visit_id
                        FROM visits
                        WHERE child_id = ?
                        ORDER BY scheduled_start, id
                        """,
                        (child["id"],),
                    ).fetchall()
                    goals = connection.execute(
                        """
                        SELECT id,
                               child_id,
                               direction_id,
                               title,
                               description,
                               status,
                               metric_label,
                               metric_target,
                               sort_order
                        FROM goals
                        WHERE child_id = ?
                        ORDER BY direction_id, sort_order, id
                        """,
                        (child["id"],),
                    ).fetchall()
                    goal_updates = connection.execute(
                        """
                        SELECT gu.id, gu.goal_id, gu.updated_at, gu.status, gu.comment, gu.metric_value
                        FROM goal_updates gu
                                 JOIN goals g ON g.id = gu.goal_id
                        WHERE g.child_id = ?
                        ORDER BY gu.updated_at, gu.id
                        """,
                        (child["id"],),
                    ).fetchall()
                return {
                    "child": dict(child),
                    "directions": [dict(row) for row in directions],
                    "visits": [dict(row) for row in visits],
                    "goals": [dict(row) for row in goals],
                    "goal_updates": [dict(row) for row in goal_updates],
                }
            except sqlite3.Error as exc:
                raise StoreError(f"Cannot read SQLite store: {self.path}") from exc

    def reset(self) -> None:
        with self._lock:
            self._recreate_from_seed()

    def _ensure_database(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.is_dir():
            raise StoreError(f"SQLite store path is a directory: {self.path}")
        if not self._has_current_schema():
            self._recreate_from_seed()

    def _has_current_schema(self) -> bool:
        if not self.path.exists():
            return False
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT version FROM schema_meta ORDER BY version DESC LIMIT 1"
                ).fetchone()
            return row is not None and int(row["version"]) == SCHEMA_VERSION
        except sqlite3.Error:
            return False

    def _recreate_from_seed(self) -> None:
        seed = self._load_seed()
        try:
            with self._connection() as connection:
                with connection:
                    connection.executescript(
                        """
                        DROP TABLE IF EXISTS goal_updates;
                        DROP TABLE IF EXISTS goals;
                        DROP TABLE IF EXISTS visits;
                        DROP TABLE IF EXISTS child_directions;
                        DROP TABLE IF EXISTS directions;
                        DROP TABLE IF EXISTS sessions;
                        DROP TABLE IF EXISTS children;
                        DROP TABLE IF EXISTS schema_meta;

                        CREATE TABLE schema_meta
                        (
                            version INTEGER NOT NULL
                        );
                        CREATE TABLE children
                        (
                            id           TEXT PRIMARY KEY,
                            display_name TEXT NOT NULL,
                            age_label    TEXT NOT NULL,
                            focus        TEXT NOT NULL
                        );
                        CREATE TABLE directions
                        (
                            id         TEXT PRIMARY KEY,
                            slug       TEXT    NOT NULL UNIQUE,
                            title      TEXT    NOT NULL,
                            color      TEXT    NOT NULL,
                            sort_order INTEGER NOT NULL
                        );
                        CREATE TABLE child_directions
                        (
                            child_id     TEXT NOT NULL,
                            direction_id TEXT NOT NULL,
                            PRIMARY KEY (child_id, direction_id),
                            FOREIGN KEY (child_id) REFERENCES children (id) ON DELETE CASCADE,
                            FOREIGN KEY (direction_id) REFERENCES directions (id) ON DELETE CASCADE
                        );
                        CREATE TABLE visits
                        (
                            id                      TEXT PRIMARY KEY,
                            child_id                TEXT NOT NULL,
                            direction_id            TEXT NOT NULL,
                            scheduled_start         TEXT NOT NULL,
                            scheduled_end           TEXT NOT NULL,
                            actual_start            TEXT,
                            actual_end              TEXT,
                            status                  TEXT NOT NULL,
                            reason_code             TEXT,
                            rescheduled_to_visit_id TEXT,
                            FOREIGN KEY (child_id) REFERENCES children (id) ON DELETE CASCADE,
                            FOREIGN KEY (direction_id) REFERENCES directions (id) ON DELETE CASCADE,
                            FOREIGN KEY (rescheduled_to_visit_id) REFERENCES visits (id)
                        );
                        CREATE TABLE goals
                        (
                            id            TEXT PRIMARY KEY,
                            child_id      TEXT    NOT NULL,
                            direction_id  TEXT    NOT NULL,
                            title         TEXT    NOT NULL,
                            description   TEXT    NOT NULL,
                            status        TEXT    NOT NULL,
                            metric_label  TEXT,
                            metric_target REAL,
                            sort_order    INTEGER NOT NULL,
                            FOREIGN KEY (child_id) REFERENCES children (id) ON DELETE CASCADE,
                            FOREIGN KEY (direction_id) REFERENCES directions (id) ON DELETE CASCADE
                        );
                        CREATE TABLE goal_updates
                        (
                            id           TEXT PRIMARY KEY,
                            goal_id      TEXT NOT NULL,
                            updated_at   TEXT NOT NULL,
                            status       TEXT NOT NULL,
                            comment      TEXT NOT NULL,
                            metric_value REAL,
                            FOREIGN KEY (goal_id) REFERENCES goals (id) ON DELETE CASCADE
                        );
                        CREATE INDEX idx_visits_child_scheduled ON visits (child_id, scheduled_start);
                        CREATE INDEX idx_goals_child_direction ON goals (child_id, direction_id);
                        CREATE INDEX idx_goal_updates_goal_updated ON goal_updates (goal_id, updated_at);
                        """
                    )
                    connection.execute("INSERT INTO schema_meta (version) VALUES (?)", (SCHEMA_VERSION,))
                    self._insert_seed(connection, seed)
        except sqlite3.Error as exc:
            raise StoreError(f"Cannot initialize SQLite store: {self.path}") from exc

    def _insert_seed(self, connection: sqlite3.Connection, seed: dict[str, Any]) -> None:
        connection.executemany(
            "INSERT INTO children (id, display_name, age_label, focus) VALUES (?, ?, ?, ?)",
            [
                (item["id"], item["display_name"], item["age_label"], item["focus"])
                for item in seed["children"]
            ],
        )
        connection.executemany(
            "INSERT INTO directions (id, slug, title, color, sort_order) VALUES (?, ?, ?, ?, ?)",
            [
                (item["id"], item["slug"], item["title"], item["color"], item["sort_order"])
                for item in seed["directions"]
            ],
        )
        connection.executemany(
            "INSERT INTO child_directions (child_id, direction_id) VALUES (?, ?)",
            [(item["child_id"], item["direction_id"]) for item in seed["child_directions"]],
        )
        connection.executemany(
            """
            INSERT INTO visits (id, child_id, direction_id, scheduled_start, scheduled_end,
                                actual_start, actual_end, status, reason_code, rescheduled_to_visit_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["id"],
                    item["child_id"],
                    item["direction_id"],
                    item["scheduled_start"],
                    item["scheduled_end"],
                    item.get("actual_start"),
                    item.get("actual_end"),
                    item["status"],
                    item.get("reason_code"),
                    None,
                )
                for item in seed["visits"]
            ],
        )
        connection.executemany(
            "UPDATE visits SET rescheduled_to_visit_id = ? WHERE id = ?",
            [
                (item["rescheduled_to_visit_id"], item["id"])
                for item in seed["visits"]
                if item.get("rescheduled_to_visit_id")
            ],
        )
        connection.executemany(
            """
            INSERT INTO goals (id, child_id, direction_id, title, description, status,
                               metric_label, metric_target, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["id"],
                    item["child_id"],
                    item["direction_id"],
                    item["title"],
                    item["description"],
                    item["status"],
                    item.get("metric_label"),
                    item.get("metric_target"),
                    item["sort_order"],
                )
                for item in seed["goals"]
            ],
        )
        connection.executemany(
            """
            INSERT INTO goal_updates (id, goal_id, updated_at, status, comment, metric_value)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["id"],
                    item["goal_id"],
                    item["updated_at"],
                    item["status"],
                    item["comment"],
                    item.get("metric_value"),
                )
                for item in seed["goal_updates"]
            ],
        )

    def _load_seed(self) -> dict[str, Any]:
        try:
            seed = json.loads(self.seed_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"Cannot read demo seed: {self.seed_path}") from exc
        self._validate_seed(seed)
        return seed

    def _validate_seed(self, seed: dict[str, Any]) -> None:
        required_lists = ("children", "directions", "child_directions", "visits", "goals", "goal_updates")
        if any(not isinstance(seed.get(name), list) for name in required_lists):
            raise StoreError(f"Demo seed has invalid shape: {self.seed_path}")
        child_ids = {item.get("id") for item in seed["children"]}
        direction_ids = {item.get("id") for item in seed["directions"]}
        goal_ids = {item.get("id") for item in seed["goals"]}
        visit_ids = {item.get("id") for item in seed["visits"]}
        if not child_ids or None in child_ids or not direction_ids or None in direction_ids:
            raise StoreError("Demo seed must define children and directions.")
        for item in seed["child_directions"]:
            self._validate_reference(item, child_ids, direction_ids)
        for item in seed["visits"]:
            self._validate_reference(item, child_ids, direction_ids)
            if item.get("status") not in VISIT_STATUSES:
                raise StoreError(f"Demo seed has invalid visit status: {item.get('status')}")
            if self._minutes_between(item.get("scheduled_start"), item.get("scheduled_end")) <= 0:
                raise StoreError("Demo seed visit scheduled duration must be positive.")
            actual_start, actual_end = item.get("actual_start"), item.get("actual_end")
            if bool(actual_start) != bool(actual_end):
                raise StoreError("Demo seed visit must define both actual timestamps.")
            if actual_start and self._minutes_between(actual_start, actual_end) <= 0:
                raise StoreError("Demo seed visit actual duration must be positive.")
            if item.get("rescheduled_to_visit_id") not in (None, *visit_ids):
                raise StoreError("Demo seed visit references an unknown rescheduled visit.")
        for item in seed["goals"]:
            self._validate_reference(item, child_ids, direction_ids)
            if item.get("status") not in GOAL_STATUSES:
                raise StoreError(f"Demo seed has invalid goal status: {item.get('status')}")
        for item in seed["goal_updates"]:
            if item.get("goal_id") not in goal_ids:
                raise StoreError("Demo seed goal update references an unknown goal.")
            if item.get("status") not in GOAL_STATUSES:
                raise StoreError(f"Demo seed has invalid goal update status: {item.get('status')}")
            if item.get("metric_value") is not None and item["metric_value"] < 0:
                raise StoreError("Demo seed metric_value must not be negative.")

    def _validate_reference(
            self, item: dict[str, Any], child_ids: set[str | None], direction_ids: set[str | None]
    ) -> None:
        if item.get("child_id") not in child_ids:
            raise StoreError("Demo seed item references an unknown child.")
        if item.get("direction_id") not in direction_ids:
            raise StoreError("Demo seed item references an unknown direction.")

    def _minutes_between(self, start: str | None, end: str | None) -> int:
        if not start or not end:
            return 0
        try:
            return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 60)
        except ValueError as exc:
            raise StoreError("Demo seed visit timestamps must use ISO format.") from exc

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(self.path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except sqlite3.Error as exc:
            raise StoreError(f"Cannot open SQLite store: {self.path}") from exc

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()
