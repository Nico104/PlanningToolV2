from PySide6.QtCore import Qt, Signal, QPoint, QTimer, QRect, QMimeData
from PySide6.QtGui import QDropEvent, QDragMoveEvent, QPainter, QPen, QDrag
from PySide6.QtWidgets import QTableWidget, QAbstractItemView, QTableWidgetSelectionRange

import math

from ...utils.qss_tokens import qss_color
from .time_grid_drag_preview_overlay import TimeGridDragPreviewOverlay


class TimeGridDropTable(QTableWidget):
    """
    A QTableWidget subclass that acts as a drop target for TerminCard drags.

    During a drag, it snaps the hover position to the grid and paints a live
    preview block (filled with the Termin type color, or red on conflict).
    All context-specific knowledge (duration, color, text, conflict checking)
    is injected via provider callbacks so this widget stays generic.

    design decisions:
    - MIME type 'application/termin-id' carries just the Termin ID as UTF-8 bytes.
      The actual Termin object is never serialized into the drag; it is looked up
      from the shared state via the injected providers.
    - Span calculation: duration_minutes / slot_minutes = number of rows
      the preview block should cover. This mirrors how TerminCards are placed.
    - Conflict checking is send to a callback so views can decide whether
      live preview checks should run for the current settings.
    - Auto-scroll: a 25 ms QTimer scrolls the viewport vertically when the cursor
      is near the top/bottom edge, enabling drags to times that are not visible.
    """

    terminDropped = Signal(str, int, int)

    def __init__(self, rows: int = 0, cols: int = 0, parent=None):
        super().__init__(rows, cols, parent)

        self.setAcceptDrops(True)

        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._read_only = False

        # Track current hover target during drag
        self._hover_row = -1
        self._hover_col = -1
        self._hover_span = 1
        self._hover_termin_id = None
        self._conflict_checker = None
        self._hover_has_conflict = False
        self._hover_conflict_text = ""

        # preview config
        self._duration_provider = None
        self._color_provider = None
        self._text_provider = None
        self._slot_minutes = 30

        # Edge auto-scroll while dragging.
        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(25)
        self._auto_scroll_timer.timeout.connect(self._auto_scroll_tick)
        self._last_drag_pos: QPoint | None = None

        self._drag_preview_overlay = TimeGridDragPreviewOverlay(self.viewport())
        self._drag_preview_overlay.setGeometry(self.viewport().rect())
        self.verticalScrollBar().valueChanged.connect(
            lambda _value: self._sync_drag_preview_overlay()
        )
        self.horizontalScrollBar().valueChanged.connect(
            lambda _value: self._sync_drag_preview_overlay()
        )

    # Drag and Drop

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        self.setAcceptDrops(not self._read_only)
        self.setDragEnabled(not self._read_only)
        self.setDragDropMode(
            QAbstractItemView.NoDragDrop if self._read_only else QAbstractItemView.DragDrop
        )
        if self._read_only:
            self._auto_scroll_timer.stop()
            self._set_hover(-1, -1)
        self.viewport().update()

    # Accept valid Termin drags and start edge auto-scroll
    def dragEnterEvent(self, e):
        if self._read_only:
            e.ignore()
            return
        if e.mimeData().hasText():
            e.acceptProposedAction()
            self._auto_scroll_timer.start()
        else:
            e.ignore()

    # Stop auto-scroll and clear hover preview when drag leaves the table
    def dragLeaveEvent(self, e):
        self._auto_scroll_timer.stop()
        self._set_hover(-1, -1)
        super().dragLeaveEvent(e)

    # Update hover preview while dragging over the grid (does the snapping to the grid)
    def dragMoveEvent(self, e: QDragMoveEvent):
        if self._read_only:
            e.ignore()
            return
        if not e.mimeData().hasText():
            e.ignore()
            return

        termin_id = e.mimeData().text().strip()
        self._hover_termin_id = termin_id
        duration = 0
        if self._duration_provider:
            try:
                duration = int(self._duration_provider(termin_id) or 0)
            except Exception:
                duration = 0
        if duration <= 0:
            duration = self._slot_minutes
        span = max(1, int(math.ceil(duration / max(1, self._slot_minutes))))

        pos = e.position().toPoint()
        self._last_drag_pos = pos

        r = self.rowAt(pos.y())
        c = self.columnAt(pos.x())
        if r < 0 or c < 0:
            self._set_hover(-1, -1)
            e.ignore()
            return

        self._set_hover(r, c, span)
        e.acceptProposedAction()

    # emit termin + target cell, then clear hover/scroll.
    def dropEvent(self, e: QDropEvent):
        if self._read_only:
            e.ignore()
            return
        md = e.mimeData()
        if not md.hasText():
            e.ignore()
            return

        termin_id = md.text().strip()

        pos: QPoint = e.position().toPoint()
        r = self.rowAt(pos.y())
        c = self.columnAt(pos.x())
        if r < 0 or c < 0:
            e.ignore()
            return

        self._auto_scroll_timer.stop()
        self._set_hover(-1, -1, 1)

        self.terminDropped.emit(termin_id, r, c)
        e.acceptProposedAction()

    def _set_hover(self, r: int, c: int, span: int = 1):
        """
        Update the hover position and refresh the drag preview.

        If the mouse is over a valid cell, check whether dropping the Termin here
        would cause a conflict, so the preview can show the right state.
        """
        if r == self._hover_row and c == self._hover_col and span == self._hover_span:
            return
        self._hover_row, self._hover_col, self._hover_span = r, c, span

        if r >= 0 and c >= 0 and self._conflict_checker and self._hover_termin_id:
            try:
                result = self._conflict_checker(self._hover_termin_id, r, c)
                if isinstance(result, str):
                    self._hover_conflict_text = result.strip()
                    self._hover_has_conflict = bool(self._hover_conflict_text)
                else:
                    self._hover_conflict_text = "Konflikt" if result else ""
                    self._hover_has_conflict = bool(result)
            except Exception:
                self._hover_has_conflict = False
                self._hover_conflict_text = ""
        else:
            self._hover_has_conflict = False
            self._hover_conflict_text = ""

        if r >= 0 and c >= 0:
            self.clearSelection()
            r_end = min(self.rowCount() - 1, r + max(1, span) - 1)
            self.setRangeSelected(QTableWidgetSelectionRange(r, c, r_end, c), True)
        else:
            self.clearSelection()
            self.setCurrentCell(-1, -1)

        self._sync_drag_preview_overlay()
        self.viewport().update()

    def _hover_preview_rect(self) -> QRect:
        if self._hover_row < 0 or self._hover_col < 0:
            return QRect()

        x = self.columnViewportPosition(self._hover_col)
        y = self.rowViewportPosition(self._hover_row)
        w = self.columnWidth(self._hover_col)
        h = self.rowHeight(self._hover_row)
        rect = QRect(x, y, w, h)

        end_row = min(self.rowCount() - 1, self._hover_row + max(1, self._hover_span) - 1)
        if end_row != self._hover_row:
            bottom_y = self.rowViewportPosition(end_row)
            bottom_h = self.rowHeight(end_row)
            rect = rect.united(QRect(x, bottom_y, w, bottom_h))

        return rect

    def _hover_preview_text(self) -> str:
        if not self._text_provider or not self._hover_termin_id:
            return ""
        try:
            return str(self._text_provider(self._hover_termin_id) or "")
        except Exception:
            return ""

    def _hover_preview_fill_color(self):
        if self._hover_has_conflict:
            return qss_color("planner-drop-conflict-preview-bg")

        fill_color = qss_color("planner-focus-border")
        if self._color_provider and self._hover_termin_id:
            try:
                fill_color = self._color_provider(self._hover_termin_id)
            except Exception:
                pass
        return fill_color

    def _sync_drag_preview_overlay(self) -> None:
        if self._hover_row < 0 or self._hover_col < 0:
            self._drag_preview_overlay.clear_preview()
            return

        self._drag_preview_overlay.setGeometry(self.viewport().rect())
        self._drag_preview_overlay.set_preview(
            rect=self._hover_preview_rect(),
            text=self._hover_preview_text(),
            fill_color=self._hover_preview_fill_color(),
            has_conflict=self._hover_has_conflict,
            conflict_text=self._hover_conflict_text,
        )

    def _auto_scroll_tick(self):
        """
        Called by the auto-scroll timer during a drag.
        """
        if self._last_drag_pos is None:
            return

        margin = 32
        step_px = 12
        dy = 0
        vp = self.viewport().rect()
        p = self._last_drag_pos

        if p.y() < vp.top() + margin:
            dy = -1
        elif p.y() > vp.bottom() - margin:
            dy = 1

        if p.x() < vp.left() + margin:
            dx = -1
        elif p.x() > vp.right() - margin:
            dx = 1

        if dy:
            sb = self.verticalScrollBar()
            old_value = sb.value()
            sb.setValue(old_value + dy * step_px)
            if sb.value() != old_value:
                r = self.rowAt(p.y())
                c = self.columnAt(p.x())
                if r >= 0 and c >= 0:
                    self._set_hover(r, c, self._hover_span)
                else:
                    self._sync_drag_preview_overlay()

    def set_duration_preview_provider(self, provider, slot_minutes: int) -> None:
        self._duration_provider = provider
        self._slot_minutes = max(1, int(slot_minutes))

    def set_color_provider(self, provider) -> None:
        self._color_provider = provider

    def set_text_provider(self, provider) -> None:
        self._text_provider = provider

    def set_conflict_checker(self, checker) -> None:
        self._conflict_checker = checker

    def paintEvent(self, e):
        """
        Paint the table and grid lines. The live drag preview is painted by
        TimeGridDragPreviewOverlay so it can appear above TerminCard widgets.
        """
        super().paintEvent(e)
        self._paint_time_grid_lines()

    def _paint_time_grid_lines(self) -> None:
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, False)

        vertical_pen = QPen(qss_color("planner-grid-vertical"))
        vertical_pen.setWidth(1)
        vertical_pen.setCosmetic(True)
        painter.setPen(vertical_pen)
        top = 0
        bottom = self.viewport().height()
        for col in range(1, self.columnCount()):
            x = self.columnViewportPosition(col)
            if x <= 0:
                continue
            painter.drawLine(x, top, x, bottom)

        half_hour_pen = QPen(qss_color("planner-grid-half-hour"))
        half_hour_pen.setWidth(1)
        half_hour_pen.setCosmetic(True)
        half_hour_pen.setDashPattern([8, 5])

        hour_pen = QPen(qss_color("planner-grid-hour"))
        hour_pen.setWidth(1)
        hour_pen.setCosmetic(True)
        left = 0
        right = self.viewport().width()

        painter.setPen(half_hour_pen)
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            text = item.text().strip() if item else ""
            if not text.endswith(":30"):
                continue
            y = self.rowViewportPosition(row)
            if y <= 0:
                continue
            painter.drawLine(left, y, right, y)

        painter.setPen(hour_pen)
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            text = item.text().strip() if item else ""
            if not text.endswith(":00"):
                continue
            y = self.rowViewportPosition(row)
            if y <= 0:
                continue
            painter.drawLine(left, y, right, y)

        painter.end()

    def startDrag(self, supportedActions):
        """
        Initiate a drag from a cell that contains a TerminCard.

        The cell widget is expected to expose `termin_id` directly (single TerminCard).
        The Termin ID is encoded as UTF-8 bytes and stored under the custom MIME type so the drop
        target can look up the full Termin from the shared application state.
        """
        if self._read_only:
            return

        current_row = self.currentRow()
        current_col = self.currentColumn()

        if current_row < 0 or current_col < 0:
            return

        cell_widget = self.cellWidget(current_row, current_col)
        if cell_widget and hasattr(cell_widget, "termin_id"):
            termin_id = cell_widget.termin_id
        else:
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(termin_id))
        drag.setMimeData(mime)

        drag.exec(Qt.MoveAction)
