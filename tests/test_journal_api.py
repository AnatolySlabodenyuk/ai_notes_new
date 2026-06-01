import json
import tempfile
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from backend.server import AppHandler, parse_month
from backend.store import DemoStore, StoreError


class _BrokenStore:
    def load_journal_data(self):
        raise StoreError("broken seed")


class JournalApiTests(unittest.TestCase):
    def start_server(self, store):
        server = ThreadingHTTPServer(("127.0.0.1", 0), AppHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        patcher = patch("backend.server.STORE", store)
        patcher.start()
        thread.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.addCleanup(thread.join, 1)
        return f"http://127.0.0.1:{server.server_port}"

    def read_json(self, url):
        with urlopen(url, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def read_error(self, url):
        with self.assertRaises(HTTPError) as caught:
            urlopen(url, timeout=2)
        return caught.exception.code, json.loads(caught.exception.read().decode("utf-8"))

    def test_parse_month_accepts_calendar_month(self):
        self.assertEqual(parse_month("2026-06"), "2026-06")

    def test_parse_month_rejects_invalid_value(self):
        with self.assertRaises(ValueError):
            parse_month("2026-13")

    def test_get_journal_returns_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_url = self.start_server(DemoStore(Path(tmp) / "app.sqlite3"))

            status, payload = self.read_json(f"{base_url}/api/journal?month=2026-06")

            self.assertEqual(status, 200)
            self.assertEqual(payload["month"], "2026-06")
            self.assertEqual(payload["child"]["id"], "child-a")
            self.assertGreaterEqual(len(payload["directions"]), 4)

    def test_get_journal_rejects_invalid_month(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_url = self.start_server(DemoStore(Path(tmp) / "app.sqlite3"))

            status, payload = self.read_error(f"{base_url}/api/journal?month=2026-13")

            self.assertEqual(status, 400)
            self.assertEqual(payload["error"]["code"], "invalid_month")

    def test_get_journal_maps_store_error(self):
        base_url = self.start_server(_BrokenStore())

        status, payload = self.read_error(f"{base_url}/api/journal?month=2026-06")

        self.assertEqual(status, 500)
        self.assertEqual(payload["error"]["code"], "store_error")

    def test_unknown_route_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_url = self.start_server(DemoStore(Path(tmp) / "app.sqlite3"))

            status, payload = self.read_error(f"{base_url}/api/missing")

            self.assertEqual(status, 404)
            self.assertEqual(payload["error"]["code"], "error")


if __name__ == "__main__":
    unittest.main()
