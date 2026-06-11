# Electronic Child Journal MVP

Local read-only demo for discussing a parent portal with a school supporting children with ASD.

The parent sees one anonymized child, a direction overview, a shared calendar, and direction-specific visits and goals
with progress history. The interface is intentionally narrow: it demonstrates parent-facing navigation and content, not
staff workflows, authentication, audio processing, or AI generation.

This is a discovery demo. It uses anonymized data and simulates a parent's access to one child. It is not production
authorization or compliance software.

## Current Product Surface

- `Обзор` shows the child's active directions as cards with monthly planned and actual hours.
- `Календарь` shows all visits for the selected month, grouped by date and color-coded by direction.
- Direction detail pages show visits, monthly comparison against the previous month, and goal progress history.
- The seeded demo supports May 2026 and June 2026.
- The frontend is read-only and talks only to `GET /api/journal?month=YYYY-MM`.

## Project Layout

```text
backend/   Python HTTP server, snapshot builder, SQLite demo store, seed data
frontend/  Static HTML, CSS, and JavaScript application
tests/     unittest coverage for API, store, journal logic, and static frontend safety
docs/      Product, design, implementation, and historical planning notes
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

The `tzdata` package is required on Windows because Python does not normally
have a system timezone database there.

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

1. Open the overview and point out that the parent starts from the child's active directions.
2. Open a direction card to review that direction's visits, received hours, and goals.
3. Open `Календарь` and select a visit to show date-based navigation into a direction.
4. Open the `ABA` direction and show a measurable goal with its small trend chart.
5. Open `Психолог` and show a goal whose progress is explained with dated comments instead of a misleading percentage.
6. Switch to May 2026 to show month filtering and comparison behavior inside direction details.

Use the customer conversation to learn:

- which exceptions parents should see in the calendar or direction detail, if any, and which should remain internal;
- who records planned and actual attendance;
- how each specialist updates goals;
- which goal metrics are genuinely meaningful for parents.

## API

```text
GET /api/journal?month=YYYY-MM
GET /api/health
```

The journal endpoint returns one anonymized parent-cabinet snapshot with `child`, `overview`, `directions`, and
`calendar` sections. Invalid or missing months return `400 invalid_month`. Store initialization or seed errors return
`500 store_error`.

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

If the local schema version changes, the app recreates the ignored demo database from `backend/demo_seed.json`. Do not
place real child personal data in the seed or local demo database.

## Documentation

- `docs/README.md` indexes current and historical documentation.
- `docs/DESIGN.md` describes the current UX rules and visual direction.
- `docs/implementation-plan.md` and `docs/parent-portal-mvp-plan.md` capture implementation and product planning
  context.
