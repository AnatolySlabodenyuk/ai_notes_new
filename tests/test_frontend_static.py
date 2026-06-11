import unittest
from pathlib import Path


class FrontendStaticSafetyTests(unittest.TestCase):
    def setUp(self):
        self.html = Path("frontend/index.html").read_text(encoding="utf-8")
        self.app = Path("frontend/app.js").read_text(encoding="utf-8")
        self.styles = Path("frontend/styles.css").read_text(encoding="utf-8")

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
        self.assertIn('navigate(`#${route.path}?${route.params}`)', self.app)

    def test_month_switch_loads_snapshot_through_hash_change(self):
        self.assertIn("const selectedMonth = event.target.value;", self.app)
        self.assertIn('route.params.set("month", selectedMonth);', self.app)
        self.assertIn('route.params.delete("date");', self.app)
        self.assertIn('navigate(`#${route.path}?${route.params}`)', self.app)
        self.assertNotIn("state.month = event.target.value;", self.app)

    def test_dashboard_copy_and_demo_boundary_are_present(self):
        self.assertIn("Электронный журнал", self.html)
        self.assertIn("обезличенные данные", self.html)
        self.assertIn("Коротко о посещениях", self.html)
        self.assertIn("Требует внимания", self.html)
        self.assertIn("Ближайшие занятия", self.html)
        self.assertIn("Обзор", self.html)
        self.assertIn("Календарь", self.html)

    def test_static_assets_use_matching_cache_busting_version(self):
        self.assertIn('href="/static/styles.css?v=7"', self.html)
        self.assertIn('src="/static/app.js?v=7"', self.html)

    def test_calendar_navigation_is_separate_from_child_card(self):
        profile_start = self.html.index('<section class="profile-card panel">')
        profile_end = self.html.index("</section>", profile_start)
        profile_markup = self.html[profile_start:profile_end]

        self.assertIn('<nav class="app-nav"', self.html)
        self.assertNotIn("overviewTab", profile_markup)
        self.assertNotIn("calendarTab", profile_markup)

    def test_parent_overview_blocks_are_rendered(self):
        self.assertIn("summaryGrid", self.html)
        self.assertIn("attentionList", self.html)
        self.assertIn("upcomingList", self.html)
        self.assertIn("summaryCard", self.app)
        self.assertIn("attention-card", self.app)
        self.assertIn("upcoming-card", self.app)

    def test_old_voice_note_workflow_is_not_rendered(self):
        self.assertNotIn("audioInput", self.html)
        self.assertNotIn("transcript", self.html)
        self.assertNotIn("whatWeDid", self.html)
        self.assertNotIn("processAudio", self.app)
        self.assertNotIn("generateFromTranscript", self.app)

    def test_direction_navigation_preserves_source_and_month(self):
        self.assertIn("?month=${state.month}&from=overview", self.app)
        self.assertIn("&date=${day.date}&from=calendar", self.app)
        self.assertIn('const directionSource = route.params.get("from") === "calendar" ? "calendar" : "overview";', self.app)
        self.assertIn('navigate(`#/${directionSource}?month=${state.month}`)', self.app)
        self.assertIn('directionSource === "calendar" ? "← Вернуться к календарю" : "← Вернуться к обзору"', self.app)

    def test_direction_navigation_keeps_source_tab_active(self):
        self.assertIn('const directionSource = isDirection && route.params.get("from") === "calendar" ? "calendar" : "overview";', self.app)
        self.assertIn('const isCalendarContext = isCalendar || (isDirection && directionSource === "calendar");', self.app)

    def test_mobile_summary_grid_is_compact_and_direction_heading_stacks(self):
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", self.styles)
        self.assertIn(".summary-card", self.styles)
        self.assertIn("align-items: start;", self.styles)

    def test_calendar_and_goals_have_timeline_hooks(self):
        self.assertIn("calendar-day-heading", self.app)
        self.assertIn("calendar-time", self.app)
        self.assertIn("metric-panel", self.app)
        self.assertIn("goal-lead", self.app)
        self.assertIn(".calendar-day::before", self.styles)
        self.assertIn(".goal-update::before", self.styles)


if __name__ == "__main__":
    unittest.main()
