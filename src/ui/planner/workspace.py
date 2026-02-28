from datetime import date, timedelta
from types import SimpleNamespace
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QBrush, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QStackedWidget, QTableWidget
)

from ...services.data_service import DataService
from ..utils.datetime_utils import date_to_qdate
from .state import PlannerState
from .day_view import PlannerDayView
from .week_view import PlannerWeekView
from .month_view import PlannerMonthView
from ..utils.crud_handlers import CrudHandlers
from .cell import TerminCard, TimeSlotCell
from PySide6.QtWidgets import QLabel
from ..components.dragdrop.week_drop_table import WeekDropTable
from ..components.dragdrop.month_drop_table import MonthDropTable
from PySide6.QtWidgets import QTableWidget as SimpleTableWidget

class PlannerWorkspace(QWidget):
    def __init__(self, parent: QWidget, ds: DataService, on_data_changed, global_filter_dock=None):
        super().__init__(parent)
        
        # self._emit_enabled = False
        self.on_data_changed = on_data_changed

        self.state = PlannerState(ds)
        self.state.reload()

        # Main layout setup
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Global filter dock controls
        self.view_cb = global_filter_dock.view_cb
        self.prev_btn = global_filter_dock.prev_btn
        self.next_btn = global_filter_dock.next_btn
        self.day_date = global_filter_dock.day_date
        self.week_from = global_filter_dock.week_from

        # Stacked widget for day/week tables
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.day_table = WeekDropTable(0, 0)
        self.week_table = WeekDropTable(0, 0)
        # Month view container: header label + table so we can show the month name
        self.month_table = MonthDropTable(0, 7)
        self.month_container = QWidget()
        month_layout = QVBoxLayout(self.month_container)
        month_layout.setContentsMargins(0, 0, 0, 0)
        month_layout.setSpacing(6)
        self.month_header = QLabel("")
        self.month_header.setObjectName("MonthHeader")
        month_layout.addWidget(self.month_header)
        month_layout.addWidget(self.month_table)
        self.day_table.setObjectName("PlannerTable")
        self.week_table.setObjectName("PlannerTable")
        self.month_table.setObjectName("PlannerTable")
        self._apply_planner_table_palette(self.day_table)
        self._apply_planner_table_palette(self.week_table)
        self._apply_planner_table_palette(self.month_table)
        self.day_table.setSortingEnabled(False)
        self.week_table.setSortingEnabled(False)
        self.month_table.setSortingEnabled(False)
        self.day_table.setAlternatingRowColors(False)
        self.week_table.setAlternatingRowColors(False)
        self.month_table.setAlternatingRowColors(False)
        self.stack.addWidget(self.day_table)
        self.stack.addWidget(self.week_table)
        self.stack.addWidget(self.month_container)

        self.crud = CrudHandlers(
            ds=ds,
            parent=self,
            planner=SimpleNamespace(refresh=lambda: None),
        )

        # Day and week view setup
        self.day_view = PlannerDayView(
            state=self.state,
            day_table=self.day_table,
            day_date=self.day_date,
            edit_by_id_cb=self._edit_termin_by_id,
            on_drop_cb=self._on_day_drop,
        )
        self.week_view = PlannerWeekView(
            state=self.state,
            week_table=self.week_table,
            week_from=self.week_from,
            edit_by_id_cb=self._edit_termin_by_id,
            on_drop_cb=self._on_week_drop,
        )
        self.month_view = PlannerMonthView(
            state=self.state,
            month_table=self.month_table,
            month_from=self.week_from,
            month_label=self.month_header,
            edit_by_id_cb=self._edit_termin_by_id,
            on_drop_cb=self._on_month_drop,
        )

        # Table click event connections
        self.week_table.cellClicked.connect(self._on_week_cell_clicked)
        self.day_table.cellClicked.connect(self._on_day_cell_clicked)
        self.month_table.cellClicked.connect(self._on_day_cell_clicked)

        # View and navigation controls
        # Navigation buttons are emitted by the global filter dock and handled
        # by MainWindow which calls PlannerWorkspace._shift_period. Do not
        # connect the buttons directly here to avoid double-calls.
        self.view_cb.currentIndexChanged.connect(self._on_view_changed)

        # Date change triggers
        self.day_date.dateChanged.connect(lambda *_: self.refresh(emit=False))
        self.week_from.dateChanged.connect(lambda *_: self.refresh(emit=False))

        # Initial state setup
        self._init_default_dates()
        self._on_view_changed()
        self.refresh(emit=False)
        self._emit_enabled = True

        # Set object names for styling
        self.day_date.setObjectName("DateEdit")
        self.week_from.setObjectName("DateEdit")
        self.view_cb.setObjectName("HeaderCombo")


    def reload_and_refresh_everything(self) -> None:
        self.refresh(emit=True)

    def _apply_planner_table_palette(self, table: QTableWidget) -> None:
        pal = QPalette(table.palette())
        pal.setColor(QPalette.Highlight, QColor(0, 0, 0, 0))
        pal.setColor(QPalette.HighlightedText, QColor("#111111"))
        table.setPalette(pal)

    def _qdate_to_pydate(self, qd: QDate) -> date:
        return date(qd.year(), qd.month(), qd.day())

    def _align_to_monday(self, d: date) -> date:
        return d - timedelta(days=d.weekday())

    def _shift_period(self, direction: int):
        view = str(self.view_cb.currentData())
        if view == "day":
            d = self._qdate_to_pydate(self.day_date.date()) + timedelta(days=direction)
            self.day_date.setDate(date_to_qdate(d))
        elif view == "week":
            wf = self._qdate_to_pydate(self.week_from.date())
            wf = self._align_to_monday(wf) + timedelta(days=7 * direction)
            self.week_from.setDate(date_to_qdate(wf))
        elif view == "month":
            # shift by calendar months
            wf = self._qdate_to_pydate(self.week_from.date())
            year = wf.year
            month = wf.month + direction
            # normalize month/year
            while month < 1:
                month += 12
                year -= 1
            while month > 12:
                month -= 12
                year += 1
            # set to same day if possible, else clamp
            day = min(wf.day, (date(year, month, 1).replace(day=1).day))
            try:
                newd = wf.replace(year=year, month=month)
            except Exception:
                # fallback to first of month
                newd = date(year, month, 1)
            self.week_from.setDate(date_to_qdate(newd))
        else:
            # default: treat as week
            wf = self._qdate_to_pydate(self.week_from.date())
            wf = self._align_to_monday(wf) + timedelta(days=7 * direction)
            self.week_from.setDate(date_to_qdate(wf))

        self.refresh(emit=False)

    def _init_default_dates(self):
        if not self.state.termine:
            return

        # only Termine that actually have a date
        dated = [t.datum for t in self.state.termine if t.datum is not None]
        if not dated:
            # fallback: today (or keep whatever is already set)
            self.day_date.setDate(QDate.currentDate())
            self.week_from.setDate(date_to_qdate(self._align_to_monday(date.today())))
            return

        min_d = min(dated)
        self.day_date.setDate(date_to_qdate(min_d))
        self.week_from.setDate(date_to_qdate(self._align_to_monday(min_d)))


    # def _rebuild_filter_boxes(self):
    #     # Planner no longer owns local filter comboboxes; global dock provides
    #     # filter dropdowns. Keep this method lightweight so refresh() can call
    #     # it to ensure state is loaded.
    #     return

    def current_filters(self):
        gf = getattr(self, "_global_filter", None)
        if gf is None:
            return {
                "raum_id": None,
                "q": "",
                "typ": None,
                "dozent": None,
                "semester_id": None,
                "geplante_semester": None,
            }
        return {
            "raum_id": gf.raum_id,
            "q": (str(gf.lva_id).strip().lower() if gf.lva_id else ""),
            "typ": gf.typ,
            "dozent": getattr(gf, "dozent", None),
            "semester_id": getattr(gf, "semester", None),
            "geplante_semester": getattr(gf, "geplante_semester", None),
        }

    def refresh(self, emit: bool = True):
        # Reload EVERYTHING every refresh so UI always matches saved JSON state
        self.state.reload()
        # self._rebuild_filter_boxes()

        filters = self.current_filters()
        filtered = self.state.filtered_termine(
            raum_id=filters["raum_id"],
            q=filters["q"],
            typ=filters["typ"],
            dozent=filters["dozent"],
            semester_id=filters["semester_id"],
            geplante_semester=filters["geplante_semester"],
        )

        view = str(self.view_cb.currentData())
        if view == "day":
            self.stack.setCurrentWidget(self.day_table)
            rooms = self.state.raeume
            if filters["raum_id"]:
                rooms = [r for r in rooms if r.id == filters["raum_id"]]
            self.day_view.refresh(filtered, rooms, None, filters["raum_id"])
        elif view == "week":
            self.stack.setCurrentWidget(self.week_table)
            self.week_view.refresh(filtered)
        elif view == "month":
            # month view uses a container (header + table)
            self.stack.setCurrentWidget(self.month_container)
            self.month_view.refresh(filtered)
        else:
            self.stack.setCurrentWidget(self.week_table)
            self.week_view.refresh(filtered)

        if emit and self._emit_enabled and callable(self.on_data_changed):
            self.on_data_changed()

    def _on_view_changed(self):
        view = str(self.view_cb.currentData())
        if view == "day":
            current_day = self._qdate_to_pydate(self.day_date.date())
            week_start = self._qdate_to_pydate(self.week_from.date())
            week_end = week_start + timedelta(days=6)
            if not (week_start <= current_day <= week_end):
                self.day_date.setDate(date_to_qdate(week_start))
        elif view == "week":
            # ensure week_from aligns to monday for the week view
            current_day = self._qdate_to_pydate(self.day_date.date())
            week_start = self._align_to_monday(current_day)
            self.week_from.setDate(date_to_qdate(week_start))
        elif view == "month":
            # keep week_from within the same month as current day
            current_day = self._qdate_to_pydate(self.day_date.date())
            month_start = current_day.replace(day=1)
            self.week_from.setDate(date_to_qdate(month_start))
        else:
            current_day = self._qdate_to_pydate(self.day_date.date())
            week_start = self._align_to_monday(current_day)
            self.week_from.setDate(date_to_qdate(week_start))

        # view switching should not refresh external docks/terminliste
        self.refresh(emit=False)

    def add_termin(self):
        if self.crud.add_termin(default_qdate=self.day_date.date(), auto_id=True):
            self.reload_and_refresh_everything()  # NEW

    def _edit_termin_by_id(self, tid: str):
        if self.crud.edit_termin_by_id(tid):
            self.reload_and_refresh_everything()  # NEW

    def set_on_data_changed(self, cb):
        self.on_data_changed = cb

    def set_global_filter_state(self, fs) -> None:
        if fs is None:
            self._global_filter = None
        else:
            self._global_filter = fs

        self.refresh(emit=False)

    def highlight_termine(self, termin_ids: list[str]) -> None:
        ids = {str(tid) for tid in (termin_ids or []) if tid}
        if not ids:
            return

        self._jump_to_first_termin(ids)

        # Clear previous highlights
        TerminCard.clear_global_focus()
        TerminCard.clear_all_highlights()
        self._clear_day_highlights()

        self._highlight_week_cards(ids)
        self._highlight_day_cells(ids)

    def clear_conflict_highlights(self) -> None:
        TerminCard.clear_global_focus()
        TerminCard.clear_all_highlights()
        self._clear_day_highlights()

    def _on_week_cell_clicked(self, row: int, col: int) -> None:
        cell_widget = self.week_table.cellWidget(row, col)
        if isinstance(cell_widget, TimeSlotCell):
            if not cell_widget.get_termin_ids():
                self.clear_conflict_highlights()
        else:
            self.clear_conflict_highlights()

    def _on_day_cell_clicked(self, row: int, col: int) -> None:
        cell_widget = self.day_table.cellWidget(row, col)
        if isinstance(cell_widget, TimeSlotCell):
            if not cell_widget.get_termin_ids():
                self.clear_conflict_highlights()
        else:
            it = self.day_table.item(row, col)
            if not it or not it.data(Qt.UserRole):
                self.clear_conflict_highlights()

    def _jump_to_first_termin(self, ids: set[str]) -> None:
        t = None
        if hasattr(self.state, "termin_map"):
            for tid in ids:
                t = self.state.termin_map.get(tid)
                if t:
                    break
        if t is None:
            t = next((x for x in self.state.termine if str(x.id) in ids), None)
        if not t or not t.datum:
            return

        self.day_date.setDate(date_to_qdate(t.datum))
        self.week_from.setDate(date_to_qdate(self._align_to_monday(t.datum)))

    def _highlight_week_cards(self, ids: set[str]) -> None:
        first_focused = False
        rows = self.week_table.rowCount()
        cols = self.week_table.columnCount()
        for r in range(rows):
            for c in range(cols):
                cell_widget = self.week_table.cellWidget(r, c)
                if not isinstance(cell_widget, TimeSlotCell):
                    continue
                for card in cell_widget.findChildren(TerminCard):
                    if card.termin_id in ids:
                        card.set_conflict_highlight(True)
                        if not first_focused:
                            card.setFocus()
                            first_focused = True

    def _highlight_day_cells(self, ids: set[str]) -> None:
        first_focused = False
        rows = self.day_table.rowCount()
        cols = self.day_table.columnCount()
        highlight_brush = QBrush(QColor(255, 244, 204))
        self._day_highlights = []
        for r in range(rows):
            for c in range(cols):
                cell_widget = self.day_table.cellWidget(r, c)
                if isinstance(cell_widget, TimeSlotCell):
                    for card in cell_widget.findChildren(TerminCard):
                        if card.termin_id in ids:
                            card.set_conflict_highlight(True)
                            if not first_focused:
                                card.setFocus()
                                first_focused = True
                else:
                    it = self.day_table.item(r, c)
                    if not it:
                        continue
                    tid = it.data(Qt.UserRole)
                    if tid and str(tid) in ids:
                        it.setBackground(highlight_brush)
                        self._day_highlights.append((r, c))

    def _clear_day_highlights(self) -> None:
        if not hasattr(self, "_day_highlights"):
            self._day_highlights = []
            return
        for r, c in self._day_highlights:
            it = self.day_table.item(r, c)
            if it:
                it.setBackground(QBrush())
        self._day_highlights = []

    def _on_week_drop(self, termin_id, new_date, new_start):
        if self.crud.move_termin(str(termin_id), new_date=new_date, new_start=new_start):
            self.reload_and_refresh_everything()

    def _on_month_drop(self, termin_id, new_date, new_start=None):
        if self.crud.move_termin(str(termin_id), new_date=new_date, new_start=new_start):
            self.reload_and_refresh_everything()

    def _on_day_drop(self, termin_id, new_date, new_start, new_room_id=None):
        if self.crud.move_termin(str(termin_id), new_date=new_date, new_start=new_start, new_room_id=new_room_id):
            self.reload_and_refresh_everything()
