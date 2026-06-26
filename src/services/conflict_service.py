from datetime import date, time, datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import re
from dataclasses import replace
from pathlib import Path
from ..core.models import Termin, Lehrveranstaltung, Raum, ConflictIssue
from .conflict_labels import conflict_category_label
from .termin_occurrence_service import expand_termine, source_termin_id
from .app_config_service import (
    ensure_user_config_file,
    load_default_config,
    save_user_config,
    user_config_path,
)


DEFAULT_CONFLICTS_PATH = user_config_path("konflikte.json")


def preview_conflict_issues(
    termine: List[Termin],
    lvas: List[Lehrveranstaltung],
    raeume: List[Raum],
    termin_id: str,
    target_date: Optional[date],
    start_mins: int,
    default_slot_mins: int,
    target_raum_id: Optional[str] = None,
    use_dragged_room: bool = False,
    conflict_settings_path: Optional[str] = None,
    data_dir: str | Path | None = None,
) -> List[ConflictIssue]:
    """
    Simulates dropping a Termin at a new position to show real-time conflict feedback during dragging.
    It creates a temporary copy of the appointments with the dragged Termin moved to the proposed date, time, and room, then runs the normal ConflictDetector
    Only real conflicts involving that dragged Termin are returned, warnings are ignored.
    """
    if not target_date:
        return []

   
    expanded = expand_termine(termine)
    dragged = next((t for t in expanded if str(t.id) == str(termin_id)), None)
    if not dragged:
        source_id = source_termin_id(termin_id)
        dragged = next((t for t in termine if str(t.id) == source_id), None)
    if not dragged:
        return []

  
    slot_mins = max(1, int(default_slot_mins or 30))
    start_h = max(0, start_mins) // 60
    start_m = max(0, start_mins) % 60
    if start_h > 23:
        return []
    target_start = time(hour=start_h, minute=start_m)

   
    moved_room_id = dragged.raum_id if use_dragged_room else (target_raum_id or dragged.raum_id)
    moved_dragged = replace(
        dragged,
        datum=target_date,
        start_zeit=target_start,
        raum_id=moved_room_id,
        duration=(dragged.duration if dragged.duration > 0 else slot_mins),
    )

  
    replaced = False
    simulated = []
    for t in expanded:
        if str(t.id) == str(dragged.id):
            simulated.append(moved_dragged)
            replaced = True
        else:
            simulated.append(t)
    if not replaced:
        simulated.append(moved_dragged)

    detector = ConflictDetector(
        lvas=lvas,
        raeume=raeume,
        conflict_settings_path=conflict_settings_path,
        data_dir=data_dir,
    )
    issues = detector.detect_all(simulated)
    return [
        issue
        for issue in issues
        if (
            issue.severity == "conflict"
            and any(
                source_termin_id(tid) == source_termin_id(termin_id)
                for tid in issue.termin_ids
            )
        )
    ]


def preview_conflict_summary(
    termine: List[Termin],
    lvas: List[Lehrveranstaltung],
    raeume: List[Raum],
    termin_id: str,
    target_date: Optional[date],
    start_mins: int,
    default_slot_mins: int,
    target_raum_id: Optional[str] = None,
    use_dragged_room: bool = False,
    conflict_settings_path: Optional[str] = None,
    data_dir: str | Path | None = None,
) -> str:
    issues = preview_conflict_issues(
        termine=termine,
        lvas=lvas,
        raeume=raeume,
        termin_id=termin_id,
        target_date=target_date,
        start_mins=start_mins,
        default_slot_mins=default_slot_mins,
        target_raum_id=target_raum_id,
        use_dragged_room=use_dragged_room,
        conflict_settings_path=conflict_settings_path,
        data_dir=data_dir,
    )
    labels = []
    seen = set()
    for issue in issues:
        category = str(getattr(issue, "category", "") or "").strip()
        label = conflict_category_label(category) or "Konflikt"
        if label not in seen:
            seen.add(label)
            labels.append(label)
    return ", ".join(labels)

def load_conflicts(path=None):
    target = Path(path) if path else ensure_user_config_file("konflikte.json")
    try:
        conflicts = json.loads(target.read_text(encoding="utf-8-sig"))
    except Exception:
        conflicts = []
    if path:
        return conflicts if isinstance(conflicts, list) else []
    return _merge_default_conflicts(conflicts)


def _merge_default_conflicts(conflicts) -> list:
    if not isinstance(conflicts, list):
        conflicts = []

    defaults = load_default_config("konflikte.json", [])
    if not isinstance(defaults, list):
        defaults = []

    user_by_key = {
        str(item.get("key")): item
        for item in conflicts
        if isinstance(item, dict) and item.get("key")
    }
    merged = []
    seen_keys = set()
    for default_item in defaults:
        if not isinstance(default_item, dict):
            continue
        key = str(default_item.get("key", ""))
        if not key:
            continue
        item = dict(default_item)
        item.update(user_by_key.get(key, {}))
        if key == "lecturer_conflict":
            item = _migrate_lecturer_conflict_label(item)
        merged.append(item)
        seen_keys.add(key)

    for item in conflicts:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", ""))
        if key and key not in seen_keys:
            merged.append(item)
    return merged


def _migrate_lecturer_conflict_label(item: dict) -> dict:
    migrated = dict(item)
    if str(migrated.get("name", "")).strip() == "Vortragenden-Konflikt":
        migrated["name"] = "Lehrpersonen-Konflikt"
    old_description = "Zwei Termine unterschiedlicher LVAs mit demselben Dozenten, am selben Tag, mit sich überschneidenden Zeiten."
    if str(migrated.get("description", "")).strip() == old_description:
        migrated["description"] = (
            "Zwei nicht-gruppierte Termine unterschiedlicher LVAs mit derselben hinterlegten Lehrperson, "
            "am selben Tag, mit sich überschneidenden Zeiten."
        )
    return migrated

def save_conflicts(conflicts, path=None):
    try:
        if path:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(conflicts, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
            tmp.replace(target)
        else:
            save_user_config("konflikte.json", conflicts, indent=4)
    except Exception:
        pass


class ConflictDetector:
    """
    Detects scheduling conflicts and warnings across a list of Termine.

    Rules are loaded from konflikte.json and can be individually enabled/disabled.
    Each rule maps to a dedicated detect_* method that returns ConflictIssue objects.
    Free-day data (Feiertage, Vorlesungsfreie Tage) is read from freie_tage.json and
    pre-processed into an in-memory date map for efficient per-Termin lookups.
    """

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
        self._lva_by_id = {str(lva.id): lva for lva in lvas}
        self._raum_by_id = {str(raum.id): raum for raum in raeume}
        self._studiensemester_names = self._load_studiensemester_names()
        self._free_days_by_date = self._load_free_days_map(conflict_settings_path)
    
    def is_assigned(self, termin: Termin) -> bool:
        return termin.datum is not None and termin.start_zeit is not None
    
    def times_overlap(self, t1: Termin, t2: Termin) -> bool:
        """
        Return True if the two Termine overlap in time using half-open interval logic.

        Two intervals [s1, e1) and [s2, e2) overlap iff s1 < e2 AND s2 < e1.
        A Termin without a start time or with zero/negative duration cannot overlap.
        """
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
        """
        Build a conflict message from a settings entry.

        The konflikte.json items may contain:
        - 'name': short label shown as the message prefix
        - 'message_template': a str.format-style template with named placeholders
          (e.g. "{left_lva} ({left_room}) ↔ {right_lva} ({right_room})")
        - 'description': fallback text when no template is present

        Falls ein Template nicht gerendert werden kann, wird der Rohtext verwendet,
        damit eine fehlerhafte Konflikt-Konfiguration die Erkennung nicht stoppt.
        """
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
        termine = expand_termine(termine)
        assigned = [t for t in termine if self.is_assigned(t)]

        # Tuple format: (settings_key, detector_fn, assigned_only)
        rules = [
            ("room_conflict", self.detect_room_conflicts, True),
            ("group_conflict", self.detect_group_conflicts, True),
            ("lecturer_conflict", self.detect_lecturer_conflicts, True),
            ("study_semester_warning", self.detect_study_semester_warnings, True),
            ("holiday_conflict", self.detect_holiday_conflicts, True),
            ("lecture_free_conflict", self.detect_lecture_free_conflicts, True),
            ("incomplete_warning", self.detect_incomplete_warnings, False),
            ("duration_warning", self.detect_duration_warnings, False),
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
            if t.datum is None:
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
                    datum=t.datum,
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
        for terms in by_room_date.values():
            for i, t1 in enumerate(terms):
                for t2 in terms[i+1:]:
                    if self.times_overlap(t1, t2):
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
                        conflicts.append(self._create_conflict(
                            "group", t1, t2, settings
                        ))
        return conflicts
    
    def detect_lecturer_conflicts(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect lecturer conflicts (same lecturer, date, overlapping time). Uses settings if provided."""
        conflicts = []
        by_lecturer_date: Dict[Tuple[str, date], List[Termin]] = {}
        for t in termine:
            if not t.datum:
                continue
            lva = next((l for l in self.lvas if l.id == t.lva_id), None)
            if not lva or not lva.vortragende:
                continue
            lecturer_key = self._lecturer_key(lva)
            if not lecturer_key:
                continue
            key = (lecturer_key, t.datum)
            by_lecturer_date.setdefault(key, []).append(t)
        for terms in by_lecturer_date.values():
            for i, t1 in enumerate(terms):
                for t2 in terms[i+1:]:
                    if self._are_lecturer_alternatives(t1, t2):
                        continue
                    if self.times_overlap(t1, t2):
                        conflicts.append(self._create_conflict(
                            "lecturer", t1, t2, settings
                        ))
        return conflicts

    def detect_study_semester_warnings(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Warn when overlapping Termine belong to LVAs with the same study-plan assignment."""
        warnings: List[ConflictIssue] = []
        by_date: Dict[date, List[Termin]] = {}
        for t in termine:
            if not t.datum:
                continue
            by_date.setdefault(t.datum, []).append(t)

        for terms in by_date.values():
            for i, t1 in enumerate(terms):
                for t2 in terms[i + 1:]:
                    if source_termin_id(t1.id) == source_termin_id(t2.id):
                        continue
                    if not self.times_overlap(t1, t2):
                        continue
                    if self._are_study_plan_alternatives(t1, t2):
                        continue

                    lva1 = self._lva_by_id.get(str(t1.lva_id))
                    lva2 = self._lva_by_id.get(str(t2.lva_id))
                    if not lva1 or not lva2:
                        continue

                    studienrichtung1 = str(getattr(lva1, "studienrichtung", "")).strip()
                    studienrichtung2 = str(getattr(lva2, "studienrichtung", "")).strip()
                    if not studienrichtung1 or studienrichtung1 != studienrichtung2:
                        continue

                    shared_semester = self._shared_studiensemester(lva1, lva2)
                    if not shared_semester:
                        continue

                    raum1 = self._raum_by_id.get(str(t1.raum_id))
                    raum2 = self._raum_by_id.get(str(t2.raum_id))
                    lva1_name = lva1.name if lva1 else t1.lva_id
                    lva2_name = lva2.name if lva2 else t2.lva_id
                    raum1_name = raum1.name if raum1 else ""
                    raum2_name = raum2.name if raum2 else ""
                    semester_label = " / ".join(
                        self._studiensemester_names.get(sem_id, sem_id)
                        for sem_id in shared_semester
                    )

                    msg = self._render_message(
                        settings,
                        {
                            "left_lva": lva1_name,
                            "left_room": raum1_name,
                            "right_lva": lva2_name,
                            "right_room": raum2_name,
                            "studienrichtung": studienrichtung1,
                            "studiensemester": semester_label,
                        },
                    )

                    end1 = t1.get_end_time()
                    end2 = t2.get_end_time()
                    warnings.append(ConflictIssue(
                        severity="warning",
                        category="semester",
                        termin_ids=[t1.id, t2.id],
                        message=msg,
                        datum=t1.datum,
                        zeit_von=min(t1.start_zeit, t2.start_zeit) if t1.start_zeit and t2.start_zeit else None,
                        zeit_bis=max(end1, end2) if end1 and end2 else None,
                        raum=", ".join(part for part in (raum1_name, raum2_name) if part),
                        lva=f"{lva1_name}, {lva2_name}" if lva1_name != lva2_name else lva1_name,
                        gruppe="",
                    ))
        return warnings

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
        min_minutes = (settings or {}).get("min_minutes", 30)
        max_minutes = (settings or {}).get("max_minutes", 240)
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

    def _shared_studiensemester(self, lva1: Lehrveranstaltung, lva2: Lehrveranstaltung) -> List[str]:
        left = [
            str(item).strip()
            for item in (getattr(lva1, "studiensemester", []) or [])
            if str(item).strip()
        ]
        right = {
            str(item).strip()
            for item in (getattr(lva2, "studiensemester", []) or [])
            if str(item).strip()
        }
        seen = set()
        shared: List[str] = []
        for semester_id in left:
            if semester_id in right and semester_id not in seen:
                seen.add(semester_id)
                shared.append(semester_id)
        return shared

    def _both_have_group_names(self, t1: Termin, t2: Termin) -> bool:
        group1 = str(getattr(getattr(t1, "gruppe", None), "name", "") or "").strip()
        group2 = str(getattr(getattr(t2, "gruppe", None), "name", "") or "").strip()
        return bool(group1 and group2)

    def _lecturer_key(self, lva: Lehrveranstaltung) -> str:
        lecturer = getattr(lva, "vortragende", None)
        if not lecturer:
            return ""
        email = str(getattr(lecturer, "email", "") or "").strip().casefold()
        if email:
            return f"mail:{email}"
        name = str(getattr(lecturer, "name", "") or "").strip().casefold()
        return f"name:{name}" if name else ""

    def is_group_term(self, termin: Termin) -> bool:
        group_obj = getattr(termin, "gruppe", None)
        group_name = str(getattr(group_obj, "name", "") or "").strip()
        group_id = str(getattr(termin, "gruppe_id", "") or "").strip()
        group_label = str(getattr(termin, "gruppenbezeichnung", "") or "").strip()
        if group_name or group_id or group_label:
            return True

        for field_name in ("name", "notiz", "besprechungshinweis"):
            text = str(getattr(termin, field_name, "") or "")
            if re.search(r"\bgr(?:uppe|\.)?\s*[A-Z0-9]", text, re.IGNORECASE):
                return True
        return False

    def _are_study_plan_alternatives(self, t1: Termin, t2: Termin) -> bool:
        if self.is_group_term(t1) or self.is_group_term(t2):
            return True

        if str(t1.lva_id) != str(t2.lva_id):
            return False

        group1 = str(getattr(getattr(t1, "gruppe", None), "name", "") or "").strip()
        group2 = str(getattr(getattr(t2, "gruppe", None), "name", "") or "").strip()
        if group1 and group2:
            return group1 != group2

        return True

    def _are_lecturer_alternatives(self, t1: Termin, t2: Termin) -> bool:
        if str(t1.lva_id) == str(t2.lva_id):
            return True
        return self.is_group_term(t1) or self.is_group_term(t2)



    def _capacity_event_types(self, settings, fallback: str) -> set[str]:
        settings = settings or {}
        raw = settings.get("event_types")
        if isinstance(raw, list):
            values = raw
        else:
            values = [settings.get("event_type", fallback)]
        return {str(value).strip().upper() for value in values if str(value).strip()}


# Separate capacity warning for Übung
    def detect_capacity_warning_uebung(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        warnings = []
        percent = settings.get('min_capacity_percent', 100) if settings else 100
        event_types = self._capacity_event_types(settings, 'UE')
        for t in termine:
            if not self.is_assigned(t):
                continue
            raum = getattr(t, 'raum', None) or next((r for r in self.raeume if r.id == t.raum_id), None)
            gruppe = getattr(t, 'gruppe', None)
            lva = next((l for l in self.lvas if l.id == t.lva_id), None)
            if raum and gruppe and (str(t.typ or "").strip().upper() in event_types):
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
        event_types = self._capacity_event_types(settings, 'VO')
        for t in termine:
            if not self.is_assigned(t):
                continue
            raum = getattr(t, 'raum', None) or next((r for r in self.raeume if r.id == t.raum_id), None)
            gruppe = getattr(t, 'gruppe', None)
            lva = next((l for l in self.lvas if l.id == t.lva_id), None)
            if raum and gruppe and (str(t.typ or "").strip().upper() in event_types):
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

    def _load_studiensemester_names(self) -> Dict[str, str]:
        path = Path(__file__).resolve().parents[1] / "studiensemester.json"
        if not path.exists():
            return {}

        try:
            obj = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}

        names: Dict[str, str] = {}
        for item in obj.get("studiensemester", []):
            if not isinstance(item, dict):
                continue
            semester_id = str(item.get("id", "")).strip()
            name = str(item.get("name", "")).strip()
            if semester_id:
                names[semester_id] = name or semester_id
        return names

    def _parse_iso_date(self, raw: str) -> Optional[date]:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            return None
