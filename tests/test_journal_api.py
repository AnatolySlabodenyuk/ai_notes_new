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
    def load_journal_data(self, child_id=None):
        raise StoreError("broken seed")


class _BrokenParentStore:
    def load_parent_journal_data(self, parent_id, child_id=None):
        raise StoreError("broken parent seed")


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

    def request_json(self, url, method, payload=None):
        from urllib.request import Request

        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urlopen(request, timeout=2) as response:
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

    def test_parent_portal_lists_only_linked_children_and_returns_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            base_url = self.start_server(store)

            _, child = self.request_json(
                f"{base_url}/api/admin/children",
                "POST",
                {"display_name": "Ребёнок Б", "age_label": "6 лет", "focus": "адаптация"},
            )
            _, parent = self.request_json(
                f"{base_url}/api/admin/parents",
                "POST",
                {"display_name": "Родитель Б", "login": "parent-b", "access_code": "demo-b"},
            )
            self.request_json(
                f"{base_url}/api/admin/parents/{parent['id']}/children",
                "POST",
                {"child_id": child["id"]},
            )

            children_status, children = self.read_json(f"{base_url}/api/parent/children?parent_id={parent['id']}")
            journal_status, journal = self.read_json(
                f"{base_url}/api/parent/journal?parent_id={parent['id']}&month=2026-06&child_id={child['id']}"
            )
            foreign_status, foreign = self.read_error(
                f"{base_url}/api/parent/journal?parent_id={parent['id']}&month=2026-06&child_id=child-a"
            )

            self.assertEqual(children_status, 200)
            self.assertEqual([item["id"] for item in children["children"]], [child["id"]])
            self.assertEqual(journal_status, 200)
            self.assertEqual(journal["child"]["id"], child["id"])
            self.assertEqual(foreign_status, 403)
            self.assertEqual(foreign["error"]["code"], "forbidden_child")

    def test_parent_portal_rejects_missing_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_url = self.start_server(DemoStore(Path(tmp) / "app.sqlite3"))

            status, payload = self.read_error(f"{base_url}/api/parent/children")

            self.assertEqual(status, 400)
            self.assertEqual(payload["error"]["code"], "missing_parent")

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

    def test_admin_child_crud_and_journal_child_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_url = self.start_server(DemoStore(Path(tmp) / "app.sqlite3"))

            status, child = self.request_json(
                f"{base_url}/api/admin/children",
                "POST",
                {"display_name": "Ребёнок Б", "age_label": "6 лет", "focus": "адаптация"},
            )
            update_status, updated = self.request_json(
                f"{base_url}/api/admin/children/{child['id']}",
                "PUT",
                {"display_name": "Ребёнок Бета"},
            )
            journal_status, journal = self.read_json(
                f"{base_url}/api/journal?month=2026-06&child_id={child['id']}"
            )

            self.assertEqual(status, 201)
            self.assertEqual(update_status, 200)
            self.assertEqual(updated["display_name"], "Ребёнок Бета")
            self.assertEqual(journal_status, 200)
            self.assertEqual(journal["child"]["id"], child["id"])

    def test_admin_direction_goal_and_visit_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_url = self.start_server(DemoStore(Path(tmp) / "app.sqlite3"))

            _, child = self.request_json(
                f"{base_url}/api/admin/children",
                "POST",
                {"display_name": "Ребёнок Б", "age_label": "6 лет", "focus": "адаптация"},
            )
            _, direction = self.request_json(
                f"{base_url}/api/admin/directions",
                "POST",
                {"slug": "music", "title": "Музыка", "color": "#445566", "sort_order": 7},
            )
            assign_status, _ = self.request_json(
                f"{base_url}/api/admin/children/{child['id']}/directions",
                "POST",
                {"direction_id": direction["id"]},
            )
            goal_status, goal = self.request_json(
                f"{base_url}/api/admin/children/{child['id']}/goals",
                "POST",
                {
                    "direction_id": direction["id"],
                    "title": "Петь короткую фразу",
                    "description": "Повторять знакомую строку.",
                    "status": "active",
                },
            )
            visit_status, visit = self.request_json(
                f"{base_url}/api/admin/children/{child['id']}/visits",
                "POST",
                {
                    "direction_id": direction["id"],
                    "scheduled_start": "2026-06-10T10:00:00+03:00",
                    "scheduled_end": "2026-06-10T11:00:00+03:00",
                    "status": "scheduled",
                },
            )

            self.assertEqual(assign_status, 200)
            self.assertEqual(goal_status, 201)
            self.assertEqual(goal["title"], "Петь короткую фразу")
            self.assertEqual(visit_status, 201)
            self.assertEqual(visit["direction_id"], direction["id"])

    def test_admin_parent_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_url = self.start_server(DemoStore(Path(tmp) / "app.sqlite3"))

            status, parent = self.request_json(
                f"{base_url}/api/admin/parents",
                "POST",
                {"display_name": "Родитель Б", "login": "parent-b", "access_code": "demo-b"},
            )
            assign_status, link = self.request_json(
                f"{base_url}/api/admin/parents/{parent['id']}/children",
                "POST",
                {"child_id": "child-a"},
            )
            list_status, children = self.read_json(f"{base_url}/api/admin/parents/{parent['id']}/children")

            self.assertEqual(status, 201)
            self.assertEqual(parent["login"], "parent-b")
            self.assertEqual(assign_status, 200)
            self.assertEqual(link["child_id"], "child-a")
            self.assertEqual(list_status, 200)
            self.assertEqual(children["children"][0]["id"], "child-a")

    def test_admin_validation_errors_return_400(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_url = self.start_server(DemoStore(Path(tmp) / "app.sqlite3"))

            from urllib.request import Request

            bad_child = Request(
                f"{base_url}/api/admin/children",
                data=json.dumps({"display_name": ""}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as caught_child:
                urlopen(bad_child, timeout=2)
            child_error = json.loads(caught_child.exception.read().decode("utf-8"))

            self.assertEqual(caught_child.exception.code, 400)
            self.assertEqual(child_error["error"]["code"], "validation_error")

            request = Request(
                f"{base_url}/api/admin/children/child-a/visits",
                data=json.dumps(
                    {
                        "direction_id": "direction-aba",
                        "scheduled_start": "2026-06-10T11:00:00+03:00",
                        "scheduled_end": "2026-06-10T10:00:00+03:00",
                        "status": "scheduled",
                    }
                ).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=2)
            error = json.loads(caught.exception.read().decode("utf-8"))

            self.assertEqual(caught.exception.code, 400)
            self.assertEqual(error["error"]["code"], "validation_error")


if __name__ == "__main__":
    unittest.main()
