from PySide6.QtCore import QDate, QTimer
from PySide6.QtWidgets import QDateEdit

class NullableDateEdit(QDateEdit):
    def __init__(self, unassigned: QDate, parent=None):
        super().__init__(parent)
        self._unassigned = unassigned

        self.setCalendarPopup(True)

        # sentinel behavior
        self.setMinimumDate(self._unassigned)
        self.setSpecialValueText("Kein Datum zugewiesen")
        self.setDate(self._unassigned)

    def showPopup(self):
        super().showPopup()

        # after popup is actually constructed/shown
        QTimer.singleShot(0, self._fix_popup_page)

    def _fix_popup_page(self):
        if self.date() != self._unassigned:
            return
        cal = self.calendarWidget()
        if not cal:
            return

        today = QDate.currentDate()
        cal.setSelectedDate(today)
        cal.setCurrentPage(today.year(), today.month())
