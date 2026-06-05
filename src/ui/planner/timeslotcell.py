from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from datetime import date

from .termincard import TerminCard


class TimeSlotCell(QWidget):
    """Container widget for one planner table cell that can stack multiple TerminCards
    """

    def __init__(self, target_date: date, parent=None):
        super().__init__(parent)
        self.target_date = target_date
        self.setContentsMargins(0, 0, 0, 0)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.setLayout(self.layout)


        self.setStyleSheet("background-color: transparent;")

    def add_termin_card(
        self,
        card: TerminCard,
        top_offset_px: int = 0,
        bottom_margin_px: int = 0,
    ) -> None:
        wrapper = QWidget(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        vbox = QVBoxLayout(wrapper)
        vbox.setContentsMargins(0, max(0, top_offset_px), 0, max(0, bottom_margin_px))
        vbox.setSpacing(0)
        vbox.addWidget(card)
        self.layout.addWidget(wrapper, 1, Qt.AlignTop)

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
