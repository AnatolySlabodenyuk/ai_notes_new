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
            self._json_error("Not found", HTTPStatus.NOT_FOUND)
        except StoreError as exc:
            self._json_error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR, "store_error")

    def do_POST(self) -> None:
        self._begin_request()
        self._json_error("Not found", HTTPStatus.NOT_FOUND)

    def _serve_journal(self, query: str) -> None:
        month_values = parse_qs(query).get("month", [])
        try:
            month = parse_month(month_values[0]) if len(month_values) == 1 else ""
            if not month:
                raise ValueError("Missing month.")
        except ValueError as exc:
            self._json_error(str(exc), HTTPStatus.BAD_REQUEST, "invalid_month")
            return
        data = STORE.load_journal_data()
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
