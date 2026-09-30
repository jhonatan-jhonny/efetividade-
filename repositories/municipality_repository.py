from __future__ import annotations

from sqlalchemy import func, select

from database.models import Municipality


class MunicipalityRepository:
    def __init__(self, session):
        self.session = session

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(Municipality)) or 0

    def upsert_many(self, records: list[dict]) -> int:
        count = 0
        for record in records:
            obj = self.session.get(Municipality, record["codigo_ibge"])
            if obj is None:
                self.session.add(Municipality(**record))
            else:
                for key, value in record.items():
                    setattr(obj, key, value)
            count += 1
        self.session.flush()
        return count

    def states(self) -> list[tuple[str, str]]:
        stmt = select(Municipality.uf, Municipality.state_name).distinct().order_by(Municipality.uf)
        return [(uf, name or uf) for uf, name in self.session.execute(stmt)]

    def by_state(self, uf: str) -> list[Municipality]:
        return list(self.session.scalars(select(Municipality).where(Municipality.uf == uf).order_by(Municipality.name)))

    def get(self, codigo_ibge: str) -> Municipality | None:
        return self.session.get(Municipality, codigo_ibge)

    def search(self, term: str, limit: int = 30) -> list[Municipality]:
        return list(
            self.session.scalars(
                select(Municipality)
                .where(func.lower(Municipality.name).contains(term.lower().strip()))
                .order_by(Municipality.name)
                .limit(limit)
            )
        )

