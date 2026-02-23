from datetime import date
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QMessageBox, QComboBox, QDateEdit
)
from ..components.widgets.tight_combobox import TightComboBox

from ..utils.datetime_utils import date_to_qdate, qdate_to_date


class FreieTageDialog(QDialog):
    def __init__(self, parent: QWidget, item: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Freier Tag bearbeiten" if item else "Freien Tag hinzufügen")
        self.setModal(True)
        self._result: Optional[Dict[str, Any]] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.setMinimumWidth(400)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(form)


        self.typ_cb = TightComboBox()
        self.typ_cb.addItems(["Feiertag", "Vorlesungsfrei"])
        self.typ_cb.setObjectName("TypCombo")

        self.art_cb = QComboBox()
        self.art_cb.setObjectName("HeaderCombo")
        self.art_cb.addItems(["single", "range"])

        self.datum_de = QDateEdit()
        self.datum_de.setCalendarPopup(True)
        self.datum_de.setObjectName("DateEdit")

        self.von_de = QDateEdit()
        self.von_de.setCalendarPopup(True)
        self.von_de.setObjectName("DateEdit")

        self.bis_de = QDateEdit()
        self.bis_de.setCalendarPopup(True)
        self.bis_de.setObjectName("DateEdit")

        self.beschr_le = QLineEdit()
        self.beschr_le.setObjectName("Field")

        today = date.today()
        self.datum_de.setDate(date_to_qdate(today))
        self.von_de.setDate(date_to_qdate(today))
        self.bis_de.setDate(date_to_qdate(today))


        # load existing
        if item:
            self.beschr_le.setText(str(item.get("beschreibung", "")))
            self.typ_cb.setCurrentText(str(item.get("typ", "Feiertag")))

            if "datum" in item and item.get("datum"):
                self.art_cb.setCurrentText("single")
                # datum
                try:
                    y, m, d = map(int, str(item.get("datum")).split("-"))
                    self.datum_de.setDate(date_to_qdate(date(y, m, d)))
                except Exception:
                    pass
            else:
                self.art_cb.setCurrentText("range")
                # von/bis
                for key, widget in [("von_datum", self.von_de), ("bis_datum", self.bis_de)]:
                    try:
                        y, m, d = map(int, str(item.get(key, "")).split("-"))
                        widget.setDate(date_to_qdate(date(y, m, d)))
                    except Exception:
                        pass


        form.addRow("Typ:", self.typ_cb)
        form.addRow("Art:", self.art_cb)
        form.addRow("Datum (single):", self.datum_de)
        form.addRow("Von (range):", self.von_de)
        form.addRow("Bis (range):", self.bis_de)
        form.addRow("Beschreibung:", self.beschr_le)

        self.art_cb.currentTextChanged.connect(self._update_visibility)
        self._update_visibility(self.art_cb.currentText())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _update_visibility(self, art: str) -> None:
        is_single = (art == "single")
        self.datum_de.setEnabled(is_single)
        self.von_de.setEnabled(not is_single)
        self.bis_de.setEnabled(not is_single)

    def _accept(self) -> None:
        beschr = self.beschr_le.text().strip()
        if not beschr:
            QMessageBox.warning(self, "Fehler", "Beschreibung ist Pflicht.")
            return


        typ = self.typ_cb.currentText().strip()
        art = self.art_cb.currentText().strip().lower()
        if art == "single":
            d = qdate_to_date(self.datum_de.date())
            self._result = {"datum": d.isoformat(), "beschreibung": beschr, "typ": typ}
        else:
            v = qdate_to_date(self.von_de.date())
            b = qdate_to_date(self.bis_de.date())
            if b < v:
                QMessageBox.warning(self, "Fehler", "Bis-Datum muss >= Von-Datum sein.")
                return
            self._result = {"von_datum": v.isoformat(), "bis_datum": b.isoformat(), "beschreibung": beschr, "typ": typ}

        self.accept()

    @property
    def result(self) -> Optional[Dict[str, Any]]:
        return self._result
