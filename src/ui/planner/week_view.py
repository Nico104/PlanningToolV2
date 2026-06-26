from collections import defaultdict
from datetime import date, time, timedelta, datetime
from typing import List, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QDateEdit, QHeaderView

from ...core.models import Termin
from ...services.conflict_service import has_preview_conflict
from ..utils.datetime_utils import qdate_to_date, monday_of, fmt_time
from ..utils.color_constants import type_color_for
from .state import PlannerState
from .timeslotcell import TimeSlotCell
from .termincard import TerminCard
from .free_day_provider import FreeDayProvider
from .render_helpers import FreeDayHeaderView, render_grouped_termine_column, week_day_accent_color


class PlannerWeekView:
    """
    Shows a week grid with time slots as rows
    Supports dropping a Termin onto a cell
    """

    def __init__(
        self,
        state: PlannerState,
        week_table: QTableWidget,
        day_date: QDateEdit,
        free_day_provider: FreeDayProvider,
        edit_by_id_cb: Callable[[str], None],
        on_drop_cb: Callable[[str, date, time], None],
    ):
        self.state = state
        self.week_table = week_table
        self.day_date = day_date
        self._free_day_provider = free_day_provider
        self.edit_by_id_cb = edit_by_id_cb
        self.on_drop_cb = on_drop_cb
        self._read_only = False

        if hasattr(self.week_table, "terminDropped"):
            self.week_table.terminDropped.connect(self._on_termin_dropped)
        if hasattr(self.week_table, "set_duration_preview_provider"):
            slot_min = int(self.state.settings.get("time_slot_minutes", 30))
            def _dur_provider(tid: str) -> int:
                t = self.state.termin_map.get(str(tid))
                return int(t.duration) if t else 0
            self.week_table.set_duration_preview_provider(_dur_provider, slot_min)
        if hasattr(self.week_table, "set_color_provider"):
            def _color_provider(tid: str) -> QColor:
                t = self.state.termin_map.get(str(tid))
                if t:
                    return type_color_for(t.typ)
                return type_color_for("")
            self.week_table.set_color_provider(_color_provider)
        if hasattr(self.week_table, "set_text_provider"):
            def _text_provider(tid: str) -> str:
                t = self.state.termin_map.get(str(tid))
                if not t or not t.start_zeit or not t.get_end_time():
                    return ""
                lva = next((l for l in self.state.lvas if l.id == t.lva_id), None)
                lva_short = f"{t.lva_id}" + ("" if not lva else f" {lva.name}")
                room_s = f"{t.raum_id}"
                gname = (t.gruppe.name if t.gruppe else "")
                grp = "" if (not gname or gname == "-") else f" Gr.{gname}"
                ap = " AP" if t.anwesenheitspflicht else ""
                return f"{fmt_time(t.start_zeit)}–{fmt_time(t.get_end_time())} {t.typ} | {room_s} | {lva_short}{grp}{ap}"
            self.week_table.set_text_provider(_text_provider)
        if hasattr(self.week_table, "set_conflict_checker"):
            def _conflict_checker_week(tid: str, row: int, col: int) -> bool:
                if not bool(self.state.settings.get("dynamic_drag_conflict_preview", True)):
                    return False
                if col <= 0:
                    return False
                week_mo = self._current_week_monday()
                target_date = week_mo + timedelta(days=col - 1)
                day_start, _, slot_min = self._day_bounds()
                start_mins = day_start.hour * 60 + day_start.minute + row * slot_min
                return has_preview_conflict(
                    termine=self.state.termine,
                    lvas=self.state.lvas,
                    raeume=self.state.raeume,
                    termin_id=tid,
                    target_date=target_date,
                    start_mins=start_mins,
                    default_slot_mins=slot_min,
                    target_raum_id=None,
                    use_dragged_room=True,
                    data_dir=self.state.ds.data_dir,
                )
            self.week_table.set_conflict_checker(_conflict_checker_week)

        self._setup_table()
        self.week_table.cellClicked.connect(self._on_cell_clicked)
        self._free_days_by_date = {}

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        if hasattr(self.week_table, "set_read_only"):
            self.week_table.set_read_only(self._read_only)

    def _day_bounds(self) -> tuple[time, time, int]:
        s = self.state.settings
        day_start = datetime.strptime(s.get("day_start", "08:00"), "%H:%M").time()
        day_end = datetime.strptime(s.get("day_end", "20:00"), "%H:%M").time()
        slot = int(s.get("time_slot_minutes", 30))
        return day_start, day_end, slot

    def _time_slots(self) -> List[time]:
        day_start, day_end, slot_min = self._day_bounds()
        slots: List[time] = []
        start = day_start.hour * 60 + day_start.minute
        end = day_end.hour * 60 + day_end.minute
        for m in range(start, end, slot_min):
            slots.append(time(hour=m // 60, minute=m % 60))
        return slots

    def _current_week_monday(self) -> date:
        return monday_of(qdate_to_date(self.day_date.date()))

    def _setup_table(self) -> None:
        t = self.week_table
        t.setWordWrap(True)
        t.setTextElideMode(Qt.ElideRight)
        t.setSelectionMode(QTableWidget.NoSelection)
        t.setFocusPolicy(Qt.NoFocus)

        t.setShowGrid(False)
        t.verticalHeader().setVisible(False)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        t.setSizeAdjustPolicy(QTableWidget.AdjustToContentsOnFirstShow)

        if not isinstance(t.horizontalHeader(), FreeDayHeaderView):
            t.setHorizontalHeader(FreeDayHeaderView(Qt.Horizontal, t))

        h = t.horizontalHeader()
        v = t.verticalHeader()
        h.setStretchLastSection(False)
        v.setSectionResizeMode(QHeaderView.Stretch)


    def refresh(self, filtered_termine: List[Termin]) -> None:
        week_mo = self._current_week_monday()
        week_su = week_mo + timedelta(days=6)
        self._free_days_by_date = self._free_day_provider.get_infos_for_range(week_mo, week_su)
        show_weekend = self.state.settings.get("show_weekend", True)
        max_weekday = 6 if show_weekend else 4

        terms = [
            t for t in filtered_termine
            if t.datum is not None
            and week_mo <= t.datum <= week_su
            and t.datum.weekday() <= max_weekday
        ]

        self._build_week_table(week_mo, terms)

    def _build_week_table(self, week_mo: date, terms: List[Termin]) -> None:
        """
        Populate the week table for the configured visible week starting at week_mo (Monday).

        Layout:
        - Column 0: time labels (read-only)
        - Columns 1..N: visible weekdays, optionally including weekend
        - Rows: one row per time slot
        - Free days: compact badge inside the day header
        """
        show_weekend = self.state.settings.get("show_weekend", True)
        days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"] if show_weekend else ["Mo", "Di", "Mi", "Do", "Fr"]
        slots = self._time_slots()
        slot_min = self._day_bounds()[2]

        header_labels = ["Zeit"]
        free_day_badges: dict[int, tuple[str, str, str]] = {}
        header_accents = {}
        header_tooltips = {}
        visible_term_counts_by_day = defaultdict(int)
        grid_start_min = slots[0].hour * 60 + slots[0].minute if slots else 0
        grid_end_min = (
            slots[-1].hour * 60 + slots[-1].minute + slot_min
            if slots
            else grid_start_min
        )
        for termin in terms:
            end_time = termin.get_end_time()
            start_time = termin.start_zeit
            if (
                termin.datum is not None
                and start_time is not None
                and end_time is not None
                and (end_time.hour * 60 + end_time.minute) > grid_start_min
                and (start_time.hour * 60 + start_time.minute) < grid_end_min
            ):
                visible_term_counts_by_day[termin.datum] += 1

        for i, day in enumerate(days):
            day_date = week_mo + timedelta(days=i)
            header_labels.append(f"{day}\n{day_date.strftime('%d.%m.%Y')}")
            day_info = self._free_days_by_date.get(day_date)
            day_type = day_info.day_type if day_info else None
            term_count = visible_term_counts_by_day.get(day_date, 0)
            accent = week_day_accent_color(term_count)
            if accent is not None:
                header_accents[1 + i] = accent
            tooltip_lines = [
                f"{day}, {day_date.strftime('%d.%m.%Y')}",
                f"{term_count} sichtbare Termin(e)",
            ]
            badge_label = self._free_day_provider.badge_for_info(day_info)
            if day_type in {"feiertag", "vorlesungsfrei"} and badge_label:
                free_day_badges[1 + i] = (
                    badge_label,
                    day_type,
                    self._free_day_provider.label_for_info(day_info),
                )
                tooltip_lines.append(self._free_day_provider.label_for_info(day_info))
            header_tooltips[1 + i] = "\n".join(tooltip_lines)

        # Clear all cell widgets before rebuilding
        for row in range(self.week_table.rowCount()):
            for col in range(self.week_table.columnCount()):
                widget = self.week_table.cellWidget(row, col)
                if widget:
                    self.week_table.removeCellWidget(row, col)
                    widget.deleteLater()

        self.week_table.clearSpans()
        self.week_table.clearContents()

        self.week_table.setRowCount(len(slots))
        self.week_table.setColumnCount(1 + len(days))
        self.week_table.setHorizontalHeaderLabels(header_labels)

        header = self.week_table.horizontalHeader()
        if isinstance(header, FreeDayHeaderView):
            header.set_section_accent_colors(header_accents)
            header.set_free_day_badges(free_day_badges)
        for section, tooltip in header_tooltips.items():
            hdr_item = self.week_table.horizontalHeaderItem(section)
            if hdr_item is not None:
                hdr_item.setToolTip(tooltip)

        h = self.week_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for c in range(1, 1 + len(days)):
            h.setSectionResizeMode(c, QHeaderView.Stretch)

        # time column
        for r, tt in enumerate(slots):
            it = QTableWidgetItem(f"{tt.hour:02d}:{tt.minute:02d}")
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignTop)
            self.week_table.setItem(r, 0, it)
        

        # render existing Termine into grid as blocks
        by_day = defaultdict(list)
        for t in terms:
            by_day[t.datum].append(t)
        for day_items in by_day.values():
            day_items.sort(key=lambda x: x.start_zeit if x.start_zeit is not None else time(0, 0))

        for col in range(len(days)):
            d0 = week_mo + timedelta(days=col)
            items = by_day.get(d0, [])

            if not items:
                continue

            render_grouped_termine_column(
                table=self.week_table,
                target_date=d0,
                col_idx=1 + col,
                items=items,
                slots=slots,
                slot_min=slot_min,
                lvas=self.state.lvas,
                edit_by_id_cb=self.edit_by_id_cb,
                card_parent=self.week_table,
                border_px=2,
                sort_group_ids=True,
                read_only=self._read_only,
            )

    def _on_cell_clicked(self, row: int, col: int) -> None:
        self.week_table.clearSelection()
        self.week_table.setCurrentCell(-1, -1)
        # Clear focus when clicking empty calendar cells
        if col <= 0:
            TerminCard.clear_global_focus()
            return
        cell_widget = self.week_table.cellWidget(row, col)
        if isinstance(cell_widget, TimeSlotCell):
            if not cell_widget.get_termin_ids():
                TerminCard.clear_global_focus()
        else:
            TerminCard.clear_global_focus()

    def _on_termin_dropped(self, termin_id: str, row: int, col: int) -> None:
        if self._read_only:
            return
        # col 0 ist Zeit-Spalte
        if col <= 0:
            return

        week_mo = self._current_week_monday()
        day_offset = col - 1  # Mo..Sa
        target_date = week_mo + timedelta(days=day_offset)

        slots = self._time_slots()
        if row < 0 or row >= len(slots):
            return
        target_start = slots[row]

        # View macht NUR callback
        self.on_drop_cb(str(termin_id), target_date, target_start)
