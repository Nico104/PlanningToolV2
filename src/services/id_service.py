from typing import Iterable
import re

def next_id(prefix: str, existing_ids: Iterable[str], width: int = 3) -> str:
    """
    Erzeugt eine neue ID wie T001, T002... basierend auf existierenden IDs.
    """
    pat = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    mx = 0
    for eid in existing_ids:
        m = pat.match(eid)
        if m:
            mx = max(mx, int(m.group(1)))
    return f"{prefix}{mx+1:0{width}d}"
