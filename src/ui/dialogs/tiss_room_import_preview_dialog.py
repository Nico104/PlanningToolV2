from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class TissRoomImportPreviewDialog(QDialog):
    def __init__(self, parent: QWidget, rooms: list[dict[str, Any]]):
        super().__init__(parent)
        self.setObjectName("TissRoomImportPreviewDialog")
        self.setModal(True)
        self.setWindowTitle("TISS-Raumliste prüfen")
        self.resize(760, 500)
        self.setMinimumSize(640, 420)

        self._preview_rows = [self._build_preview_row(room) for room in rooms]

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("TISS-Raumliste prüfen", self)
        title.setObjectName("TissRoomImportTitle")

        self.summary_label = QLabel(self)
        self.summary_label.setObjectName("TissRoomImportSummary")
        self.summary_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        header_row.addWidget(title)
        header_row.addStretch(1)
        header_row.addWidget(self.summary_label)
        root.addLayout(header_row)

        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName("TissRoomImportTable")
        self.table.setHorizontalHeaderLabels(["", "Raumnummer", "Raum", "Kapazität"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.verticalHeader().setMinimumSectionSize(28)
        self.table.itemChanged.connect(self._refresh_summary)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 38)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(3, 100)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton("Abbrechen", self)
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(cancel_btn)

        self.import_btn = QPushButton("Räume importieren", self)
        self.import_btn.setObjectName("PrimaryButton")
        self.import_btn.clicked.connect(self.accept)
        actions.addWidget(self.import_btn)
        root.addLayout(actions)

        self._fill_table()
        self._refresh_summary()

    @property
    def selected_rooms(self) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for row, preview in enumerate(self._preview_rows):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                selected.append(dict(preview["room"]))
        return selected

    def _build_preview_row(self, room: dict[str, Any]) -> dict[str, Any]:
        room_id = str(room.get("id", "")).strip()
        name = str(room.get("name", "")).strip()
        capacity = self._safe_int(room.get("kapazitaet"))

        return {
            "room": {
                "id": room_id,
                "name": name,
                "kapazitaet": capacity,
            }
        }

    def _fill_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._preview_rows))
        for row, preview in enumerate(self._preview_rows):
            room = preview["room"]
            self._set_checkbox_item(row)
            self._set_text_item(row, 1, room["id"])
            self._set_text_item(row, 2, room["name"])
            self._set_text_item(row, 3, str(room["kapazitaet"]), Qt.AlignCenter)
        self.table.blockSignals(False)

    def _set_checkbox_item(self, row: int) -> None:
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
        item.setCheckState(Qt.Checked)
        self.table.setItem(row, 0, item)

    def _set_text_item(self, row: int, column: int, text: str, alignment=Qt.AlignVCenter | Qt.AlignLeft) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setTextAlignment(alignment)
        self.table.setItem(row, column, item)

    def _refresh_summary(self, *_args) -> None:
        total = len(self._preview_rows)
        selected = len(self.selected_rooms)
        self.summary_label.setText(f"{selected} ausgewählt · {total} Räume erkannt")
        self.import_btn.setEnabled(selected > 0)

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
