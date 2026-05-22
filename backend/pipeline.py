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


def child_history_summary(child: dict[str, Any]) -> str:
    sessions = child.get("sessions", [])[-5:]
    if not sessions:
        return "Истории пока нет."
    return "\n".join(
        f"- {session.get('created_at', '')}: {session.get('history_update') or session.get('internal_note', '')}"
        for session in sessions
    )


def build_generation_payload(transcript: str, child: dict[str, Any]) -> dict[str, Any]:
    cleaned = validate_transcript(transcript)
    goals = ", ".join(child.get("goals", [])) or "цели не указаны"
    history = child_history_summary(child)
    system = (
        "Ты помощник коррекционного специалиста. Пиши только на русском. "
        "Не выдумывай факты, оценки, диагнозы, баллы или события. "
        "Если факта нет во входных данных, не добавляй его. "
        "Верни строго JSON с полями internal_note, parent_message, history_update, qa_suggestions. "
        "parent_message должен быть спокойным, конкретным, понятным родителю и без тяжёлой терминологии."
    )
    user = (
        f"Обезличенный ребёнок: {child.get('display_name', 'ребёнок')}.\n"
        f"Фокус и цели: {goals}.\n\n"
        f"История последних занятий:\n{history}\n\n"
        f"Сырой транскрипт заметки специалиста после занятия:\n{cleaned}\n\n"
        "Сформируй:\n"
        "1. internal_note: структурированную внутреннюю заметку специалиста.\n"
        "2. parent_message: короткое сообщение родителю: что делали, что получилось, что делать дома.\n"
        "3. history_update: одно короткое обновление для истории прогресса.\n"
        "4. qa_suggestions: 2-3 вопроса/ответа по истории или домашней практике."
    )
    return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}


def generate_drafts(transcript: str, child: dict[str, Any], client: OllamaClient) -> dict[str, Any]:
    payload = build_generation_payload(transcript, child)
    return client.chat_json(payload["messages"])
