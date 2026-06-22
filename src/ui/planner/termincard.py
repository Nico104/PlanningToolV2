import weakref

from PySide6.QtCore import Qt, QMimeData, Signal
from PySide6.QtGui import QColor, QDrag, QPainter, QPixmap
from PySide6.QtWidgets import QLabel
from shiboken6 import isValid

from ..utils.qss_tokens import qss_color
from ..utils.color_constants import type_accent_color_for


class TerminCard(QLabel):
    """Compact planner card with focus, highlight and drag behaviour."""

    DRAG_THRESHOLD = 5
    doubleClicked = Signal(str)
    _focused_card_ref: weakref.ref | None = None
    _highlighted_refs: list[weakref.ref] = []

    def __init__(
        self,
        termin_id: str,
        text: str,
        bg_color: QColor,
        parent=None,
        zu_besprechen: bool = False,
        besprechungshinweis: str = "",
        typ: str = "",
        is_series: bool = False,
        details_tooltip: str = "",
    ):
        display_text = f"! {text}" if zu_besprechen else text
        super().__init__(display_text, parent)
        self.termin_id = termin_id
        self.bg_color = bg_color
        self.accent_color = type_accent_color_for(typ)
        self._zu_besprechen = bool(zu_besprechen)
        self._besprechungshinweis = str(besprechungshinweis or "").strip()
        self._is_series = bool(is_series)
        self._focused = False 
        self._highlighted = False
        self._read_only = False

        self.setWordWrap(True)
        right_padding = 14 if self._is_series else 2
        self._base_style = (
            f"background-color: {bg_color.name()};"
            f"color: {qss_color('planner-text').name()};"
            f"padding: 2px {right_padding}px 2px 7px;"
            "border: none;"
            "font-size: 10px;"
            "border-radius: 4px;"
        )
        self._apply_style()
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setContentsMargins(0, 0, 0, 0)
        self.setFocusPolicy(Qt.StrongFocus)
        tooltip_lines = []
        if self._is_series:
            tooltip_lines.append("Serientermin")
        if self._zu_besprechen:
            tooltip_lines.append("Zu besprechen")
            if self._besprechungshinweis:
                tooltip_lines.append(self._besprechungshinweis)
        details_tooltip = str(details_tooltip or "").strip()
        if details_tooltip:
            if tooltip_lines:
                tooltip_lines.append("")
            tooltip_lines.extend(details_tooltip.splitlines())
        if tooltip_lines:
            self.setToolTip("\n".join(tooltip_lines))

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        self.setCursor(Qt.ArrowCursor if self._read_only else Qt.OpenHandCursor)

    def _show_read_only_warning(self) -> None:
        cb = getattr(self.window(), "_show_history_read_only_toast", None)
        if callable(cb):
            cb()

    def _apply_style(self) -> None:
        if self._highlighted:
            border = f"border: 2px solid {qss_color('planner-drop-conflict-bg').name()};"
        elif self._focused:
            border = f"border: 2px solid {qss_color('planner-focus-border').name()};"
        elif self._zu_besprechen:
            border = f"border: 2px solid {qss_color('planner-discuss-border').name()};"
        else:
            border = "border: none;"
        self.setStyleSheet(self._base_style + border)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        try:
            show_type_accent = not (self._highlighted or self._focused or self._zu_besprechen)
            if show_type_accent:
                painter.fillRect(0, 0, 4, self.height(), self.accent_color)

            if self._is_series and self.width() >= 28 and self.height() >= 16:
                marker_color = QColor(self.accent_color if show_type_accent else qss_color("planner-text"))
                marker_color.setAlpha(42)
                text_color = QColor(self.accent_color if show_type_accent else qss_color("planner-text"))
                badge_rect = self.rect().adjusted(self.width() - 13, 2, -2, -(self.height() - 12))
                painter.setPen(Qt.NoPen)
                painter.setBrush(marker_color)
                painter.drawRoundedRect(badge_rect, 2, 2)
                font = painter.font()
                font.setBold(True)
                font.setPointSize(max(6, font.pointSize() - 2))
                painter.setFont(font)
                painter.setPen(text_color)
                painter.drawText(badge_rect, Qt.AlignCenter, "S")
        finally:
            painter.end()

    @classmethod
    def clear_global_focus(cls) -> None:
        card = cls._focused_card_ref() if cls._focused_card_ref else None
        if card is not None and isValid(card):
            card._focused = False
            card._apply_style()
            card.clearFocus()
        cls._focused_card_ref = None

    @classmethod
    def clear_all_highlights(cls) -> None:
        for ref in cls._highlighted_refs:
            card = ref() if ref else None
            if card is not None and isValid(card):
                card._highlighted = False
                card._apply_style()
        cls._highlighted_refs = []

    def set_conflict_highlight(self, enabled: bool) -> None:
        self._highlighted = enabled
        if enabled:
            self._highlighted_refs.append(weakref.ref(self))
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setFocus()
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        prev = TerminCard._focused_card_ref() if TerminCard._focused_card_ref else None
        if prev is not None and isValid(prev) and prev is not self:
            prev._focused = False
            prev._apply_style()
        self._focused = True
        TerminCard._focused_card_ref = weakref.ref(self)
        self._apply_style()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._focused = False
        cur = TerminCard._focused_card_ref() if TerminCard._focused_card_ref else None
        if cur is self:
            TerminCard._focused_card_ref = None
        self._apply_style()
        super().focusOutEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._read_only:
            self._show_read_only_warning()
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit(self.termin_id)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if self._read_only:
            if (
                event.buttons() & Qt.LeftButton
                and hasattr(self, "_drag_start_pos")
                and (event.pos() - self._drag_start_pos).manhattanLength() >= self.DRAG_THRESHOLD
            ):
                self._show_read_only_warning()
                delattr(self, "_drag_start_pos")
            return
        if not (event.buttons() & Qt.LeftButton):
            return

        if not hasattr(self, '_drag_start_pos'):
            return

        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance < self.DRAG_THRESHOLD:
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(self.termin_id))
        drag.setMimeData(mime)

        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        self.render(pixmap)
        drag.setPixmap(pixmap)

        drag.exec(Qt.MoveAction)

        super().mouseMoveEvent(event)
