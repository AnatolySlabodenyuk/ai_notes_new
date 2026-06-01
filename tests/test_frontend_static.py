import unittest
from pathlib import Path


class FrontendStaticSafetyTests(unittest.TestCase):
    def setUp(self):
        self.html = Path("frontend/index.html").read_text(encoding="utf-8")
        self.app = Path("frontend/app.js").read_text(encoding="utf-8")

    def test_app_does_not_render_store_data_with_inner_html(self):
        self.assertNotIn(".innerHTML", self.app)

    def test_frontend_uses_read_only_journal_endpoint(self):
        self.assertIn("/api/journal?month=", self.app)
        self.assertNotIn("/api/children", self.app)
        self.assertNotIn("method: \"POST\"", self.app)

    def test_hash_routes_cover_overview_calendar_and_direction(self):
        self.assertIn("#/overview", self.app)
        self.assertIn("#/calendar", self.app)
        self.assertIn("#/direction/", self.app)
        self.assertIn("hashchange", self.app)
        self.assertIn('navigate(`#${route.path}?month=${selectedMonth}`)', self.app)

    def test_month_switch_loads_snapshot_through_hash_change(self):
        self.assertIn("const selectedMonth = event.target.value;", self.app)
        self.assertIn('navigate(`#${route.path}?month=${selectedMonth}`)', self.app)
        self.assertNotIn("state.month = event.target.value;", self.app)

    def test_dashboard_copy_and_demo_boundary_are_present(self):
        self.assertIn("Электронный журнал", self.html)
        self.assertIn("обезличенные данные", self.html)
        self.assertIn("Требует внимания", self.html)
        self.assertIn("Ближайшие занятия", self.html)
        self.assertIn("Обзор", self.html)
        self.assertIn("Календарь", self.html)

    def test_old_voice_note_workflow_is_not_rendered(self):
        self.assertNotIn("audioInput", self.html)
        self.assertNotIn("transcript", self.html)
        self.assertNotIn("whatWeDid", self.html)
        self.assertNotIn("processAudio", self.app)
        self.assertNotIn("generateFromTranscript", self.app)


if __name__ == "__main__":
    unittest.main()
