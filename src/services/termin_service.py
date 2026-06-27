from datetime import date, datetime, time, timedelta
from typing import List, Optional, Dict, Tuple

from ..core.models import Termin, Zeitfenster
from .termin_occurrence_service import expand_termine


class TerminService:
    """Service for Termin-related calculations, such as finding free time slots in a room"""

    def __init__(self, settings: Dict):
        self.settings = settings

    @staticmethod
    def _to_dt(d: date, t: time) -> datetime:
        return datetime(d.year, d.month, d.day, t.hour, t.minute)

    def find_free_slots_in_room(
        self,
        termine: List[Termin],
        raum_id: str,
        datum: date,
        duration_minutes: int,
        semester_id: Optional[str] = None,
    ) -> List[Zeitfenster]:
        """
        Return all free time windows in a room on a given date that fit the requested duration.

        Algorithm:

        1. Collect busy intervals.
        Filter Termine to those matching the room and date, then convert each one
        to a (start_datetime, end_datetime) interval. Sort by start time.

        2. Merge overlapping busy intervals.
        Go through the sorted intervals. If the next interval starts after the
        current merged block ends, start a new block. Otherwise, extend the current
        block's end to cover the overlap.

        3. Adjust free periods to the time grid and filter by minimum duration.
        Find the gaps between the merged busy periods.
        - The gap start is rounded up to the next grid line, so the returned slot
            always starts on a valid time.
        - The gap end is rounded down to the previous grid line.
        After adjusting, only gaps that are at least as long as the requested duration
        are returned. This ensures the returned Zeitfenster fit the visual grid and
        are long enough for the event.
        """
        day_start = datetime.strptime(self.settings.get("day_start", "08:00"), "%H:%M").time()
        day_end = datetime.strptime(self.settings.get("day_end", "18:00"), "%H:%M").time()

        # relevante Termine
        expanded_termine = expand_termine(termine)
        rel = [
            t
            for t in expanded_termine
            if t.raum_id == raum_id
            and t.datum == datum
            and t.start_zeit is not None
            and t.duration > 0
            and (semester_id is None or t.semester_id == semester_id)
        ]
        rel = sorted(rel, key=lambda x: x.start_zeit)

        start_dt = self._to_dt(datum, day_start)
        end_dt = self._to_dt(datum, day_end)
        slot = timedelta(minutes=int(self.settings.get("time_slot_minutes", 15)))
        want = timedelta(minutes=duration_minutes)

        # belegte Intervalle als dt
        busy: List[Tuple[datetime, datetime]] = [
            (self._to_dt(datum, t.start_zeit), self._to_dt(datum, t.get_end_time() or t.start_zeit))
            for t in rel
        ]

        # Merge busy
        merged_tmp = []
        for b in busy:
            if not merged_tmp or b[0] > merged_tmp[-1][1]:
                merged_tmp.append(list(b))  # add new interval
            else:
                merged_tmp[-1][1] = max(merged_tmp[-1][1], b[1])
        # convert it to a list of tuples from a list of lists because tuples are not mutable
        merged: List[Tuple[datetime, datetime]] = [(a, b) for a, b in merged_tmp]

        # Erzeuge freie Fenster
        free: List[Tuple[datetime, datetime]] = []
        cursor = start_dt
        for a, b in merged:
            if a > cursor:
                free.append((cursor, a))
            cursor = max(cursor, b)
        if cursor < end_dt:
            free.append((cursor, end_dt))

        # Rastere in Slots und filtere nach Mindestdauer
        out: List[Zeitfenster] = []
        for a, b in free:
            # runden auf Slot-Raster nach oben/unten
            def ceil_to_slot(dt: datetime) -> datetime:
                minutes = dt.hour * 60 + dt.minute
                s = int(slot.total_seconds() // 60)
                m = ((minutes + s - 1) // s) * s
                return dt.replace(hour=m // 60, minute=m % 60, second=0, microsecond=0)

            def floor_to_slot(dt: datetime) -> datetime:
                minutes = dt.hour * 60 + dt.minute
                s = int(slot.total_seconds() // 60)
                m = (minutes // s) * s
                return dt.replace(hour=m // 60, minute=m % 60, second=0, microsecond=0)

            a2 = ceil_to_slot(a)
            b2 = floor_to_slot(b)
            if b2 - a2 >= want:
                out.append(Zeitfenster(von=a2.time(), bis=b2.time()))
        return out
