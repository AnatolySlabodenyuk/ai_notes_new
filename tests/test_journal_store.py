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
            self.assertEqual(version, 3)

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


if __name__ == "__main__":
    unittest.main()
