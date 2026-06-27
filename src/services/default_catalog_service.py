from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from .import_merge_service import build_payload

DEFAULT_CATALOG_LABEL = "TISS-Daten TU Wien ETIT, Juni 2026"


def _default_tables_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "default_tables"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int_value(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except Exception:
        return 0


def _first_email(value: Any) -> str:
    return _text(value).split(";", 1)[0].strip()


def _semester_ids(value: Any) -> list[str]:
    text = _text(value)
    if not text:
        return []
    semester_ids: list[str] = []
    for part in (item.strip() for item in re.split(r"[;,/]", text)):
        if not part:
            continue
        if part.lower() in {"ohne semesterempfehlung", "ohne empfehlung", "none", "null", "-"}:
            continue
        semester_id = f"sem{part}" if part.isdigit() else part
        if semester_id not in semester_ids:
            semester_ids.append(semester_id)
    return semester_ids


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_default_catalog_payload(
    default_dir: Path | None = None,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    base = default_dir or _default_tables_dir()
    entries_by_file: dict[str, list[dict[str, Any]]] = {}

    lvas: list[dict[str, Any]] = []
    seen_lvas: set[str] = set()
    for row in _read_csv(base / "tu_wien_etit_lva_vortragende_2026S.csv"):
        lva_id = _text(row.get("id"))
        if not lva_id or lva_id in seen_lvas:
            continue
        seen_lvas.add(lva_id)
        lvas.append(
            {
                "id": lva_id,
                "name": _text(row.get("name")),
                "vortragende": {
                    "name": _text(row.get("vortragende_name")),
                    "email": _first_email(row.get("vortragende_email")),
                },
                "studiensemester": _semester_ids(row.get("studiensemester")),
                "studienrichtung": _text(row.get("studienrichtung")) or "ETIT",
                "ects": _text(row.get("ects")),
            }
        )
    if lvas:
        entries_by_file["lehrveranstaltungen.json"] = lvas

    rooms: list[dict[str, Any]] = []
    seen_rooms: set[str] = set()
    for row in _read_csv(base / "tu_wien_raeume.csv"):
        room_id = _text(row.get("id"))
        if not room_id or room_id in seen_rooms:
            continue
        seen_rooms.add(room_id)
        rooms.append(
            {
                "id": room_id,
                "name": _text(row.get("name")),
                "kapazitaet": _int_value(row.get("kapazitaet")),
                "gebaeude": _text(row.get("gebaeude")),
                "__catalog_gebaeude": _text(row.get("gebaeude")),
            }
        )
    if rooms:
        entries_by_file["raeume.json"] = rooms

    return build_payload(entries_by_file)
