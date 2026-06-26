from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ...utils.qss_tokens import qss_color


class TimeGridDragPreviewOverlay(QWidget):
    """Transparent overlay that paints the live drag preview above cell widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

        self._rect = QRect()
        self._text = ""
        self._has_conflict = False
        self._conflict_text = ""
        self._fill_color = QColor()
        self.hide()

    def set_preview(
        self,
        rect: QRect,
        text: str,
        fill_color: QColor,
        has_conflict: bool,
        conflict_text: str = "",
    ) -> None:
        self._rect = QRect(rect)
        self._text = str(text or "")
        self._fill_color = QColor(fill_color)
        self._has_conflict = bool(has_conflict)
        self._conflict_text = str(conflict_text or "").strip()

        if self._rect.isValid() and self._rect.width() > 0 and self._rect.height() > 0:
            self.show()
            self.raise_()
            self.update()
        else:
            self.clear_preview()

    def clear_preview(self) -> None:
        self._rect = QRect()
        self._text = ""
        self._has_conflict = False
        self._conflict_text = ""
        self.hide()
        self.update()

    def paintEvent(self, event) -> None:
        if self._rect.isNull() or not self._rect.isValid():
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            preview_rect = self._rect.adjusted(1, 1, -2, -2)

            painter.setBrush(self._fill_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(preview_rect, 4, 4)

            content_rect = preview_rect.adjusted(6, 5, -6, -5)
            base_font = painter.font()

            if self._has_conflict and content_rect.width() > 36 and content_rect.height() > 16:
                label = f"Konflikt: {self._conflict_text or 'Prüfen'}"
                metrics = painter.fontMetrics()
                label = metrics.elidedText(label, Qt.ElideRight, max(1, content_rect.width() - 8))
                label_height = min(18, max(14, content_rect.height()))
                label_width = min(content_rect.width(), metrics.horizontalAdvance(label) + 12)
                label_rect = QRect(content_rect.left(), content_rect.top(), label_width, label_height)

                painter.setBrush(qss_color("planner-drop-conflict-bg"))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(label_rect, 3, 3)

                label_font = painter.font()
                label_font.setBold(True)
                label_font.setPointSize(max(7, label_font.pointSize() - 1))
                painter.setFont(label_font)
                painter.setPen(qss_color("planner-drop-conflict-text"))
                painter.drawText(label_rect.adjusted(6, 0, -6, 0), Qt.AlignLeft | Qt.AlignVCenter, label)

                content_rect.setTop(content_rect.top() + label_height + 4)
                painter.setFont(base_font)

            if self._text:
                painter.setPen(qss_color("planner-text"))
                painter.drawText(content_rect, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, self._text)

            border_color = (
                qss_color("planner-drop-conflict-bg")
                if self._has_conflict
                else qss_color("planner-focus-border")
            )
            pen = QPen(border_color)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(preview_rect, 4, 4)
        finally:
            painter.end()
