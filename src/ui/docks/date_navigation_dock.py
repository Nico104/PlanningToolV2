from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QDateEdit,
    QSizePolicy,
)

from ..components.widgets.tight_combobox import TightComboBox


class DateNavigationDock(QDockWidget):
    """
    Dock for global date/view navigation only.
    """

    viewChanged = Signal(str)
    navPrev = Signal()
    navNext = Signal()
    dayDateChanged = Signal(QDate)
    weekFromChanged = Signal(QDate)

    def __init__(self, parent=None):
        super().__init__("Navigation", parent)
        self.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)

        self._widget = QWidget(self)
        self._widget.setObjectName("HeaderBar")

        headerBar = QHBoxLayout(self._widget)
        headerBar.setContentsMargins(6, 6, 6, 6)
        headerBar.setSpacing(8)

        self.view_cb = TightComboBox()
        self.view_cb.addItem("Wochen", "week")
        self.view_cb.addItem("Tag", "day")
        self.view_cb.addItem("Monat", "month")
        self.view_cb.setFixedWidth(100)
        self.view_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.view_cb)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setObjectName("NavButton")
        self.prev_btn.setFixedWidth(36)
        headerBar.addWidget(self.prev_btn)

        self.next_btn = QPushButton("▶")
        self.next_btn.setObjectName("NavButton")
        self.next_btn.setFixedWidth(36)
        headerBar.addWidget(self.next_btn)

        self.day_date = QDateEdit()
        self.day_date.setObjectName("DateEdit")
        self.day_date.setCalendarPopup(True)
        self.day_date.setDate(QDate.currentDate())
        self.day_date.setMinimumWidth(120)
        self.day_date.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        headerBar.addWidget(self.day_date)

        # hidden backing date for week/month navigation compatibility
        self.week_from = QDateEdit()
        self.week_from.setObjectName("DateEdit")
        self.week_from.setCalendarPopup(True)
        self.week_from.setDate(self._monday_of(QDate.currentDate()))
        self.week_from.setVisible(False)
        headerBar.addWidget(self.week_from)

        # week selectors
        self.week_number_cb = TightComboBox()
        self.week_number_cb.setMinimumWidth(90)
        self.week_number_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.week_number_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.week_number_cb)

        self.week_year_cb = TightComboBox()
        self.week_year_cb.setMinimumWidth(100)
        self.week_year_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.week_year_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.week_year_cb)

        # month selectors
        self.month_name_cb = TightComboBox()
        self.month_name_cb.setMinimumWidth(130)
        self.month_name_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.month_name_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.month_name_cb)

        self.month_year_cb = TightComboBox()
        self.month_year_cb.setMinimumWidth(100)
        self.month_year_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.month_year_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.month_year_cb)

        self.view_cb.currentIndexChanged.connect(self._on_view_change)

        self.prev_btn.clicked.connect(self.navPrev.emit)
        self.next_btn.clicked.connect(self.navNext.emit)

        self.day_date.dateChanged.connect(self.dayDateChanged.emit)
        self.week_from.dateChanged.connect(self.weekFromChanged.emit)

        self.week_from.dateChanged.connect(lambda *_: self._sync_selectors_with_dates())
        self.day_date.dateChanged.connect(lambda *_: self._sync_selectors_with_dates())

        self.week_year_cb.currentIndexChanged.connect(self._on_week_year_changed)
        self.week_number_cb.currentIndexChanged.connect(self._on_week_number_changed)

        self.month_year_cb.currentIndexChanged.connect(self._on_month_year_changed)
        self.month_name_cb.currentIndexChanged.connect(self._on_month_name_changed)

        self.setWidget(self._widget)

        self._populate_week_year_selector()
        self._populate_month_year_selector()
        self._populate_month_name_selector()

        self._sync_selectors_with_dates()
        self._on_view_change()

    def _monday_of(self, date: QDate) -> QDate:
        return date.addDays(1 - date.dayOfWeek())

    def _weeks_in_iso_year(self, year: int) -> int:
        return QDate(year, 12, 28).weekNumber()[0]

    def _iso_week_start(self, year: int, week: int) -> QDate:
        jan4 = QDate(year, 1, 4)
        first_monday = jan4.addDays(1 - jan4.dayOfWeek())
        return first_monday.addDays((week - 1) * 7)

    def _populate_week_year_selector(self) -> None:
        self.week_year_cb.blockSignals(True)
        self.week_year_cb.clear()

        current = QDate.currentDate().year()
        for year in range(current - 2, current + 4):
            self.week_year_cb.addItem(str(year), year)

        self.week_year_cb.blockSignals(False)

    def _populate_week_number_selector(self, year: int, selected: int | None = None) -> None:
        self.week_number_cb.blockSignals(True)
        self.week_number_cb.clear()

        max_weeks = self._weeks_in_iso_year(year)

        for week in range(1, max_weeks + 1):
            self.week_number_cb.addItem(f"KW {week:02d}", week)

        if selected is not None:
            idx = self.week_number_cb.findData(selected)
            if idx >= 0:
                self.week_number_cb.setCurrentIndex(idx)

        self.week_number_cb.blockSignals(False)

    def _populate_month_year_selector(self) -> None:
        self.month_year_cb.blockSignals(True)
        self.month_year_cb.clear()

        current = QDate.currentDate().year()
        for year in range(current - 2, current + 4):
            self.month_year_cb.addItem(str(year), year)

        self.month_year_cb.blockSignals(False)

    def _populate_month_name_selector(self, selected: int | None = None) -> None:
        self.month_name_cb.blockSignals(True)
        self.month_name_cb.clear()

        for m in range(1, 13):
            self.month_name_cb.addItem(QDate(2000, m, 1).toString("MMMM"), m)

        if selected is not None:
            idx = self.month_name_cb.findData(selected)
            if idx >= 0:
                self.month_name_cb.setCurrentIndex(idx)

        self.month_name_cb.blockSignals(False)

    def _sync_selectors_with_dates(self) -> None:
        d = self.week_from.date()

        iso_week, iso_year = d.weekNumber()

        self.week_year_cb.blockSignals(True)
        yidx = self.week_year_cb.findData(iso_year)
        if yidx >= 0:
            self.week_year_cb.setCurrentIndex(yidx)
        self.week_year_cb.blockSignals(False)

        self._populate_week_number_selector(iso_year, iso_week)

        self.month_year_cb.blockSignals(True)
        midx = self.month_year_cb.findData(d.year())
        if midx >= 0:
            self.month_year_cb.setCurrentIndex(midx)
        self.month_year_cb.blockSignals(False)

        self._populate_month_name_selector(d.month())

    def _on_week_year_changed(self, idx: int) -> None:
        year = self.week_year_cb.itemData(idx)
        if not isinstance(year, int):
            return

        week = self.week_number_cb.currentData()
        if not isinstance(week, int):
            week = 1

        max_weeks = self._weeks_in_iso_year(year)
        week = min(week, max_weeks)

        monday = self._iso_week_start(year, week)
        self.week_from.setDate(monday)

    def _on_week_number_changed(self, idx: int) -> None:
        year = self.week_year_cb.currentData()
        week = self.week_number_cb.itemData(idx)

        if not isinstance(year, int) or not isinstance(week, int):
            return

        monday = self._iso_week_start(year, week)
        self.week_from.setDate(monday)

    def _on_month_year_changed(self, idx: int) -> None:
        year = self.month_year_cb.itemData(idx)
        month = self.month_name_cb.currentData()

        if not isinstance(year, int):
            return
        if not isinstance(month, int):
            month = 1

        self.week_from.setDate(QDate(year, month, 1))

    def _on_month_name_changed(self, idx: int) -> None:
        month = self.month_name_cb.itemData(idx)
        year = self.month_year_cb.currentData()

        if not isinstance(month, int) or not isinstance(year, int):
            return

        self.week_from.setDate(QDate(year, month, 1))

    def _on_view_change(self, *_) -> None:
        view = str(self.view_cb.currentData())

        self.day_date.setVisible(view == "day")

        self.week_number_cb.setVisible(view == "week")
        self.week_year_cb.setVisible(view == "week")

        self.month_name_cb.setVisible(view == "month")
        self.month_year_cb.setVisible(view == "month")

        self._sync_selectors_with_dates()
        self.viewChanged.emit(view)