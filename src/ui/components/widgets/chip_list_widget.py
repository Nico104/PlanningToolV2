from PySide6.QtWidgets import QWidget, QLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Signal, QRect, QSize, Qt, QPoint

# FlowLayout implementation for wrapping chips
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=6):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        for item in self.itemList:
            wid = item.widget()
            spaceX = self.spacing()
            spaceY = self.spacing()
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
        return y + lineHeight - rect.y()

class ChipListWidget(QWidget):
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
        # Only show the name (truncate if too long)
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
