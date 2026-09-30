from datetime import date

from utils.dates import is_in_office, year_bounds


def test_interval_overlaps_year():
    assert is_in_office("2021-01-01", "2023-05-14", 2023)
    assert not is_in_office("2021-01-01", "2022-12-31", 2023)
    assert is_in_office("2023-12-31", None, 2023)


def test_leap_year_boundaries():
    assert date(2024, 2, 29)
    assert year_bounds(2024) == (date(2024, 1, 1), date(2024, 12, 31))
    assert is_in_office("2024-02-29", "2024-02-29", 2024)

