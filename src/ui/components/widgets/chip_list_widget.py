from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Signal, Qt

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
        # Remove old widgets
        for chip in self.chip_widgets:
            self.layout.removeWidget(chip)
            chip.deleteLater()
        self.chip_widgets = []
        # Add new chips
        for idx, text in enumerate(self.items):
            chip = self._make_chip(text, idx)
            self.layout.addWidget(chip)
            self.chip_widgets.append(chip)

    def _make_chip(self, text, idx):
        chip = QWidget(self)
        from PySide6.QtWidgets import QHBoxLayout
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(8, 2, 4, 2)
        chip_layout.setSpacing(4)
        label = QLabel(text, chip)
        label.setStyleSheet('QLabel { padding: 0 2px; border: none; background: transparent; }')
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        btn = QPushButton('✕', chip)
        btn.setFixedSize(18, 18)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet('QPushButton { border: none; background: transparent; color: #888; font-weight: bold; padding: 0 2px; } QPushButton:hover { color: #444; background: #eee; }')
        btn.clicked.connect(lambda _, i=idx: self.chipDeleted.emit(i))
        chip_layout.addWidget(label)
        chip_layout.addWidget(btn)
        chip.setStyleSheet('QWidget { border-radius: 6px; background: #fff; border: 1px solid #222; padding-left: 0px; padding-right: 0px; }')
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
