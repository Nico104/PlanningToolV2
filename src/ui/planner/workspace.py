import calendar
from datetime import date, timedelta
from types import SimpleNamespace

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QStackedWidget, QTableWidget
)

from ...services.data_service import DataService
from ...services.termin_occurrence_service import expand_termine, source_termin_id
from ..utils.datetime_utils import date_to_qdate
from .state import PlannerState
from .day_view import PlannerDayView
from .week_view import PlannerWeekView
from .month_view import PlannerMonthView
from .free_day_provider import FreeDayProvider
from ..utils.crud_handlers import CrudHandlers
from .termincard import TerminCard
from .timeslotcell import TimeSlotCell
from ..components.dragdrop.time_grid_drop_table import TimeGridDropTable
from ..components.dragdrop.month_drop_table import MonthDropTable

class PlannerWorkspace(QWidget):
    """Main planner container coordinating day/week/month views and shared state
    """

    def __init__(self, parent: QWidget, ds: DataService, on_data_changed, global_filter_dock=None):
        super().__init__(parent)
        
        self.on_data_changed = on_data_changed

        self.state = PlannerState(ds)
        self.state.reload()
        self.free_day_provider = FreeDayProvider(self.state.ds.data_dir)

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

        # Stacked widget for day/week/month tables
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.day_table = TimeGridDropTable()
        self.week_table = TimeGridDropTable()
        self.month_table = MonthDropTable()
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
            undo_service=getattr(parent, "undo_service", None),
        )

        # Day, week, month view setup
        self.day_view = PlannerDayView(
            state=self.state,
            day_table=self.day_table,
            day_date=self.day_date,
            free_day_provider=self.free_day_provider,
            edit_by_id_cb=self._edit_termin_by_id,
            on_drop_cb=self._on_day_drop,
        )
        self.week_view = PlannerWeekView(
            state=self.state,
            week_table=self.week_table,
            week_from=self.week_from,
            free_day_provider=self.free_day_provider,
            edit_by_id_cb=self._edit_termin_by_id,
            on_drop_cb=self._on_week_drop,
        )
        self.month_view = PlannerMonthView(
            state=self.state,
            month_table=self.month_table,
            month_from=self.week_from,
            month_label=self.month_header,
            free_day_provider=self.free_day_provider,
            edit_by_id_cb=self._edit_termin_by_id,
            on_drop_cb=self._on_month_drop,
        )

        # Table click event connections
        self.week_table.cellClicked.connect(self._on_week_cell_clicked)
        self.day_table.cellClicked.connect(self._on_day_cell_clicked)
        self.month_table.cellClicked.connect(self._on_month_cell_clicked)

        # View change event connection
        self.view_cb.currentIndexChanged.connect(self._on_view_changed)

        # Date change triggers
        self.day_date.dateChanged.connect(self._on_date_changed)
        self.week_from.dateChanged.connect(self._on_date_changed)

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
        elif view == "month":
            wf = self._qdate_to_pydate(self.week_from.date())
            month_index = (wf.month - 1) + direction
            year = wf.year + (month_index // 12)
            month = (month_index % 12) + 1
            day = min(wf.day, calendar.monthrange(year, month)[1])
            newd = wf.replace(year=year, month=month, day=day)
            self.week_from.setDate(date_to_qdate(newd))
        else:
            # default: treat as week
            wf = self._qdate_to_pydate(self.week_from.date())
            wf = self._align_to_monday(wf) + timedelta(days=7 * direction)
            self.week_from.setDate(date_to_qdate(wf))

        self.refresh(emit=False)

    def _init_default_dates(self):
        """Initialize day/week controls to a stable starting point

        Preference order:
        1. Earliest dated Termin in current state.
        2. Today, if Termine exist but none has a date.
        """
        if not self.state.termine:
            return

        dated = [t.datum for t in self.state.occurrences if t.datum is not None]
        if not dated:
            self.day_date.setDate(QDate.currentDate())
            self.week_from.setDate(date_to_qdate(self._align_to_monday(date.today())))
            return

        min_d = min(dated)
        self.day_date.setDate(date_to_qdate(min_d))
        self.week_from.setDate(date_to_qdate(self._align_to_monday(min_d)))


    def current_filters(self):
        # getattr wird verwendet, falls _global_filter noch nicht gesetzt wurde
        gf = getattr(self, "_global_filter", None)
        if gf is None:
            return {
                "raum_id": None,
                "lva_id": None,
                "typ": None,
                "dozent": None,
                "studienrichtung": None,
                "semester_id": None,
                "studiensemester": None,
            }
        return {
            "raum_id": gf.raum_id,
            "lva_id": gf.lva_id,
            "typ": gf.typ,
            "dozent": getattr(gf, "dozent", None),
            "studienrichtung": getattr(gf, "studienrichtung", None),
            "semester_id": getattr(gf, "semester", None),
            "studiensemester": getattr(gf, "studiensemester", None),
        }

    def refresh(self, emit: bool = True):
        self.state.reload()

        filters = self.current_filters()
        filtered = self.state.filtered_termine(
            raum_id=filters["raum_id"],
            lva_id=filters["lva_id"],
            typ=filters["typ"],
            dozent=filters["dozent"],
            studienrichtung=filters["studienrichtung"],
            semester_id=filters["semester_id"],
            studiensemester=filters["studiensemester"],
        )
        expanded = expand_termine(filtered)

        view = str(self.view_cb.currentData())
        if view == "day":
            self.stack.setCurrentWidget(self.day_table)
            rooms = self.state.raeume
            if filters["raum_id"]:
                rooms = [r for r in rooms if r.id == filters["raum_id"]]
            self.day_view.refresh(expanded, rooms)
        elif view == "week":
            self.stack.setCurrentWidget(self.week_table)
            self.week_view.refresh(expanded)
        elif view == "month":
            self.stack.setCurrentWidget(self.month_container)
            self.month_view.refresh(expanded)
        else:
            self.stack.setCurrentWidget(self.week_table)
            self.week_view.refresh(expanded)

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

    def _edit_termin_by_id(self, tid: str):
        if self.crud.edit_termin_by_id(tid):
            self.reload_and_refresh_everything()

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
        source_ids = {source_termin_id(tid) for tid in ids}

        self._jump_to_first_termin(ids)

        # Clear previous highlights
        self.clear_conflict_highlights()

        self._highlight_week_cards(ids, source_ids)
        self._highlight_day_cells(ids, source_ids)
        self._highlight_month_cells(ids, source_ids)

    def clear_conflict_highlights(self) -> None:
        TerminCard.clear_global_focus()
        TerminCard.clear_all_highlights()
        self._clear_month_highlights()

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
            self.clear_conflict_highlights()

    def _on_month_cell_clicked(self, row: int, col: int) -> None:
        self.clear_conflict_highlights()

    def _on_date_changed(self, *_args) -> None:
        self.refresh(emit=False)

    def _jump_to_first_termin(self, ids: set[str]) -> None:
        t = next((self.state.termin_map.get(str(tid)) for tid in ids if self.state.termin_map.get(str(tid))), None)
        if not t or not t.datum:
            return

        self.day_date.setDate(date_to_qdate(t.datum))
        self.week_from.setDate(date_to_qdate(self._align_to_monday(t.datum)))

    def _highlight_week_cards(self, ids: set[str], source_ids: set[str]) -> None:
        first_focused = False
        rows = self.week_table.rowCount()
        cols = self.week_table.columnCount()
        for r in range(rows):
            for c in range(cols):
                cell_widget = self.week_table.cellWidget(r, c)
                if not isinstance(cell_widget, TimeSlotCell):
                    continue
                for card in cell_widget.findChildren(TerminCard):
                    if card.termin_id in ids or source_termin_id(card.termin_id) in source_ids:
                        card.set_conflict_highlight(True)
                        if not first_focused:
                            card.setFocus()
                            first_focused = True

    def _highlight_day_cells(self, ids: set[str], source_ids: set[str]) -> None:
        first_focused = False
        rows = self.day_table.rowCount()
        cols = self.day_table.columnCount()
        for r in range(rows):
            for c in range(cols):
                cell_widget = self.day_table.cellWidget(r, c)
                if isinstance(cell_widget, TimeSlotCell):
                    for card in cell_widget.findChildren(TerminCard):
                        if card.termin_id in ids or source_termin_id(card.termin_id) in source_ids:
                            card.set_conflict_highlight(True)
                            if not first_focused:
                                card.setFocus()
                                first_focused = True

    def _highlight_month_cells(self, ids: set[str], source_ids: set[str]) -> None:
        rows = self.month_table.rowCount()
        cols = self.month_table.columnCount()
        for r in range(rows):
            for c in range(cols):
                cell_widget = self.month_table.cellWidget(r, c)
                if cell_widget is None:
                    continue
                day_ids = cell_widget.property("day_ids") or []
                has_match = any(str(tid) in ids or source_termin_id(tid) in source_ids for tid in day_ids)
                cell_widget.setProperty("monthConflictHighlight", has_match)
                cell_widget.style().unpolish(cell_widget)
                cell_widget.style().polish(cell_widget)
                cell_widget.update()

    def _clear_month_highlights(self) -> None:
        rows = self.month_table.rowCount()
        cols = self.month_table.columnCount()
        for r in range(rows):
            for c in range(cols):
                cell_widget = self.month_table.cellWidget(r, c)
                if cell_widget is None:
                    continue
                if cell_widget.property("monthConflictHighlight"):
                    cell_widget.setProperty("monthConflictHighlight", False)
                    cell_widget.style().unpolish(cell_widget)
                    cell_widget.style().polish(cell_widget)
                    cell_widget.update()

    def _on_week_drop(self, termin_id, new_date, new_start):
        self._move_termin_and_refresh(str(termin_id), new_date=new_date, new_start=new_start)

    def _on_month_drop(self, termin_id, new_date, new_start=None):
        self._move_termin_and_refresh(str(termin_id), new_date=new_date, new_start=new_start)

    def _on_day_drop(self, termin_id, new_date, new_start, new_room_id=None):
        self._move_termin_and_refresh(
            str(termin_id),
            new_date=new_date,
            new_start=new_start,
            new_room_id=new_room_id,
        )

    def _move_termin_and_refresh(self, termin_id: str, **kwargs) -> None:
        if self.crud.move_termin(termin_id, **kwargs):
            self.reload_and_refresh_everything()
