import json
import os
import sys
from pathlib import Path
from typing import Any

APP_NAME = "Planungstool"
CONFIG_DIR_ENV = "PLANUNGSTOOL_CONFIG_DIR"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_config_path(filename: str) -> Path:
    return project_root() / "src" / filename


def user_config_dir() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()

    home = Path.home()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return base / APP_NAME
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / APP_NAME


def user_config_path(filename: str) -> Path:
    return user_config_dir() / filename


def ensure_user_config_file(filename: str) -> Path:
    target = user_config_path(filename)
    if target.exists():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    source = default_config_path(filename)
    if source.exists():
        target.write_text(source.read_text(encoding="utf-8-sig"), encoding="utf-8")
    return target


def load_user_config(filename: str, fallback: Any) -> Any:
    path = ensure_user_config_file(filename)
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback


def load_default_config(filename: str, fallback: Any) -> Any:
    path = default_config_path(filename)
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback


def save_user_config(filename: str, obj: Any, *, indent: int = 2) -> None:
    target = user_config_path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    tmp.replace(target)
