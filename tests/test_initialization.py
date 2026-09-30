from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from config.sources import SOURCE_DEFINITIONS
from database.models import Base, Municipality, Source
from repositories.municipality_repository import MunicipalityRepository
from repositories.source_repository import seed_sources


def test_source_seed_is_idempotent(db_session):
    first = seed_sources(db_session)
    db_session.commit()

    writes = []
    engine = db_session.get_bind()

    def record_writes(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            writes.append(statement)

    event.listen(engine, "before_cursor_execute", record_writes)
    second = seed_sources(db_session)
    event.remove(engine, "before_cursor_execute", record_writes)

    assert set(first) == set(second)
    assert db_session.scalar(select(func.count()).select_from(Source)) == len(first)
    assert writes == []


def test_source_seed_tolerates_concurrent_sqlite_startup(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{(tmp_path / 'startup.db').as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 5},
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    def seed_once():
        with Session() as session:
            result = seed_sources(session)
            session.commit()
            return set(result)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: seed_once(), range(4)))

    assert all(result == set(SOURCE_DEFINITIONS) for result in results)
    with Session() as session:
        assert session.scalar(select(func.count()).select_from(Source)) == len(SOURCE_DEFINITIONS)


def test_municipality_upsert_updates_without_duplicate(db_session):
    repository = MunicipalityRepository(db_session)
    base = {"codigo_ibge": "3122306", "name": "Divinópolis", "uf": "MG"}
    repository.upsert_many([base])
    repository.upsert_many([{**base, "state_name": "Minas Gerais"}])

    assert repository.count() == 1
    assert repository.get("3122306").state_name == "Minas Gerais"
