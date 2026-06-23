# Electronic Child Journal

Local product demo for an electronic child journal used by a school or center supporting children with ASD. The app now has two surfaces:

- a read-only parent journal for reviewing one selected child's directions, calendar, visits, and goals;
- an internal operational admin for maintaining children, the shared direction catalog, child-direction assignments, child-specific goals, and one-off calendar visits.

This is still a local discovery/product demo. It uses anonymized data and does not implement production login, authorization, audit logging, or compliance guarantees.

## Current Product Surface

- `Обзор` shows the selected child's active directions as cards with monthly planned and actual hours.
- `Календарь` shows all active visits for the selected child and month, grouped by date and color-coded by direction.
- Direction detail pages show visits, monthly comparison against the previous month, and goal progress history.
- `Админка` lets staff create, edit, archive, and restore children and directions; connect directions to a child; and manage that child's goals and one-off visit schedule.
- The parent journal can load a specific child with `child_id`, while keeping the previous first-active-child fallback.
- The seeded demo supports May 2026 and June 2026.

## Project Layout

```text
backend/   Python HTTP server, snapshot builder, SQLite store, seed data
frontend/  Static HTML, CSS, and JavaScript application
tests/     unittest coverage for API, store, journal logic, and static frontend checks
docs/      Current docs plus historical planning artifacts
data/      Ignored local SQLite demo database
```

## Run

Create a virtual environment and install the runtime dependency:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m backend.server
```

The `tzdata` package is required on Windows because Python does not normally have a system timezone database there.

If the existing `.venv` points to a removed Python installation, recreate it:

```powershell
Remove-Item -Recurse -Force .venv
python -m venv .venv
```

Open:

```text
http://127.0.0.1:8765
```

Set `LOG_LEVEL=DEBUG` or another standard Python logging level to change server verbosity.

## Demo Script

1. Open the overview and point out the selected child dropdown.
2. Open a direction card to review that direction's visits, received hours, and goals.
3. Open `Календарь` and select a visit to show date-based navigation into a direction.
4. Open `ABA` and show a measurable goal with its small trend chart.
5. Open `Психолог` and show a goal whose progress is explained with dated comments.
6. Switch to May 2026 to show month filtering and comparison behavior.
7. Open `Админка`, add or edit a child, connect a direction, add a goal, and add a one-off scheduled visit.

Use the customer conversation to learn:

- which exceptions parents should see in the calendar or direction detail, if any, and which should remain internal;
- who records planned and actual attendance;
- how each specialist updates goals;
- which goal metrics are genuinely meaningful for parents;
- which admin workflows need roles, audit, or bulk operations before production.

## API

```text
GET /api/journal?month=YYYY-MM
GET /api/journal?month=YYYY-MM&child_id=<child-id>
GET /api/health

GET  /api/admin/children
POST /api/admin/children
PUT  /api/admin/children/{child_id}
POST /api/admin/children/{child_id}/archive
POST /api/admin/children/{child_id}/restore

GET  /api/admin/directions
POST /api/admin/directions
PUT  /api/admin/directions/{direction_id}
POST /api/admin/directions/{direction_id}/archive
POST /api/admin/directions/{direction_id}/restore

GET    /api/admin/children/{child_id}/directions
POST   /api/admin/children/{child_id}/directions
DELETE /api/admin/children/{child_id}/directions/{direction_id}

GET    /api/admin/children/{child_id}/goals
POST   /api/admin/children/{child_id}/goals
PUT    /api/admin/children/{child_id}/goals/{goal_id}
DELETE /api/admin/children/{child_id}/goals/{goal_id}

GET    /api/admin/children/{child_id}/visits
POST   /api/admin/children/{child_id}/visits
PUT    /api/admin/children/{child_id}/visits/{visit_id}
DELETE /api/admin/children/{child_id}/visits/{visit_id}
```

The journal endpoint returns a computed parent-cabinet snapshot with `child`, `overview`, `directions`, and `calendar` sections. Invalid or missing months return `400 invalid_month`. Admin validation errors return `400 validation_error`. Store initialization or seed errors return `500 store_error`.

## Test

After activating the virtual environment, run:

```powershell
python -m unittest discover -s tests
```

If the local `.venv` is unavailable, the Codex runtime Python can also run the suite:

```powershell
& 'C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

## Data

Demo state is stored in a local SQLite database:

```text
data/app.sqlite3
```

If the local schema version changes, the app recreates the ignored demo database from `backend/demo_seed.json`. The current SQLite schema version is `5`. Do not place real child personal data in the seed or local demo database.

## Documentation

- `docs/README.md` indexes current and historical documentation.
- `docs/DESIGN.md` describes the current UX rules and visual direction.
- `docs/implementation-plan.md` captures current backend, frontend, data, API, and test context.
- `docs/parent-portal-mvp-plan.md` captures the current product/demo plan.
