from __future__ import annotations

from html.parser import HTMLParser
import json
import re
import ssl
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .id_service import next_id


OPEN_HOLIDAYS_PUBLIC_URL = "https://openholidaysapi.org/PublicHolidays"
OPEN_HOLIDAYS_MAX_DAYS = 1095
TUWIEN_ACADEMIC_CALENDAR_URL = "https://www.tuwien.at/studium/zulassung/akademischer-kalender"

_TUWIEN_FREE_DAY_LABELS = {
    "Allerseelen",
    "Tag des Landespatrons",
    "Weihnachtsferien",
    "Semesterferien",
    "Osterferien",
    "Pfingstferien",
    "Rektorstag",
    "Sommerferien",
}
_TUWIEN_MONTHS = {
    "jänner": 1,
    "februar": 2,
    "märz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}
_TUWIEN_DATE_RE = re.compile(
    r"(\d{1,2})\.\s*"
    r"(Jänner|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"\s+(\d{4})",
    re.IGNORECASE,
)

STATUS_NEW = "Neu"
STATUS_EXISTS = "Schon vorhanden"
STATUS_OVERLAP = "Überlappt"


@dataclass(frozen=True)
class FreeDayCandidate:
    typ: str
    beschreibung: str
    start: date
    end: date
    quelle: str

    @property
    def is_range(self) -> bool:
        return self.start != self.end

    def to_item(self) -> dict[str, Any]:
        return {
            "beschreibung": self.beschreibung,
            "typ": self.typ,
            "von_datum": self.start.isoformat(),
            "bis_datum": self.end.isoformat(),
        }


@dataclass(frozen=True)
class FreeDayPreviewItem:
    candidate: FreeDayCandidate
    status: str
    checked: bool


def build_open_holidays_public_url(
    *,
    valid_from: date,
    valid_to: date,
    country_iso_code: str = "AT",
    subdivision_code: str = "AT-WI",
    language_iso_code: str = "DE",
) -> str:
    params = {
        "countryIsoCode": country_iso_code,
        "subdivisionCode": subdivision_code,
        "languageIsoCode": language_iso_code,
        "validFrom": valid_from.isoformat(),
        "validTo": valid_to.isoformat(),
    }
    return f"{OPEN_HOLIDAYS_PUBLIC_URL}?{urlencode(params)}"


def fetch_open_holidays_public_holidays(
    *,
    valid_from: date,
    valid_to: date,
    country_iso_code: str = "AT",
    subdivision_code: str = "AT-WI",
    language_iso_code: str = "DE",
    timeout_seconds: int = 12,
) -> list[FreeDayCandidate]:
    if valid_to < valid_from:
        raise ValueError("Bis-Datum muss nach dem Von-Datum liegen.")
    if (valid_to - valid_from).days + 1 > OPEN_HOLIDAYS_MAX_DAYS:
        raise ValueError("OpenHolidays erlaubt maximal 1095 Tage pro Anfrage.")

    url = build_open_holidays_public_url(
        valid_from=valid_from,
        valid_to=valid_to,
        country_iso_code=country_iso_code,
        subdivision_code=subdivision_code,
        language_iso_code=language_iso_code,
    )
    request = Request(url, headers={"Accept": "text/json", "User-Agent": "plannerV2"})

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8-sig"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenHolidays antwortet mit HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenHolidays ist nicht erreichbar: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenHolidays hat keine gültige JSON-Antwort geliefert.") from exc

    if not isinstance(payload, list):
        raise RuntimeError("OpenHolidays hat ein unerwartetes Antwortformat geliefert.")

    return [_candidate_from_open_holidays(item, subdivision_code) for item in payload if isinstance(item, dict)]


def fetch_tuwien_academic_free_days(timeout_seconds: int = 12) -> list[FreeDayCandidate]:
    request = Request(
        TUWIEN_ACADEMIC_CALENDAR_URL,
        headers={"Accept": "text/html", "User-Agent": "plannerV2"},
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            html = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"TU-Wien-Kalender antwortet mit HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"TU-Wien-Kalender ist nicht erreichbar: {exc.reason}") from exc
    except ssl.SSLError as exc:
        raise RuntimeError(f"TU-Wien-Kalender konnte wegen TLS/Zertifikat nicht geladen werden: {exc}") from exc

    candidates = parse_tuwien_academic_free_days(html)
    if not candidates:
        raise RuntimeError("Auf der TU-Wien-Seite wurden keine Ferienblöcke erkannt.")
    return candidates


def parse_tuwien_academic_free_days(html: str) -> list[FreeDayCandidate]:
    parts = _extract_text_parts(html)
    candidates: list[FreeDayCandidate] = []
    seen: set[str] = set()

    for start_index, text in enumerate(parts):
        if text != "Einteilung des Studienjahrs":
            continue

        study_year = ""
        free_days_index: int | None = None
        for index in range(start_index + 1, min(start_index + 30, len(parts))):
            if re.fullmatch(r"Wintersemester \d{4}/\d{2}", parts[index]):
                study_year = parts[index].replace("Wintersemester ", "").strip()
            if parts[index] == "Lehrveranstaltungsfreie Zeit (Ferien)":
                free_days_index = index
                break

        if free_days_index is None:
            continue

        for index in range(free_days_index + 1, min(free_days_index + 20, len(parts))):
            line = parts[index]
            if ":" not in line:
                break
            label = line.split(":", 1)[0].strip()
            if label not in _TUWIEN_FREE_DAY_LABELS:
                break

            dates = _parse_tuwien_dates(line)
            if not dates:
                continue
            if " bis " in line.lower() and len(dates) < 2:
                continue
            start = dates[0]
            end = dates[-1]
            source_key = study_year or start.strftime("%Y")
            source_id = f"tuwien:{source_key}:{label}:{start.isoformat()}:{end.isoformat()}"
            if source_id in seen:
                continue
            seen.add(source_id)
            candidates.append(
                FreeDayCandidate(
                    typ="Vorlesungsfrei",
                    beschreibung=label,
                    start=start,
                    end=end,
                    quelle=f"auto:tuwien:academic-calendar:{source_key}",
                )
            )

    return sorted(candidates, key=lambda item: (item.start, item.end, item.beschreibung))


def prepare_free_day_preview(
    candidates: Iterable[FreeDayCandidate],
    existing_items: Iterable[dict[str, Any]],
) -> list[FreeDayPreviewItem]:
    existing = list(existing_items)
    preview: list[FreeDayPreviewItem] = []
    seen_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        status = classify_free_day_candidate(candidate, [*existing, *seen_candidates])
        preview.append(FreeDayPreviewItem(candidate=candidate, status=status, checked=status != STATUS_EXISTS))
        seen_candidates.append(candidate.to_item())
    return preview


def append_free_day_candidates(
    existing_items: list[dict[str, Any]],
    candidates: Iterable[FreeDayCandidate],
) -> tuple[list[dict[str, Any]], int]:
    updated = [dict(item) for item in existing_items]
    changed = 0
    for candidate in candidates:
        if classify_free_day_candidate(candidate, updated) == STATUS_EXISTS:
            continue
        item = candidate.to_item()
        item["id"] = next_id("FT", [str(existing.get("id", "")) for existing in updated], width=3)
        updated.append(item)
        changed += 1
    return updated, changed


def classify_free_day_candidate(candidate: FreeDayCandidate, existing_items: Iterable[dict[str, Any]]) -> str:
    candidate_type = _normalize(candidate.typ)
    candidate_name = _normalize(candidate.beschreibung)

    for item in existing_items:
        item_range = _item_range(item)
        if item_range is None:
            continue

        item_start, item_end = item_range
        item_type = _normalize(str(item.get("typ", "")))
        item_name = _normalize(str(item.get("beschreibung", "")))

        same_range = item_start == candidate.start and item_end == candidate.end
        same_type = item_type == candidate_type
        if same_range and same_type and item_name == candidate_name:
            return STATUS_EXISTS
        if same_range and same_type and _looks_like_named_free_day(candidate, item):
            return STATUS_EXISTS
        if same_type and _ranges_overlap(candidate.start, candidate.end, item_start, item_end):
            return STATUS_OVERLAP

    return STATUS_NEW


def _candidate_from_open_holidays(item: dict[str, Any], subdivision_code: str) -> FreeDayCandidate:
    start = _parse_iso_date(str(item.get("startDate", "")))
    end = _parse_iso_date(str(item.get("endDate", "")))
    if end < start:
        end = start
    return FreeDayCandidate(
        typ="Feiertag",
        beschreibung=_localized_name(item.get("name", []), "DE"),
        start=start,
        end=end,
        quelle=f"auto:openholidays:public:{subdivision_code}",
    )


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.replace("\xa0", " ").split())
        if text:
            self.parts.append(text)


def _extract_text_parts(html: str) -> list[str]:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.parts


def _parse_tuwien_dates(line: str) -> list[date]:
    dates: list[date] = []
    for day, month, year in _TUWIEN_DATE_RE.findall(line):
        month_number = _TUWIEN_MONTHS[month.lower()]
        dates.append(date(int(year), month_number, int(day)))
    return dates




def _localized_name(names: Any, language: str) -> str:
    if isinstance(names, list):
        fallback = ""
        for entry in names:
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("text", "")).strip()
            if not text:
                continue
            fallback = fallback or text
            if str(entry.get("language", "")).upper() == language.upper():
                return text
        if fallback:
            return fallback
    return "Feiertag"


def _item_range(item: dict[str, Any]) -> tuple[date, date] | None:
    try:
        if item.get("von_datum") and item.get("bis_datum"):
            start = _parse_iso_date(str(item["von_datum"]))
            end = _parse_iso_date(str(item["bis_datum"]))
            return (start, end) if end >= start else (end, start)
    except ValueError:
        return None
    return None


def _parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _normalize(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def _looks_like_named_free_day(candidate: FreeDayCandidate, item: dict[str, Any]) -> bool:
    if candidate.is_range:
        return False

    item_range = _item_range(item)
    if item_range is None or item_range[0] != item_range[1]:
        return False

    candidate_source = _normalize(candidate.quelle)
    candidate_name = _normalize(candidate.beschreibung)
    item_name = _normalize(str(item.get("beschreibung", "")))
    if candidate_name and item_name and candidate_name == item_name:
        return True

    automatic_sources = ("auto:openholidays", "auto:tuwien")
    return candidate_source.startswith(automatic_sources)
