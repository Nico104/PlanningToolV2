from typing import List, Optional

from ..core.models import Termin
from datetime import date as _date, time as _time


def filter_termine(
    termine: List[Termin],

    semester_id: Optional[str] = None,
    studiensemester: Optional[str] = None,
    raum_id: Optional[str] = None,
    lva_id: Optional[str] = None,
    typ: Optional[str] = None,
    dozent: Optional[str] = None,
    studienrichtung: Optional[str] = None,
    zu_besprechen: bool = False,
    datum: Optional[str] = None,
    lva_dict: Optional[dict] = None,
) -> List[Termin]:
    """
    Filter a list of Termine by any combination of criteria and return them sorted.

    Filters are applied sequentially (each narrows the previous result).
    All filter parameters are optional; omitting one means 'no restriction'.

    Semester filter (semester_id):
        Matches only Termine whose own semester_id field matches the given value (e.g., "testsem", "ws24").
        This is for filtering by academic term/year.

    Studiensemester filter (studiensemester):
        Matches only Termine whose associated LVA (course) lists the given value (e.g., "sem6", "qs4")
        in its studiensemester attribute.
        Requires lva_dict; raises ValueError if it is missing.

    Dozent filter (dozent):
        Resolves the lecturer name via lva_dict (Termin -> LVA -> vortragende.name).
        Requires lva_dict; raises ValueError if it is missing.

    Studienrichtung filter (studienrichtung):
        Matches Termine through the Studienrichtung stored on their associated LVA.
        Requires lva_dict; raises ValueError if it is missing.

    Sort order:
        Unassigned Termine (datum=None) are placed first so they are always visible
        at the top of the Termine dock regardless of date filters. Assigned Termine
        are sorted by (date, start_time, id).
    """
    out = termine

    if semester_id:
        # Only match Termine whose semester_id matches the filter
        out = [t for t in out if getattr(t, 'semester_id', None) == semester_id]
    if studiensemester:
        # Only match Termine whose LVA's Studiensemester list contains the filter value (e.g., "sem6", "qs4", ...)
        if lva_dict is None:
            raise ValueError("Für den Studiensemester-Filter muss lva_dict (lva_id → LVA-Objekt) übergeben werden.")
        out = [
            t for t in out
            if studiensemester in (getattr(lva_dict.get(t.lva_id), 'studiensemester', []) or [])
        ]
    if raum_id:
        out = [t for t in out if t.raum_id == raum_id]
    if lva_id:
        out = [t for t in out if t.lva_id == lva_id]
    if typ:
        out = [t for t in out if t.typ == typ]
    if studienrichtung:
        if lva_dict is None:
            raise ValueError("Für den Studienrichtung-Filter muss lva_dict (lva_id → LVA-Objekt) übergeben werden.")
        out = [
            t for t in out
            if t.lva_id in lva_dict and getattr(lva_dict[t.lva_id], "studienrichtung", None) == studienrichtung
        ]
    if dozent:
        if lva_dict is None:
            raise ValueError("Für den Dozent-Filter muss lva_dict (lva_id → LVA-Objekt) übergeben werden.")
        out = [t for t in out if t.lva_id in lva_dict and getattr(lva_dict[t.lva_id].vortragende, 'name', None) == dozent]
    if zu_besprechen:
        out = [t for t in out if bool(getattr(t, "zu_besprechen", False))]
    if datum:
        out = [t for t in out if t.datum is not None and t.datum.isoformat() == datum]

    
    def _sort_key(t: Termin):
        # unassigned first
        unassigned = (t.datum is None)

        d = t.datum or _date.min
        von = (t.start_zeit if t.start_zeit else _time.min)

        # (False, ...) comes before (True, ...) so invert: (not)
        return (not unassigned, d, von, t.id)

    return sorted(out, key=_sort_key)
