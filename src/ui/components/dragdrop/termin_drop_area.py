from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QWidget


class TerminDropArea(QWidget):
    terminDroppedToList = Signal(str)
    MIME = "application/termin-id"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(self.MIME):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(self.MIME):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e: QDropEvent):
        md = e.mimeData()
        if not md.hasFormat(self.MIME):
            e.ignore()
            return

        tid = bytes(md.data(self.MIME)).decode("utf-8").strip()
        if tid:
            self.terminDroppedToList.emit(tid)
            e.acceptProposedAction()
        else:
            e.ignore()
