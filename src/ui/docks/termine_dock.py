from typing import List, Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QMenu, QFrame, QLabel
)

from ..utils.datetime_utils import fmt_date, fmt_time
from ...core.models import Termin, Lehrveranstaltung, Raum
from ..components.cards.termin_card import TerminCard
from ..components.dragdrop.termin_drop_area import TerminDropArea
from datetime import date as date, time as time
from collections import defaultdict


class TermineDock(QDockWidget):
    termin_double_clicked = Signal(str)
    termin_delete_clicked = Signal(str)
    termin_unassign_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__("Termine", parent)
        self.setAllowedAreas(Qt.AllDockWidgetAreas)

        self._all_termine: List[Termin] = []
        self._lvas: List[Lehrveranstaltung] = []
        self._raeume: List[Raum] = []

        header = QWidget(self)
        header.setObjectName("HeaderBar")
        root = QVBoxLayout(header)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        #Header bar
        bar = QHBoxLayout()
        bar.setSpacing(8)
        root.addLayout(bar)

        #Scroll area with cards
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setLineWidth(0)


        self.container = TerminDropArea()
        self.container.terminDroppedToList.connect(self._on_drop_to_list)

        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(8, 2, 8, 2)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch(1)

        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

        self.setWidget(header)


    def set_rows(
        self,
        termine: List[Termin],
        lvas: List[Lehrveranstaltung],
        raeume: List[Raum],
    ) -> None:
        self._all_termine = list(termine)
        self._lvas = list(lvas)
        self._raeume = list(raeume)

        # Global filtering is applied by MainWindow before calling set_rows
        self._build_cards()

    def _build_cards(self) -> None:
        # clear old cards (leave last stretch)
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # MainWindow supplies already-filtered termine to set_rows()
        terms = self._all_termine

        def _sort_key(t: Termin):
            unassigned = (t.datum is None) or (t.start_zeit is None)
            d = t.datum or date.min
            von = (t.start_zeit if t.start_zeit else time.min)
            return (not unassigned, d, von, t.id)

        terms = sorted(terms, key=_sort_key)

        # Group termine by lva_id
        lva_groups = defaultdict(list)
        for t in terms:
            lva_groups[t.lva_id].append(t)

        # Sort LVA groups by LVA name (if available), else by lva_id
        def lva_sort_key(lva_id):
            lva = next((l for l in self._lvas if l.id == lva_id), None)
            return (lva.name if lva else str(lva_id))

        for lva_id in sorted(lva_groups.keys(), key=lva_sort_key):
            lva = next((l for l in self._lvas if l.id == lva_id), None)
            lva_name = lva.name if lva else str(lva_id)
            
            # Insert LVA heade
            lva_label = QLabel(lva_name)
            lva_label.setObjectName("LvaHeaderLabel")
            lva_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.list_layout.insertWidget(self.list_layout.count() - 1, lva_label)

            for t in lva_groups[lva_id]:
                raum = next((r for r in self._raeume if r.id == t.raum_id), None)
                title = f"{t.lva_id} – {(lva.name if lva else '')}".strip(" –")
                raum_txt = f"{t.raum_id} – {(raum.name if raum else '')}".strip(" –")
                date_text = fmt_date(t.datum)
                end_time = t.get_end_time()
                time_text = (
                    f"{fmt_time(t.start_zeit)} – {fmt_time(end_time)} ({t.duration} min)"
                    if t.start_zeit and end_time
                    else ""
                )

                card = TerminCard(
                    termin_id=t.id,
                    title=title,
                    date=date_text,
                    time=time_text,
                    typ=t.typ,
                    raum=raum_txt,
                    ap=t.anwesenheitspflicht,
                    duration=t.duration,
                    name=getattr(t, "name", None),
                    parent=self.container,
                )

                card.double_clicked.connect(self.termin_double_clicked.emit)
                card.right_clicked.connect(self._open_menu)

                self.list_layout.insertWidget(self.list_layout.count() - 1, card)


    def _on_drop_to_list(self, termin_id: str) -> None:
        self.termin_unassign_requested.emit(termin_id)

    def _open_menu(self, termin_id: str) -> None:
        menu = QMenu(self)
        act_edit = menu.addAction("Bearbeiten")
        act_del = menu.addAction("Löschen")

        chosen = menu.exec(self.cursor().pos())
        if chosen == act_edit:
            self.termin_double_clicked.emit(termin_id)
        elif chosen == act_del:
            self.termin_delete_clicked.emit(termin_id)
            