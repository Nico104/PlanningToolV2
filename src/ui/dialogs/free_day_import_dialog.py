from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from ...services.free_day_import_service import (
    FreeDayCandidate,
    FreeDayPreviewItem,
    STATUS_EXISTS,
    STATUS_OVERLAP,
    fetch_open_holidays_public_holidays,
    fetch_tuwien_academic_free_days,
    prepare_free_day_preview,
)
from ..components.widgets.tight_combobox import TightComboBox
from ..utils.datetime_utils import date_to_qdate, qdate_to_date


class FreeDayImportDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        *,
        existing_items: list[dict],
        default_from: Optional[date] = None,
        default_to: Optional[date] = None,
    ):
        super().__init__(parent)
        self.setObjectName("FreeDayImportDialog")
        self.setModal(True)
        self.setWindowTitle("Freie Tage importieren")
        self.resize(980, 760)
        self.setMinimumSize(860, 680)

        today = date.today()
        self._existing_items = list(existing_items)
        self._api_candidates: list[FreeDayCandidate] = []
        self._tuwien_candidates: list[FreeDayCandidate] = []
        self._manual_candidates: list[FreeDayCandidate] = []
        self._preview: list[FreeDayPreviewItem] = []
        self._result_candidates: list[FreeDayCandidate] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        title = QLabel("Freie Tage importieren", self)
        title.setObjectName("FreeDayImportTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Feiertage und vorlesungsfreie Zeiträume aus öffentlichen Quellen laden oder manuell ergänzen.",
            self,
        )
        subtitle.setObjectName("FreeDayImportSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        controls = QHBoxLayout()
        controls.setSpacing(16)
        controls.setAlignment(Qt.AlignTop)
        api_panel = self._build_api_panel(
            default_from or date(today.year, 1, 1), default_to or date(today.year, 12, 31)
        )
        manual_panel = self._build_manual_panel()
        controls.addWidget(api_panel, 1, Qt.AlignTop)
        controls.addWidget(manual_panel, 1, Qt.AlignTop)
        root.addLayout(controls)

        self.table = QTableWidget(0, 7, self)
        self.table.setObjectName("FreeDayImportTable")
        self.table.setHorizontalHeaderLabels(
            ["", "Typ", "Beschreibung", "Von", "Bis", "Quelle", "Status"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._refresh_summary)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 38)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 260)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 130)
        self.table.setColumnWidth(6, 130)

        preview_panel = QFrame(self)
        preview_panel.setObjectName("FreeDayImportPreviewPanel")
        preview_panel.setMinimumHeight(280)
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(14, 12, 14, 14)
        preview_layout.setSpacing(10)

        preview_header = QHBoxLayout()
        preview_title = QLabel("Vorschau", preview_panel)
        preview_title.setObjectName("FreeDayImportPanelTitle")
        preview_header.addWidget(preview_title)
        preview_header.addStretch(1)
        self.summary_label = QLabel(preview_panel)
        self.summary_label.setObjectName("FreeDayImportSummary")
        self.summary_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        preview_header.addWidget(self.summary_label)
        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self.table, 1)
        root.addWidget(preview_panel, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_btn = QPushButton("Schließen", self)
        self.cancel_btn.setObjectName("SecondaryButton")
        self.cancel_btn.clicked.connect(self.reject)
        actions.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Ausgewählte importieren", self)
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.clicked.connect(self._accept_selection)
        actions.addWidget(self.save_btn)
        root.addLayout(actions)

        self._refresh_preview()

    @property
    def selected_candidates(self) -> list[FreeDayCandidate]:
        return list(self._result_candidates)

    def _build_api_panel(self, default_from: date, default_to: date) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("FreeDayImportPanel")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        label = QLabel("Automatisch laden", panel)
        label.setObjectName("FreeDayImportPanelTitle")
        layout.addWidget(label)
        help_label = QLabel(
            "Gesetzliche Feiertage werden über OpenHolidays geladen. TU-Wien-Zeiträume werden von der TU-Wien-Website übernommen; es werden nur dort bereits eingetragene Zeiträume gefunden.",
            panel,
        )
        help_label.setObjectName("FreeDayImportHelp")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.from_de = self._new_date_edit(default_from)
        self.to_de = self._new_date_edit(default_to)
        form.addRow("Von:", self.from_de)
        form.addRow("Bis:", self.to_de)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch(1)
        self.load_btn = QPushButton("Feiertage und TU-Wien-Zeiträume laden", panel)
        self.load_btn.setObjectName("SecondaryButton")
        self.load_btn.clicked.connect(self._load_automatic_sources)
        row.addWidget(self.load_btn)
        layout.addLayout(row)
        return panel

    def _build_manual_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("FreeDayImportPanel")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        label = QLabel("Manuell ergänzen", panel)
        label.setObjectName("FreeDayImportPanelTitle")
        layout.addWidget(label)
        help_label = QLabel(
            "Eigene vorlesungsfreie Zeiträume oder Feiertage in die Vorschau aufnehmen.", panel
        )
        help_label.setObjectName("FreeDayImportHelp")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.manual_type_cb = TightComboBox(panel)
        self.manual_type_cb.setObjectName("Field")
        self.manual_type_cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.manual_type_cb.addItems(["Vorlesungsfrei", "Feiertag"])
        self.manual_name_le = QLineEdit(panel)
        self.manual_name_le.setObjectName("Field")
        self.manual_name_le.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.manual_name_le.setPlaceholderText("z.B. Weihnachtsferien")
        today = date.today()
        self.manual_from_de = self._new_date_edit(today)
        self.manual_to_de = self._new_date_edit(today)

        form.addRow("Typ:", self.manual_type_cb)
        form.addRow("Name:", self.manual_name_le)
        form.addRow("Von:", self.manual_from_de)
        form.addRow("Bis:", self.manual_to_de)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch(1)
        self.add_manual_btn = QPushButton("Zur Vorschau hinzufügen", panel)
        self.add_manual_btn.setObjectName("SecondaryButton")
        self.add_manual_btn.clicked.connect(self._add_manual_candidate)
        row.addWidget(self.add_manual_btn)
        layout.addLayout(row)
        return panel

    def _new_date_edit(self, value: date) -> QDateEdit:
        edit = QDateEdit(self)
        edit.setObjectName("DateEdit")
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd.MM.yyyy")
        edit.setDate(date_to_qdate(value))
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return edit

    def _load_automatic_sources(self) -> None:
        valid_from = qdate_to_date(self.from_de.date())
        valid_to = qdate_to_date(self.to_de.date())
        errors: list[str] = []

        try:
            self.load_btn.setEnabled(False)
            self.load_btn.setText("Lade...")
            try:
                self._api_candidates = fetch_open_holidays_public_holidays(
                    valid_from=valid_from, valid_to=valid_to
                )
            except Exception as exc:
                self._api_candidates = []
                errors.append(f"OpenHolidays: {exc}")

            try:
                tuwien_candidates = fetch_tuwien_academic_free_days()
                self._tuwien_candidates = [
                    candidate
                    for candidate in tuwien_candidates
                    if candidate.start <= valid_to and valid_from <= candidate.end
                ]
            except Exception as exc:
                self._tuwien_candidates = []
                errors.append(f"TU Wien: {exc}")
        finally:
            self.load_btn.setEnabled(True)
            self.load_btn.setText("Feiertage und TU-Wien-Zeiträume laden")

        self._refresh_preview()
        if errors and not self._api_candidates and not self._tuwien_candidates:
            QMessageBox.warning(self, "Freie Tage laden", "\n\n".join(errors))
            return
        if errors:
            QMessageBox.warning(self, "Teilweise geladen", "\n\n".join(errors))
        if not self._api_candidates and not self._tuwien_candidates:
            QMessageBox.information(
                self,
                "Keine freien Tage",
                "Für diesen Zeitraum wurden keine gesetzlichen Feiertage oder TU-Wien-Ferien erkannt.",
            )

    def _add_manual_candidate(self) -> None:
        name = self.manual_name_le.text().strip()
        if not name:
            QMessageBox.warning(self, "Fehler", "Name ist Pflicht.")
            return

        start = qdate_to_date(self.manual_from_de.date())
        end = qdate_to_date(self.manual_to_de.date())
        if end < start:
            QMessageBox.warning(self, "Fehler", "Bis-Datum muss nach dem Von-Datum liegen.")
            return

        self._manual_candidates.append(
            FreeDayCandidate(
                typ=self.manual_type_cb.currentText().strip(),
                beschreibung=name,
                start=start,
                end=end,
                quelle="manuell:akademisch",
            )
        )
        self.manual_name_le.clear()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        candidates = sorted(
            [*self._api_candidates, *self._tuwien_candidates, *self._manual_candidates],
            key=lambda candidate: (
                candidate.start,
                candidate.end,
                candidate.typ,
                self._source_priority(candidate.quelle),
                candidate.beschreibung.lower(),
            ),
        )
        self._preview = prepare_free_day_preview(candidates, self._existing_items)

        self.table.blockSignals(True)
        self.table.setRowCount(len(self._preview))
        for row, item in enumerate(self._preview):
            self._set_checkbox_item(row, item)
            candidate = item.candidate
            self._set_text_item(row, 1, candidate.typ)
            self._set_text_item(row, 2, candidate.beschreibung)
            self._set_text_item(row, 3, candidate.start.strftime("%d.%m.%Y"), Qt.AlignCenter)
            self._set_text_item(row, 4, candidate.end.strftime("%d.%m.%Y"), Qt.AlignCenter)
            self._set_text_item(row, 5, self._source_label(candidate.quelle))
            self._set_text_item(row, 6, item.status)
        self.table.blockSignals(False)
        self._refresh_summary()

    def _set_checkbox_item(self, row: int, preview_item: FreeDayPreviewItem) -> None:
        checkbox = QTableWidgetItem()
        if preview_item.status == STATUS_EXISTS:
            checkbox.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        else:
            checkbox.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            checkbox.setCheckState(Qt.Checked if preview_item.checked else Qt.Unchecked)
        checkbox.setData(Qt.UserRole, row)
        self.table.setItem(row, 0, checkbox)

    def _set_text_item(
        self, row: int, column: int, text: str, alignment=Qt.AlignVCenter | Qt.AlignLeft
    ) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setTextAlignment(alignment)
        self.table.setItem(row, column, item)

    def _refresh_summary(self, *_args) -> None:
        total = len(self._preview)
        checked = len(self._checked_candidates())
        existing = sum(1 for item in self._preview if item.status == STATUS_EXISTS)
        overlaps = sum(1 for item in self._preview if item.status == STATUS_OVERLAP)
        self.summary_label.setText(
            f"{checked} ausgewählt · {total} Vorschläge · {existing} schon vorhanden · {overlaps} überlappt"
        )
        self.save_btn.setEnabled(checked > 0)

    def _checked_candidates(self) -> list[FreeDayCandidate]:
        selected: list[FreeDayCandidate] = []
        for row, preview_item in enumerate(self._preview):
            if preview_item.status == STATUS_EXISTS:
                continue
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                selected.append(preview_item.candidate)
        return selected

    def _accept_selection(self) -> None:
        selected = self._checked_candidates()
        if not selected:
            QMessageBox.warning(
                self, "Keine Auswahl", "Es sind keine neuen freien Tage ausgewählt."
            )
            return
        self._result_candidates = selected
        self.accept()

    def _source_label(self, quelle: str) -> str:
        if quelle.startswith("auto:openholidays"):
            return "OpenHolidays"
        if quelle.startswith("auto:tuwien"):
            return "TU Wien"
        if quelle.startswith("manuell"):
            return "Manuell"
        return quelle

    def _source_priority(self, quelle: str) -> int:
        if quelle.startswith("auto:openholidays"):
            return 0
        if quelle.startswith("auto:tuwien"):
            return 1
        if quelle.startswith("manuell"):
            return 3
        return 2
