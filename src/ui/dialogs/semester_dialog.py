from datetime import date
from typing import Optional

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QMessageBox, QDateEdit
)

from ...core.models import Semester
from ..utils.datetime_utils import date_to_qdate, qdate_to_date



class SemesterDialog(QDialog):
    def __init__(self, parent: QWidget, sem: Optional[Semester] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Semester bearbeiten" if sem else "Semester hinzufügen")
        self.setModal(True)
        self._result: Optional[Semester] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.setMinimumWidth(400)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(form)

        self.id_le = QLineEdit(sem.id if sem else "")
        self.id_le.setObjectName("Field")
        self.name_le = QLineEdit(sem.name if sem else "")
        self.name_le.setObjectName("Field")
        self.start_de = QDateEdit()
        self.start_de.setCalendarPopup(True)
        self.start_de.setObjectName("DateEdit")
        self.end_de = QDateEdit()
        self.end_de.setCalendarPopup(True)
        self.end_de.setObjectName("DateEdit")

        if sem:
            self.start_de.setDate(date_to_qdate(sem.start))
            self.end_de.setDate(date_to_qdate(sem.end))
        else:
            today = date.today()
            self.start_de.setDate(date_to_qdate(today))
            self.end_de.setDate(date_to_qdate(today))

        form.addRow("ID:", self.id_le)
        form.addRow("Name:", self.name_le)
        form.addRow("Start:", self.start_de)
        form.addRow("Ende:", self.end_de)

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
        sid = self.id_le.text().strip()
        name = self.name_le.text().strip()
        if not sid or not name:
            QMessageBox.warning(self, "Fehler", "ID und Name sind Pflicht.")
            return
        s = Semester(
            id=sid,
            name=name,
            start=qdate_to_date(self.start_de.date()),
            end=qdate_to_date(self.end_de.date()),
        )
        self._result = s
        self.accept()

    @property
    def result(self) -> Optional[Semester]:
        return self._result