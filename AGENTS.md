# Repository Guidelines

## Project Structure & Module Organization

This repository is a local MVP demo for an electronic child journal. Backend code lives in `backend/`, with `server.py` exposing HTTP endpoints, `store.py` managing SQLite-backed demo state, `journal.py` holding journal logic, and `demo_seed.json` containing anonymized seed data. Frontend assets are static files in `frontend/`: `index.html`, `app.js`, and `styles.css`. Tests live in `tests/` and cover backend behavior plus frontend static checks. Local demo data is stored in `data/app.sqlite3` and should remain ignored.

## Build, Test, and Development Commands

- `python -m venv .venv` creates a local virtual environment.
- `.\.venv\Scripts\Activate.ps1` activates it on Windows PowerShell.
- `python -m pip install -r requirements.txt` installs runtime dependencies; currently `tzdata` is required for Windows timezone support.
- `python -m backend.server` runs the local app at `http://127.0.0.1:8765`.
- `python -m unittest discover -s tests` runs the test suite. The README also documents the bundled Codex runtime Python path for environments where the local `.venv` is stale.

## Coding Style & Naming Conventions

Use Python standard-library patterns and 4-space indentation. Keep backend modules small and explicit, with `snake_case` functions, methods, and test names. Frontend code is plain HTML, CSS, and JavaScript; avoid adding build tooling unless the project actually needs it.

## Testing Guidelines

Tests use `unittest` and should be named `test_*.py`. Prefer temporary directories and local HTTP servers, as existing tests do, rather than mutating shared demo data. Add or update tests when changing API behavior, seed validation, schema handling, or frontend assumptions.

## Commit & Pull Request Guidelines

Recent commits are short, imperative summaries such as `fix frontend` and `docs: specify journal navigation and mobile polish`. Keep commits focused and describe the user-visible change. Pull requests should include a concise summary, test results, and screenshots or notes for UI changes.

## Security & Configuration Tips

Do not place real child personal data in `backend/demo_seed.json` or `data/app.sqlite3`. This project is a discovery demo, not production authorization or compliance software.
