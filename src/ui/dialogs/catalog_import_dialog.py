from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...services.import_merge_service import (
    IMPORT_FILE_SCHEMAS,
    build_payload,
    classify_entry,
    existing_entry_map,
    get_entry_id,
    payload_list,
)
from ..components.widgets.tight_combobox import TightComboBox


class CatalogImportDialog(QDialog):
    import_requested = Signal(dict)

    _STATUS_LABELS = {
        "new": "Neu",
        "changed": "Geändert",
        "identical": "Vorhanden",
    }

    _FILE_LABELS = {
        "lehrveranstaltungen.json": "LVAs",
        "raeume.json": "Räume",
    }

    _IMPORT_LABELS = {
        "lehrveranstaltungen.json": ("LVA", "LVAs"),
        "raeume.json": ("Raum", "Räume"),
    }

    _COLUMNS = {
        "lehrveranstaltungen.json": [
            ("status", "Status"),
            ("id", "LVA-Nr."),
            ("name", "Name"),
            ("ects", "ECTS"),
            ("teacher", "Vortragende"),
            ("studiensemester", "Studiensemester"),
            ("studienrichtung", "Studienrichtung"),
        ],
        "raeume.json": [
            ("status", "Status"),
            ("id", "Raumnummer"),
            ("name", "Raum"),
            ("kapazitaet", "Kapazität"),
            ("gebaeude", "Gebäude"),
        ],
    }

    def __init__(
        self,
        parent: QWidget,
        data_dir: Path,
        payload: dict[str, Any],
        *,
        title: str,
        subtitle: str,
    ):
        super().__init__(parent)
        self.setObjectName("CatalogImportDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(1080, 680)
        self.setMinimumSize(860, 520)

        self._data_dir = Path(data_dir)
        self._rows_by_file: dict[str, list[dict[str, Any]]] = {}
        self._tables: dict[str, QTableWidget] = {}
        self._search_fields: dict[str, QLineEdit] = {}
        self._building_filters: dict[str, TightComboBox] = {}
        self._file_by_tab_index: dict[int, str] = {}
        self._source_entries_by_file: dict[str, list[dict[str, Any]]] = {}
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_label = QLabel(title, self)
        title_label.setObjectName("CatalogImportTitle")
        header.addWidget(title_label)
        header.addStretch(1)
        self.summary_label = QLabel(self)
        self.summary_label.setObjectName("CatalogImportSummary")
        self.summary_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self.summary_label)
        root.addLayout(header)

        subtitle_label = QLabel(subtitle, self)
        subtitle_label.setObjectName("CatalogImportSubtitle")
        subtitle_label.setWordWrap(True)
        root.addWidget(subtitle_label)

        self.tabs = QTabWidget(self)
        root.addWidget(self.tabs, 1)

        for file_name, content in payload.items():
            if file_name not in self._COLUMNS:
                continue
            schema = IMPORT_FILE_SCHEMAS.get(file_name)
            if schema is None:
                continue
            entries = payload_list(content, schema)
            rows = self._build_rows(file_name, entries)
            if rows:
                self._source_entries_by_file[file_name] = entries
                self._rows_by_file[file_name] = rows
                self._add_tab(file_name, rows)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)
        self.done_btn = QPushButton("Fertig", self)
        self.done_btn.setObjectName("SecondaryButton")
        self.done_btn.clicked.connect(self.accept)
        actions.addWidget(self.done_btn)

        self.import_btn = QPushButton("Auswahl importieren", self)
        self.import_btn.setObjectName("PrimaryButton")
        self.import_btn.clicked.connect(self._request_import)
        actions.addWidget(self.import_btn)
        root.addLayout(actions)

        self._build_busy_overlay()
        self.tabs.currentChanged.connect(lambda *_: self._refresh_summary())
        self._refresh_all_filters()
        self._refresh_summary()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_busy_overlay"):
            self._busy_overlay.setGeometry(self.rect())

    def closeEvent(self, event) -> None:
        if self._busy:
            event.ignore()
            return
        super().closeEvent(event)

    @property
    def selected_payload(self) -> dict[str, dict[str, list[dict[str, Any]]]]:
        selected: dict[str, list[dict[str, Any]]] = {}
        file_name = self._active_file_name()
        if not file_name:
            return {}
        table = self._tables[file_name]
        rows = self._rows_by_file[file_name]
        for row_index, row_data in enumerate(rows):
            item = table.item(row_index, 0)
            if item and item.checkState() == Qt.Checked and row_data["status"] != "identical":
                selected.setdefault(file_name, []).append(dict(row_data["import_entry"]))
        return build_payload(selected)

    def _active_file_name(self) -> str | None:
        return self._file_by_tab_index.get(self.tabs.currentIndex())

    def refresh_statuses(self) -> None:
        for file_name, entries in self._source_entries_by_file.items():
            rows = self._build_rows(file_name, entries)
            self._rows_by_file[file_name] = rows
            self._fill_table(file_name, self._tables[file_name], rows)
            self._apply_filter(file_name)
        self._refresh_summary()

    def _request_import(self) -> None:
        selected = self.selected_payload
        if selected:
            self.import_requested.emit(selected)

    def set_busy(self, busy: bool, text: str = "Bitte warten...") -> None:
        if self._busy == busy and self._busy_text.text() == text:
            return
        self._busy = busy
        self._busy_text.setText(text)
        self.tabs.setEnabled(not busy)
        self.done_btn.setEnabled(not busy)
        self.import_btn.setEnabled(False if busy else bool(self.selected_payload))
        self._busy_overlay.setVisible(busy)
        if busy:
            self._busy_overlay.raise_()
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()
            self._refresh_summary()
        QApplication.processEvents()

    def _build_rows(self, file_name: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        schema = IMPORT_FILE_SCHEMAS[file_name]
        existing = existing_entry_map(self._data_dir, file_name)
        rows: list[dict[str, Any]] = []
        for entry in entries:
            import_entry = self._import_entry(entry)
            entry_id = get_entry_id(import_entry, schema.id_field)
            if not entry_id:
                continue
            status = classify_entry(import_entry, existing, schema.id_field)
            cells = self._cell_values(file_name, entry, status)
            building = str(entry.get("__catalog_gebaeude", "") or "").strip()
            rows.append(
                {
                    "import_entry": import_entry,
                    "status": status,
                    "cells": cells,
                    "search": " ".join(str(value).casefold() for value in cells.values()),
                    "building": building,
                }
            )
        return rows

    @staticmethod
    def _import_entry(entry: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in entry.items() if not str(key).startswith("__catalog_")}

    def _add_tab(self, file_name: str, rows: list[dict[str, Any]]) -> None:
        tab = QWidget(self.tabs)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        search = QLineEdit(tab)
        search.setObjectName("HeaderSearch")
        search.setClearButtonEnabled(True)
        search.setPlaceholderText(
            "Raum, Nummer oder Gebäude suchen"
            if file_name == "raeume.json"
            else "LVA, Nummer oder Lehrperson suchen"
        )
        search.textChanged.connect(lambda *_: self._apply_filter(file_name))
        filters.addWidget(search, 3)
        self._search_fields[file_name] = search

        if file_name == "raeume.json":
            building_filter = TightComboBox(tab, min_popup_width=340)
            building_filter.setObjectName("HeaderCombo")
            building_filter.setMaxVisibleItems(14)
            building_filter.addItem("Alle Gebäude", "")
            for building in sorted({row["building"] for row in rows if row["building"]}):
                building_filter.addItem(building, building)
            building_filter.currentIndexChanged.connect(lambda *_: self._apply_filter(file_name))
            filters.addWidget(building_filter, 2)
            self._building_filters[file_name] = building_filter

        select_new_btn = QPushButton("Neue", tab)
        select_new_btn.setObjectName("SecondaryButton")
        select_new_btn.setToolTip("Neue sichtbare Einträge auswählen")
        select_new_btn.clicked.connect(lambda: self._set_visible_checks(file_name, "new"))
        filters.addWidget(select_new_btn)

        select_all_btn = QPushButton("Alle", tab)
        select_all_btn.setObjectName("SecondaryButton")
        select_all_btn.setToolTip("Alle sichtbaren Einträge auswählen")
        select_all_btn.clicked.connect(lambda: self._set_visible_checks(file_name, "all"))
        filters.addWidget(select_all_btn)

        clear_btn = QPushButton("Keine", tab)
        clear_btn.setObjectName("SecondaryButton")
        clear_btn.setToolTip("Sichtbare Einträge abwählen")
        clear_btn.clicked.connect(lambda: self._set_visible_checks(file_name, "none"))
        filters.addWidget(clear_btn)
        layout.addLayout(filters)

        columns = self._COLUMNS[file_name]
        table = QTableWidget(0, len(columns) + 1, tab)
        table.setObjectName("CatalogImportTable")
        table.setHorizontalHeaderLabels([""] + [label for _, label in columns])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setFocusPolicy(Qt.NoFocus)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(30)
        table.itemChanged.connect(self._refresh_summary)
        self._fill_table(file_name, table, rows)
        layout.addWidget(table, 1)
        self._tables[file_name] = table

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for idx in range(1, len(columns) + 1):
            header.setSectionResizeMode(idx, QHeaderView.ResizeToContents)
        stretch_column = 3 if file_name == "raeume.json" else 3
        header.setSectionResizeMode(stretch_column, QHeaderView.Stretch)

        index = self.tabs.addTab(tab, self._FILE_LABELS.get(file_name, file_name))
        self._file_by_tab_index[index] = file_name

    def _build_busy_overlay(self) -> None:
        self._busy_overlay = QFrame(self)
        self._busy_overlay.setObjectName("CatalogImportBusyOverlay")
        self._busy_overlay.setGeometry(self.rect())
        self._busy_overlay.hide()

        overlay_layout = QVBoxLayout(self._busy_overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.addStretch(1)

        panel = QFrame(self._busy_overlay)
        panel.setObjectName("CatalogImportBusyPanel")
        panel.setFixedWidth(300)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(10)

        self._busy_text = QLabel("Bitte warten...", panel)
        self._busy_text.setObjectName("CatalogImportBusyText")
        self._busy_text.setAlignment(Qt.AlignCenter)
        panel_layout.addWidget(self._busy_text)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(panel)
        row.addStretch(1)
        overlay_layout.addLayout(row)
        overlay_layout.addStretch(1)

    def _fill_table(self, file_name: str, table: QTableWidget, rows: list[dict[str, Any]]) -> None:
        columns = self._COLUMNS[file_name]
        table.blockSignals(True)
        table.setRowCount(len(rows))
        for row_index, row_data in enumerate(rows):
            check = QTableWidgetItem()
            if row_data["status"] == "identical":
                check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                check.setCheckState(Qt.Unchecked)
            else:
                check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
                check.setCheckState(Qt.Checked if row_data["status"] == "new" else Qt.Unchecked)
            table.setItem(row_index, 0, check)
            for col_index, (key, _label) in enumerate(columns, start=1):
                value = row_data["cells"].get(key, "")
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if key in {"status", "kapazitaet", "ects"}:
                    item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row_index, col_index, item)
        table.blockSignals(False)

    def _cell_values(self, file_name: str, entry: dict[str, Any], status: str) -> dict[str, str]:
        if file_name == "raeume.json":
            return {
                "status": self._STATUS_LABELS[status],
                "id": str(entry.get("id", "")),
                "name": str(entry.get("name", "")),
                "kapazitaet": str(entry.get("kapazitaet", "")),
                "gebaeude": str(entry.get("__catalog_gebaeude", "")),
            }

        teacher = entry.get("vortragende") if isinstance(entry.get("vortragende"), dict) else {}
        semester = entry.get("studiensemester")
        semester_text = (
            ", ".join(str(item) for item in semester)
            if isinstance(semester, list)
            else str(semester or "")
        )
        return {
            "status": self._STATUS_LABELS[status],
            "id": str(entry.get("id", "")),
            "name": str(entry.get("name", "")),
            "ects": str(entry.get("ects", "")),
            "teacher": str(teacher.get("name", "")),
            "studiensemester": semester_text,
            "studienrichtung": str(entry.get("studienrichtung", "")),
        }

    def _refresh_all_filters(self) -> None:
        for file_name in self._tables:
            self._apply_filter(file_name)

    def _apply_filter(self, file_name: str) -> None:
        table = self._tables[file_name]
        search = self._search_fields[file_name].text().strip().casefold()
        building = (
            self._building_filters.get(file_name).currentData()
            if file_name in self._building_filters
            else ""
        )

        for row_index, row_data in enumerate(self._rows_by_file[file_name]):
            visible = True
            if search and search not in row_data["search"]:
                visible = False
            if building and building != row_data["building"]:
                visible = False
            table.setRowHidden(row_index, not visible)
        self._refresh_summary()

    def _set_visible_checks(self, file_name: str, mode: str) -> None:
        table = self._tables[file_name]
        table.blockSignals(True)
        for row_index, row_data in enumerate(self._rows_by_file[file_name]):
            if table.isRowHidden(row_index):
                continue
            if row_data["status"] == "identical":
                continue
            item = table.item(row_index, 0)
            if item is None:
                continue
            checked = mode == "all" or (mode == "new" and row_data["status"] == "new")
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        table.blockSignals(False)
        self._refresh_summary()

    def _refresh_summary(self, *_args) -> None:
        file_name = self._active_file_name()
        if not file_name:
            self.summary_label.clear()
            self.import_btn.setEnabled(False)
            self.import_btn.setText("Importieren")
            return

        total = len(self._rows_by_file[file_name])
        selected = 0
        changed = 0
        new = 0
        table = self._tables[file_name]
        for row_index, row_data in enumerate(self._rows_by_file[file_name]):
            item = table.item(row_index, 0)
            if item and item.checkState() == Qt.Checked and row_data["status"] != "identical":
                selected += 1
                if row_data["status"] == "new":
                    new += 1
                elif row_data["status"] == "changed":
                    changed += 1
        label = self._FILE_LABELS.get(file_name, "Einträge")
        self.summary_label.setText(
            f"{label}: {selected} ausgewählt · {new} neu · {changed} geändert · {total} gesamt"
        )
        singular, plural = self._IMPORT_LABELS.get(file_name, ("Eintrag", "Einträge"))
        item_label = singular if selected == 1 else plural
        self.import_btn.setText(f"{selected} {item_label} importieren")
        self.import_btn.setEnabled(selected > 0 and not self._busy)
