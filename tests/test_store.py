import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.store import DemoStore, StoreError, UnknownChildError


class DemoStoreTests(unittest.TestCase):
    def test_creates_sqlite_database_and_loads_seed_data_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app.sqlite3"
            store = DemoStore(db_path)

            data = store.load()

            self.assertIn("children", data)
            self.assertEqual(len(data["children"]), 2)
            self.assertTrue(all(child.get("parent_label") for child in data["children"]))
            self.assertTrue(db_path.exists())
            with closing(sqlite3.connect(db_path)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            self.assertIn("children", tables)
            self.assertIn("sessions", tables)

    def test_appends_published_parent_session_to_child_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            child_id = store.load()["children"][0]["id"]

            session = store.add_session(
                child_id,
                {
                    "transcript": "Сегодня ребёнок повторял звук Р в слогах.",
                    "what_we_did": "Тренировали звук Р в слогах.",
                    "what_changed": "Появились более устойчивые попытки произношения.",
                    "home_practice": "Дома спокойно повторить 5 коротких слов.",
                },
            )

            data = store.load()
            child = data["children"][0]
            self.assertEqual(session["status"], "published")
            self.assertEqual(child["sessions"][-1]["id"], session["id"])
            self.assertIn("published_at", child["sessions"][-1])
            self.assertEqual(child["sessions"][-1]["what_we_did"], "Тренировали звук Р в слогах.")
            self.assertNotIn("internal_note", child["sessions"][-1])

    def test_get_child_returns_child_with_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            child_id = store.load()["children"][0]["id"]

            child = store.get_child(child_id)

            self.assertEqual(child["id"], child_id)
            self.assertGreaterEqual(len(child["sessions"]), 1)

    def test_add_child_creates_empty_profile_with_persisted_goals(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            store.load()

            child = store.add_child(
                {
                    "display_name": "Ребёнок В",
                    "age_label": "7 лет",
                    "focus": "речь и спокойные переходы",
                    "goals": ["просить помощь", "закреплять домашнюю практику"],
                }
            )

            loaded = store.get_child(child["id"])
            self.assertTrue(child["id"].startswith("child-"))
            self.assertEqual(loaded["display_name"], "Ребёнок В")
            self.assertEqual(loaded["parent_label"], "Родитель: Ребёнок В")
            self.assertEqual(loaded["age_label"], "7 лет")
            self.assertEqual(loaded["focus"], "речь и спокойные переходы")
            self.assertEqual(loaded["goals"], ["просить помощь", "закреплять домашнюю практику"])
            self.assertEqual(loaded["sessions"], [])

    def test_add_child_rejects_blank_display_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            store.load()

            with self.assertRaises(StoreError):
                store.add_child({"display_name": "   ", "goals": []})

    def test_database_open_errors_raise_named_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.sqlite3"
            path.mkdir()
            store = DemoStore(path)

            with self.assertRaises(StoreError):
                store.load()

    def test_reset_replaces_existing_data_with_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            child_id = store.load()["children"][0]["id"]
            store.add_session(
                child_id,
                {
                    "transcript": "Сегодня ребёнок повторял звук Р в слогах.",
                    "what_we_did": "Тренировали звук Р в слогах.",
                    "what_changed": "Появились более устойчивые попытки произношения.",
                    "home_practice": "Дома спокойно повторить 5 коротких слов.",
                },
            )

            data = store.reset()

            self.assertEqual(len(data["children"]), 2)
            self.assertEqual(len(data["children"][0]["sessions"]), 1)

    def test_reset_child_sessions_clears_only_selected_child_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            data = store.load()
            first_child_id = data["children"][0]["id"]
            second_child_id = data["children"][1]["id"]
            store.add_session(
                first_child_id,
                {
                    "transcript": "Сегодня ребёнок повторял звук Р в слогах.",
                    "what_we_did": "Тренировали звук Р в слогах.",
                    "what_changed": "Появились более устойчивые попытки произношения.",
                    "home_practice": "Дома спокойно повторить 5 коротких слов.",
                },
            )

            updated = store.reset_child_sessions(first_child_id)

            first_child = next(child for child in updated["children"] if child["id"] == first_child_id)
            second_child = next(child for child in updated["children"] if child["id"] == second_child_id)
            self.assertEqual(first_child["sessions"], [])
            self.assertGreaterEqual(len(second_child["sessions"]), 1)

    def test_reset_child_sessions_rejects_unknown_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            store.load()

            with self.assertRaises(UnknownChildError):
                store.reset_child_sessions("missing-child")

    def test_unknown_child_raises_specific_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DemoStore(Path(tmp) / "app.sqlite3")
            store.load()

            with self.assertRaises(UnknownChildError):
                store.get_child("missing-child")


if __name__ == "__main__":
    unittest.main()
