from __future__ import annotations

from datetime import date, datetime


def parse_date(value: str | date | datetime | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    clean = str(value).strip().split("T")[0].split(" ")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    return None


def year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def intervals_overlap(start: date, end: date | None, range_start: date, range_end: date) -> bool:
    effective_end = end or date.max
    return start <= range_end and effective_end >= range_start


def is_in_office(start: str | date, end: str | date | None, year: int) -> bool:
    parsed_start = parse_date(start)
    parsed_end = parse_date(end)
    if parsed_start is None:
        return False
    return intervals_overlap(parsed_start, parsed_end, *year_bounds(year))


def legislature_for_year(year: int) -> int:
    """Legislatura federal: 56ª=2019–2023, com posse em 1º de fevereiro."""
    return 56 + ((year - 2019) // 4)

