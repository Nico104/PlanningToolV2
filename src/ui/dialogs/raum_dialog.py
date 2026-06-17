from typing import Optional
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QMessageBox, QSpinBox,
    QLabel, QFrame,
)

from ...core.models import Raum


class RaumDialog(QDialog):
    """Dialog for creating or editing a room with name and capacity"""
    def __init__(self, parent: QWidget, raum: Optional[Raum] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Raum bearbeiten" if raum else "Raum hinzufügen")
        self.setModal(True)
        self._result: Optional[Raum] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(12)
        self.setMinimumWidth(460)

        title = QLabel("Raum", self)
        title.setObjectName("DialogTitle")
        lay.addWidget(title)
        subtitle = QLabel("Raumnummer, Bezeichnung, Kapazität und Gebäude für die Planung erfassen.", self)
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.id_le = QLineEdit(raum.id if raum else "")
        self.id_le.setObjectName("Field")
        self.name_le = QLineEdit(raum.name if raum else "")
        self.name_le.setObjectName("Field")
        self.cap_sb = QSpinBox()
        self.cap_sb.setRange(1, 2000)
        self.cap_sb.setValue(raum.kapazitaet if raum else 30)
        self.cap_sb.setObjectName("Field")
        self.building_le = QLineEdit(getattr(raum, "gebaeude", "") if raum else "")
        self.building_le.setObjectName("Field")

        form.addRow("Raumnummer:", self.id_le)
        form.addRow("Raum:", self.name_le)
        form.addRow("Kapazität:", self.cap_sb)
        form.addRow("Gebäude:", self.building_le)
        lay.addWidget(self._section("Raumdaten", form))

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setObjectName("DialogButtons")
        ok_btn = bb.button(QDialogButtonBox.Ok)
        cancel_btn = bb.button(QDialogButtonBox.Cancel)
        if ok_btn:
            ok_btn.setText("Speichern")
            ok_btn.setObjectName("PrimaryButton")
        if cancel_btn:
            cancel_btn.setText("Abbrechen")
            cancel_btn.setObjectName("SecondaryButton")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

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

    def _accept(self):
        rid = self.id_le.text().strip()
        name = self.name_le.text().strip()
        if not rid or not name:
            QMessageBox.warning(self, "Fehler", "Raumnummer und Raum sind Pflicht.")
            return
        self._result = Raum(
            id=rid,
            name=name,
            kapazitaet=int(self.cap_sb.value()),
            gebaeude=self.building_le.text().strip(),
        )
        self.accept()

    @property
    def result(self) -> Optional[Raum]:
        return self._result
