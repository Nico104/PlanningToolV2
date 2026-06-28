from __future__ import annotations

from datetime import date, datetime
from typing import Any


def free_day_entry_key(entry: dict[str, Any]) -> str | None:
    def text_key(value: Any) -> str:
        return " ".join(str(value or "").strip().casefold().split())

    def date_key(value: Any) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()

        text = str(value or "").strip()
        if not text:
            return ""
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            return text[:10]
        return text

    values = (
        text_key(entry.get("typ")),
        text_key(entry.get("beschreibung")),
        date_key(entry.get("von_datum")),
        date_key(entry.get("bis_datum")),
    )
    if not all(values):
        return None
    return "|".join(values)
