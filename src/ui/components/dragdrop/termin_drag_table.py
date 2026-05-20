from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView


class TerminDragTable(QTableWidget):
    """Table for selecting Termine to drag; users can't edit cells, only drag rows"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setDefaultDropAction(Qt.MoveAction)

    def startDrag(self, supportedActions):
        row = self.currentRow()
        if row < 0:
            return

        id_item = self.item(row, 0)
        if not id_item:
            return

        termin_id = (id_item.text() or "").strip()
        if not termin_id:
            return

        md = QMimeData()
        md.setText(termin_id)

        drag = QDrag(self)
        drag.setMimeData(md)
        drag.exec(Qt.MoveAction)
