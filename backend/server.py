from __future__ import annotations

import base64
import json
import mimetypes
import os
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


class ClientRequestError(RuntimeError):
    """Raised when the client sends malformed input."""


class AppHandler(BaseHTTPRequestHandler):
    server_version = "AfterSessionOS/0.1"

    def do_GET(self) -> None:
        if self.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        if self.path == "/" or self.path.startswith("/static/"):
            self._serve_static()
            return
        if self.path == "/api/children":
            self._json_response(STORE.load())
            return
        if self.path == "/api/health":
            self._json_response({"ok": True, "ollama_url": self._ollama_url(), "model": self._ollama_model()})
            return
        self._json_error("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
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
        transcript = self._transcribe_from_payload(payload)
        child = STORE.get_child(str(payload.get("child_id", "")))
        try:
            drafts = generate_drafts(transcript, child, self._ollama_client())
        except (OllamaError, ValueError) as exc:
            self._json_error(str(exc), HTTPStatus.BAD_GATEWAY, "ollama_error")
            return
        self._json_response({"transcript": transcript, "drafts": drafts})

    def _transcribe_audio(self) -> None:
        payload = self._read_json()
        transcript = self._transcribe_from_payload(payload)
        self._json_response({"transcript": transcript})

    def _generate_drafts(self) -> None:
        payload = self._read_json()
        child = STORE.get_child(str(payload.get("child_id", "")))
        transcript = str(payload.get("transcript", ""))
        try:
            drafts = generate_drafts(transcript, child, self._ollama_client())
        except (OllamaError, ValueError) as exc:
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

        return transcribe_audio(audio, model_name=str(payload.get("asr_model") or "small"))

    def _save_session(self) -> None:
        payload = self._read_json()
        required = ("child_id", "transcript", "internal_note", "parent_message", "history_update")
        missing = [key for key in required if not str(payload.get(key, "")).strip()]
        if missing:
            self._json_error(f"Missing fields: {', '.join(missing)}", HTTPStatus.BAD_REQUEST, "validation_error")
            return
        session = STORE.add_session(str(payload["child_id"]), payload)
        self._json_response({"session": session, "data": STORE.load()})

    def _ask_history(self) -> None:
        payload = self._read_json()
        child = STORE.get_child(str(payload.get("child_id", "")))
        question = str(payload.get("question", "")).strip()
        if not question:
            self._json_error("Question is empty.", HTTPStatus.BAD_REQUEST, "validation_error")
            return
        messages = [
            {
                "role": "system",
                "content": "Отвечай только на основании истории занятий. Если данных нет, так и скажи. Не выдумывай факты.",
            },
            {"role": "user", "content": json.dumps({"question": question, "child": child}, ensure_ascii=False)},
        ]
        try:
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
        except OllamaError as exc:
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
        self.wfile.write(path.read_bytes())

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

    def _json_error(self, message: str, status: HTTPStatus, code: str = "error") -> None:
        self._json_response({"error": {"code": code, "message": message}}, status)

    def _ollama_url(self) -> str:
        return os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

    def _ollama_model(self) -> str:
        return os.environ.get("OLLAMA_MODEL", "llama3.1")

    def _ollama_client(self) -> OllamaClient:
        return OllamaClient(base_url=self._ollama_url(), model=self._ollama_model())

    def log_message(self, format: str, *args: object) -> None:
        print(f"[server] {self.address_string()} - {format % args}")


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORE.load()
    httpd = ThreadingHTTPServer((host, port), AppHandler)
    print(f"After-Session OS running at http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
