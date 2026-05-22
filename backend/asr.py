from __future__ import annotations

import tempfile
from pathlib import Path


class ASRError(RuntimeError):
    """Base class for local speech-to-text failures."""


class ASRUnavailableError(ASRError):
    """Raised when local ASR dependencies or models are unavailable."""


class EmptyTranscriptError(ASRError):
    """Raised when ASR succeeds but returns no usable transcript."""


def transcribe_audio(audio_bytes: bytes, model_name: str = "small", language: str = "ru") -> str:
    if not audio_bytes:
        raise EmptyTranscriptError("Audio file is empty.")

    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception as exc:
        raise ASRUnavailableError(
            "Local ASR requires faster-whisper. Install it and make sure the Whisper model is available."
        ) from exc

    with tempfile.NamedTemporaryFile(delete=False, suffix=".audio") as tmp:
        tmp.write(audio_bytes)
        tmp_path = Path(tmp.name)

    try:
        try:
            model = WhisperModel(model_name, device="auto", compute_type="auto")
            segments, _info = model.transcribe(str(tmp_path), language=language)
            transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        except Exception as exc:
            raise ASRUnavailableError(f"Local ASR failed: {exc}") from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    if not transcript:
        raise EmptyTranscriptError("ASR returned an empty transcript.")
    return transcript
