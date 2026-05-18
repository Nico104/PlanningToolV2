from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
import json
import re

from PySide6.QtGui import QColor


class FreeDayProvider:
    """Shared provider for free-day data and styles used by planner views
    """

    def __init__(self, data_dir: Path):
        self._data_dir = Path(data_dir)
        self._styles = self._load_free_day_styles()

    def get_styles(self) -> dict[str, object]:
        return self._styles

    def get_type_for_date(self, target: date) -> Optional[str]:
        return self.get_types_for_range(target, target).get(target)

    def get_types_for_range(self, start: date, end: date) -> dict[date, str]:
        path = self._data_dir / "freie_tage.json"
        if not path.exists():
            return {}

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        out: dict[date, str] = {}
        for item in payload.get("freie_tage", []):
            day_type = item.get("typ", "").strip().lower()
            if not day_type:
                continue

            single_raw = str(item.get("datum", "")).strip()
            if single_raw:
                d = self._parse_iso_date(single_raw)
                if d is not None and start <= d <= end:
                    out[d] = day_type
                continue

            start_raw = str(item.get("von_datum", "")).strip()
            end_raw = str(item.get("bis_datum", "")).strip()
            d0 = self._parse_iso_date(start_raw)
            d1 = self._parse_iso_date(end_raw)
            if d0 is None or d1 is None or d1 < d0:
                continue

            cur = max(d0, start)
            lim = min(d1, end)
            while cur <= lim:
                out[cur] = day_type
                cur += timedelta(days=1)

        return out

    @staticmethod
    def label_for_type(day_type: Optional[str]) -> str:
        if day_type == "feiertag":
            return "Feiertag"
        if day_type == "vorlesungsfrei":
            return "Vorlesungsfrei"
        return ""

    def _load_free_day_styles(self) -> dict[str, object]:
        try:
            qss = (Path(__file__).resolve().parent.parent / "styles" / "light.qss").read_text(encoding="utf-8")
        except OSError:
            return {}

        qss_values = self._qss_values(qss)
        styles: dict[str, object] = {}

        for token, key in {
            "free-day-holiday-bg": "holiday_bg",
            "free-day-lecture-bg": "lecture_bg",
        }.items():
            color = QColor(qss_values.get(token, ""))
            if color.isValid():
                styles[key] = color

        return styles

    @staticmethod
    def _qss_values(qss: str) -> dict[str, str]:
        return {
            token.strip(): value.strip().rstrip(";")
            for line in qss.splitlines()
            if ":" in line
            for token, value in [line.split(":", 1)]
        }

    def _parse_iso_date(self, raw: str) -> Optional[date]:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            return None
