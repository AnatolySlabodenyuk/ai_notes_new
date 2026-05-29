from __future__ import annotations

from typing import Any

from .ollama_client import OllamaClient


def validate_transcript(transcript: str) -> str:
    cleaned = " ".join(transcript.split())
    if not cleaned:
        raise ValueError("Transcript is empty.")
    if len(cleaned) < 20:
        raise ValueError("Transcript is too short to generate a reliable note.")
    return cleaned


def build_generation_payload(transcript: str, child: dict[str, Any]) -> dict[str, Any]:
    cleaned = validate_transcript(transcript)
    system = (
        "Ты справочный помощник для подготовки родительской карточки ребенка. Пиши только на русском. "
        "Не выдумывай факты, оценки, диагнозы, баллы или события. "
        "Факты для трёх родительских блоков бери только из текущего транскрипта. "
        "Не превращай цели ребёнка или историю прошлых занятий в события сегодняшнего занятия. "
        "Если факта нет в текущем транскрипте, не добавляй его. "
        "Верни строго JSON с полями what_we_did, what_changed, home_practice. "
        "Все три блока должны быть спокойными, конкретными, понятными родителю и без тяжёлой терминологии. "
        "Это черновик: специалист центра обязательно проверяет и утверждает текст перед публикацией."
    )
    user = (
        f"Обезличенный ребёнок: {child.get('display_name', 'ребёнок')}.\n"
        "Цели ребёнка и история прошлых занятий намеренно не передаются в эту генерацию, "
        "чтобы не смешивать их с фактами текущего занятия.\n\n"
        f"Сырой транскрипт заметки специалиста после занятия:\n{cleaned}\n\n"
        "Если в транскрипте не сказано, что получилось или что делать дома, "
        "так и напиши: специалист не указал это в голосовой заметке, нужно уточнить перед публикацией.\n\n"
        "Сформируй:\n"
        "1. what_we_did: что делали на занятии, простыми словами.\n"
        "2. what_changed: только то, что в транскрипте сказано как результат, изменение или наблюдение.\n"
        "3. home_practice: только домашнюю практику, прямо указанную в транскрипте."
    )
    return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}


def generate_drafts(transcript: str, child: dict[str, Any], client: OllamaClient) -> dict[str, Any]:
    payload = build_generation_payload(transcript, child)
    return client.chat_json(payload["messages"])
