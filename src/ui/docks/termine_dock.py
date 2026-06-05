from collections import defaultdict
from datetime import date, time
from functools import partial
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QMenu, QFrame, QToolButton, QLineEdit, QLabel
)

from ..utils.datetime_utils import fmt_date, fmt_time
from ...core.models import Termin, Lehrveranstaltung, Raum
from ..components.cards.termin_card import TerminCard
from ..components.dragdrop.termin_drop_area import TerminDropArea



class TermineDock(QDockWidget):
    """Dock widget that lists Termine as grouped cards with edit/delete/unassign signals"""
    termin_double_clicked = Signal(str)
    termin_delete_clicked = Signal(str)
    termin_unassign_requested = Signal(str)
    termin_jump_requested = Signal(str)

    def _init_group_states(self):
        self._group_states = {}

    def __init__(self, parent=None):
        super().__init__("Termine", parent)
        self.setAllowedAreas(Qt.AllDockWidgetAreas)

        self._all_termine: List[Termin] = []
        self._lvas: List[Lehrveranstaltung] = []
        self._raeume: List[Raum] = []
        self._search_query = ""
        self._read_only = False

        header = QWidget(self)
        header.setObjectName("HeaderBar")
        root = QVBoxLayout(header)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        #Header bar
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 2)
        bar.setSpacing(8)
        root.addLayout(bar)

        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("HeaderSearch")
        self.search_input.setPlaceholderText("Suche: Name, LVA, Raum, Dozent")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(self._jump_to_first_search_result)
        bar.addWidget(self.search_input, 1)

        self.result_label = QLabel("", self)
        self.result_label.setObjectName("TermineSearchResult")
        self.result_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bar.addWidget(self.result_label)

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

    def set_read_only(self, read_only: bool) -> None:
        read_only = bool(read_only)
        if read_only == self._read_only:
            return
        self._read_only = read_only
        if hasattr(self.container, "set_read_only"):
            self.container.set_read_only(self._read_only)
        self._build_cards()

    def set_rows(
        self,
        termine: List[Termin],
        lvas: List[Lehrveranstaltung],
        raeume: List[Raum],
    ) -> None:
        self._all_termine = list(termine)
        self._lvas = list(lvas)
        self._raeume = list(raeume)

        self._init_group_states()
        self._build_cards()


    def _normalize(self, text: str) -> str:
        return str(text or "").strip().lower()

    def _search_blob(self, termin: Termin) -> str:
        lva = next((l for l in self._lvas if l.id == termin.lva_id), None)
        raum = next((r for r in self._raeume if r.id == termin.raum_id), None)
        dozent = ""
        if lva and getattr(lva, "vortragende", None):
            dozent = getattr(lva.vortragende, "name", "") or ""

        parts = [
            getattr(termin, "name", ""),
            termin.id,
            termin.lva_id,
            termin.raum_id,
            lva.name if lva else "",
            raum.name if raum else "",
            dozent,
            getattr(termin, "besprechungshinweis", ""),
            "zu besprechen" if bool(getattr(termin, "zu_besprechen", False)) else "",
        ]
        return self._normalize(" ".join(parts))

    def _filtered_terms_for_search(self) -> List[Termin]:
        terms = self._all_termine
        query = self._normalize(self._search_query)
        if not query:
            return terms

        filtered: List[Termin] = []
        for t in terms:
            blob = self._search_blob(t)
            if query in blob:
                filtered.append(t)
        return filtered

    def _on_search_text_changed(self, text: str) -> None:
        self._search_query = text
        self._build_cards()

    def set_search_enabled(self, enabled: bool) -> None:
        self.search_input.setVisible(enabled)
        self.result_label.setVisible(enabled)
        if not enabled:
            self.search_input.clear()
            self._search_query = ""
            self._build_cards()

    def _jump_to_first_search_result(self) -> None:
        terms = self._filtered_terms_for_search()
        if not terms:
            return

        assigned = [t for t in terms if t.datum and t.start_zeit]
        if not assigned:
            return
        self.termin_jump_requested.emit(assigned[0].id)

    def _build_cards(self) -> None:
        # clear old cards (leave last stretch)
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # MainWindow supplies already-filtered termine to set_rows()
        terms = self._filtered_terms_for_search()
        self.result_label.setText(f"{len(terms)} Treffer" if self._search_query.strip() else "")

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

        # Sort LVA groups by display name, then by ID
        def lva_sort_key(lva_id):
            lva = next((l for l in self._lvas if l.id == lva_id), None)
            return ((lva.name if lva else ""), (lva.id if lva else str(lva_id)))

        for lva_id in sorted(lva_groups.keys(), key=lva_sort_key):
            lva = next((l for l in self._lvas if l.id == lva_id), None)
            lva_name = lva.name if lva else str(lva_id)

            # Collapsible group header
            group_key = str(lva_id)
            if group_key not in self._group_states:
                self._group_states[group_key] = True  # default expanded


            # Count assigned/total termine in group
            group_termine = lva_groups[lva_id]
            total_count = len(group_termine)
            assigned_count = sum(1 for t in group_termine if t.datum and t.start_zeit)
            header_text = f"{lva_name} ({assigned_count}/{total_count})"

            header_btn = QToolButton()
            header_btn.setText(header_text)
            header_btn.setCheckable(True)
            header_btn.setChecked(self._group_states[group_key])
            header_btn.setArrowType(Qt.DownArrow if self._group_states[group_key] else Qt.RightArrow)
            header_btn.setObjectName("LvaHeaderButton")
            header_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            header_btn.setMinimumHeight(28)
            header_btn.setMinimumWidth(120)
            header_btn.setStyleSheet(
                "QToolButton#LvaHeaderButton {"
                " color: #222;"
                " background: transparent;"
                " font-weight: bold;"
                " text-align: left;"
                " padding-left: 4px;"
                " border: none;"
                "}"
                "QToolButton#LvaHeaderButton:checked {"
                " background: #f5f5f5;"
                "}"
            )

            group_cards = []
            def toggle_group(checked, cards, btn, key):
                self._group_states[key] = checked
                btn.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
                for card in cards:
                    card.setVisible(checked)

            header_btn.toggled.connect(partial(toggle_group, cards=group_cards, btn=header_btn, key=group_key))
            self.list_layout.insertWidget(self.list_layout.count() - 1, header_btn)

            for t in lva_groups[lva_id]:
                raum = next((r for r in self._raeume if r.id == t.raum_id), None)
                title = f"{t.lva_id} – {(lva.name if lva else '')}".strip(" –")
                raum_txt = f"{t.raum_id} – {(raum.name if raum else '')}".strip(" –")
                if t.is_series() and getattr(t, "datum_bis", None):
                    date_text = f"{fmt_date(t.datum)} – {fmt_date(t.datum_bis)}"
                else:
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
                    zu_besprechen=bool(getattr(t, "zu_besprechen", False)),
                    besprechungshinweis=str(getattr(t, "besprechungshinweis", "") or ""),
                )

                if hasattr(card, "set_read_only"):
                    card.set_read_only(self._read_only)
                card.double_clicked.connect(self.termin_double_clicked.emit)
                card.right_clicked.connect(self._open_menu)
                card.setVisible(self._group_states[group_key])
                group_cards.append(card)
                self.list_layout.insertWidget(self.list_layout.count() - 1, card)


    def _on_drop_to_list(self, termin_id: str) -> None:
        if self._read_only:
            self._show_history_read_only_toast()
            return
        self.termin_unassign_requested.emit(termin_id)

    def _show_history_read_only_toast(self) -> None:
        cb = getattr(self.window(), "_show_history_read_only_toast", None)
        if callable(cb):
            cb()

    def _open_menu(self, termin_id: str) -> None:
        menu = QMenu(self)
        t = next((x for x in self._all_termine if x.id == termin_id), None)
        assigned = bool(t and t.datum and t.start_zeit)

        act_jump = None
        if assigned:
            act_jump = menu.addAction("Springe zu")

        if self._read_only:
            if act_jump is None:
                return
            chosen = menu.exec(self.cursor().pos())
            if chosen == act_jump:
                self.termin_jump_requested.emit(termin_id)
            return

        act_edit = menu.addAction("Bearbeiten")
        act_del = menu.addAction("Löschen")

        chosen = menu.exec(self.cursor().pos())
        if act_jump is not None and chosen == act_jump:
            self.termin_jump_requested.emit(termin_id)
        elif chosen == act_edit:
            self.termin_double_clicked.emit(termin_id)
        elif chosen == act_del:
            self.termin_delete_clicked.emit(termin_id)
            
