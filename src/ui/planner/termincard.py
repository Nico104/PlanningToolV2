from PySide6.QtCore import Qt, QMimeData, Signal
from shiboken6 import isValid
import weakref
from PySide6.QtGui import QColor, QDrag
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap



class TerminCard(QLabel):
    """
    A compact card widget for displaying and dragging a single Termin in the planner grid
    Handles focus, highlighting, drag-and-drop, and double-click events for planner items
    """
    DRAG_THRESHOLD = 5  # Minimum drag distance (pixels) to start drag operation
    doubleClicked = Signal(str)
    _focused_card_ref: weakref.ref | None = None  # Tracks the currently focused card globally
    _highlighted_refs: list[weakref.ref] = []  # Tracks all highlighted cards globally

    def __init__(self, termin_id: str, text: str, bg_color: QColor, parent=None):
        super().__init__(text, parent)
        self.termin_id = termin_id
        self.bg_color = bg_color
        self._focused = False 
        self._highlighted = False

        self.setWordWrap(True)
        self._base_style = (
            f"background-color: {bg_color.name()};"
            "color: #111111;"
            "padding: 0px;"
            "border: none;"
            "font-size: 10px;"
            "border-radius: 4px;"
        )
        self._apply_style()
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setContentsMargins(0, 0, 0, 0)
        self.setFocusPolicy(Qt.StrongFocus)

    def _apply_style(self) -> None:
        """Update the card's stylesheet based on focus/highlight state"""
        border = "border: 2px solid #111111;" if (self._focused or self._highlighted) else "border: none;"
        self.setStyleSheet(self._base_style + border)

    @classmethod
    def clear_global_focus(cls) -> None:
        """Remove focus from any globally focused card (if any)"""
        card = cls._focused_card_ref() if cls._focused_card_ref else None
        if card is not None and isValid(card):
            card._focused = False
            card._apply_style()
            card.clearFocus()
        cls._focused_card_ref = None

    @classmethod
    def clear_all_highlights(cls) -> None:
        """Remove highlight from all cards globally"""
        for ref in cls._highlighted_refs:
            card = ref() if ref else None
            if card is not None and isValid(card):
                card._highlighted = False
                card._apply_style()
        cls._highlighted_refs = []

    def set_conflict_highlight(self, enabled: bool) -> None:
        """Highlight this card to indicate a conflict"""
        self._highlighted = enabled
        if enabled:
            self._highlighted_refs.append(weakref.ref(self)) #weakref so being in the highlight list doesn’t keep it alive unnecessarily
        self._apply_style()

    def mousePressEvent(self, event):
        """Start drag operation or set focus when user clicks on the card"""
        if event.button() == Qt.LeftButton:
            self.setFocus()
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        """Handle focus-in: update global focus and style"""
        prev = TerminCard._focused_card_ref() if TerminCard._focused_card_ref else None
        if prev is not None and isValid(prev) and prev is not self:
            prev._focused = False
            prev._apply_style()
        self._focused = True
        TerminCard._focused_card_ref = weakref.ref(self)
        self._apply_style()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        """Handle focus-out: clear global focus if this card was focused."""
        self._focused = False
        cur = TerminCard._focused_card_ref() if TerminCard._focused_card_ref else None
        if cur is self:
            TerminCard._focused_card_ref = None
        self._apply_style()
        super().focusOutEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Emit doubleClicked signal with termin_id on left double-click"""
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit(self.termin_id)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        """
        Start drag-and-drop if mouse moved far enough with left button pressed
        Sets up MIME data and drag pixmap for visual feedback
        """
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