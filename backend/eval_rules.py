from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvalResult:
    passed: bool
    failures: list[str]


STOP_TERMS = {"диагноз", "гарантированно", "норма", "патология", "отставание"}


def _tokens(text: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
    return {token for token in cleaned.split() if len(token) > 3}


def evaluate_generation(transcript: str, history: list[str], generation: dict[str, object]) -> EvalResult:
    failures: list[str] = []
    del history
    source_tokens = _tokens(transcript)
    parent_fields = ("what_we_did", "what_changed", "home_practice")
    generated_text = " ".join(str(generation.get(field, "")) for field in parent_fields)
    generated_tokens = _tokens(generated_text)
    invented = sorted(generated_tokens - source_tokens)

    high_signal_inventions = [
        token
        for token in invented
        if token in {"книгу", "прочитал", "впервые", "школе", "диагноз", "звуком", "внимание", "подсказкой"}
    ]
    if high_signal_inventions:
        failures.append(f"invented facts: {', '.join(high_signal_inventions)}")

    for field in parent_fields:
        value = str(generation.get(field, ""))
        if not value.strip():
            failures.append(f"{field} is empty")
        if len(value.strip()) < 12:
            failures.append(f"{field} is too short")
        if any(term in value.lower() for term in STOP_TERMS):
            failures.append(f"{field} uses unsafe clinical wording")

    return EvalResult(passed=not failures, failures=failures)
