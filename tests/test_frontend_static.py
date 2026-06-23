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
        self.assertIn("/api/parent/journal?parent_id=", self.app)
        self.assertIn("/api/parent/children?parent_id=", self.app)
        self.assertIn("/api/admin/children", self.app)

    def test_hash_routes_cover_parent_and_admin_surfaces(self):
        self.assertIn("#/parent/overview", self.app)
        self.assertIn("#/parent/calendar", self.app)
        self.assertIn("#/parent/direction/", self.app)
        self.assertIn("#/admin/day", self.app)
        self.assertIn("#/admin/children", self.app)
        self.assertIn("#/admin/schedule", self.app)
        self.assertIn("#/admin/directions", self.app)
        self.assertIn("#/admin/parents", self.app)
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
        self.assertIn("Родительский кабинет", self.html)
        self.assertIn("Операционный центр", self.html)
        self.assertIn("Обзор", self.html)
        self.assertIn("Календарь", self.html)

    def test_static_assets_use_matching_cache_busting_version(self):
        self.assertIn('href="/static/styles.css?v=11"', self.html)
        self.assertIn('src="/static/app.js?v=11"', self.html)

    def test_calendar_navigation_is_separate_from_child_card(self):
        profile_start = self.html.index('<section class="profile-card panel" id="profileCard">')
        profile_end = self.html.index("</section>", profile_start)
        profile_markup = self.html[profile_start:profile_end]

        self.assertIn('<nav class="app-nav"', self.html)
        self.assertNotIn("overviewTab", profile_markup)
        self.assertNotIn("calendarTab", profile_markup)

    def test_customer_removed_overview_blocks_are_not_rendered(self):
        self.assertNotIn("summaryGrid", self.html)
        self.assertNotIn("attentionList", self.html)
        self.assertNotIn("upcomingList", self.html)
        self.assertNotIn("Коротко о посещениях", self.html)
        self.assertNotIn("Требует внимания", self.html)
        self.assertNotIn("Ближайшие занятия", self.html)
        self.assertNotIn("summaryCard", self.app)
        self.assertNotIn("attention-card", self.app)
        self.assertNotIn("upcoming-card", self.app)

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
        self.assertIn('navigate(`#/parent/${directionSource}?month=${state.month}`)', self.app)
        self.assertIn('directionSource === "calendar" ? "← Вернуться к календарю" : "← Вернуться к обзору"', self.app)

    def test_direction_navigation_keeps_source_tab_active(self):
        self.assertIn('const directionSource = isDirection && route.params.get("from") === "calendar" ? "calendar" : "overview";', self.app)
        self.assertIn('const isCalendarContext = isCalendar || (isDirection && directionSource === "calendar");', self.app)

    def test_mobile_summary_grid_is_compact_and_direction_heading_stacks(self):
        self.assertIn("@media (max-width: 620px)", self.styles)
        self.assertIn(".direction-grid", self.styles)
        self.assertIn("align-items: start;", self.styles)

    def test_calendar_and_goals_have_timeline_hooks(self):
        self.assertIn("calendar-day-heading", self.app)
        self.assertIn("calendar-time", self.app)
        self.assertIn("metric-panel", self.app)
        self.assertIn("goal-lead", self.app)
        self.assertIn(".calendar-day::before", self.styles)
        self.assertIn(".goal-update::before", self.styles)

    def test_admin_routes_forms_and_mutation_calls_are_present(self):
        self.assertIn("#/admin", self.html)
        self.assertIn("adminView", self.html)
        self.assertIn("childForm", self.html)
        self.assertIn("directionForm", self.html)
        self.assertIn("goalForm", self.html)
        self.assertIn("visitForm", self.html)
        self.assertIn("loadAdmin", self.app)
        self.assertIn('mutate("/api/admin/children", "POST"', self.app)
        self.assertIn('"PUT"', self.app)
        self.assertIn('"DELETE"', self.app)
        self.assertIn("/api/admin/directions", self.app)
        self.assertIn("/goals", self.app)
        self.assertIn("/visits", self.app)

    def test_admin_layout_has_operational_sections(self):
        self.assertIn("Операционный центр", self.html)
        self.assertIn("День", self.html)
        self.assertIn("Дети", self.html)
        self.assertIn("Родители", self.html)
        self.assertIn("Настройки", self.html)
        self.assertIn("Направления", self.html)
        self.assertIn("Цели", self.html)
        self.assertIn("Расписание", self.html)
        self.assertIn("childWorkspaceView", self.html)
        self.assertIn("Быстрые действия", self.html)
        self.assertIn(".admin-layout", self.styles)
        self.assertIn(".admin-shell", self.styles)
        self.assertIn(".admin-sidebar", self.styles)
        self.assertIn(".admin-table", self.styles)

    def test_parent_cabinet_does_not_render_admin_controls(self):
        parent_start = self.html.index('<section id="parentShell"')
        admin_start = self.html.index('<section id="adminShell"')
        parent_markup = self.html[parent_start:admin_start]

        self.assertNotIn("Админка", parent_markup)
        self.assertNotIn("childForm", parent_markup)
        self.assertNotIn("directionForm", parent_markup)
        self.assertNotIn("goalForm", parent_markup)
        self.assertNotIn("visitForm", parent_markup)
        self.assertIn("parentChildSelect", parent_markup)


if __name__ == "__main__":
    unittest.main()
