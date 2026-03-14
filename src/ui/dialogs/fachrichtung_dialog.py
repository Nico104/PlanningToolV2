from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QMessageBox
)


class FachrichtungDialog(QDialog):
    """Dialog for creating or editing a Fachrichtung with id and name"""

    def __init__(self, parent: QWidget, fachrichtung: Optional[dict] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Fachrichtung bearbeiten" if fachrichtung else "Fachrichtung hinzufügen")
        self.setModal(True)
        self._result: Optional[dict] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.setMinimumWidth(400)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(form)

        self.id_le = QLineEdit((fachrichtung or {}).get("id", ""))
        self.id_le.setObjectName("Field")
        self.name_le = QLineEdit((fachrichtung or {}).get("name", ""))
        self.name_le.setObjectName("Field")

        form.addRow("ID:", self.id_le)
        form.addRow("Name:", self.name_le)

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
