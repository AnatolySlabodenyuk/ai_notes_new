# Local Voice After-Session OS

Standalone local MVP for a director demo: upload an anonymized post-session audio note, transcribe it locally, generate drafts through local Ollama, review/edit, and save into local JSON demo memory.

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

When running with redirected output, request logs are written to `server.log`:

```powershell
Get-Content server.log -Wait
```

Logs include request method/path, status, duration, ASR timing, Ollama model, generation timing, and save events. Audio payloads and full note text are not logged.

## Local Models

Ollama must be running locally. Defaults:

```text
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_NUM_PREDICT=700
```

Make sure the selected model is actually pulled in Ollama:

```powershell
ollama list
ollama pull qwen3:8b
```

Or point the app at a model you already have.

Override in PowerShell:

```powershell
$env:OLLAMA_MODEL='qwen3:8b'
$env:OLLAMA_TIMEOUT_SECONDS='180'
$env:OLLAMA_NUM_PREDICT='700'
```

The app sends `think=false` to Ollama chat requests. This matters for thinking models such as Qwen3; without it, the model can spend the whole timeout budget producing hidden reasoning instead of the JSON response.

For audio transcription, install `faster-whisper` in the Python environment used to run the server and make sure the selected Whisper model can be downloaded or is cached locally. The backend currently uses model name `small` by default.

The first Whisper run may print:

```text
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
```

This is a Hugging Face rate-limit warning, not an app failure. You can ignore it for occasional local demos, or set `HF_TOKEN` if downloads are slow or rate-limited.

## Test

```powershell
& 'C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

## Data

Demo state is stored in:

```text
data/demo-store.json
```

Only anonymized demo children/sessions belong here. This MVP is not production compliance software and must not process real child personal data.
