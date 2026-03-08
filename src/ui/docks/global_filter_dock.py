from typing import Optional
import os
import json

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
from ...core.states import FilterState


class GlobalFilterDock(QDockWidget):
    """
    Dockable Global Header Bar
    """

    filtersChanged = Signal(object)
    viewChanged = Signal(str)
    navPrev = Signal()
    navNext = Signal()
    dayDateChanged = Signal(QDate)
    weekFromChanged = Signal(QDate)

    def __init__(self, parent=None):
        super().__init__("Filter", parent)
        self.setAllowedAreas(Qt.AllDockWidgetAreas)

        self._widget = QWidget(self)
        self._widget.setObjectName("HeaderBar")

        headerBar = QHBoxLayout(self._widget)
        headerBar.setContentsMargins(6, 6, 6, 6)
        headerBar.setSpacing(8)

        # --- Filters ----------------------------------------------------------

        self.fachrichtung_cb = TightComboBox()
        self.fachrichtung_cb.setToolTip("Fachrichtung filter")
        self.fachrichtung_cb.setMinimumWidth(120)
        self.fachrichtung_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.fachrichtung_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.fachrichtung_cb)

        self.semester_cb = TightComboBox()
        self.semester_cb.setToolTip("Semester filter")
        self.semester_cb.setMinimumWidth(110)
        self.semester_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.semester_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.semester_cb)

        self.lva_cb = TightComboBox()
        self.lva_cb.setToolTip("LVA filter")
        self.lva_cb.setMinimumWidth(140)
        self.lva_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.lva_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.lva_cb)

        self.dozent_cb = TightComboBox()
        self.dozent_cb.setToolTip("Dozent filter")
        self.dozent_cb.setMinimumWidth(120)
        self.dozent_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.dozent_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.dozent_cb)

        self.typ_cb = TightComboBox()
        self.typ_cb.setToolTip("Typ filter")
        self.typ_cb.setMinimumWidth(110)
        self.typ_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.typ_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.typ_cb)

        self.room_cb = TightComboBox()
        self.room_cb.setToolTip("Raum filter")
        self.room_cb.setMinimumWidth(120)
        self.room_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.room_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.room_cb)

        self.geplante_semester_cb = TightComboBox()
        self.geplante_semester_cb.setToolTip("Geplantes Semester (LVA) filter")
        self.geplante_semester_cb.setMinimumWidth(150)
        self.geplante_semester_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.geplante_semester_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.geplante_semester_cb)

        # --- View -------------------------------------------------------------

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

        # --- Day selector -----------------------------------------------------

        self.day_date = QDateEdit()
        self.day_date.setObjectName("DateEdit")
        self.day_date.setCalendarPopup(True)
        self.day_date.setDate(QDate.currentDate())
        self.day_date.setMinimumWidth(120)
        self.day_date.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        headerBar.addWidget(self.day_date)

        # Hidden planner backing date
        self.week_from = QDateEdit()
        self.week_from.setObjectName("DateEdit")
        self.week_from.setCalendarPopup(True)
        self.week_from.setDate(self._monday_of(QDate.currentDate()))
        self.week_from.setVisible(False)
        headerBar.addWidget(self.week_from)

        # --- Week selector (KW + Year) ---------------------------------------

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

        # --- Month selector (Month + Year) -----------------------------------

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

        # --- Signals ----------------------------------------------------------

        self.fachrichtung_cb.currentIndexChanged.connect(self._on_change)
        self.semester_cb.currentIndexChanged.connect(self._on_change)
        self.lva_cb.currentIndexChanged.connect(self._on_change)
        self.dozent_cb.currentIndexChanged.connect(self._on_change)
        self.typ_cb.currentIndexChanged.connect(self._on_change)
        self.room_cb.currentIndexChanged.connect(self._on_change)
        self.geplante_semester_cb.currentIndexChanged.connect(self._on_change)

        self.view_cb.currentIndexChanged.connect(self._on_view_change)

        self.prev_btn.clicked.connect(self.navPrev.emit)
        self.next_btn.clicked.connect(self.navNext.emit)

        self.day_date.dateChanged.connect(self.dayDateChanged.emit)
        self.week_from.dateChanged.connect(self.weekFromChanged.emit)

        # keep visible selectors synced when hidden backing date changes
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

    # ------------------------------------------------------------------------

    def _monday_of(self, date: QDate) -> QDate:
        return date.addDays(1 - date.dayOfWeek())

    def _weeks_in_iso_year(self, year: int) -> int:
        return QDate(year, 12, 28).weekNumber()[0]

    def _iso_week_start(self, year: int, week: int) -> QDate:
        jan4 = QDate(year, 1, 4)
        first_monday = jan4.addDays(1 - jan4.dayOfWeek())
        return first_monday.addDays((week - 1) * 7)

    # ------------------------------------------------------------------------

    def _populate_week_year_selector(self) -> None:
        self.week_year_cb.blockSignals(True)
        self.week_year_cb.clear()

        current = QDate.currentDate().year()
        for year in range(current - 2, current + 4):
            self.week_year_cb.addItem(str(year), year)

        self.week_year_cb.blockSignals(False)

    def _populate_week_number_selector(self, year: int, selected: Optional[int] = None) -> None:
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

    # ------------------------------------------------------------------------

    def _populate_month_year_selector(self) -> None:
        self.month_year_cb.blockSignals(True)
        self.month_year_cb.clear()

        current = QDate.currentDate().year()
        for year in range(current - 2, current + 4):
            self.month_year_cb.addItem(str(year), year)

        self.month_year_cb.blockSignals(False)

    def _populate_month_name_selector(self, selected: Optional[int] = None) -> None:
        self.month_name_cb.blockSignals(True)
        self.month_name_cb.clear()

        for m in range(1, 13):
            self.month_name_cb.addItem(QDate(2000, m, 1).toString("MMMM"), m)

        if selected is not None:
            idx = self.month_name_cb.findData(selected)
            if idx >= 0:
                self.month_name_cb.setCurrentIndex(idx)

        self.month_name_cb.blockSignals(False)

    # ------------------------------------------------------------------------

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

    # ------------------------------------------------------------------------

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

    # ------------------------------------------------------------------------

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

    # ------------------------------------------------------------------------

    def _on_view_change(self, *_) -> None:
        view = str(self.view_cb.currentData())

        self.day_date.setVisible(view == "day")

        self.week_number_cb.setVisible(view == "week")
        self.week_year_cb.setVisible(view == "week")

        self.month_name_cb.setVisible(view == "month")
        self.month_year_cb.setVisible(view == "month")

        self._sync_selectors_with_dates()
        self.viewChanged.emit(view)

    # ------------------------------------------------------------------------

    def _on_change(self, *_) -> None:
        fs = FilterState(
            fachrichtung=self.fachrichtung_cb.currentData() or None,
            semester=self.semester_cb.currentData() or None,
            lva_id=self.lva_cb.currentData() or None,
            raum_id=self.room_cb.currentData() or None,
            typ=self.typ_cb.currentData() or None,
            dozent=self.dozent_cb.currentData() or None,
            geplante_semester=self.geplante_semester_cb.currentData() or None,
        )
        self.filtersChanged.emit(fs)

    # ------------------------------------------------------------------------

    def refresh_filter_options(
        self,
        fachrichtungen,
        semester_list,
        lva_list,
        raum_list,
        typ_list=None,
        dozent_list=None,
        current: Optional[FilterState] = None,
    ) -> None:
        cur_fach = current.fachrichtung if current else None
        cur_sem = current.semester if current else None
        cur_lva = current.lva_id if current else None
        cur_room = current.raum_id if current else None
        cur_typ = current.typ if current else None
        cur_dozent = current.dozent if current else None
        cur_geplante_semester = current.geplante_semester if current else None

        # geplante semester
        semester_path = os.path.join(os.getcwd(), "data", "geplante_semester.json")
        try:
            with open(semester_path, encoding="utf-8") as f:
                semester_data = json.load(f)["geplante_semester"]
        except Exception:
            semester_data = []

        sem_id_to_display = {s["id"]: s["name"] for s in semester_data}

        geplante_semester_ids = set()
        for lv in lva_list:
            for sem_id in getattr(lv, "geplante_semester", []):
                geplante_semester_ids.add(sem_id)

        geplante_semester_items = [("Geplantes Semester: Alle", None)] + [
            (sem_id_to_display.get(sem_id, sem_id), sem_id)
            for sem_id in sorted(geplante_semester_ids)
        ]

        self.geplante_semester_cb.blockSignals(True)
        self.geplante_semester_cb.clear()
        for text, data in geplante_semester_items:
            self.geplante_semester_cb.addItem(text, data)
        if cur_geplante_semester is not None:
            i = self.geplante_semester_cb.findData(cur_geplante_semester)
            if i >= 0:
                self.geplante_semester_cb.setCurrentIndex(i)
        self.geplante_semester_cb.blockSignals(False)

        # fachrichtung
        fach_items = []
        for f in fachrichtungen:
            if isinstance(f, dict):
                fach_items.append((f.get("name", f.get("id", "")), f.get("id", "")))
            else:
                fach_items.append((str(f), str(f)))
        self._set_combo_items(
            self.fachrichtung_cb,
            "Fachrichtung: Alle",
            None,
            fach_items,
            cur_fach,
        )

        # semester
        semester_items = []
        for sem in semester_list:
            if isinstance(sem, tuple):
                semester_items.append((f"{sem[0]} – {sem[1]}", sem[0]))
            else:
                semester_items.append((str(sem), str(sem)))
        self._set_combo_items(
            self.semester_cb,
            "Semester: Alle",
            None,
            semester_items,
            cur_sem,
        )

        # lva
        self._set_combo_items(
            self.lva_cb,
            "LVA: Alle",
            None,
            [(f"{lv.id} – {getattr(lv, 'name', '')}", lv.id) for lv in lva_list],
            cur_lva,
        )

        # typ
        typ_items = [(tp, tp) for tp in sorted({t for t in typ_list or [] if t})]
        self._set_combo_items(
            self.typ_cb,
            "Typ: Alle",
            None,
            typ_items,
            cur_typ,
        )

        # raum
        self._set_combo_items(
            self.room_cb,
            "Raum: Alle",
            None,
            [(f"{r.id} – {getattr(r, 'name', '')}", r.id) for r in raum_list],
            cur_room,
        )

        # dozent
        if dozent_list is not None:
            dozent_items = [(d, d) for d in sorted({d for d in dozent_list if d})]
        else:
            dozent_items = [
                (d, d)
                for d in sorted(
                    {
                        getattr(lv.vortragende, "name", "")
                        for lv in lva_list
                        if hasattr(lv, "vortragende") and getattr(lv.vortragende, "name", "")
                    }
                )
            ]
        self._set_combo_items(
            self.dozent_cb,
            "Dozent: Alle",
            None,
            dozent_items,
            cur_dozent,
        )

    def _set_combo_items(self, combo, label: str, default_data, items, current) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(label, default_data)

        for text, data in items:
            combo.addItem(text, data)

        if current is not None and current != "":
            i = combo.findData(current)
            if i >= 0:
                combo.setCurrentIndex(i)

        combo.blockSignals(False)