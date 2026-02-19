from PySide6.QtCore import Qt, QSize, QMimeData, Signal
from shiboken6 import isValid
import weakref
from PySide6.QtGui import QColor, QBrush, QDrag, QPainter, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from datetime import date
from PySide6.QtGui import QPixmap


class TerminCard(QLabel):
    #A compact card widget for displaying a single termin
    MIME = "application/termin-id"
    doubleClicked = Signal(str)  # Emits termin_id
    _focused_card_ref: weakref.ref | None = None
    _highlighted_refs: list[weakref.ref] = []

    def __init__(self, termin_id: str, text: str, bg_color: QColor, parent=None):
        super().__init__(text, parent)
        self.termin_id = termin_id
        self.bg_color = bg_color
        self._is_dragging = False
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
        if self._focused:
            border = "border: 2px solid #111111;"
        elif self._highlighted:
            border = "border: 2px solid #ff9800;"
        else:
            border = "border: none;"
        self.setStyleSheet(self._base_style + border)

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
        #Start drag operation when user clicks on the card
        if event.button() == Qt.LeftButton:
            self.setFocus()
            self._drag_start_pos = event.pos()
            self._is_dragging = False
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

    def mouseReleaseEvent(self, event):
        #Handle click if not dragging
        if event.button() == Qt.LeftButton and not self._is_dragging:
            #handle click
            pass
        self._is_dragging = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit(self.termin_id)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        
        if not hasattr(self, '_drag_start_pos'):
            return
            
        # Only start drag if moved enough distance
        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance < 5:  # Minimum drag distance
            return

        self._is_dragging = True

        # Create and execute drag with visual feedback
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(self.MIME, str(self.termin_id).encode("utf-8"))
        drag.setMimeData(mime)
        
        # Set a drag pixmap
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        self.render(pixmap)
        drag.setPixmap(pixmap)
        
        # Execute the drag and drop operation
        # Returns Qt.MoveAction if successfully dropped
        result = drag.exec(Qt.MoveAction)
        
        super().mouseMoveEvent(event)


class TimeSlotCell(QWidget):
    def __init__(self, target_date: date, parent=None):
        super().__init__(parent)
        self.target_date = target_date
        self._grid_row_height = 0
        self._grid_span_rows = 0
        self.setContentsMargins(0, 0, 0, 0)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.setLayout(self.layout)
        
       
        self.setStyleSheet("background-color: transparent;")

    def set_grid_info(self, row_height: int, span_rows: int) -> None:
        self._grid_row_height = max(0, row_height)
        self._grid_span_rows = max(0, span_rows)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._grid_row_height <= 0 or self._grid_span_rows <= 1:
            return
        painter = QPainter(self)
        pen = QPen(QColor("#f0efec"))
        painter.setPen(pen)
        for i in range(1, self._grid_span_rows):
            y = i * self._grid_row_height
            painter.drawLine(0, y, self.width(), y)

    def add_termin_card(self, card: TerminCard, top_offset_px: int = 0) -> None:
        wrapper = QWidget(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        vbox = QVBoxLayout(wrapper)
        vbox.setContentsMargins(0, max(0, top_offset_px), 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(card)
        self.layout.addWidget(wrapper, 1, Qt.AlignTop)  # align to top, equal horizontal space

    def clear_cards(self) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def get_termin_ids(self) -> list[str]:
        ids = []
        for i in range(self.layout.count()):
            item = self.layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, TerminCard):
                    ids.append(widget.termin_id)
                else:
                    child_card = widget.findChild(TerminCard)
                    if child_card:
                        ids.append(child_card.termin_id)
        return ids
