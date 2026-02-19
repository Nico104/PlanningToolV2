from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate, QFrame, QApplication, QListView


class _TightDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        sz = super().sizeHint(option, index)
        sz.setHeight(max(24, sz.height() - 2))
        return sz


class TightComboBox(QComboBox):
    def keyPressEvent(self, event):
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
        w.setStyleSheet("background: transparent;")   # only window, not the view

        v.setFrameShape(QFrame.NoFrame)
        v.setContentsMargins(0, 0, 0, 0)
        v.setViewportMargins(0, 0, 0, 0)

        v.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        v.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)



    # def wheelEvent(self, event):
    #     # Prevent accidental changes while scrolling
    #     event.ignore()

    def showPopup(self):
        self._apply_popup_window_flags()
        self._sync_popup_styling()
        self._fit_popup_width()
        self._fit_popup_height()  
        super().showPopup()


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

        w.setAttribute(Qt.WA_StyledBackground, True)
        w.setStyleSheet("""
            /* This is the container behind the list */
            background: #f8f8f8;
            border: 1px solid #4a4a4a;
            border-radius: 1px;
        """)

        lay = w.layout()
        if lay:
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            
        v.setStyleSheet("""
            QAbstractItemView {
                background: transparent;
                border: none;
                outline: 0;
                padding: 6px; /* inner padding inside the rounded window */
                selection-background-color: #4f86ff;
                selection-color: white;
            }

            QAbstractItemView::item {
                padding: 7px 12px;
                margin: 2px;
                border-radius: 4px;
                color: black;
            }

            QAbstractItemView::item:hover {
                background: rgba(255,255,255,14%);
            }

            QAbstractItemView::item:selected,
            QAbstractItemView::item:!active:selected {
                background: #4f86ff;
                color: white;
            }

            QScrollBar:vertical {
                width: 10px;
                background: transparent;
                margin: 6px 2px 6px 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,35%);
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)




