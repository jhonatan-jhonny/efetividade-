from __future__ import annotations

import unicodedata
from datetime import date, timedelta

from config.sources import CAMARA_API
from repositories.mandate_repository import MandateRepository
from repositories.politician_repository import PoliticianRepository
from repositories.source_repository import touch_source
from utils.dates import parse_date
from utils.requests import http


def _plain(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch)).upper()


def reconstruct_exercise_intervals(events: list[dict], year: int) -> list[dict]:
    """Reconstrói intervalos a partir de eventos oficiais, sem inferir mandato eleitoral."""
    ordered = sorted(
        (e for e in events if parse_date(e.get("dataHora"))),
        key=lambda e: e.get("dataHora") or "",
    )
    intervals, active = [], None
    for event in ordered:
        event_date = parse_date(event.get("dataHora"))
        status = _plain(event.get("situacao"))
        description = _plain(event.get("descricaoStatus"))
        is_exercise = status == "EXERCICIO"
        is_party_change = "ALTERACAO DE PARTIDO" in description
        if is_exercise and active is None:
            active = {
                "start_date": event_date,
                "end_date": None,
                "party": event.get("siglaPartido"),
                "titularity": event.get("condicaoEleitoral"),
                "start_reason": event.get("descricaoStatus"),
            }
        elif active is not None and not is_exercise and not is_party_change:
            active["end_date"] = event_date
            active["end_reason"] = event.get("descricaoStatus") or event.get("situacao")
            intervals.append(active)
            active = None
    if active is not None:
        intervals.append(active)
    year_start, year_end = date(year, 1, 1), date(year, 12, 31)
    return [i for i in intervals if i["start_date"] <= year_end and (i["end_date"] is None or i["end_date"] >= year_start)]


class CamaraService:
    def __init__(self, session):
        self.session = session
        self.source = touch_source(session, "camara")
        self.people = PoliticianRepository(session)
        self.exercises = MandateRepository(session)

    def _list(self, uf: str, year: int) -> list[dict]:
        payload = http.get(
            f"{CAMARA_API}/deputados",
            params={
                "siglaUf": uf,
                "dataInicio": f"{year}-01-01",
                "dataFim": f"{year}-12-31",
                "itens": 100,
                "ordem": "ASC",
                "ordenarPor": "nome",
            },
            timeout=60,
        ).json()
        unique = {}
        for item in payload.get("dados", []):
            unique[str(item["id"])] = item
        return list(unique.values())

    def sync_deputies(self, uf: str, year: int) -> int:
        count = 0
        for item in self._list(uf, year):
            politician = self.people.upsert(
                source="camara",
                external_id=str(item["id"]),
                name=item.get("nome") or "Nome não informado",
                photo_url=item.get("urlFoto"),
            )
            history_url = f"{CAMARA_API}/deputados/{item['id']}/historico"
            events = http.get(history_url, timeout=60).json().get("dados", [])
            intervals = reconstruct_exercise_intervals(events, year)
            for interval in intervals:
                self.exercises.upsert_exercise(
                    {
                        "politician_id": politician.id,
                        "office": "Deputado federal",
                        "jurisdiction_type": "state",
                        "uf": uf,
                        "start_date": interval["start_date"],
                        "end_date": interval.get("end_date"),
                        "exercise_type": "parliamentary_exercise",
                        "titularity": interval.get("titularity"),
                        "start_reason": interval.get("start_reason"),
                        "end_reason": interval.get("end_reason"),
                        "party_at_start": interval.get("party"),
                        "source_id": self.source.id,
                        "verification_status": "verified",
                        "original_reference": history_url,
                    }
                )
                count += 1
        return count

