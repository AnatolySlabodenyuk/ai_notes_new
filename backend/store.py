from __future__ import annotations

import json
import tempfile
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StoreError(RuntimeError):
    """Raised when the local demo JSON store cannot be read or written."""


class UnknownChildError(StoreError):
    """Raised when a request references a child id that does not exist."""


SEED_DATA: dict[str, Any] = {
    "children": [
        {
            "id": "child-a",
            "display_name": "Ребёнок А",
            "age_label": "6 лет",
            "focus": "речь, внимание, домашняя практика",
            "goals": [
                "произносить звук Р в слогах и коротких словах",
                "удерживать внимание на задании 5-7 минут",
                "получать короткую понятную домашнюю практику",
            ],
            "sessions": [
                {
                    "id": "seed-1",
                    "created_at": "2026-05-20T10:00:00Z",
                    "status": "confirmed",
                    "transcript": "Работали над звуком Р в слогах. С подсказкой получалось лучше, без подсказки звук иногда заменялся.",
                    "internal_note": "Фокус: звук Р в слогах. С подсказкой артикуляция стабильнее, без подсказки сохраняются замены.",
                    "parent_message": "Сегодня тренировались произносить звук Р в слогах. Лучше получалось после подсказки. Дома можно повторить 5 коротких слов спокойно, без давления.",
                    "history_update": "Звук Р появляется в слогах с подсказкой, самостоятельное произношение пока нестабильно.",
                },
                {
                    "id": "seed-2",
                    "created_at": "2026-05-21T10:00:00Z",
                    "status": "confirmed",
                    "transcript": "Повторяли звук Р в словах рыба, рак, робот. Ребёнок быстрее включался в задание, устал ближе к концу.",
                    "internal_note": "Фокус: перенос звука Р в короткие слова. Включение быстрее, к концу занятия появилась усталость.",
                    "parent_message": "Сегодня пробовали звук Р в словах: рыба, рак, робот. В начале занятия ребёнок включался быстрее. Дома достаточно 3-5 минут короткой практики.",
                    "history_update": "Появился перенос звука Р в отдельные короткие слова, внимание лучше в начале занятия.",
                },
            ],
        }
    ]
}


class DemoStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return self.reset()
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise StoreError(f"Demo store JSON is corrupt: {self.path}") from exc
            except OSError as exc:
                raise StoreError(f"Cannot read demo store: {self.path}") from exc

    def save(self, data: dict[str, Any]) -> None:
        with self._lock:
            tmp_path: Path | None = None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=self.path.parent,
                    delete=False,
                    suffix=".tmp",
                ) as tmp:
                    tmp_path = Path(tmp.name)
                    json.dump(data, tmp, ensure_ascii=False, indent=2)
                tmp_path.replace(self.path)
            except OSError as exc:
                if tmp_path is not None:
                    tmp_path.unlink(missing_ok=True)
                raise StoreError(f"Cannot write demo store: {self.path}") from exc

    def reset(self) -> dict[str, Any]:
        with self._lock:
            data = deepcopy(SEED_DATA)
            self.save(data)
            return data

    def get_child(self, child_id: str) -> dict[str, Any]:
        with self._lock:
            data = self.load()
            for child in data.get("children", []):
                if child.get("id") == child_id:
                    return child
            raise UnknownChildError(f"Unknown child id: {child_id}")

    def add_session(self, child_id: str, session: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            data = self.load()
            for child in data.get("children", []):
                if child.get("id") == child_id:
                    saved = {
                        "id": f"session-{uuid.uuid4().hex[:10]}",
                        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "status": "confirmed",
                        "transcript": session["transcript"],
                        "internal_note": session["internal_note"],
                        "parent_message": session["parent_message"],
                        "history_update": session["history_update"],
                    }
                    child.setdefault("sessions", []).append(saved)
                    self.save(data)
                    return saved
            raise UnknownChildError(f"Unknown child id: {child_id}")
