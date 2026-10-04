"""Проверка ответа: дихотомически 0/1 для IRT-модели (§10.4). open_approach оценивается отдельно."""

from typing import Any


def score(kind: str, key: dict[str, Any], response: dict[str, Any] | None) -> float | None:
    if kind == "open_approach":
        return None
    if not response:
        return 0.0
    if kind in {"single_choice", "multi_choice", "code_output"}:
        chosen = sorted(response.get("choice_ids") or [])
        return 1.0 if chosen == key["choice_ids"] else 0.0
    if kind == "ordering":
        return 1.0 if list(response.get("order") or []) == key["order"] else 0.0
    if kind == "numeric":
        number = response.get("number")
        if number is None:
            return 0.0
        expected = float(key["number"])
        tolerance = max(float(key.get("tolerance", 0.0)), 1e-9)
        return 1.0 if abs(float(number) - expected) <= tolerance else 0.0
    raise ValueError(f"неизвестный вид задания {kind}")
