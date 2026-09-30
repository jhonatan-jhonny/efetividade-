from __future__ import annotations

import math
from dataclasses import dataclass


def is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def format_number(value, decimals: int = 0) -> str:
    if is_missing(value):
        return "Não disponível"
    text = f"{float(value):,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def format_currency(value, decimals: int = 0) -> str:
    return "Não disponível" if is_missing(value) else f"R$ {format_number(value, decimals)}"


def format_rate(value, decimals: int = 1) -> str:
    return "Não disponível" if is_missing(value) else f"{format_number(value, decimals)} / 100 mil"


def per_100k(occurrences: float | int | None, population: float | int | None) -> float | None:
    if occurrences is None or population is None or population <= 0:
        return None
    return float(occurrences) / float(population) * 100_000


@dataclass(frozen=True)
class Change:
    absolute: float | None
    percent: float | None
    comparable: bool
    reason: str | None = None


def calculate_change(current, previous, *, comparable: bool = True) -> Change:
    if not comparable:
        return Change(None, None, False, "mudança metodológica")
    if is_missing(current) or is_missing(previous):
        return Change(None, None, False, "valor ausente")
    absolute = float(current) - float(previous)
    if float(previous) == 0:
        return Change(absolute, None, False, "base anterior igual a zero")
    return Change(absolute, absolute / abs(float(previous)) * 100, True)


def safe_float(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(" ", "")
    if text in {"", "-", "..", "...", "X", "null", "None"}:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None

