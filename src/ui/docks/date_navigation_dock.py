from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QDateEdit,
    QSizePolicy,
)
from ..components.widgets.tight_combobox import TightComboBox


class DateNavigationDock(QDockWidget):
    """
    Dock for global date/view navigation only
    """

    navPrev = Signal()
    navNext = Signal()
    previousYearToggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__("Navigation", parent)
        self.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self._syncing_navigation = False

        title_bar = QWidget(self)
        title_bar.setFixedHeight(0)
        self.setTitleBarWidget(title_bar)

        self._panel = QWidget(self)
        self._panel.setObjectName("NavigationDockPanel")
        panel_lay = QVBoxLayout(self._panel)
        panel_lay.setContentsMargins(1, 1, 1, 1)
        panel_lay.setSpacing(0)

        self._title_label = QLabel("Navigation", self._panel)
        self._title_label.setObjectName("NavigationDockTitle")
        panel_lay.addWidget(self._title_label)

        self._widget = QWidget(self._panel)
        self._widget.setObjectName("HeaderBar")
        panel_lay.addWidget(self._widget)

        headerBar = QHBoxLayout(self._widget)
        headerBar.setContentsMargins(6, 6, 6, 6)
        headerBar.setSpacing(8)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setObjectName("NavButton")
        self.prev_btn.setFixedWidth(36)
        headerBar.addWidget(self.prev_btn)

        self.next_btn = QPushButton("▶")
        self.next_btn.setObjectName("NavButton")
        self.next_btn.setFixedWidth(36)
        headerBar.addWidget(self.next_btn)

        self.previous_year_btn = QPushButton("↶")
        self.previous_year_btn.setObjectName("NavButton")
        self.previous_year_btn.setFixedWidth(36)
        self.previous_year_btn.setCheckable(True)
        self.previous_year_btn.setToolTip(
            "Vorjahr anzeigen (Strg+Alt+V). Modus in den Einstellungen: gedrückt halten oder umschalten."
        )
        headerBar.addWidget(self.previous_year_btn)

        self.view_cb = TightComboBox()
        self.view_cb.addItem("Wochen", "week")
        self.view_cb.addItem("Tag", "day")
        self.view_cb.addItem("Monat", "month")
        self.view_cb.setFixedWidth(120)
        self.view_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.view_cb)

        self.day_date = QDateEdit()
        self.day_date.setObjectName("DateEdit")
        self.day_date.setCalendarPopup(True)
        self.day_date.setDate(QDate.currentDate())
        self.day_date.setMinimumWidth(120)
        self.day_date.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        headerBar.addWidget(self.day_date)

        # week selectors
        self.week_number_cb = TightComboBox()
        self.week_number_cb.setMinimumWidth(160)
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
        self.previous_year_btn.toggled.connect(self.previousYearToggled.emit)

        self.day_date.dateChanged.connect(self._on_navigation_date_changed)

        self.week_year_cb.currentIndexChanged.connect(self._on_week_year_changed)
        self.week_number_cb.currentIndexChanged.connect(self._on_week_number_changed)

        self.month_year_cb.currentIndexChanged.connect(self._on_month_year_changed)
        self.month_name_cb.currentIndexChanged.connect(self._on_month_name_changed)

        self.setWidget(self._panel)

        self._populate_week_year_selector()
        self._populate_month_year_selector()
        self._populate_month_name_selector()

        self._sync_selectors_with_dates()
        self._on_view_change()

    def preferred_inline_width(self) -> int:
        return 560

    def _monday_of(self, date: QDate) -> QDate:
        return date.addDays(1 - date.dayOfWeek())

    def _weeks_in_iso_year(self, year: int) -> int:
        return QDate(year, 12, 28).weekNumber()[0]

    def _iso_week_start(self, year: int, week: int) -> QDate:
        jan4 = QDate(year, 1, 4)
        first_monday = jan4.addDays(1 - jan4.dayOfWeek())
        return first_monday.addDays((week - 1) * 7)

    def _week_label(self, year: int, week: int) -> str:
        start = self._iso_week_start(year, week)
        return f"KW {week:02d} ({start.toString('dd.MM.yyyy')})"

    def _month_start(self, date: QDate) -> QDate:
        return QDate(date.year(), date.month(), 1)

    def _current_week_anchor(self) -> QDate:
        return self._monday_of(self.day_date.date())

    def _current_month_anchor(self) -> QDate:
        return self._month_start(self.day_date.date())

    def _on_navigation_date_changed(self, _date: QDate) -> None:
        if self._syncing_navigation:
            return

        self._syncing_navigation = True
        try:
            self._sync_selectors_with_dates()
        finally:
            self._syncing_navigation = False

    def _populate_week_year_selector(self) -> None:
        self.week_year_cb.blockSignals(True)
        self.week_year_cb.clear()

        for year in range(2000, 2100):
            self.week_year_cb.addItem(str(year), year)

        self.week_year_cb.blockSignals(False)

    def _populate_week_number_selector(self, year: int, selected: int | None = None) -> None:
        self.week_number_cb.blockSignals(True)
        self.week_number_cb.clear()

        max_weeks = self._weeks_in_iso_year(year)

        for week in range(1, max_weeks + 1):
            self.week_number_cb.addItem(self._week_label(year, week), week)

        if selected is not None:
            idx = self.week_number_cb.findData(selected)
            if idx >= 0:
                self.week_number_cb.setCurrentIndex(idx)

        self.week_number_cb.blockSignals(False)

    def _populate_month_year_selector(self) -> None:
        self.month_year_cb.blockSignals(True)
        self.month_year_cb.clear()

        for year in range(2000, 2100):
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
        week_anchor = self._current_week_anchor()
        iso_week, iso_year = week_anchor.weekNumber()

        self.week_year_cb.blockSignals(True)
        yidx = self.week_year_cb.findData(iso_year)
        if yidx >= 0:
            self.week_year_cb.setCurrentIndex(yidx)
        self.week_year_cb.blockSignals(False)

        self._populate_week_number_selector(iso_year, iso_week)

        month_anchor = self._current_month_anchor()

        self.month_year_cb.blockSignals(True)
        midx = self.month_year_cb.findData(month_anchor.year())
        if midx >= 0:
            self.month_year_cb.setCurrentIndex(midx)
        self.month_year_cb.blockSignals(False)

        self._populate_month_name_selector(month_anchor.month())

    def _on_week_year_changed(self, idx: int) -> None:
        year = self.week_year_cb.itemData(idx)
        if not isinstance(year, int):
            return

        week = self.week_number_cb.currentData()
        if not isinstance(week, int):
            week = 1

        max_weeks = self._weeks_in_iso_year(year)
        week = min(week, max_weeks)

        self.day_date.setDate(self._iso_week_start(year, week))

    def _on_week_number_changed(self, idx: int) -> None:
        year = self.week_year_cb.currentData()
        week = self.week_number_cb.itemData(idx)

        if not isinstance(year, int) or not isinstance(week, int):
            return

        self.day_date.setDate(self._iso_week_start(year, week))

    def _on_month_year_changed(self, idx: int) -> None:
        year = self.month_year_cb.itemData(idx)
        month = self.month_name_cb.currentData()

        if not isinstance(year, int):
            return
        if not isinstance(month, int):
            month = 1

        self.day_date.setDate(QDate(year, month, 1))

    def _on_month_name_changed(self, idx: int) -> None:
        month = self.month_name_cb.itemData(idx)
        year = self.month_year_cb.currentData()

        if not isinstance(month, int) or not isinstance(year, int):
            return

        self.day_date.setDate(QDate(year, month, 1))

    def _on_view_change(self, *_) -> None:
        view = str(self.view_cb.currentData())

        self.day_date.setVisible(view == "day")

        self.week_number_cb.setVisible(view == "week")
        self.week_year_cb.setVisible(view == "week")

        self.month_name_cb.setVisible(view == "month")
        self.month_year_cb.setVisible(view == "month")

        self._sync_selectors_with_dates()
