from datetime import date
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..components.widgets.tight_combobox import TightComboBox
from ..utils.datetime_utils import date_to_qdate, qdate_to_date


class FreieTageDialog(QDialog):
    def __init__(self, parent: QWidget, item: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Freien Zeitraum bearbeiten" if item else "Freien Zeitraum hinzufügen")
        self.setModal(True)
        self._result: Optional[Dict[str, Any]] = None
        self.resize(480, 360)
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        title = QLabel("Freier Zeitraum", self)
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        subtitle = QLabel("Ein einzelner freier Tag wird mit gleichem Von- und Bis-Datum erfasst.", self)
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.typ_cb = TightComboBox(self)
        self.typ_cb.setObjectName("HeaderCombo")
        self.typ_cb.addItems(["Feiertag", "Vorlesungsfrei"])

        self.von_de = self._new_date_edit()
        self.bis_de = self._new_date_edit()

        self.beschr_le = QLineEdit(self)
        self.beschr_le.setObjectName("Field")
        self.beschr_le.setPlaceholderText("z. B. Weihnachtsferien")

        form.addRow("Typ:", self.typ_cb)
        form.addRow("Von:", self.von_de)
        form.addRow("Bis:", self.bis_de)
        form.addRow("Beschreibung:", self.beschr_le)
        root.addWidget(self._section("Zeitraum", form))

        if item:
            self._load_item(item)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.setObjectName("DialogButtons")
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        cancel_btn = buttons.button(QDialogButtonBox.Cancel)
        if ok_btn:
            ok_btn.setText("Speichern")
            ok_btn.setObjectName("PrimaryButton")
        if cancel_btn:
            cancel_btn.setText("Abbrechen")
            cancel_btn.setObjectName("SecondaryButton")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _new_date_edit(self) -> QDateEdit:
        edit = QDateEdit(self)
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd.MM.yyyy")
        edit.setDate(date_to_qdate(date.today()))
        edit.setObjectName("DateEdit")
        return edit

    def _section(self, title: str, content_layout: QFormLayout) -> QFrame:
        section = QFrame(self)
        section.setObjectName("DialogSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        label = QLabel(title, section)
        label.setObjectName("DialogSectionTitle")
        layout.addWidget(label)
        layout.addLayout(content_layout)
        return section

    def _load_item(self, item: Dict[str, Any]) -> None:
        self.beschr_le.setText(str(item.get("beschreibung", "")))
        self.typ_cb.setCurrentText(str(item.get("typ", "Feiertag")))

        start_raw = str(item.get("von_datum") or "").strip()
        end_raw = str(item.get("bis_datum") or "").strip()
        for raw, widget in [(start_raw, self.von_de), (end_raw, self.bis_de)]:
            try:
                y, m, d = map(int, raw.split("-"))
                widget.setDate(date_to_qdate(date(y, m, d)))
            except Exception:
                pass

    def _accept(self) -> None:
        beschreibung = self.beschr_le.text().strip()
        if not beschreibung:
            QMessageBox.warning(self, "Fehler", "Beschreibung ist Pflicht.")
            return

        start = qdate_to_date(self.von_de.date())
        end = qdate_to_date(self.bis_de.date())
        if end < start:
            QMessageBox.warning(self, "Fehler", "Bis-Datum muss nach dem Von-Datum liegen.")
            return

        self._result = {
            "von_datum": start.isoformat(),
            "bis_datum": end.isoformat(),
            "beschreibung": beschreibung,
            "typ": self.typ_cb.currentText().strip(),
        }
        self.accept()

    @property
    def result(self) -> Optional[Dict[str, Any]]:
        return self._result
