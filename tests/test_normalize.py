import pytest

from etl.normalize import municipality_key, normalize_municipality_code, normalize_text


def test_normalize_municipality_without_name_join():
    assert normalize_text("São João d'El-Rei") == "SAO JOAO D EL REI"
    assert normalize_municipality_code("3122306") == "3122306"
    assert municipality_key("3122306", "Divinópolis", "MG") == "3122306"


def test_municipality_code_is_mandatory():
    with pytest.raises(ValueError):
        municipality_key("", "Divinópolis", "MG")

