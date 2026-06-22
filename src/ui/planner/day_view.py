from datetime import date, time, datetime
from collections import defaultdict
from typing import List, Optional, Tuple, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QDateEdit, QHeaderView

from ...core.models import Raum, Termin
from ...services.conflict_service import has_preview_conflict
from ..utils.datetime_utils import qdate_to_date, fmt_time, date_to_qdate
from ..utils.color_constants import type_color_for
from .state import PlannerState
from .timeslotcell import TimeSlotCell
from .termincard import TerminCard
from .free_day_provider import FreeDayProvider
from .render_helpers import FreeDayHeaderView, render_grouped_termine_column, section_accent_color


class PlannerDayView:
    """
    Shows a day grid with time slots as rows and rooms as columns
    Supports drag & drop and overlapping appointments
    """

    def __init__(
        self,
        state: PlannerState,
        day_table: QTableWidget,
        day_date: QDateEdit,
        free_day_provider: FreeDayProvider,
        edit_by_id_cb: Callable[[str], None],
        on_drop_cb: Callable[[str, date, time, Optional[str]], None],
    ):
        self.state = state
        self.day_table = day_table
        self.day_date = day_date
        self._free_day_provider = free_day_provider
        self.edit_by_id_cb = edit_by_id_cb
        self.on_drop_cb = on_drop_cb
        self._read_only = False
        
        self._room_list: List[Raum] = []

        if hasattr(self.day_table, "terminDropped"):
            self.day_table.terminDropped.connect(self._on_termin_dropped)
        if hasattr(self.day_table, "set_duration_preview_provider"):
            def _dur_provider(tid: str) -> int:
                t = self.state.termin_map.get(str(tid))
                return int(t.duration) if t else 0
            slot_min = int(self.state.settings.get("time_slot_minutes", 30))
            self.day_table.set_duration_preview_provider(_dur_provider, slot_min)
        if hasattr(self.day_table, "set_color_provider"):
            def _color_provider(tid: str) -> QColor:
                t = self.state.termin_map.get(str(tid))
                if t:
                    return type_color_for(t.typ)
                return type_color_for("")
            self.day_table.set_color_provider(_color_provider)
        if hasattr(self.day_table, "set_text_provider"):
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
            self.day_table.set_text_provider(_text_provider)
        if hasattr(self.day_table, "set_conflict_checker"):
            def _conflict_checker_day(tid: str, row: int, col: int) -> bool:
                if col <= 0 or not self._room_list or col > len(self._room_list):
                    return False
                target_raum_id = self._room_list[col - 1].id
                target_date = qdate_to_date(self.day_date.date())
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
                    target_raum_id=target_raum_id,
                    use_dragged_room=False,
                    data_dir=self.state.ds.data_dir,
                )
            self.day_table.set_conflict_checker(_conflict_checker_day)

        self._setup_table()
        self.day_table.cellClicked.connect(self._on_cell_clicked)

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        if hasattr(self.day_table, "set_read_only"):
            self.day_table.set_read_only(self._read_only)

    def _setup_table(self) -> None:
        t = self.day_table
        t.setWordWrap(True)
        t.setTextElideMode(Qt.ElideRight)

        t.setShowGrid(False)
        t.verticalHeader().setVisible(False)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        t.setSizeAdjustPolicy(QTableWidget.AdjustToContentsOnFirstShow)
        if not isinstance(t.horizontalHeader(), FreeDayHeaderView):
            t.setHorizontalHeader(FreeDayHeaderView(Qt.Horizontal, t))
        self.day_table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

    # Get day bounds and slot size from settings
    def _day_bounds(self) -> Tuple[time, time, int]:
        s = self.state.settings
        day_start = datetime.strptime(s.get("day_start", "08:00"), "%H:%M").time()
        day_end = datetime.strptime(s.get("day_end", "18:00"), "%H:%M").time()
        slot = int(s.get("time_slot_minutes", 30))
        return day_start, day_end, slot

    # Generate list of time slots based on settings
    def _time_slots(self) -> List[time]:
        day_start, day_end, slot_min = self._day_bounds()
        slots: List[time] = []
        start = day_start.hour * 60 + day_start.minute
        end = day_end.hour * 60 + day_end.minute
        for m in range(start, end, slot_min):
            slots.append(time(hour=m // 60, minute=m % 60))
        return slots

    # Refresh table for current day and filters
    def refresh(self, filtered_termine: List[Termin], rooms: List[Raum]) -> None:
        assert self.state.ts is not None

        d = qdate_to_date(self.day_date.date())
        terms_day = [t for t in filtered_termine if t.datum == d]
        free_day_info = self._free_day_provider.get_info_for_date(d)
        self._build_day_grid(rooms, terms_day, d, free_day_info)

    # Build the day grid: rows=time slots, columns=rooms
    def _build_day_grid(self, rooms: List[Raum], terms: List[Termin], d: date, free_day_info) -> None:
        """
        Populate the day table with time-slot rows and room columns for the given date.

        Layout:
        - Column 0: time labels (read-only, right-aligned)
        - Columns 1..N: one column per room
        - Rows: one row per slot
        - Free days: compact badge inside the header
        """
        assert self.state.ts is not None

        slots = self._time_slots()

        for row in range(self.day_table.rowCount()):
            for col in range(self.day_table.columnCount()):
                widget = self.day_table.cellWidget(row, col)
                if widget:
                    self.day_table.removeCellWidget(row, col)
                    widget.deleteLater()

        self.day_table.clearSpans()
        self.day_table.clearContents()

        self.day_table.setRowCount(len(slots))
        self.day_table.setColumnCount(1 + len(rooms))
        headers = ["Zeit"] + [f"{r.id}\n{r.name}" for r in rooms]

        self.day_table.setHorizontalHeaderLabels(headers)
        self.day_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.day_table.horizontalHeader().setMinimumHeight(44)
        for idx, room in enumerate(rooms, start=1):
            hdr_item = self.day_table.horizontalHeaderItem(idx)
            if hdr_item is not None:
                tooltip_lines = [
                    f"{room.id} – {room.name}",
                    f"Kapazität: {room.kapazitaet}",
                ]
                building = str(getattr(room, "gebaeude", "") or "").strip()
                if building:
                    tooltip_lines.append(f"Gebäude: {building}")
                hdr_item.setToolTip("\n".join(tooltip_lines))

        # header sizing: time column fixed, rooms stretch
        h = self.day_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for c in range(1, 1 + len(rooms)):
            h.setSectionResizeMode(c, QHeaderView.Stretch)

        # time column
        for r, tt in enumerate(slots):
            it = QTableWidgetItem(f"{tt.hour:02d}:{tt.minute:02d}")
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignTop)
            self.day_table.setItem(r, 0, it)

        free_day_badges: dict[int, tuple[str, str, str]] = {}
        if free_day_info:
            free_day_type = free_day_info.day_type
            day_label = self._free_day_provider.label_for_info(free_day_info)
            badge_label = self._free_day_provider.badge_for_info(free_day_info)

            time_hdr = self.day_table.horizontalHeaderItem(0)
            if time_hdr is not None:
                time_hdr.setToolTip(day_label)
            for c in range(1, 1 + len(rooms)):
                hdr_item = self.day_table.horizontalHeaderItem(c)
                if hdr_item is not None:
                    room_tip = hdr_item.toolTip().strip()
                    hdr_item.setToolTip(f"{room_tip}\n{day_label}" if room_tip else day_label)
                if free_day_type in {"feiertag", "vorlesungsfrei"} and badge_label:
                    free_day_badges[c] = (badge_label, free_day_type, day_label)

        header = self.day_table.horizontalHeader()
        if isinstance(header, FreeDayHeaderView):
            header.set_section_accent_colors(
                {
                    idx: section_accent_color(
                        str(getattr(room, "gebaeude", "") or "").strip()
                        or room.id
                        or room.name
                    )
                    for idx, room in enumerate(rooms, start=1)
                }
            )
            header.set_free_day_badges(free_day_badges)

        if hasattr(self.day_table, "current_day_qdate"):
            self.day_table.current_day_qdate = date_to_qdate(d)

        room_index = {r.id: idx for idx, r in enumerate(rooms)}
        
        # Store room list for drop handler
        self._room_list = rooms

        by_room = defaultdict(list)
        for t in terms:
            if t.raum_id in room_index:
                by_room[t.raum_id].append(t)

        for items in by_room.values():
            items.sort(key=lambda x: x.start_zeit if x.start_zeit else time(0, 0))

        for room_id, items in by_room.items():
            if not items:
                continue

            render_grouped_termine_column(
                table=self.day_table,
                target_date=d,
                col_idx=1 + room_index[room_id],
                items=items,
                slots=slots,
                slot_min=self._day_bounds()[2],
                lvas=self.state.lvas,
                edit_by_id_cb=self.edit_by_id_cb,
                card_parent=self.day_table,
                border_px=2,
                sort_group_ids=False,
                read_only=self._read_only,
            )

    def _on_cell_clicked(self, row: int, col: int) -> None:
        # Clear focus when clicking empty calendar cells
        if col <= 0:
            TerminCard.clear_global_focus()
            return
        cell_widget = self.day_table.cellWidget(row, col)
        if isinstance(cell_widget, TimeSlotCell):
            if not cell_widget.get_termin_ids():
                TerminCard.clear_global_focus()
        else:
            TerminCard.clear_global_focus()

    def _on_termin_dropped(self, termin_id: str, row: int, col: int) -> None:
        if self._read_only:
            return
        # col 0 is time column
        if col <= 0:
            return

        d = qdate_to_date(self.day_date.date())

        slots = self._time_slots()
        if row < 0 or row >= len(slots):
            return
        target_start = slots[row]
        
        # Determine target room from column
        room_idx = col - 1  # subtract time column
        target_room_id = None
        if 0 <= room_idx < len(self._room_list):
            target_room_id = self._room_list[room_idx].id

        # View only does callback
        self.on_drop_cb(str(termin_id), d, target_start, target_room_id)

