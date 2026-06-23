# Audit: Electronic Child Journal MVP

Date: 2026-06-23

## Scope

Read-only audit of the current MVP for the child journal project.

Checked:
- repository setup and project instructions;
- README, `.gitignore`, backend, frontend, tests, and demo seed behavior;
- API health and main parent/admin endpoints on the local server;
- static frontend structure, route logic, form handling, and responsive CSS;
- existing test suite.

Not fully checked:
- real browser click-through and screenshots. The local OpenClaw browser route could not start because the environment has no supported Chrome/Chromium installed. No browser or Playwright dependency was installed during this audit.

## Current State

The MVP is functional as a local product demo.

Implemented surfaces:
- parent journal with child profile, directions, visits, goals, and calendar;
- operational center with children, parents, directions, child-direction assignment, goals, visits, and settings;
- SQLite demo store seeded from `backend/demo_seed.json`;
- JSON API through the Python standard library HTTP server;
- Python `unittest` coverage for journal logic, store behavior, API behavior, and static frontend checks.

Baseline checks:
- `python -m unittest discover -s tests` passes: 47 tests.
- `GET /api/health` returns OK.
- Demo seed currently exposes 1 child, 1 parent, 6 directions, 11 visits, and 3 goals.

## Findings

### P0 - Blocks Demo

No P0 issues found during this audit.

The app starts, core APIs respond, and the existing automated tests pass.

### P1 - Should Fix Before Showing

1. Admin form errors are not shown to the user.

   Evidence: `loadJournal()` and initial boot show errors through `errorBox`, but submit handlers such as `childForm`, `directionForm`, `goalForm`, `visitForm`, `parentForm`, and assignment forms call `mutate(...)` without local `try/catch`.

   Impact: validation failures like missing fields, duplicate slugs, or invalid visit durations can fail silently from the user's point of view, likely only surfacing in the console.

   Recommended fix: wrap all admin form submit handlers and inline row actions in a shared `runAction(...)` helper that shows success/error state in `errorBox` or a local admin notification area.

2. The operational "Day" screen is misleading.

   Evidence: `renderAdminDay()` renders `activeVisits.slice(0, 6)` from all active visits. The heading says "Сегодня и ближайшие занятия", but the logic does not filter by current date, selected date, or upcoming visits.

   Impact: a specialist may see old/past demo visits under a "today" heading. This weakens the demo because the admin surface looks operational but does not behave like a day planner.

   Recommended fix: either rename the section to "Ближайшие и последние занятия" for the demo, or add real date filtering and a date selector.

3. Empty state in admin day does not render.

   Evidence: `activeVisits.slice(0, 6).map(...) || [empty(...)]` always returns an array; an empty array is truthy in JavaScript.

   Impact: if a child has no visits, the admin day list becomes empty without explanation.

   Recommended fix: create `const shownVisits = activeVisits.slice(0, 6)` and render `shownVisits.length ? ... : [empty(...)]`.

4. README and implementation are already drifting.

   Evidence:
   - README says SQLite schema version is `4`;
   - code uses `SCHEMA_VERSION = 5`;
   - README references `docs/README.md`, `docs/DESIGN.md`, `docs/implementation-plan.md`, and `docs/parent-portal-mvp-plan.md`, but `docs/` has no files in this checkout.

   Impact: a future Codex/local developer can follow stale docs and make wrong assumptions.

   Recommended fix: update README and create current docs, starting with this audit and a short roadmap/demo script.

5. Parent access is hardcoded in the frontend.

   Evidence: `state.parentId = "parent-a"`.

   Impact: acceptable for a demo, but it should be visibly framed as a demo limitation. It is not production authentication.

   Recommended fix: keep hardcoded parent for MVP demo, but document this as a non-production boundary and avoid calling it authorization.

### P2 - UX/UI Polish

1. Mobile parent navigation reserves three columns for two tabs.

   Evidence: responsive CSS sets `.app-nav { grid-template-columns: 1fr 1fr 1fr; }`, but the parent nav has only "Обзор" and "Календарь".

   Impact: mobile layout likely has an awkward empty column.

   Recommended fix: use two columns for `.app-nav`, or use `repeat(auto-fit, minmax(...))`.

2. Parent and admin surfaces share one visual language too much.

   Impact: parent view should feel calm and explanatory, while operational center should be denser and faster for staff. Current structure is functional but still reads like a generic admin demo.

   Recommended fix: keep parent surface lighter and more narrative; make admin tables denser with clearer row-level actions and local feedback.

3. Access codes are rendered as plain text inputs.

   Evidence: parent rows render `access_code` with a standard text input.

   Impact: acceptable in a local demo, but not good even for a realistic admin prototype.

   Recommended fix: use `type="password"` or a masked display with "show/copy" only when needed.

4. Legacy frontend constant remains.

   Evidence: `LEGACY_JOURNAL_ENDPOINT` exists and is tested, but the parent flow uses `/api/parent/journal`.

   Impact: minor confusion for future maintainers.

   Recommended fix: either remove it and update tests, or explicitly document why the legacy endpoint remains for compatibility.

5. Some labels promise more than the demo implements.

   Examples:
   - "Настройки" is read-only informational cards;
   - "История" appears as a mini-tab label but does not behave as an interactive tab;
   - "Сегодня и ближайшие занятия" does not filter by day.

   Recommended fix: either make these interactions real, or tune copy to match the current demo.

## Architecture Notes

- `backend/store.py` is large for a demo store. It currently contains schema creation, seed loading, validation, CRUD, parent-child access, and helper methods. Do not rewrite it wholesale, but split later if the project grows.
- `frontend/app.js` mixes API calls, global state, rendering, form handling, and route logic. This is acceptable for a no-framework MVP, but future changes should extract small helpers instead of adding more global branching.
- `frontend/styles.css` is large enough that UI redesign should be done in focused sections, not as a one-shot restyle.

## Recommended First Fixes

1. Add shared frontend action/error handling for admin mutations.
2. Fix `renderAdminDay()` empty state and clarify/filter the "today" logic.
3. Fix mobile `.app-nav` two-tab layout.
4. Update README schema version and remove stale docs references or create the referenced docs.
5. Mask parent access codes in the admin UI.

## Suggested Workflow

For each fix:

1. Write or update the smallest relevant test.
2. Implement the minimal change.
3. Run `python -m unittest discover -s tests`.
4. Smoke-test the changed flow through API or browser.
5. Keep each commit focused.

For UI/UX:

1. Add browser tooling only after explicit approval.
2. Run desktop and mobile screenshots for parent overview, parent calendar, direction detail, admin day, admin children, admin parents, and admin schedule.
3. Convert observed UI issues into prioritized fixes rather than doing a broad redesign.

