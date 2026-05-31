from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QMessageBox
)
from ...core.models import Studiensemester

class StudiensemesterDialog(QDialog):
    """Form dialog for creating or editing a Studiensemester with name, optional note and ID fields."""

    def __init__(self, parent: QWidget, studiensemester: Optional[Studiensemester] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Studiensemester bearbeiten" if studiensemester else "Studiensemester hinzufügen")
        self.setModal(True)
        self._result: Optional[Studiensemester] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.setMinimumWidth(400)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(form)

        self.name_le = QLineEdit(studiensemester.name if studiensemester else "")
        self.name_le.setObjectName("Field")
        self.notiz_le = QLineEdit(studiensemester.notiz if studiensemester and studiensemester.notiz else "")
        self.notiz_le.setObjectName("Field")
        self.id_le = QLineEdit(studiensemester.id if studiensemester else "")
        self.id_le.setObjectName("Field")

        form.addRow("Name:", self.name_le)
        form.addRow("Notiz:", self.notiz_le)
        form.addRow("ID:", self.id_le)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setObjectName("DialogButtons")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def get_result(self) -> Optional[Studiensemester]:
        if self.exec() == QDialog.Accepted:
            return Studiensemester(
                id=self.id_le.text().strip(),
                name=self.name_le.text().strip(),
                notiz=self.notiz_le.text().strip() or None
            )
        return None
