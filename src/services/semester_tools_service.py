from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Iterable, List, Sequence

from ..core.models import Lehrveranstaltung, Semester, Termin
from .id_service import next_id


DATE_MODE_SEMESTER_WEEK = "semester_week"
DATE_MODE_PLUS_YEAR = "plus_year"


@dataclass(frozen=True)
class LvaTermSummary:
    lva_id: str
    lva_name: str
    typ: str
    count: int


def semester_lva_summaries(
    termine: Iterable[Termin],
    lvas: Iterable[Lehrveranstaltung],
    semester_id: str,
) -> List[LvaTermSummary]:
    lva_by_id = {str(lva.id): lva for lva in lvas}
    counts: dict[str, int] = {}
    types_by_lva: dict[str, set[str]] = {}
    for termin in termine:
        if str(getattr(termin, "semester_id", "")) != str(semester_id):
            continue
        lva_id = str(getattr(termin, "lva_id", ""))
        if not lva_id:
            continue
        counts[lva_id] = counts.get(lva_id, 0) + 1
        termin_type = str(getattr(termin, "typ", "") or "").strip()
        if termin_type:
            types_by_lva.setdefault(lva_id, set()).add(termin_type)

    summaries: List[LvaTermSummary] = []
    for lva_id, count in counts.items():
        lva = lva_by_id.get(lva_id)
        typ_values = sorted(types_by_lva.get(lva_id, set()))
        summaries.append(
            LvaTermSummary(
                lva_id=lva_id,
                lva_name=str(getattr(lva, "name", "") or lva_id),
                typ=", ".join(typ_values),
                count=count,
            )
        )
    return sorted(summaries, key=lambda item: (item.lva_name.casefold(), item.lva_id.casefold()))


def count_semester_termine(termine: Iterable[Termin], semester_id: str) -> int:
    return sum(1 for termin in termine if str(getattr(termin, "semester_id", "")) == str(semester_id))


def _add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def map_date_to_target_semester(value: date, source: Semester, target: Semester, mode: str) -> date:
    if mode == DATE_MODE_PLUS_YEAR:
        return _add_years(value, target.start.year - source.start.year)

    source_delta_days = (value - source.start).days
    source_week_index = source_delta_days // 7
    target_week_start = target.start + timedelta(days=source_week_index * 7)
    weekday_offset = (value.weekday() - target_week_start.weekday()) % 7
    return target_week_start + timedelta(days=weekday_offset)


def _map_optional_date(value: date | None, source: Semester, target: Semester, mode: str) -> date | None:
    if value is None:
        return None
    return map_date_to_target_semester(value, source, target, mode)


def _map_series_end_date(value: date | None, source: Semester, target: Semester, mode: str) -> date | None:
    if value is None:
        return None
    if mode == DATE_MODE_SEMESTER_WEEK and value == source.end:
        return target.end
    return map_date_to_target_semester(value, source, target, mode)


def copy_semester_termine(
    termine: Sequence[Termin],
    *,
    source: Semester,
    target: Semester,
    lva_ids: Iterable[str],
    date_mode: str = DATE_MODE_SEMESTER_WEEK,
    copy_ausfall_daten: bool = False,
) -> tuple[List[Termin], int]:
    if source.id == target.id:
        raise ValueError("Quell- und Zielsemester müssen unterschiedlich sein.")

    selected_lva_ids = {str(lva_id) for lva_id in lva_ids if str(lva_id).strip()}
    if not selected_lva_ids:
        return list(termine), 0

    out = list(termine)
    existing_ids = [str(termin.id) for termin in out]
    created: List[Termin] = []

    for termin in termine:
        if str(getattr(termin, "semester_id", "")) != str(source.id):
            continue
        if str(getattr(termin, "lva_id", "")) not in selected_lva_ids:
            continue

        new_id = next_id("T", existing_ids, width=3)
        existing_ids.append(new_id)
        created.append(
            replace(
                termin,
                id=new_id,
                semester_id=target.id,
                datum=_map_optional_date(termin.datum, source, target, date_mode),
                datum_bis=_map_series_end_date(termin.datum_bis, source, target, date_mode),
                ausfall_daten=[
                    map_date_to_target_semester(value, source, target, date_mode)
                    for value in (getattr(termin, "ausfall_daten", []) or [])
                ] if copy_ausfall_daten else [],
            )
        )

    out.extend(created)
    return out, len(created)


def delete_semester_termine(termine: Sequence[Termin], semester_id: str) -> tuple[List[Termin], int]:
    kept = [termin for termin in termine if str(getattr(termin, "semester_id", "")) != str(semester_id)]
    return kept, len(termine) - len(kept)
