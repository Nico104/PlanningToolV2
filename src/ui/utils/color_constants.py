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
