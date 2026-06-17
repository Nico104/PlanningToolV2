from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QMessageBox,
    QLabel, QFrame,
)


class StudienrichtungDialog(QDialog):
    """Dialog for creating or editing a Studienrichtung with id and name"""

    def __init__(self, parent: QWidget, studienrichtung: Optional[dict] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Studienrichtung bearbeiten" if studienrichtung else "Studienrichtung hinzufügen")
        self.setModal(True)
        self._result: Optional[dict] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(12)
        self.setMinimumWidth(460)

        title = QLabel("Studienrichtung", self)
        title.setObjectName("DialogTitle")
        lay.addWidget(title)
        subtitle = QLabel("ID und Bezeichnung einer Studienrichtung für LVAs erfassen.", self)
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.id_le = QLineEdit((studienrichtung or {}).get("id", ""))
        self.id_le.setObjectName("Field")
        self.name_le = QLineEdit((studienrichtung or {}).get("name", ""))
        self.name_le.setObjectName("Field")

        form.addRow("ID:", self.id_le)
        form.addRow("Name:", self.name_le)
        lay.addWidget(self._section("Studienrichtung", form))

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

    def _accept(self) -> None:
        fid = self.id_le.text().strip()
        name = self.name_le.text().strip()
        if not fid or not name:
            QMessageBox.warning(self, "Fehler", "ID und Name sind Pflicht.")
            return
        self._result = {"id": fid, "name": name}
        self.accept()

    @property
    def result(self) -> Optional[dict]:
        return self._result
