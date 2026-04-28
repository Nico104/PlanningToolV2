import base64

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QInputDialog


class LayoutManager:
    """Manage dock/window layout presets for the main window
    """

    DEFAULT_LAYOUT = "Standard"

    def __init__(self, mw):
        self.mw = mw
        self._layouts: dict[str, bytes] = {}
        self._current_layout_name: str | None = None

        self.mw.act_save_layout.triggered.connect(self._save_layout_dialog)
        self.mw.act_reset_layouts.triggered.connect(self._reset_default_layouts)

    def init_default(self) -> None:
        self._load_persisted_layouts()
        if self.DEFAULT_LAYOUT not in self._layouts:
            self._layouts[self.DEFAULT_LAYOUT] = self.mw.saveState()
        if self._current_layout_name not in self._layouts:
            self._current_layout_name = self.DEFAULT_LAYOUT
        self._rebuild_layout_menu_items()
        self.apply_layout(self._current_layout_name)

    def _rebuild_layout_menu_items(self) -> None:
        lm = self.mw.layout_menu
        lm.clear()

        lm.addAction(self.mw.act_save_layout)
        lm.addAction(self.mw.act_reset_layouts)
        lm.addSeparator()

        self.mw.layout_group = QActionGroup(self.mw)
        self.mw.layout_group.setExclusive(True)

        for name in self._layouts:
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
            self._persist_layouts()
            self._rebuild_layout_menu_items()

    def _save_layout_dialog(self) -> None:
        name, ok = QInputDialog.getText(self.mw, "Layout speichern", "Name für Layout:")
        if not ok or not name.strip():
            return
        name = name.strip()

        self._layouts[name] = self.mw.saveState()
        self._current_layout_name = name
        self._persist_layouts()
        self._rebuild_layout_menu_items()

    def _reset_default_layouts(self) -> None:
        std = self._layouts.get(self.DEFAULT_LAYOUT)
        self._layouts.clear()

        if std is None:
            std = self.mw.saveState()

        self._layouts[self.DEFAULT_LAYOUT] = std
        self._current_layout_name = self.DEFAULT_LAYOUT
        self.mw.restoreState(std)
        self._persist_layouts()
        self._rebuild_layout_menu_items()

    def _load_persisted_layouts(self) -> None:
        settings = self.mw.ds.load_settings()
        raw_layouts = settings.get("layout_presets", {})
        raw_current = settings.get("layout_current")

        self._layouts = {}
        if isinstance(raw_layouts, dict):
            for name, encoded in raw_layouts.items():
                if not isinstance(name, str) or not isinstance(encoded, str):
                    continue
                try:
                    self._layouts[name] = base64.b64decode(encoded)
                except Exception:
                    continue

        self._current_layout_name = raw_current if isinstance(raw_current, str) else None

    def _persist_layouts(self) -> None:
        settings = self.mw.ds.load_settings()
        settings["layout_presets"] = {
            name: base64.b64encode(state).decode("ascii")
            for name, state in self._layouts.items()
        }
        settings["layout_current"] = self._current_layout_name
        self.mw.ds.save_settings(settings)
