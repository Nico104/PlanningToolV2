from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QApplication
from PySide6.QtGui import QPalette


class TickCheckBox(QCheckBox):
    """Styled checkbox with a custom tick icon for use inside dialogs

    The widget picks a white or dark checkmark SVG depending on the current
    application palette (dark mode → white icon).
    """

    def __init__(self, label=None, parent=None):
        super().__init__(label or "", parent)

        # detect dark theme by sampling the window background lightness
        app = QApplication.instance()
        dark = False
        if app is not None:
            try:
                bg = app.palette().color(QPalette.Window)
                dark = bg.lightness() < 128
            except Exception:
                dark = False

        icon_name = "check-marksvg_white.svg" if dark else "check-marksvg.svg"
        check_icon_path = (
            Path(__file__).resolve().parents[2] / "assets" / "icons" / icon_name
        ).as_posix()

        border_color = "#47515c" if dark else "#bbb"

        self.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {border_color};
                border-radius: 4px;
                background: transparent;
            }}
            QCheckBox::indicator:unchecked {{
                image: none;
            }}
            QCheckBox::indicator:checked {{
                image: url('{check_icon_path}');
            }}
        """)
