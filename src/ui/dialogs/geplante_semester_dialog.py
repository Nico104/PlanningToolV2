from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QMessageBox
)
from ...core.models import GeplantesSemester

class GeplanteSemesterDialog(QDialog):
    def __init__(self, parent: QWidget, geplantes_semester: Optional[GeplantesSemester] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Geplantes Semester bearbeiten" if geplantes_semester else "Geplantes Semester hinzufügen")
        self.setModal(True)
        self._result: Optional[GeplantesSemester] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.setMinimumWidth(400)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(form)

        self.name_le = QLineEdit(geplantes_semester.name if geplantes_semester else "")
        self.name_le.setObjectName("Field")
        self.notiz_le = QLineEdit(geplantes_semester.notiz if geplantes_semester and geplantes_semester.notiz else "")
        self.notiz_le.setObjectName("Field")
        self.id_le = QLineEdit(geplantes_semester.id if geplantes_semester else "")
        self.id_le.setObjectName("Field")

        form.addRow("Name:", self.name_le)
        form.addRow("Notiz:", self.notiz_le)
        form.addRow("ID:", self.id_le)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setObjectName("DialogButtons")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def get_result(self) -> Optional[GeplantesSemester]:
        if self.exec() == QDialog.Accepted:
            return GeplantesSemester(
                id=self.id_le.text().strip(),
                name=self.name_le.text().strip(),
                notiz=self.notiz_le.text().strip() or None
            )
        return None
