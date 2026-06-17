from datetime import date, datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json

from PySide6.QtGui import QColor

from ..utils.qss_tokens import qss_color


@dataclass(frozen=True)
class FreeDayInfo:
    day_type: str
    descriptions: tuple[str, ...] = ()


class FreeDayProvider:
    """Shared provider for free-day data and styles used by planner views
    """

    def __init__(self, data_dir: Path):
        self._data_dir = Path(data_dir)
        self._styles = self._load_free_day_styles()

    def get_styles(self) -> dict[str, object]:
        return self._styles

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

    @staticmethod
    def label_for_type(day_type: Optional[str]) -> str:
        if day_type == "feiertag":
            return "Feiertag"
        if day_type == "vorlesungsfrei":
            return "Vorlesungsfrei"
        return ""

    def label_for_info(self, info: Optional[FreeDayInfo]) -> str:
        if info is None:
            return ""
        base = self.label_for_type(info.day_type)
        descriptions = [text for text in info.descriptions if text]
        if not descriptions:
            return base
        return f"{base}: {', '.join(descriptions)}" if base else ", ".join(descriptions)

    def badge_for_info(self, info: Optional[FreeDayInfo]) -> str:
        if info is None:
            return ""
        descriptions = [text for text in info.descriptions if text]
        if descriptions:
            return ", ".join(descriptions)
        return self.label_for_type(info.day_type)

    def _load_free_day_styles(self) -> dict[str, object]:
        styles: dict[str, object] = {}
        styles["holiday_bg"] = qss_color("free-day-holiday-bg")
        styles["lecture_bg"] = qss_color("free-day-lecture-bg")
        styles["cell_border"] = qss_color("free-day-cell-border")
        return styles

    def _parse_iso_date(self, raw: str) -> Optional[date]:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            return None

    def _merge_infos(self, items: list[tuple[str, str]]) -> FreeDayInfo:
        priority = {"feiertag": 0, "vorlesungsfrei": 1}
        sorted_items = sorted(items, key=lambda item: (priority.get(item[0], 9), item[0], item[1]))
        day_type = sorted_items[0][0]
        descriptions: list[str] = []
        seen = set()
        for item_type, description in sorted_items:
            if not description or description in seen:
                continue
            seen.add(description)
            descriptions.append(description)
        for item_type, _ in sorted_items:
            if item_type == day_type:
                continue
            type_label = self.label_for_type(item_type).lower()
            if type_label and type_label not in seen:
                seen.add(type_label)
                descriptions.append(type_label)
        return FreeDayInfo(day_type=day_type, descriptions=tuple(descriptions))
