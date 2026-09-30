from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Municipality(Base):
    __tablename__ = "municipalities"
    codigo_ibge: Mapped[str] = mapped_column(String(7), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    uf: Mapped[str] = mapped_column(String(2), index=True)
    state_name: Mapped[str | None] = mapped_column(String(80))
    region: Mapped[str | None] = mapped_column(String(40))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    area_km2: Mapped[float | None] = mapped_column(Float)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MunicipalityCodeMapping(Base):
    __tablename__ = "municipality_code_mappings"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_ibge: Mapped[str] = mapped_column(ForeignKey("municipalities.codigo_ibge"), index=True)
    system: Mapped[str] = mapped_column(String(30), index=True)
    external_code: Mapped[str] = mapped_column(String(30), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("system", "external_code", name="uq_mapping_system_code"),)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    organization: Mapped[str] = mapped_column(String(200))
    dataset_name: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    api_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    update_frequency: Mapped[str | None] = mapped_column(String(100))
    last_checked: Mapped[datetime | None] = mapped_column(DateTime)
    license: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(180))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    latest_reference_period: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="not_available")
    notes: Mapped[str | None] = mapped_column(Text)


class Indicator(Base):
    __tablename__ = "indicators"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_ibge: Mapped[str] = mapped_column(ForeignKey("municipalities.codigo_ibge"), index=True)
    indicator_code: Mapped[str] = mapped_column(String(100), index=True)
    indicator_name: Mapped[str] = mapped_column(String(220))
    category: Mapped[str] = mapped_column(String(60), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int | None] = mapped_column(Integer)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(80))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    reference_date: Mapped[date | None] = mapped_column(Date)
    reference_period: Mapped[str | None] = mapped_column(String(40))
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    methodology_version: Mapped[str | None] = mapped_column(String(100))
    quality_status: Mapped[str] = mapped_column(String(30), default="complete")
    original_reference: Mapped[str | None] = mapped_column(Text)
    source_record_id: Mapped[str | None] = mapped_column(String(200))
    is_comparable: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[Source] = relationship()
    __table_args__ = (
        UniqueConstraint("codigo_ibge", "indicator_code", "year", "month", name="uq_indicator_period"),
        Index("ix_indicator_lookup", "codigo_ibge", "category", "year"),
    )


class Politician(Base):
    __tablename__ = "politicians"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(100), index=True)
    external_source: Mapped[str | None] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(220), index=True)
    civil_name: Mapped[str | None] = mapped_column(String(220))
    photo_url: Mapped[str | None] = mapped_column(Text)
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (UniqueConstraint("external_source", "external_id", name="uq_politician_external"),)


class Party(Base):
    __tablename__ = "parties"
    id: Mapped[int] = mapped_column(primary_key=True)
    abbreviation: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str | None] = mapped_column(String(160))
    tse_number: Mapped[int | None] = mapped_column(Integer)


class PartyAffiliation(Base):
    __tablename__ = "party_affiliations"
    id: Mapped[int] = mapped_column(primary_key=True)
    politician_id: Mapped[int] = mapped_column(ForeignKey("politicians.id"), index=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    party: Mapped[Party] = relationship()


class Candidacy(Base):
    __tablename__ = "candidacies"
    id: Mapped[int] = mapped_column(primary_key=True)
    politician_id: Mapped[int] = mapped_column(ForeignKey("politicians.id"), index=True)
    election_year: Mapped[int] = mapped_column(Integer, index=True)
    election_type: Mapped[str | None] = mapped_column(String(100))
    office: Mapped[str] = mapped_column(String(100))
    codigo_ibge: Mapped[str | None] = mapped_column(String(7), index=True)
    uf: Mapped[str | None] = mapped_column(String(2), index=True)
    candidate_number: Mapped[str | None] = mapped_column(String(20))
    party: Mapped[str | None] = mapped_column(String(30))
    coalition: Mapped[str | None] = mapped_column(Text)
    application_status: Mapped[str | None] = mapped_column(String(120))
    totalization_status: Mapped[str | None] = mapped_column(String(120))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    source_record_id: Mapped[str | None] = mapped_column(String(120))


class ElectionResult(Base):
    __tablename__ = "election_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidacy_id: Mapped[int] = mapped_column(ForeignKey("candidacies.id"), index=True)
    round: Mapped[int | None] = mapped_column(Integer)
    votes: Mapped[int | None] = mapped_column(Integer)
    vote_percentage: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(120))
    is_final: Mapped[bool] = mapped_column(Boolean, default=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))


class Mandate(Base):
    __tablename__ = "mandates"
    id: Mapped[int] = mapped_column(primary_key=True)
    politician_id: Mapped[int] = mapped_column(ForeignKey("politicians.id"), index=True)
    office: Mapped[str] = mapped_column(String(100), index=True)
    jurisdiction_type: Mapped[str] = mapped_column(String(30))
    codigo_ibge: Mapped[str | None] = mapped_column(String(7), index=True)
    uf: Mapped[str | None] = mapped_column(String(2), index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    verification_status: Mapped[str] = mapped_column(String(40), default="partial")


class OfficeExercise(Base):
    __tablename__ = "office_exercises"
    id: Mapped[int] = mapped_column(primary_key=True)
    politician_id: Mapped[int] = mapped_column(ForeignKey("politicians.id"), index=True)
    mandate_id: Mapped[int | None] = mapped_column(ForeignKey("mandates.id"))
    office: Mapped[str] = mapped_column(String(100), index=True)
    jurisdiction_type: Mapped[str] = mapped_column(String(30))
    codigo_ibge: Mapped[str | None] = mapped_column(String(7), index=True)
    uf: Mapped[str | None] = mapped_column(String(2), index=True)
    country: Mapped[str | None] = mapped_column(String(2), default="BR")
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, index=True)
    exercise_type: Mapped[str] = mapped_column(String(50), default="regular")
    titularity: Mapped[str | None] = mapped_column(String(50))
    start_reason: Mapped[str | None] = mapped_column(Text)
    end_reason: Mapped[str | None] = mapped_column(Text)
    party_at_start: Mapped[str | None] = mapped_column(String(30))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    verification_status: Mapped[str] = mapped_column(String(40), default="partial")
    original_reference: Mapped[str | None] = mapped_column(Text)
    politician: Mapped[Politician] = relationship()
    source: Mapped[Source] = relationship()
    __table_args__ = (Index("ix_exercise_period", "office", "start_date", "end_date"),)


class PoliticalEvent(Base):
    __tablename__ = "political_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    politician_id: Mapped[int] = mapped_column(ForeignKey("politicians.id"), index=True)
    office: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(50))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))


class SyncLog(Base):
    __tablename__ = "sync_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset: Mapped[str] = mapped_column(String(80), index=True)
    endpoint: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    success: Mapped[bool | None] = mapped_column(Boolean)
    records_received: Mapped[int | None] = mapped_column(Integer)
    cache_status: Mapped[str | None] = mapped_column(String(20))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)


class DataQuality(Base):
    __tablename__ = "data_quality"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset: Mapped[str] = mapped_column(String(80), index=True)
    codigo_ibge: Mapped[str | None] = mapped_column(String(7), index=True)
    year: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    coverage: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

