import json
from pathlib import Path


REQUIRED_DATA_FILES = {
    "raeume.json": ("raeume", []),
    "lehrveranstaltungen.json": ("lehrveranstaltungen", []),
    "termine.json": ("termine", []),
    "studienrichtungen.json": ("studienrichtungen", [{"id": "ETIT", "name": "Elektrotechnik"}]),
    "freie_tage.json": ("freie_tage", []),
}


def load_settings(settings_path: Path) -> dict:
    if not settings_path.exists():
        return {}
    try:
        return json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(settings_path: Path, settings: dict) -> None:
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def resolve_data_dir(project_root: Path, settings: dict) -> Path:
    data_path = str(settings.get("data_path", "")).strip()
    if not data_path:
        return project_root / "data"

    data_dir = Path(data_path)
    if not data_dir.is_absolute():
        data_dir = (project_root / data_dir).resolve()
    return data_dir


def data_path_for_settings(project_root: Path, data_dir: Path) -> str:
    data_dir = data_dir.resolve()
    try:
        return str(data_dir.relative_to(project_root.resolve()))
    except ValueError:
        return str(data_dir)


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_or_initialize_data_dir(data_dir: Path) -> tuple[list[str], list[str]]:
    created: list[str] = []
    invalid: list[str] = []

    for filename, (root_key, default_items) in REQUIRED_DATA_FILES.items():
        path = data_dir / filename
        if not path.exists():
            write_json(path, {root_key: default_items})
            created.append(filename)
            continue

        if not path.is_file():
            invalid.append(f"{filename} ist keine Datei.")
            continue

        try:
            obj = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            invalid.append(f"{filename}: ungültiges JSON ({exc})")
            continue

        if not isinstance(obj, dict) or not isinstance(obj.get(root_key), list):
            invalid.append(f"{filename}: erwartetes Format {{{root_key}: [...]}} fehlt.")

    return created, invalid
