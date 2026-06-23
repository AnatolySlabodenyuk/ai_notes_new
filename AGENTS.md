# AGENTS.md

## Project

This repository is a local MVP/demo of an electronic child journal for a child support or development center.

The current product has two surfaces:
- parent journal: selected child's directions, schedule, visits, goals, and progress;
- operational center: staff/admin workflows for children, parents, directions, goals, and visits.

Use anonymized demo data only. Do not add real children, parents, diagnoses, phone numbers, addresses, documents, or other personal data to seed files, tests, screenshots, docs, commits, or logs.

## Stack

- Backend: Python standard library HTTP server, SQLite store, JSON API.
- Frontend: static HTML, CSS, and JavaScript.
- Tests: Python `unittest`.
- Demo database: `data/app.sqlite3`, ignored by git and recreated from `backend/demo_seed.json`.

## Useful Commands

Run the app:

```bash
python -m backend.server
```

Open:

```text
http://127.0.0.1:8765
```

Run tests:

```bash
python -m unittest discover -s tests
```

## Working Rules

- Before code changes, state a short plan and wait for explicit approval.
- For feature work and bug fixes, write or update tests first when the behavior is testable.
- Keep changes small and reviewable.
- Do not introduce a framework or new dependency without explicit approval.
- Prefer the existing simple architecture unless the change clearly needs a new boundary.
- Keep parent-facing copy clear, warm, and non-medical. Do not let the app present AI or the system as making diagnostic decisions.
- Keep admin workflows practical for a small center: fewer screens, clear labels, predictable actions.

## Verification

Before calling work complete:
- run `python -m unittest discover -s tests`;
- smoke-test the changed user flow when UI/API behavior changed;
- check `git status --short`;
- mention any generated ignored files such as `data/app.sqlite3` or `__pycache__/`.

## Current Risks

- `backend/store.py`, `frontend/app.js`, and `frontend/styles.css` are large MVP files. Avoid broad rewrites; improve touched areas gradually.
- README and docs can drift from implementation. Update docs when behavior, commands, API, or demo script changes.
- The project is not production-ready: no real authentication, authorization, audit logging, compliance model, or personal-data handling guarantees.

