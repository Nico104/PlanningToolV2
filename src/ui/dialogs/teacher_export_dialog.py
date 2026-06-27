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
        self.setWindowTitle("Export für Lehrende")
        self.setModal(True)
        self.resize(1120, 720)
        self.setMinimumSize(920, 640)

        self._lvas = list(teachers)
        self._teachers = self._lvas
        self._semesters = list(semesters)
        self._updating_teacher_selection = False
        today = date.today()
        self._default_from = default_from or today
        self._default_to = default_to or self._default_from

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        title = QLabel("Export für Lehrende")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Termine nach LVA, Lehrperson, Semester und Zeitraum als Excel-Datei exportieren."
        )
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

        self.only_with_terms_cb = QCheckBox("Nur LVAs mit Terminen")
        self.only_with_terms_cb.setChecked(True)
        self.only_with_terms_cb.stateChanged.connect(self._apply_filter)
        tools.addWidget(self.only_with_terms_cb)

        left.addLayout(tools)

        self.table = QTableWidget(0, 5, self)
        self.table.setObjectName("TeacherExportTable")
        self.table.setHorizontalHeaderLabels(
            ["", "LVA-Nr.", "Lehrveranstaltung", "Lehrperson", "Termine"]
        )
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
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 42)
        self.table.setColumnWidth(3, 260)

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
        self.date_from_de.dateChanged.connect(self._update_teacher_counts)
        self.date_to_de.dateChanged.connect(self._update_teacher_counts)
        range_form.addRow("Von:", self.date_from_de)
        range_form.addRow("Bis:", self.date_to_de)
        right.addLayout(range_form)

        range_help = QLabel(
            "Exportiert werden Termine, die im Zeitraum und in den ausgewählten Semestern liegen."
        )
        range_help.setObjectName("TeacherExportHint")
        range_help.setWordWrap(True)
        right.addWidget(range_help)

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
        self._rebuild_semesters_for_selected_teachers(
            checked_ids=self._default_checked_semester_ids()
        )
        self._update_teacher_counts()

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

    def selected_term_count(self) -> int:
        total = 0
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                total += self._row_term_count(row)
        return total

    def selected_lva_count_with_terms(self) -> int:
        count = 0
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked and self._row_term_count(row) > 0:
                count += 1
        return count

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
    def _count_text(count: int, singular: str, plural: str) -> str:
        return f"{count} {singular if count == 1 else plural}"

    def _default_checked_semester_ids(self) -> set[str]:
        selected_teachers = self._selected_teacher_options()
        in_range = {
            semester.id
            for semester in self._semesters
            if self._term_count_for_semester_in_current_range(semester.id, selected_teachers) > 0
        }
        if in_range:
            return in_range
        return {semester.id for semester in self._semesters if semester.term_count > 0}

    def _populate_semesters(
        self,
        rows: Optional[list[tuple[SemesterExportOption, int]]] = None,
        checked_ids: Optional[set[str]] = None,
    ) -> None:
        if self.semester_table is None:
            return

        rows = (
            rows
            if rows is not None
            else [(semester, semester.term_count) for semester in self._semesters]
        )
        checked_ids = (
            checked_ids if checked_ids is not None else self._default_checked_semester_ids()
        )

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
            teacher_tooltip = teacher_text
            if lva.teacher_email:
                teacher_tooltip = f"{teacher_text}\n{lva.teacher_email}"
            self._set_text_item(row, 3, teacher_text, tooltip=teacher_tooltip)
            self._set_text_item(row, 4, "0", Qt.AlignCenter)
        self.table.blockSignals(False)

    def _set_text_item(
        self,
        row: int,
        column: int,
        text: str,
        alignment=Qt.AlignVCenter | Qt.AlignLeft,
        *,
        tooltip: Optional[str] = None,
    ) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setTextAlignment(alignment)
        item.setToolTip(tooltip or text)
        self.table.setItem(row, column, item)

    def _set_semester_text_item(
        self, row: int, column: int, text: str, alignment=Qt.AlignVCenter | Qt.AlignLeft
    ) -> None:
        if self.semester_table is None:
            return
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setTextAlignment(alignment)
        item.setToolTip(text)
        self.semester_table.setItem(row, column, item)

    def _selected_semesters_for_counts(self) -> Optional[list[str]]:
        selected = self.selected_semester_ids()
        if selected is None:
            return None
        return selected

    def _teacher_for_row(self, row: int) -> Optional[LvaExportOption]:
        checkbox = self.table.item(row, 0)
        return checkbox.data(Qt.UserRole + 1) if checkbox else None

    def _row_term_count(self, row: int) -> int:
        item = self.table.item(row, 4)
        if item is None:
            return 0
        try:
            return int(item.text() or "0")
        except ValueError:
            return 0

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
        date_from, date_to = self.selected_date_range()
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            teacher = self._teacher_for_row(row)
            if teacher is None:
                continue
            lva_count, term_count = teacher.counts_for_filters(
                selected_semesters, date_from, date_to
            )
            self.table.item(row, 4).setText(str(term_count))
        self.table.blockSignals(False)
        self._update_semester_counts_for_current_range()
        self._apply_filter(self.search.text())

    def _term_count_for_semester_in_current_range(
        self, semester_id: str, teachers: list[LvaExportOption]
    ) -> int:
        date_from, date_to = self.selected_date_range()
        total = 0
        for teacher in teachers:
            _lva_count, term_count = teacher.counts_for_filters([semester_id], date_from, date_to)
            total += term_count
        return total

    def _update_semester_counts_for_current_range(self) -> None:
        if self.semester_table is None:
            return
        teachers = self._selected_teacher_options()
        self.semester_table.blockSignals(True)
        try:
            for row in range(self.semester_table.rowCount()):
                checkbox = self.semester_table.item(row, 0)
                count_item = self.semester_table.item(row, 2)
                if checkbox is None or count_item is None:
                    continue
                semester_id = str(checkbox.data(Qt.UserRole) or "")
                count_item.setText(
                    str(self._term_count_for_semester_in_current_range(semester_id, teachers))
                )
        finally:
            self.semester_table.blockSignals(False)

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
            term_count = self._term_count_for_semester_in_current_range(
                semester.id, selected_teachers
            )
            rows.append((semester, term_count))

        if check_all_visible:
            checked_ids = {semester.id for semester, term_count in rows if term_count > 0}

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
        needle = (
            self.search.text().strip().lower()
            if isinstance(text, int)
            else str(text or "").strip().lower()
        )
        only_with_terms = self.only_with_terms_cb.isChecked()
        for row in range(self.table.rowCount()):
            teacher = self._teacher_for_row(row)
            haystack = " ".join(
                [
                    *[
                        self.table.item(row, col).text().lower()
                        for col in range(1, self.table.columnCount())
                        if self.table.item(row, col)
                    ],
                    teacher.teacher_name.lower() if teacher else "",
                    teacher.teacher_email.lower() if teacher else "",
                ]
            )
            hidden = bool(needle and needle not in haystack)
            if only_with_terms and (teacher is None or teacher.term_count <= 0):
                hidden = True
            self.table.setRowHidden(row, hidden)
        self._update_summary()

    def _set_all_checked(self, checked: bool) -> None:
        self._set_teacher_checked(checked)
        self._rebuild_semesters_for_selected_teachers()
        self._update_teacher_counts()
        self._update_summary()

    def _set_teacher_checked(self, checked: bool) -> None:
        self._updating_teacher_selection = True
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            self.table.item(row, 0).setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.table.blockSignals(False)
        self._updating_teacher_selection = False

    def _select_teachers_with_terms(self) -> None:
        self._updating_teacher_selection = True
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            teacher = self._teacher_for_row(row)
            has_terms = teacher is not None and teacher.term_count > 0
            self.table.item(row, 0).setCheckState(Qt.Checked if has_terms else Qt.Unchecked)
        self.table.blockSignals(False)
        self._updating_teacher_selection = False
        self._rebuild_semesters_for_selected_teachers()
        self._update_teacher_counts()

    def _update_summary(self) -> None:
        selected_lvas = len(self.selected_lva_ids())
        visible_teachers = sum(
            not self.table.isRowHidden(row) for row in range(self.table.rowCount())
        )
        total_terms = self.selected_term_count()
        selected_lvas_with_terms = self.selected_lva_count_with_terms()

        selected_semesters = self.selected_semester_ids()
        has_semester_selection = selected_semesters is not None
        semester_count = len(selected_semesters or [])

        if has_semester_selection:
            calendar_options = ""
            if self.selected_export_format() == "calendar":
                days = "mit Wochenende" if self.selected_include_weekend() else "Mo-Fr"
                raster = "60 min" if self.selected_calendar_slot_minutes() == 60 else "30 min"
                calendar_options = f" · {days} · {raster}"
            terms_text = self._count_text(total_terms, "Termin", "Termine")
            lvas_text = self._count_text(selected_lvas_with_terms, "LVA", "LVAs")
            semester_text = self._count_text(semester_count, "Semester", "Semestern")
            self.summary.setText(
                f"Export: {terms_text} aus {lvas_text} in "
                f"{semester_text} · {visible_teachers} sichtbar · "
                f"{self.selected_export_format_label()}{calendar_options}"
            )
            self.export_btn.setText(
                f"{terms_text} exportieren" if total_terms > 0 else "Keine Termine ausgewählt"
            )
            self.export_btn.setEnabled(selected_lvas > 0 and semester_count > 0 and total_terms > 0)
        else:
            calendar_options = ""
            if self.selected_export_format() == "calendar":
                days = "mit Wochenende" if self.selected_include_weekend() else "Mo-Fr"
                raster = "60 min" if self.selected_calendar_slot_minutes() == 60 else "30 min"
                calendar_options = f" · {days} · {raster}"
            terms_text = self._count_text(total_terms, "Termin", "Termine")
            lvas_text = self._count_text(selected_lvas_with_terms, "LVA", "LVAs")
            self.summary.setText(
                f"Export: {terms_text} aus {lvas_text} · "
                f"{visible_teachers} sichtbar · {self.selected_export_format_label()}{calendar_options}"
            )
            self.export_btn.setText(
                f"{terms_text} exportieren" if total_terms > 0 else "Keine Termine ausgewählt"
            )
            self.export_btn.setEnabled(selected_lvas > 0 and total_terms > 0)
