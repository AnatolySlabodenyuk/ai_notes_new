from __future__ import annotations

import json
import logging
import mimetypes
import os
import sys
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .journal import SCHOOL_TIMEZONE, build_journal_snapshot
from .store import DemoStore, StoreError

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "frontend"
DATA_DIR = ROOT / "data"
STORE = DemoStore(DATA_DIR / "app.sqlite3")
LOGGER = logging.getLogger("child_journal")


def parse_month(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise ValueError("Month must use YYYY-MM format.") from exc
    if parsed.strftime("%Y-%m") != value:
        raise ValueError("Month must use YYYY-MM format.")
    return value


class AppHandler(BaseHTTPRequestHandler):
    server_version = "ChildJournalDemo/0.2"

    def do_GET(self) -> None:
        self._begin_request()
        parsed_url = urlparse(self.path)
        try:
            if parsed_url.path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                self._finish_request(HTTPStatus.NO_CONTENT, 0)
                return
            if parsed_url.path == "/" or parsed_url.path.startswith("/static/"):
                self._serve_static(parsed_url.path)
                return
            if parsed_url.path == "/api/health":
                self._json_response({"ok": True, "pid": os.getpid()})
                return
            if parsed_url.path == "/api/journal":
                self._serve_journal(parsed_url.query)
                return
            if parsed_url.path.startswith("/api/parent/"):
                self._serve_parent_get(parsed_url.path, parsed_url.query)
                return
            if parsed_url.path.startswith("/api/admin/"):
                self._serve_admin_get(parsed_url.path)
                return
            self._json_error("Not found", HTTPStatus.NOT_FOUND)
        except StoreError as exc:
            self._json_error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR, "store_error")

    def do_POST(self) -> None:
        self._begin_request()
        self._serve_admin_mutation("POST")

    def do_PUT(self) -> None:
        self._begin_request()
        self._serve_admin_mutation("PUT")

    def do_DELETE(self) -> None:
        self._begin_request()
        self._serve_admin_mutation("DELETE")

    def _serve_journal(self, query: str) -> None:
        month_values = parse_qs(query).get("month", [])
        try:
            params = parse_qs(query)
            month_values = params.get("month", [])
            child_values = params.get("child_id", [])
            month = parse_month(month_values[0]) if len(month_values) == 1 else ""
            if not month:
                raise ValueError("Missing month.")
            child_id = child_values[0] if len(child_values) == 1 else None
        except ValueError as exc:
            self._json_error(str(exc), HTTPStatus.BAD_REQUEST, "invalid_month")
            return
        data = STORE.load_journal_data(child_id)
        snapshot = build_journal_snapshot(
            month=month,
            child=data["child"],
            directions=data["directions"],
            visits=data["visits"],
            goals=data["goals"],
            goal_updates=data["goal_updates"],
            now=datetime.now(SCHOOL_TIMEZONE).isoformat(),
        )
        self._json_response(snapshot)

    def _serve_parent_get(self, path: str, query: str) -> None:
        try:
            params = parse_qs(query)
            parent_id = self._required_query_value(params, "parent_id")
            parts = self._path_parts(path)
            if parts == ["api", "parent", "children"]:
                self._json_response({"children": STORE.list_parent_children(parent_id)})
                return
            if parts == ["api", "parent", "journal"]:
                month = parse_month(self._required_query_value(params, "month"))
                child_values = params.get("child_id", [])
                child_id = child_values[0] if len(child_values) == 1 else None
                data = STORE.load_parent_journal_data(parent_id, child_id)
                snapshot = build_journal_snapshot(
                    month=month,
                    child=data["child"],
                    directions=data["directions"],
                    visits=data["visits"],
                    goals=data["goals"],
                    goal_updates=data["goal_updates"],
                    now=datetime.now(SCHOOL_TIMEZONE).isoformat(),
                )
                self._json_response(snapshot)
                return
            self._json_error("Not found", HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_error(str(exc), HTTPStatus.BAD_REQUEST, "missing_parent")
        except StoreError as exc:
            code = "forbidden_child" if "not linked" in str(exc) else "validation_error"
            status = HTTPStatus.FORBIDDEN if code == "forbidden_child" else HTTPStatus.BAD_REQUEST
            self._json_error(str(exc), status, code)

    def _serve_admin_get(self, path: str) -> None:
        try:
            parts = self._path_parts(path)
            if parts == ["api", "admin", "children"]:
                self._json_response({"children": STORE.list_children()})
                return
            if parts == ["api", "admin", "directions"]:
                self._json_response({"directions": STORE.list_directions()})
                return
            if parts == ["api", "admin", "parents"]:
                self._json_response({"parents": STORE.list_parents()})
                return
            if len(parts) == 5 and parts[:3] == ["api", "admin", "parents"] and parts[4] == "children":
                self._json_response({"children": STORE.list_parent_children(parts[3])})
                return
            if len(parts) == 5 and parts[:3] == ["api", "admin", "children"]:
                child_id = parts[3]
                if parts[4] == "directions":
                    self._json_response({"child_directions": STORE.list_child_directions(child_id)})
                    return
                if parts[4] == "goals":
                    self._json_response({"goals": STORE.list_goals(child_id)})
                    return
                if parts[4] == "visits":
                    self._json_response({"visits": STORE.list_visits(child_id)})
                    return
            self._json_error("Not found", HTTPStatus.NOT_FOUND)
        except StoreError as exc:
            self._json_error(str(exc), HTTPStatus.BAD_REQUEST, "validation_error")

    def _serve_admin_mutation(self, method: str) -> None:
        parsed_url = urlparse(self.path)
        try:
            parts = self._path_parts(parsed_url.path)
            payload = {} if method == "DELETE" else self._read_json_body()
            if method == "POST" and parts == ["api", "admin", "children"]:
                self._json_response(STORE.create_child(payload), HTTPStatus.CREATED)
                return
            if method == "PUT" and len(parts) == 4 and parts[:3] == ["api", "admin", "children"]:
                self._json_response(STORE.update_child(parts[3], payload))
                return
            if method == "POST" and len(parts) == 5 and parts[:3] == ["api", "admin", "children"]:
                if parts[4] == "archive":
                    self._json_response(STORE.archive_child(parts[3]))
                    return
                if parts[4] == "restore":
                    self._json_response(STORE.restore_child(parts[3]))
                    return
            if method == "POST" and parts == ["api", "admin", "directions"]:
                self._json_response(STORE.create_direction(payload), HTTPStatus.CREATED)
                return
            if method == "PUT" and len(parts) == 4 and parts[:3] == ["api", "admin", "directions"]:
                self._json_response(STORE.update_direction(parts[3], payload))
                return
            if method == "POST" and len(parts) == 5 and parts[:3] == ["api", "admin", "directions"]:
                if parts[4] == "archive":
                    self._json_response(STORE.archive_direction(parts[3]))
                    return
                if parts[4] == "restore":
                    self._json_response(STORE.restore_direction(parts[3]))
                    return
            if method == "POST" and parts == ["api", "admin", "parents"]:
                self._json_response(STORE.create_parent(payload), HTTPStatus.CREATED)
                return
            if method == "PUT" and len(parts) == 4 and parts[:3] == ["api", "admin", "parents"]:
                self._json_response(STORE.update_parent(parts[3], payload))
                return
            if method == "POST" and len(parts) == 5 and parts[:3] == ["api", "admin", "parents"]:
                if parts[4] == "archive":
                    self._json_response(STORE.archive_parent(parts[3]))
                    return
                if parts[4] == "restore":
                    self._json_response(STORE.restore_parent(parts[3]))
                    return
                if parts[4] == "children":
                    child_id = self._required_payload_id(payload, "child_id")
                    self._json_response(STORE.assign_parent_child(parts[3], child_id))
                    return
            if (
                    method == "DELETE"
                    and len(parts) == 6
                    and parts[:3] == ["api", "admin", "parents"]
                    and parts[4] == "children"
            ):
                self._json_response(STORE.remove_parent_child(parts[3], parts[5]))
                return
            if len(parts) >= 5 and parts[:3] == ["api", "admin", "children"]:
                child_id = parts[3]
                if method == "POST" and len(parts) == 5 and parts[4] == "directions":
                    direction_id = self._required_payload_id(payload, "direction_id")
                    self._json_response(STORE.assign_direction(child_id, direction_id))
                    return
                if method == "DELETE" and len(parts) == 6 and parts[4] == "directions":
                    self._json_response(STORE.remove_child_direction(child_id, parts[5]))
                    return
                if method == "POST" and len(parts) == 5 and parts[4] == "goals":
                    self._json_response(STORE.create_goal(child_id, payload), HTTPStatus.CREATED)
                    return
                if method == "PUT" and len(parts) == 6 and parts[4] == "goals":
                    self._json_response(STORE.update_goal(child_id, parts[5], payload))
                    return
                if method == "DELETE" and len(parts) == 6 and parts[4] == "goals":
                    self._json_response(STORE.archive_goal(child_id, parts[5]))
                    return
                if method == "POST" and len(parts) == 5 and parts[4] == "visits":
                    self._json_response(STORE.create_visit(child_id, payload), HTTPStatus.CREATED)
                    return
                if method == "PUT" and len(parts) == 6 and parts[4] == "visits":
                    self._json_response(STORE.update_visit(child_id, parts[5], payload))
                    return
                if method == "DELETE" and len(parts) == 6 and parts[4] == "visits":
                    self._json_response(STORE.archive_visit(child_id, parts[5]))
                    return
            self._json_error("Not found", HTTPStatus.NOT_FOUND)
        except (StoreError, ValueError) as exc:
            self._json_error(str(exc), HTTPStatus.BAD_REQUEST, "validation_error")

    def _path_parts(self, path: str) -> list[str]:
        return [part for part in path.split("/") if part]

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def _required_payload_id(self, payload: dict, field: str) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing required field: {field}")
        return value.strip()

    def _required_query_value(self, params: dict[str, list[str]], field: str) -> str:
        values = params.get(field, [])
        if len(values) != 1 or not values[0].strip():
            raise ValueError(f"Missing required field: {field}")
        return values[0].strip()

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path == "/" else request_path.replace("/static/", "", 1)
        path = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in path.parents and path != STATIC_DIR.resolve():
            self._json_error("Invalid path", HTTPStatus.BAD_REQUEST)
            return
        if not path.exists() or not path.is_file():
            self._json_error("Not found", HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
        self._finish_request(HTTPStatus.OK, len(body))

    def _json_response(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self._finish_request(status, len(body))

    def _json_error(self, message: str, status: HTTPStatus, code: str = "error") -> None:
        self._log_error("request_error status=%s code=%s message=%s", status.value, code, message)
        self._json_response({"error": {"code": code, "message": message}}, status)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _begin_request(self) -> None:
        self.request_id = uuid.uuid4().hex[:8]
        self.request_started_at = time.perf_counter()
        self._log_info("request_start method=%s path=%s", self.command, self.path)

    def _finish_request(self, status: HTTPStatus, body_bytes: int) -> None:
        self._log_info(
            "request_done status=%d duration_ms=%d response_bytes=%d",
            status.value,
            round((time.perf_counter() - self.request_started_at) * 1000),
            body_bytes,
        )

    def _log_info(self, message: str, *args: object) -> None:
        LOGGER.info("[%s] " + message, getattr(self, "request_id", "--------"), *args)

    def _log_error(self, message: str, *args: object) -> None:
        LOGGER.error("[%s] " + message, getattr(self, "request_id", "--------"), *args)


def configure_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s pid=%(process)d %(message)s",
        stream=sys.stdout,
        force=True,
    )


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    configure_logging()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORE.load_journal_data()
    httpd = ThreadingHTTPServer((host, port), AppHandler)
    LOGGER.info("Child Journal demo running at http://%s:%s", host, port)
    httpd.serve_forever()


if __name__ == "__main__":
    run()
