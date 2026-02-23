from typing import Optional

from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtWidgets import QDockWidget, QWidget, QHBoxLayout, QPushButton, QDateEdit

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


        self.fachrichtung_cb = TightComboBox()
        self.fachrichtung_cb.setToolTip("Fachrichtung filter")
        self.fachrichtung_cb.setMinimumWidth(200)
        headerBar.addWidget(self.fachrichtung_cb)

        self.semester_cb = TightComboBox()
        self.semester_cb.setToolTip("Semester filter")
        self.semester_cb.setMinimumWidth(160)
        headerBar.addWidget(self.semester_cb)


        self.lva_cb = TightComboBox()
        self.lva_cb.setToolTip("LVA filter")
        self.lva_cb.setMinimumWidth(220)
        headerBar.addWidget(self.lva_cb)

        self.dozent_cb = TightComboBox()
        self.dozent_cb.setToolTip("Dozent filter")
        self.dozent_cb.setMinimumWidth(180)
        headerBar.addWidget(self.dozent_cb)

        self.typ_cb = TightComboBox()
        self.typ_cb.setToolTip("Typ filter")
        self.typ_cb.setMinimumWidth(160)
        headerBar.addWidget(self.typ_cb)

        self.room_cb = TightComboBox()
        self.room_cb.setToolTip("Raum filter")
        self.room_cb.setMinimumWidth(200)
        headerBar.addWidget(self.room_cb)

        # Geplante Semester filter
        self.geplante_semester_cb = TightComboBox()
        self.geplante_semester_cb.setToolTip("Geplantes Semester (LVA) filter")
        self.geplante_semester_cb.setMinimumWidth(160)
        headerBar.addWidget(self.geplante_semester_cb)
        
        
        # View selector + navigation + dates
        self.view_cb = TightComboBox()
        self.view_cb.addItem("Wochen", "week")
        self.view_cb.addItem("Tag", "day")
        self.view_cb.setFixedWidth(120)
        headerBar.addWidget(self.view_cb)

        self.prev_btn = QPushButton("<")
        self.prev_btn.setObjectName("NavButton")
        self.prev_btn.setFixedWidth(36)
        headerBar.addWidget(self.prev_btn)

        self.next_btn = QPushButton(">")
        self.next_btn.setObjectName("NavButton")
        self.next_btn.setFixedWidth(36)
        headerBar.addWidget(self.next_btn)

        self.day_date = QDateEdit()
        self.day_date.setObjectName("DateEdit")
        self.day_date.setCalendarPopup(True)
        self.day_date.setDate(QDate.currentDate())
        self.day_date.setFixedWidth(150)
        headerBar.addWidget(self.day_date)

        self.week_from = QDateEdit()
        self.week_from.setObjectName("DateEdit")
        self.week_from.setCalendarPopup(True)
        self.week_from.setFixedWidth(150)
        self.week_from.setDate(QDate.currentDate().addDays(-28))
        headerBar.addWidget(self.week_from)
        
        # self.sem_cb.setObjectName("HeaderCombo")


        self.fachrichtung_cb.setObjectName("HeaderCombo")
        self.semester_cb.setObjectName("HeaderCombo")
        self.lva_cb.setObjectName("HeaderCombo")
        self.dozent_cb.setObjectName("HeaderCombo")
        self.typ_cb.setObjectName("HeaderCombo")
        self.room_cb.setObjectName("HeaderCombo")
        self.view_cb.setObjectName("HeaderCombo")


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

        self.setWidget(self._widget)

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

    def _on_view_change(self, *_) -> None:
        self.viewChanged.emit(str(self.view_cb.currentData()))

    def refresh_filter_options(self, fachrichtungen, semester_list, lva_list, raum_list, typ_list=None, dozent_list=None, current: Optional[FilterState] = None) -> None:
        # Populate geplante_semester_cb with names
        import os, json
        semester_path = os.path.join(os.getcwd(), "data", "geplante_semester.json")
        try:
            with open(semester_path, encoding="utf-8") as f:
                semester_data = json.load(f)["geplante_semester"]
        except Exception:
            semester_data = []
        sem_id_to_display = {s["id"]: s["name"] for s in semester_data}
        geplante_semester_ids = set()
        for lv in lva_list:
            for sem_id in getattr(lv, 'geplante_semester', []):
                geplante_semester_ids.add(sem_id)
        geplante_semester_items = [("Geplantes Semester: Alle", None)] + [ (sem_id_to_display.get(sem_id, sem_id), sem_id) for sem_id in sorted(geplante_semester_ids)]
        self.geplante_semester_cb.blockSignals(True)
        self.geplante_semester_cb.clear()
        for text, data in geplante_semester_items:
            self.geplante_semester_cb.addItem(text, data)
        if current and getattr(current, 'geplante_semester', None):
            i = self.geplante_semester_cb.findData(current.geplante_semester)
            if i >= 0:
                self.geplante_semester_cb.setCurrentIndex(i)
        self.geplante_semester_cb.blockSignals(False)
        cur_fach = current.fachrichtung if current else None
        cur_sem = current.semester if current else None
        cur_lva = current.lva_id if current else None
        cur_room = current.raum_id if current else None
        cur_typ = current.typ if current else None
        cur_dozent = current.dozent if current else None

        # Use name as display, id as data for fachrichtungen
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
        # Ensure 'Semester: Alle' has None as data, others have their id and name
        semester_items = [("Semester: Alle", None)]
        for sem in semester_list:
            if isinstance(sem, tuple):
                semester_items.append((f"{sem[0]} – {sem[1]}", sem[0]))
            else:
                semester_items.append((str(sem), str(sem)))
        self.semester_cb.blockSignals(True)
        self.semester_cb.clear()
        for text, data in semester_items:
            self.semester_cb.addItem(text, data)
        if cur_sem is not None and cur_sem != "":
            i = self.semester_cb.findData(cur_sem)
            if i >= 0:
                self.semester_cb.setCurrentIndex(i)
        self.semester_cb.blockSignals(False)
        self._set_combo_items(
            self.lva_cb,
            "LVA: Alle",
            None,
            [(f"{lv.id} – {getattr(lv, 'name', '')}", lv.id) for lv in lva_list],
            cur_lva,
        )
        typ_items = [(tp, tp) for tp in sorted({t for t in typ_list or [] if t})]
        self._set_combo_items(self.typ_cb, "Typ: Alle", None, typ_items, cur_typ)
        self._set_combo_items(
            self.room_cb,
            "Raum: alle",
            "",
            [(f"{r.id} – {getattr(r, 'name', '')}", r.id) for r in raum_list],
            cur_room,
        )
        dozent_items = [(d, d) for d in sorted({getattr(lv.vortragende, 'name', '') for lv in lva_list if hasattr(lv, 'vortragende') and getattr(lv.vortragende, 'name', '')})]
        self._set_combo_items(self.dozent_cb, "Dozent: Alle", None, dozent_items, cur_dozent)

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
