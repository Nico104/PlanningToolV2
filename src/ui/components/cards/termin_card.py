from PySide6.QtCore import Qt, Signal, QPoint, QMimeData, QRectF
from PySide6.QtGui import QDrag, QMouseEvent, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QFrame

from ...utils.color_constants import type_accent_color_for
from ...utils.qss_tokens import qss_color


class TerminCard(QFrame):
    """Interactive Termin card with drag-and-drop plus double/right-click signals"""

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
        name: str = None,
        gruppe: str = "",
        semester: str = "",
        parent=None,
        zu_besprechen: bool = False,
        besprechungshinweis: str = "",
        is_series: bool = False,
        missing_room: bool = False,
    ):
        super().__init__(parent)
        self.termin_id = termin_id
        self._press_pos: QPoint | None = None
        self._read_only = False
        self._accent_color = type_accent_color_for(typ)
        self._zu_besprechen = bool(zu_besprechen)
        self._besprechungshinweis = str(besprechungshinweis or "").strip()
        self._is_series = bool(is_series)
        self._missing_room = bool(missing_room or not str(raum or "").strip())
        self._needs_attention = self._zu_besprechen or self._missing_room

        self.setObjectName("TerminCard")
        self.setProperty("zuBesprechen", self._zu_besprechen)
        self.setProperty("needsAttention", self._needs_attention)
        self.setProperty("series", self._is_series)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)
        tooltip_lines = []
        if self._is_series:
            tooltip_lines.append("Serientermin")
        if self._zu_besprechen:
            tooltip_lines.append("Zu besprechen")
            if self._besprechungshinweis:
                tooltip_lines.append(self._besprechungshinweis)
        if self._missing_room:
            tooltip_lines.append("Kein Raum zugewiesen")
        if tooltip_lines:
            self.setToolTip("\n".join(tooltip_lines))

        marker_count = int(self._zu_besprechen) + int(self._missing_room)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 10, 12 + (13 * marker_count), 10)

        root.setSpacing(6)

        if name:
            lbl_name = QLabel(name)
            lbl_name.setObjectName("CardName")
            root.addWidget(lbl_name)
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
            l.setProperty("chip", True)
            return l

        chips.addWidget(chip(typ, "ChipType"))
        semester_text = str(semester or "").strip()
        if semester_text:
            semester_chip = chip(semester_text, "ChipSemester")
            semester_key = semester_text.upper().replace(" ", "")
            semester_chip.setProperty(
                "kind",
                "ss" if semester_key.startswith("SS") else "ws",
            )
            chips.addWidget(semester_chip)
        if str(gruppe or "").strip():
            chips.addWidget(chip(str(gruppe).strip(), "ChipGroup"))
        if self._is_series:
            chips.addWidget(chip("Serie", "ChipSeries"))
        if not self._missing_room:
            chips.addWidget(chip(raum, "ChipRoom"))
        else:
            chips.addWidget(chip("Kein Raum", "ChipMissingRoom"))
        if self._zu_besprechen:
            discuss_chip = chip("Zu besprechen", "ChipDiscuss")
            if self._besprechungshinweis:
                discuss_chip.setToolTip(self._besprechungshinweis)
            chips.addWidget(discuss_chip)
        # if ap:
        #     chips.addWidget(chip("Anwesenheitspflicht", "ChipAP"))

        chips.addStretch(1)
        root.addLayout(chips)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        try:
            painter.fillRect(1, 1, 3, max(0, self.height() - 2), self._accent_color)
            if self.width() < 32 or self.height() < 24:
                return

            painter.setRenderHint(QPainter.Antialiasing, True)

            def draw_badge(label: str, bg_name: str, fg_name: str, x_right: int) -> int:
                rect = QRectF(self.width() - x_right - 10, 8, 10, 10)
                painter.setPen(Qt.NoPen)
                painter.setBrush(qss_color(bg_name))
                painter.drawRoundedRect(rect, 2, 2)
                font = painter.font()
                font.setBold(True)
                font.setPointSize(max(6, font.pointSize() - 2))
                painter.setFont(font)
                painter.setPen(qss_color(fg_name))
                painter.drawText(rect.toRect(), Qt.AlignCenter, label)
                return x_right + 13

            right = 8
            if self._zu_besprechen:
                right = draw_badge(
                    "!",
                    "planner-discuss-border",
                    "planner-discuss-badge-text",
                    right,
                )
            if self._missing_room:
                draw_badge(
                    "R",
                    "planner-missing-room-border",
                    "planner-missing-room-badge-text",
                    right,
                )
        finally:
            painter.end()

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        self.setCursor(Qt.ArrowCursor if self._read_only else Qt.PointingHandCursor)

    def _show_read_only_warning(self) -> None:
        cb = getattr(self.window(), "_show_history_read_only_toast", None)
        if callable(cb):
            cb()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            self._press_pos = e.pos()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._read_only:
            if (
                e.buttons() & Qt.LeftButton
                and self._press_pos is not None
                and (e.pos() - self._press_pos).manhattanLength() >= 8
            ):
                self._show_read_only_warning()
                self._press_pos = None
            return
        if not (e.buttons() & Qt.LeftButton):
            return
        if self._press_pos is None:
            return
        if (e.pos() - self._press_pos).manhattanLength() < 8:
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.termin_id)
        drag.setMimeData(mime)

        pm = QPixmap(self.size())
        pm.fill(Qt.transparent)

        p = QPainter(pm)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)

            scale = 0.6

            p.translate(pm.width() * (1 - scale) / 2, pm.height() * (1 - scale) / 2)
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
        if self._read_only:
            self._show_read_only_warning()
            e.accept()
            return
        self.double_clicked.emit(self.termin_id)
        super().mouseDoubleClickEvent(e)

    def contextMenuEvent(self, e) -> None:
        self.right_clicked.emit(self.termin_id)
        e.accept()
