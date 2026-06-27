from PySide6.QtWidgets import QDialog, QFrame, QVBoxLayout, QLabel, QDialogButtonBox


class DeleteDialog(QDialog):
    def __init__(self, parent, text, *, detail: str = "", title: str = "Löschen bestätigen"):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(12)

        title_label = QLabel(title, self)
        title_label.setObjectName("DialogTitle")
        lay.addWidget(title_label)

        subtitle = QLabel(text, self)
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        if detail:
            section = QFrame(self)
            section.setObjectName("DialogSection")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(14, 12, 14, 14)
            section_layout.setSpacing(6)
            detail_label = QLabel(detail, section)
            detail_label.setWordWrap(True)
            section_layout.addWidget(detail_label)
            lay.addWidget(section)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setObjectName("DialogButtons")
        ok_btn = bb.button(QDialogButtonBox.Ok)
        cancel_btn = bb.button(QDialogButtonBox.Cancel)
        if ok_btn:
            ok_btn.setText("Löschen")
            ok_btn.setObjectName("DangerButton")
        if cancel_btn:
            cancel_btn.setText("Abbrechen")
            cancel_btn.setObjectName("SecondaryButton")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
