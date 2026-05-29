from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any


class OllamaError(RuntimeError):
    """Raised when Ollama is unavailable or returns unusable output."""


REQUIRED_GENERATION_FIELDS = ("what_we_did", "what_changed", "home_practice")


def _extract_json_object(response: dict[str, Any]) -> dict[str, Any]:
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

    return parsed


def parse_ollama_json(response: dict[str, Any]) -> dict[str, Any]:
    parsed = _extract_json_object(response)

    missing = [field for field in REQUIRED_GENERATION_FIELDS if field not in parsed]
    if missing:
        raise OllamaError(f"Ollama response missing fields: {', '.join(missing)}")

    return parsed


class OllamaClient:
    def __init__(
            self,
            base_url: str = "http://127.0.0.1:11434",
            model: str = "gemma3:4b",
            timeout_seconds: float = 120,
            think: bool = False,
            num_predict: int | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.think = think
        self.num_predict = num_predict

    def list_models(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/api/tags")
        models = payload.get("models", [])
        if not isinstance(models, list):
            raise OllamaError("Ollama /api/tags returned an unexpected shape.")
        return models

    def chat_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": 0.2}
        if self.num_predict is not None:
            options["num_predict"] = self.num_predict

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "think": self.think,
            "options": options,
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
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            finally:
                exc.close()
            message = payload.get("error") or f"Ollama returned HTTP {exc.code}: {exc.reason}"
            raise OllamaError(str(message)) from exc
        except TimeoutError as exc:
            raise OllamaError(
                f"Ollama request to {self.base_url} timed out after {self.timeout_seconds} seconds."
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self.base_url}. Is Ollama running and is the model pulled?") from exc
        except json.JSONDecodeError as exc:
            raise OllamaError("Ollama returned non-JSON output.") from exc
