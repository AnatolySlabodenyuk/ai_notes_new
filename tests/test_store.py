import json
import tempfile
import unittest
from pathlib import Path

from backend.store import DemoStore, StoreError, UnknownChildError


class DemoStoreTests(unittest.TestCase):
    def test_loads_seed_data_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "demo-store.json")

            data = store.load()

            self.assertIn("children", data)
            self.assertGreaterEqual(len(data["children"]), 1)
            self.assertTrue((Path(tmp) / "demo-store.json").exists())

    def test_appends_confirmed_session_to_child_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "demo-store.json")
            child_id = store.load()["children"][0]["id"]

            session = store.add_session(
                child_id,
                {
                    "transcript": "Сегодня ребёнок повторял звук Р в слогах.",
                    "internal_note": "Работали над артикуляцией звука Р.",
                    "parent_message": "Сегодня тренировались произносить звук Р.",
                    "history_update": "Появились более устойчивые попытки произношения.",
                },
            )

            data = store.load()
            child = data["children"][0]
            self.assertEqual(session["status"], "confirmed")
            self.assertEqual(child["sessions"][-1]["id"], session["id"])
            self.assertEqual(child["sessions"][-1]["parent_message"], "Сегодня тренировались произносить звук Р.")

    def test_corrupt_json_raises_named_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo-store.json"
            path.write_text("{broken", encoding="utf-8")
            store = DemoStore(path)

            with self.assertRaises(StoreError):
                store.load()

    def test_reset_replaces_existing_data_with_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo-store.json"
            path.write_text(json.dumps({"children": []}), encoding="utf-8")
            store = DemoStore(path)

            data = store.reset()

            self.assertGreaterEqual(len(data["children"]), 1)

    def test_unknown_child_raises_specific_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "demo-store.json")
            store.load()

            with self.assertRaises(UnknownChildError):
                store.get_child("missing-child")


if __name__ == "__main__":
    unittest.main()
