import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.store import DemoStore, StoreError


class JournalStoreTests(unittest.TestCase):
    def test_load_journal_data_creates_current_schema_and_bulk_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")

            data = store.load_journal_data()

            self.assertEqual(data["child"]["id"], "child-a")
            self.assertGreaterEqual(len(data["directions"]), 4)
            self.assertGreaterEqual(len(data["visits"]), 1)
            self.assertGreaterEqual(len(data["goals"]), 1)
            self.assertGreaterEqual(len(data["goal_updates"]), 1)
            with closing(sqlite3.connect(store.path)) as connection:
                version = connection.execute("SELECT version FROM schema_meta").fetchone()[0]
            self.assertEqual(version, 5)

    def test_existing_old_database_is_replaced_when_schema_version_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app.sqlite3"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute("CREATE TABLE children (id TEXT PRIMARY KEY)")
                connection.execute("INSERT INTO children (id) VALUES ('legacy-child')")

            store = DemoStore(db_path)
            data = store.load_journal_data()

            self.assertEqual(data["child"]["id"], "child-a")
            with closing(sqlite3.connect(db_path)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            self.assertIn("directions", tables)
            self.assertNotIn("sessions", tables)

    def test_seed_validation_rejects_unknown_direction_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_path = Path(tmp) / "seed.json"
            seed = json.loads(Path("backend/demo_seed.json").read_text(encoding="utf-8"))
            seed["visits"][0]["direction_id"] = "missing-direction"
            seed_path.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")

            store = DemoStore(Path(tmp) / "app.sqlite3", seed_path=seed_path)

            with self.assertRaisesRegex(StoreError, "unknown direction"):
                store.load_journal_data()

    def test_seed_validation_rejects_invalid_visit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_path = Path(tmp) / "seed.json"
            seed = json.loads(Path("backend/demo_seed.json").read_text(encoding="utf-8"))
            seed["visits"][0]["status"] = "mystery"
            seed_path.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")

            store = DemoStore(Path(tmp) / "app.sqlite3", seed_path=seed_path)

            with self.assertRaisesRegex(StoreError, "invalid visit status"):
                store.load_journal_data()

    def test_seed_validation_rejects_negative_metric_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_path = Path(tmp) / "seed.json"
            seed = json.loads(Path("backend/demo_seed.json").read_text(encoding="utf-8"))
            seed["goal_updates"][0]["metric_value"] = -1
            seed_path.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")

            store = DemoStore(Path(tmp) / "app.sqlite3", seed_path=seed_path)

            with self.assertRaisesRegex(StoreError, "metric_value"):
                store.load_journal_data()

    def test_seed_validation_rejects_negative_visit_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_path = Path(tmp) / "seed.json"
            seed = json.loads(Path("backend/demo_seed.json").read_text(encoding="utf-8"))
            seed["visits"][0]["scheduled_end"] = "2026-05-20T09:00:00+03:00"
            seed_path.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")

            store = DemoStore(Path(tmp) / "app.sqlite3", seed_path=seed_path)

            with self.assertRaisesRegex(StoreError, "scheduled duration"):
                store.load_journal_data()

    def test_store_manages_children_and_journal_selects_active_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")

            child = store.create_child(
                {"display_name": "Ребёнок Б", "age_label": "6 лет", "focus": "адаптация"}
            )
            store.update_child(child["id"], {"display_name": "Ребёнок Бета", "focus": "коммуникация"})

            selected = store.load_journal_data(child["id"])
            children = store.list_children()

            self.assertEqual(selected["child"]["display_name"], "Ребёнок Бета")
            self.assertEqual(selected["child"]["age_label"], "6 лет")
            self.assertTrue(any(item["id"] == child["id"] for item in children))

    def test_parent_accounts_only_load_assigned_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            child = store.create_child(
                {"display_name": "Ребёнок Б", "age_label": "6 лет", "focus": "адаптация"}
            )
            parent = store.create_parent(
                {"display_name": "Родитель Б", "login": "parent-b", "access_code": "demo-b"}
            )
            store.assign_parent_child(parent["id"], child["id"])

            children = store.list_parent_children(parent["id"])
            selected = store.load_parent_journal_data(parent["id"], child["id"])

            self.assertEqual(children, [child])
            self.assertEqual(selected["child"]["id"], child["id"])
            with self.assertRaisesRegex(StoreError, "not linked"):
                store.load_parent_journal_data(parent["id"], "child-a")

    def test_seed_contains_demo_parent_for_parent_portal(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")

            parents = store.list_parents()
            children = store.list_parent_children("parent-a")

            self.assertTrue(any(parent["id"] == "parent-a" for parent in parents))
            self.assertEqual(children[0]["id"], "child-a")

    def test_archived_child_is_not_available_for_parent_journal_until_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            child = store.create_child(
                {"display_name": "Ребёнок Б", "age_label": "6 лет", "focus": "адаптация"}
            )

            archived = store.archive_child(child["id"])

            self.assertIsNotNone(archived["archived_at"])
            with self.assertRaisesRegex(StoreError, "Child is archived"):
                store.load_journal_data(child["id"])

            restored = store.restore_child(child["id"])
            self.assertIsNone(restored["archived_at"])
            self.assertEqual(store.load_journal_data(child["id"])["child"]["id"], child["id"])

    def test_store_manages_directions_assignments_goals_and_visits(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            child = store.create_child(
                {"display_name": "Ребёнок Б", "age_label": "6 лет", "focus": "адаптация"}
            )
            direction = store.create_direction(
                {"slug": "music", "title": "Музыка", "color": "#445566", "sort_order": 7}
            )

            store.assign_direction(child["id"], direction["id"])
            goal = store.create_goal(
                child["id"],
                {
                    "direction_id": direction["id"],
                    "title": "Петь короткую фразу",
                    "description": "Повторять знакомую строку.",
                    "status": "active",
                    "metric_label": "повторов",
                    "metric_target": 5,
                    "sort_order": 1,
                },
            )
            visit = store.create_visit(
                child["id"],
                {
                    "direction_id": direction["id"],
                    "scheduled_start": "2026-06-10T10:00:00+03:00",
                    "scheduled_end": "2026-06-10T11:00:00+03:00",
                    "status": "scheduled",
                },
            )

            data = store.load_journal_data(child["id"])

            self.assertEqual(data["directions"][0]["id"], direction["id"])
            self.assertEqual(data["goals"][0]["id"], goal["id"])
            self.assertEqual(data["visits"][0]["id"], visit["id"])

            store.remove_child_direction(child["id"], direction["id"])
            self.assertEqual(store.load_journal_data(child["id"])["directions"], [])
            self.assertTrue(any(item["id"] == direction["id"] for item in store.list_directions()))

    def test_store_validates_admin_goal_and_visit_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            direction = store.create_direction(
                {"slug": "music", "title": "Музыка", "color": "#445566", "sort_order": 7}
            )

            with self.assertRaisesRegex(StoreError, "assigned direction"):
                store.create_goal(
                    "child-a",
                    {
                        "direction_id": direction["id"],
                        "title": "Цель",
                        "description": "Описание",
                        "status": "active",
                    },
                )

            with self.assertRaisesRegex(StoreError, "duration"):
                store.create_visit(
                    "child-a",
                    {
                        "direction_id": "direction-aba",
                        "scheduled_start": "2026-06-10T11:00:00+03:00",
                        "scheduled_end": "2026-06-10T10:00:00+03:00",
                        "status": "scheduled",
                    },
                )


if __name__ == "__main__":
    unittest.main()
