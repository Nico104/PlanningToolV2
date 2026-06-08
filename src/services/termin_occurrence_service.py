from dataclasses import replace
import calendar
from datetime import date, timedelta
from typing import Iterable, List, Optional

from ..core.models import Termin


OCCURRENCE_SEPARATOR = "@"
SUPPORTED_PERIODIZITAET = {"täglich", "wöchentlich", "2-wöchentlich", "monatlich", "2-monatlich"}


def occurrence_id(termin_id: str, occurrence_date: date) -> str:
    return f"{termin_id}{OCCURRENCE_SEPARATOR}{occurrence_date.isoformat()}"


def is_occurrence_id(termin_id: str) -> bool:
    return OCCURRENCE_SEPARATOR in str(termin_id)


def source_termin_id(termin_id: str) -> str:
    return str(termin_id).split(OCCURRENCE_SEPARATOR, 1)[0]


def occurrence_date_from_id(termin_id: str) -> Optional[date]:
    parts = str(termin_id).split(OCCURRENCE_SEPARATOR, 1)
    if len(parts) != 2:
        return None
    try:
        return date.fromisoformat(parts[1])
    except Exception:
        return None


def is_series_termin(termin: Termin) -> bool:
    if is_occurrence_id(termin.id):
        return False
    return termin.is_series()


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def series_date_sequence(start: date, end: date, periodizitaet: str) -> List[date]:
    if periodizitaet not in SUPPORTED_PERIODIZITAET:
        return [start]
    if end < start:
        return [start]

    dates: List[date] = []
    if periodizitaet in {"monatlich", "2-monatlich"}:
        months_step = 1 if periodizitaet == "monatlich" else 2
        step = 0
        while True:
            current = add_months(start, step * months_step)
            if current > end:
                break
            dates.append(current)
            step += 1
        return dates

    if periodizitaet == "täglich":
        delta = timedelta(days=1)
    elif periodizitaet == "wöchentlich":
        delta = timedelta(days=7)
    else:
        delta = timedelta(days=14)

    current = start
    while current <= end:
        dates.append(current)
        current += delta
    return dates


def series_dates(termin: Termin) -> List[date]:
    if not is_series_termin(termin):
        return [termin.datum] if termin.datum is not None else []

    if termin.periodizitaet not in SUPPORTED_PERIODIZITAET:
        return [termin.datum] if termin.datum is not None else []

    skipped = set(getattr(termin, "ausfall_daten", []) or [])
    return [
        current
        for current in series_date_sequence(termin.datum, termin.datum_bis, termin.periodizitaet)
        if current not in skipped
    ]


def series_exceptions_by_original_date(termin: Termin):
    out = {}
    for item in getattr(termin, "serien_ausnahmen", []) or []:
        original = getattr(item, "original_datum", None)
        target = getattr(item, "datum", None)
        if original is None or target is None:
            continue
        out[original] = item
    return out


def expand_termin(termin: Termin) -> List[Termin]:
    if not is_series_termin(termin):
        return [termin]
    exceptions = series_exceptions_by_original_date(termin)
    occurrences: List[Termin] = []
    for occurrence_date in series_dates(termin):
        exception = exceptions.get(occurrence_date)
        if exception:
            occurrences.append(
                replace(
                    termin,
                    id=occurrence_id(termin.id, occurrence_date),
                    datum=exception.datum,
                    start_zeit=exception.start_zeit if exception.start_zeit is not None else termin.start_zeit,
                    raum_id=exception.raum_id if exception.raum_id is not None else termin.raum_id,
                    duration=exception.duration if exception.duration is not None else termin.duration,
                )
            )
        else:
            occurrences.append(
                replace(termin, id=occurrence_id(termin.id, occurrence_date), datum=occurrence_date)
            )
    return occurrences


def expand_termine(termine: Iterable[Termin]) -> List[Termin]:
    out: List[Termin] = []
    for termin in termine:
        out.extend(expand_termin(termin))
    return out
