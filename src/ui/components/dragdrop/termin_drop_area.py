from PySide6.QtCore import Signal
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QWidget


class TerminDropArea(QWidget):
    """Invisible drop target that accepts Termin drags and emits terminDroppedToList to unassign them"""

    terminDroppedToList = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._read_only = False
        self.setAcceptDrops(True)

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        self.setAcceptDrops(not self._read_only)

    def dragEnterEvent(self, e):
        if self._read_only:
            e.ignore()
            return
        if e.mimeData().hasText():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._read_only:
            e.ignore()
            return
        if e.mimeData().hasText():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e: QDropEvent):
        if self._read_only:
            e.ignore()
            return
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
