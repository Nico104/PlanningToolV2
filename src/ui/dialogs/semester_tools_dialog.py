from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.models import Lehrveranstaltung, Semester, Termin
from ...services.semester_rules import semester_from_id
from ...services.semester_tools_service import (
    DATE_MODE_PLUS_YEAR,
    DATE_MODE_SEMESTER_WEEK,
    count_semester_termine,
    semester_lva_summaries,
)
from ..components.widgets.semester_selector import SemesterSelector


@dataclass(frozen=True)
class SemesterToolRequest:
    action: str
    source: Optional[Semester] = None
    target: Optional[Semester] = None
    semester: Optional[Semester] = None
    lva_ids: tuple[str, ...] = ()
    date_mode: str = DATE_MODE_SEMESTER_WEEK
    copy_ausfall_daten: bool = False


class SemesterToolsDialog(QDialog):
    def __init__(
        self,
        parent,
        *,
        termine: Iterable[Termin],
        lvas: Iterable[Lehrveranstaltung],
        default_semester_id: Optional[str] = None,
    ):
        super().__init__(parent)
        self.setObjectName("SemesterToolsDialog")
        self.setModal(True)
        self.setWindowTitle("Semester-Werkzeuge")
        self.resize(820, 620)
        self.setMinimumSize(720, 520)

        self._termine = list(termine)
        self._lvas = list(lvas)
        self._semester_by_id: dict[str, Semester] = {}
        self._result: Optional[SemesterToolRequest] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        title = QLabel("Semester-Werkzeuge", self)
        title.setObjectName("SemesterToolsTitle")
        root.addWidget(title)
        subtitle = QLabel(
            "Termine semesterweise kopieren oder aus einem Semester entfernen.",
            self,
        )
        subtitle.setObjectName("SemesterToolsSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        tabs = QTabWidget(self)
        tabs.setObjectName("SemesterToolsTabs")
        tabs.addTab(self._build_copy_tab(), "Kopieren")
        tabs.addTab(self._build_clear_tab(), "Leeren")
        root.addWidget(tabs, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.close_btn = QPushButton("Schließen", self)
        self.close_btn.setObjectName("SecondaryButton")
        self.close_btn.clicked.connect(self.reject)
        bottom.addWidget(self.close_btn)
        root.addLayout(bottom)

        if default_semester_id:
            self.copy_source_selector.set_semester_id(default_semester_id, emit=True)
            self.clear_selector.set_semester_id(default_semester_id, emit=True)
        self._set_default_copy_target()
        self._refresh_copy_table()
        self._refresh_clear_table()

    @property
    def result_request(self) -> Optional[SemesterToolRequest]:
        return self._result

    def _build_copy_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(12)

        intro = QLabel("Ausgewählte LVAs aus einem Quellsemester in ein Zielsemester kopieren.", self)
        intro.setObjectName("SemesterToolsHelp")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        controls = QFormLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setHorizontalSpacing(14)
        controls.setVerticalSpacing(10)
        controls.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.copy_source_selector = SemesterSelector(self, include_all=False)
        self.copy_target_selector = SemesterSelector(self, include_all=False)
        self.copy_source_selector.semesterChanged.connect(self._refresh_copy_table)
        self.copy_target_selector.semesterChanged.connect(self._refresh_copy_summary)
        controls.addRow("Quelle:", self.copy_source_selector)
        controls.addRow("Ziel:", self.copy_target_selector)
        layout.addWidget(self._section("Quelle und Ziel", controls))

        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)
        self.mode_group = QButtonGroup(self)
        self.mode_week_rb = QRadioButton("Gleiche Position im Semester", self)
        self.mode_year_rb = QRadioButton("Gleicher Kalendertag", self)
        self.mode_week_rb.setChecked(True)
        self.mode_group.addButton(self.mode_week_rb)
        self.mode_group.addButton(self.mode_year_rb)
        self.mode_group.buttonClicked.connect(self._refresh_copy_summary)
        mode_row.addWidget(self.mode_week_rb)
        mode_row.addWidget(self.mode_year_rb)
        mode_row.addStretch(1)
        mode_help = QLabel("Gleiche Position im Semester übernimmt den gleichen n-ten Wochentag seit Semesterbeginn, z. B. 2. Dienstag zu 2. Dienstag. Gleicher Kalendertag verschiebt das Datum um ein Jahr.", self)
        mode_help.setObjectName("SemesterToolsHelp")
        mode_help.setWordWrap(True)
        mode_layout = QVBoxLayout()
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(8)
        mode_layout.addLayout(mode_row)
        mode_layout.addWidget(mode_help)
        layout.addWidget(self._section("Datumsübernahme", mode_layout))

        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.copy_summary = QLabel(self)
        self.copy_summary.setObjectName("SemesterToolsSummary")
        tools.addWidget(self.copy_summary, 1)
        layout.addWidget(self._section("Auswahl", tools))

        self.copy_table = self._new_table(["", "LVA", "Typ", "Termine"])
        self.copy_table.itemChanged.connect(self._refresh_copy_summary)
        layout.addWidget(self.copy_table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.copy_btn = QPushButton("Ausgewählte Termine kopieren", self)
        self.copy_btn.setObjectName("PrimaryButton")
        self.copy_btn.clicked.connect(self._accept_copy)
        actions.addWidget(self.copy_btn)
        layout.addLayout(actions)

        return tab

    def _build_clear_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(12)

        intro = QLabel("Alle Termine des gewählten Semesters werden zur Kontrolle aufgelistet.", self)
        intro.setObjectName("SemesterToolsHelp")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        controls = QFormLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setHorizontalSpacing(14)
        controls.setVerticalSpacing(10)
        controls.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.clear_selector = SemesterSelector(self, include_all=False)
        self.clear_selector.semesterChanged.connect(self._refresh_clear_table)
        controls.addRow("Semester:", self.clear_selector)
        layout.addWidget(self._section("Semester", controls))

        self.clear_summary = QLabel(self)
        self.clear_summary.setObjectName("SemesterToolsSummary")
        summary_layout = QHBoxLayout()
        summary_layout.addWidget(self.clear_summary)
        layout.addWidget(self._section("Betroffene Termine", summary_layout))

        self.clear_table = self._new_table(["LVA", "Typ", "Termine"])
        self.clear_table.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.clear_table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.clear_btn = QPushButton("Termine aus Semester löschen", self)
        self.clear_btn.setObjectName("DangerButton")
        self.clear_btn.clicked.connect(self._accept_clear)
        actions.addWidget(self.clear_btn)
        layout.addLayout(actions)

        return tab

    def _section(self, title: str, content_layout) -> QFrame:
        section = QFrame(self)
        section.setObjectName("SemesterToolsSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        label = QLabel(title, self)
        label.setObjectName("SemesterToolsSectionTitle")
        layout.addWidget(label)
        layout.addLayout(content_layout)
        return section

    def _new_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers), self)
        table.setObjectName("SemesterToolsTable")
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)

        header = table.horizontalHeader()
        for column in range(len(headers)):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        stretch_column = 1 if len(headers) == 4 else 0
        header.setSectionResizeMode(stretch_column, QHeaderView.Stretch)
        if len(headers) == 4:
            table.setColumnWidth(0, 42)
        return table

    def _semester_from_selector(self, selector: SemesterSelector) -> Optional[Semester]:
        semester_id = selector.current_semester_id()
        if not semester_id:
            return None
        existing = self._semester_by_id.get(str(semester_id))
        if existing:
            return existing
        semester = semester_from_id(str(semester_id))
        if semester:
            self._semester_by_id[semester.id] = semester
        return semester

    def _source_semester(self) -> Optional[Semester]:
        return self._semester_from_selector(self.copy_source_selector)

    def _target_semester(self) -> Optional[Semester]:
        return self._semester_from_selector(self.copy_target_selector)

    def _clear_semester(self) -> Optional[Semester]:
        return self._semester_from_selector(self.clear_selector)

    def _set_default_copy_target(self) -> None:
        kind = self.copy_source_selector.current_kind()
        if not kind:
            return
        target_id = f"{kind}{(self.copy_source_selector.current_year() + 1) % 100:02d}"
        self.copy_target_selector.set_semester_id(target_id, emit=True)

    def _refresh_copy_table(self, *_args) -> None:
        source = self._source_semester()
        summaries = semester_lva_summaries(self._termine, self._lvas, source.id if source else "")

        self.copy_table.blockSignals(True)
        self.copy_table.setRowCount(len(summaries))
        for row, summary in enumerate(summaries):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            checkbox.setCheckState(Qt.Checked)
            checkbox.setData(Qt.UserRole, summary.lva_id)
            self.copy_table.setItem(row, 0, checkbox)

            self._set_text_item(self.copy_table, row, 1, f"{summary.lva_id} - {summary.lva_name}")
            self._set_text_item(self.copy_table, row, 2, summary.typ or "-")
            self._set_text_item(self.copy_table, row, 3, str(summary.count), Qt.AlignCenter)
        self.copy_table.blockSignals(False)
        self._refresh_copy_summary()

    def _refresh_clear_table(self, *_args) -> None:
        semester = self._clear_semester()
        summaries = semester_lva_summaries(self._termine, self._lvas, semester.id if semester else "")

        self.clear_table.setRowCount(len(summaries))
        for row, summary in enumerate(summaries):
            self._set_text_item(self.clear_table, row, 0, f"{summary.lva_id} - {summary.lva_name}")
            self._set_text_item(self.clear_table, row, 1, summary.typ or "-")
            self._set_text_item(self.clear_table, row, 2, str(summary.count), Qt.AlignCenter)
        self._refresh_clear_summary()

    def _set_text_item(
        self,
        table: QTableWidget,
        row: int,
        column: int,
        text: str,
        alignment=Qt.AlignVCenter | Qt.AlignLeft,
    ) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setTextAlignment(alignment)
        table.setItem(row, column, item)

    def _selected_copy_lva_ids(self) -> tuple[str, ...]:
        selected: list[str] = []
        for row in range(self.copy_table.rowCount()):
            checkbox = self.copy_table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                selected.append(str(checkbox.data(Qt.UserRole)))
        return tuple(selected)

    def _selected_copy_term_count(self) -> int:
        total = 0
        for row in range(self.copy_table.rowCount()):
            checkbox = self.copy_table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                total += int(self.copy_table.item(row, 3).text() or "0")
        return total

    def _refresh_copy_summary(self, *_args) -> None:
        source = self._source_semester()
        target = self._target_semester()
        selected_lvas = len(self._selected_copy_lva_ids()) if hasattr(self, "copy_table") else 0
        selected_terms = self._selected_copy_term_count() if hasattr(self, "copy_table") else 0
        target_terms = count_semester_termine(self._termine, target.id) if target else 0
        self.copy_summary.setText(
            f"{selected_lvas} LVA ausgewählt · {selected_terms} Termine · Ziel enthält {target_terms} Termine"
        )
        self.copy_btn.setEnabled(bool(source and target and source.id != target.id and selected_terms > 0))

    def _refresh_clear_summary(self) -> None:
        semester = self._clear_semester()
        term_count = count_semester_termine(self._termine, semester.id) if semester else 0
        lva_count = self.clear_table.rowCount()
        self.clear_summary.setText(f"{lva_count} LVA · {term_count} Termine")
        self.clear_btn.setEnabled(term_count > 0)

    def _date_mode(self) -> str:
        return DATE_MODE_PLUS_YEAR if self.mode_year_rb.isChecked() else DATE_MODE_SEMESTER_WEEK

    def _accept_copy(self) -> None:
        source = self._source_semester()
        target = self._target_semester()
        lva_ids = self._selected_copy_lva_ids()
        term_count = self._selected_copy_term_count()
        if source is None or target is None:
            QMessageBox.warning(self, "Fehler", "Quelle oder Ziel fehlt.")
            return
        if source.id == target.id:
            QMessageBox.warning(self, "Fehler", "Quelle und Ziel müssen unterschiedlich sein.")
            return
        if not lva_ids or term_count <= 0:
            QMessageBox.warning(self, "Fehler", "Keine LVA ausgewählt.")
            return

        target_terms = count_semester_termine(self._termine, target.id)
        if target_terms > 0:
            answer = QMessageBox.question(
                self,
                "Zielsemester enthält Termine",
                f"{target.name} enthält bereits {target_terms} Termine. Trotzdem kopieren?",
            )
            if answer != QMessageBox.Yes:
                return

        self._result = SemesterToolRequest(
            action="copy",
            source=source,
            target=target,
            lva_ids=lva_ids,
            date_mode=self._date_mode(),
            copy_ausfall_daten=False,
        )
        self.accept()

    def _accept_clear(self) -> None:
        semester = self._clear_semester()
        if semester is None:
            QMessageBox.warning(self, "Fehler", "Semester fehlt.")
            return
        term_count = count_semester_termine(self._termine, semester.id)
        if term_count <= 0:
            QMessageBox.warning(self, "Keine Termine", "Dieses Semester enthält keine Termine.")
            return

        answer = QMessageBox.question(
            self,
            "Termine löschen",
            f"{term_count} Termine aus {semester.name} löschen?",
        )
        if answer != QMessageBox.Yes:
            return

        self._result = SemesterToolRequest(action="clear", semester=semester)
        self.accept()
