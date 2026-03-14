from datetime import date
import calendar
from typing import List

from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QTableWidget,
    QWidget,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
    QHeaderView,
)

from ...core.models import Termin
from ..utils.datetime_utils import qdate_to_date, date_to_qdate


from ..dialogs.day_events_dialog import DayEventsDialog
from .free_day_provider import FreeDayProvider


class PlannerMonthView:
    """monthly grid view. Shows day numbers and a +N indicator when events exist.
    Clicking a day with events opens a dialog listing that day's termins
    """

    def __init__(self, state, month_table: QTableWidget, month_from, free_day_provider: FreeDayProvider, month_label=None, edit_by_id_cb=None, on_drop_cb=None):
        self.state = state
        self.table = month_table
        self.month_from = month_from
        self._free_day_provider = free_day_provider
        self.edit_by_id_cb = edit_by_id_cb
        self.on_drop_cb = on_drop_cb
        self.month_label = month_label
        self._free_day_styles = self._free_day_provider.get_styles()

        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"])
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setShowGrid(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(90)
        self.table.setStyleSheet("""
            QLabel#MonthDayNumber { font-weight: 600; font-size: 14px; }
            QLabel#MonthDayCount { color: #666; font-size: 11px; }
            QTableWidget { background: white; }
        """)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._last_filtered: List[Termin] = []

        class _Watcher(QObject):
            def __init__(self, owner, qparent=None):
                super().__init__(qparent)
                self._owner = owner

            def eventFilter(self, obj, ev):
                if ev.type() in (QEvent.Show, QEvent.Resize):
                    try:
                        self._owner.refresh(self._owner._last_filtered)
                    except Exception:
                        pass
                return False

        self._watcher = _Watcher(self, self.table.viewport())
        self.table.viewport().installEventFilter(self._watcher)

        if hasattr(self.table, 'terminDropped'):
            self.table.terminDropped.connect(self._on_table_drop)

    def refresh(self, filtered_termine: List[Termin]):
        try:
            mf = qdate_to_date(self.month_from.date())
        except Exception:
            mf = date.today()

        year = mf.year
        month = mf.month
        first_weekday, days_in_month = calendar.monthrange(year, month)

        # calendar.monthrange uses Mon=0..Sun=6, matching our column order exactly,
        # so first_weekday is directly the number of empty cells before day 1
        start_offset = first_weekday

        total_cells = start_offset + days_in_month
        weeks = (total_cells + 6) // 7

        self.table.setRowCount(weeks)

        by_date = {}
        for t in filtered_termine:
            if getattr(t, 'datum', None):
                by_date.setdefault(t.datum, []).append(t)

        first_day = date(year, month, 1)
        last_day = date(year, month, days_in_month)
        free_days = self._free_day_provider.get_types_for_range(first_day, last_day)

        self._last_filtered = list(filtered_termine or [])
        day = 1
        
        vp_height = max(1, self.table.viewport().height())
        row_height = max(60, int(vp_height / max(1, weeks)))
        for r in range(weeks):
            self.table.setRowHeight(r, row_height)
            for c in range(7):
                cell_index = r * 7 + c
                if cell_index < start_offset or day > days_in_month:
                    # empty cell
                    w = QWidget()
                    w.setProperty("day_ids", [])
                    self.table.setCellWidget(r, c, w)
                else:
                    d = date(year, month, day)
                    items = by_date.get(d, [])
                    day_type = free_days.get(d)

                    # Build a small widget with day number and count
                    w = QWidget()
                    lay = QVBoxLayout(w)
                    lay.setContentsMargins(6, 4, 6, 4)
                    lay.setSpacing(2)

                    day_lbl = QLabel(f"{day}")
                    day_lbl.setObjectName("MonthDayNumber")
                    day_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)

                    count_lbl = QLabel(f"(+{len(items)})" if items else "")
                    count_lbl.setObjectName("MonthDayCount")
                    count_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)

                    lay.addWidget(day_lbl)
                    if day_type:
                        type_lbl = QLabel(self._free_day_provider.label_for_type(day_type))
                        type_lbl.setObjectName("MonthDayType")
                        type_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                        lay.addWidget(type_lbl)
                    lay.addWidget(count_lbl)
                    w.setProperty("day_ids", [str(t.id) for t in items])
                    w.setProperty("day_date", d)
                    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                    if day_type == "feiertag":
                        bg_color = self._free_day_styles.get("holiday_bg")
                    elif day_type == "vorlesungsfrei":
                        bg_color = self._free_day_styles.get("lecture_bg")
                    else:
                        bg_color = None

                    if isinstance(bg_color, QColor) and bg_color.isValid():
                        bg = bg_color.name()
                        w.setObjectName("MonthFreeDayCell")
                        w.setStyleSheet(
                            f"QWidget#MonthFreeDayCell {{ background: {bg}; border: 1px solid #dfe6ee; border-radius: 6px; }}"
                            " QLabel { background: transparent; border: none; }"
                            " QLabel#MonthDayType { font-size: 10px; font-weight: 600; border: none; background: transparent; }"
                        )

                    self.table.setCellWidget(r, c, w)
                    day += 1

        if self.month_label is not None:
            self.month_label.setText(f"{calendar.month_name[month]} {year}")

        avail_w = max(1, self.table.viewport().width())
        col_w = max(48, avail_w // 7)
        for i in range(7):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Fixed)
            self.table.setColumnWidth(i, col_w)
        self.table.updateGeometry()
        self.table.viewport().update()

    def _on_cell_clicked(self, row: int, col: int):
        w = self.table.cellWidget(row, col)
        if not w:
            return
        data = w.property("day_ids")
        if not data:
            return

        ids = set(str(x) for x in data)
        if hasattr(self.state, 'termin_map'):
            term_list = [t for tid in ids if (t := self.state.termin_map.get(tid))]
        else:
            term_list = [t for t in self.state.termine if str(t.id) in ids]

        target_day = w.property("day_date")
        if not isinstance(target_day, date):
            target_day = None

        def _switch_view(view_key: str) -> None:
            mw = self.table.window()
            if not mw or target_day is None:
                return
            planner = getattr(mw, "planner", None)
            if not planner:
                return
            planner.day_date.setDate(date_to_qdate(target_day))
            planner.week_from.setDate(date_to_qdate(planner._align_to_monday(target_day)))
            idx = planner.view_cb.findData(view_key)
            if idx >= 0:
                planner.view_cb.setCurrentIndex(idx)
            planner.refresh(emit=False)

        dlg = DayEventsDialog(
            self.table.window(),
            term_list,
            edit_cb=self.edit_by_id_cb,
            day=target_day,
            go_week_cb=lambda: _switch_view("week"),
            go_day_cb=lambda: _switch_view("day"),
        )
        dlg.exec()

    def _on_table_drop(self, termin_id: str, row: int, col: int):
        try:
            mf = qdate_to_date(self.month_from.date())
        except Exception:
            mf = date.today()

        year = mf.year
        month = mf.month
        first_weekday, days_in_month = calendar.monthrange(year, month)
        start_offset = first_weekday

        cell_index = row * 7 + col
        day = cell_index - start_offset + 1
        if day < 1 or day > days_in_month:
            return

        new_date = date(year, month, day)

        new_start = None
        try:
            t = (self.state.termin_map.get(str(termin_id)) if hasattr(self.state, 'termin_map') else None)
            if not t:
                t = next((x for x in self.state.termine if str(x.id) == str(termin_id)), None)

            room_id = getattr(t, 'raum_id', None) if t else None
            duration = int(getattr(t, 'duration', 0) or 0) if t else 0
            if duration <= 0:
                duration = int(self.state.settings.get('time_slot_minutes', 30))

            if room_id and getattr(self.state, 'ts', None):
                free = self.state.ts.find_free_slots_in_room(self.state.termine, room_id, new_date, duration)
                if free:
                    new_start = free[0].von
        except Exception:
            new_start = None

        if callable(self.on_drop_cb):
            self.on_drop_cb(str(termin_id), new_date, new_start)
