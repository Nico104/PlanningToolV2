from datetime import date, time, timedelta, datetime
from typing import List, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QDateEdit, QHeaderView, QSizePolicy

from ...core.models import Termin
from ..utils.datetime_utils import qdate_to_date, monday_of, fmt_time, mins_from_time
from ..utils.color_constants import TYPE_COLORS, DEFAULT_BG, DEFAULT_FG
from .state import PlannerState
from ..utils.datetime_utils import date_to_qdate
from .cell import TimeSlotCell, TerminCard



class PlannerWeekView:
    """
    Shows a week grid (Mo-Sa) with time slots as rows
    Supports dropping a Termin onto a cell
    """

    def __init__(
        self,
        state: PlannerState,
        week_table: QTableWidget,
        week_from: QDateEdit,
        edit_by_id_cb: Callable[[str], None],
        on_drop_cb: Callable[[str, date, time], None],
    ):
        self.state = state
        self.week_table = week_table
        self.week_from = week_from
        self.edit_by_id_cb = edit_by_id_cb
        self.on_drop_cb = on_drop_cb

        if hasattr(self.week_table, "terminDropped"):
            self.week_table.terminDropped.connect(self._on_termin_dropped)
        if hasattr(self.week_table, "set_duration_preview_provider"):
            slot_min = int(self.state.settings.get("time_slot_minutes", 30))
            def _dur_provider(tid: str) -> int:
                t = next((tt for tt in self.state.termine if tt.id == tid), None)
                return int(t.duration) if t else 0
            self.week_table.set_duration_preview_provider(_dur_provider, slot_min)
        if hasattr(self.week_table, "set_color_provider"):
            def _color_provider(tid: str) -> QColor:
                t = next((tt for tt in self.state.termine if tt.id == tid), None)
                if t:
                    typ = (t.typ or "").strip().upper()
                    for k, color in TYPE_COLORS:
                        if typ == k:
                            return color
                return DEFAULT_BG
            self.week_table.set_color_provider(_color_provider)
        if hasattr(self.week_table, "set_text_provider"):
            def _text_provider(tid: str) -> str:
                t = next((tt for tt in self.state.termine if tt.id == tid), None)
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

        self._setup_table()
        self.week_table.cellClicked.connect(self._on_cell_clicked)

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

    def _setup_table(self) -> None:
        t = self.week_table
        t.setWordWrap(True)
        t.setTextElideMode(Qt.ElideRight)

        t.setShowGrid(True)
        t.verticalHeader().setVisible(False)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        t.setSizeAdjustPolicy(QTableWidget.AdjustToContentsOnFirstShow)

        h = t.horizontalHeader()
        v = t.verticalHeader()
        h.setStretchLastSection(False)
        v.setSectionResizeMode(QHeaderView.Fixed)
        
        self.week_table.verticalHeader().setDefaultSectionSize(26)


    def refresh(self, filtered_termine: List[Termin]) -> None:
        week_mo = monday_of(qdate_to_date(self.week_from.date()))
        week_su = week_mo + timedelta(days=6)

        # keep Mo–Sa only
        terms = [
            t for t in filtered_termine
            if t.datum is not None
            and week_mo <= t.datum <= week_su
            and t.datum.weekday() <= 5
        ]

        self._build_week_table(week_mo, terms)

    def _build_week_table(self, week_mo: date, terms: List[Termin]) -> None:
        # store current week monday on table (handy in other places)
        if hasattr(self.week_table, "week_monday_qdate"):
            self.week_table.week_monday_qdate = date_to_qdate(week_mo)

        days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa"]
        slots = self._time_slots()
        slot_min = self._day_bounds()[2]

        # Build header labels with styled date
        header_labels = ["Zeit"]
        for i, day in enumerate(days):
            day_date = week_mo + timedelta(days=i)
            # Use line break for styling via QSS
            header_labels.append(f"{day}\n{day_date.strftime('%d.%m.%Y')}")

        # Clear all cell widgets before rebuilding
        for row in range(self.week_table.rowCount()):
            for col in range(self.week_table.columnCount()):
                widget = self.week_table.cellWidget(row, col)
                if widget:
                    self.week_table.removeCellWidget(row, col)
                    widget.deleteLater()

        self.week_table.clearSpans()

        self.week_table.setRowCount(len(slots))
        self.week_table.setColumnCount(1 + len(days))
        self.week_table.setHorizontalHeaderLabels(header_labels)

        #time column compact, days stretch
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
        by_day = []
        for t in terms:
            found = next((bd for bd in by_day if bd[0] == t.datum), None)
            if found:
                found[1].append(t)
            else:
                by_day.append([t.datum, [t]])
        from datetime import time as _time
        for bd in by_day:
            bd[1].sort(key=lambda x: x.start_zeit if x.start_zeit is not None else _time(0, 0))

        for col in range(6):
            d0 = week_mo + timedelta(days=col)
            found = next((bd for bd in by_day if bd[0] == d0), None)
            items = found[1] if found else []

            if not items:
                continue

            # Group overlapping
            appointment_groups = self._group_concurrent_appointments(items, slots)

            groups_by_id = []
            for termin, group_id in appointment_groups:
                found = next((g for g in groups_by_id if g[0] == group_id), None)
                if found:
                    found[1].append(termin)
                else:
                    groups_by_id.append([group_id, [termin]])

            for group in groups_by_id:
                group_id, group_appointments = group
                valid_apps = [
                    app for app in group_appointments
                    if isinstance(app.start_zeit, time)
                    and app.get_end_time() is not None
                ]
                if not valid_apps:
                    continue

                group_start_min = min(mins_from_time(app.start_zeit) for app in valid_apps)
                group_end_min = max(mins_from_time(app.get_end_time()) for app in valid_apps)

                if group_end_min <= group_start_min:
                    continue

                start_t = time(hour=group_start_min // 60, minute=group_start_min % 60)
                if start_t not in slots:
                    continue

                row = slots.index(start_t)
                col_idx = 1 + col

                total_dur = group_end_min - group_start_min
                max_span = max(1, (total_dur + slot_min - 1) // slot_min)
                max_span = min(max_span, len(slots) - row)

                cell_widget = TimeSlotCell(d0)
                self.week_table.setCellWidget(row, col_idx, cell_widget)

                if max_span > 1:
                    try:
                        self.week_table.setSpan(row, col_idx, max_span, 1)
                    except:
                        pass

                row_height = self.week_table.rowHeight(row)
                cell_widget.set_grid_info(row_height, max_span)

                for app in valid_apps:
                    app_start = mins_from_time(app.start_zeit)
                    app_end = mins_from_time(app.get_end_time())
                    if app_end <= app_start:
                        continue

                    offset_rows = max(0, (app_start - group_start_min) // slot_min)
                    app_dur = app_end - app_start
                    app_span_rows = max(1, (app_dur + slot_min - 1) // slot_min)
                    app_span_rows = min(app_span_rows, len(slots) - row - offset_rows)

                    app_text = self._format_termin_text(app)
                    typ = (app.typ or "").strip().upper()
                    bg = DEFAULT_BG
                    for k, color in TYPE_COLORS:
                        if typ == k:
                            bg = color
                            break
                    card = TerminCard(app.id, app_text, bg, self.week_table)
                    card.doubleClicked.connect(self.edit_by_id_cb)

                    card_pixel_height = app_span_rows * row_height
                    border_px = 1
                    inner_height = max(1, card_pixel_height - (2 * border_px))
                    card.setFixedHeight(inner_height)
                    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

                    top_offset_px = offset_rows * row_height
                    cell_widget.add_termin_card(card, top_offset_px=top_offset_px)



    def _on_cell_clicked(self, row: int, col: int) -> None:
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

    def _group_concurrent_appointments(self, items: List[Termin], slots: List[time]) -> List[tuple]:
        """
        Group appointments by time overlap.
        Returns list of (termin, group_id) tuples.
        All appointments with the same group_id overlap with each other.
        """
        if not items:
            return []
        
        sorted_items = sorted(
            items,
            key=lambda x: mins_from_time(x.start_zeit) if x.start_zeit else 0
        )

        groups: List[tuple] = []
        group_counter = 0
        current_group: List[Termin] = []
        current_end = None

        for t in sorted_items:
            if not t.start_zeit or not t.get_end_time():
                continue

            t_start = mins_from_time(t.start_zeit)
            t_end = mins_from_time(t.get_end_time())

            if current_end is None:
                current_group = [t]
                current_end = t_end
                continue

            if t_start < current_end:
                current_group.append(t)
                current_end = max(current_end, t_end)
            else:
                for member in current_group:
                    groups.append((member, group_counter))
                group_counter += 1
                current_group = [t]
                current_end = t_end

        if current_group:
            for member in current_group:
                groups.append((member, group_counter))

        return groups

    def _format_termin_text(self, t: Termin) -> str:
        end_raw = t.get_end_time()
        lva = next((l for l in self.state.lvas if l.id == t.lva_id), None)
        lva_short = f"{t.lva_id}" + ("" if not lva else f" {lva.name}")
        room_s = f"{t.raum_id}"
        gname = (t.gruppe.name if t.gruppe else "")
        grp = "" if (not gname or gname == "-") else f" Gr.{gname}"
        ap = " AP" if t.anwesenheitspflicht else ""

        return (
            f"{fmt_time(t.start_zeit)}–{fmt_time(end_raw)} "
            f"{t.typ} | {room_s} | {lva_short}{grp}{ap}"
        )

    def _on_termin_dropped(self, termin_id: str, row: int, col: int) -> None:
        # col 0 ist Zeit-Spalte
        if col <= 0:
            return

        week_mo = monday_of(qdate_to_date(self.week_from.date()))
        day_offset = col - 1  # Mo..Sa
        target_date = week_mo + timedelta(days=day_offset)

        slots = self._time_slots()
        if row < 0 or row >= len(slots):
            return
        target_start = slots[row]

        # View macht NUR callback (Workspace entscheidet Speichern + Reload + Refresh)
        self.on_drop_cb(str(termin_id), target_date, target_start)
