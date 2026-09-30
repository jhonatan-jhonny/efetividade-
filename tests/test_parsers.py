from services.camara import reconstruct_exercise_intervals
from services.ibge import _extract_series
from services.sinesp import _find_column
from services.tse import _resource


def test_ibge_parser_keeps_missing_as_null():
    payload = [{"variavel": "População", "unidade": "Pessoas", "resultados": [{"series": [{"serie": {"2022": "231091"}}]}]}]
    assert _extract_series(payload, 2022)[0] == 231091
    assert _extract_series([], 2022)[0] is None


def test_camara_parser_reconstructs_real_intervals_and_party_change():
    events = [
        {"dataHora": "2021-01-01T10:00", "situacao": "Exercício", "siglaPartido": "A", "descricaoStatus": "Entrada - Posse"},
        {"dataHora": "2022-03-31T18:00", "situacao": "Exercício", "siglaPartido": "B", "descricaoStatus": "Alteração de partido"},
        {"dataHora": "2023-05-14T12:00", "situacao": "Afastado", "siglaPartido": "B", "descricaoStatus": "Saída - Licença"},
        {"dataHora": "2023-08-02T12:00", "situacao": "Exercício", "siglaPartido": "B", "descricaoStatus": "Entrada - Retorno"},
        {"dataHora": "2024-12-31T23:59", "situacao": "Fim de Mandato", "siglaPartido": "B"},
    ]
    intervals = reconstruct_exercise_intervals(events, 2023)
    assert len(intervals) == 2
    assert intervals[0]["end_date"].isoformat() == "2023-05-14"
    assert intervals[1]["start_date"].isoformat() == "2023-08-02"


def test_tse_catalog_resource_and_sinesp_columns():
    package = {"resources": [{"name": "Candidatos", "url": "https://cdn.tse.jus.br/file.zip"}]}
    assert _resource(package, "candidatos").endswith("file.zip")
    columns = ["Código IBGE", "Ano de referência", "Quantidade de ocorrências"]
    assert _find_column(columns, "codigo ibge") == "Código IBGE"
    assert _find_column(columns, "quantidade") == "Quantidade de ocorrências"

