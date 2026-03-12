from typing import List, Callable, Optional
from datetime import date
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QListWidget,
    QDialogButtonBox,
    QListWidgetItem,
    QLabel,
    QWidget,
    QHBoxLayout,
    QFrame,
)
from PySide6.QtCore import Qt

from ...core.models import Termin
from ..utils.datetime_utils import fmt_time, fmt_date


class DayEventsDialog(QDialog):
    def __init__(
        self,
        parent,
        termins: List[Termin],
        edit_cb: Optional[Callable[[str], None]] = None,
        day: Optional[date] = None,
        go_week_cb: Optional[Callable[[], None]] = None,
        go_day_cb: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.setObjectName("DayEventsDialog")
        self.setModal(True)
        self.setWindowTitle("Termine des Tages")
        self.edit_cb = edit_cb
        self.go_week_cb = go_week_cb
        self.go_day_cb = go_day_cb

        # Header with date (if provided)
        lay = QVBoxLayout(self)
        hdr = QWidget()
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(8)
        title = QLabel("Termine des Tages")
        title.setObjectName("DialogTitle")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch(1)
        if day is not None:
            date_lbl = QLabel(fmt_date(day))
            date_lbl.setObjectName("DialogDate")
            hdr_layout.addWidget(date_lbl)
        lay.addWidget(hdr)

        self.listw = QListWidget()
        self.listw.setObjectName("DayEventsList")
        self.listw.setSelectionMode(QListWidget.SingleSelection)
        self.listw.setWordWrap(True)
        self.listw.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # use card-style rows instead of alternating colors
        self.listw.setAlternatingRowColors(False)
        self.listw.setSpacing(8)  # more space between cards

        for t in termins:
            start = fmt_time(t.start_zeit) if getattr(t, 'start_zeit', None) else ""
            end = fmt_time(t.get_end_time()) if getattr(t, 'get_end_time', None) else ""
            it = QListWidgetItem()
            it.setData(Qt.UserRole, str(t.id))
            row_widget = self._build_row_widget(
                start=start,
                end=end,
                typ=str(getattr(t, 'typ', '') or ''),
                raum_id=str(getattr(t, 'raum_id', '') or ''),
                name=str(getattr(t, 'name', '') or ''),
            )
            # make item a bit taller to accommodate card padding
            hint = row_widget.sizeHint()
            # add some extra height for margins
            hint.setHeight(hint.height() + 16)
            it.setSizeHint(hint)
            self.listw.addItem(it)
            self.listw.setItemWidget(it, row_widget)

        self.listw.itemDoubleClicked.connect(self._on_item_double)
        lay.addWidget(self.listw)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        close_btn = bb.button(QDialogButtonBox.Close)
        if close_btn is not None:
            close_btn.setObjectName("PrimaryButton")
        self.btn_week = bb.addButton("Zur Wochenansicht", QDialogButtonBox.ActionRole)
        self.btn_week.setObjectName("SecondaryButton")
        self.btn_day = bb.addButton("Zur Tagesansicht", QDialogButtonBox.ActionRole)
        self.btn_day.setObjectName("SecondaryButton")
        self.btn_week.clicked.connect(self._go_week)
        self.btn_day.clicked.connect(self._go_day)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        # sizing
        self.resize(480, 360)

    def _build_row_widget(self, *, start: str, end: str, typ: str, raum_id: str, name: str) -> QWidget:
        # use a frame so we can style it like a card
        row = QFrame(self.listw)
        row.setObjectName("DayEventCard")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        time_text = f"{start}–{end}".strip("–")
        time_lbl = QLabel(time_text if time_text else "Zeit offen", row)
        time_lbl.setObjectName("DayEventTime")
        time_lbl.setMinimumWidth(92)

        name_lbl = QLabel(name if name else "(Ohne Titel)", row)
        name_lbl.setObjectName("DayEventTitle")
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet("font-weight:600;")

        top.addWidget(time_lbl, 0)
        top.addWidget(name_lbl, 1)
        layout.addLayout(top)

        meta_parts = []
        if typ:
            meta_parts.append(typ)
        if raum_id:
            meta_parts.append(raum_id)
        meta_lbl = QLabel(" • ".join(meta_parts) if meta_parts else "", row)
        meta_lbl.setObjectName("DayEventMeta")
        layout.addWidget(meta_lbl)

        return row

    def _on_item_double(self, item: QListWidgetItem):
        tid = item.data(Qt.UserRole)
        if self.edit_cb and tid:
            try:
                self.edit_cb(str(tid))
            finally:
                self.accept()



    def _go_week(self):
        if self.go_week_cb:
            try:
                self.go_week_cb()
            finally:
                self.accept()

    def _go_day(self):
        if self.go_day_cb:
            try:
                self.go_day_cb()
            finally:
                self.accept()
