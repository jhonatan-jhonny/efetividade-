from datetime import date

from database.models import Party, PartyAffiliation, Politician, Source
from repositories.politician_repository import PoliticianRepository


def test_historic_party_is_not_overwritten(db_session):
    source = Source(key="official", name="Fonte", organization="Órgão", url="https://example.gov.br")
    person = Politician(external_source="test", external_id="1", name="Pessoa")
    party_a = Party(abbreviation="A")
    party_b = Party(abbreviation="B")
    db_session.add_all([source, person, party_a, party_b])
    db_session.flush()
    db_session.add_all(
        [
            PartyAffiliation(politician_id=person.id, party_id=party_a.id, start_date=date(2018, 1, 1), end_date=date(2020, 12, 31), source_id=source.id),
            PartyAffiliation(politician_id=person.id, party_id=party_b.id, start_date=date(2021, 1, 1), source_id=source.id),
        ]
    )
    db_session.flush()
    repo = PoliticianRepository(db_session)
    assert repo.party_for_date(person.id, date(2019, 6, 1)).party.abbreviation == "A"
    assert repo.party_for_date(person.id, date(2022, 6, 1)).party.abbreviation == "B"
