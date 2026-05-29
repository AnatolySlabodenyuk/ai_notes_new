# Parent Card MVP

Local demo for a director presentation at a center supporting children with ASD.

The flow: a specialist records or uploads a short post-session voice note, the app transcribes it locally, local Ollama generates three parent-friendly draft blocks, the specialist edits and publishes them, and the parent-facing child card shows the approved session feed.

This is a discovery demo with anonymized data. It simulates role separation in the UI, but it is not production authorization or compliance software.

## Run

Use the bundled or system Python:

```powershell
python -m backend.server
```

If `python` is not on PATH in this Codex workspace, use:

```powershell
& 'C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m backend.server
```

Open:

```text
http://127.0.0.1:8765
```

## Demo Script

1. Start the app and keep `Специалист / админ` selected.
2. Pick an anonymized child.
3. Upload audio, or paste a transcript manually if local ASR is unavailable.
4. Generate three blocks: `Что делали`, `Что получилось`, `Что попробовать дома`.
5. Edit the blocks as the specialist and publish them.
6. Switch to `Родитель` mode and show the read-only session feed.

Use the director conversation to learn:

- how specialists currently write parent updates;
- how long the post-session communication takes;
- what would block the center from adopting this workflow.

## Local Models

Ollama must be running locally. Defaults:

```text
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_NUM_PREDICT=700
```

Make sure the selected model is pulled in Ollama:

```powershell
ollama list
ollama pull gemma3:4b
```

For audio transcription, install `faster-whisper` in the Python environment used to run the server. The backend uses Whisper model `small` by default.

If ASR is not available during a demo, paste a transcript manually and use the `Сгенерировать 3 блока из транскрипта` button.

## Test

```powershell
& 'C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

## Data

Demo state is stored in a local SQLite database:

```text
data/app.sqlite3
```

If the database is missing or empty, the app creates it and loads anonymized demo seed data from `backend/demo_seed.json`. The `data/` directory is ignored by git so local pilot data stays out of the repository.

Only anonymized demo children/sessions belong here. The UI role switch is for demonstration only; do not use this MVP with real child personal data.
