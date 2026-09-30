from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from database.models import Party, PartyAffiliation, Politician


class PoliticianRepository:
    def __init__(self, session):
        self.session = session

    def upsert(self, *, source: str, external_id: str, name: str, **fields) -> Politician:
        obj = self.session.scalar(
            select(Politician).where(
                Politician.external_source == source,
                Politician.external_id == str(external_id),
            )
        )
        if obj is None:
            obj = Politician(external_source=source, external_id=str(external_id), name=name, **fields)
            self.session.add(obj)
        else:
            obj.name = name or obj.name
            for key, value in fields.items():
                if value is not None:
                    setattr(obj, key, value)
        self.session.flush()
        return obj

    def search(self, term: str, limit: int = 30):
        return list(
            self.session.scalars(
                select(Politician)
                .where(or_(Politician.name.ilike(f"%{term}%"), Politician.civil_name.ilike(f"%{term}%")))
                .order_by(Politician.name)
                .limit(limit)
            )
        )

    def party_for_date(self, politician_id: int, on_date):
        stmt = (
            select(PartyAffiliation)
            .options(joinedload(PartyAffiliation.party))
            .where(
                PartyAffiliation.politician_id == politician_id,
                PartyAffiliation.start_date <= on_date,
                or_(PartyAffiliation.end_date.is_(None), PartyAffiliation.end_date >= on_date),
            )
            .order_by(PartyAffiliation.start_date.desc())
        )
        return self.session.scalar(stmt)

