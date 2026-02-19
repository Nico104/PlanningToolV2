from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QFrame


class ConflictCard(QFrame):
    clicked = Signal(list)

    def __init__(
        self,
        termin_ids: list[str],
        title: str,
        subtitle: str,
        typ: str,
        raum: str,
        lva: str,
        gruppe: str,
        message: str,
        conflict_kind: str,
        severity: str,
        parent=None,
    ):
        super().__init__(parent)
        self.termin_ids = termin_ids

        self.setObjectName("ConflictCard")
        self.setCursor(Qt.PointingHandCursor)
        # self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("conflictKind", conflict_kind)
        self.setProperty("severity", severity)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("CardTitle")
        root.addWidget(lbl_title)

        lbl_sub = QLabel(subtitle)
        lbl_sub.setObjectName("CardSub")
        root.addWidget(lbl_sub)

        lbl_msg = QLabel(message)
        lbl_msg.setObjectName("CardSub")
        lbl_msg.setWordWrap(True)
        root.addWidget(lbl_msg)

        chips = QHBoxLayout()
        chips.setSpacing(6)

        def chip(text, name):
            l = QLabel(text)
            l.setObjectName(name)
            l.setAlignment(Qt.AlignCenter)
            l.setProperty("chip", True)
            return l

        chips.addWidget(chip(typ, "ChipType"))
        if raum:
            chips.addWidget(chip(raum, "ChipRoom"))
        if lva:
            chips.addWidget(chip(lva, "ChipLva"))
        if gruppe:
            chips.addWidget(chip(gruppe, "ChipGroup"))

        chips.addStretch(1)
        root.addLayout(chips)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.termin_ids)
        super().mousePressEvent(e)
