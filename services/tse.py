from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from config.settings import DOWNLOAD_DIR
from config.sources import TSE_CKAN_API
from database.models import Candidacy, ElectionResult, MunicipalityCodeMapping
from repositories.politician_repository import PoliticianRepository
from repositories.source_repository import touch_source
from utils.dates import parse_date
from utils.requests import ExternalServiceError, http


def _resource(package: dict, name_contains: str) -> str:
    wanted = name_contains.casefold()
    for item in package.get("resources", []):
        if wanted in (item.get("name") or "").casefold():
            return item["url"]
    raise ExternalServiceError(f"Recurso '{name_contains}' não localizado no catálogo oficial do TSE.")


class TSEService:
    def __init__(self, session):
        self.session = session
        self.source = touch_source(session, "tse")
        self.people = PoliticianRepository(session)

    def _package(self, package_id: str) -> dict:
        payload = http.get(f"{TSE_CKAN_API}/package_show", params={"id": package_id}).json()
        if not payload.get("success"):
            raise ExternalServiceError(f"Conjunto do TSE indisponível: {package_id}")
        return payload["result"]

    def _download(self, url: str) -> Path:
        destination = DOWNLOAD_DIR / Path(url).name
        if not destination.exists() or destination.stat().st_size == 0:
            http.stream_to_file(url, destination)
        return destination

    def sync_municipality_mapping(self) -> int:
        package = self._package("codigos-oficiais-de-uf-e-municipios-segundo-o-tse-e-o-ibge")
        url = _resource(package, "Códigos oficiais")
        archive = self._download(url)
        count = 0
        with zipfile.ZipFile(archive) as zf:
            csv_name = next(name for name in zf.namelist() if name.lower().endswith(".csv"))
            with zf.open(csv_name) as stream:
                frame = pd.read_csv(stream, sep=";", encoding="latin1", dtype=str)
        for row in frame.to_dict("records"):
            ibge = str(row.get("CD_MUNICIPIO_IBGE") or "").replace(".0", "").zfill(7)
            tse = str(row.get("CD_MUNICIPIO_TSE") or "").replace(".0", "").zfill(5)
            if not ibge.strip("0") or not tse.strip("0"):
                continue
            existing = self.session.scalar(
                select(MunicipalityCodeMapping).where(
                    MunicipalityCodeMapping.system == "TSE",
                    MunicipalityCodeMapping.external_code == tse,
                )
            )
            if existing is None:
                self.session.add(
                    MunicipalityCodeMapping(
                        codigo_ibge=ibge, system="TSE", external_code=tse, source_id=self.source.id
                    )
                )
            else:
                existing.codigo_ibge = ibge
                existing.collected_at = datetime.utcnow()
            count += 1
        self.session.flush()
        return count

    def _tse_code(self, codigo_ibge: str) -> str:
        mapping = self.session.scalar(
            select(MunicipalityCodeMapping).where(
                MunicipalityCodeMapping.system == "TSE",
                MunicipalityCodeMapping.codigo_ibge == codigo_ibge,
            )
        )
        if mapping is None:
            self.sync_municipality_mapping()
            mapping = self.session.scalar(
                select(MunicipalityCodeMapping).where(
                    MunicipalityCodeMapping.system == "TSE",
                    MunicipalityCodeMapping.codigo_ibge == codigo_ibge,
                )
            )
        if mapping is None:
            raise ExternalServiceError("O mapeamento oficial IBGE–TSE não contém este município.")
        return mapping.external_code

    def sync_election(self, codigo_ibge: str, uf: str, year: int) -> int:
        tse_code = self._tse_code(codigo_ibge)
        search = http.get(
            f"{TSE_CKAN_API}/package_search",
            params={"q": f' title:"Candidatos - {year}" ', "rows": 50},
        ).json()
        packages = search.get("result", {}).get("results", [])
        package = next((p for p in packages if str(year) in p.get("title", "") and "Candidatos" in p.get("title", "")), None)
        if package is None:
            raise ExternalServiceError(f"Conjunto de candidatos {year} não encontrado no catálogo TSE.")
        candidate_url = _resource(package, "Candidatos")
        candidate_zip = self._download(candidate_url)
        candidate_count = 0
        with zipfile.ZipFile(candidate_zip) as zf:
            member = next(
                (n for n in zf.namelist() if n.upper().endswith(f"_{uf}.CSV")),
                next(n for n in zf.namelist() if n.lower().endswith(".csv")),
            )
            with zf.open(member) as stream:
                for chunk in pd.read_csv(stream, sep=";", encoding="latin1", dtype=str, chunksize=50_000):
                    if "SG_UE" not in chunk:
                        continue
                    selected = chunk[chunk["SG_UE"].fillna("").str.zfill(5) == tse_code]
                    for row in selected.to_dict("records"):
                        external_id = row.get("SQ_CANDIDATO")
                        if not external_id:
                            continue
                        politician = self.people.upsert(
                            source="tse",
                            external_id=external_id,
                            name=row.get("NM_URNA_CANDIDATO") or row.get("NM_CANDIDATO") or "Nome não informado",
                            civil_name=row.get("NM_CANDIDATO"),
                            birth_date=parse_date(row.get("DT_NASCIMENTO")),
                            gender=row.get("DS_GENERO"),
                        )
                        office = row.get("DS_CARGO") or "Cargo não informado"
                        existing = self.session.scalar(
                            select(Candidacy).where(
                                Candidacy.politician_id == politician.id,
                                Candidacy.election_year == year,
                                Candidacy.office == office,
                                Candidacy.codigo_ibge == codigo_ibge,
                            )
                        )
                        data = {
                            "election_type": row.get("NM_TIPO_ELEICAO"),
                            "candidate_number": row.get("NR_CANDIDATO"),
                            "party": row.get("SG_PARTIDO"),
                            "coalition": row.get("NM_COLIGACAO"),
                            "application_status": row.get("DS_SITUACAO_CANDIDATURA"),
                            "totalization_status": row.get("DS_SIT_TOT_TURNO"),
                            "source_id": self.source.id,
                            "source_record_id": external_id,
                        }
                        if existing is None:
                            self.session.add(
                                Candidacy(
                                    politician_id=politician.id,
                                    election_year=year,
                                    office=office,
                                    codigo_ibge=codigo_ibge,
                                    uf=uf,
                                    **data,
                                )
                            )
                        else:
                            for key, value in data.items():
                                setattr(existing, key, value)
                        candidate_count += 1
        self.session.flush()
        self._sync_votes(codigo_ibge, tse_code, uf, year)
        return candidate_count

    def _sync_votes(self, codigo_ibge: str, tse_code: str, uf: str, year: int) -> None:
        try:
            package = self._package(f"resultados-{year}")
            url = _resource(package, "Votação nominal por município e zona")
        except ExternalServiceError:
            return
        archive = self._download(url)
        totals: dict[tuple[str, int], int] = {}
        with zipfile.ZipFile(archive) as zf:
            member = next(
                (n for n in zf.namelist() if n.upper().endswith(f"_{uf}.CSV")),
                next(n for n in zf.namelist() if n.lower().endswith(".csv")),
            )
            with zf.open(member) as stream:
                for chunk in pd.read_csv(stream, sep=";", encoding="latin1", dtype=str, chunksize=100_000):
                    code_col = "CD_MUNICIPIO" if "CD_MUNICIPIO" in chunk else "SG_UE"
                    selected = chunk[chunk[code_col].fillna("").str.zfill(5) == tse_code]
                    for row in selected.to_dict("records"):
                        candidate = row.get("SQ_CANDIDATO")
                        try:
                            turn = int(row.get("NR_TURNO") or 1)
                            votes = int(float(row.get("QT_VOTOS_NOMINAIS") or 0))
                        except ValueError:
                            continue
                        if candidate:
                            totals[(candidate, turn)] = totals.get((candidate, turn), 0) + votes
        candidacies = list(
            self.session.scalars(
                select(Candidacy).where(
                    Candidacy.codigo_ibge == codigo_ibge,
                    Candidacy.election_year == year,
                )
            )
        )
        for candidacy in candidacies:
            for (external_id, turn), votes in totals.items():
                if candidacy.source_record_id != external_id:
                    continue
                result = self.session.scalar(
                    select(ElectionResult).where(
                        ElectionResult.candidacy_id == candidacy.id,
                        ElectionResult.round == turn,
                    )
                )
                if result is None:
                    self.session.add(
                        ElectionResult(
                            candidacy_id=candidacy.id,
                            round=turn,
                            votes=votes,
                            status=candidacy.totalization_status,
                            is_final=True,
                            source_id=self.source.id,
                        )
                    )
                else:
                    result.votes = votes

