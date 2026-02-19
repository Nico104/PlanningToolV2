from src.services.conflict_service import load_conflicts, save_conflicts
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, QCheckBox, QLabel, QPushButton, QSpinBox
)
from PySide6.QtCore import Qt, Signal
from src.ui.components.widgets.tick_checkbox import TickCheckBox


class KonflikteDialog(QDialog):
    conflicts_changed = Signal()
    def __init__(self, parent=None, conflicts_path=None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Konflikte")
        self.setModal(True)
        self.conflicts_path = conflicts_path
        self.conflicts = load_conflicts(self.conflicts_path)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.setMinimumWidth(400)

        # Scrollable area for conflict rows
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll_content = QWidget()
        self.conflict_layout = QVBoxLayout(scroll_content)
        self.conflict_layout.setContentsMargins(0, 0, 0, 0)
        self.conflict_layout.setSpacing(0)
        scroll.setWidget(scroll_content)
        lay.addWidget(scroll)
        self.populate_conflicts()

    def save_conflicts(self):
        save_conflicts(self.conflicts, self.conflicts_path)
        self.conflicts_changed.emit()

    def populate_conflicts(self):
        # Remove old widgets
        while self.conflict_layout.count():
            child = self.conflict_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for idx, conflict in enumerate(self.conflicts):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 6, 12, 6)
            row_layout.setSpacing(18)
            row.setStyleSheet("background: #fff; border: none;")
            checkbox = TickCheckBox()
            checkbox.setChecked(conflict.get('enabled', True))
            label = QLabel(conflict['name'])
            label.setStyleSheet("font-size: 15px;")
            row_layout.addWidget(checkbox, alignment=Qt.AlignVCenter)
            row_layout.addWidget(label, alignment=Qt.AlignVCenter)

            # Add compact, inline percent input for capacity warnings (styled like termin_dialog)
            if conflict.get('key', '').startswith('capacity_warning'):
                percent_box = QSpinBox()
                percent_box.setObjectName("ConflictPercentSpin")
                percent_box.setRange(1, 100)
                percent_box.setButtonSymbols(QSpinBox.NoButtons)
                percent_box.setValue(conflict.get('min_capacity_percent', 100))
                percent_box.setMinimumWidth(60)
                percent_box.setMaximumWidth(90)
                percent_box.setFixedHeight(28)
                percent_box.setStyleSheet(
                    "QSpinBox {"
                    "  background: #fff;"
                    "  border: 1px solid #d0d0d0;"
                    "  border-radius: 4px;"
                    "  padding: 0 8px 0 8px;"
                    "  font-size: 14px;"
                    "}"
                )
                percent_box.setToolTip("Mindest-Auslastung in Prozent, bevor eine Warnung angezeigt wird.")
                percent_label = QLabel("Min. Kapazität:")
                percent_label.setObjectName("ConflictPercentLabel")
                percent_sign = QLabel("%")
                percent_sign.setObjectName("ConflictPercentSign")
                # Inline layout for label, spinbox, and percent sign
                percent_inline = QWidget()
                percent_inline_layout = QHBoxLayout(percent_inline)
                percent_inline_layout.setContentsMargins(0, 0, 0, 0)
                percent_inline_layout.setSpacing(4)
                percent_inline_layout.addWidget(percent_label)
                percent_inline_layout.addWidget(percent_box)
                percent_inline_layout.addWidget(percent_sign)
                percent_inline_layout.addStretch(1)
                def on_percent_changed(val, idx=idx):
                    self.conflicts[idx]['min_capacity_percent'] = val
                    self.save_conflicts()
                percent_box.valueChanged.connect(on_percent_changed)
                row_layout.addWidget(percent_inline, alignment=Qt.AlignVCenter)

            # Add min/max duration input for duration_warning
            if conflict.get('key', '') == 'duration_warning':
                # Min duration group
                min_label = QLabel("Min. Dauer:")
                min_label.setObjectName("ConflictDurationMinLabel")
                min_box = QSpinBox()
                min_box.setObjectName("ConflictDurationMinSpin")
                min_box.setRange(1, 240)
                min_box.setButtonSymbols(QSpinBox.NoButtons)
                min_box.setValue(conflict.get('min_minutes', 30))
                min_box.setMinimumWidth(60)
                min_box.setMaximumWidth(90)
                min_box.setFixedHeight(28)
                min_box.setStyleSheet(
                    "QSpinBox {"
                    "  background: #fff;"
                    "  border: 1px solid #d0d0d0;"
                    "  border-radius: 4px;"
                    "  padding: 0 8px 0 8px;"
                    "  font-size: 14px;"
                    "}"
                )
                min_box.setToolTip('Minimale erlaubte Dauer in Minuten')
                min_sign = QLabel("min")
                min_sign.setObjectName("ConflictDurationMinSign")
                min_group = QWidget()
                min_group_layout = QHBoxLayout(min_group)
                min_group_layout.setContentsMargins(0, 0, 0, 0)
                min_group_layout.setSpacing(4)
                min_group_layout.addWidget(min_label)
                min_group_layout.addWidget(min_box)
                min_group_layout.addWidget(min_sign)

                # Max duration group
                max_label = QLabel("Max. Dauer:")
                max_label.setObjectName("ConflictDurationMaxLabel")
                max_box = QSpinBox()
                max_box.setObjectName("ConflictDurationMaxSpin")
                max_box.setRange(30, 600)
                max_box.setButtonSymbols(QSpinBox.NoButtons)
                max_box.setValue(conflict.get('max_minutes', 240))
                max_box.setMinimumWidth(60)
                max_box.setMaximumWidth(90)
                max_box.setFixedHeight(28)
                max_box.setStyleSheet(
                    "QSpinBox {"
                    "  background: #fff;"
                    "  border: 1px solid #d0d0d0;"
                    "  border-radius: 4px;"
                    "  padding: 0 8px 0 8px;"
                    "  font-size: 14px;"
                    "}"
                )
                max_box.setToolTip('Maximale erlaubte Dauer in Minuten')
                max_sign = QLabel("min")
                max_sign.setObjectName("ConflictDurationMaxSign")
                max_group = QWidget()
                max_group_layout = QHBoxLayout(max_group)
                max_group_layout.setContentsMargins(0, 0, 0, 0)
                max_group_layout.setSpacing(4)
                max_group_layout.addWidget(max_label)
                max_group_layout.addWidget(max_box)
                max_group_layout.addWidget(max_sign)

                # Inline layout for min/max duration, with spacing between groups
                duration_inline = QWidget()
                duration_inline_layout = QHBoxLayout(duration_inline)
                duration_inline_layout.setContentsMargins(0, 0, 0, 0)
                duration_inline_layout.setSpacing(24)  # More space between min and max
                duration_inline_layout.addWidget(min_group)
                duration_inline_layout.addWidget(max_group)
                duration_inline_layout.addStretch(1)
                def on_min_changed(val, idx=idx):
                    self.conflicts[idx]['min_minutes'] = val
                    self.save_conflicts()
                def on_max_changed(val, idx=idx):
                    self.conflicts[idx]['max_minutes'] = val
                    self.save_conflicts()
                min_box.valueChanged.connect(on_min_changed)
                max_box.valueChanged.connect(on_max_changed)
                row_layout.addWidget(duration_inline, alignment=Qt.AlignVCenter)

            if 'details' in conflict:
                edit_btn = QPushButton("Details ändern")
                edit_btn.setStyleSheet("padding: 2px 10px;")
                row_layout.addWidget(edit_btn, alignment=Qt.AlignVCenter)
                def on_edit_details(idx=idx):
                    print(f"Edit details for conflict: {self.conflicts[idx]['name']}")
                edit_btn.clicked.connect(on_edit_details)
            row_layout.addStretch(1)
            def on_toggle(state, idx=idx):
                self.conflicts[idx]['enabled'] = bool(state)
                self.save_conflicts()
            checkbox.stateChanged.connect(on_toggle)
            self.conflict_layout.addWidget(row)
        self.conflict_layout.addStretch(1)

    def _on_ok(self):
        self.save_conflicts()
        self.accept()
