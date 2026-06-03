from __future__ import annotations

from typing import Iterable, Optional

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
    QWidget,
)

from ...services.excel_exchange_service import SemesterExportOption, TeacherExportOption


class TeacherExportDialog(QDialog):
    """Select semesters and teachers for the teacher Excel export."""

    def __init__(
        self,
        teachers: Iterable[TeacherExportOption],
        semesters: Iterable[SemesterExportOption] = (),
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("TeacherExportDialog")
        self.setWindowTitle("Export für Lehrende")
        self.setModal(True)
        self.resize(940, 580)
        self.setMinimumSize(760, 500)

        self._teachers = list(teachers)
        self._semesters = list(semesters)
        self._updating_teacher_selection = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        title = QLabel("Export für Lehrende")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        subtitle = QLabel("Wählen Sie aus, welche Lehrpersonen und Semester in die Excel-Datei aufgenommen werden.")
        subtitle.setObjectName("DialogSubtitle")
        root.addWidget(subtitle)

        selection_tools = QHBoxLayout()
        selection_tools.setSpacing(8)
        selection_tools.addStretch(1)

        self.select_all_btn = QPushButton("Alle")
        self.select_all_btn.setObjectName("SecondaryButton")
        self.select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        selection_tools.addWidget(self.select_all_btn)

        self.clear_btn = QPushButton("Keine")
        self.clear_btn.setObjectName("SecondaryButton")
        self.clear_btn.clicked.connect(lambda: self._set_all_checked(False))
        selection_tools.addWidget(self.clear_btn)
        root.addLayout(selection_tools)

        content = QHBoxLayout()
        content.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(8)

        teacher_label = QLabel("Lehrpersonen")
        teacher_label.setObjectName("TeacherExportSectionLabel")
        left.addWidget(teacher_label)

        tools = QHBoxLayout()
        tools.setSpacing(8)

        self.search = QLineEdit(self)
        self.search.setObjectName("TeacherSearch")
        self.search.setPlaceholderText("Lehrperson oder E-Mail suchen")
        self.search.textChanged.connect(self._apply_filter)
        tools.addWidget(self.search, 1)

        left.addLayout(tools)

        self.table = QTableWidget(0, 5, self)
        self.table.setObjectName("TeacherExportTable")
        self.table.setHorizontalHeaderLabels(["", "Lehrperson", "E-Mail", "LVAs", "Termine"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._on_teacher_selection_changed)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 42)

        left.addWidget(self.table, 1)
        content.addLayout(left, 1)

        if self._semesters:
            right_widget = QWidget(self)
            right_widget.setObjectName("TeacherExportSidePanel")
            right_widget.setFixedWidth(300)
            right = QVBoxLayout(right_widget)
            right.setContentsMargins(0, 0, 0, 0)
            right.setSpacing(8)

            semester_header = QHBoxLayout()
            semester_header.setSpacing(8)
            semester_label = QLabel("Semester")
            semester_label.setObjectName("TeacherExportSectionLabel")
            semester_header.addWidget(semester_label, 1)
            right.addLayout(semester_header)

            self.semester_table = QTableWidget(0, 3, self)
            self.semester_table.setObjectName("TeacherExportTable")
            self.semester_table.setHorizontalHeaderLabels(["", "Semester", "Termine"])
            self.semester_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.semester_table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.semester_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.semester_table.verticalHeader().setVisible(False)
            self.semester_table.setAlternatingRowColors(True)

            semester_header_view = self.semester_table.horizontalHeader()
            semester_header_view.setSectionResizeMode(0, QHeaderView.Fixed)
            semester_header_view.setSectionResizeMode(1, QHeaderView.Stretch)
            semester_header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            self.semester_table.setColumnWidth(0, 36)
            self.semester_table.itemChanged.connect(self._on_semester_selection_changed)
            right.addWidget(self.semester_table, 1)

            content.addWidget(right_widget)
        else:
            self.semester_table = None

        root.addLayout(content, 1)

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

        self._populate_semesters()
        self._populate_teachers()
        self._update_teacher_counts()
        self._select_teachers_with_terms()
        self._rebuild_semesters_for_selected_teachers(checked_ids={semester.id for semester in self._semesters[-2:]})

    def selected_teachers(self) -> list[tuple[str, str]]:
        selected = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                value = checkbox.data(Qt.UserRole)
                if value:
                    selected.append((str(value[0]), str(value[1])))
        return selected

    def selected_semester_ids(self) -> Optional[list[str]]:
        if self.semester_table is None:
            return None
        selected = []
        for row in range(self.semester_table.rowCount()):
            checkbox = self.semester_table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                selected.append(str(checkbox.data(Qt.UserRole)))
        return selected

    def _populate_semesters(
        self,
        rows: Optional[list[tuple[SemesterExportOption, int]]] = None,
        checked_ids: Optional[set[str]] = None,
    ) -> None:
        if self.semester_table is None:
            return

        rows = rows if rows is not None else [(semester, semester.term_count) for semester in self._semesters]
        checked_ids = checked_ids if checked_ids is not None else {semester.id for semester in self._semesters[-2:]}

        self.semester_table.blockSignals(True)
        self.semester_table.setRowCount(len(rows))
        for row, (semester, term_count) in enumerate(rows):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            checkbox.setCheckState(Qt.Checked if semester.id in checked_ids else Qt.Unchecked)
            checkbox.setData(Qt.UserRole, semester.id)
            self.semester_table.setItem(row, 0, checkbox)

            self._set_semester_text_item(row, 1, semester.name)
            self._set_semester_text_item(row, 2, str(term_count), Qt.AlignCenter)
        self.semester_table.blockSignals(False)

    def _populate_teachers(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._teachers))
        for row, teacher in enumerate(self._teachers):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            checkbox.setCheckState(Qt.Checked)
            checkbox.setData(Qt.UserRole, teacher.key)
            checkbox.setData(Qt.UserRole + 1, teacher)
            self.table.setItem(row, 0, checkbox)

            self._set_text_item(row, 1, teacher.name)
            self._set_text_item(row, 2, teacher.email or "-")
            self._set_text_item(row, 3, "0", Qt.AlignCenter)
            self._set_text_item(row, 4, "0", Qt.AlignCenter)
        self.table.blockSignals(False)

    def _set_text_item(self, row: int, column: int, text: str, alignment=Qt.AlignVCenter | Qt.AlignLeft) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setTextAlignment(alignment)
        self.table.setItem(row, column, item)

    def _set_semester_text_item(self, row: int, column: int, text: str, alignment=Qt.AlignVCenter | Qt.AlignLeft) -> None:
        if self.semester_table is None:
            return
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setTextAlignment(alignment)
        self.semester_table.setItem(row, column, item)

    def _selected_semesters_for_counts(self) -> Optional[list[str]]:
        selected = self.selected_semester_ids()
        if selected is None:
            return None
        return selected

    def _teacher_for_row(self, row: int) -> Optional[TeacherExportOption]:
        checkbox = self.table.item(row, 0)
        return checkbox.data(Qt.UserRole + 1) if checkbox else None

    def _selected_teacher_options(self) -> list[TeacherExportOption]:
        selected = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                teacher = self._teacher_for_row(row)
                if teacher is not None:
                    selected.append(teacher)
        return selected

    def _update_teacher_counts(self) -> None:
        selected_semesters = self._selected_semesters_for_counts()
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            teacher = self._teacher_for_row(row)
            if teacher is None:
                continue
            lva_count, term_count = teacher.counts_for_semesters(selected_semesters)
            self.table.item(row, 3).setText(str(lva_count))
            self.table.item(row, 4).setText(str(term_count))
        self.table.blockSignals(False)
        self._apply_filter(self.search.text())

    def _rebuild_semesters_for_selected_teachers(
        self,
        checked_ids: Optional[set[str]] = None,
        *,
        check_all_visible: bool = False,
    ) -> None:
        if self.semester_table is None:
            return

        if checked_ids is None:
            checked_ids = set(self.selected_semester_ids() or [])

        selected_teachers = self._selected_teacher_options()
        rows: list[tuple[SemesterExportOption, int]] = []
        for semester in self._semesters:
            term_count = sum(int(teacher.semester_term_counts.get(semester.id, 0)) for teacher in selected_teachers)
            if term_count > 0:
                rows.append((semester, term_count))

        if check_all_visible:
            checked_ids = {semester.id for semester, _term_count in rows}
        elif rows and not any(semester.id in checked_ids for semester, _term_count in rows):
            checked_ids = {semester.id for semester, _term_count in rows}

        self._populate_semesters(rows, checked_ids)

    def _on_semester_selection_changed(self, *_args) -> None:
        self._update_teacher_counts()
        self._update_summary()

    def _on_teacher_selection_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_teacher_selection or item.column() != 0:
            return
        self._rebuild_semesters_for_selected_teachers()
        self._update_teacher_counts()

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

    def _set_all_checked(self, checked: bool) -> None:
        self._set_teacher_checked(checked)
        if checked:
            self._rebuild_semesters_for_selected_teachers(check_all_visible=True)
        else:
            self._populate_semesters([], set())
        self._update_teacher_counts()
        self._update_summary()

    def _set_teacher_checked(self, checked: bool) -> None:
        self._updating_teacher_selection = True
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.table.blockSignals(False)
        self._updating_teacher_selection = False

    def _select_teachers_with_terms(self) -> None:
        self._updating_teacher_selection = True
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            term_count = int(self.table.item(row, 4).text() or "0")
            self.table.item(row, 0).setCheckState(Qt.Checked if term_count > 0 else Qt.Unchecked)
        self.table.blockSignals(False)
        self._updating_teacher_selection = False
        self._rebuild_semesters_for_selected_teachers()
        self._update_teacher_counts()

    def _update_summary(self) -> None:
        selected_teachers = len(self.selected_teachers())
        visible_teachers = sum(not self.table.isRowHidden(row) for row in range(self.table.rowCount()))
        total_terms = 0
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                total_terms += int(self.table.item(row, 4).text() or "0")

        selected_semesters = self.selected_semester_ids()
        has_semester_selection = selected_semesters is not None
        semester_count = len(selected_semesters or [])

        if has_semester_selection:
            self.summary.setText(
                f"{selected_teachers} Lehrende · {visible_teachers} sichtbar · "
                f"{semester_count} Semester · {total_terms} Termine"
            )
            self.export_btn.setEnabled(selected_teachers > 0 and semester_count > 0)
        else:
            self.summary.setText(f"{selected_teachers} ausgewählt · {visible_teachers} sichtbar · {total_terms} Termine")
            self.export_btn.setEnabled(selected_teachers > 0)
