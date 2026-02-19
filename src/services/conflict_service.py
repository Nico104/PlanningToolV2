from datetime import date, time
from typing import List, Dict, Optional, Tuple, Callable
import os
import json
from ..core.models import Termin, Lehrveranstaltung, Raum, Semester, ConflictIssue


def load_conflicts(path=None):
    path = path or "data/konflikte.json"
    abs_path = os.path.abspath(path)
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[conflict_service] Fehler beim Laden: {e}")
        return []

def save_conflicts(conflicts, path=None):
    path = path or "data/konflikte.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(conflicts, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[conflict_service] Fehler beim Speichern: {e}")


UNASSIGNED_DATE = date(2026, 1, 1)


class ConflictDetector:
    def __init__(self, 
                 lvas: List[Lehrveranstaltung],
                 raeume: List[Raum],
                 conflict_settings_path: str = None):
        self.lvas = lvas
        self.raeume = raeume
        # Load conflict settings (konflikte.json)
        self.conflict_settings = {}
        settings = load_conflicts(conflict_settings_path)
        for entry in settings:
            key = entry.get("key")
            if key:
                self.conflict_settings[key] = entry
    
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
        
        # startA < endB AND startB < endA
        return (t1.start_zeit < end2) and (t2.start_zeit < end1)
    
    
    def detect_all(self, termine: List[Termin]) -> List[ConflictIssue]:
        """Detect all conflicts and warnings in the given Termine list, respecting settings from konflikte.json."""
        issues = []
        assigned = [t for t in termine if self.is_assigned(t)]

        # Map method names to settings keys
        method_to_key = {
            'detect_room_conflicts': 'room_conflict',
            'detect_group_conflicts': 'group_conflict',
            'detect_lecturer_conflicts': 'lecturer_conflict',
            'detect_incomplete_warnings': 'incomplete_warning',
            'detect_outside_period_warnings': 'outside_period_warning',
            'detect_capacity_warnings': 'capacity_warning',
            'detect_duration_warnings': 'duration_warning',
            'detect_weekend_warnings': 'weekend_warning',
        }

        # Auto-discover all detection methods
        for method_name in dir(self):
            if method_name.startswith('detect_') and (
                method_name.endswith('_conflicts') or method_name.endswith('_warnings')
            ):
                key = method_to_key.get(method_name)
                settings = self.conflict_settings.get(key, {}) if key else {}
                enabled = settings.get('enabled', True)
                if not enabled:
                    continue
                method = getattr(self, method_name)
                if callable(method):
                    # Pass appropriate termine list based on method name
                    # Warnings can check all termine, conflicts typically check assigned only
                    if '_warnings' in method_name:
                        detected = method(termine, settings)
                    else:
                        detected = method(assigned, settings)
                    if detected:
                        issues.extend(detected)
        return issues
    
    
    
    def detect_incomplete_warnings(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect warnings for incomplete or unassigned Termine. Uses settings if provided."""
        warnings = []
        for t in termine:
            problems = []
            # Check for missing/unassigned date
            if t.datum is None or t.datum == UNASSIGNED_DATE:
                problems.append("kein Datum")
            # Check for missing time
            if t.start_zeit is None:
                problems.append("keine Startzeit")
            # Check for missing/invalid duration
            if t.duration <= 0:
                problems.append("keine Dauer")
            # Check for missing room
            if not t.raum_id or t.raum_id.strip() == "":
                problems.append("kein Raum")
            if problems:
                lva = next((l for l in self.lvas if l.id == t.lva_id), None)
                raum = next((r for r in self.raeume if r.id == t.raum_id), None)
                msg = f"Unvollständiger Termin: {', '.join(problems)}"
                # Optionally use settings['description'] or other details
                if settings and settings.get('description'):
                    msg += f" ({settings['description']})"
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
                            msg_prefix = "Raum-Konflikt"
                            if settings and settings.get('description'):
                                msg_prefix += f" ({settings['description']})"
                            conflicts.append(self._create_conflict(
                                "room", t1, t2, msg_prefix
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
                            msg_prefix = "Gruppen-Konflikt"
                            if settings and settings.get('description'):
                                msg_prefix += f" ({settings['description']})"
                            conflicts.append(self._create_conflict(
                                "group", t1, t2, msg_prefix
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
                            msg_prefix = "Vortragenden-Konflikt"
                            if settings and settings.get('description'):
                                msg_prefix += f" ({settings['description']})"
                            conflicts.append(self._create_conflict(
                                "lecturer", t1, t2, msg_prefix
                            ))
        return conflicts
    
    
    def detect_duration_warnings(self, termine: List[Termin], settings=None) -> List[ConflictIssue]:
        """Detect warnings for Termine that are unusually short (<30min) or long (>4h)."""
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
                msg = f"Ungewöhnliche Dauer: {duration} Minuten."
                if settings and settings.get('description'):
                    msg += f" ({settings['description']})"
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
        """Detect warnings for Termine that fall on a weekend (Saturday or Sunday)."""
        warnings = []
        for t in termine:
            if not t.datum:
                continue
            if t.datum.weekday() >= 5:  # 5=Saturday, 6=Sunday
                lva = next((l for l in self.lvas if l.id == t.lva_id), None)
                raum = next((r for r in self.raeume if r.id == t.raum_id), None)
                msg = "Termin liegt auf einem Wochenende."
                if settings and settings.get('description'):
                    msg += f" ({settings['description']})"
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
        """Detect warnings for Termine that fall on a Saturday."""
        warnings = []
        for t in termine:
            if not t.datum:
                continue
            if t.datum.weekday() == 5:  # Saturday
                lva = next((l for l in self.lvas if l.id == t.lva_id), None)
                raum = next((r for r in self.raeume if r.id == t.raum_id), None)
                msg = "Termin liegt auf einem Samstag."
                if settings and settings.get('description'):
                    msg += f" ({settings['description']})"
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
        """Detect warnings for Termine that fall on a Sunday."""
        warnings = []
        for t in termine:
            if not t.datum:
                continue
            if t.datum.weekday() == 6:  # Sunday
                lva = next((l for l in self.lvas if l.id == t.lva_id), None)
                raum = next((r for r in self.raeume if r.id == t.raum_id), None)
                msg = "Termin liegt auf einem Sonntag."
                if settings and settings.get('description'):
                    msg += f" ({settings['description']})"
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
    
    def _create_conflict(self, category: str, t1: Termin, t2: Termin, msg_prefix: str) -> ConflictIssue:
        """Create a conflict issue for two overlapping Termine."""
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

        msg = f"{msg_prefix}: {lva1_name} ({raum1_name}) ↔ {lva2_name} ({raum2_name})"

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
                    msg = f"Übung: Gruppe ({gruppe.groesse} Personen) benötigt {percent}% Platz: {required}, Raumkapazität: {raum.kapazitaet}"
                    if settings and settings.get('description'):
                        msg += f" ({settings['description']})"
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

# Separate capacity warning for Vorlesung
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
                    msg = f"Vorlesung: Gruppe ({gruppe.groesse} Personen) benötigt {percent}% Platz: {required}, Raumkapazität: {raum.kapazitaet}"
                    if settings and settings.get('description'):
                        msg += f" ({settings['description']})"
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