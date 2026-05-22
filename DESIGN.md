# Design System — Local Voice After-Session OS

## Product Context

- **What this is:** A local web-first demo that turns a specialist's post-session voice note into a transcript, internal draft note, parent message, and anonymized progress history.
- **Who it's for:** Individual correction/development specialists and center directors evaluating the workflow.
- **Space/industry:** Child development, correctional education, speech/behavioral therapy documentation.
- **Project type:** Dense web app workspace, not a landing page.

## Aesthetic Direction

- **Direction:** Quiet clinical warmth.
- **Decoration level:** Intentional minimal.
- **Mood:** Calm, reliable, and human. The interface should feel like a trusted workspace after a long session, not like a hospital EHR or generic AI dashboard.
- **Reference signals:** SpeechWay, Ogma Therapy, and OVScribe all emphasize record → review/edit → save/export, human approval, history, and safety.

## Typography

- **Display:** IBM Plex Sans or Inter — clear professional interface headings.
- **Body:** IBM Plex Sans or Inter — readable Russian UI and notes.
- **UI/Labels:** Same as body, medium weight.
- **Data/Tables:** IBM Plex Sans with tabular numerals.
- **Parent Preview:** Optional Source Serif 4 or Literata for a warmer letter-like feel.
- **Scale:** 12px metadata, 14px controls, 16px body, 20px panel titles, 28px page title.

## Color

- **Approach:** Restrained balanced.
- **Background:** `#F7F5F0` warm white.
- **Surface:** `#FFFFFF`.
- **Ink:** `#202124`.
- **Muted text:** `#66706B`.
- **Primary:** `#2F7D7A` muted teal for action and active pipeline states.
- **Secondary:** `#8BAA8F` sage for calm success states.
- **Human accent:** `#B46A55` clay for parent-message warmth.
- **Warning:** `#E8C36A` soft amber.
- **Error:** `#B94747`.
- **Border:** `#DDD8CE`.
- **Dark mode:** Not in v1.

## Spacing

- **Base unit:** 8px.
- **Density:** Compact professional.
- **Scale:** 4, 8, 12, 16, 24, 32, 48.

## Layout

- **Approach:** Three-zone workspace.
- **Desktop grid:** left child/history rail, center audio/transcript/internal note, right parent preview/history Q&A.
- **Mobile:** Collapses into stacked sections.
- **Border radius:** 8px max for panels and repeated items; 999px only for tiny status pills.

## Motion

- **Approach:** Minimal-functional.
- **Use for:** Pipeline status changes, save confirmation, focus and error transitions.
- **Avoid:** Decorative AI shimmer, blobs, bokeh, oversized marketing hero animation.

## UX Rules

- Human approval is visually dominant before save.
- Pipeline status must show the actual processing step.
- Parent message preview should feel warmer than the internal note.
- Do not show real personal data in demo copy.
- Do not imply production compliance; keep copy honest about local demo behavior.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-22 | Quiet clinical warmth | Balances trust, care, and operational clarity for a sensitive child-development workflow. |
