from typing import Optional
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QMessageBox, QSpinBox
)

from ...core.models import Semester, Raum, Lehrveranstaltung, Vortragende, Termin, Zeitfenster, Gruppe


class RaumDialog(QDialog):
    def __init__(self, parent: QWidget, raum: Optional[Raum] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Raum bearbeiten" if raum else "Raum hinzufügen")
        self.setModal(True)
        self._result: Optional[Raum] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.setMinimumWidth(400)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(form)

        self.id_le = QLineEdit(raum.id if raum else "")
        self.id_le.setObjectName("Field")
        self.name_le = QLineEdit(raum.name if raum else "")
        self.name_le.setObjectName("Field")
        self.cap_sb = QSpinBox()
        self.cap_sb.setRange(1, 2000)
        self.cap_sb.setValue(raum.kapazitaet if raum else 30)
        self.cap_sb.setObjectName("Field")

        form.addRow("ID:", self.id_le)
        form.addRow("Name:", self.name_le)
        form.addRow("Kapazität:", self.cap_sb)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setObjectName("DialogButtons")
        ok_btn = bb.button(QDialogButtonBox.Ok)
        cancel_btn = bb.button(QDialogButtonBox.Cancel)
        if ok_btn:
            ok_btn.setObjectName("PrimaryButton")
        if cancel_btn:
            cancel_btn.setObjectName("SecondaryButton")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _accept(self):
        rid = self.id_le.text().strip()
        name = self.name_le.text().strip()
        if not rid or not name:
            QMessageBox.warning(self, "Fehler", "ID und Name sind Pflicht.")
            return
        self._result = Raum(id=rid, name=name, kapazitaet=int(self.cap_sb.value()))
        self.accept()

    @property
    def result(self) -> Optional[Raum]:
        return self._result