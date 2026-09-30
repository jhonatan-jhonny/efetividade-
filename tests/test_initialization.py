from sqlalchemy import func, select

from database.models import Municipality, Source
from repositories.municipality_repository import MunicipalityRepository
from repositories.source_repository import seed_sources


def test_source_seed_is_idempotent(db_session):
    first = seed_sources(db_session)
    second = seed_sources(db_session)

    assert set(first) == set(second)
    assert db_session.scalar(select(func.count()).select_from(Source)) == len(first)


def test_municipality_upsert_updates_without_duplicate(db_session):
    repository = MunicipalityRepository(db_session)
    base = {"codigo_ibge": "3122306", "name": "Divinópolis", "uf": "MG"}
    repository.upsert_many([base])
    repository.upsert_many([{**base, "state_name": "Minas Gerais"}])

    assert repository.count() == 1
    assert repository.get("3122306").state_name == "Minas Gerais"
