from datetime import datetime
from typing import Dict, Optional
from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QSpinBox, QTimeEdit, QPushButton
)

from ..components.widgets.tick_checkbox import TickCheckBox
from ..components.widgets.tight_combobox import TightComboBox


class SettingsDialog(QDialog):
    """Dialog for app settings"""
    def __init__(self, parent=None, settings: Optional[Dict] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.result_settings: Optional[Dict] = None
        self._syncing_times = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.setMinimumWidth(400)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(form)

        self.slot_cb = TightComboBox()
        self.slot_cb.setObjectName("Field")
        self.slot_cb.addItem("30 min", 30)
        self.slot_cb.addItem("60 min", 60)

        self.duration_step_sb = QSpinBox()
        self.duration_step_sb.setRange(1, 60)
        self.duration_step_sb.setSingleStep(5)
        self.duration_step_sb.setSuffix(" min")
        self.duration_step_sb.setObjectName("Field")

        self.day_start_te = QTimeEdit()
        self.day_start_te.setObjectName("Field")
        self.day_start_te.setDisplayFormat("HH:mm")
        self.day_end_te = QTimeEdit()
        self.day_end_te.setObjectName("Field")
        self.day_end_te.setDisplayFormat("HH:mm")

        self.data_path_le = QLineEdit()
        self.data_path_le.setObjectName("Field")
        self.show_termine_search_cb = TickCheckBox()
        self.show_termine_search_cb.setObjectName("Field")
        self.previous_year_shortcut_mode_cb = TightComboBox()
        self.previous_year_shortcut_mode_cb.setObjectName("Field")
        self.previous_year_shortcut_mode_cb.addItem("Gedrückt halten", "hold")
        self.previous_year_shortcut_mode_cb.addItem("Umschalten", "toggle")
        self.theme_cb = TightComboBox()
        self.theme_cb.setObjectName("Field")
        self.theme_cb.addItem("Hell", "light")
        self.theme_cb.addItem("Dunkel", "dark")
        form.addRow("Zeit-Raster:", self.slot_cb)
        form.addRow("Tag Start:", self.day_start_te)
        form.addRow("Tag Ende:", self.day_end_te)
        form.addRow("Dauer-Schritte (Minuten):", self.duration_step_sb)
        form.addRow("Datenpfad:", self.data_path_le)
        form.addRow("Termine-Suche anzeigen:", self.show_termine_search_cb)
        form.addRow("Vorjahr-Shortcut:", self.previous_year_shortcut_mode_cb)
        form.addRow("Design:", self.theme_cb)

        # Wochenende anzeigen
        self.show_weekend_cb = TickCheckBox()
        self.show_weekend_cb.setObjectName("Field")
        form.addRow("Wochenende im Kalender anzeigen:", self.show_weekend_cb)

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
        self.slot_cb.currentIndexChanged.connect(self._on_slot_changed)
        self.day_start_te.timeChanged.connect(lambda *_: self._enforce_hour_times())
        self.day_end_te.timeChanged.connect(lambda *_: self._enforce_hour_times())

        self.load(settings or {})

    def load(self, s: Dict) -> None:
        slot = self._nearest_slot_value(int(s.get("time_slot_minutes", 30)))
        idx = self.slot_cb.findData(slot)
        self.slot_cb.setCurrentIndex(idx if idx >= 0 else 0)
        self.duration_step_sb.setValue(int(s.get("duration_step_minutes", 15)))

        ds = datetime.strptime(s.get("day_start", "08:00"), "%H:%M").time()
        de = datetime.strptime(s.get("day_end", "18:00"), "%H:%M").time()
        self.day_start_te.setTime(QTime(ds.hour, ds.minute))
        self.day_end_te.setTime(QTime(de.hour, de.minute))
        self._sync_time_edit_constraints()
        self.data_path_le.setText(s.get("data_path", ""))
        self.show_termine_search_cb.setChecked(bool(s.get("show_termine_search", True)))
        mode = str(s.get("previous_year_shortcut_mode", "hold")).strip().lower()
        mode_idx = self.previous_year_shortcut_mode_cb.findData(mode)
        self.previous_year_shortcut_mode_cb.setCurrentIndex(mode_idx if mode_idx >= 0 else 0)
        theme = str(s.get("theme", "light")).strip().lower()
        theme_idx = self.theme_cb.findData(theme)
        self.theme_cb.setCurrentIndex(theme_idx if theme_idx >= 0 else 0)
        self.show_weekend_cb.setChecked(bool(s.get("show_weekend", False)))

    def _on_ok(self) -> None:
        self.result_settings = {
            "time_slot_minutes": int(self.slot_cb.currentData() or 30),
            "duration_step_minutes": int(self.duration_step_sb.value()),
            "day_start": self.day_start_te.time().toString("HH:mm"),
            "day_end": self.day_end_te.time().toString("HH:mm"),
            "data_path": self.data_path_le.text(),
            "show_termine_search": self.show_termine_search_cb.isChecked(),
            "previous_year_shortcut_mode": self.previous_year_shortcut_mode_cb.currentData() or "hold",
            "theme": self.theme_cb.currentData() or "light",
            "show_weekend": self.show_weekend_cb.isChecked(),
        }
        self.accept()

    def _on_slot_changed(self, *_args) -> None:
        self._sync_time_edit_constraints()

    def _sync_time_edit_constraints(self) -> None:
        is_hour_grid = int(self.slot_cb.currentData() or 30) == 60
        self.day_start_te.setToolTip("Nur volle Stunden möglich." if is_hour_grid else "")
        self.day_end_te.setToolTip("Nur volle Stunden möglich." if is_hour_grid else "")
        if is_hour_grid:
            self._round_day_bounds_to_hours()

    def _enforce_hour_times(self) -> None:
        if int(self.slot_cb.currentData() or 30) == 60:
            self._round_day_bounds_to_hours()

    def _round_day_bounds_to_hours(self) -> None:
        if self._syncing_times:
            return
        self._syncing_times = True
        try:
            self.day_start_te.setTime(self._round_time_to_hour(self.day_start_te.time(), round_up=False))
            self.day_end_te.setTime(self._round_time_to_hour(self.day_end_te.time(), round_up=True))
        finally:
            self._syncing_times = False

    def _round_time_to_hour(self, value: QTime, *, round_up: bool) -> QTime:
        hour = value.hour()
        minute = value.minute()
        if minute == 0:
            return QTime(hour, 0)
        if round_up:
            hour = min(23, hour + 1)
        return QTime(hour, 0)

    def _nearest_slot_value(self, value: int) -> int:
        return 60 if value >= 45 else 30
