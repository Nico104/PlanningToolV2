from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Optional

from ..core.models import Semester


SEMESTER_ID_RE = re.compile(r"^(SS|WS)[\s_-]?(\d{2}|\d{4})$", re.IGNORECASE)


def _semester_parts_from_id(semester_id: str) -> tuple[Optional[str], Optional[int]]:
    match = SEMESTER_ID_RE.match(str(semester_id or "").strip())
    if not match:
        return None, None

    kind = match.group(1).upper()
    raw_year = match.group(2)
    if len(raw_year) == 4:
        return kind, int(raw_year)
    return kind, 2000 + int(raw_year)


def semester_id_for_kind_year(kind: str, year: int) -> str:
    return f"{kind.upper()}{year % 100:02d}"


def semester_for_kind_year(kind: str, year: int) -> Semester:
    kind = kind.upper()
    sid = semester_id_for_kind_year(kind, year)
    if kind == "WS":
        return Semester(
            id=sid,
            name=f"Wintersemester {year}/{(year + 1) % 100:02d}",
            start=date(year, 10, 1),
            end=date(year + 1, 1, 31),
        )

    return Semester(
        id=sid,
        name=f"Sommersemester {year}",
        start=date(year, 3, 1),
        end=date(year, 6, 30),
    )


def semester_from_id(semester_id: str) -> Optional[Semester]:
    kind, year = _semester_parts_from_id(semester_id)
    if kind is None or year is None:
        return None
    return semester_for_kind_year(kind, year)


def semester_for_date(value: date) -> Semester:
    if value.month >= 10:
        return semester_for_kind_year("WS", value.year)
    if value.month <= 2:
        return semester_for_kind_year("WS", value.year - 1)
    return semester_for_kind_year("SS", value.year)


def semester_id_for_date(value: date) -> str:
    return semester_for_date(value).id


def _semester_distance_to_dates(semester: Semester, first_date: date, last_date: date) -> int:
    if last_date < semester.start:
        return (semester.start - last_date).days
    if first_date > semester.end:
        return (first_date - semester.end).days
    return 0


def nearest_semester_for_dates(dates: Iterable[date]) -> Optional[Semester]:
    planned_dates = [value for value in dates if value is not None]
    if not planned_dates:
        return None

    first_date = min(planned_dates)
    last_date = max(planned_dates)
    years = range(first_date.year - 1, last_date.year + 2)
    candidates = [
        semester_for_kind_year(kind, year)
        for year in years
        for kind in ("SS", "WS")
    ]

    containing = next(
        (
            semester
            for semester in candidates
            if all(semester.start <= planned_date <= semester.end for planned_date in planned_dates)
        ),
        None,
    )
    if containing:
        return containing

    return min(
        candidates,
        key=lambda semester: (
            _semester_distance_to_dates(semester, first_date, last_date),
            abs((semester.start - first_date).days),
            semester.id,
        ),
    )
