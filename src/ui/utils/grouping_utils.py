from typing import List, Tuple
from ...core.models import Termin
from ..utils.datetime_utils import mins_from_time

def group_concurrent_appointments(items: List[Termin]) -> List[Tuple[Termin, int]]:
    """
    Group Termine that overlap in time so they can be rendered side-by-side.

    The algorithm is a single-pass sweep over Termine sorted by start time:
    - Maintain a 'current group' and the furthest end time seen in that group.
    - If the next Termin starts before the current group ends, it overlaps and
      is added to the group; the group's end time is extended if necessary.
    - If it starts at or after the current group's end, the group is closed and
      a new one is started.

    All members of the same group receive the same integer group_counter so
    that the caller can collect them, determine the combined time span,
    and place them all into one shared TimeSlotCell.
    """
    if not items:
        return []

    sorted_items = sorted(
        items,
        key=lambda x: mins_from_time(x.start_zeit) if x.start_zeit else 0
    )

    groups: List[Tuple[Termin, int]] = []
    group_counter = 0
    current_group: List[Termin] = []
    current_end = None

    for t in sorted_items:
        if not t.start_zeit or not t.get_end_time():
            continue

        t_start = mins_from_time(t.start_zeit)
        t_end = mins_from_time(t.get_end_time())

        if current_end is None:
            current_group = [t]
            current_end = t_end
            continue

        if t_start < current_end:
            current_group.append(t)
            current_end = max(current_end, t_end)
        else:
            for member in current_group:
                groups.append((member, group_counter))
            group_counter += 1
            current_group = [t]
            current_end = t_end

    if current_group:
        for member in current_group:
            groups.append((member, group_counter))

    return groups
