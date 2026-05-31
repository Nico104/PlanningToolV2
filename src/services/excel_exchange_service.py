from __future__ import annotations

import json
import re
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .termin_occurrence_service import SUPPORTED_PERIODIZITAET, series_date_sequence
from .semester_generation import generate_semesters


_FILE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "raeume.json": {
        "sheet": "Raeume",
        "list_key": "raeume",
        "columns": ["id", "name", "kapazitaet"],
    },
    "lehrveranstaltungen.json": {
        "sheet": "Lehrveranstaltungen",
        "list_key": "lehrveranstaltungen",
        "columns": [
            "id",
            "name",
            "vortragende.name",
            "vortragende.email",
            "typ",
            "studiensemester",
            "studienrichtung",
            "ects",
        ],
    },
    "termine.json": {
        "sheet": "Termine",
        "list_key": "termine",
        "columns": [
            "id",
            "name",
            "lva_id",
            "typ",
            "datum",
            "datum_bis",
            "periodizitaet",
            "start_zeit",
            "raum_id",
            "gruppe.name",
            "gruppe.groesse",
            "anwesenheitspflicht",
            "duration",
            "semester_id",
            "ausfall_daten",
            "notiz",
        ],
    },
    "studienrichtungen.json": {
        "sheet": "Studienrichtungen",
        "list_key": "studienrichtungen",
        "columns": ["id", "name"],
    },
    "freie_tage.json": {
        "sheet": "FreieTage",
        "list_key": "freie_tage",
        "columns": ["id", "typ", "beschreibung", "datum", "von_datum", "bis_datum"],
    },
    "studiensemester.json": {
        "sheet": "Studiensemester",
        "list_key": "studiensemester",
        "columns": ["id", "name", "notiz"],
    },
}

_EXCEL_HEADER_LABELS: Dict[str, str] = {
    "lehrveranstaltungen.json:id": "LVA-Nr.",
    "lehrveranstaltungen.json:studienrichtung": "Studienrichtung",
    "lehrveranstaltungen.json:studiensemester": "Studiensemester",
    "termine.json:lva_id": "LVA-Nr.",
}


@dataclass(frozen=True)
class TeacherExportOption:
    name: str
    email: str
    lva_count: int
    term_count: int

    @property
    def key(self) -> tuple[str, str]:
        return (self.name, self.email)


def _read_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_json_list(path: Path, list_key: str) -> List[Dict[str, Any]]:
    payload = _read_json_file(path)
    rows = payload.get(list_key, []) if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def _semester_export_rows(data_dir: Path) -> List[Dict[str, Any]]:
    extra_ids = {
        _safe_text(item.get("semester_id"))
        for item in _read_json_list(data_dir / "termine.json", "termine")
        if _safe_text(item.get("semester_id"))
    }
    return [
        {"id": s.id, "name": s.name, "start": s.start.isoformat(), "end": s.end.isoformat()}
        for s in generate_semesters(extra_ids=extra_ids)
    ]


def _get_nested(data: Dict[str, Any], path: str) -> Any:
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
        if node is None:
            return None
    return node


def _set_nested(data: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    node = data
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    node[parts[-1]] = value


def _serialize_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(str(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _safe_date(value: Any) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = _safe_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue
    return None


def _safe_time(value: Any) -> Optional[time]:
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    text = _safe_text(value)
    if not text:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except Exception:
            continue
    return None


def _safe_end_time(start_value: Any, duration_value: Any) -> Optional[time]:
    start = _safe_time(start_value)
    duration = _parse_int(duration_value)
    if start is None or duration is None or duration <= 0:
        return None
    base = datetime.combine(date(2000, 1, 1), start)
    return (base + timedelta(minutes=duration)).time()


def _excel_compatible_sheet_name(base_name: str, used_names: set[str]) -> str:
    cleaned = re.sub(r"[\\/?*\[\]:]", "", _safe_text(base_name))
    cleaned = re.sub(r"\s+", " ", cleaned).strip() or "Ohne Lehrperson"
    cleaned = cleaned[:31]

    candidate = cleaned
    index = 2
    while candidate in used_names:
        suffix = f" {index}"
        candidate = f"{cleaned[:31 - len(suffix)]}{suffix}".strip()
        index += 1
    used_names.add(candidate)
    return candidate


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    txt = str(value).strip().lower()
    return txt in {"1", "true", "wahr", "yes", "ja"}


def _parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    txt = str(value).strip()
    if not txt:
        return None
    return int(float(txt))


def _parse_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    txt = str(value).strip()
    if not txt:
        return []
    return [p.strip() for p in txt.split(";") if p.strip()]


def _series_dates_from_entry(termin: Dict[str, Any]) -> List[date]:
    start = _safe_date(termin.get("datum"))
    end = _safe_date(termin.get("datum_bis"))
    period = _safe_text(termin.get("periodizitaet"))
    if start is None:
        return []
    if end is None or end < start or period not in SUPPORTED_PERIODIZITAET:
        return [start]
    skipped = {d for d in (_safe_date(item) for item in _parse_list(termin.get("ausfall_daten"))) if d is not None}
    return [current for current in series_date_sequence(start, end, period) if current not in skipped]


def _expand_termin_entries(termine: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for termin in termine:
        if not isinstance(termin, dict):
            continue
        dates = _series_dates_from_entry(termin)
        if not dates:
            yield termin
            continue
        if len(dates) == 1:
            item = dict(termin)
            item["datum"] = dates[0].isoformat()
            yield item
            continue
        for occurrence_date in dates:
            item = dict(termin)
            item["datum"] = occurrence_date.isoformat()
            yield item


def _normalize_entry(file_name: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    if file_name == "raeume.json":
        if "kapazitaet" in entry:
            val = _parse_int(entry.get("kapazitaet"))
            entry["kapazitaet"] = 0 if val is None else val
    elif file_name == "lehrveranstaltungen.json":
        entry["typ"] = _parse_list(entry.get("typ"))
        entry["studiensemester"] = _parse_list(entry.get("studiensemester"))
    elif file_name == "termine.json":
        entry["notiz"] = str(entry.get("notiz", ""))
        entry["raum_id"] = str(entry.get("raum_id", ""))
        entry["semester_id"] = str(entry.get("semester_id", ""))
        period = str(entry.get("periodizitaet", "") or "").strip()
        entry["periodizitaet"] = None if not period or period.lower() == "keine" else period
        entry["ausfall_daten"] = _parse_list(entry.get("ausfall_daten"))

        if "duration" in entry:
            val = _parse_int(entry.get("duration"))
            entry["duration"] = 0 if val is None else val
        else:
            entry["duration"] = 0

        entry["anwesenheitspflicht"] = _parse_bool(entry.get("anwesenheitspflicht"))

        gruppe = entry.get("gruppe")
        if isinstance(gruppe, dict):
            g_name = str(gruppe.get("name", "")).strip()
            g_size = _parse_int(gruppe.get("groesse"))
            if g_name or g_size not in (None, 0):
                entry["gruppe"] = {"name": g_name or "-", "groesse": g_size or 0}
            else:
                entry["gruppe"] = None
        else:
            entry["gruppe"] = None

        if entry.get("datum") in (None, ""):
            entry["datum"] = None
        if entry.get("datum_bis") in (None, ""):
            entry["datum_bis"] = None
            entry["periodizitaet"] = None
        if entry.get("start_zeit") in (None, ""):
            entry["start_zeit"] = None
    elif file_name == "freie_tage.json":
        if not str(entry.get("id", "")).strip():
            entry.pop("id", None)
        datum = str(entry.get("datum", "")).strip()
        von = str(entry.get("von_datum", "")).strip()
        bis = str(entry.get("bis_datum", "")).strip()
        if datum:
            entry["datum"] = datum
            entry.pop("von_datum", None)
            entry.pop("bis_datum", None)
        elif von and bis:
            entry["von_datum"] = von
            entry["bis_datum"] = bis
            entry.pop("datum", None)
    return entry


def export_project_to_excel(data_dir: Path, output_path: Path) -> None:
    wb = Workbook()
    default_sheet = wb.active
    wb.remove(default_sheet)

    for file_name, cfg in _FILE_SCHEMAS.items():
        sheet = wb.create_sheet(cfg["sheet"])
        columns: List[str] = cfg["columns"]
        list_key = cfg["list_key"]
        sheet.append([_EXCEL_HEADER_LABELS.get(f"{file_name}:{col}", col) for col in columns])

        payload = _read_json_file(data_dir / file_name)
        rows = payload.get(list_key, []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            rows = []

        for item in rows:
            if not isinstance(item, dict):
                continue
            row = [_serialize_cell(_get_nested(item, col)) for col in columns]
            sheet.append(row)

    wb.save(output_path)


def _is_empty_row(values: Tuple[Any, ...]) -> bool:
    for val in values:
        if val is not None and str(val).strip() != "":
            return False
    return True


def import_project_from_excel(excel_path: Path) -> Dict[str, Dict[str, Any]]:
    wb = load_workbook(excel_path, data_only=True)
    result: Dict[str, Dict[str, Any]] = {}

    for file_name, cfg in _FILE_SCHEMAS.items():
        sheet_name = cfg["sheet"]
        columns: List[str] = cfg["columns"]
        list_key = cfg["list_key"]

        if sheet_name not in wb.sheetnames:
            sheet_name = next((alias for alias in cfg.get("sheet_aliases", []) if alias in wb.sheetnames), sheet_name)
        if sheet_name not in wb.sheetnames:
            continue

        ws = wb[sheet_name]
        entries: List[Dict[str, Any]] = []

        for values in ws.iter_rows(min_row=2, max_col=len(columns), values_only=True):
            if _is_empty_row(values):
                continue

            entry: Dict[str, Any] = {}
            for idx, col in enumerate(columns):
                raw = values[idx] if idx < len(values) else None
                if raw is None:
                    continue
                txt = str(raw).strip()
                if txt == "":
                    continue
                _set_nested(entry, col, txt)

            normalized = _normalize_entry(file_name, entry)
            entries.append(normalized)

        result[file_name] = {list_key: entries}

    return result


def get_teacher_export_options(data_dir: Path) -> List[TeacherExportOption]:
    lvas = _read_json_list(data_dir / "lehrveranstaltungen.json", "lehrveranstaltungen")
    termine = _read_json_list(data_dir / "termine.json", "termine")

    teacher_lvas: Dict[tuple[str, str], set[str]] = defaultdict(set)
    lva_teacher: Dict[str, tuple[str, str]] = {}

    for lva in lvas:
        if not isinstance(lva, dict):
            continue
        name = _safe_text(lva.get("vortragende", {}).get("name"))
        email = _safe_text(lva.get("vortragende", {}).get("email"))
        lva_id = _safe_text(lva.get("id"))
        if not name:
            continue
        key = (name, email)
        if lva_id:
            teacher_lvas[key].add(lva_id)
            lva_teacher[lva_id] = key
        else:
            teacher_lvas[key]

    teacher_terms: Dict[tuple[str, str], int] = defaultdict(int)
    for termin in _expand_termin_entries(termine):
        if not isinstance(termin, dict):
            continue
        key = lva_teacher.get(_safe_text(termin.get("lva_id")))
        if key:
            teacher_terms[key] += 1

    return [
        TeacherExportOption(
            name=name,
            email=email,
            lva_count=len(teacher_lvas[(name, email)]),
            term_count=teacher_terms[(name, email)],
        )
        for name, email in sorted(teacher_lvas.keys(), key=lambda item: (item[0].lower(), item[1].lower()))
    ]


def export_terms_for_teachers_to_excel(
    data_dir: Path,
    output_path: Path,
    teacher_filter: Optional[Iterable[tuple[str, str]]] = None,
) -> None:
    headers = [
        "Raum",
        "Datum",
        "Beginn",
        "Ende",
        "LVA-Nr.",
        "Lehrveranstaltung",
        "Lehrperson",
        "E-Mail",
        "Typ",
        "Semester",
        "Gruppe",
        "Gruppengröße",
        "Anwesenheitspflicht",
    ]

    teacher_filter_set = (
        {(_safe_text(item[0]), _safe_text(item[1] if len(item) > 1 else "")) for item in teacher_filter}
        if teacher_filter is not None
        else None
    )
    lvas = _read_json_list(data_dir / "lehrveranstaltungen.json", "lehrveranstaltungen")
    termine = _read_json_list(data_dir / "termine.json", "termine")
    raeume = _read_json_list(data_dir / "raeume.json", "raeume")
    semester = _semester_export_rows(data_dir)

    lva_map = {_safe_text(item.get("id")): item for item in lvas if _safe_text(item.get("id"))}
    raum_map = {_safe_text(item.get("id")): item for item in raeume if _safe_text(item.get("id"))}
    semester_map = {_safe_text(item.get("id")): item for item in semester if _safe_text(item.get("id"))}

    rows_by_teacher: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    rows_without_teacher: List[Dict[str, Any]] = []
    if teacher_filter_set is not None:
        for teacher_key in teacher_filter_set:
            if teacher_key[0]:
                rows_by_teacher[teacher_key]

    for termin in _expand_termin_entries(termine):
        if not isinstance(termin, dict):
            continue

        lva = lva_map.get(_safe_text(termin.get("lva_id")))
        teacher_name = _safe_text(lva.get("vortragende", {}).get("name")) if isinstance(lva, dict) else ""
        teacher_email = _safe_text(lva.get("vortragende", {}).get("email")) if isinstance(lva, dict) else ""
        if teacher_filter_set is not None and (teacher_name, teacher_email) not in teacher_filter_set:
            continue
        room_item = raum_map.get(_safe_text(termin.get("raum_id")))
        semester_item = semester_map.get(_safe_text(termin.get("semester_id")))
        gruppe = termin.get("gruppe") if isinstance(termin.get("gruppe"), dict) else {}
        datum = _safe_date(termin.get("datum"))
        start = _safe_time(termin.get("start_zeit"))
        ende = _safe_end_time(termin.get("start_zeit"), termin.get("duration"))

        row = {
            "LVA-Nr.": _safe_text(lva.get("id")) if isinstance(lva, dict) else _safe_text(termin.get("lva_id")),
            "Lehrveranstaltung": _safe_text(lva.get("name")) if isinstance(lva, dict) else _safe_text(termin.get("name")),
            "Lehrperson": teacher_name,
            "E-Mail": teacher_email,
            "Typ": _safe_text(termin.get("typ")),
            "Semester": _safe_text(semester_item.get("name")) if isinstance(semester_item, dict) else _safe_text(termin.get("semester_id")),
            "Gruppe": _safe_text(gruppe.get("name")) if isinstance(gruppe, dict) else "",
            "Gruppengröße": gruppe.get("groesse", "") if isinstance(gruppe, dict) else "",
            "Raum": _safe_text(room_item.get("name")) if isinstance(room_item, dict) else _safe_text(termin.get("raum_id")),
            "Datum": datum.isoformat() if datum else "",
            "Beginn": start.strftime("%H:%M") if start else "",
            "Ende": ende.strftime("%H:%M") if ende else "",
            "Anwesenheitspflicht": "Ja" if bool(termin.get("anwesenheitspflicht", False)) else "Nein",
        }

        (rows_by_teacher[(teacher_name, teacher_email)] if teacher_name else rows_without_teacher).append(row)

    def sort_key(row: Dict[str, Any]) -> tuple:
        datum = _safe_date(row.get("Datum"))
        start = _safe_time(row.get("Beginn"))
        return (datum is None, datum or date.max, start is None, start or time.max, _safe_text(row.get("LVA-Nr.")))

    def write_sheet(sheet, data_rows: List[Dict[str, Any]]) -> None:
        sheet.append(headers)
        for row in data_rows:
            sheet.append([row.get(col, "") for col in headers])
        if data_rows:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions

        header_fill = PatternFill("solid", fgColor="1F4E78")
        header_font = Font(color="FFFFFF", bold=False)
        border = Border(bottom=Side(style="thin", color="9EADBA"))
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.border = border
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for column_cells in sheet.columns:
            width = 0
            for cell in column_cells:
                value = cell.value
                if value is None:
                    continue
                text = value.strftime("%H:%M") if isinstance(value, time) else value.isoformat() if isinstance(value, date) and not isinstance(value, datetime) else str(value)
                width = max(width, len(text))
            sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(max(width + 2, 10), 36)

    wb = Workbook()
    wb.remove(wb.active)
    used_names: set[str] = set()

    if rows_without_teacher and teacher_filter_set is None:
        sheet = wb.create_sheet(_excel_compatible_sheet_name("Ohne Lehrperson", used_names))
        write_sheet(sheet, sorted(rows_without_teacher, key=sort_key))

    teacher_counts: Dict[str, int] = defaultdict(int)
    for (teacher_name, teacher_email), data_rows in sorted(rows_by_teacher.items(), key=lambda item: (item[0][0].lower(), item[0][1].lower())):
        base_name = teacher_name or teacher_email or "Ohne Lehrperson"
        teacher_counts[base_name] += 1
        display_name = base_name if teacher_counts[base_name] == 1 else f"{base_name} {teacher_counts[base_name]}"
        sheet = wb.create_sheet(_excel_compatible_sheet_name(display_name, used_names))
        write_sheet(sheet, sorted(data_rows, key=sort_key))

    if not wb.sheetnames:
        sheet = wb.create_sheet(_excel_compatible_sheet_name("Keine Termine", used_names))
        write_sheet(sheet, [])

    wb.save(output_path)
