from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from config.sources import DATASET_TTLS, IBGE_AGGREGATES, IBGE_LOCALITIES
from database.models import DataQuality
from repositories.indicator_repository import IndicatorRepository
from repositories.municipality_repository import MunicipalityRepository
from repositories.source_repository import touch_source
from utils.formatting import safe_float
from utils.requests import ExternalServiceError, http


def _extract_series(payload: list, year: int) -> tuple[float | None, str | None, str | None]:
    if not payload:
        return None, None, None
    item = payload[0]
    for result in item.get("resultados", []):
        for series in result.get("series", []):
            raw = series.get("serie", {}).get(str(year))
            if raw is not None:
                return safe_float(raw), item.get("unidade"), item.get("variavel")
    return None, item.get("unidade"), item.get("variavel")


class IBGEService:
    def __init__(self, session):
        self.session = session
        self.source = touch_source(session, "ibge")
        self.indicators = IndicatorRepository(session)

    def sync_municipalities(self, force: bool = False) -> int:
        repo = MunicipalityRepository(self.session)
        if repo.count() >= 5500 and not force:
            return repo.count()
        payload = http.get(f"{IBGE_LOCALITIES}/municipios").json()
        records = []
        for row in payload:
            immediate = row.get("regiao-imediata") or {}
            intermediate = immediate.get("regiao-intermediaria") or {}
            state = intermediate.get("UF") or (row.get("microrregiao") or {}).get("mesorregiao", {}).get("UF", {})
            region = state.get("regiao") or {}
            records.append(
                {
                    "codigo_ibge": str(row["id"]),
                    "name": row["nome"],
                    "uf": state.get("sigla", ""),
                    "state_name": state.get("nome"),
                    "region": region.get("nome"),
                    "collected_at": datetime.utcnow(),
                }
            )
        return repo.upsert_many(records)

    def _sidra(self, table: int, variable: int, year: int, codigo_ibge: str):
        url = (
            f"{IBGE_AGGREGATES}/{table}/periodos/{year}/variaveis/{variable}"
            f"?localidades=N6[{codigo_ibge}]"
        )
        result = http.get(url).json()
        value, unit, name = _extract_series(result, year)
        return value, unit, name, url

    def _save_unavailable(self, codigo_ibge: str, dataset: str, year: int, note: str):
        existing = self.session.scalar(
            select(DataQuality).where(
                DataQuality.dataset == dataset,
                DataQuality.codigo_ibge == codigo_ibge,
                DataQuality.year == year,
            )
        )
        if existing is None:
            self.session.add(
                DataQuality(dataset=dataset, codigo_ibge=codigo_ibge, year=year, status="not_available", notes=note)
            )
        else:
            existing.status, existing.notes, existing.checked_at = "not_available", note, datetime.utcnow()

    def sync_population(self, codigo_ibge: str, year: int, force: bool = False):
        if not force and self.indicators.is_fresh(
            codigo_ibge, "population", year, DATASET_TTLS["population"]
        ):
            return self.indicators.get(codigo_ibge, "population", year)
        table, variable, methodology = (9514, 93, "Censo Demográfico 2022") if year == 2022 else (
            6579,
            9324,
            "Estimativas da População",
        )
        value, unit, name, url = self._sidra(table, variable, year, codigo_ibge)
        if value is None:
            self._save_unavailable(
                codigo_ibge,
                "population",
                year,
                f"O SIDRA não publicou valor municipal na tabela {table} para este ano.",
            )
            return None
        return self.indicators.upsert(
            {
                "codigo_ibge": codigo_ibge,
                "indicator_code": "population",
                "indicator_name": name or "População residente",
                "category": "demography",
                "year": year,
                "value": value,
                "unit": unit or "Pessoas",
                "source_id": self.source.id,
                "reference_date": date(year, 7, 1) if year != 2022 else date(2022, 8, 1),
                "reference_period": str(year),
                "methodology_version": methodology,
                "quality_status": "complete",
                "original_reference": url,
                "source_record_id": f"SIDRA:{table}:{variable}:{codigo_ibge}:{year}",
                "is_comparable": year != 2022,
            }
        )

    def sync_gdp(self, codigo_ibge: str, year: int, force: bool = False):
        if year < 2002:
            return None
        if not force and self.indicators.is_fresh(codigo_ibge, "gdp", year, DATASET_TTLS["gdp"]):
            return self.indicators.get(codigo_ibge, "gdp", year)
        definitions = {
            37: ("gdp", "PIB a preços correntes"),
            513: ("gdp_agriculture", "VAB da agropecuária"),
            517: ("gdp_industry", "VAB da indústria"),
            6575: ("gdp_services", "VAB dos serviços"),
            525: ("gdp_public_admin", "VAB da administração pública"),
        }
        saved = {}
        for variable, (code, fallback_name) in definitions.items():
            try:
                value, unit, name, url = self._sidra(5938, variable, year, codigo_ibge)
            except ExternalServiceError:
                if variable == 37:
                    raise
                continue
            if value is None:
                continue
            # A tabela 5938 publica milhares de reais; persistimos em reais para formatação consistente.
            if unit and "Mil Reais" in unit:
                value *= 1000
                unit = "R$"
            saved[code] = self.indicators.upsert(
                {
                    "codigo_ibge": codigo_ibge,
                    "indicator_code": code,
                    "indicator_name": name or fallback_name,
                    "category": "economy",
                    "year": year,
                    "value": value,
                    "unit": unit or "R$",
                    "source_id": self.source.id,
                    "reference_period": str(year),
                    "methodology_version": "PIB dos Municípios — referência 2010",
                    "quality_status": "complete",
                    "original_reference": url,
                    "source_record_id": f"SIDRA:5938:{variable}:{codigo_ibge}:{year}",
                    "is_comparable": True,
                }
            )
        if "gdp" not in saved:
            self._save_unavailable(codigo_ibge, "gdp", year, "Ano ainda não disponível no PIB dos Municípios/SIDRA.")
            return None
        population = self.indicators.get(codigo_ibge, "population", year)
        if population and population.value and population.value > 0:
            self.indicators.upsert(
                {
                    "codigo_ibge": codigo_ibge,
                    "indicator_code": "gdp_per_capita_calculated",
                    "indicator_name": "PIB por habitante (cálculo da plataforma)",
                    "category": "economy",
                    "year": year,
                    "value": saved["gdp"].value / population.value,
                    "unit": "R$ por habitante",
                    "source_id": self.source.id,
                    "reference_period": str(year),
                    "methodology_version": "PIB municipal ÷ população de referência do mesmo ano",
                    "quality_status": "estimated",
                    "original_reference": saved["gdp"].original_reference,
                    "source_record_id": f"DERIVED:gdp/population:{codigo_ibge}:{year}",
                    "is_comparable": population.is_comparable,
                }
            )
        return saved["gdp"]

    def sync_core(self, codigo_ibge: str, year: int, force: bool = False) -> dict:
        result = {"population": None, "gdp": None, "errors": []}
        for key, action in (
            ("population", lambda: self.sync_population(codigo_ibge, year, force)),
            ("gdp", lambda: self.sync_gdp(codigo_ibge, year, force)),
        ):
            try:
                result[key] = action()
            except ExternalServiceError as exc:
                result["errors"].append(str(exc))
        self.session.flush()
        return result

