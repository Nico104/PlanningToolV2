from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Optional

from ..core.models import Semester


SEMESTER_ID_RE = re.compile(r"^(SS|WS)[\s_-]?(\d{2}|\d{4})$", re.IGNORECASE)


def semester_year_from_id(semester_id: str) -> Optional[int]:
    match = SEMESTER_ID_RE.match(str(semester_id or "").strip())
    if not match:
        return None

    raw_year = match.group(2)
    if len(raw_year) == 4:
        return int(raw_year)
    return 2000 + int(raw_year)


def generated_semester_id(kind: str, year: int) -> str:
    return f"{kind.upper()}{year % 100:02d}"


def generated_semester_for(kind: str, year: int) -> Semester:
    kind = kind.upper()
    sid = generated_semester_id(kind, year)
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


def generate_semesters(
    *,
    anchor_year: Optional[int] = None,
    extra_ids: Iterable[str] = (),
    years_before: int = 3,
    years_after: int = 6,
) -> list[Semester]:
    base_year = anchor_year or date.today().year
    years = set(range(base_year - years_before, base_year + years_after + 1))

    for semester_id in extra_ids:
        parsed_year = semester_year_from_id(str(semester_id))
        if parsed_year is not None:
            years.add(parsed_year)

    out: list[Semester] = []
    for year in sorted(years):
        out.append(generated_semester_for("SS", year))
        out.append(generated_semester_for("WS", year))
    return out
