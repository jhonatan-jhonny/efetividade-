from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import datetime

from openpyxl import load_workbook
from sqlalchemy import select

from config.settings import DOWNLOAD_DIR
from config.sources import SINESP_YEAR_XLSX
from database.models import DataQuality
from repositories.indicator_repository import IndicatorRepository
from repositories.source_repository import touch_source
from utils.requests import ExternalServiceError, http


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c)).upper()
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


def _find_column(columns, *terms):
    normalized = {c: _norm(c) for c in columns}
    for term in terms:
        wanted = _norm(term)
        for original, clean in normalized.items():
            if wanted == clean or wanted in clean:
                return original
    return None


class SinespService:
    def __init__(self, session):
        self.session = session
        self.source = touch_source(session, "sinesp")
        self.indicators = IndicatorRepository(session)

    def sync_municipality(self, codigo_ibge: str, year: int) -> int:
        if year < 2015 or year > datetime.now().year:
            raise ExternalServiceError("A série municipal Sinesp VDE publicada cobre anos a partir de 2015.")
        source_url = SINESP_YEAR_XLSX.format(year=year)
        destination = DOWNLOAD_DIR / f"sinesp_vde_{year}.xlsx"
        if not destination.exists():
            http.stream_to_file(source_url, destination)
        workbook = load_workbook(destination, read_only=True, data_only=True)
        stored = 0
        missing_code = False
        for worksheet in workbook.worksheets:
            rows = worksheet.iter_rows(values_only=True)
            headers = next(rows, None)
            if not headers:
                continue
            headers = [str(value or "") for value in headers]
            code_col = _find_column(headers, "codigo ibge", "cod ibge")
            indicator_col = _find_column(headers, "indicador", "evento", "natureza", "tipo")
            value_col = _find_column(headers, "total", "quantidade", "ocorrencias")
            if code_col is None:
                missing_code = True
                continue
            if indicator_col is None or value_col is None:
                continue
            indexes = {header: idx for idx, header in enumerate(headers)}
            aggregates = defaultdict(float)
            found = defaultdict(bool)
            for row in rows:
                raw_code = re.sub(r"\D", "", str(row[indexes[code_col]] or "")).zfill(7)
                if raw_code != codigo_ibge:
                    continue
                indicator = row[indexes[indicator_col]]
                raw_value = row[indexes[value_col]]
                if indicator is None or raw_value is None:
                    continue
                try:
                    value = float(str(raw_value).replace(",", "."))
                except ValueError:
                    continue
                aggregates[str(indicator)] += value
                found[str(indicator)] = True
            for indicator, value in aggregates.items():
                code = f"crime_{_norm(indicator).lower()}"
                self.indicators.upsert(
                    {
                        "codigo_ibge": codigo_ibge,
                        "indicator_code": code,
                        "indicator_name": str(indicator),
                        "category": "security",
                        "year": year,
                        "value": value,
                        "unit": "Ocorrências/vítimas conforme indicador",
                        "source_id": self.source.id,
                        "reference_period": str(year),
                        "methodology_version": "Sinesp VDE — publicação municipal MJSP",
                        "quality_status": "partial",
                        "original_reference": source_url,
                        "source_record_id": f"SINESP:{codigo_ibge}:{year}:{code}",
                        "is_comparable": True,
                    }
                )
                stored += 1
        workbook.close()
        if stored == 0 and missing_code:
            reason = (
                "A planilha anual oficial publica UF e nome do município, mas não código IBGE. "
                "O join automático por nome foi recusado para preservar a integridade territorial."
            )
            quality = self.session.scalar(
                select(DataQuality).where(
                    DataQuality.dataset == "sinesp",
                    DataQuality.codigo_ibge == codigo_ibge,
                    DataQuality.year == year,
                )
            )
            if quality is None:
                self.session.add(
                    DataQuality(
                        dataset="sinesp",
                        codigo_ibge=codigo_ibge,
                        year=year,
                        status="not_available",
                        coverage="Fonte sem código territorial interoperável",
                        notes=reason,
                    )
                )
            else:
                quality.status, quality.coverage, quality.notes = (
                    "not_available",
                    "Fonte sem código territorial interoperável",
                    reason,
                )
            raise ExternalServiceError(reason)
        if stored == 0:
            raise ExternalServiceError("A publicação municipal do Sinesp não contém o município/ano ou mudou de layout.")
        return stored

