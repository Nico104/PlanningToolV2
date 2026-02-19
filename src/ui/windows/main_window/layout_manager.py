from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QInputDialog


class LayoutManager:
    def __init__(self, mw):
        self.mw = mw
        self._layouts: dict[str, bytes] = {}
        self._current_layout_name: str | None = None

        self.mw.act_save_layout.triggered.connect(self._save_layout_dialog)
        self.mw.act_reset_layouts.triggered.connect(self._reset_default_layouts)

    def init_default(self) -> None:
        self._layouts["Standard"] = self.mw.saveState()
        self._current_layout_name = "Standard"
        self._rebuild_layout_menu_items()

    def _rebuild_layout_menu_items(self) -> None:
        lm = self.mw.layout_menu
        lm.clear()

        lm.addAction(self.mw.act_save_layout)
        lm.addAction(self.mw.act_reset_layouts)
        lm.addSeparator()

        self.mw.layout_group = QActionGroup(self.mw)
        self.mw.layout_group.setExclusive(True)

        for name in self._layouts.keys():
            act = QAction(name, self.mw, checkable=True)
            act.setChecked(name == self._current_layout_name)
            act.triggered.connect(lambda checked, n=name: self.apply_layout(n))
            self.mw.layout_group.addAction(act)
            lm.addAction(act)

    def apply_layout(self, name: str) -> None:
        state = self._layouts.get(name)
        if not state:
            return
        ok = self.mw.restoreState(state)
        if ok:
            self._current_layout_name = name
            self._rebuild_layout_menu_items()

    def _save_layout_dialog(self) -> None:
        name, ok = QInputDialog.getText(self.mw, "Layout speichern", "Name für Layout:")
        if not ok or not name.strip():
            return
        name = name.strip()

        self._layouts[name] = self.mw.saveState()
        self._current_layout_name = name
        self._rebuild_layout_menu_items()

    def _reset_default_layouts(self) -> None:
        std = self._layouts.get("Standard")
        self._layouts.clear()

        if std is None:
            std = self.mw.saveState()

        self._layouts["Standard"] = std
        self._current_layout_name = "Standard"
        self.apply_layout("Standard")
        self._rebuild_layout_menu_items()
