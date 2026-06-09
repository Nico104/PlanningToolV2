from pathlib import Path

from PySide6.QtGui import QColor


_TOKENS: dict[str, str] = {}


def set_qss_tokens(qss: str) -> None:
    global _TOKENS
    _TOKENS = parse_qss_tokens(qss)


def load_qss_tokens(path: Path) -> None:
    try:
        set_qss_tokens(path.read_text(encoding="utf-8"))
    except OSError:
        set_qss_tokens("")


def parse_qss_tokens(qss: str) -> dict[str, str]:
    values: dict[str, str] = {}
    in_tokens_block = False

    for raw_line in qss.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("/*"):
            continue
        if "QWidget#PlannerStyleTokens" in line:
            in_tokens_block = True
            continue
        if in_tokens_block and line.startswith("}"):
            in_tokens_block = False
            continue
        if not in_tokens_block or ":" not in line:
            continue

        token, value = line.split(":", 1)
        values[token.strip()] = value.strip().rstrip(";")

    return values


def qss_token(name: str, fallback: str = "") -> str:
    return _TOKENS.get(name, fallback)


def qss_color(name: str, fallback: str) -> QColor:
    color = QColor(qss_token(name, fallback))
    if color.isValid():
        return color
    return QColor(fallback)
