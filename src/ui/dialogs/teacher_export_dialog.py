from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...services.excel_exchange_service import LvaExportOption, SemesterExportOption
from ...services.semester_rules import semester_from_id


class TeacherExportDialog(QDialog):
    """Select semesters and teachers for the teacher Excel export."""

    def __init__(
        self,
        teachers: Iterable[LvaExportOption],
        semesters: Iterable[SemesterExportOption] = (),
        default_from: Optional[date] = None,
        default_to: Optional[date] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("TeacherExportDialog")
        self.setWindowTitle("Terminexport")
        self.setModal(True)
        self.resize(1120, 720)
        self.setMinimumSize(920, 640)

        self._lvas = list(teachers)
        self._teachers = self._lvas
        self._semesters = list(semesters)
        self._updating_teacher_selection = False
        self._syncing_date_range = False
        today = date.today()
        self._default_from = default_from or today
        self._default_to = default_to or self._default_from

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        title = QLabel("Terminexport")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        subtitle = QLabel("Wählen Sie aus, welche LVAs, Semester und welches Format exportiert werden.")
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

        teacher_label = QLabel("LVAs und Lehrpersonen")
        teacher_label.setObjectName("TeacherExportSectionLabel")
        left.addWidget(teacher_label)

        tools = QHBoxLayout()
        tools.setSpacing(8)

        self.search = QLineEdit(self)
        self.search.setObjectName("TeacherSearch")
        self.search.setPlaceholderText("LVA, Lehrperson oder E-Mail suchen")
        self.search.textChanged.connect(self._apply_filter)
        tools.addWidget(self.search, 1)

        left.addLayout(tools)

        self.table = QTableWidget(0, 5, self)
        self.table.setObjectName("TeacherExportTable")
        self.table.setHorizontalHeaderLabels(["", "LVA-Nr.", "Lehrveranstaltung", "Lehrperson", "Termine"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._on_teacher_selection_changed)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 42)

        left.addWidget(self.table, 1)
        content.addLayout(left, 1)

        right_widget = QWidget(self)
        right_widget.setObjectName("TeacherExportSidePanel")
        right_widget.setFixedWidth(360)
        right = QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(10)

        format_label = QLabel("Export")
        format_label.setObjectName("TeacherExportSectionLabel")
        right.addWidget(format_label)

        self.format_group = QButtonGroup(self)
        self.list_format_rb = QRadioButton("Tabellenliste")
        self.calendar_format_rb = QRadioButton("Wochenkalender")
        self.list_format_rb.setChecked(True)
        self.format_group.addButton(self.list_format_rb)
        self.format_group.addButton(self.calendar_format_rb)
        self.format_group.buttonToggled.connect(lambda *_args: self._update_summary())
        right.addWidget(self.list_format_rb)
        right.addWidget(self.calendar_format_rb)

        range_label = QLabel("Zeitraum")
        range_label.setObjectName("TeacherExportSectionLabel")
        right.addWidget(range_label)

        range_form = QFormLayout()
        range_form.setContentsMargins(0, 0, 0, 0)
        range_form.setSpacing(8)
        self.date_from_de = self._new_date_edit(self._default_from)
        self.date_to_de = self._new_date_edit(self._default_to)
        self.date_from_de.dateChanged.connect(self._update_summary)
        self.date_to_de.dateChanged.connect(self._update_summary)
        range_form.addRow("Von:", self.date_from_de)
        range_form.addRow("Bis:", self.date_to_de)
        right.addLayout(range_form)

        calendar_label = QLabel("Kalender")
        calendar_label.setObjectName("TeacherExportSectionLabel")
        right.addWidget(calendar_label)

        self.include_weekend_cb = QCheckBox("Wochenende mit exportieren")
        self.include_weekend_cb.setChecked(False)
        self.include_weekend_cb.stateChanged.connect(self._update_summary)
        right.addWidget(self.include_weekend_cb)

        self.slot_group = QButtonGroup(self)
        self.half_hour_rb = QRadioButton("Halbstündlich")
        self.full_hour_rb = QRadioButton("Stündlich")
        self.half_hour_rb.setChecked(True)
        self.slot_group.addButton(self.half_hour_rb)
        self.slot_group.addButton(self.full_hour_rb)
        self.slot_group.buttonToggled.connect(lambda *_args: self._update_summary())
        right.addWidget(self.half_hour_rb)
        right.addWidget(self.full_hour_rb)

        if self._semesters:
            right.addSpacing(6)

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
        else:
            self.semester_table = None

        content.addWidget(right_widget)
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

    def selected_lva_ids(self) -> list[str]:
        selected = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                value = checkbox.data(Qt.UserRole)
                if value:
                    selected.append(str(value))
        return selected

    def selected_teachers(self) -> list[tuple[str, str]]:
        seen: set[tuple[str, str]] = set()
        selected: list[tuple[str, str]] = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                option = self._teacher_for_row(row)
                if option is None or not option.teacher_name:
                    continue
                key = (option.teacher_name, option.teacher_email)
                if key not in seen:
                    selected.append(key)
                    seen.add(key)
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

    def selected_export_format(self) -> str:
        return "calendar" if self.calendar_format_rb.isChecked() else "list"

    def selected_export_format_label(self) -> str:
        return "Wochenkalender" if self.selected_export_format() == "calendar" else "Tabellenliste"

    def selected_date_range(self) -> tuple[date, date]:
        start = self._date_from_edit(self.date_from_de)
        end = self._date_from_edit(self.date_to_de)
        if end < start:
            return end, start
        return start, end

    def selected_include_weekend(self) -> bool:
        return self.include_weekend_cb.isChecked()

    def selected_calendar_slot_minutes(self) -> int:
        return 60 if self.full_hour_rb.isChecked() else 30

    def _new_date_edit(self, value: date) -> QDateEdit:
        edit = QDateEdit(self)
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd.MM.yyyy")
        edit.setDate(QDate(value.year, value.month, value.day))
        return edit

    @staticmethod
    def _date_from_edit(edit: QDateEdit) -> date:
        qdate = edit.date()
        return date(qdate.year(), qdate.month(), qdate.day())

    @staticmethod
    def _set_date_edit(edit: QDateEdit, value: date) -> None:
        edit.setDate(QDate(value.year, value.month, value.day))

    def _sync_date_range_to_selected_semesters(self) -> None:
        if self.semester_table is None or self._syncing_date_range:
            return

        selected = self.selected_semester_ids() or []
        semesters = [semester_from_id(semester_id) for semester_id in selected]
        semesters = [semester for semester in semesters if semester is not None]
        if not semesters:
            return

        self._syncing_date_range = True
        self.date_from_de.blockSignals(True)
        self.date_to_de.blockSignals(True)
        try:
            self._set_date_edit(self.date_from_de, min(semester.start for semester in semesters))
            self._set_date_edit(self.date_to_de, max(semester.end for semester in semesters))
        finally:
            self.date_from_de.blockSignals(False)
            self.date_to_de.blockSignals(False)
            self._syncing_date_range = False
        self._update_summary()

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
        self._sync_date_range_to_selected_semesters()

    def _populate_teachers(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._teachers))
        for row, lva in enumerate(self._teachers):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            checkbox.setCheckState(Qt.Checked)
            checkbox.setData(Qt.UserRole, lva.id)
            checkbox.setData(Qt.UserRole + 1, lva)
            self.table.setItem(row, 0, checkbox)

            self._set_text_item(row, 1, lva.id)
            self._set_text_item(row, 2, lva.name or "-")
            teacher_text = lva.teacher_name or "-"
            if lva.teacher_email:
                teacher_text = f"{teacher_text} · {lva.teacher_email}"
            self._set_text_item(row, 3, teacher_text)
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

    def _teacher_for_row(self, row: int) -> Optional[LvaExportOption]:
        checkbox = self.table.item(row, 0)
        return checkbox.data(Qt.UserRole + 1) if checkbox else None

    def _selected_teacher_options(self) -> list[LvaExportOption]:
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
        self._sync_date_range_to_selected_semesters()
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
        selected_lvas = len(self.selected_lva_ids())
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
            calendar_options = ""
            if self.selected_export_format() == "calendar":
                days = "mit Wochenende" if self.selected_include_weekend() else "Mo-Fr"
                raster = "60 min" if self.selected_calendar_slot_minutes() == 60 else "30 min"
                calendar_options = f" · {days} · {raster}"
            self.summary.setText(
                f"{selected_lvas} LVAs · {visible_teachers} sichtbar · "
                f"{semester_count} Semester · {total_terms} Termine · {self.selected_export_format_label()}{calendar_options}"
            )
            self.export_btn.setEnabled(selected_lvas > 0 and semester_count > 0)
        else:
            calendar_options = ""
            if self.selected_export_format() == "calendar":
                days = "mit Wochenende" if self.selected_include_weekend() else "Mo-Fr"
                raster = "60 min" if self.selected_calendar_slot_minutes() == 60 else "30 min"
                calendar_options = f" · {days} · {raster}"
            self.summary.setText(
                f"{selected_lvas} LVAs · {visible_teachers} sichtbar · "
                f"{total_terms} Termine · {self.selected_export_format_label()}{calendar_options}"
            )
            self.export_btn.setEnabled(selected_lvas > 0)
