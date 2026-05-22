from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any


class OllamaError(RuntimeError):
    """Raised when Ollama is unavailable or returns unusable output."""


REQUIRED_GENERATION_FIELDS = ("internal_note", "parent_message", "history_update", "qa_suggestions")


def parse_ollama_json(response: dict[str, Any]) -> dict[str, Any]:
    content = ""
    if isinstance(response.get("message"), dict):
        content = str(response["message"].get("content", ""))
    elif response.get("response"):
        content = str(response.get("response"))

    if not content.strip():
        raise OllamaError("Ollama returned an empty response.")

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise OllamaError("Ollama response did not contain JSON.")

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise OllamaError("Ollama response JSON is invalid.") from exc

    missing = [field for field in REQUIRED_GENERATION_FIELDS if field not in parsed]
    if missing:
        raise OllamaError(f"Ollama response missing fields: {', '.join(missing)}")

    if not isinstance(parsed["qa_suggestions"], list):
        raise OllamaError("Ollama response field qa_suggestions must be a list.")

    return parsed


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "llama3.1", timeout_seconds: float = 60):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def list_models(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/api/tags")
        models = payload.get("models", [])
        if not isinstance(models, list):
            raise OllamaError("Ollama /api/tags returned an unexpected shape.")
        return models

    def chat_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }
        return parse_ollama_json(self._request("POST", "/api/chat", payload))

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OllamaError(f"Cannot reach Ollama at {self.base_url}. Is Ollama running and is the model pulled?") from exc
        except json.JSONDecodeError as exc:
            raise OllamaError("Ollama returned non-JSON output.") from exc
