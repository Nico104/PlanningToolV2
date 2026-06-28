from datetime import date, datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json


@dataclass(frozen=True)
class FreeDayBadgeLine:
    day_type: str
    text: str


@dataclass(frozen=True)
class FreeDayInfo:
    badge_lines: tuple[FreeDayBadgeLine, ...] = ()


class FreeDayProvider:
    """Shared provider for free-day data and styles used by planner views"""

    def __init__(self, data_dir: Path):
        self._data_dir = Path(data_dir)

    def get_info_for_date(self, target: date) -> Optional[FreeDayInfo]:
        return self.get_infos_for_range(target, target).get(target)

    def get_infos_for_range(self, start: date, end: date) -> dict[date, FreeDayInfo]:
        path = self._data_dir / "freie_tage.json"
        if not path.exists():
            return {}

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        raw: dict[date, list[tuple[str, str]]] = {}
        for item in payload.get("freie_tage", []):
            day_type = item.get("typ", "").strip().lower()
            if not day_type:
                continue
            description = str(item.get("beschreibung", "")).strip()

            start_raw = str(item.get("von_datum", "")).strip()
            end_raw = str(item.get("bis_datum", "")).strip()
            d0 = self._parse_iso_date(start_raw)
            d1 = self._parse_iso_date(end_raw)
            if d0 is None or d1 is None or d1 < d0:
                continue

            cur = max(d0, start)
            lim = min(d1, end)
            while cur <= lim:
                raw.setdefault(cur, []).append((day_type, description))
                cur += timedelta(days=1)

        return {day: self._merge_infos(items) for day, items in raw.items()}

    def badge_lines_for_info(self, info: Optional[FreeDayInfo]) -> tuple[FreeDayBadgeLine, ...]:
        return info.badge_lines if info is not None else ()

    def _parse_iso_date(self, raw: str) -> Optional[date]:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            return None

    def _merge_infos(self, items: list[tuple[str, str]]) -> FreeDayInfo:
        priority = {"feiertag": 0, "vorlesungsfrei": 1}
        sorted_items = sorted(items, key=lambda item: (priority.get(item[0], 9), item[0], item[1]))
        badge_lines: list[FreeDayBadgeLine] = []
        seen = set()
        for item_type, description in sorted_items:
            if not description or description in seen:
                continue
            seen.add(description)
            badge_lines.append(FreeDayBadgeLine(item_type, description))
        return FreeDayInfo(badge_lines=tuple(badge_lines))
