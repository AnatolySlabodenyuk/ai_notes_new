# Journal Navigation And Mobile Polish Design

## Goal

Fix the confirmed context-loss bugs in the child journal and tighten the mobile overview without redesigning the product.

## Scope

The implementation covers four changes:

1. Direction pages remember whether the user arrived from the overview or calendar.
2. The back button returns to that source section while preserving the selected month.
3. Goal updates shown for a selected month include only records at or before the end of that month.
4. The overview becomes denser on narrow screens and nested cards receive quieter styling.

The overall information architecture, color palette, desktop layout, and data model remain unchanged.

## Navigation Design

Direction links include a `from` hash query parameter:

- Direction cards on the overview navigate with `from=overview`.
- Calendar visits navigate with `from=calendar`.

The direction view resolves the return target from the current route. Known values return to their matching section with `month=<selected month>`. Missing or invalid values fall back to the overview with the selected month.

The back button label reflects the target:

- `← Вернуться к обзору`
- `← Вернуться к календарю`

The upper tabs keep orientation while inside a direction:

- A direction opened from calendar highlights `Календарь`.
- A direction opened from overview, or without a valid source, highlights `Обзор`.

## Goal History Design

The backend snapshot treats the selected month as an end-of-period view. A goal update is included when its school-timezone month is less than or equal to the selected month.

This preserves useful prior history while preventing future records from leaking into earlier monthly views. `latest_update`, metric values, and sparklines are derived only from the filtered updates.

## Mobile Visual Design

At widths up to `620px`:

- Summary metrics use a `2x2` grid instead of four full-width cards.
- Summary cards use tighter padding and slightly smaller values.
- The directions section title and explanatory hint stack vertically.
- Nested visit, goal, calendar-day, direction, and calendar-visit cards use a flatter visual treatment than top-level panels.

Top-level panels remain distinct so the user can scan the overview as a small number of sections.

## Verification

Automated tests cover:

- Goal updates from a later month are absent from an earlier snapshot.
- Prior goal history remains available in a later snapshot.
- Frontend route strings include source context and preserve month on return.
- CSS contains the narrow-screen `2x2` summary layout and stacked directions header.

Browser verification covers:

- Calendar visit → direction → back returns to calendar and preserves month.
- Overview direction → back returns to overview and preserves month.
- May direction detail does not show June goal updates.
- Mobile overview is shorter and its directions heading no longer competes with the hint.

