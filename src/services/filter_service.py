from typing import List, Optional

from ..core.models import Termin
from datetime import date as _date, time as _time


def filter_termine(
    termine: List[Termin],

    semester_id: Optional[str] = None,
    raum_id: Optional[str] = None,
    lva_id: Optional[str] = None,
    typ: Optional[str] = None,
    dozent: Optional[str] = None,
    datum: Optional[str] = None,  # YYYY-MM-DD
    lva_dict: Optional[dict] = None,  # Mapping lva_id -> LVA-Objekt
) -> List[Termin]:
    out = termine

    if semester_id:
        out = [t for t in out if getattr(t, 'semester_id', None) == semester_id]
    if raum_id:
        out = [t for t in out if t.raum_id == raum_id]
    if lva_id:
        out = [t for t in out if t.lva_id == lva_id]
    if typ:
        out = [t for t in out if t.typ == typ]
    if dozent:
        if lva_dict is None:
            raise ValueError("Für den Dozent-Filter muss lva_dict (lva_id → LVA-Objekt) übergeben werden.")
        out = [t for t in out if t.lva_id in lva_dict and getattr(lva_dict[t.lva_id].vortragende, 'name', None) == dozent]
    if datum:
        out = [t for t in out if t.datum is not None and t.datum.isoformat() == datum]

    # return sorted(out, key=lambda t: (t.datum, t.zeit.von, t.zeit.bis))
    def _sort_key(t: Termin):
        # unassigned first
        unassigned = (t.datum is None)

        d = t.datum or _date.min
        von = (t.start_zeit if t.start_zeit else _time.min)

        # (False, ...) comes before (True, ...) so invert:
        return (not unassigned, d, von, t.id)

    return sorted(out, key=_sort_key)
