from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


class StoreError(RuntimeError):
    """Raised when the local demo SQLite store cannot be read or written."""


SCHEMA_VERSION = 4
DEFAULT_SEED_PATH = Path(__file__).with_name("demo_seed.json")
VISIT_STATUSES = {"scheduled", "completed", "partial", "cancelled", "absent", "rescheduled"}
GOAL_STATUSES = {"active", "progress", "achieved", "paused"}


class DemoStore:
    def __init__(self, path: Path, seed_path: Path = DEFAULT_SEED_PATH):
        self.path = path
        self.seed_path = seed_path
        self._lock = threading.RLock()

    def load_journal_data(self, child_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            try:
                with self._connection() as connection:
                    child = self._select_child_for_journal(connection, child_id)
                    directions = connection.execute(
                        """
                        SELECT d.id, d.slug, d.title, d.color, d.sort_order
                        FROM directions d
                                 JOIN child_directions cd ON cd.direction_id = d.id
                        WHERE cd.child_id = ?
                          AND cd.archived_at IS NULL
                          AND d.archived_at IS NULL
                        ORDER BY d.sort_order, d.id
                        """,
                        (child["id"],),
                    ).fetchall()
                    visits = connection.execute(
                        """
                        SELECT v.id,
                               v.child_id,
                               v.direction_id,
                               v.scheduled_start,
                               v.scheduled_end,
                               v.actual_start,
                               v.actual_end,
                               v.status,
                               v.reason_code,
                               v.rescheduled_to_visit_id
                        FROM visits v
                                 JOIN directions d ON d.id = v.direction_id
                                 JOIN child_directions cd
                                      ON cd.child_id = v.child_id AND cd.direction_id = v.direction_id
                        WHERE v.child_id = ?
                          AND v.archived_at IS NULL
                          AND d.archived_at IS NULL
                          AND cd.archived_at IS NULL
                        ORDER BY v.scheduled_start, v.id
                        """,
                        (child["id"],),
                    ).fetchall()
                    goals = connection.execute(
                        """
                        SELECT g.id,
                               g.child_id,
                               g.direction_id,
                               g.title,
                               g.description,
                               g.status,
                               g.metric_label,
                               g.metric_target,
                               g.sort_order
                        FROM goals g
                                 JOIN directions d ON d.id = g.direction_id
                                 JOIN child_directions cd
                                      ON cd.child_id = g.child_id AND cd.direction_id = g.direction_id
                        WHERE g.child_id = ?
                          AND g.archived_at IS NULL
                          AND d.archived_at IS NULL
                          AND cd.archived_at IS NULL
                        ORDER BY g.direction_id, g.sort_order, g.id
                        """,
                        (child["id"],),
                    ).fetchall()
                    goal_updates = connection.execute(
                        """
                        SELECT gu.id, gu.goal_id, gu.updated_at, gu.status, gu.comment, gu.metric_value
                        FROM goal_updates gu
                                 JOIN goals g ON g.id = gu.goal_id
                        WHERE g.child_id = ?
                          AND g.archived_at IS NULL
                        ORDER BY gu.updated_at, gu.id
                        """,
                        (child["id"],),
                    ).fetchall()
                return {
                    "child": self._public_row(child),
                    "directions": [dict(row) for row in directions],
                    "visits": [dict(row) for row in visits],
                    "goals": [dict(row) for row in goals],
                    "goal_updates": [dict(row) for row in goal_updates],
                }
            except sqlite3.Error as exc:
                raise StoreError(f"Cannot read SQLite store: {self.path}") from exc

    def list_children(self) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_database()
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT id, display_name, age_label, focus, archived_at
                    FROM children
                    ORDER BY archived_at IS NOT NULL, display_name, id
                    """
                ).fetchall()
            return [dict(row) for row in rows]

    def create_child(self, payload: dict[str, Any]) -> dict[str, Any]:
        display_name = self._required_text(payload, "display_name")
        age_label = self._required_text(payload, "age_label")
        focus = self._required_text(payload, "focus")
        child_id = self._new_id("child")
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                connection.execute(
                    """
                    INSERT INTO children (id, display_name, age_label, focus, archived_at)
                    VALUES (?, ?, ?, ?, NULL)
                    """,
                    (child_id, display_name, age_label, focus),
                )
                return self._get_child(connection, child_id)

    def update_child(self, child_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                current = self._get_child(connection, child_id)
                values = {
                    "display_name": self._optional_text(payload, "display_name", current["display_name"]),
                    "age_label": self._optional_text(payload, "age_label", current["age_label"]),
                    "focus": self._optional_text(payload, "focus", current["focus"]),
                }
                connection.execute(
                    """
                    UPDATE children
                    SET display_name = ?, age_label = ?, focus = ?
                    WHERE id = ?
                    """,
                    (values["display_name"], values["age_label"], values["focus"], child_id),
                )
                return self._get_child(connection, child_id)

    def archive_child(self, child_id: str) -> dict[str, Any]:
        return self._set_archived("children", child_id, self._now_iso())

    def restore_child(self, child_id: str) -> dict[str, Any]:
        return self._set_archived("children", child_id, None)

    def list_directions(self) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_database()
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT id, slug, title, color, sort_order, archived_at
                    FROM directions
                    ORDER BY archived_at IS NOT NULL, sort_order, title, id
                    """
                ).fetchall()
            return [dict(row) for row in rows]

    def create_direction(self, payload: dict[str, Any]) -> dict[str, Any]:
        direction_id = self._new_id("direction")
        slug = self._required_slug(payload, "slug")
        title = self._required_text(payload, "title")
        color = self._required_text(payload, "color")
        sort_order = self._integer(payload.get("sort_order", 0), "sort_order")
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                try:
                    connection.execute(
                        """
                        INSERT INTO directions (id, slug, title, color, sort_order, archived_at)
                        VALUES (?, ?, ?, ?, ?, NULL)
                        """,
                        (direction_id, slug, title, color, sort_order),
                    )
                except sqlite3.IntegrityError as exc:
                    raise StoreError("Direction slug already exists.") from exc
                return self._get_direction(connection, direction_id)

    def update_direction(self, direction_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                current = self._get_direction(connection, direction_id)
                slug = self._optional_slug(payload, "slug", current["slug"])
                title = self._optional_text(payload, "title", current["title"])
                color = self._optional_text(payload, "color", current["color"])
                sort_order = self._integer(payload.get("sort_order", current["sort_order"]), "sort_order")
                try:
                    connection.execute(
                        """
                        UPDATE directions
                        SET slug = ?, title = ?, color = ?, sort_order = ?
                        WHERE id = ?
                        """,
                        (slug, title, color, sort_order, direction_id),
                    )
                except sqlite3.IntegrityError as exc:
                    raise StoreError("Direction slug already exists.") from exc
                return self._get_direction(connection, direction_id)

    def archive_direction(self, direction_id: str) -> dict[str, Any]:
        return self._set_archived("directions", direction_id, self._now_iso())

    def restore_direction(self, direction_id: str) -> dict[str, Any]:
        return self._set_archived("directions", direction_id, None)

    def assign_direction(self, child_id: str, direction_id: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                self._get_child(connection, child_id, active=True)
                self._get_direction(connection, direction_id, active=True)
                connection.execute(
                    """
                    INSERT INTO child_directions (child_id, direction_id, archived_at)
                    VALUES (?, ?, NULL)
                    ON CONFLICT(child_id, direction_id) DO UPDATE SET archived_at = NULL
                    """,
                    (child_id, direction_id),
                )
                return self._get_child_direction(connection, child_id, direction_id)

    def remove_child_direction(self, child_id: str, direction_id: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                self._get_child(connection, child_id)
                self._get_direction(connection, direction_id)
                connection.execute(
                    """
                    UPDATE child_directions
                    SET archived_at = ?
                    WHERE child_id = ? AND direction_id = ?
                    """,
                    (self._now_iso(), child_id, direction_id),
                )
                return self._get_child_direction(connection, child_id, direction_id)

    def list_child_directions(self, child_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_database()
            with self._connection() as connection:
                self._get_child(connection, child_id)
                rows = connection.execute(
                    """
                    SELECT child_id, direction_id, archived_at
                    FROM child_directions
                    WHERE child_id = ?
                    ORDER BY archived_at IS NOT NULL, direction_id
                    """,
                    (child_id,),
                ).fetchall()
            return [dict(row) for row in rows]

    def list_goals(self, child_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_database()
            with self._connection() as connection:
                self._get_child(connection, child_id)
                rows = connection.execute(
                    """
                    SELECT id, child_id, direction_id, title, description, status,
                           metric_label, metric_target, sort_order, archived_at
                    FROM goals
                    WHERE child_id = ?
                    ORDER BY archived_at IS NOT NULL, direction_id, sort_order, id
                    """,
                    (child_id,),
                ).fetchall()
            return [dict(row) for row in rows]

    def create_goal(self, child_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        goal_id = self._new_id("goal")
        values = self._goal_values(payload, require_all=True)
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                self._require_assigned_direction(connection, child_id, values["direction_id"])
                connection.execute(
                    """
                    INSERT INTO goals (id, child_id, direction_id, title, description, status,
                                       metric_label, metric_target, sort_order, archived_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        goal_id,
                        child_id,
                        values["direction_id"],
                        values["title"],
                        values["description"],
                        values["status"],
                        values["metric_label"],
                        values["metric_target"],
                        values["sort_order"],
                    ),
                )
                return self._get_goal(connection, goal_id)

    def update_goal(self, child_id: str, goal_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                current = self._get_goal(connection, goal_id, child_id)
                merged = {**dict(current), **payload}
                values = self._goal_values(merged, require_all=True)
                self._require_assigned_direction(connection, child_id, values["direction_id"])
                connection.execute(
                    """
                    UPDATE goals
                    SET direction_id = ?, title = ?, description = ?, status = ?,
                        metric_label = ?, metric_target = ?, sort_order = ?
                    WHERE id = ? AND child_id = ?
                    """,
                    (
                        values["direction_id"],
                        values["title"],
                        values["description"],
                        values["status"],
                        values["metric_label"],
                        values["metric_target"],
                        values["sort_order"],
                        goal_id,
                        child_id,
                    ),
                )
                return self._get_goal(connection, goal_id, child_id)

    def archive_goal(self, child_id: str, goal_id: str) -> dict[str, Any]:
        return self._archive_child_item("goals", child_id, goal_id)

    def list_visits(self, child_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_database()
            with self._connection() as connection:
                self._get_child(connection, child_id)
                rows = connection.execute(
                    """
                    SELECT id, child_id, direction_id, scheduled_start, scheduled_end,
                           actual_start, actual_end, status, reason_code,
                           rescheduled_to_visit_id, archived_at
                    FROM visits
                    WHERE child_id = ?
                    ORDER BY archived_at IS NOT NULL, scheduled_start, id
                    """,
                    (child_id,),
                ).fetchall()
            return [dict(row) for row in rows]

    def create_visit(self, child_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        visit_id = self._new_id("visit")
        values = self._visit_values(payload, require_all=True)
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                self._require_assigned_direction(connection, child_id, values["direction_id"])
                self._validate_visit_reference(connection, values["rescheduled_to_visit_id"])
                connection.execute(
                    """
                    INSERT INTO visits (id, child_id, direction_id, scheduled_start, scheduled_end,
                                        actual_start, actual_end, status, reason_code,
                                        rescheduled_to_visit_id, archived_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        visit_id,
                        child_id,
                        values["direction_id"],
                        values["scheduled_start"],
                        values["scheduled_end"],
                        values["actual_start"],
                        values["actual_end"],
                        values["status"],
                        values["reason_code"],
                        values["rescheduled_to_visit_id"],
                    ),
                )
                return self._get_visit(connection, visit_id, child_id)

    def update_visit(self, child_id: str, visit_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                current = self._get_visit(connection, visit_id, child_id)
                merged = {**dict(current), **payload}
                values = self._visit_values(merged, require_all=True)
                self._require_assigned_direction(connection, child_id, values["direction_id"])
                self._validate_visit_reference(connection, values["rescheduled_to_visit_id"])
                connection.execute(
                    """
                    UPDATE visits
                    SET direction_id = ?, scheduled_start = ?, scheduled_end = ?,
                        actual_start = ?, actual_end = ?, status = ?, reason_code = ?,
                        rescheduled_to_visit_id = ?
                    WHERE id = ? AND child_id = ?
                    """,
                    (
                        values["direction_id"],
                        values["scheduled_start"],
                        values["scheduled_end"],
                        values["actual_start"],
                        values["actual_end"],
                        values["status"],
                        values["reason_code"],
                        values["rescheduled_to_visit_id"],
                        visit_id,
                        child_id,
                    ),
                )
                return self._get_visit(connection, visit_id, child_id)

    def archive_visit(self, child_id: str, visit_id: str) -> dict[str, Any]:
        return self._archive_child_item("visits", child_id, visit_id)

    def reset(self) -> None:
        with self._lock:
            self._recreate_from_seed()

    def _select_child_for_journal(
            self, connection: sqlite3.Connection, child_id: str | None
    ) -> sqlite3.Row:
        if child_id:
            row = connection.execute(
                """
                SELECT id, display_name, age_label, focus, archived_at
                FROM children
                WHERE id = ?
                """,
                (child_id,),
            ).fetchone()
            if row is None:
                raise StoreError("Unknown child.")
            if row["archived_at"] is not None:
                raise StoreError("Child is archived.")
            return row
        row = connection.execute(
            """
            SELECT id, display_name, age_label, focus, archived_at
            FROM children
            WHERE archived_at IS NULL
            ORDER BY id
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            raise StoreError("No active child is available.")
        return row

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
                            focus        TEXT NOT NULL,
                            archived_at  TEXT
                        );
                        CREATE TABLE directions
                        (
                            id          TEXT PRIMARY KEY,
                            slug        TEXT    NOT NULL UNIQUE,
                            title       TEXT    NOT NULL,
                            color       TEXT    NOT NULL,
                            sort_order  INTEGER NOT NULL,
                            archived_at TEXT
                        );
                        CREATE TABLE child_directions
                        (
                            child_id     TEXT NOT NULL,
                            direction_id TEXT NOT NULL,
                            archived_at  TEXT,
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
                            archived_at             TEXT,
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
                            archived_at   TEXT,
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
                        CREATE INDEX idx_child_directions_child ON child_directions (child_id, archived_at);
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
            """
            INSERT INTO children (id, display_name, age_label, focus, archived_at)
            VALUES (?, ?, ?, ?, NULL)
            """,
            [
                (item["id"], item["display_name"], item["age_label"], item["focus"])
                for item in seed["children"]
            ],
        )
        connection.executemany(
            """
            INSERT INTO directions (id, slug, title, color, sort_order, archived_at)
            VALUES (?, ?, ?, ?, ?, NULL)
            """,
            [
                (item["id"], item["slug"], item["title"], item["color"], item["sort_order"])
                for item in seed["directions"]
            ],
        )
        connection.executemany(
            "INSERT INTO child_directions (child_id, direction_id, archived_at) VALUES (?, ?, NULL)",
            [(item["child_id"], item["direction_id"]) for item in seed["child_directions"]],
        )
        connection.executemany(
            """
            INSERT INTO visits (id, child_id, direction_id, scheduled_start, scheduled_end,
                                actual_start, actual_end, status, reason_code,
                                rescheduled_to_visit_id, archived_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
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
                               metric_label, metric_target, sort_order, archived_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
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

    def _get_child(self, connection: sqlite3.Connection, child_id: str, active: bool = False) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT id, display_name, age_label, focus, archived_at
            FROM children
            WHERE id = ?
            """,
            (child_id,),
        ).fetchone()
        if row is None:
            raise StoreError("Unknown child.")
        if active and row["archived_at"] is not None:
            raise StoreError("Child is archived.")
        return dict(row)

    def _get_direction(
            self, connection: sqlite3.Connection, direction_id: str, active: bool = False
    ) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT id, slug, title, color, sort_order, archived_at
            FROM directions
            WHERE id = ?
            """,
            (direction_id,),
        ).fetchone()
        if row is None:
            raise StoreError("Unknown direction.")
        if active and row["archived_at"] is not None:
            raise StoreError("Direction is archived.")
        return dict(row)

    def _get_child_direction(
            self, connection: sqlite3.Connection, child_id: str, direction_id: str
    ) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT child_id, direction_id, archived_at
            FROM child_directions
            WHERE child_id = ? AND direction_id = ?
            """,
            (child_id, direction_id),
        ).fetchone()
        if row is None:
            raise StoreError("Child direction assignment was not found.")
        return dict(row)

    def _get_goal(
            self, connection: sqlite3.Connection, goal_id: str, child_id: str | None = None
    ) -> dict[str, Any]:
        params: tuple[Any, ...] = (goal_id,) if child_id is None else (goal_id, child_id)
        row = connection.execute(
            """
            SELECT id, child_id, direction_id, title, description, status,
                   metric_label, metric_target, sort_order, archived_at
            FROM goals
            WHERE id = ?""" + ("" if child_id is None else " AND child_id = ?"),
            params,
        ).fetchone()
        if row is None:
            raise StoreError("Unknown goal.")
        return dict(row)

    def _get_visit(
            self, connection: sqlite3.Connection, visit_id: str, child_id: str | None = None
    ) -> dict[str, Any]:
        params: tuple[Any, ...] = (visit_id,) if child_id is None else (visit_id, child_id)
        row = connection.execute(
            """
            SELECT id, child_id, direction_id, scheduled_start, scheduled_end,
                   actual_start, actual_end, status, reason_code,
                   rescheduled_to_visit_id, archived_at
            FROM visits
            WHERE id = ?""" + ("" if child_id is None else " AND child_id = ?"),
            params,
        ).fetchone()
        if row is None:
            raise StoreError("Unknown visit.")
        return dict(row)

    def _require_assigned_direction(
            self, connection: sqlite3.Connection, child_id: str, direction_id: str
    ) -> None:
        self._get_child(connection, child_id, active=True)
        self._get_direction(connection, direction_id, active=True)
        row = connection.execute(
            """
            SELECT 1
            FROM child_directions
            WHERE child_id = ? AND direction_id = ? AND archived_at IS NULL
            """,
            (child_id, direction_id),
        ).fetchone()
        if row is None:
            raise StoreError("Goal or visit must use an assigned direction.")

    def _validate_visit_reference(self, connection: sqlite3.Connection, visit_id: str | None) -> None:
        if visit_id is None:
            return
        self._get_visit(connection, visit_id)

    def _set_archived(self, table: str, item_id: str, archived_at: str | None) -> dict[str, Any]:
        if table not in {"children", "directions"}:
            raise StoreError("Unsupported archive table.")
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                column_getter = self._get_child if table == "children" else self._get_direction
                column_getter(connection, item_id)
                connection.execute(
                    f"UPDATE {table} SET archived_at = ? WHERE id = ?",
                    (archived_at, item_id),
                )
                return column_getter(connection, item_id)

    def _archive_child_item(self, table: str, child_id: str, item_id: str) -> dict[str, Any]:
        if table not in {"goals", "visits"}:
            raise StoreError("Unsupported archive table.")
        with self._lock:
            self._ensure_database()
            with self._connection() as connection, connection:
                getter = self._get_goal if table == "goals" else self._get_visit
                getter(connection, item_id, child_id)
                connection.execute(
                    f"UPDATE {table} SET archived_at = ? WHERE id = ? AND child_id = ?",
                    (self._now_iso(), item_id, child_id),
                )
                return getter(connection, item_id, child_id)

    def _goal_values(self, payload: dict[str, Any], require_all: bool) -> dict[str, Any]:
        status = self._required_text(payload, "status") if require_all else payload.get("status")
        if status not in GOAL_STATUSES:
            raise StoreError(f"Invalid goal status: {status}")
        metric_target = payload.get("metric_target")
        if metric_target in ("", None):
            metric_target = None
        else:
            metric_target = float(metric_target)
            if metric_target < 0:
                raise StoreError("Goal metric_target must not be negative.")
        return {
            "direction_id": self._required_text(payload, "direction_id"),
            "title": self._required_text(payload, "title"),
            "description": self._required_text(payload, "description"),
            "status": status,
            "metric_label": self._nullable_text(payload.get("metric_label")),
            "metric_target": metric_target,
            "sort_order": self._integer(payload.get("sort_order", 0), "sort_order"),
        }

    def _visit_values(self, payload: dict[str, Any], require_all: bool) -> dict[str, Any]:
        status = self._required_text(payload, "status") if require_all else payload.get("status")
        if status not in VISIT_STATUSES:
            raise StoreError(f"Invalid visit status: {status}")
        scheduled_start = self._required_text(payload, "scheduled_start")
        scheduled_end = self._required_text(payload, "scheduled_end")
        if self._minutes_between(scheduled_start, scheduled_end) <= 0:
            raise StoreError("Visit scheduled duration must be positive.")
        actual_start = self._nullable_text(payload.get("actual_start"))
        actual_end = self._nullable_text(payload.get("actual_end"))
        if bool(actual_start) != bool(actual_end):
            raise StoreError("Visit must define both actual timestamps.")
        if actual_start and self._minutes_between(actual_start, actual_end) <= 0:
            raise StoreError("Visit actual duration must be positive.")
        return {
            "direction_id": self._required_text(payload, "direction_id"),
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "actual_start": actual_start,
            "actual_end": actual_end,
            "status": status,
            "reason_code": self._nullable_text(payload.get("reason_code")),
            "rescheduled_to_visit_id": self._nullable_text(payload.get("rescheduled_to_visit_id")),
        }

    def _required_text(self, payload: dict[str, Any], field: str) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise StoreError(f"Missing required field: {field}")
        return value.strip()

    def _optional_text(self, payload: dict[str, Any], field: str, fallback: str) -> str:
        if field not in payload:
            return fallback
        return self._required_text(payload, field)

    def _nullable_text(self, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise StoreError("Expected text value.")
        stripped = value.strip()
        return stripped or None

    def _required_slug(self, payload: dict[str, Any], field: str) -> str:
        value = self._required_text(payload, field)
        if any(not (char.isalnum() or char in "-_") for char in value):
            raise StoreError(f"Invalid slug: {value}")
        return value

    def _optional_slug(self, payload: dict[str, Any], field: str, fallback: str) -> str:
        if field not in payload:
            return fallback
        return self._required_slug(payload, field)

    def _integer(self, value: Any, field: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise StoreError(f"Invalid integer field: {field}") from exc

    def _public_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data.pop("archived_at", None)
        return data

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:10]}"

    def _now_iso(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

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
