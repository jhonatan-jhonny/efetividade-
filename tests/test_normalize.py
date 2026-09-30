import pytest

from etl.normalize import municipality_key, normalize_municipality_code, normalize_text
from utils.politics import canonical_office, ordered_offices


def test_normalize_municipality_without_name_join():
    assert normalize_text("São João d'El-Rei") == "SAO JOAO D EL REI"
    assert normalize_municipality_code("3122306") == "3122306"
    assert municipality_key("3122306", "Divinópolis", "MG") == "3122306"


def test_municipality_code_is_mandatory():
    with pytest.raises(ValueError):
        municipality_key("", "Divinópolis", "MG")


def test_canonical_office_keeps_each_political_role_separate():
    assert canonical_office("PRESIDENTE") == "Presidente"
    assert canonical_office("VICE-PREFEITO") == "Vice-prefeito"
    assert canonical_office("Deputado Federal") == "Deputado federal"
    assert canonical_office("DEPUTADO ESTADUAL") == "Deputado estadual"
    offices = ordered_offices(["PREFEITO", "Cargo regional"])
    assert offices.count("Prefeito") == 1
    assert offices[-1] == "Cargo regional"

