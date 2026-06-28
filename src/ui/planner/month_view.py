from datetime import date
import calendar
from typing import List

from PySide6.QtCore import Qt, QObject, QEvent, QRect
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFontMetrics
from PySide6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QHeaderView,
    QStyledItemDelegate,
    QStyle,
)

from ...core.models import Termin
from ..utils.datetime_utils import qdate_to_date, date_to_qdate
from ..utils.qss_tokens import qss_color


from ..dialogs.day_events_dialog import DayEventsDialog
from .free_day_provider import FreeDayProvider


MONTH_DAY_IDS_ROLE = Qt.UserRole + 1
MONTH_DAY_DATE_ROLE = Qt.UserRole + 2
MONTH_DAY_NUMBER_ROLE = Qt.UserRole + 3
MONTH_IN_MONTH_ROLE = Qt.UserRole + 4
MONTH_BG_ROLE = Qt.UserRole + 5
MONTH_BADGES_ROLE = Qt.UserRole + 6
MONTH_TERM_COUNT_ROLE = Qt.UserRole + 7
MONTH_DISCUSS_COUNT_ROLE = Qt.UserRole + 8
MONTH_CONFLICT_ROLE = Qt.UserRole + 9


class MonthCellDelegate(QStyledItemDelegate):
    """Paints month cells directly, without embedded widgets."""

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        rect = option.rect
        in_month = bool(index.data(MONTH_IN_MONTH_ROLE))

        if in_month:
            bg = index.data(MONTH_BG_ROLE)
            if not isinstance(bg, QColor) or not bg.isValid():
                bg = qss_color("month-day-bg")
            painter.fillRect(rect, bg)
        else:
            self._paint_outside_month(painter, rect)

        self._paint_grid(painter, rect, index)

        if in_month:
            self._paint_day_content(painter, option, index)

        if option.state & QStyle.State_Selected:
            self._paint_focus_border(painter, rect, qss_color("planner-focus-border"))

        if bool(index.data(MONTH_CONFLICT_ROLE)):
            self._paint_focus_border(painter, rect.adjusted(1, 1, -1, -1), qss_color("planner-focus-border"))

        painter.restore()

    def _paint_outside_month(self, painter: QPainter, rect) -> None:
        bg = qss_color("month-outside-bg")
        stripe = qss_color("month-outside-stripe")
        painter.fillRect(rect, bg)
        painter.setClipRect(rect)
        painter.setPen(QPen(stripe, 1))
        start = rect.left() - rect.height()
        end = rect.right() + rect.height()
        for x in range(start, end, 12):
            painter.drawLine(x, rect.bottom(), x + rect.height(), rect.top())
        painter.setClipping(False)

    def _paint_grid(self, painter: QPainter, rect, index) -> None:
        pen = QPen(qss_color("planner-grid-vertical"), 1)
        painter.setPen(pen)
        painter.drawLine(rect.topLeft(), rect.topRight())
        painter.drawLine(rect.topLeft(), rect.bottomLeft())
        if index.row() == index.model().rowCount() - 1:
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if index.column() == index.model().columnCount() - 1:
            painter.drawLine(rect.topRight(), rect.bottomRight())

    def _paint_day_content(self, painter: QPainter, option, index) -> None:
        rect = option.rect.adjusted(6, 5, -6, -5)
        day_number = index.data(MONTH_DAY_NUMBER_ROLE)
        if day_number is None:
            return

        text_color = qss_color("planner-text")
        painter.setPen(text_color)
        day_font = option.font
        day_font.setBold(True)
        day_font.setPointSize(max(9, day_font.pointSize()))
        painter.setFont(day_font)
        painter.drawText(rect.left(), rect.top(), rect.width(), 18, Qt.AlignLeft | Qt.AlignTop, str(day_number))

        badges = index.data(MONTH_BADGES_ROLE) or []
        y = rect.top() + max(28, int(option.rect.height() * 0.46))
        for day_type, text in badges[:3]:
            self._paint_badge(painter, rect.left(), y, rect.width(), day_type, str(text))
            y += 20

        hidden_count = max(0, len(badges) - 3)
        if hidden_count:
            fallback_type = badges[0][0] if badges else ""
            self._paint_badge(painter, rect.left(), y, rect.width(), fallback_type, f"+{hidden_count}")
            y += 20

        term_count = int(index.data(MONTH_TERM_COUNT_ROLE) or 0)
        if term_count:
            painter.setPen(QColor("#666666"))
            count_font = option.font
            count_font.setPointSize(max(8, count_font.pointSize() - 1))
            painter.setFont(count_font)
            painter.drawText(rect.left(), y + 1, rect.width(), 16, Qt.AlignLeft | Qt.AlignTop, f"(+{term_count})")
            y += 17

        discuss_count = int(index.data(MONTH_DISCUSS_COUNT_ROLE) or 0)
        if discuss_count:
            painter.setPen(qss_color("planner-discuss-border"))
            discuss_font = option.font
            discuss_font.setBold(True)
            discuss_font.setPointSize(max(8, discuss_font.pointSize() - 1))
            painter.setFont(discuss_font)
            painter.drawText(rect.left(), y, rect.width(), 16, Qt.AlignLeft | Qt.AlignTop, f"! {discuss_count}")

    def _paint_badge(self, painter: QPainter, x: int, y: int, width: int, day_type: str, text: str) -> None:
        if day_type == "feiertag":
            bg = qss_color("free-day-holiday-badge-bg")
            fg = qss_color("free-day-holiday-badge-text")
        else:
            bg = qss_color("free-day-lecture-badge-bg")
            fg = qss_color("free-day-lecture-badge-text")

        badge = QRect(x, y, max(0, width), 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(badge, 3, 3)

        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(8, font.pointSize() - 1))
        painter.setFont(font)
        metrics = QFontMetrics(font)
        label = metrics.elidedText(text, Qt.ElideRight, max(0, badge.width() - 8))
        painter.setPen(fg)
        painter.drawText(badge.adjusted(4, 0, -4, 0), Qt.AlignLeft | Qt.AlignVCenter, label)

    def _paint_focus_border(self, painter: QPainter, rect, color: QColor) -> None:
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect.adjusted(1, 1, -2, -2))


class PlannerMonthView:
    """monthly grid view. Shows day numbers and a +N indicator when events exist.
    Clicking a day with events opens a dialog listing that day's termins
    """

    def __init__(
        self,
        state,
        month_table: QTableWidget,
        day_date,
        free_day_provider: FreeDayProvider,
        month_label=None,
        edit_by_id_cb=None,
        on_drop_cb=None,
    ):
        self.state = state
        self.table = month_table
        self.day_date = day_date
        self._free_day_provider = free_day_provider
        self.edit_by_id_cb = edit_by_id_cb
        self.on_drop_cb = on_drop_cb
        self.month_label = month_label
        self._read_only = False

        show_weekend = self.state.settings.get("show_weekend", True)
        if show_weekend:
            self.table.setColumnCount(7)
            self.table.setHorizontalHeaderLabels(["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"])
        else:
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["Mo", "Di", "Mi", "Do", "Fr"])
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setShowGrid(False)
        self.table.setItemDelegate(MonthCellDelegate(self.table))
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(90)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._last_filtered: List[Termin] = []

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

        self._watcher = _Watcher(self, self.table.viewport())
        self.table.viewport().installEventFilter(self._watcher)

        if hasattr(self.table, "terminDropped"):
            self.table.terminDropped.connect(self._on_table_drop)

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        if hasattr(self.table, "set_read_only"):
            self.table.set_read_only(self._read_only)

    def refresh(self, filtered_termine: List[Termin]):
        try:
            mf = qdate_to_date(self.day_date.date())
        except Exception:
            mf = date.today()

        year = mf.year
        month = mf.month

        show_weekend = self.state.settings.get("show_weekend", True)
        day_headers = (
            ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
            if show_weekend
            else ["Mo", "Di", "Mi", "Do", "Fr"]
        )
        days_in_week = len(day_headers)
        month_weeks = [
            week
            for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
            if any(day.month == month for day in (week if show_weekend else week[:5]))
        ]

        self.table.setColumnCount(days_in_week)
        self.table.setHorizontalHeaderLabels(day_headers)
        self.table.setRowCount(len(month_weeks))

        by_date = {}
        for t in filtered_termine:
            if getattr(t, "datum", None):
                by_date.setdefault(t.datum, []).append(t)

        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        free_days = self._free_day_provider.get_infos_for_range(first_day, last_day)

        self._last_filtered = list(filtered_termine or [])
        vp_height = max(1, self.table.viewport().height())
        row_height = max(60, int(vp_height / max(1, len(month_weeks))))
        for r, week_dates in enumerate(month_weeks):
            self.table.setRowHeight(r, row_height)
            visible_dates = week_dates if show_weekend else week_dates[:5]
            for c, d in enumerate(visible_dates):
                old_widget = self.table.cellWidget(r, c)
                if old_widget is not None:
                    self.table.removeCellWidget(r, c)
                    old_widget.deleteLater()

                if d.month != month:
                    self.table.setItem(r, c, self._outside_month_item())
                else:
                    old_item = self.table.takeItem(r, c)
                    if old_item is not None:
                        del old_item
                    items = by_date.get(d, [])
                    discuss_count = sum(
                        1 for item in items if bool(getattr(item, "zu_besprechen", False))
                    )
                    day_info = free_days.get(d)
                    badge_lines = (
                        list(self._free_day_provider.badge_lines_for_info(day_info))
                        if day_info
                        else []
                    )
                    day_type = badge_lines[0].day_type if badge_lines else None
                    if day_type == "feiertag":
                        cell_bg = qss_color("free-day-holiday-bg")
                    elif day_type == "vorlesungsfrei":
                        cell_bg = qss_color("free-day-lecture-bg")
                    else:
                        cell_bg = qss_color("month-day-bg")
                    cell_item = QTableWidgetItem("")
                    cell_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    cell_item.setBackground(QBrush(cell_bg))
                    cell_item.setData(MONTH_IN_MONTH_ROLE, True)
                    cell_item.setData(MONTH_DAY_DATE_ROLE, d)
                    cell_item.setData(MONTH_DAY_NUMBER_ROLE, d.day)
                    cell_item.setData(MONTH_DAY_IDS_ROLE, [str(t.id) for t in items])
                    cell_item.setData(MONTH_BG_ROLE, cell_bg)
                    cell_item.setData(MONTH_TERM_COUNT_ROLE, len(items))
                    cell_item.setData(MONTH_DISCUSS_COUNT_ROLE, discuss_count)

                    if badge_lines:
                        cell_item.setData(
                            MONTH_BADGES_ROLE,
                            [(line.day_type, line.text) for line in badge_lines if line.text],
                        )
                        cell_item.setToolTip("\n".join(line.text for line in badge_lines if line.text))

                    self.table.setItem(r, c, cell_item)

        if self.month_label is not None:
            self.month_label.setText(f"{calendar.month_name[month]} {year}")

        avail_w = max(1, self.table.viewport().width())
        col_w = max(48, avail_w // max(1, days_in_week))
        for i in range(days_in_week):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Fixed)
            self.table.setColumnWidth(i, col_w)
        self.table.updateGeometry()
        self.table.viewport().update()

    def _outside_month_item(self) -> QTableWidgetItem:
        item = QTableWidgetItem("")
        item.setFlags(Qt.NoItemFlags)
        item.setToolTip("Nicht im angezeigten Monat")
        item.setData(MONTH_IN_MONTH_ROLE, False)
        return item

    def _on_cell_clicked(self, row: int, col: int):
        item = self.table.item(row, col)
        if item is None:
            return
        data = item.data(MONTH_DAY_IDS_ROLE)
        if not data:
            return

        ids = set(str(x) for x in data)
        if hasattr(self.state, "termin_map"):
            term_list = [t for tid in ids if (t := self.state.termin_map.get(tid))]
        else:
            term_list = [t for t in self.state.termine if str(t.id) in ids]

        target_day = item.data(MONTH_DAY_DATE_ROLE)
        if not isinstance(target_day, date):
            target_day = None

        def _switch_view(view_key: str) -> None:
            mw = self.table.window()
            if not mw or target_day is None:
                return
            planner = getattr(mw, "planner", None)
            if not planner:
                return
            planner.day_date.setDate(date_to_qdate(target_day))
            idx = planner.view_cb.findData(view_key)
            if idx >= 0:
                planner.view_cb.setCurrentIndex(idx)
            planner.refresh(emit=False)

        dlg = DayEventsDialog(
            self.table.window(),
            term_list,
            edit_cb=self.edit_by_id_cb,
            day=target_day,
            go_week_cb=lambda: _switch_view("week"),
            go_day_cb=lambda: _switch_view("day"),
        )
        dlg.exec()

    def _on_table_drop(self, termin_id: str, row: int, col: int):
        if self._read_only:
            return
        item = self.table.item(row, col)
        if item is None:
            return
        new_date = item.data(MONTH_DAY_DATE_ROLE)
        if not isinstance(new_date, date):
            return

        new_start = None
        try:
            t = (
                self.state.termin_map.get(str(termin_id))
                if hasattr(self.state, "termin_map")
                else None
            )
            if not t:
                t = next((x for x in self.state.termine if str(x.id) == str(termin_id)), None)

            room_id = getattr(t, "raum_id", None) if t else None
            duration = int(getattr(t, "duration", 0) or 0) if t else 0
            if duration <= 0:
                duration = int(self.state.settings.get("time_slot_minutes", 30))

            if room_id and getattr(self.state, "ts", None):
                free = self.state.ts.find_free_slots_in_room(
                    self.state.termine, room_id, new_date, duration
                )
                if free:
                    new_start = free[0].von
        except Exception:
            new_start = None

        if callable(self.on_drop_cb):
            self.on_drop_cb(str(termin_id), new_date, new_start)
