from datetime import date, time, datetime, timedelta
from typing import List, Dict, Optional, Tuple
import os
import json
from pathlib import Path
from ..core.models import Termin, Lehrveranstaltung, Raum, ConflictIssue


DEFAULT_CONFLICTS_PATH = Path(__file__).resolve().parents[1] / "konflikte.json"


def load_conflicts(path=None):
    path = path or str(DEFAULT_CONFLICTS_PATH)
    abs_path = os.path.abspath(path)
    try:
        with open(abs_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return []

def save_conflicts(conflicts, path=None):
    path = path or str(DEFAULT_CONFLICTS_PATH)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(conflicts, f, ensure_ascii=False, indent=4)
    except Exception:
        pass


UNASSIGNED_DATE = date(2026, 1, 1)


class ConflictDetector:
    def __init__(self, 
                 lvas: List[Lehrveranstaltung],
                 raeume: List[Raum],
                 conflict_settings_path: str = None,
                 data_dir: str | Path | None = None):
        self.lvas = lvas
        self.raeume = raeume
        self.data_dir = Path(data_dir).resolve() if data_dir else None
        # Load conflict settings (konflikte.json)
        self.conflict_settings = {}
        settings = load_conflicts(conflict_settings_path)
        for entry in settings:
            key = entry.get("key")
            if key:
                self.conflict_settings[key] = entry
        self._free_days_by_date = self._load_free_days_map(conflict_settings_path)
    
    def is_assigned(self, termin: Termin) -> bool:
        return (termin.datum is not None and 
                termin.datum != UNASSIGNED_DATE and
                termin.start_zeit is not None)
    
    def times_overlap(self, t1: Termin, t2: Termin) -> bool:
        if not t1.start_zeit or not t2.start_zeit:
            return False
        if t1.duration <= 0 or t2.duration <= 0:
            return False
        
        end1 = t1.get_end_time()
        end2 = t2.get_end_time()
        
        if not end1 or not end2:
            return False
        
        return (t1.start_zeit < end2) and (t2.start_zeit < end1)

    def _render_message(self, settings=None, values: Optional[Dict[str, object]] = None) -> str:
        if not settings:
            return ""

        name = str(settings.get("name", "")).strip()
        template = str(settings.get("message_template", "")).strip()
        description = str(settings.get("description", "")).strip()

        detail = ""
        if template:
            try:
                detail = template.format(**(values or {}))
            except Exception:
                detail = template
        elif description:
            detail = description

        if name and detail:
            return f"{name}: {detail}"
        return name or detail
    
    
    def detect_all(self, termine: List[Termin]) -> List[ConflictIssue]:
        """Detect all conflicts and warnings in the given Termine list, respecting settings from konflikte.json."""
        issues = []
        assigned = [t for t in termine if self.is_assigned(t)]

        # Tuple format: (settings_key, detector_fn, assigned_only)
        rules = [
            ("room_conflict", self.detect_room_conflicts, True),
            ("group_conflict", self.detect_group_conflicts, True),
            ("lecturer_conflict", self.detect_lecturer_conflicts, True),
            ("holiday_conflict", self.detect_holiday_conflicts, True),
            ("lecture_free_conflict", self.detect_lecture_free_conflicts, True),
            ("incomplete_warning", self.detect_incomplete_warnings, False),
            ("duration_warning", self.detect_duration_warnings, False),
            ("weekend_warning", self.detect_weekend_warnings, False),
            ("saturday_warning", self.detect_saturday_warning, False),
            ("sunday_warning", self.detect_sunday_warning, False),
            ("capacity_warning_uebung", self.detect_capacity_warning_uebung, False),
            ("capacity_warning_vorlesung", self.detect_capacity_warning_vorlesung, False),
        ]

        for key, detector, assigned_only in rules:
            settings = self.conflict_settings.get(key, {})
            if not settings.get("enabled", True):
                continue
            source = assigned if assigned_only else termine
            detected = detector(source, settings)
            if detected:
                issues.extend(detected)
        return issues
    
    
    
    def detect_incomplete_warnings(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect warnings for incomplete or unassigned Termine. Uses settings if provided."""
        warnings = []
        missing_labels = (settings or {}).get("missing_labels", {})
        if not isinstance(missing_labels, dict):
            missing_labels = {}

        def label(key: str) -> str:
            val = str(missing_labels.get(key, "")).strip()
            return val

        for t in termine:
            problems = []
            has_missing = False
            # Check for missing/unassigned date
            if t.datum is None or t.datum == UNASSIGNED_DATE:
                has_missing = True
                txt = label("date")
                if txt:
                    problems.append(txt)
            # Check for missing time
            if t.start_zeit is None:
                has_missing = True
                txt = label("start_time")
                if txt:
                    problems.append(txt)
            # Check for missing/invalid duration
            if t.duration <= 0:
                has_missing = True
                txt = label("duration")
                if txt:
                    problems.append(txt)
            # Check for missing room
            if not t.raum_id or t.raum_id.strip() == "":
                has_missing = True
                txt = label("room")
                if txt:
                    problems.append(txt)
            if has_missing:
                lva = next((l for l in self.lvas if l.id == t.lva_id), None)
                raum = next((r for r in self.raeume if r.id == t.raum_id), None)
                msg = self._render_message(settings, {"missing": ", ".join(problems)})
                warnings.append(ConflictIssue(
                    severity="warning",
                    category="incomplete",
                    termin_ids=[t.id],
                    message=msg,
                    datum=t.datum if t.datum and t.datum != UNASSIGNED_DATE else None,
                    zeit_von=t.start_zeit,
                    zeit_bis=t.get_end_time(),
                    raum=raum.name if raum else "",
                    lva=lva.name if lva else t.lva_id,
                    gruppe=t.gruppe.name if t.gruppe else ""
                ))
        return warnings
    
    def detect_room_conflicts(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect room conflicts (same room, date, overlapping time). Uses settings if provided."""
        conflicts = []
        by_room_date: Dict[Tuple[str, date], List[Termin]] = {}
        for t in termine:
            if not t.raum_id or not t.datum:
                continue
            key = (t.raum_id, t.datum)
            by_room_date.setdefault(key, []).append(t)
        for (raum_id, datum), terms in by_room_date.items():
            for i, t1 in enumerate(terms):
                for t2 in terms[i+1:]:
                    if self.times_overlap(t1, t2):
                        if t1.id < t2.id:
                            conflicts.append(self._create_conflict(
                                "room", t1, t2, settings
                            ))
        return conflicts
    
    def detect_group_conflicts(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect group conflicts (same LVA + group, date, overlapping time). Uses settings if provided."""
        conflicts = []
        by_lva_group_date: Dict[Tuple[str, str, date], List[Termin]] = {}
        for t in termine:
            if not t.datum or not t.gruppe:
                continue
            group_key = t.gruppe.name
            key = (t.lva_id, group_key, t.datum)
            by_lva_group_date.setdefault(key, []).append(t)
        for key, terms in by_lva_group_date.items():
            for i, t1 in enumerate(terms):
                for t2 in terms[i+1:]:
                    if self.times_overlap(t1, t2):
                        if t1.id < t2.id:
                            conflicts.append(self._create_conflict(
                                "group", t1, t2, settings
                            ))
        return conflicts
    
    def detect_lecturer_conflicts(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect lecturer conflicts (same lecturer, date, overlapping time). Uses settings if provided."""
        conflicts = []
        by_lecturer_date = []
        for t in termine:
            if not t.datum:
                continue
            lva = next((l for l in self.lvas if l.id == t.lva_id), None)
            if not lva or not lva.vortragende:
                continue
            lecturer_key = lva.vortragende.email
            found = next((bl for bl in by_lecturer_date if bl[0] == lecturer_key and bl[1] == t.datum), None)
            if found:
                found[2].append(t)
            else:
                by_lecturer_date.append([lecturer_key, t.datum, [t]])
        for bl in by_lecturer_date:
            lecturer_email, datum, terms = bl
            for i, t1 in enumerate(terms):
                for t2 in terms[i+1:]:
                    if self.times_overlap(t1, t2):
                        if t1.id < t2.id:
                            conflicts.append(self._create_conflict(
                                "lecturer", t1, t2, settings
                            ))
        return conflicts

    def detect_holiday_conflicts(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect conflicts for Termine that fall on Feiertag dates"""
        conflicts: List[ConflictIssue] = []
        if not self._free_days_by_date:
            return conflicts

        for t in termine:
            if not self.is_assigned(t):
                continue
            if not t.datum:
                continue
            day_types = self._free_days_by_date.get(t.datum, set())
            if "feiertag" not in day_types:
                continue

            lva = next((l for l in self.lvas if l.id == t.lva_id), None)
            raum = next((r for r in self.raeume if r.id == t.raum_id), None)
            msg = self._render_message(settings)

            conflicts.append(ConflictIssue(
                severity="conflict",
                category="holiday",
                termin_ids=[t.id],
                message=msg,
                datum=t.datum,
                zeit_von=t.start_zeit,
                zeit_bis=t.get_end_time(),
                raum=raum.name if raum else "",
                lva=lva.name if lva else t.lva_id,
                gruppe=t.gruppe.name if t.gruppe else "",
            ))

        return conflicts

    def detect_lecture_free_conflicts(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect conflicts for Termine that fall on Vorlesungsfrei dates"""
        conflicts: List[ConflictIssue] = []
        if not self._free_days_by_date:
            return conflicts

        for t in termine:
            if not self.is_assigned(t):
                continue
            if not t.datum:
                continue
            day_types = self._free_days_by_date.get(t.datum, set())
            if "vorlesungsfrei" not in day_types:
                continue

            lva = next((l for l in self.lvas if l.id == t.lva_id), None)
            raum = next((r for r in self.raeume if r.id == t.raum_id), None)
            msg = self._render_message(settings)

            conflicts.append(ConflictIssue(
                severity="conflict",
                category="lecture_free",
                termin_ids=[t.id],
                message=msg,
                datum=t.datum,
                zeit_von=t.start_zeit,
                zeit_bis=t.get_end_time(),
                raum=raum.name if raum else "",
                lva=lva.name if lva else t.lva_id,
                gruppe=t.gruppe.name if t.gruppe else "",
            ))

        return conflicts
    
    
    def detect_duration_warnings(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect warnings for Termine that are unusually short or long"""
        warnings = []
        min_minutes = 30
        max_minutes = 240
        for t in termine:
            if not self.is_assigned(t):
                continue
            duration = t.duration
            if duration > 0 and (duration < min_minutes or duration > max_minutes):
                lva = next((l for l in self.lvas if l.id == t.lva_id), None)
                raum = next((r for r in self.raeume if r.id == t.raum_id), None)
                msg = self._render_message(settings, {"duration": duration})
                warnings.append(ConflictIssue(
                    severity="warning",
                    category="duration",
                    termin_ids=[t.id],
                    message=msg,
                    datum=t.datum,
                    zeit_von=t.start_zeit,
                    zeit_bis=t.get_end_time(),
                    raum=raum.name if raum else "",
                    lva=lva.name if lva else t.lva_id,
                    gruppe=t.gruppe.name if t.gruppe else ""
                ))
        return warnings

    def detect_weekend_warnings(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect warnings for Termine that fall on a weekend (Saturday or Sunday)"""
        warnings = []
        for t in termine:
            if not t.datum:
                continue
            if t.datum.weekday() >= 5:  # 5=Saturday, 6=Sunday
                lva = next((l for l in self.lvas if l.id == t.lva_id), None)
                raum = next((r for r in self.raeume if r.id == t.raum_id), None)
                msg = self._render_message(settings)
                warnings.append(ConflictIssue(
                    severity="warning",
                    category="weekend",
                    termin_ids=[t.id],
                    message=msg,
                    datum=t.datum,
                    zeit_von=t.start_zeit,
                    zeit_bis=t.get_end_time(),
                    raum=raum.name if raum else "",
                    lva=lva.name if lva else t.lva_id,
                    gruppe=t.gruppe.name if t.gruppe else ""
                ))
        return warnings
    
    def detect_saturday_warning(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect warnings for Termine that fall on a Saturday"""
        warnings = []
        for t in termine:
            if not t.datum:
                continue
            if t.datum.weekday() == 5:  # Saturday
                lva = next((l for l in self.lvas if l.id == t.lva_id), None)
                raum = next((r for r in self.raeume if r.id == t.raum_id), None)
                msg = self._render_message(settings)
                warnings.append(ConflictIssue(
                    severity="warning",
                    category="saturday",
                    termin_ids=[t.id],
                    message=msg,
                    datum=t.datum,
                    zeit_von=t.start_zeit,
                    zeit_bis=t.get_end_time(),
                    raum=raum.name if raum else "",
                    lva=lva.name if lva else t.lva_id,
                    gruppe=t.gruppe.name if t.gruppe else ""
                ))
        return warnings

    def detect_sunday_warning(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect warnings for Termine that fall on a Sunday"""
        warnings = []
        for t in termine:
            if not t.datum:
                continue
            if t.datum.weekday() == 6:  # Sunday
                lva = next((l for l in self.lvas if l.id == t.lva_id), None)
                raum = next((r for r in self.raeume if r.id == t.raum_id), None)
                msg = self._render_message(settings)
                warnings.append(ConflictIssue(
                    severity="warning",
                    category="sunday",
                    termin_ids=[t.id],
                    message=msg,
                    datum=t.datum,
                    zeit_von=t.start_zeit,
                    zeit_bis=t.get_end_time(),
                    raum=raum.name if raum else "",
                    lva=lva.name if lva else t.lva_id,
                    gruppe=t.gruppe.name if t.gruppe else ""
                ))
        return warnings
    
    def _create_conflict(self, category: str, t1: Termin, t2: Termin, settings=None) -> ConflictIssue:
        """Create a conflict issue for two overlapping Termine"""
        lva1 = next((l for l in self.lvas if l.id == t1.lva_id), None)
        lva2 = next((l for l in self.lvas if l.id == t2.lva_id), None)
        raum1 = next((r for r in self.raeume if r.id == t1.raum_id), None)
        raum2 = next((r for r in self.raeume if r.id == t2.raum_id), None)

        lva1_name = lva1.name if lva1 else t1.lva_id
        lva2_name = lva2.name if lva2 else t2.lva_id
        raum1_name = raum1.name if raum1 else ""
        raum2_name = raum2.name if raum2 else ""

        # Use earlier time as reference
        zeit_von = min(t1.start_zeit, t2.start_zeit) if t1.start_zeit and t2.start_zeit else None
        end1 = t1.get_end_time()
        end2 = t2.get_end_time()
        zeit_bis = max(end1, end2) if end1 and end2 else None

        msg = self._render_message(
            settings,
            {
                "left_lva": lva1_name,
                "left_room": raum1_name,
                "right_lva": lva2_name,
                "right_room": raum2_name,
            },
        )

        return ConflictIssue(
            severity="conflict",
            category=category,
            termin_ids=[t1.id, t2.id],
            message=msg,
            datum=t1.datum,  # Both should have same date
            zeit_von=zeit_von,
            zeit_bis=zeit_bis,
            raum=raum1_name if category == "room" else f"{raum1_name}, {raum2_name}",
            lva=f"{lva1_name}, {lva2_name}" if lva1_name != lva2_name else lva1_name,
            gruppe=""  # Could be enhanced to show both groups
        )

# Separate capacity warning for Übung
    def detect_capacity_warning_uebung(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        warnings = []
        percent = settings.get('min_capacity_percent', 100) if settings else 100
        event_type = settings.get('event_type', 'uebung') if settings else 'uebung'
        for t in termine:
            if not self.is_assigned(t):
                continue
            raum = getattr(t, 'raum', None) or next((r for r in self.raeume if r.id == t.raum_id), None)
            gruppe = getattr(t, 'gruppe', None)
            lva = next((l for l in self.lvas if l.id == t.lva_id), None)
            typ = getattr(t, 'typ', None) or (lva.typ if lva and hasattr(lva, 'typ') else None)
            if raum and gruppe and (typ == event_type):
                required = int(gruppe.groesse * percent / 100)
                if raum.kapazitaet < required:
                    msg = self._render_message(
                        settings,
                        {
                            "group_size": gruppe.groesse,
                            "percent": percent,
                            "required": required,
                            "room_capacity": raum.kapazitaet,
                        },
                    )
                    warnings.append(ConflictIssue(
                        severity="warning",
                        category="Kapazität Übung",
                        termin_ids=[t.id],
                        message=msg,
                        datum=t.datum,
                        zeit_von=t.start_zeit,
                        zeit_bis=t.get_end_time(),
                        raum=raum.name,
                        lva=lva.name if lva else t.lva_id,
                        gruppe=gruppe.name
                    ))
        return warnings


    def detect_capacity_warning_vorlesung(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        warnings = []
        percent = settings.get('min_capacity_percent', 60) if settings else 60
        event_type = settings.get('event_type', 'vorlesung') if settings else 'vorlesung'
        for t in termine:
            if not self.is_assigned(t):
                continue
            raum = getattr(t, 'raum', None) or next((r for r in self.raeume if r.id == t.raum_id), None)
            gruppe = getattr(t, 'gruppe', None)
            lva = next((l for l in self.lvas if l.id == t.lva_id), None)
            typ = getattr(t, 'typ', None) or (lva.typ if lva and hasattr(lva, 'typ') else None)
            if raum and gruppe and (typ == event_type):
                required = int(gruppe.groesse * percent / 100)
                if raum.kapazitaet < required:
                    msg = self._render_message(
                        settings,
                        {
                            "group_size": gruppe.groesse,
                            "percent": percent,
                            "required": required,
                            "room_capacity": raum.kapazitaet,
                        },
                    )
                    warnings.append(ConflictIssue(
                        severity="warning",
                        category="Kapazität Vorlesung",
                        termin_ids=[t.id],
                        message=msg,
                        datum=t.datum,
                        zeit_von=t.start_zeit,
                        zeit_bis=t.get_end_time(),
                        raum=raum.name,
                        lva=lva.name if lva else t.lva_id,
                        gruppe=gruppe.name
                    ))
        return warnings

    def _load_free_days_map(self, conflict_settings_path: Optional[str]) -> Dict[date, set[str]]:
        if self.data_dir:
            free_path = self.data_dir / "freie_tage.json"
        elif conflict_settings_path:
            free_path = Path(conflict_settings_path).resolve().parent / "freie_tage.json"
        else:
            free_path = Path("data") / "freie_tage.json"

        if not free_path.exists():
            return {}

        try:
            payload = json.loads(free_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}

        out: Dict[date, set[str]] = {}
        for item in payload.get("freie_tage", []):
            raw_type = str(item.get("typ", "")).strip().lower()
            if "feiertag" in raw_type:
                day_type = "feiertag"
            elif "vorlesungsfrei" in raw_type:
                day_type = "vorlesungsfrei"
            else:
                continue

            single_raw = str(item.get("datum", "")).strip()
            if single_raw:
                d = self._parse_iso_date(single_raw)
                if d is not None:
                    out.setdefault(d, set()).add(day_type)
                continue

            start_raw = str(item.get("von_datum", "")).strip()
            end_raw = str(item.get("bis_datum", "")).strip()
            d0 = self._parse_iso_date(start_raw)
            d1 = self._parse_iso_date(end_raw)
            if d0 is None or d1 is None or d1 < d0:
                continue

            cur = d0
            while cur <= d1:
                out.setdefault(cur, set()).add(day_type)
                cur += timedelta(days=1)

        return out

    def _parse_iso_date(self, raw: str) -> Optional[date]:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            return None
