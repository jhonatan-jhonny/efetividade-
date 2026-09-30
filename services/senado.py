from __future__ import annotations

from datetime import date

from config.sources import SENADO_API
from repositories.mandate_repository import MandateRepository
from repositories.politician_repository import PoliticianRepository
from repositories.source_repository import touch_source
from utils.dates import legislature_for_year, parse_date
from utils.requests import http


def _text(node, path: str):
    found = node.find(path)
    return found.text.strip() if found is not None and found.text else None


class SenadoService:
    def __init__(self, session):
        self.session = session
        self.source = touch_source(session, "senado")
        self.people = PoliticianRepository(session)
        self.exercises = MandateRepository(session)

    def sync_senators(self, uf: str, year: int) -> int:
        legislature = legislature_for_year(year)
        url = f"{SENADO_API}/senador/lista/legislatura/{legislature}"
        root = http.get(
            url,
            params={"uf": uf},
            timeout=60,
            headers={"Accept": "application/xml, text/xml"},
        ).xml()
        count = 0
        for node in root.findall(".//Parlamentar"):
            external_id = _text(node, ".//IdentificacaoParlamentar/CodigoParlamentar")
            name = _text(node, ".//IdentificacaoParlamentar/NomeParlamentar")
            if not external_id or not name:
                continue
            politician = self.people.upsert(
                source="senado",
                external_id=external_id,
                name=name,
                civil_name=_text(node, ".//IdentificacaoParlamentar/NomeCompletoParlamentar"),
                photo_url=_text(node, ".//IdentificacaoParlamentar/UrlFotoParlamentar"),
                gender=_text(node, ".//IdentificacaoParlamentar/SexoParlamentar"),
            )
            party = _text(node, ".//IdentificacaoParlamentar/SiglaPartidoParlamentar")
            participation = _text(node, ".//Mandato/DescricaoParticipacao")
            exercises = node.findall(".//Mandato/Exercicios/Exercicio") or node.findall(".//Exercicio")
            if exercises:
                exercises = [
                    (
                        parse_date(_text(ex, "DataInicio")),
                        parse_date(_text(ex, "DataFim")),
                        _text(ex, "DescricaoCausaAfastamento") or _text(ex, "SiglaCausaAfastamento"),
                    )
                    for ex in exercises
                ]
            else:
                # Mandato/suplência sem nó de exercício não comprova ocupação efetiva.
                exercises = []
            for start, end, reason in exercises:
                if not start or start > date(year, 12, 31) or (end and end < date(year, 1, 1)):
                    continue
                self.exercises.upsert_exercise(
                    {
                        "politician_id": politician.id,
                        "office": "Senador",
                        "jurisdiction_type": "state",
                        "uf": uf,
                        "start_date": start,
                        "end_date": end,
                        "exercise_type": "parliamentary_exercise",
                        "titularity": participation,
                        "end_reason": reason,
                        "party_at_start": party,
                        "source_id": self.source.id,
                        "verification_status": "verified",
                        "original_reference": url,
                    }
                )
                count += 1
        return count

