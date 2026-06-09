from PySide6.QtGui import QColor

from .qss_tokens import qss_color

TYPE_COLORS = [
    ("VO", QColor("#E3F2FD")),  
    ("UE", QColor("#E8F5E9")),  
    ("LU", QColor("#FFF3E0")),
    ("SE", QColor("#F3E5F5")),
]
DEFAULT_BG = QColor("#F7F7F7")
DEFAULT_FG = QColor("#111111")


def type_colors() -> list[tuple[str, QColor]]:
    return [
        ("VO", qss_color("termin-vo-bg", "#E3F2FD")),
        ("UE", qss_color("termin-ue-bg", "#E8F5E9")),
        ("LU", qss_color("termin-lu-bg", "#FFF3E0")),
        ("SE", qss_color("termin-se-bg", "#F3E5F5")),
    ]


def default_bg() -> QColor:
    return qss_color("termin-default-bg", "#F7F7F7")


def planner_text_color() -> QColor:
    return qss_color("planner-text", "#111111")


def type_color_for(typ: str) -> QColor:
    typ = (typ or "").strip().upper()
    for key, color in type_colors():
        if typ == key:
            return color
    return default_bg()
