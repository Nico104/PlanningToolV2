from typing import Optional
import os
import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QHBoxLayout,
    QSizePolicy,
)

from ..components.widgets.tight_combobox import TightComboBox
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

        self.fachrichtung_cb.currentIndexChanged.connect(self._on_change)
        self.semester_cb.currentIndexChanged.connect(self._on_change)
        self.lva_cb.currentIndexChanged.connect(self._on_change)
        self.dozent_cb.currentIndexChanged.connect(self._on_change)
        self.typ_cb.currentIndexChanged.connect(self._on_change)
        self.room_cb.currentIndexChanged.connect(self._on_change)
        self.geplante_semester_cb.currentIndexChanged.connect(self._on_change)

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