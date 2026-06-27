from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget, QLabel, QPushButton, QSizePolicy

from .flow_layout import FlowLayout


class ChipListWidget(QWidget):
    """Wrapping chip list with removable items that emits the deleted chip index"""

    chipDeleted = Signal(int)  # emits the index of the chip to delete

    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        self.layout = FlowLayout(self, spacing=6)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.chip_widgets = []
        self.items = items or []
        self.refresh()

    def refresh(self):
        for chip in self.chip_widgets:
            self.layout.removeWidget(chip)
            chip.deleteLater()
        self.chip_widgets = []

        for idx, text in enumerate(self.items):
            chip = self._make_chip(text, idx)
            self.layout.addWidget(chip)
            self.chip_widgets.append(chip)

    def _make_chip(self, text, idx):
        chip = QWidget(self)
        chip.setObjectName("ChipItem")
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(8, 2, 4, 2)
        chip_layout.setSpacing(4)
        label = QLabel(text, chip)
        label.setObjectName("ChipLabel")
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        btn = QPushButton("✕", chip)
        btn.setObjectName("ChipDeleteButton")
        btn.setFixedSize(18, 18)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda _, i=idx: self.chipDeleted.emit(i))
        chip_layout.addWidget(label)
        chip_layout.addWidget(btn)
        chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        return chip

    def setItems(self, items):
        self.items = items
        self.refresh()

    def addItem(self, text):
        self.items.append(text)
        self.refresh()

    def removeItem(self, idx):
        if 0 <= idx < len(self.items):
            del self.items[idx]
            self.refresh()
