from collections import defaultdict
from datetime import date, time
from html import escape
from typing import Callable, Iterable, Sequence

from PySide6.QtCore import QSize, Qt, QRect
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QHeaderView, QStyle, QStyleOptionHeader, QTableWidget, QSizePolicy

from ...core.models import Termin
from ...services.termin_occurrence_service import occurrence_date_from_id, is_occurrence_id
from ..utils.datetime_utils import fmt_date, fmt_time, mins_from_time
from ..utils.grouping_utils import group_concurrent_appointments
from ..utils.color_constants import planner_text_color, type_accent_color_for, type_color_for
from ..utils.qss_tokens import qss_color
from .free_day_provider import FreeDayBadgeLine
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


def is_series_exception_instance(termin: Termin) -> bool:
    occurrence_date = occurrence_date_from_id(str(getattr(termin, "id", "")))
    if occurrence_date is None:
        return False
    return any(
        getattr(item, "original_datum", None) == occurrence_date
        for item in (getattr(termin, "serien_ausnahmen", []) or [])
    )


def is_series_instance(termin: Termin) -> bool:
    return bool(termin.is_series() or is_occurrence_id(str(getattr(termin, "id", ""))))


class FreeDayHeaderView(QHeaderView):
    def __init__(self, orientation: Qt.Orientation, parent=None):
        super().__init__(orientation, parent)
        self._badges: dict[int, tuple[tuple[FreeDayBadgeLine, ...], str]] = {}
        self._accent_colors: dict[int, QColor] = {}
        self.setMinimumHeight(44)
        self.sectionResized.connect(self._sync_height)

    def set_free_day_badges(
        self, badges: dict[int, tuple[tuple[FreeDayBadgeLine, ...], str]]
    ) -> None:
        self._badges = dict(badges)
        self._sync_height()
        self.viewport().update()

    def set_section_accent_colors(self, colors: dict[int, QColor]) -> None:
        self._accent_colors = {
            int(section): QColor(color)
            for section, color in colors.items()
            if QColor(color).isValid()
        }
        self._sync_height()
        self.viewport().update()

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        hint.setHeight(max(hint.height(), self._content_height()))
        return hint

    def _badge_height(self, lines: tuple[FreeDayBadgeLine, ...]) -> int:
        line_count = max(1, len(lines))
        return 7 + (line_count * 17) + max(0, line_count - 1) * 3

    def _content_height(self) -> int:
        model = self.model()
        metrics = self.fontMetrics()
        if model is None:
            return 44
        height = 44
        for section in range(self.count()):
            if self.isSectionHidden(section):
                continue
            text = model.headerData(section, self.orientation(), Qt.DisplayRole)
            text = "" if text is None else str(text)
            width = max(40, self.sectionSize(section) - 8)
            if width <= 40 and self.count():
                width = max(40, self.viewport().width() // max(1, self.count()) - 8)
            text_rect = metrics.boundingRect(
                QRect(0, 0, width, 1000),
                Qt.AlignCenter | Qt.TextWordWrap,
                text,
            )
            badge = self._badges.get(section)
            badge_reserved = self._badge_height(badge[0]) + 8 if badge else 4
            top_padding = 8 if self._accent_colors.get(section) else 4
            text_height = max(metrics.height(), text_rect.height())
            height = max(height, top_padding + text_height + badge_reserved + 2)
        return height

    def _sync_height(self, *_args) -> None:
        height = self._content_height()
        if self.minimumHeight() != height:
            self.setMinimumHeight(height)
            self.updateGeometry()

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
        reserved_badge_height = self._badge_height(badge[0]) + 4 if badge else 0
        text_rect = rect.adjusted(
            4,
            8 if accent else 4,
            -4,
            -(reserved_badge_height + 4) if badge else -4,
        )

        painter.setPen(planner_text_color())
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, text)

        if badge:
            badge_lines, _tooltip = badge
            self._paint_badge(painter, rect, badge_lines)

        painter.restore()

    def _badge_colors(self, day_type: str) -> tuple[QColor, QColor, QColor]:
        if day_type == "feiertag":
            bg = qss_color("free-day-holiday-badge-bg")
            border = qss_color("free-day-holiday-badge-border")
            fg = qss_color("free-day-holiday-badge-text")
        else:
            bg = qss_color("free-day-lecture-badge-bg")
            border = qss_color("free-day-lecture-badge-border")
            fg = qss_color("free-day-lecture-badge-text")
        return bg, border, fg

    def _paint_badge(
        self, painter, section_rect, lines: tuple[FreeDayBadgeLine, ...]
    ) -> None:
        if not lines:
            return
        badge_height = self._badge_height(lines)
        badge_rect = section_rect.adjusted(5, section_rect.height() - badge_height - 5, -5, -5)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        line_height = 17
        gap = 3
        top = badge_rect.top() + 4
        for index, line in enumerate(lines):
            bg, border, fg = self._badge_colors(line.day_type)
            line_rect = badge_rect.adjusted(0, 0, 0, 0)
            line_rect.setTop(top + index * (line_height + gap))
            line_rect.setHeight(line_height)
            painter.setBrush(bg)
            painter.setPen(QPen(border, 0.5))
            painter.drawRoundedRect(line_rect, 4, 4)
            painter.setPen(fg)
            label = metrics.elidedText(line.text, Qt.ElideRight, max(1, line_rect.width() - 12))
            line_rect = line_rect.adjusted(6, 0, -6, 0)
            painter.drawText(line_rect, Qt.AlignLeft | Qt.AlignVCenter, label)


def format_termin_text(t: Termin, lvas) -> str:
    end_raw = t.get_end_time()
    lva = next((l for l in lvas if l.id == t.lva_id), None)
    lva_short = f"{t.lva_id}" + ("" if not lva else f" {lva.name}")
    room_s = str(t.raum_id or "").strip() or "Kein Raum"
    gname = t.gruppe.name if t.gruppe else ""
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
    missing_room = not str(t.raum_id or "").strip()
    series_exception = is_series_exception_instance(t)
    series = is_series_instance(t)
    discuss = bool(getattr(t, "zu_besprechen", False))
    discuss_hint = str(getattr(t, "besprechungshinweis", "") or "").strip()

    def badge_line(marker: str, text: str, color: str) -> str:
        return (
            f"<span style='color:{color}; font-weight:700;'>{escape(marker)}</span>"
            f"&nbsp;{escape(text)}"
        )

    series_color = type_accent_color_for(str(t.typ or "").strip().upper()).name()

    badge_lines = []
    if series_exception:
        badge_lines.append(badge_line("SA", "Serienausnahme", series_color))
    elif series:
        badge_lines.append(
            badge_line(
                "S",
                f"Serientermin: {t.periodizitaet}, bis {fmt_date(t.datum_bis)}",
                series_color,
            )
        )
    if missing_room:
        badge_lines.append(
            badge_line("R", "Kein Raum zugewiesen", qss_color("planner-missing-room-border").name())
        )
    if discuss:
        text = "Zu besprechen" + (f": {discuss_hint}" if discuss_hint else "")
        badge_lines.append(badge_line("!", text, qss_color("planner-discuss-border").name()))

    lines = [
        str(t.name or "(Ohne Titel)"),
        f"ID: {t.id}",
        f"LVA: {lva_text}",
        f"Typ: {t.typ or '-'}",
        f"Datum: {fmt_date(t.datum)}",
        f"Zeit: {fmt_time(t.start_zeit)}-{fmt_time(end_raw)}",
        f"Dauer: {int(t.duration or 0)} min",
    ]

    if not missing_room:
        lines.append(f"Raum: {room_text}")
    if group_text:
        lines.append(f"Gruppe: {group_text}")
    if getattr(t, "semester_id", ""):
        lines.append(f"Semester: {t.semester_id}")
    if t.anwesenheitspflicht:
        lines.append("Anwesenheitspflicht")
    if str(getattr(t, "notiz", "") or "").strip():
        lines.append(f"Notiz: {str(t.notiz).strip()}")

    detail_html = "<br>".join(escape(line) for line in lines)
    if not badge_lines:
        return f"<html><body>{detail_html}</body></html>"

    badge_html = "<br>".join(badge_lines)
    return f"<html><body>{badge_html}<br><br>{detail_html}</body></html>"


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
    context_menu_cb: Callable[[str], None] | None = None,
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

    group_entries = sorted(groups_by_id.items()) if sort_group_ids else groups_by_id.items()

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
            app_span_rows = max(
                1, (offset_minutes % slot_min + visual_app_dur + slot_min - 1) // slot_min
            )
            app_span_rows = min(app_span_rows, len(slots) - row - offset_rows)

            app_text = format_termin_text(app, lvas)
            typ = (app.typ or "").strip().upper()
            bg = type_color_for(typ)
            is_exception = is_series_exception_instance(app)
            is_series = is_series_instance(app)
            card = TerminCard(
                app.id,
                app_text,
                bg,
                card_parent,
                zu_besprechen=bool(getattr(app, "zu_besprechen", False)),
                besprechungshinweis=str(getattr(app, "besprechungshinweis", "") or ""),
                typ=typ,
                is_series=is_series,
                is_series_exception=is_exception,
                missing_room=not bool(str(getattr(app, "raum_id", "") or "").strip()),
                details_tooltip=format_termin_tooltip(app, lvas),
            )
            card.set_read_only(read_only)
            card.doubleClicked.connect(edit_by_id_cb)
            if context_menu_cb is not None:
                card.rightClicked.connect(context_menu_cb)

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
