from typing import List, Optional

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMenu
)


def make_item(text: str) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def selected_id(table: QTableWidget) -> Optional[str]:
    row = table.currentRow()
    # gibt -1 zurück wenn keine Zeile selektiert ist
    if row < 0:
        return None

    id_col = table.property("id_column")
    if not isinstance(id_col, int) or id_col < 0 or id_col >= table.columnCount():
        id_col = None
        for col in range(table.columnCount()):
            hdr = table.horizontalHeaderItem(col)
            if hdr and hdr.text().strip().upper() == "ID":
                id_col = col
                break

    if id_col is None:
        lva_nr_headers = {"LVA-NR.", "LVA-NR", "LVA NR", "RAUMNUMMER"}
        for col in range(table.columnCount()):
            hdr = table.horizontalHeaderItem(col)
            if hdr and hdr.text().strip().upper() in lva_nr_headers:
                id_col = col
                break

    if id_col is None:
        return None

    it = table.item(row, id_col)
    return it.text().strip() if it else None


class EditorTab(QWidget):
    """Reusable table tab with Add/Edit/Delete buttons and context menu
    Used for Date Editor"""

    add_clicked = Signal()
    edit_clicked = Signal()
    delete_clicked = Signal()

    def __init__(self, title: str, columns: List[str], parent: QWidget, id_column: Optional[int] = None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        self._actions_enabled = True

        # Button row
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Hinzufügen")
        self.btn_edit = QPushButton("Bearbeiten")
        self.btn_del = QPushButton("Löschen")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_del)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        # Table
        self.table = QTableWidget(0, len(columns), self)
        self.table.setHorizontalHeaderLabels(columns)
        if id_column is not None:
            self.table.setProperty("id_column", id_column)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Context menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._open_context_menu)
        self.table.cellDoubleClicked.connect(lambda r, c: self._emit_edit_if_selected())

        root.addWidget(self.table, 1)

        # wire buttons
        self.btn_add.clicked.connect(self.add_clicked.emit)
        self.btn_edit.clicked.connect(self.edit_clicked.emit)
        self.btn_del.clicked.connect(self.delete_clicked.emit)

        self.setObjectName(f"EditorTab_{title}")

    def set_actions_enabled(self, enabled: bool) -> None:
        self._actions_enabled = bool(enabled)
        self.btn_add.setEnabled(self._actions_enabled)
        self.btn_edit.setEnabled(self._actions_enabled)
        self.btn_del.setEnabled(self._actions_enabled)

    def _open_context_menu(self, pos: QPoint) -> None:
        if not self._actions_enabled:
            return
        idx = self.table.indexAt(pos)
        if not idx.isValid():
            return
        self.table.selectRow(idx.row())

        menu = QMenu(self)
        act_edit = menu.addAction("Bearbeiten")
        act_del = menu.addAction("Löschen")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))

        if chosen == act_edit:
            self.edit_clicked.emit()
        elif chosen == act_del:
            self.delete_clicked.emit()

    def _emit_edit_if_selected(self) -> None:
        if not self._actions_enabled:
            return
        if self.table.currentRow() >= 0:
            self.edit_clicked.emit()
