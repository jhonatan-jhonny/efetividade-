from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from config.sources import SOURCE_DEFINITIONS
from database.models import Source


def seed_sources(session) -> dict[str, Source]:
    result = {}
    for key, values in SOURCE_DEFINITIONS.items():
        source = session.scalar(select(Source).where(Source.key == key))
        if source is None:
            source = Source(key=key, **values)
            session.add(source)
            session.flush()
        result[key] = source
    return result


def touch_source(session, key: str) -> Source:
    source = seed_sources(session)[key]
    source.last_checked = datetime.utcnow()
    return source

