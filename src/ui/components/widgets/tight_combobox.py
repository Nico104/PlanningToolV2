from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QComboBox, QStyledItemDelegate, QFrame, QListView

from ...utils.qss_tokens import qss_token


class _TightDelegate(QStyledItemDelegate):
    """Item delegate that reduces row height in the combo popup."""

    def sizeHint(self, option, index):
        sz = super().sizeHint(option, index)
        sz.setHeight(max(20, sz.height() - 4))
        return sz


class TightComboBox(QComboBox):
    """Custom combo box with auto-sized popup, custom styling, and keyboard letter-jump"""

    def keyPressEvent(self, event):
        # Jump to the first item whose text starts with the typed letter.
        key = event.text()
        if key and len(key) == 1 and key.isprintable():
            key_lower = key.lower()
            for i in range(self.count()):
                item_text = self.itemText(i)
                if item_text.lower().startswith(key_lower):
                    self.setCurrentIndex(i)
                    return
        super().keyPressEvent(event)

    def __init__(self, parent=None, *, compact_height: int = 32, min_popup_width: int = 180):
        super().__init__(parent)
        self._compact_height = compact_height
        self._min_popup_width = min_popup_width


        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        
        self.setMinimumHeight(self._compact_height)

        self.setItemDelegate(_TightDelegate(self))
        self._apply_popup_window_flags()
        
        self.setView(QListView())


    def _fit_popup_height(self):
        v = self.view()
        n = min(self.count(), self.maxVisibleItems())
        if n <= 0:
            return

        row_h = v.sizeHintForRow(0)
        if row_h <= 0:
            row_h = 28

        extra = 12
        v.setFixedHeight(row_h * n + extra)





    def _apply_popup_window_flags(self):
        v = self.view()
        w = v.window()

        w.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        
        w.setAttribute(Qt.WA_TranslucentBackground, True)
        w.setStyleSheet("background: transparent;")

        v.setFrameShape(QFrame.NoFrame)
        v.setContentsMargins(0, 0, 0, 0)
        v.setViewportMargins(0, 0, 0, 0)

        v.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        v.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)



    # def wheelEvent(self, event):
    #     # Prevent accidental changes while scrolling
    #     event.ignore()

    def showPopup(self):
        self._apply_popup_window_flags()
        self._sync_popup_styling()
        self._fit_popup_width()
        self._fit_popup_height()  
        super().showPopup()

        # Ensure the popup window tightly wraps the view and stays anchored to the combo box.
        # Qt's automatic placement can drift when this custom popup is used inside nested dialogs.
        try:
            v = self.view()
            w = v.window()
            w.setFixedSize(v.width(), v.height())
            self._position_popup_window()
        except Exception:
            pass

    def _position_popup_window(self):
        v = self.view()
        w = v.window()
        popup_w = max(v.width(), self.width())
        popup_h = max(1, v.height())

        screen = QApplication.screenAt(self.mapToGlobal(QPoint(0, 0)))
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return

        geo = screen.availableGeometry()
        below = self.mapToGlobal(QPoint(0, self.height()))
        above = self.mapToGlobal(QPoint(0, -popup_h))

        x = below.x()
        x = max(geo.left(), min(x, geo.right() - popup_w + 1))

        if below.y() + popup_h <= geo.bottom():
            y = below.y()
        elif above.y() >= geo.top():
            y = above.y()
        else:
            y = max(geo.top(), min(below.y(), geo.bottom() - popup_h + 1))

        w.move(x, y)


    def _fit_popup_width(self):
        fm = QFontMetrics(self.font())

        longest = 0
        for i in range(self.count()):
            t = self.itemText(i)
            longest = max(longest, fm.horizontalAdvance(t))

        padding = 52
        target = longest + padding
        target = max(self._min_popup_width, target)

        self.view().setMinimumWidth(target)
        self.view().setFixedWidth(target)

    def sizeHint(self) -> QSize:
        s = super().sizeHint()
        s.setHeight(self._compact_height)
        return s

    def _sync_popup_styling(self):
        v = self.view()
        w = v.window()
        popup_bg = qss_token("popup-bg")
        popup_border = qss_token("popup-border")
        selection_bg = qss_token("popup-selection-bg")
        popup_text = qss_token("popup-text")
        selection_text = qss_token("popup-selection-text")
        hover_bg = qss_token("popup-hover-bg")

        w.setAttribute(Qt.WA_StyledBackground, True)
        w.setStyleSheet(f"""
            /* This is the container behind the list */
            background: {popup_bg};
            border: 1px solid {popup_border};
            border-radius: 1px;
        """)

        lay = w.layout()
        if lay:
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            
        v.setStyleSheet(f"""
            QAbstractItemView {{
                background: transparent;
                border: none;
                outline: 0;
                    padding: 0px; /* remove inner padding so items align with popup edges */
                selection-background-color: {selection_bg};
                selection-color: {selection_text};
            }}

            QAbstractItemView::item {{
                /* match header combo padding vertically (6px) so selected row aligns */
                    padding: 6px 12px;
                    margin: 0px; /* remove item margin so selection fills width */
                border-radius: 4px;
                color: {popup_text};
            }}

            QAbstractItemView::item:hover {{
                background: {hover_bg};
            }}

            QAbstractItemView::item:selected,
            QAbstractItemView::item:!active:selected {{
                background: {selection_bg};
                color: {selection_text};
            }}
        """)




