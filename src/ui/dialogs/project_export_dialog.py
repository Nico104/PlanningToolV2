from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from ..components.widgets.tight_combobox import TightComboBox


@dataclass(frozen=True)
class ExportFileOption:
    file_name: str
    label: str
    description: str = ""


class ProjectExportDialog(QDialog):
    def __init__(self, parent, options: list[ExportFileOption]):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Exportieren")
        self.setModal(True)
        self.setMinimumWidth(620)
        self._options = list(options)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        title = QLabel("Exportieren", self)
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Wählen Sie, welche Projektdaten als importierbare JSON-Datei exportiert werden sollen.",
            self,
        )
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        mode_section = QFrame(self)
        mode_section.setObjectName("DialogSection")
        mode_layout = QVBoxLayout(mode_section)
        mode_layout.setContentsMargins(14, 12, 14, 14)
        mode_layout.setSpacing(8)

        mode_title = QLabel("Umfang", mode_section)
        mode_title.setObjectName("DialogSectionTitle")
        mode_layout.addWidget(mode_title)

        self.mode_group = QButtonGroup(self)
        self.all_rb = QRadioButton("Ganzes Projekt", mode_section)
        self.all_rb.setToolTip("Alle Projektdateien in einem JSON-Bundle exportieren.")
        self.selected_rb = QRadioButton("Einzelne Datei", mode_section)
        self.selected_rb.setToolTip("Genau eine Projektdatei exportieren, z.B. freie Tage.")
        self.mode_group.addButton(self.all_rb)
        self.mode_group.addButton(self.selected_rb)
        self.all_rb.setChecked(True)
        mode_layout.addWidget(self.all_rb)
        mode_layout.addWidget(self.selected_rb)
        root.addWidget(mode_section)

        format_section = QFrame(self)
        format_section.setObjectName("DialogSection")
        format_layout = QVBoxLayout(format_section)
        format_layout.setContentsMargins(14, 12, 14, 14)
        format_layout.setSpacing(8)

        format_title = QLabel("Format", format_section)
        format_title.setObjectName("DialogSectionTitle")
        format_layout.addWidget(format_title)

        self.format_cb = TightComboBox(format_section)
        self.format_cb.setObjectName("Field")
        self.format_cb.currentIndexChanged.connect(self._refresh_state)
        format_layout.addWidget(self.format_cb)
        root.addWidget(format_section)

        files_section = QFrame(self)
        files_section.setObjectName("DialogSection")
        files_layout = QVBoxLayout(files_section)
        files_layout.setContentsMargins(14, 12, 14, 14)
        files_layout.setSpacing(8)

        files_title = QLabel("Datei", files_section)
        files_title.setObjectName("DialogSectionTitle")
        files_layout.addWidget(files_title)

        self.file_cb = TightComboBox(files_section)
        self.file_cb.setObjectName("Field")
        for option in self._options:
            self.file_cb.addItem(option.label, option.file_name)
        self.file_cb.currentIndexChanged.connect(self._refresh_state)
        files_layout.addWidget(self.file_cb)

        self.file_help = QLabel(files_section)
        self.file_help.setObjectName("SettingsHelp")
        self.file_help.setWordWrap(True)
        files_layout.addWidget(self.file_help)

        root.addWidget(files_section)

        hint = QLabel(
            "Das ganze Projekt wird als Bundle exportiert. Eine einzelne Datei wird direkt als normale JSON-Datei exportiert und kann später über Importieren wieder eingelesen werden.",
            self,
        )
        hint.setObjectName("DialogSubtitle")
        hint.setWordWrap(True)
        root.addWidget(hint)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton("Abbrechen", self)
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(cancel_btn)

        self.export_btn = QPushButton("Exportieren", self)
        self.export_btn.setObjectName("PrimaryButton")
        self.export_btn.clicked.connect(self.accept)
        actions.addWidget(self.export_btn)
        root.addLayout(actions)

        self.all_rb.toggled.connect(self._refresh_state)
        self.selected_rb.toggled.connect(self._refresh_state)
        self._refresh_state()

    def selected_files(self) -> list[str]:
        if self.all_rb.isChecked():
            return [option.file_name for option in self._options]
        file_name = self.file_cb.currentData()
        return [str(file_name)] if file_name else []

    def selected_format(self) -> str:
        return str(self.format_cb.currentData() or "json")

    def _refresh_state(self) -> None:
        selected_mode = self.selected_rb.isChecked()
        current_format = self.selected_format()
        self.format_cb.blockSignals(True)
        self.format_cb.clear()
        self.format_cb.addItem("JSON", "json")
        self.format_cb.addItem("Excel", "xlsx")
        if selected_mode:
            self.format_cb.addItem("CSV", "csv")
        index = self.format_cb.findData(current_format)
        self.format_cb.setCurrentIndex(index if index >= 0 else 0)
        self.format_cb.blockSignals(False)

        self.file_cb.setEnabled(selected_mode)
        selected_file = str(self.file_cb.currentData() or "")
        option = next((item for item in self._options if item.file_name == selected_file), None)
        self.file_help.setText(option.description if selected_mode and option else "")
        self.export_btn.setEnabled(bool(self.selected_files()))
