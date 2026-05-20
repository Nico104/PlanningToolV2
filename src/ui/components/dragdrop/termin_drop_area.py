from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QWidget


class TerminDropArea(QWidget):
    """Invisible drop target that accepts Termin drags and emits terminDroppedToList to unassign them"""

    terminDroppedToList = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e: QDropEvent):
        md = e.mimeData()
        if not md.hasText():
            e.ignore()
            return

        tid = md.text().strip()
        if tid:
            self.terminDroppedToList.emit(tid)
            e.acceptProposedAction()
        else:
            e.ignore()
