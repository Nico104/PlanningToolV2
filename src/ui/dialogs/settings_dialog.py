from datetime import datetime
from typing import Dict, Optional
from PySide6.QtCore import Qt

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QSpinBox, QTimeEdit, QPushButton
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings: Optional[Dict] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.result_settings: Optional[Dict] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.setMinimumWidth(400)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(form)

        self.slot_sb = QSpinBox()
        self.slot_sb.setRange(5, 120)
        self.slot_sb.setSingleStep(5)
        self.slot_sb.setObjectName("Field")

        self.duration_step_sb = QSpinBox()
        self.duration_step_sb.setRange(1, 60)
        self.duration_step_sb.setSingleStep(5)
        self.duration_step_sb.setSuffix(" min")
        self.duration_step_sb.setObjectName("Field")

        self.day_start_te = QTimeEdit()
        self.day_start_te.setObjectName("Field")
        self.day_end_te = QTimeEdit()
        self.day_end_te.setObjectName("Field")

        from PySide6.QtWidgets import QLineEdit
        self.data_path_le = QLineEdit()
        self.data_path_le.setObjectName("Field")
        form.addRow("Zeit-Raster (Minuten):", self.slot_sb)
        form.addRow("Dauer-Schritte (Minuten):", self.duration_step_sb)
        form.addRow("Tag Start:", self.day_start_te)
        form.addRow("Tag Ende:", self.day_end_te)
        form.addRow("Datenpfad:", self.data_path_le)

        btns = QHBoxLayout()
        lay.addLayout(btns)
        btns.addStretch(1)

        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.setObjectName("SecondaryButton")
        self.ok_btn = QPushButton("Speichern")
        self.ok_btn.setObjectName("PrimaryButton")
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.ok_btn)

        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn.clicked.connect(self._on_ok)

        self.load(settings or {})

    def load(self, s: Dict) -> None:
        self.slot_sb.setValue(int(s.get("time_slot_minutes", 30)))
        self.duration_step_sb.setValue(int(s.get("duration_step_minutes", 15)))

        ds = datetime.strptime(s.get("day_start", "08:00"), "%H:%M").time()
        de = datetime.strptime(s.get("day_end", "18:00"), "%H:%M").time()
        self.day_start_te.setTime(QTime(ds.hour, ds.minute))
        self.day_end_te.setTime(QTime(de.hour, de.minute))
        self.data_path_le.setText(s.get("data_path", ""))

    def _on_ok(self) -> None:
        self.result_settings = {
            "time_slot_minutes": int(self.slot_sb.value()),
            "duration_step_minutes": int(self.duration_step_sb.value()),
            "day_start": self.day_start_te.time().toString("HH:mm"),
            "day_end": self.day_end_te.time().toString("HH:mm"),
            "data_path": self.data_path_le.text(),
        }
        self.accept()
