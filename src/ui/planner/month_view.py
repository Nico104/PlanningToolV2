from datetime import date, datetime
import calendar
from typing import List

from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtWidgets import (
    QTableWidgetItem,
    QTableWidget,
    QListWidgetItem,
    QAbstractItemView,
    QWidget,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
    QHeaderView,
)

from ...core.models import Termin
from ..utils.datetime_utils import qdate_to_date, date_to_qdate

from PySide6.QtWidgets import QDialog

from ..dialogs.day_events_dialog import DayEventsDialog


class PlannerMonthView:
    """Simple monthly grid view. Shows day numbers and a +N indicator when events exist.

    Clicking a day with events opens a dialog listing that day's termins.
    """

    def __init__(self, state, month_table: QTableWidget, month_from, month_label=None, edit_by_id_cb=None, on_drop_cb=None):
        self.state = state
        self.table = month_table
        self.month_from = month_from
        self.edit_by_id_cb = edit_by_id_cb
        self.on_drop_cb = on_drop_cb
        self.month_label = month_label

        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"])
        # no cell editing in month view
        # Make the table expand to fill available space
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Appearance tweaks
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setShowGrid(True)
        self.table.setWordWrap(False)
        # Default row height; will be adjusted in refresh as well
        self.table.verticalHeader().setDefaultSectionSize(90)
        # Simple stylesheet for month labels
        self.table.setStyleSheet("""
            QLabel#MonthDayNumber { font-weight: 600; font-size: 14px; }
            QLabel#MonthDayCount { color: #666; font-size: 11px; }
            QTableWidget { background: white; }
        """)
        self.table.cellClicked.connect(self._on_cell_clicked)
        # hide horizontal scrollbar so columns must fit the available width
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # store last filtered set so we can re-layout on resize/show
        self._last_filtered: List[Termin] = []

        # small watcher to detect resize/show events and reflow the grid
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

        # watcher parent should be a QObject; pass the table viewport as parent
        self._watcher = _Watcher(self, self.table.viewport())
        self.table.viewport().installEventFilter(self._watcher)

        # connect drop callback if the table supports it
        try:
            if hasattr(self.table, 'terminDropped'):
                self.table.terminDropped.connect(self._on_table_drop)
        except Exception:
            pass

    def refresh(self, filtered_termine: List[Termin]):
        # Determine month to show from month_from (QDateEdit)
        try:
            mf = qdate_to_date(self.month_from.date())
        except Exception:
            mf = date.today()

        year = mf.year
        month = mf.month
        first_weekday, days_in_month = calendar.monthrange(year, month)

        # monthrange returns Mon=0..Sun=6 but first_weekday is Mon=0
        # We want to align to Monday. first_weekday already matches our header.
        start_offset = first_weekday  # number of blank days before 1st

        total_cells = start_offset + days_in_month
        weeks = (total_cells + 6) // 7

        self.table.setRowCount(weeks)

        # Build mapping date -> list of termins
        by_date = {}
        for t in filtered_termine:
            if getattr(t, 'datum', None):
                by_date.setdefault(t.datum, []).append(t)

        # cache filtered termins for later relayout triggers
        self._last_filtered = list(filtered_termine or [])
        # cache filtered termins for later relayout triggers
        self._last_filtered = list(filtered_termine or [])
        day = 1
        # Use viewport height for stable row sizing when the widget is in a stacked layout
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

                    # Build a small widget with day number and count
                    w = QWidget()
                    lay = QVBoxLayout(w)
                    lay.setContentsMargins(6, 4, 6, 4)
                    lay.setSpacing(2)

                    day_lbl = QLabel(f"{day}")
                    day_lbl.setObjectName("MonthDayNumber")
                    day_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)

                    count_lbl = QLabel("")
                    count_lbl.setObjectName("MonthDayCount")
                    count_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                    if items:
                        count_lbl.setText(f"(+{len(items)})")
                    else:
                        count_lbl.setText("")

                    lay.addWidget(day_lbl)
                    lay.addWidget(count_lbl)
                    w.setLayout(lay)
                    w.setProperty("day_ids", [str(t.id) for t in items])
                    # store the actual date on the widget for click handler
                    w.setProperty("day_date", d)
                    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                    self.table.setCellWidget(r, c, w)
                    day += 1

        # Ensure headers and columns look good
        # Update month label if provided
        if self.month_label is not None:
            try:
                self.month_label.setText(f"{calendar.month_name[month]} {year}")
            except Exception:
                pass

        # Calculate column widths to evenly fill the viewport and disable horizontal scrolling
        avail_w = max(1, self.table.viewport().width())
        col_w = max(48, avail_w // 7)
        # Use Fixed resize mode so setColumnWidth takes effect
        for i in range(7):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Fixed)
            self.table.setColumnWidth(i, col_w)
        # Force layout updates
        self.table.updateGeometry()
        self.table.viewport().update()

    def _on_cell_clicked(self, row: int, col: int):
        w = self.table.cellWidget(row, col)
        if not w:
            return
        data = w.property("day_ids")
        if not data:
            return

        # Resolve termins from ids
        ids = set(str(x) for x in (data or []))
        term_list = []
        if hasattr(self.state, 'termin_map'):
            for tid in ids:
                t = self.state.termin_map.get(tid)
                if t:
                    term_list.append(t)
        else:
            for t in self.state.termine:
                if str(t.id) in ids:
                    term_list.append(t)

        # get stored day date
        day_date = w.property("day_date")

        dlg = DayEventsDialog(self.table.window(), term_list, edit_cb=self.edit_by_id_cb, day=day_date)
        dlg.exec()

    def _on_table_drop(self, termin_id: str, row: int, col: int):
        # Map dropped cell (row,col) to a calendar date using current month_from
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

        # Determine earliest available start time for the termin's room
        new_start = None
        try:
            # find the termin object
            t = None
            if hasattr(self.state, 'termin_map'):
                t = self.state.termin_map.get(str(termin_id))
            if not t:
                t = next((x for x in self.state.termine if str(x.id) == str(termin_id)), None)

            room_id = getattr(t, 'raum_id', None) if t else None
            duration = int(getattr(t, 'duration', 0) or 0) if t else 0
            if duration <= 0:
                duration = int(self.state.settings.get('time_slot_minutes', 30))

            if room_id and self.state and getattr(self.state, 'ts', None):
                free = self.state.ts.find_free_slots_in_room(self.state.termine, room_id, new_date, duration)
                if free:
                    # pick the first available slot's start time
                    new_start = free[0].von
        except Exception:
            new_start = None

        if callable(self.on_drop_cb):
            try:
                # follow day/week conventions: (termin_id, new_date, new_start)
                self.on_drop_cb(str(termin_id), new_date, new_start)
            except Exception:
                pass
