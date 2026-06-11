import unittest

from backend.journal import build_journal_snapshot


def visit(
        visit_id,
        direction_id,
        scheduled_start,
        scheduled_end,
        status,
        actual_start=None,
        actual_end=None,
        reason_code=None,
        rescheduled_to_visit_id=None,
):
    return {
        "id": visit_id,
        "child_id": "child-a",
        "direction_id": direction_id,
        "scheduled_start": scheduled_start,
        "scheduled_end": scheduled_end,
        "actual_start": actual_start,
        "actual_end": actual_end,
        "status": status,
        "reason_code": reason_code,
        "rescheduled_to_visit_id": rescheduled_to_visit_id,
    }


class JournalSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.child = {
            "id": "child-a",
            "display_name": "Ребёнок А",
            "age_label": "7 лет",
            "focus": "коммуникация и самостоятельность",
        }
        self.directions = [
            {"id": "direction-aba", "slug": "aba", "title": "ABA", "color": "#2f7d7a", "sort_order": 1},
            {
                "id": "direction-speech",
                "slug": "speech",
                "title": "Логопед",
                "color": "#b46a55",
                "sort_order": 2,
            },
        ]

    def build(self, visits, goals=None, updates=None, now="2026-06-01T08:00:00+03:00", month="2026-06"):
        return build_journal_snapshot(
            month=month,
            child=self.child,
            directions=self.directions,
            visits=visits,
            goals=goals or [],
            goal_updates=updates or [],
            now=now,
        )

    def test_counts_full_and_partial_visits_from_actual_minutes(self):
        snapshot = self.build(
            [
                visit(
                    "full",
                    "direction-aba",
                    "2026-06-02T10:00:00+03:00",
                    "2026-06-02T11:00:00+03:00",
                    "completed",
                    "2026-06-02T10:00:00+03:00",
                    "2026-06-02T11:00:00+03:00",
                ),
                visit(
                    "partial",
                    "direction-aba",
                    "2026-06-03T10:00:00+03:00",
                    "2026-06-03T11:00:00+03:00",
                    "partial",
                    "2026-06-03T10:15:00+03:00",
                    "2026-06-03T10:45:00+03:00",
                    "late_arrival",
                ),
            ]
        )

        aba = snapshot["directions"][0]
        self.assertEqual(aba["planned_minutes"], 120)
        self.assertEqual(aba["actual_minutes"], 90)
        self.assertEqual(snapshot["overview"]["planned_minutes"], 120)
        self.assertEqual(snapshot["overview"]["actual_minutes"], 90)

    def test_cancelled_absent_and_rescheduled_visits_do_not_add_actual_minutes(self):
        snapshot = self.build(
            [
                visit(
                    "cancelled",
                    "direction-aba",
                    "2026-06-02T10:00:00+03:00",
                    "2026-06-02T11:00:00+03:00",
                    "cancelled",
                    reason_code="specialist_unavailable",
                ),
                visit(
                    "absent",
                    "direction-aba",
                    "2026-06-03T10:00:00+03:00",
                    "2026-06-03T11:00:00+03:00",
                    "absent",
                    reason_code="child_absent",
                ),
                visit(
                    "moved-from",
                    "direction-aba",
                    "2026-06-04T10:00:00+03:00",
                    "2026-06-04T11:00:00+03:00",
                    "rescheduled",
                    reason_code="family_request",
                    rescheduled_to_visit_id="moved-to",
                ),
                visit(
                    "moved-to",
                    "direction-aba",
                    "2026-06-05T10:00:00+03:00",
                    "2026-06-05T11:00:00+03:00",
                    "completed",
                    "2026-06-05T10:00:00+03:00",
                    "2026-06-05T11:00:00+03:00",
                ),
            ]
        )

        aba = snapshot["directions"][0]
        self.assertEqual(aba["planned_minutes"], 240)
        self.assertEqual(aba["actual_minutes"], 60)
        self.assertEqual(len(snapshot["overview"]["attention_items"]), 3)

    def test_builds_month_comparison_from_previous_month(self):
        snapshot = self.build(
            [
                visit(
                    "may",
                    "direction-aba",
                    "2026-05-20T10:00:00+03:00",
                    "2026-05-20T11:00:00+03:00",
                    "completed",
                    "2026-05-20T10:00:00+03:00",
                    "2026-05-20T11:00:00+03:00",
                ),
                visit(
                    "june",
                    "direction-aba",
                    "2026-06-20T10:00:00+03:00",
                    "2026-06-20T12:00:00+03:00",
                    "completed",
                    "2026-06-20T10:00:00+03:00",
                    "2026-06-20T12:00:00+03:00",
                ),
            ]
        )

        self.assertEqual(snapshot["overview"]["comparison"]["actual_minutes_delta"], 60)

    def test_groups_month_by_school_timezone_offset(self):
        snapshot = self.build(
            [
                visit(
                    "boundary",
                    "direction-aba",
                    "2026-05-31T21:30:00+00:00",
                    "2026-05-31T22:30:00+00:00",
                    "completed",
                    "2026-05-31T21:30:00+00:00",
                    "2026-05-31T22:30:00+00:00",
                )
            ]
        )

        self.assertEqual(snapshot["overview"]["planned_minutes"], 60)
        self.assertEqual(snapshot["calendar"][0]["date"], "2026-06-01")

    def test_returns_three_upcoming_visits_and_goal_history(self):
        goals = [
            {
                "id": "goal-requests",
                "child_id": "child-a",
                "direction_id": "direction-aba",
                "title": "Самостоятельно просить помощь",
                "description": "Использовать короткую просьбу без подсказки.",
                "status": "progress",
                "metric_label": "самостоятельных просьб из 10 попыток",
                "metric_target": 10,
                "sort_order": 1,
            }
        ]
        updates = [
            {
                "id": "update-1",
                "goal_id": "goal-requests",
                "updated_at": "2026-05-20T12:00:00+03:00",
                "status": "active",
                "comment": "Начали наблюдение.",
                "metric_value": 3,
            },
            {
                "id": "update-2",
                "goal_id": "goal-requests",
                "updated_at": "2026-06-01T12:00:00+03:00",
                "status": "progress",
                "comment": "Чаще просит без подсказки.",
                "metric_value": 6,
            },
        ]
        visits = [
            visit(
                f"upcoming-{day}",
                "direction-aba",
                f"2026-06-0{day}T10:00:00+03:00",
                f"2026-06-0{day}T11:00:00+03:00",
                "scheduled",
            )
            for day in range(2, 6)
        ]

        snapshot = self.build(visits, goals=goals, updates=updates)

        self.assertEqual(len(snapshot["overview"]["upcoming_visits"]), 3)
        goal = snapshot["directions"][0]["goals"][0]
        self.assertEqual(goal["latest_update"]["metric_value"], 6)
        self.assertEqual(len(goal["updates"]), 2)

    def test_empty_month_returns_zero_totals(self):
        snapshot = self.build([])

        self.assertEqual(snapshot["overview"]["planned_minutes"], 0)
        self.assertEqual(snapshot["overview"]["actual_minutes"], 0)
        self.assertEqual(snapshot["calendar"], [])

    def test_goal_history_excludes_updates_after_selected_month(self):
        goals = [
            {
                "id": "goal-requests",
                "child_id": "child-a",
                "direction_id": "direction-aba",
                "title": "Самостоятельно просить помощь",
                "description": "Использовать короткую просьбу без подсказки.",
                "status": "progress",
                "metric_label": "самостоятельных просьб",
                "metric_target": 10,
                "sort_order": 1,
            }
        ]
        updates = [
            {
                "id": "update-may",
                "goal_id": "goal-requests",
                "updated_at": "2026-05-20T12:00:00+03:00",
                "status": "active",
                "comment": "Начали наблюдение.",
                "metric_value": 3,
            },
            {
                "id": "update-june",
                "goal_id": "goal-requests",
                "updated_at": "2026-06-01T12:00:00+03:00",
                "status": "progress",
                "comment": "Чаще просит без подсказки.",
                "metric_value": 6,
            },
        ]

        snapshot = self.build([], goals=goals, updates=updates, month="2026-05")

        goal = snapshot["directions"][0]["goals"][0]
        self.assertEqual([update["id"] for update in goal["updates"]], ["update-may"])
        self.assertEqual(goal["latest_update"]["metric_value"], 3)


if __name__ == "__main__":
    unittest.main()
