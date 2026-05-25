from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import sys
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .asr import ASRError, transcribe_audio
from .ollama_client import OllamaClient, OllamaError
from .pipeline import generate_drafts
from .store import DemoStore, StoreError, UnknownChildError


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "frontend"
DATA_DIR = ROOT / "data"
STORE = DemoStore(DATA_DIR / "demo-store.json")
LOGGER = logging.getLogger("after_session_os")


class ClientRequestError(RuntimeError):
    """Raised when the client sends malformed input."""


class AppHandler(BaseHTTPRequestHandler):
    server_version = "AfterSessionOS/0.1"

    def do_GET(self) -> None:
        self._begin_request()
        if self.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            self._finish_request(HTTPStatus.NO_CONTENT, 0)
            return
        if self.path == "/" or self.path.startswith("/static/"):
            self._serve_static()
            return
        if self.path == "/api/children":
            self._json_response(STORE.load())
            return
        if self.path == "/api/health":
            self._json_response(
                {
                    "ok": True,
                    "pid": os.getpid(),
                    "ollama_url": self._ollama_url(),
                    "model": self._ollama_model(),
                }
            )
            return
        self._json_error("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        self._begin_request()
        try:
            if self.path == "/api/reset":
                self._json_response(STORE.reset())
            elif self.path == "/api/transcribe":
                self._transcribe_audio()
            elif self.path == "/api/generate":
                self._generate_drafts()
            elif self.path == "/api/process-audio":
                self._process_audio()
            elif self.path == "/api/save-session":
                self._save_session()
            elif self.path == "/api/ask-history":
                self._ask_history()
            else:
                self._json_error("Not found", HTTPStatus.NOT_FOUND)
        except UnknownChildError as exc:
            self._json_error(str(exc), HTTPStatus.NOT_FOUND, "unknown_child")
        except ClientRequestError as exc:
            self._json_error(str(exc), HTTPStatus.BAD_REQUEST, "bad_request")
        except ASRError as exc:
            self._json_error(str(exc), HTTPStatus.BAD_GATEWAY, "asr_error")
        except StoreError as exc:
            self._json_error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR, "store_error")

    def _process_audio(self) -> None:
        payload = self._read_json()
        self._log_info(
            "process_audio_start child_id=%s asr_model=%s audio_base64_chars=%d",
            payload.get("child_id", ""),
            payload.get("asr_model") or "small",
            len(str(payload.get("audio_base64", ""))),
        )
        transcript = self._transcribe_from_payload(payload)
        child = STORE.get_child(str(payload.get("child_id", "")))
        try:
            started = time.perf_counter()
            client = self._ollama_client()
            self._log_info(
                "ollama_generate_start model=%s timeout_seconds=%s transcript_chars=%d",
                client.model,
                client.timeout_seconds,
                len(transcript),
            )
            drafts = generate_drafts(transcript, child, client)
            self._log_info("ollama_generate_done duration_ms=%d", self._elapsed_ms(started))
        except (OllamaError, ValueError) as exc:
            self._log_error("ollama_generate_failed error=%s", exc)
            self._json_error(str(exc), HTTPStatus.BAD_GATEWAY, "ollama_error")
            return
        self._log_info("process_audio_done transcript_chars=%d", len(transcript))
        self._json_response({"transcript": transcript, "drafts": drafts})

    def _transcribe_audio(self) -> None:
        payload = self._read_json()
        self._log_info(
            "transcribe_start child_id=%s asr_model=%s audio_base64_chars=%d",
            payload.get("child_id", ""),
            payload.get("asr_model") or "small",
            len(str(payload.get("audio_base64", ""))),
        )
        transcript = self._transcribe_from_payload(payload)
        self._log_info("transcribe_done transcript_chars=%d", len(transcript))
        self._json_response({"transcript": transcript})

    def _generate_drafts(self) -> None:
        payload = self._read_json()
        child = STORE.get_child(str(payload.get("child_id", "")))
        transcript = str(payload.get("transcript", ""))
        try:
            started = time.perf_counter()
            client = self._ollama_client()
            self._log_info(
                "generate_start child_id=%s model=%s timeout_seconds=%s transcript_chars=%d",
                payload.get("child_id", ""),
                client.model,
                client.timeout_seconds,
                len(transcript),
            )
            drafts = generate_drafts(transcript, child, client)
            self._log_info("generate_done duration_ms=%d", self._elapsed_ms(started))
        except (OllamaError, ValueError) as exc:
            self._log_error("generate_failed error=%s", exc)
            self._json_error(str(exc), HTTPStatus.BAD_GATEWAY, "ollama_error")
            return
        self._json_response({"drafts": drafts})

    def _transcribe_from_payload(self, payload: dict[str, Any]) -> str:
        audio_base64 = str(payload.get("audio_base64", ""))
        if "," in audio_base64:
            audio_base64 = audio_base64.split(",", 1)[1]
        try:
            audio = base64.b64decode(audio_base64, validate=True)
        except ValueError as exc:
            raise ClientRequestError("Audio payload is not valid base64.") from exc

        model_name = str(payload.get("asr_model") or "small")
        started = time.perf_counter()
        self._log_info("asr_start model=%s audio_bytes=%d", model_name, len(audio))
        transcript = transcribe_audio(audio, model_name=model_name)
        self._log_info("asr_done duration_ms=%d transcript_chars=%d", self._elapsed_ms(started), len(transcript))
        return transcript

    def _save_session(self) -> None:
        payload = self._read_json()
        required = ("child_id", "transcript", "internal_note", "parent_message", "history_update")
        missing = [key for key in required if not str(payload.get(key, "")).strip()]
        if missing:
            self._json_error(f"Missing fields: {', '.join(missing)}", HTTPStatus.BAD_REQUEST, "validation_error")
            return
        session = STORE.add_session(str(payload["child_id"]), payload)
        self._log_info("save_session_done child_id=%s session_id=%s", payload["child_id"], session["id"])
        self._json_response({"session": session, "data": STORE.load()})

    def _ask_history(self) -> None:
        payload = self._read_json()
        child = STORE.get_child(str(payload.get("child_id", "")))
        question = str(payload.get("question", "")).strip()
        if not question:
            self._json_error("Question is empty.", HTTPStatus.BAD_REQUEST, "validation_error")
            return
        self._log_info("ask_history_start child_id=%s question_chars=%d", payload.get("child_id", ""), len(question))
        messages = [
            {
                "role": "system",
                "content": "Отвечай только на основании истории занятий. Если данных нет, так и скажи. Не выдумывай факты.",
            },
            {"role": "user", "content": json.dumps({"question": question, "child": child}, ensure_ascii=False)},
        ]
        try:
            started = time.perf_counter()
            answer = self._ollama_client().chat_json(
                [
                    messages[0],
                    {
                        "role": "user",
                        "content": messages[1]["content"]
                        + '\nВерни JSON: {"internal_note":"", "parent_message":"", "history_update":"", "qa_suggestions":["ответ"]}',
                    },
                ]
            )
            self._log_info("ask_history_done duration_ms=%d", self._elapsed_ms(started))
        except OllamaError as exc:
            self._log_error("ask_history_failed error=%s", exc)
            self._json_error(str(exc), HTTPStatus.BAD_GATEWAY, "ollama_error")
            return
        self._json_response({"answer": answer.get("qa_suggestions", [""])[0], "raw": answer})

    def _serve_static(self) -> None:
        relative = "index.html" if self.path == "/" else self.path.replace("/static/", "", 1)
        path = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in path.parents and path != STATIC_DIR.resolve():
            self._json_error("Invalid path", HTTPStatus.BAD_REQUEST)
            return
        if not path.exists() or not path.is_file():
            self._json_error("Not found", HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.end_headers()
        body = path.read_bytes()
        self.wfile.write(body)
        self._finish_request(HTTPStatus.OK, len(body))

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise ClientRequestError("Request body is not valid JSON.") from exc

    def _json_response(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self._finish_request(status, len(body))

    def _json_error(self, message: str, status: HTTPStatus, code: str = "error") -> None:
        self._log_error("request_error status=%s code=%s message=%s", status.value, code, message)
        self._json_response({"error": {"code": code, "message": message}}, status)

    def _ollama_url(self) -> str:
        return os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

    def _ollama_model(self) -> str:
        return os.environ.get("OLLAMA_MODEL", "qwen3:8b")

    def _ollama_timeout_seconds(self) -> float:
        return float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "180"))

    def _ollama_num_predict(self) -> int | None:
        value = os.environ.get("OLLAMA_NUM_PREDICT", "700").strip()
        return int(value) if value else None

    def _ollama_client(self) -> OllamaClient:
        return OllamaClient(
            base_url=self._ollama_url(),
            model=self._ollama_model(),
            timeout_seconds=self._ollama_timeout_seconds(),
            think=False,
            num_predict=self._ollama_num_predict(),
        )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _begin_request(self) -> None:
        self.request_id = uuid.uuid4().hex[:8]
        self.request_started_at = time.perf_counter()
        self._log_info("request_start method=%s path=%s", self.command, self.path)

    def _finish_request(self, status: HTTPStatus, body_bytes: int) -> None:
        self._log_info(
            "request_done status=%d duration_ms=%d response_bytes=%d",
            status.value,
            self._elapsed_ms(getattr(self, "request_started_at", time.perf_counter())),
            body_bytes,
        )

    def _elapsed_ms(self, started: float) -> int:
        return round((time.perf_counter() - started) * 1000)

    def _log_info(self, message: str, *args: object) -> None:
        LOGGER.info("[%s] " + message, getattr(self, "request_id", "--------"), *args)

    def _log_error(self, message: str, *args: object) -> None:
        LOGGER.error("[%s] " + message, getattr(self, "request_id", "--------"), *args)


def configure_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s pid=%(process)d %(message)s",
        stream=sys.stdout,
        force=True,
    )


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    configure_logging()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORE.load()
    httpd = ThreadingHTTPServer((host, port), AppHandler)
    LOGGER.info("After-Session OS running at http://%s:%s", host, port)
    httpd.serve_forever()


if __name__ == "__main__":
    run()
