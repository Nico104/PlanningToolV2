from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout


class Toast(QWidget):
    def __init__(self, parent, text: str, duration_ms: int = 3000):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.duration_ms = duration_ms

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.label = QLabel(text, self)
        self.label.setStyleSheet(
            "color: white; background: rgba(50,50,50,0.95); padding:8px 12px; border-radius:6px;"
        )
        layout.addWidget(self.label)

    def show(self) -> None:
        parent = self.parent() if self.parent() is not None else None
        if parent:
            
            pg = parent.geometry()
            w = self.sizeHint().width()
            h = self.sizeHint().height()
            x = pg.x() + (pg.width() - w) // 2
            y = pg.y() + pg.height() - h - 24
            self.move(QPoint(max(8, x), max(8, y)))
        super().show()
        QTimer.singleShot(self.duration_ms, self.close)
