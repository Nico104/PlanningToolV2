from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from datetime import date

from .termincard import TerminCard


class TimeSlotCell(QWidget):
    """Container widget for one planner table cell that can stack multiple TerminCards
    """

    def __init__(self, target_date: date, parent=None):
        super().__init__(parent)
        self.target_date = target_date
        self._grid_row_height = 0
        self._grid_span_rows = 0
        self.setContentsMargins(0, 0, 0, 0)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.setLayout(self.layout)


        self.setStyleSheet("background-color: transparent;")

    def set_grid_info(self, row_height: int, span_rows: int) -> None:
        self._grid_row_height = max(0, row_height)
        self._grid_span_rows = max(0, span_rows)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._grid_row_height <= 0 or self._grid_span_rows <= 1:
            return
        painter = QPainter(self)
        pen = QPen(QColor("#f0efec"))
        painter.setPen(pen)
        for i in range(1, self._grid_span_rows):
            y = i * self._grid_row_height
            painter.drawLine(0, y, self.width(), y)

    def add_termin_card(self, card: TerminCard, top_offset_px: int = 0) -> None:
        wrapper = QWidget(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        vbox = QVBoxLayout(wrapper)
        vbox.setContentsMargins(0, max(0, top_offset_px), 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(card)
        self.layout.addWidget(wrapper, 1, Qt.AlignTop)

    def clear_cards(self) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def get_termin_ids(self) -> list[str]:
        ids = []
        for i in range(self.layout.count()):
            item = self.layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, TerminCard):
                    ids.append(widget.termin_id)
                else:
                    child_card = widget.findChild(TerminCard)
                    if child_card:
                        ids.append(child_card.termin_id)
        return ids