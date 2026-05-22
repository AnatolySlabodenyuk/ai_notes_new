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

## Local Models

Ollama must be running locally. Defaults:

```text
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.1
```

Override in PowerShell:

```powershell
$env:OLLAMA_MODEL='qwen2.5:7b'
```

For audio transcription, install `faster-whisper` in the Python environment used to run the server and make sure the selected Whisper model can be downloaded or is cached locally. The backend currently uses model name `small` by default.

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
