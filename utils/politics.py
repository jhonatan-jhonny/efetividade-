from __future__ import annotations

import re
import unicodedata


POLITICAL_OFFICES = (
    "Presidente",
    "Vice-presidente",
    "Governador",
    "Vice-governador",
    "Prefeito",
    "Vice-prefeito",
    "Senador",
    "Deputado federal",
    "Deputado estadual",
    "Deputado distrital",
    "Vereador",
)


def canonical_office(value: str | None) -> str:
    """Normalize source-specific spelling without merging distinct offices."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    key = re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")
    aliases = {
        "PRESIDENTE": "Presidente",
        "VICE_PRESIDENTE": "Vice-presidente",
        "GOVERNADOR": "Governador",
        "VICE_GOVERNADOR": "Vice-governador",
        "PREFEITO": "Prefeito",
        "VICE_PREFEITO": "Vice-prefeito",
        "SENADOR": "Senador",
        "DEPUTADO_FEDERAL": "Deputado federal",
        "DEPUTADO_ESTADUAL": "Deputado estadual",
        "DEPUTADO_DISTRITAL": "Deputado distrital",
        "VEREADOR": "Vereador",
    }
    return aliases.get(key, str(value or "Cargo não informado").strip())


def ordered_offices(values) -> tuple[str, ...]:
    normalized = {canonical_office(value) for value in values}
    extras = sorted(normalized - set(POLITICAL_OFFICES))
    return (*POLITICAL_OFFICES, *extras)
