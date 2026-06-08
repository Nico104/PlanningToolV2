from __future__ import annotations

import re
from datetime import date
from typing import Optional

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
