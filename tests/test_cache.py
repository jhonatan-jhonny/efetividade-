from datetime import datetime, timedelta

from database.models import Indicator, Municipality, Source
from repositories.indicator_repository import IndicatorRepository


def test_persistent_cache_freshness(db_session):
    source = Source(key="ibge", name="IBGE", organization="IBGE", url="https://ibge.gov.br")
    city = Municipality(codigo_ibge="3122306", name="Divinópolis", uf="MG")
    db_session.add_all([source, city])
    db_session.flush()
    item = Indicator(
        codigo_ibge=city.codigo_ibge, indicator_code="population", indicator_name="População",
        category="demography", year=2022, value=231091, unit="Pessoas", source_id=source.id,
        collected_at=datetime.utcnow(),
    )
    db_session.add(item)
    db_session.flush()
    repo = IndicatorRepository(db_session)
    assert repo.is_fresh(city.codigo_ibge, "population", 2022, 60)
    item.collected_at = datetime.utcnow() - timedelta(days=2)
    db_session.flush()
    assert not repo.is_fresh(city.codigo_ibge, "population", 2022, 60)

