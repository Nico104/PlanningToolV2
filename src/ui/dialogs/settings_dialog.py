from datetime import datetime
from typing import Dict, Optional
from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QSpinBox, QTimeEdit, QPushButton, QLabel, QFrame, QWidget,
    QTabWidget, QScrollArea, QApplication
)

from ...services.conflict_service import load_conflicts, save_conflicts
from ..components.widgets.tick_checkbox import TickCheckBox
from ..components.widgets.tight_combobox import TightComboBox


class SettingsDialog(QDialog):
    """Dialog for app settings"""
    def __init__(self, parent=None, settings: Optional[Dict] = None, initial_tab: str = "general"):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Einstellungen")
        self.setModal(True)
        self.result_settings: Optional[Dict] = None
        self.conflicts = load_conflicts()
        self._conflict_controls = []
        self._syncing_times = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)
        self.setMinimumWidth(760)

        title = QLabel("Einstellungen")
        title.setObjectName("SettingsTitle")
        subtitle = QLabel("Kalender, Filterverhalten, App-Ansicht und Konfliktprüfungen konfigurieren. Änderungen am Datenpfad oder Design werden nach einem Neustart vollständig aktiv.")
        subtitle.setObjectName("SettingsSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("SettingsTabs")
        root.addWidget(self.tabs, 1)

        general_page = self._scrollable_page()
        general_content = general_page.widget()
        lay = QVBoxLayout(general_content)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(14)
        self.tabs.addTab(general_page, "Allgemein")

        self.slot_cb = TightComboBox()
        self.slot_cb.setObjectName("Field")
        self.slot_cb.addItem("30 min", 30)
        self.slot_cb.addItem("60 min", 60)

        self.duration_step_sb = QSpinBox()
        self.duration_step_sb.setRange(1, 60)
        self.duration_step_sb.setSingleStep(5)
        self.duration_step_sb.setSuffix(" min")
        self.duration_step_sb.setObjectName("Field")

        self.day_room_page_size_sb = QSpinBox()
        self.day_room_page_size_sb.setRange(4, 24)
        self.day_room_page_size_sb.setSingleStep(1)
        self.day_room_page_size_sb.setObjectName("Field")

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
        self.jump_to_semester_start_cb = TickCheckBox()
        self.jump_to_semester_start_cb.setObjectName("Field")
        self.previous_year_shortcut_mode_cb = TightComboBox()
        self.previous_year_shortcut_mode_cb.setObjectName("Field")
        self.previous_year_shortcut_mode_cb.addItem("Gedrückt halten", "hold")
        self.previous_year_shortcut_mode_cb.addItem("Umschalten", "toggle")
        self.theme_cb = TightComboBox()
        self.theme_cb.setObjectName("Field")
        self.theme_cb.addItem("Hell", "light")
        self.theme_cb.addItem("Dunkel", "dark")

        self.show_weekend_cb = TickCheckBox()
        self.show_weekend_cb.setObjectName("Field")

        content = QHBoxLayout()
        content.setSpacing(12)
        lay.addLayout(content)
        left_col = QVBoxLayout()
        left_col.setSpacing(12)
        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        content.addLayout(left_col, 1)
        content.addLayout(right_col, 1)

        calendar_section, calendar_grid = self._section("Kalender")
        left_col.addWidget(calendar_section)
        self._add_field(calendar_grid, 0, "Zeit-Raster", self.slot_cb, "Abstand der Zeilen in Tages- und Wochenansicht.")
        self._add_field(calendar_grid, 1, "Tag beginnt", self.day_start_te)
        self._add_field(calendar_grid, 2, "Tag endet", self.day_end_te)
        self._add_field(calendar_grid, 3, "Dauer-Schritte", self.duration_step_sb, "Schrittweite beim Einstellen der Termindauer.")
        self._add_field(calendar_grid, 4, "Wochenende anzeigen", self.show_weekend_cb, "Samstag und Sonntag in Wochen- und Monatsansicht einblenden.")

        view_section, view_grid = self._section("Planungsansicht")
        left_col.addWidget(view_section)
        self._add_field(view_grid, 0, "Räume pro Tagesseite", self.day_room_page_size_sb, "Wie viele Raumspalten gleichzeitig in der Tagesansicht sichtbar sind.")
        self._add_field(view_grid, 1, "Termine-Suche", self.show_termine_search_cb, "Suchfeld im Termine-Dock anzeigen.")
        self._add_field(view_grid, 2, "Semesterfilter springt", self.jump_to_semester_start_cb, "Beim Auswählen eines Semesters zur ersten passenden Woche springen.")
        left_col.addStretch(1)

        app_section, app_grid = self._section("Projekt und App")
        right_col.addWidget(app_section)
        self._add_field(app_grid, 0, "Datenpfad", self.data_path_le, "Ordner, in dem die Projektdaten gespeichert werden.")
        self._add_field(app_grid, 1, "Vorjahr-Shortcut", self.previous_year_shortcut_mode_cb, "Legt fest, ob Strg+Alt+V gehalten oder umgeschaltet wird.")
        self._add_field(app_grid, 2, "Design", self.theme_cb)
        right_col.addStretch(1)

        conflicts_page = self._build_conflicts_page()
        self.tabs.addTab(conflicts_page, "Konflikte")
        if initial_tab == "conflicts":
            self.tabs.setCurrentWidget(conflicts_page)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        root.addLayout(btns)
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
        self._fit_to_screen()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        max_height = max(520, available.height() - 80)
        max_width = max(720, available.width() - 80)
        self.setMaximumSize(max_width, max_height)
        self.resize(min(max(self.width(), 760), max_width), min(max(self.height(), 640), max_height))

    def _scrollable_page(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        content.setObjectName("SettingsPage")
        scroll.setWidget(content)
        return scroll

    def _section(self, title: str) -> tuple[QFrame, QGridLayout]:
        frame = QFrame()
        frame.setObjectName("SettingsSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        label = QLabel(title)
        label.setObjectName("SettingsSectionTitle")
        layout.addWidget(label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        grid.setColumnMinimumWidth(0, 132)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return frame, grid

    def _add_field(self, grid: QGridLayout, row: int, label_text: str, field: QWidget, help_text: str = "") -> None:
        base_row = row * 2
        label = QLabel(label_text)
        label.setObjectName("SettingsFieldLabel")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(label, base_row, 0)
        grid.addWidget(field, base_row, 1)
        if help_text:
            help_label = QLabel(help_text)
            help_label.setObjectName("SettingsHelp")
            help_label.setWordWrap(True)
            grid.addWidget(help_label, base_row + 1, 1)
            grid.setRowMinimumHeight(base_row + 1, 16)

    def _build_conflicts_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("SettingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        intro = QLabel("Festlegen, welche Prüfungen im Konflikte-Dock erscheinen. Konflikte blockieren die Planung nicht; sie markieren Einträge, die geprüft werden sollten.")
        intro.setObjectName("SettingsSubtitle")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        content.setObjectName("SettingsConflictList")
        self.conflict_layout = QVBoxLayout(content)
        self.conflict_layout.setContentsMargins(0, 0, 0, 0)
        self.conflict_layout.setSpacing(8)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self._populate_conflict_settings()
        return page

    def _populate_conflict_settings(self) -> None:
        self._conflict_controls = []
        for idx, conflict in enumerate(self.conflicts):
            row = QFrame()
            row.setObjectName("SettingsConflictRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)
            row_layout.setSpacing(12)

            checkbox = TickCheckBox()
            checkbox.setObjectName("Field")
            checkbox.setChecked(bool(conflict.get("enabled", True)))
            row_layout.addWidget(checkbox, alignment=Qt.AlignTop)

            text_box = QVBoxLayout()
            text_box.setSpacing(3)
            name = QLabel(str(conflict.get("name", "Konfliktprüfung")))
            name.setObjectName("SettingsConflictName")
            text_box.addWidget(name)
            description = str(conflict.get("description", "")).strip()
            if description:
                help_label = QLabel(description)
                help_label.setObjectName("SettingsHelp")
                help_label.setWordWrap(True)
                text_box.addWidget(help_label)
            row_layout.addLayout(text_box, 1)

            controls = {"enabled": checkbox}
            options = self._conflict_options_widget(conflict, controls)
            if options is not None:
                row_layout.addWidget(options, alignment=Qt.AlignVCenter)

            self._conflict_controls.append(controls)
            self.conflict_layout.addWidget(row)
        self.conflict_layout.addStretch(1)

    def _conflict_options_widget(self, conflict: Dict, controls: Dict) -> Optional[QWidget]:
        key = str(conflict.get("key", ""))
        if key.startswith("capacity_warning"):
            box = QWidget()
            layout = QHBoxLayout(box)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            type_label = QLabel(f"Typen: {self._conflict_event_types_text(conflict)}")
            type_label.setObjectName("SettingsHelp")
            label = QLabel("ab")
            label.setObjectName("SettingsHelp")
            spin = QSpinBox()
            spin.setObjectName("ConflictPercentSpin")
            spin.setRange(1, 100)
            spin.setButtonSymbols(QSpinBox.NoButtons)
            spin.setValue(int(conflict.get("min_capacity_percent", 100)))
            spin.setFixedWidth(72)
            controls["min_capacity_percent"] = spin
            sign = QLabel("%")
            sign.setObjectName("SettingsHelp")
            layout.addWidget(type_label)
            layout.addSpacing(10)
            layout.addWidget(label)
            layout.addWidget(spin)
            layout.addWidget(sign)
            return box

        if key == "duration_warning":
            box = QWidget()
            layout = QHBoxLayout(box)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            min_spin = QSpinBox()
            min_spin.setObjectName("ConflictDurationMinSpin")
            min_spin.setRange(1, 240)
            min_spin.setButtonSymbols(QSpinBox.NoButtons)
            min_spin.setValue(int(conflict.get("min_minutes", 30)))
            min_spin.setFixedWidth(72)
            controls["min_minutes"] = min_spin
            max_spin = QSpinBox()
            max_spin.setObjectName("ConflictDurationMaxSpin")
            max_spin.setRange(30, 600)
            max_spin.setButtonSymbols(QSpinBox.NoButtons)
            max_spin.setValue(int(conflict.get("max_minutes", 240)))
            max_spin.setFixedWidth(72)
            controls["max_minutes"] = max_spin
            for widget in (QLabel("min"), min_spin, QLabel("bis"), max_spin, QLabel("min")):
                if isinstance(widget, QLabel):
                    widget.setObjectName("SettingsHelp")
                layout.addWidget(widget)
            return box

        return None

    def _conflict_event_types_text(self, conflict: Dict) -> str:
        raw = conflict.get("event_types")
        if isinstance(raw, list):
            values = raw
        else:
            values = [conflict.get("event_type", "")]
        cleaned = [str(value).strip().upper() for value in values if str(value).strip()]
        return ", ".join(cleaned) if cleaned else "-"

    def _collect_conflicts(self) -> list:
        result = []
        for conflict, controls in zip(self.conflicts, self._conflict_controls):
            item = dict(conflict)
            enabled = controls.get("enabled")
            if enabled is not None:
                item["enabled"] = bool(enabled.isChecked())
            for key in ("min_capacity_percent", "min_minutes", "max_minutes"):
                widget = controls.get(key)
                if widget is not None:
                    item[key] = int(widget.value())
            result.append(item)
        return result


    def load(self, s: Dict) -> None:
        slot = self._nearest_slot_value(int(s.get("time_slot_minutes", 30)))
        idx = self.slot_cb.findData(slot)
        self.slot_cb.setCurrentIndex(idx if idx >= 0 else 0)
        self.duration_step_sb.setValue(int(s.get("duration_step_minutes", 15)))
        self.day_room_page_size_sb.setValue(self._clamped_room_page_size(s.get("day_room_page_size", 8)))

        ds = datetime.strptime(s.get("day_start", "08:00"), "%H:%M").time()
        de = datetime.strptime(s.get("day_end", "18:00"), "%H:%M").time()
        self.day_start_te.setTime(QTime(ds.hour, ds.minute))
        self.day_end_te.setTime(QTime(de.hour, de.minute))
        self._sync_time_edit_constraints()
        self.data_path_le.setText(s.get("data_path", ""))
        self.show_termine_search_cb.setChecked(bool(s.get("show_termine_search", True)))
        self.jump_to_semester_start_cb.setChecked(bool(s.get("jump_to_semester_start_on_filter", True)))
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
            "day_room_page_size": int(self.day_room_page_size_sb.value()),
            "day_start": self.day_start_te.time().toString("HH:mm"),
            "day_end": self.day_end_te.time().toString("HH:mm"),
            "data_path": self.data_path_le.text(),
            "show_termine_search": self.show_termine_search_cb.isChecked(),
            "jump_to_semester_start_on_filter": self.jump_to_semester_start_cb.isChecked(),
            "previous_year_shortcut_mode": self.previous_year_shortcut_mode_cb.currentData() or "hold",
            "theme": self.theme_cb.currentData() or "light",
            "show_weekend": self.show_weekend_cb.isChecked(),
        }
        save_conflicts(self._collect_conflicts())
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

    def _clamped_room_page_size(self, value) -> int:
        try:
            parsed = int(value)
        except Exception:
            parsed = 8
        return max(4, min(24, parsed))
