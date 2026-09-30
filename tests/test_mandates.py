from datetime import date

from database.models import Municipality, OfficeExercise, Politician, Source
from repositories.mandate_repository import MandateRepository


def seed(db_session):
    source = Source(key="official", name="Fonte", organization="Órgão", url="https://example.gov.br")
    city = Municipality(codigo_ibge="3122306", name="Divinópolis", uf="MG")
    first = Politician(external_source="test", external_id="1", name="Prefeito A")
    second = Politician(external_source="test", external_id="2", name="Vice B")
    db_session.add_all([source, city, first, second])
    db_session.flush()
    db_session.add_all(
        [
            OfficeExercise(
                politician_id=first.id, office="Prefeito", jurisdiction_type="municipality",
                codigo_ibge=city.codigo_ibge, start_date=date(2021, 1, 1), end_date=date(2023, 5, 14),
                source_id=source.id, verification_status="verified",
            ),
            OfficeExercise(
                politician_id=second.id, office="Prefeito", jurisdiction_type="municipality",
                codigo_ibge=city.codigo_ibge, start_date=date(2023, 5, 15), end_date=date(2023, 8, 1),
                exercise_type="interim", source_id=source.id, verification_status="verified",
            ),
            OfficeExercise(
                politician_id=first.id, office="Prefeito", jurisdiction_type="municipality",
                codigo_ibge=city.codigo_ibge, start_date=date(2023, 8, 2), end_date=date(2024, 12, 31),
                source_id=source.id, verification_status="verified",
            ),
        ]
    )
    db_session.flush()
    return city


def test_all_officeholders_during_year_are_returned(db_session):
    city = seed(db_session)
    results = MandateRepository(db_session).for_year(2023, codigo_ibge=city.codigo_ibge, uf="MG", offices=["Prefeito"])
    assert len(results) == 3
    assert {item.politician.name for item in results} == {"Prefeito A", "Vice B"}

