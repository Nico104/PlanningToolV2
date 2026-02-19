from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox

class DeleteDialog(QDialog):
    def __init__(self, parent, text):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Löschen")
        self.setModal(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        label = QLabel(text)
        label.setWordWrap(True)
        lay.addWidget(label)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setObjectName("DialogButtons")
        ok_btn = bb.button(QDialogButtonBox.Ok)
        cancel_btn = bb.button(QDialogButtonBox.Cancel)
        if ok_btn:
            ok_btn.setObjectName("PrimaryButton")
        if cancel_btn:
            cancel_btn.setObjectName("SecondaryButton")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
