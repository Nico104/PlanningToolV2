from collections import defaultdict
from datetime import date, time
from typing import Callable, Iterable, Sequence

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QHeaderView, QStyle, QStyleOptionHeader, QTableWidget, QSizePolicy

from ...core.models import Termin
from ..utils.datetime_utils import fmt_date, fmt_time, mins_from_time
from ..utils.grouping_utils import group_concurrent_appointments
from ..utils.color_constants import planner_text_color, type_color_for
from ..utils.qss_tokens import qss_color
from .timeslotcell import TimeSlotCell
from .termincard import TerminCard


_SECTION_ACCENT_PALETTE = (
    "#2f80ed",
    "#27ae60",
    "#f2994a",
    "#9b51e0",
    "#eb5757",
    "#00a3a3",
    "#f2c94c",
    "#56ccf2",
)


def section_accent_color(key: str, index: int = 0) -> QColor:
    text = str(key or "")
    seed = sum((pos + 1) * ord(ch) for pos, ch in enumerate(text))
    color = _SECTION_ACCENT_PALETTE[(seed + index) % len(_SECTION_ACCENT_PALETTE)]
    return QColor(color)


def week_day_accent_color(term_count: int) -> QColor | None:
    if term_count >= 6:
        return QColor("#f2994a")
    if term_count >= 3:
        return QColor("#f2c94c")
    if term_count > 0:
        return QColor("#27ae60")
    return None


class FreeDayHeaderView(QHeaderView):
    def __init__(self, orientation: Qt.Orientation, parent=None):
        super().__init__(orientation, parent)
        self._badges: dict[int, tuple[str, str, str]] = {}
        self._accent_colors: dict[int, QColor] = {}

    def set_free_day_badges(self, badges: dict[int, tuple[str, str, str]]) -> None:
        self._badges = dict(badges)
        self.setMinimumHeight(64 if self._badges else 44)
        self.viewport().update()

    def set_section_accent_colors(self, colors: dict[int, QColor]) -> None:
        self._accent_colors = {
            int(section): QColor(color)
            for section, color in colors.items()
            if QColor(color).isValid()
        }
        self.viewport().update()

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        if self._badges:
            hint.setHeight(max(hint.height(), 64))
        return hint

    def paintSection(self, painter, rect, logical_index: int) -> None:
        if not rect.isValid():
            return

        painter.save()

        option = QStyleOptionHeader()
        self.initStyleOption(option)
        option.rect = rect
        option.section = logical_index
        option.text = ""
        self.style().drawControl(QStyle.CE_Header, option, painter, self)

        accent = self._accent_colors.get(logical_index)
        if accent is not None and accent.isValid():
            accent_rect = rect.adjusted(0, 0, 0, -(rect.height() - 5))
            painter.fillRect(accent_rect, accent)

        text = self.model().headerData(logical_index, self.orientation(), Qt.DisplayRole)
        text = "" if text is None else str(text)
        badge = self._badges.get(logical_index)
        text_rect = rect.adjusted(4, 8 if accent else 4, -4, -24 if badge else -4)

        painter.setPen(planner_text_color())
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, text)

        if badge:
            badge_text, day_type, _tooltip = badge
            self._paint_badge(painter, rect, badge_text, day_type)

        painter.restore()

    def _paint_badge(self, painter, section_rect, text: str, day_type: str) -> None:
        badge_rect = section_rect.adjusted(4, section_rect.height() - 24, -4, -4)

        if day_type == "feiertag":
            bg = qss_color("free-day-holiday-badge-bg")
            border = qss_color("free-day-holiday-badge-border")
            fg = qss_color("free-day-holiday-badge-text")
        else:
            bg = qss_color("free-day-lecture-badge-bg")
            border = qss_color("free-day-lecture-badge-border")
            fg = qss_color("free-day-lecture-badge-text")

        painter.setBrush(bg)
        painter.setPen(QPen(border, 0.5))
        painter.drawRoundedRect(badge_rect, 0, 0)

        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(fg)
        metrics = painter.fontMetrics()
        label = metrics.elidedText(text, Qt.ElideRight, max(1, badge_rect.width() - 10))
        painter.drawText(badge_rect.adjusted(5, 0, -5, 0), Qt.AlignLeft | Qt.AlignVCenter, label)


def format_termin_text(t: Termin, lvas) -> str:
    end_raw = t.get_end_time()
    lva = next((l for l in lvas if l.id == t.lva_id), None)
    lva_short = f"{t.lva_id}" + ("" if not lva else f" {lva.name}")
    room_s = f"{t.raum_id}"
    gname = (t.gruppe.name if t.gruppe else "")
    grp = "" if (not gname or gname == "-") else f" Gr.{gname}"
    ap = " AP" if t.anwesenheitspflicht else ""

    return (
        f"{fmt_time(t.start_zeit)}–{fmt_time(end_raw)} "
        f"{t.typ} | {room_s} | {lva_short}{grp}{ap}"
    )


def format_termin_tooltip(t: Termin, lvas) -> str:
    end_raw = t.get_end_time()
    lva = next((l for l in lvas if l.id == t.lva_id), None)
    lva_text = f"{t.lva_id}" + ("" if not lva else f" - {lva.name}")
    room_text = str(t.raum_id or "Kein Raum")
    group_text = t.gruppe.name if t.gruppe else ""

    lines = [
        str(t.name or "(Ohne Titel)"),
        f"ID: {t.id}",
        f"LVA: {lva_text}",
        f"Typ: {t.typ or '-'}",
        f"Datum: {fmt_date(t.datum)}",
        f"Zeit: {fmt_time(t.start_zeit)}-{fmt_time(end_raw)}",
        f"Dauer: {int(t.duration or 0)} min",
        f"Raum: {room_text}",
    ]

    if group_text:
        lines.append(f"Gruppe: {group_text}")
    if getattr(t, "semester_id", ""):
        lines.append(f"Semester: {t.semester_id}")
    if t.anwesenheitspflicht:
        lines.append("Anwesenheitspflicht")
    if t.is_series():
        lines.append(f"Serie: {t.periodizitaet}, bis {fmt_date(t.datum_bis)}")
    if getattr(t, "zu_besprechen", False):
        hint = str(getattr(t, "besprechungshinweis", "") or "").strip()
        lines.append("Zu besprechen" + (f": {hint}" if hint else ""))
    if str(getattr(t, "notiz", "") or "").strip():
        lines.append(f"Notiz: {str(t.notiz).strip()}")

    return "\n".join(lines)


def place_termin_card(
    table: QTableWidget,
    cell_widget: TimeSlotCell,
    card: TerminCard,
    row: int,
    offset_rows: int,
    app_span_rows: int,
    border_px: int = 2,
    top_offset_px_override: int | None = None,
    card_pixel_height_override: int | None = None,
) -> None:
    def rows_height(start_row: int, count: int) -> int:
        return sum(
            max(0, table.rowHeight(start_row + i))
            for i in range(max(0, count))
            if 0 <= start_row + i < table.rowCount()
        )

    inset_px = 1
    top_offset_px = (
        top_offset_px_override
        if top_offset_px_override is not None
        else rows_height(row, offset_rows)
    )
    card_pixel_height = (
        card_pixel_height_override
        if card_pixel_height_override is not None
        else rows_height(row + offset_rows, app_span_rows)
    )
    inner_height = max(1, card_pixel_height - (2 * inset_px))
    card.setFixedHeight(inner_height)
    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    cell_widget.add_termin_card(
        card,
        top_offset_px=top_offset_px + inset_px,
        bottom_margin_px=inset_px,
    )


def render_grouped_termine_column(
    table: QTableWidget,
    target_date: date,
    col_idx: int,
    items: list[Termin],
    slots: Sequence[time],
    slot_min: int,
    lvas: Iterable,
    edit_by_id_cb: Callable[[str], None],
    card_parent,
    border_px: int = 2,
    sort_group_ids: bool = False,
    read_only: bool = False,
) -> None:
    """The function groups concurrent Termine, creates a single TimeSlotCell per group,
    applies row spanning for total group duration, and places each TerminCard at the
    correct vertical offset inside that cell.
    """
    if not items:
        return

    if not slots:
        return

    grid_start_min = mins_from_time(slots[0])
    grid_end_min = mins_from_time(slots[-1]) + slot_min

    def minutes_offset_px(start_row: int, minutes_from_row_start: int) -> int:
        minutes_from_row_start = max(0, minutes_from_row_start)
        full_rows = minutes_from_row_start // slot_min
        extra_minutes = minutes_from_row_start % slot_min
        px = sum(
            max(0, table.rowHeight(start_row + i))
            for i in range(full_rows)
            if 0 <= start_row + i < table.rowCount()
        )
        partial_row = start_row + full_rows
        if 0 <= partial_row < table.rowCount() and extra_minutes:
            px += round(table.rowHeight(partial_row) * extra_minutes / slot_min)
        return px

    appointment_groups = group_concurrent_appointments(items)
    groups_by_id = defaultdict(list)
    for termin, group_id in appointment_groups:
        groups_by_id[group_id].append(termin)

    group_entries = (
        sorted(groups_by_id.items()) if sort_group_ids else groups_by_id.items()
    )

    for _, group_appointments in group_entries:
        valid_apps = [
            app
            for app in group_appointments
            if isinstance(app.start_zeit, time) and app.get_end_time() is not None
        ]
        if not valid_apps:
            continue

        group_start_min = min(mins_from_time(app.start_zeit) for app in valid_apps)
        group_end_min = max(mins_from_time(app.get_end_time()) for app in valid_apps)
        if group_end_min <= group_start_min:
            continue
        if group_end_min <= grid_start_min or group_start_min >= grid_end_min:
            continue

        anchor_min = max(grid_start_min, group_start_min)
        anchor_min = grid_start_min + ((anchor_min - grid_start_min) // slot_min) * slot_min
        row = max(0, min((anchor_min - grid_start_min) // slot_min, len(slots) - 1))

        visual_group_end = min(grid_end_min, group_end_min)
        total_visual_dur = visual_group_end - anchor_min
        max_span = max(1, (total_visual_dur + slot_min - 1) // slot_min)
        max_span = min(max_span, len(slots) - row)

        cell_widget = TimeSlotCell(target_date)
        table.setCellWidget(row, col_idx, cell_widget)

        if max_span > 1:
            try:
                table.setSpan(row, col_idx, max_span, 1)
            except Exception:
                pass

        for app in valid_apps:
            app_start = mins_from_time(app.start_zeit)
            app_end = mins_from_time(app.get_end_time())
            if app_end <= app_start:
                continue
            if app_end <= grid_start_min or app_start >= grid_end_min:
                continue

            visual_app_start = max(app_start, anchor_min)
            visual_app_end = min(app_end, grid_end_min)
            offset_minutes = max(0, visual_app_start - anchor_min)
            visual_app_dur = max(1, visual_app_end - visual_app_start)

            top_offset_px = minutes_offset_px(row, offset_minutes)
            bottom_offset_px = minutes_offset_px(row, offset_minutes + visual_app_dur)
            card_pixel_height = max(1, bottom_offset_px - top_offset_px)

            offset_rows = max(0, offset_minutes // slot_min)
            app_span_rows = max(1, (offset_minutes % slot_min + visual_app_dur + slot_min - 1) // slot_min)
            app_span_rows = min(app_span_rows, len(slots) - row - offset_rows)

            app_text = format_termin_text(app, lvas)
            typ = (app.typ or "").strip().upper()
            bg = type_color_for(typ)
            card = TerminCard(
                app.id,
                app_text,
                bg,
                card_parent,
                zu_besprechen=bool(getattr(app, "zu_besprechen", False)),
                besprechungshinweis=str(getattr(app, "besprechungshinweis", "") or ""),
                typ=typ,
                is_series=bool(app.is_series()),
                details_tooltip=format_termin_tooltip(app, lvas),
            )
            card.set_read_only(read_only)
            card.doubleClicked.connect(edit_by_id_cb)

            place_termin_card(
                table=table,
                cell_widget=cell_widget,
                card=card,
                row=row,
                offset_rows=offset_rows,
                app_span_rows=app_span_rows,
                border_px=border_px,
                top_offset_px_override=top_offset_px,
                card_pixel_height_override=card_pixel_height,
            )
