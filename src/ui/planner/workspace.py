import calendar
import re
from datetime import date, timedelta
from types import SimpleNamespace

from PySide6.QtCore import QDate
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QStackedWidget, QTableWidget, QPushButton
)

from ...services.data_service import DataService
from ...services.termin_occurrence_service import expand_termine, source_termin_id
from ..utils.datetime_utils import date_to_qdate
from ..utils.qss_tokens import qss_color
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
        self._previous_year_enabled = False

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

        # Stacked widget for day/week/month tables
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self._day_room_page = 0
        self.day_container = QWidget()
        day_layout = QVBoxLayout(self.day_container)
        day_layout.setContentsMargins(0, 0, 0, 0)
        day_layout.setSpacing(6)
        self.day_room_pager = QWidget()
        self.day_room_pager.setObjectName("DayRoomPager")
        day_pager_layout = QHBoxLayout(self.day_room_pager)
        day_pager_layout.setContentsMargins(0, 0, 0, 0)
        day_pager_layout.setSpacing(6)
        day_pager_layout.addStretch(1)
        self.day_room_prev_btn = QPushButton("◀")
        self.day_room_prev_btn.setObjectName("NavButton")
        self.day_room_prev_btn.setFixedWidth(32)
        self.day_room_prev_btn.setToolTip("Vorige Räume")
        self.day_room_next_btn = QPushButton("▶")
        self.day_room_next_btn.setObjectName("NavButton")
        self.day_room_next_btn.setFixedWidth(32)
        self.day_room_next_btn.setToolTip("Nächste Räume")
        self.day_room_label = QLabel("")
        self.day_room_label.setObjectName("DayRoomPagerLabel")
        day_pager_layout.addWidget(self.day_room_prev_btn)
        day_pager_layout.addWidget(self.day_room_label)
        day_pager_layout.addWidget(self.day_room_next_btn)
        day_layout.addWidget(self.day_room_pager)

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
        day_layout.addWidget(self.day_table)
        self.stack.addWidget(self.day_container)
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
            day_date=self.day_date,
            free_day_provider=self.free_day_provider,
            edit_by_id_cb=self._edit_termin_by_id,
            on_drop_cb=self._on_week_drop,
        )
        self.month_view = PlannerMonthView(
            state=self.state,
            month_table=self.month_table,
            day_date=self.day_date,
            month_label=self.month_header,
            free_day_provider=self.free_day_provider,
            edit_by_id_cb=self._edit_termin_by_id,
            on_drop_cb=self._on_month_drop,
        )
        self._apply_history_read_only()

        # Table click event connections
        self.week_table.cellClicked.connect(self._on_week_cell_clicked)
        self.day_table.cellClicked.connect(self._on_day_cell_clicked)
        self.month_table.cellClicked.connect(self._on_month_cell_clicked)
        self.day_room_prev_btn.clicked.connect(lambda: self._shift_day_room_page(-1))
        self.day_room_next_btn.clicked.connect(lambda: self._shift_day_room_page(1))

        # View change event connection
        self.view_cb.currentIndexChanged.connect(self._on_view_changed)

        # Date change triggers
        self.day_date.dateChanged.connect(self._on_date_changed)

        # Initial state setup
        self._init_default_dates()
        self._on_view_changed()
        self.refresh(emit=False)
        self._emit_enabled = True

        # Set object names for styling
        self.day_date.setObjectName("DateEdit")
        self.view_cb.setObjectName("HeaderCombo")


    def reload_and_refresh_everything(self) -> None:
        self.refresh(emit=True)

    def _apply_planner_table_palette(self, table: QTableWidget) -> None:
        pal = QPalette(table.palette())
        pal.setColor(QPalette.Highlight, QColor(0, 0, 0, 0))
        pal.setColor(QPalette.HighlightedText, qss_color("planner-text"))
        table.setPalette(pal)

    def _qdate_to_pydate(self, qd: QDate) -> date:
        return date(qd.year(), qd.month(), qd.day())

    def _shift_period(self, direction: int):
        view = str(self.view_cb.currentData())
        current = self._qdate_to_pydate(self.day_date.date())
        if view == "day":
            new_date = current + timedelta(days=direction)
        elif view == "month":
            month_index = (current.month - 1) + direction
            year = current.year + (month_index // 12)
            month = (month_index % 12) + 1
            day = min(current.day, calendar.monthrange(year, month)[1])
            new_date = current.replace(year=year, month=month, day=day)
        else:
            new_date = current + timedelta(days=7 * direction)

        self.day_date.setDate(date_to_qdate(new_date))

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
            return

        min_d = min(dated)
        self.day_date.setDate(date_to_qdate(min_d))


    def current_filters(self):
        # getattr wird verwendet, falls _global_filter noch nicht gesetzt wurde
        gf = getattr(self, "_global_filter", None)
        if gf is None:
            return {
                "raum_id": None,
                "gebaeude": None,
                "lva_id": None,
                "typ": None,
                "dozent": None,
                "studienrichtung": None,
                "semester_id": None,
                "studiensemester": None,
                "zu_besprechen": False,
            }
        return {
            "raum_id": gf.raum_id,
            "gebaeude": getattr(gf, "gebaeude", None),
            "lva_id": gf.lva_id,
            "typ": gf.typ,
            "dozent": getattr(gf, "dozent", None),
            "studienrichtung": getattr(gf, "studienrichtung", None),
            "semester_id": getattr(gf, "semester", None),
            "studiensemester": getattr(gf, "studiensemester", None),
            "zu_besprechen": bool(getattr(gf, "zu_besprechen", False)),
        }

    def refresh(self, emit: bool = True):
        self.state.reload()

        filters = self.current_filters()
        filters_for_planner = self._filters_for_display(filters)
        filtered = self.state.filtered_termine(
            raum_id=filters_for_planner["raum_id"],
            lva_id=filters_for_planner["lva_id"],
            typ=filters_for_planner["typ"],
            dozent=filters_for_planner["dozent"],
            studienrichtung=filters_for_planner["studienrichtung"],
            semester_id=filters_for_planner["semester_id"],
            studiensemester=filters_for_planner["studiensemester"],
            zu_besprechen=filters_for_planner["zu_besprechen"],
        )
        if filters_for_planner.get("gebaeude") and not filters_for_planner.get("raum_id"):
            filtered = self._filter_terms_by_building(filtered, filters_for_planner["gebaeude"])
        expanded = expand_termine(filtered)

        view = str(self.view_cb.currentData())
        if view == "day":
            self.stack.setCurrentWidget(self.day_container)
            rooms = self._day_rooms_for_filters(filters)
            rooms = self._paged_day_rooms(rooms, bool(filters["raum_id"]))
            self.day_view.refresh(expanded, rooms)
        elif view == "week":
            self.day_room_pager.setVisible(False)
            self.stack.setCurrentWidget(self.week_table)
            self.week_view.refresh(expanded)
        elif view == "month":
            self.day_room_pager.setVisible(False)
            self.stack.setCurrentWidget(self.month_container)
            self.month_view.refresh(expanded)
        else:
            self.day_room_pager.setVisible(False)
            self.stack.setCurrentWidget(self.week_table)
            self.week_view.refresh(expanded)

        if emit and self._emit_enabled and callable(self.on_data_changed):
            self.on_data_changed()

    def set_previous_year_enabled(self, enabled: bool, *, refresh: bool = True) -> None:
        self._previous_year_enabled = bool(enabled)
        self._apply_history_read_only()
        if refresh:
            self.refresh(emit=False)

    def _apply_history_read_only(self) -> None:
        read_only = bool(self._previous_year_enabled)
        for view in (self.day_view, self.week_view, self.month_view):
            if hasattr(view, "set_read_only"):
                view.set_read_only(read_only)

    def _filters_for_display(self, filters: dict) -> dict:
        out = dict(filters)
        if self._previous_year_enabled and out.get("semester_id"):
            out["semester_id"] = self._previous_semester_id(out["semester_id"])
        return out

    @staticmethod
    def _previous_semester_id(semester_id: str) -> str:
        match = re.match(r"^(SS|WS)[\s_-]?(\d{2}|\d{4})$", str(semester_id or "").strip(), re.IGNORECASE)
        if not match:
            return semester_id
        kind = match.group(1).upper()
        raw_year = match.group(2)
        year = int(raw_year) if len(raw_year) == 4 else 2000 + int(raw_year)
        return f"{kind}{(year - 1) % 100:02d}"

    def _on_view_changed(self):
        # view switching should not refresh external docks/terminliste
        self.refresh(emit=False)

    def _day_rooms_for_filters(self, filters) -> list:
        rooms = self.state.raeume
        if filters.get("gebaeude"):
            rooms = [
                r for r in rooms
                if str(getattr(r, "gebaeude", "") or "").strip() == filters["gebaeude"]
            ]
        if filters["raum_id"]:
            return [r for r in rooms if r.id == filters["raum_id"]]
        return rooms

    def _filter_terms_by_building(self, termine: list, gebaeude: str) -> list:
        room_by_id = {str(room.id): room for room in self.state.raeume}
        return [
            termin for termin in termine
            if str(getattr(room_by_id.get(str(termin.raum_id)), "gebaeude", "") or "").strip() == gebaeude
        ]

    def _paged_day_rooms(self, rooms: list, has_room_filter: bool) -> list:
        total = len(rooms)
        page_size = self._day_room_page_size()
        show_pager = not has_room_filter and total > page_size

        if not show_pager:
            self._day_room_page = 0
            self.day_room_pager.setVisible(False)
            return rooms

        page_count = max(1, (total + page_size - 1) // page_size)
        self._day_room_page = max(0, min(self._day_room_page, page_count - 1))
        start = self._day_room_page * page_size
        end = min(start + page_size, total)

        self.day_room_pager.setVisible(True)
        self.day_room_label.setText(f"Räume {start + 1}-{end} von {total}")
        self.day_room_prev_btn.setEnabled(self._day_room_page > 0)
        self.day_room_next_btn.setEnabled(end < total)
        return rooms[start:end]

    def _day_room_page_size(self) -> int:
        try:
            value = int(self.state.settings.get("day_room_page_size", 8))
        except Exception:
            value = 8
        return max(4, min(24, value))

    def _shift_day_room_page(self, direction: int) -> None:
        self._day_room_page = max(0, self._day_room_page + direction)
        self.refresh(emit=False)

    def _show_day_room_page_for_room(self, room_id: str) -> None:
        if not room_id or self.current_filters().get("raum_id"):
            return
        for idx, room in enumerate(self.state.raeume):
            if room.id == room_id:
                self._day_room_page = idx // self._day_room_page_size()
                return

    def _edit_termin_by_id(self, tid: str):
        if self._previous_year_enabled:
            self._show_history_read_only_toast()
            return
        if self.crud.edit_termin_by_id(tid):
            self.reload_and_refresh_everything()

    def _show_history_read_only_toast(self) -> None:
        cb = getattr(self.window(), "_show_history_read_only_toast", None)
        if callable(cb):
            cb()

    def set_global_filter_state(self, fs) -> None:
        old_room_id = getattr(getattr(self, "_global_filter", None), "raum_id", None)
        new_room_id = getattr(fs, "raum_id", None) if fs is not None else None
        if old_room_id != new_room_id:
            self._day_room_page = 0

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

        self._show_day_room_page_for_room(getattr(t, "raum_id", ""))
        self.day_date.setDate(date_to_qdate(t.datum))

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
        if self._previous_year_enabled:
            self._show_history_read_only_toast()
            return
        if self.crud.move_termin(termin_id, **kwargs):
            self.reload_and_refresh_everything()
