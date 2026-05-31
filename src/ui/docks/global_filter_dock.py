from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QHBoxLayout,
    QSizePolicy,
)

from ..components.widgets.tight_combobox import TightComboBox
from ..components.widgets.semester_selector import SemesterSelector
from ...core.states import FilterState


class GlobalFilterDock(QDockWidget):
    """
    Dock for content filters
    """

    filtersChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__("Filter", parent)
        self.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)

        self._widget = QWidget(self)
        self._widget.setObjectName("HeaderBar")

        headerBar = QHBoxLayout(self._widget)
        headerBar.setContentsMargins(6, 6, 6, 6)
        headerBar.setSpacing(8)

        self.studienrichtung_cb = TightComboBox()
        self.studienrichtung_cb.setToolTip("Studienrichtung filter")
        self.studienrichtung_cb.setMinimumWidth(120)
        self.studienrichtung_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.studienrichtung_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.studienrichtung_cb)

        self.semester_selector = SemesterSelector(self, all_label="Semester: Alle")
        self.semester_selector.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        headerBar.addWidget(self.semester_selector)

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

        self.studiensemester_cb = TightComboBox()
        self.studiensemester_cb.setToolTip("Studiensemester filter")
        self.studiensemester_cb.setMinimumWidth(150)
        self.studiensemester_cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.studiensemester_cb.setObjectName("HeaderCombo")
        headerBar.addWidget(self.studiensemester_cb)

        self.studienrichtung_cb.currentIndexChanged.connect(self._on_change)
        self.semester_selector.semesterChanged.connect(self._on_change)
        self.lva_cb.currentIndexChanged.connect(self._on_change)
        self.dozent_cb.currentIndexChanged.connect(self._on_change)
        self.typ_cb.currentIndexChanged.connect(self._on_change)
        self.room_cb.currentIndexChanged.connect(self._on_change)
        self.studiensemester_cb.currentIndexChanged.connect(self._on_change)

        self.setWidget(self._widget)

    def _on_change(self, *_) -> None:
        fs = FilterState(
            studienrichtung=self.studienrichtung_cb.currentData() or None,
            semester=self.semester_selector.current_semester_id(),
            lva_id=self.lva_cb.currentData() or None,
            raum_id=self.room_cb.currentData() or None,
            typ=self.typ_cb.currentData() or None,
            dozent=self.dozent_cb.currentData() or None,
            studiensemester=self.studiensemester_cb.currentData() or None,
        )
        self.filtersChanged.emit(fs)

    def refresh_filter_options(
        self,
        studienrichtungen,
        semester_list,
        lva_list,
        raum_list,
        studiensemester_list=None,
        typ_list=None,
        dozent_list=None,
        current: Optional[FilterState] = None,
    ) -> None:
        cur_studienrichtung = current.studienrichtung if current else None
        cur_sem = current.semester if current else None
        cur_lva = current.lva_id if current else None
        cur_room = current.raum_id if current else None
        cur_typ = current.typ if current else None
        cur_dozent = current.dozent if current else None
        cur_studiensemester = current.studiensemester if current else None

        sem_id_to_display = {}
        for item in studiensemester_list or []:
            if isinstance(item, dict):
                semester_id = str(item.get("id", "")).strip()
                name = str(item.get("name", "")).strip()
            else:
                semester_id = str(getattr(item, "id", "")).strip()
                name = str(getattr(item, "name", "")).strip()
            if semester_id:
                sem_id_to_display[semester_id] = name or semester_id

        studiensemester_ids = set()
        for lv in lva_list:
            for sem_id in getattr(lv, "studiensemester", []):
                studiensemester_ids.add(sem_id)

        studiensemester_items = [("Studiensemester: Alle", None)] + [
            (sem_id_to_display.get(sem_id, sem_id), sem_id)
            for sem_id in sorted(studiensemester_ids)
        ]

        self.studiensemester_cb.blockSignals(True)
        self.studiensemester_cb.clear()
        for text, data in studiensemester_items:
            self.studiensemester_cb.addItem(text, data)
        if cur_studiensemester is not None:
            i = self.studiensemester_cb.findData(cur_studiensemester)
            if i >= 0:
                self.studiensemester_cb.setCurrentIndex(i)
        self.studiensemester_cb.blockSignals(False)

        studienrichtung_items = []
        for f in studienrichtungen:
            if isinstance(f, dict):
                studienrichtung_items.append((f.get("name", f.get("id", "")), f.get("id", "")))
            else:
                studienrichtung_items.append((str(f), str(f)))
        self._set_combo_items(
            self.studienrichtung_cb,
            "Studienrichtung: Alle",
            None,
            studienrichtung_items,
            cur_studienrichtung,
        )

        self.semester_selector.set_semester_id(cur_sem)

        self._set_combo_items(
            self.lva_cb,
            "LVA: Alle",
            None,
            [(f"{lv.id} – {getattr(lv, 'name', '')}", lv.id) for lv in lva_list],
            cur_lva,
        )

        typ_items = [(tp, tp) for tp in sorted({t for t in typ_list or [] if t})]
        self._set_combo_items(
            self.typ_cb,
            "Typ: Alle",
            None,
            typ_items,
            cur_typ,
        )

        self._set_combo_items(
            self.room_cb,
            "Raum: Alle",
            None,
            [(f"{r.id} – {getattr(r, 'name', '')}", r.id) for r in raum_list],
            cur_room,
        )

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
