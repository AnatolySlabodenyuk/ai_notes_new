# Unified Implementation Plan: Local Voice After-Session OS

## Summary

Build a standalone web-first MVP for a director demo: a specialist uploads or records post-session audio, a local ASR model transcribes it, a local Ollama model generates an internal note, a parent message, and a history update, and the specialist edits and confirms before saving.

## Architecture

```text
Web UI
  -> Local Backend API
    -> ASR module: audio -> transcript
    -> Ollama proxy: transcript + history -> drafts
    -> JSON store: confirmed sessions -> local anonymized memory
  -> Web UI: edit, confirm, save
```

## Source Of Truth Decisions

- Standalone local demo; no production deployment.
- Backend proxy owns ASR, prompts, Ollama errors, and JSON persistence.
- ASR uses local `faster-whisper` when installed.
- Ollama uses local `/api/chat` with JSON output.
- Storage is `data/demo-store.json` with anonymized demo children/sessions.
- Design follows `DESIGN.md`.

## Not In Scope

- Real personal data, auth, roles, audit logs, full CRM, Telegram, ROI dashboard, source-linked trust layer, cloud deploy.
