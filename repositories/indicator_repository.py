from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from database.models import Indicator
from utils.logging import get_logger

logger = get_logger(__name__)


class IndicatorRepository:
    def __init__(self, session):
        self.session = session

    def upsert(self, data: dict) -> Indicator:
        stmt = select(Indicator).where(
            Indicator.codigo_ibge == data["codigo_ibge"],
            Indicator.indicator_code == data["indicator_code"],
            Indicator.year == data["year"],
            Indicator.month.is_(None) if data.get("month") is None else Indicator.month == data["month"],
        )
        obj = self.session.scalar(stmt)
        if obj is None:
            obj = Indicator(**data)
            self.session.add(obj)
        else:
            for key, value in data.items():
                setattr(obj, key, value)
        self.session.flush()
        return obj

    def get(self, codigo_ibge: str, code: str, year: int) -> Indicator | None:
        return self.session.scalar(
            select(Indicator)
            .options(joinedload(Indicator.source))
            .where(
                Indicator.codigo_ibge == codigo_ibge,
                Indicator.indicator_code == code,
                Indicator.year == year,
                Indicator.month.is_(None),
            )
        )

    def latest_at_or_before(self, codigo_ibge: str, code: str, year: int) -> Indicator | None:
        return self.session.scalar(
            select(Indicator)
            .options(joinedload(Indicator.source))
            .where(
                Indicator.codigo_ibge == codigo_ibge,
                Indicator.indicator_code == code,
                Indicator.year <= year,
            )
            .order_by(Indicator.year.desc(), Indicator.month.desc())
            .limit(1)
        )

    def series(self, codigo_ibge: str, code: str, start_year: int | None = None, end_year: int | None = None):
        stmt = select(Indicator).options(joinedload(Indicator.source)).where(
            Indicator.codigo_ibge == codigo_ibge,
            Indicator.indicator_code == code,
            Indicator.month.is_(None),
        )
        if start_year is not None:
            stmt = stmt.where(Indicator.year >= start_year)
        if end_year is not None:
            stmt = stmt.where(Indicator.year <= end_year)
        return list(self.session.scalars(stmt.order_by(Indicator.year)))

    def category(self, codigo_ibge: str, category: str, year: int):
        return list(
            self.session.scalars(
                select(Indicator)
                .options(joinedload(Indicator.source))
                .where(
                    Indicator.codigo_ibge == codigo_ibge,
                    Indicator.category == category,
                    Indicator.year == year,
                )
                .order_by(Indicator.indicator_name)
            )
        )

    def is_fresh(self, codigo_ibge: str, code: str, year: int, ttl_seconds: int) -> bool:
        obj = self.get(codigo_ibge, code, year)
        fresh = bool(obj and obj.collected_at >= datetime.utcnow() - timedelta(seconds=ttl_seconds))
        logger.info(
            "persistent_cache status=%s municipality=%s indicator=%s year=%s",
            "hit" if fresh else "miss",
            codigo_ibge,
            code,
            year,
        )
        return fresh

