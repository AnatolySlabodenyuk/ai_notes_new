# Electronic Child Journal MVP

Local read-only demo for discussing a parent portal with a school supporting children with ASD.

The parent sees one anonymized child, a direction overview, a shared calendar, and direction-specific visits and goals with progress history.

This is a discovery demo. It uses anonymized data and simulates a parent's access to one child. It is not production authorization or compliance software.

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

The journal endpoint returns one anonymized parent-cabinet snapshot. Invalid months return `400 invalid_month`.

## Test

```powershell
& 'C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

## Data

Demo state is stored in a local SQLite database:

```text
data/app.sqlite3
```

If the local schema version changes, the app recreates the ignored demo database from `backend/demo_seed.json`. Do not place real child personal data in the seed or local demo database.
