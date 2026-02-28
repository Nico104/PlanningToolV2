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
)
from PySide6.QtCore import Qt

from ...core.models import Termin
from ..utils.datetime_utils import fmt_time, fmt_date


class DayEventsDialog(QDialog):
    def __init__(self, parent, termins: List[Termin], edit_cb: Optional[Callable[[str], None]] = None, day: Optional[date] = None):
        super().__init__(parent)
        self.setModal(True)
        self.edit_cb = edit_cb

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
        self.listw.setSelectionMode(QListWidget.SingleSelection)
        self.listw.setWordWrap(True)
        self.listw.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        for t in termins:
            start = fmt_time(t.start_zeit) if getattr(t, 'start_zeit', None) else ""
            end = fmt_time(t.get_end_time()) if getattr(t, 'get_end_time', None) else ""
            label = f"{start}–{end} • {getattr(t, 'typ', '')} • {getattr(t, 'raum_id', '')} — {getattr(t, 'name', '')}"
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, str(t.id))
            self.listw.addItem(it)

        self.listw.itemDoubleClicked.connect(self._on_item_double)
        lay.addWidget(self.listw)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        # sizing
        self.resize(480, 360)

    def _on_item_double(self, item: QListWidgetItem):
        tid = item.data(Qt.UserRole)
        if self.edit_cb and tid:
            try:
                self.edit_cb(str(tid))
            finally:
                self.accept()
