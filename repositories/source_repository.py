from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config.sources import SOURCE_DEFINITIONS
from database.models import Source


def seed_sources(session) -> dict[str, Source]:
    """Create missing source rows without writing again on every app rerun."""
    keys = tuple(SOURCE_DEFINITIONS)
    existing = {
        source.key: source
        for source in session.scalars(select(Source).where(Source.key.in_(keys)))
    }
    missing = [
        {"key": key, **SOURCE_DEFINITIONS[key]}
        for key in keys
        if key not in existing
    ]

    if missing:
        dialect = session.get_bind().dialect.name
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert

            statement = insert(Source).values(missing)
            session.execute(statement.on_conflict_do_nothing(index_elements=[Source.key]))
        elif dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            statement = insert(Source).values(missing)
            session.execute(statement.on_conflict_do_nothing(index_elements=[Source.key]))
        else:
            for payload in missing:
                try:
                    with session.begin_nested():
                        session.add(Source(**payload))
                        session.flush()
                except IntegrityError:
                    # Another transaction inserted the same source first.
                    pass
        session.flush()
        existing = {
            source.key: source
            for source in session.scalars(select(Source).where(Source.key.in_(keys)))
        }

    absent = set(keys) - set(existing)
    if absent:
        raise RuntimeError(
            f"Não foi possível inicializar as fontes: {', '.join(sorted(absent))}."
        )
    return {key: existing[key] for key in keys}


def touch_source(session, key: str) -> Source:
    source = session.scalar(select(Source).where(Source.key == key))
    if source is None:
        source = seed_sources(session)[key]
    source.last_checked = datetime.utcnow()
    return source
