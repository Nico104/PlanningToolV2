from PySide6.QtGui import QColor

from .qss_tokens import qss_color


def planner_text_color() -> QColor:
    return qss_color("planner-text")


def type_color_for(typ: str) -> QColor:
    key = (typ or "").strip().lower()
    if key:
        try:
            return qss_color(f"termin-{key}-bg")
        except KeyError:
            pass
    return qss_color("termin-default-bg")


def type_accent_color_for(typ: str) -> QColor:
    key = (typ or "").strip().lower()
    colors = {
        "vo": "#1d4ed8",
        "ue": "#15803d",
        "vu": "#7c3aed",
        "lu": "#d97706",
        "se": "#a21caf",
    }
    return QColor(colors.get(key, "#64748b"))
