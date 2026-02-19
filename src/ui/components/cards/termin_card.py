from PySide6.QtCore import Qt, Signal, QPoint, QMimeData
from PySide6.QtGui import QDrag, QMouseEvent, QPixmap
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QFrame

from PySide6.QtCore import QPoint, QRectF
from PySide6.QtGui import QPainter, QPainterPath

# def mouseMoveEvent(self, e: QMouseEvent) -> None:
#     if not (e.buttons() & Qt.LeftButton):
#         return
#     if self._press_pos is None:
#         return

#     if (e.pos() - self._press_pos).manhattanLength() < 8:
#         return

#     drag = QDrag(self)
#     mime = QMimeData()
#     mime.setText(self.termin_id)
#     mime.setData(MIME_TERMIN_ID, self.termin_id.encode("utf-8"))
#     drag.setMimeData(mime)

#     # --- nice drag preview: transparent + rounded corners ---
#     pm = QPixmap(self.size())
#     pm.fill(Qt.transparent)

#     p = QPainter(pm)
#     p.setRenderHint(QPainter.Antialiasing, True)

#     radius = 4  # muss zu deinem QSS border-radius passen
#     path = QPainterPath()
#     path.addRoundedRect(QRectF(0, 0, pm.width()-8, pm.height()-2), radius, radius)
#     p.setClipPath(path)

#     self.render(p)  # render widget into painter (clipped)
#     p.end()

#     drag.setPixmap(pm)
#     drag.setHotSpot(self._press_pos)

#     drag.exec(Qt.CopyAction)



MIME_TERMIN_ID = "application/termin-id"


class TerminCard(QFrame):
    double_clicked = Signal(str)
    right_clicked = Signal(str)

    def __init__(
        self,
        termin_id: str,
        title: str,
        date: str,
        time: str,
        typ: str,
        raum: str,
        ap: bool,
        duration: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.termin_id = termin_id
        self._press_pos: QPoint | None = None

        self.setObjectName("TerminCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        
        root.setSpacing(6)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("CardTitle")
        root.addWidget(lbl_title)

        lbl_dt = QLabel(f"{date} · {time}")
        lbl_dt.setObjectName("CardSub")
        root.addWidget(lbl_dt)

        chips = QHBoxLayout()
        chips.setSpacing(6)

        def chip(text, name):
            l = QLabel(text)
            l.setObjectName(name)
            l.setAlignment(Qt.AlignCenter)
            l.setProperty("chip", True)  # optional für generisches Chip-Styling
            return l

        chips.addWidget(chip(typ, "ChipType"))
        chips.addWidget(chip(raum, "ChipRoom"))
        if ap:
            chips.addWidget(chip("AP", "ChipAP"))
        if duration > 0:
            chips.addWidget(chip(f"{duration} min", "ChipDuration"))

        chips.addStretch(1)
        root.addLayout(chips)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            self._press_pos = e.pos()
        super().mousePressEvent(e)


    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if not (e.buttons() & Qt.LeftButton):
            return
        if self._press_pos is None:
            return
        if (e.pos() - self._press_pos).manhattanLength() < 8:
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.termin_id)
        mime.setData(MIME_TERMIN_ID, self.termin_id.encode("utf-8"))
        drag.setMimeData(mime)

        pm = QPixmap(self.size())
        pm.fill(Qt.transparent)

        p = QPainter(pm)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)

            scale = 0.6

            # keep it centered
            p.translate(pm.width() * (1 - scale) / 2,
                        pm.height() * (1 - scale) / 2)
            p.scale(scale, scale)

            radius = 4
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, pm.width(), pm.height()), radius, radius)
            p.setClipPath(path)

            self.render(p, QPoint(0, 0))
        finally:
            p.end()


        drag.setPixmap(pm)
        drag.setHotSpot(self._press_pos)

        drag.exec(Qt.CopyAction)


    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        self.double_clicked.emit(self.termin_id)
        super().mouseDoubleClickEvent(e)

    def contextMenuEvent(self, e) -> None:
        self.right_clicked.emit(self.termin_id)
        e.accept()
