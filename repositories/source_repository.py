from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config.sources import SOURCE_DEFINITIONS
from database.models import Source


def seed_sources(session) -> dict[str, Source]:
    """Cria/atualiza o catálogo de fontes de forma atômica e idempotente.

    O Streamlit pode executar o script simultaneamente em mais de uma sessão.
    Um SELECT seguido de INSERT permite que ambas tentem criar a mesma chave;
    o UPSERT elimina essa janela tanto no SQLite quanto no PostgreSQL.
    """
    result = {}
    dialect = session.get_bind().dialect.name
    for key, values in SOURCE_DEFINITIONS.items():
        payload = {"key": key, **values}
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert

            statement = insert(Source).values(**payload)
            statement = statement.on_conflict_do_update(
                index_elements=[Source.key],
                set_={field: getattr(statement.excluded, field) for field in values},
            )
            session.execute(statement)
        elif dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            statement = insert(Source).values(**payload)
            statement = statement.on_conflict_do_update(
                index_elements=[Source.key],
                set_={field: getattr(statement.excluded, field) for field in values},
            )
            session.execute(statement)
        else:
            source = session.scalar(select(Source).where(Source.key == key))
            if source is None:
                try:
                    with session.begin_nested():
                        session.add(Source(**payload))
                        session.flush()
                except IntegrityError:
                    # Outra transação criou a chave durante esta operação.
                    pass
        session.flush()
        source = session.scalar(select(Source).where(Source.key == key))
        if source is None:
            raise RuntimeError(f"Não foi possível inicializar a fonte {key!r}.")
        result[key] = source
    return result


def touch_source(session, key: str) -> Source:
    source = seed_sources(session)[key]
    source.last_checked = datetime.utcnow()
    return source

