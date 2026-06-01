from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

SCHOOL_TIMEZONE = ZoneInfo("Europe/Moscow")
ATTENTION_STATUSES = {"partial", "cancelled", "absent", "rescheduled"}


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(SCHOOL_TIMEZONE)


def _minutes_between(start: str | None, end: str | None) -> int:
    if not start or not end:
        return 0
    return max(0, round((_parse_timestamp(end) - _parse_timestamp(start)).total_seconds() / 60))


def _month_of(value: str) -> str:
    return _parse_timestamp(value).strftime("%Y-%m")


def _previous_month(month: str) -> str:
    year, month_number = map(int, month.split("-"))
    if month_number == 1:
        return f"{year - 1}-12"
    return f"{year}-{month_number - 1:02d}"


def _actual_minutes(visit: dict[str, Any]) -> int:
    return _minutes_between(visit.get("actual_start"), visit.get("actual_end"))


def _planned_minutes(visit: dict[str, Any]) -> int:
    return _minutes_between(visit["scheduled_start"], visit["scheduled_end"])


def _decorate_visit(visit: dict[str, Any]) -> dict[str, Any]:
    scheduled = _parse_timestamp(visit["scheduled_start"])
    return {
        **visit,
        "date": scheduled.strftime("%Y-%m-%d"),
        "planned_minutes": _planned_minutes(visit),
        "actual_minutes": _actual_minutes(visit),
    }


def _build_goal(goal: dict[str, Any], updates: list[dict[str, Any]]) -> dict[str, Any]:
    ordered_updates = sorted(updates, key=lambda item: item["updated_at"])
    return {
        **goal,
        "updates": ordered_updates,
        "latest_update": ordered_updates[-1] if ordered_updates else None,
    }


def _sum_minutes(visits: list[dict[str, Any]]) -> tuple[int, int]:
    return (
        sum(visit["planned_minutes"] for visit in visits),
        sum(visit["actual_minutes"] for visit in visits),
    )


def build_journal_snapshot(
        *,
        month: str,
        child: dict[str, Any],
        directions: list[dict[str, Any]],
        visits: list[dict[str, Any]],
        goals: list[dict[str, Any]],
        goal_updates: list[dict[str, Any]],
        now: str,
) -> dict[str, Any]:
    previous_month = _previous_month(month)
    decorated_visits = [_decorate_visit(visit) for visit in visits]
    current_visits = [visit for visit in decorated_visits if _month_of(visit["scheduled_start"]) == month]
    previous_visits = [
        visit for visit in decorated_visits if _month_of(visit["scheduled_start"]) == previous_month
    ]
    updates_by_goal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for update in goal_updates:
        updates_by_goal[update["goal_id"]].append(update)

    goals_by_direction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for goal in goals:
        goals_by_direction[goal["direction_id"]].append(_build_goal(goal, updates_by_goal[goal["id"]]))

    direction_snapshots = []
    for direction in sorted(directions, key=lambda item: item["sort_order"]):
        direction_visits = [visit for visit in current_visits if visit["direction_id"] == direction["id"]]
        previous_direction_visits = [
            visit for visit in previous_visits if visit["direction_id"] == direction["id"]
        ]
        planned_minutes, actual_minutes = _sum_minutes(direction_visits)
        _, previous_actual_minutes = _sum_minutes(previous_direction_visits)
        direction_snapshots.append(
            {
                **direction,
                "planned_minutes": planned_minutes,
                "actual_minutes": actual_minutes,
                "comparison": {"actual_minutes_delta": actual_minutes - previous_actual_minutes},
                "visits": direction_visits,
                "goals": sorted(goals_by_direction[direction["id"]], key=lambda item: item["sort_order"]),
            }
        )

    planned_minutes, actual_minutes = _sum_minutes(current_visits)
    _, previous_actual_minutes = _sum_minutes(previous_visits)
    attention_items = [visit for visit in current_visits if visit["status"] in ATTENTION_STATUSES]
    now_datetime = _parse_timestamp(now)
    upcoming_visits = sorted(
        (
            visit
            for visit in decorated_visits
            if _parse_timestamp(visit["scheduled_start"]) >= now_datetime and visit["status"] == "scheduled"
        ),
        key=lambda item: item["scheduled_start"],
    )[:3]

    calendar: list[dict[str, Any]] = []
    visits_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for visit in current_visits:
        visits_by_date[visit["date"]].append(visit)
    for date, day_visits in sorted(visits_by_date.items()):
        calendar.append({"date": date, "visits": sorted(day_visits, key=lambda item: item["scheduled_start"])})

    return {
        "month": month,
        "child": child,
        "overview": {
            "planned_minutes": planned_minutes,
            "actual_minutes": actual_minutes,
            "comparison": {"actual_minutes_delta": actual_minutes - previous_actual_minutes},
            "attention_items": attention_items,
            "upcoming_visits": upcoming_visits,
        },
        "directions": direction_snapshots,
        "calendar": calendar,
    }
