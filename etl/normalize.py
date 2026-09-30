from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^A-Za-z0-9]+", " ", value).strip().upper()
    return re.sub(r"\s+", " ", value)


def normalize_municipality_code(value) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(7) if digits else None


def municipality_key(codigo_ibge: str, name: str | None = None, uf: str | None = None) -> str:
    code = normalize_municipality_code(codigo_ibge)
    if not code:
        raise ValueError("codigo_ibge é obrigatório; joins por nome são proibidos")
    return code

