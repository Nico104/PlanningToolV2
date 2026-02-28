from PySide6.QtCore import Qt, Signal, QPoint, QTimer, QMimeData
from PySide6.QtGui import QDropEvent, QDragMoveEvent
from PySide6.QtWidgets import QTableWidget, QAbstractItemView, QTableWidgetSelectionRange


class MonthDropTable(QTableWidget):
    """Simpler drop-capable table for month grid.

    Emits `terminDropped(termin_id, row, col)` when a `Termin` is dropped
    onto a month cell. Provides a basic hover selection visual.
    """

    terminDropped = Signal(str, int, int)
    MIME = "application/termin-id"

    def __init__(self, rows: int, cols: int, parent=None):
        super().__init__(rows, cols, parent)

        self.setAcceptDrops(True)

        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

        self._hover_row = -1
        self._hover_col = -1

        # auto-scroll for large month tables (keeps behavior similar to week)
        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(25)
        self._last_drag_pos: QPoint | None = None
        self._auto_scroll_timer.timeout.connect(self._auto_scroll_tick)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(self.MIME):
            e.acceptProposedAction()
            self._auto_scroll_timer.start()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self._auto_scroll_timer.stop()
        self._set_hover(-1, -1)
        super().dragLeaveEvent(e)

    def dragMoveEvent(self, e: QDragMoveEvent):
        if not e.mimeData().hasFormat(self.MIME):
            e.ignore()
            return

        self._last_drag_pos = e.position().toPoint()

        r = self.rowAt(self._last_drag_pos.y())
        c = self.columnAt(self._last_drag_pos.x())
        if r < 0 or c < 0:
            self._set_hover(-1, -1)
            e.ignore()
            return

        self._set_hover(r, c)
        e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        md = e.mimeData()
        if not md.hasFormat(self.MIME):
            e.ignore()
            return

        termin_id = bytes(md.data(self.MIME)).decode("utf-8").strip()

        pos = e.position().toPoint()
        r = self.rowAt(pos.y())
        c = self.columnAt(pos.x())
        if r < 0 or c < 0:
            e.ignore()
            return

        self._auto_scroll_timer.stop()
        self._set_hover(-1, -1)

        self.terminDropped.emit(termin_id, r, c)
        e.acceptProposedAction()

    def _set_hover(self, r: int, c: int):
        if r == self._hover_row and c == self._hover_col:
            return
        self._hover_row, self._hover_col = r, c

        if r >= 0 and c >= 0:
            self.clearSelection()
            self.setRangeSelected(QTableWidgetSelectionRange(r, c, r, c), True)
        else:
            self.clearSelection()
            self.setCurrentCell(-1, -1)

        self.viewport().update()

    def _auto_scroll_tick(self):
        if self._last_drag_pos is None:
            return

        margin = 20
        dy = 0
        dx = 0
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
            sb.setValue(sb.value() + dy * 2)
        if dx:
            sb = self.horizontalScrollBar()
            sb.setValue(sb.value() + dx * 6)
