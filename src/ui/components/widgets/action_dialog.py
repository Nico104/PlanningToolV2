from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


@dataclass(frozen=True)
class DialogAction:
    key: str
    label: str
    description: str = ""
    role: str = "secondary"


class ActionDialog(QDialog):
    def __init__(
        self,
        parent,
        *,
        title: str,
        subtitle: str,
        actions: list[DialogAction],
        section_title: str = "Aktion auswählen",
    ):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(560)
        self._result_key: Optional[str] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        title_label = QLabel(title, self)
        title_label.setObjectName("DialogTitle")
        root.addWidget(title_label)

        subtitle_label = QLabel(subtitle, self)
        subtitle_label.setObjectName("DialogSubtitle")
        subtitle_label.setWordWrap(True)
        root.addWidget(subtitle_label)

        section = QFrame(self)
        section.setObjectName("DialogSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(14, 12, 14, 14)
        section_layout.setSpacing(8)

        section_label = QLabel(section_title, section)
        section_label.setObjectName("DialogSectionTitle")
        section_layout.addWidget(section_label)

        for action in actions:
            button = QPushButton(action.label, section)
            button.setObjectName("ActionChoiceButton")
            button.setProperty("role", action.role)
            button.setMinimumHeight(42)
            button.setToolTip(action.description)
            button.clicked.connect(lambda _checked=False, key=action.key: self._choose(key))
            section_layout.addWidget(button)
            if action.description:
                help_label = QLabel(action.description, section)
                help_label.setObjectName("SettingsHelp")
                help_label.setTextFormat(Qt.RichText)
                help_label.setWordWrap(True)
                section_layout.addWidget(help_label)

        root.addWidget(section)

        actions_row = QHBoxLayout()
        actions_row.addStretch(1)
        cancel_btn = QPushButton("Abbrechen", self)
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        actions_row.addWidget(cancel_btn)
        root.addLayout(actions_row)

    @property
    def result_key(self) -> Optional[str]:
        return self._result_key

    def _choose(self, key: str) -> None:
        self._result_key = key
        self.accept()
