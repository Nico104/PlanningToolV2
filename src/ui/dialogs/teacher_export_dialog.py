from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.services.excel_exchange_service import TeacherExportOption


class TeacherExportDialog(QDialog):
    """Selects the teachers that should be included in the teacher Excel export."""

    def __init__(self, teachers: Iterable[TeacherExportOption], parent=None):
        super().__init__(parent)
        self.setObjectName("TeacherExportDialog")
        self.setWindowTitle("Export für Lehrende")
        self.setModal(True)
        self.resize(760, 560)
        self.setMinimumSize(640, 460)

        self._teachers = list(teachers)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        title = QLabel("Export für Lehrende")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        subtitle = QLabel("Wählen Sie aus, welche Lehrpersonen in die Excel-Datei aufgenommen werden.")
        subtitle.setObjectName("DialogSubtitle")
        root.addWidget(subtitle)

        tools = QHBoxLayout()
        tools.setSpacing(8)

        self.search = QLineEdit(self)
        self.search.setObjectName("TeacherSearch")
        self.search.setPlaceholderText("Lehrperson oder E-Mail suchen")
        self.search.textChanged.connect(self._apply_filter)
        tools.addWidget(self.search, 1)

        self.select_all_btn = QPushButton("Alle")
        self.select_all_btn.setObjectName("SecondaryButton")
        self.select_all_btn.clicked.connect(lambda: self._set_visible_checked(True))
        tools.addWidget(self.select_all_btn)

        self.select_active_btn = QPushButton("Mit Terminen")
        self.select_active_btn.setObjectName("SecondaryButton")
        self.select_active_btn.clicked.connect(self._select_with_terms)
        tools.addWidget(self.select_active_btn)

        self.clear_btn = QPushButton("Keine")
        self.clear_btn.setObjectName("SecondaryButton")
        self.clear_btn.clicked.connect(lambda: self._set_visible_checked(False))
        tools.addWidget(self.clear_btn)

        root.addLayout(tools)

        self.table = QTableWidget(0, 5, self)
        self.table.setObjectName("TeacherExportTable")
        self.table.setHorizontalHeaderLabels(["", "Lehrperson", "E-Mail", "LVAs", "Termine"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._update_summary)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 42)

        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.summary = QLabel()
        self.summary.setObjectName("TeacherExportSummary")
        bottom.addWidget(self.summary, 1)

        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.setObjectName("SecondaryButton")
        self.cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(self.cancel_btn)

        self.export_btn = QPushButton("Exportieren")
        self.export_btn.setObjectName("PrimaryButton")
        self.export_btn.clicked.connect(self.accept)
        bottom.addWidget(self.export_btn)
        root.addLayout(bottom)

        self._populate()
        self._update_summary()

    def selected_teachers(self) -> list[tuple[str, str]]:
        selected = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                selected.append(checkbox.data(Qt.UserRole))
        return selected

    def _populate(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._teachers))
        for row, teacher in enumerate(self._teachers):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            checkbox.setCheckState(Qt.Checked)
            checkbox.setData(Qt.UserRole, teacher.key)
            self.table.setItem(row, 0, checkbox)

            self._set_text_item(row, 1, teacher.name)
            self._set_text_item(row, 2, teacher.email or "-")
            self._set_text_item(row, 3, str(teacher.lva_count), Qt.AlignCenter)
            self._set_text_item(row, 4, str(teacher.term_count), Qt.AlignCenter)
        self.table.blockSignals(False)

    def _set_text_item(self, row: int, column: int, text: str, alignment=Qt.AlignVCenter | Qt.AlignLeft) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setTextAlignment(alignment)
        self.table.setItem(row, column, item)

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for row in range(self.table.rowCount()):
            haystack = " ".join(
                self.table.item(row, col).text().lower()
                for col in range(1, self.table.columnCount())
                if self.table.item(row, col)
            )
            self.table.setRowHidden(row, bool(needle and needle not in haystack))
        self._update_summary()

    def _set_visible_checked(self, checked: bool) -> None:
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            self.table.item(row, 0).setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.table.blockSignals(False)
        self._update_summary()

    def _select_with_terms(self) -> None:
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            term_count = int(self.table.item(row, 4).text() or "0")
            self.table.item(row, 0).setCheckState(Qt.Checked if term_count > 0 else Qt.Unchecked)
        self.table.blockSignals(False)
        self._update_summary()

    def _update_summary(self) -> None:
        selected = len(self.selected_teachers())
        visible = sum(not self.table.isRowHidden(row) for row in range(self.table.rowCount()))
        total_terms = 0
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                total_terms += int(self.table.item(row, 4).text() or "0")

        self.summary.setText(f"{selected} ausgewählt · {visible} sichtbar · {total_terms} Termine")
        self.export_btn.setEnabled(selected > 0)
