from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import joinedload

from database.models import OfficeExercise


class MandateRepository:
    def __init__(self, session):
        self.session = session

    def upsert_exercise(self, data: dict) -> OfficeExercise:
        stmt = select(OfficeExercise).where(
            OfficeExercise.politician_id == data["politician_id"],
            OfficeExercise.office == data["office"],
            OfficeExercise.start_date == data["start_date"],
            OfficeExercise.codigo_ibge.is_(None)
            if data.get("codigo_ibge") is None
            else OfficeExercise.codigo_ibge == data["codigo_ibge"],
            OfficeExercise.uf.is_(None) if data.get("uf") is None else OfficeExercise.uf == data["uf"],
        )
        obj = self.session.scalar(stmt)
        if obj is None:
            obj = OfficeExercise(**data)
            self.session.add(obj)
        else:
            for key, value in data.items():
                setattr(obj, key, value)
        self.session.flush()
        return obj

    def for_year(
        self,
        year: int,
        *,
        codigo_ibge: str | None = None,
        uf: str | None = None,
        offices: list[str] | None = None,
    ) -> list[OfficeExercise]:
        start, end = date(year, 1, 1), date(year, 12, 31)
        stmt = (
            select(OfficeExercise)
            .options(joinedload(OfficeExercise.politician), joinedload(OfficeExercise.source))
            .where(
                OfficeExercise.start_date <= end,
                or_(OfficeExercise.end_date.is_(None), OfficeExercise.end_date >= start),
            )
        )
        locality = []
        if codigo_ibge:
            locality.append(OfficeExercise.codigo_ibge == codigo_ibge)
        if uf:
            locality.append(and_(OfficeExercise.codigo_ibge.is_(None), OfficeExercise.uf == uf))
        locality.append(and_(OfficeExercise.codigo_ibge.is_(None), OfficeExercise.uf.is_(None)))
        stmt = stmt.where(or_(*locality))
        if offices:
            stmt = stmt.where(OfficeExercise.office.in_(offices))
        return list(self.session.scalars(stmt.order_by(OfficeExercise.office, OfficeExercise.start_date)))

    def timeline(self, codigo_ibge: str, uf: str, start_year: int, end_year: int):
        start, end = date(start_year, 1, 1), date(end_year, 12, 31)
        stmt = (
            select(OfficeExercise)
            .options(joinedload(OfficeExercise.politician), joinedload(OfficeExercise.source))
            .where(
                OfficeExercise.start_date <= end,
                or_(OfficeExercise.end_date.is_(None), OfficeExercise.end_date >= start),
                or_(
                    OfficeExercise.codigo_ibge == codigo_ibge,
                    and_(OfficeExercise.codigo_ibge.is_(None), OfficeExercise.uf == uf),
                    and_(OfficeExercise.codigo_ibge.is_(None), OfficeExercise.uf.is_(None)),
                ),
            )
        )
        return list(self.session.scalars(stmt.order_by(OfficeExercise.start_date)))

