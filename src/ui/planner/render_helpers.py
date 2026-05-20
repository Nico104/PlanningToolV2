from collections import defaultdict
from datetime import date, time
from typing import Callable, Iterable, Sequence

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget, QSizePolicy

from ...core.models import Termin
from ..utils.datetime_utils import fmt_time, mins_from_time
from ..utils.grouping_utils import group_concurrent_appointments
from ..utils.color_constants import TYPE_COLORS, DEFAULT_BG
from .timeslotcell import TimeSlotCell
from .termincard import TerminCard


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


def place_termin_card(
    table: QTableWidget,
    cell_widget: TimeSlotCell,
    card: TerminCard,
    row: int,
    offset_rows: int,
    app_span_rows: int,
    border_px: int = 2,
) -> None:
    row_height = table.rowHeight(row)
    card_pixel_height = app_span_rows * row_height
    inner_height = max(1, card_pixel_height - (2 * border_px))
    card.setFixedHeight(inner_height)
    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    top_offset_px = offset_rows * row_height
    cell_widget.add_termin_card(card, top_offset_px=top_offset_px)


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
) -> None:
    """The function groups concurrent Termine, creates a single TimeSlotCell per group,
    applies row spanning for total group duration, and places each TerminCard at the
    correct vertical offset inside that cell.
    """
    if not items:
        return

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

        start_t = time(hour=group_start_min // 60, minute=group_start_min % 60)
        if start_t not in slots:
            continue

        row = slots.index(start_t)

        total_dur = group_end_min - group_start_min
        max_span = max(1, (total_dur + slot_min - 1) // slot_min)
        max_span = min(max_span, len(slots) - row)

        cell_widget = TimeSlotCell(target_date)
        table.setCellWidget(row, col_idx, cell_widget)

        if max_span > 1:
            try:
                table.setSpan(row, col_idx, max_span, 1)
            except Exception:
                pass

        row_height = table.rowHeight(row)
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

            app_text = format_termin_text(app, lvas)
            typ = (app.typ or "").strip().upper()
            bg = next((color for k, color in TYPE_COLORS if typ == k), DEFAULT_BG)
            card = TerminCard(app.id, app_text, bg, card_parent)
            card.doubleClicked.connect(edit_by_id_cb)

            place_termin_card(
                table=table,
                cell_widget=cell_widget,
                card=card,
                row=row,
                offset_rows=offset_rows,
                app_span_rows=app_span_rows,
                border_px=border_px,
            )
