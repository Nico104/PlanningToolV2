import json
from dataclasses import dataclass
from pathlib import Path

from .app_config_service import load_default_config, load_user_config, save_user_config


REQUIRED_DATA_FILES = {
    "raeume.json": ("raeume", []),
    "lehrveranstaltungen.json": ("lehrveranstaltungen", []),
    "termine.json": ("termine", []),
    "studienrichtungen.json": ("studienrichtungen", [{"id": "ETIT", "name": "Elektrotechnik"}]),
    "freie_tage.json": ("freie_tage", []),
}

PROJECT_REFERENCE_RULES = [
    ("termine.json", None, "lva_id", "lehrveranstaltungen.json", "lehrveranstaltungen", "LVA-IDs"),
    ("termine.json", None, "raum_id", "raeume.json", "raeume", "Raum-IDs"),
    ("termine.json", "serien_ausnahmen", "raum_id", "raeume.json", "raeume", "Raum-IDs in Serienausnahmen"),
    ("lehrveranstaltungen.json", None, "studienrichtung", "studienrichtungen.json", "studienrichtungen", "Studienrichtungs-IDs"),
    ("lehrveranstaltungen.json", None, "studiensemester", "studiensemester.json", "studiensemester", "Studiensemester-IDs"),
]


@dataclass(frozen=True)
class ProjectFolderInspection:
    present_files: list[str]
    valid_files: list[str]
    missing_files: list[str]
    invalid_files: list[str]

    @property
    def has_project_files(self) -> bool:
        return bool(self.present_files)


def load_settings() -> dict:
    defaults = load_default_config("settings.json", {})
    settings = load_user_config("settings.json", {})
    if not isinstance(defaults, dict):
        defaults = {}
    if not isinstance(settings, dict):
        settings = {}
    merged = dict(defaults)
    merged.update(settings)
    return merged


def save_settings(settings: dict) -> None:
    save_user_config("settings.json", settings)


def resolve_data_dir(settings: dict) -> Path | None:
    data_path = str(settings.get("data_path", "")).strip()
    if not data_path:
        return None

    data_dir = Path(data_path).expanduser()
    return data_dir.resolve() if data_dir.is_absolute() else None


def data_path_for_settings(data_dir: Path) -> str:
    return str(data_dir.expanduser().resolve())


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_json_id(value) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"none", "null"} else text


def _reference_errors(loaded_items: dict[str, list], missing_files: list[str]) -> list[str]:
    errors: list[str] = []

    for source_file, child_list_key, source_key, target_file, target_root_key, label in PROJECT_REFERENCE_RULES:
        source_items = loaded_items.get(source_file)
        if not source_items:
            continue

        refs: set[str] = set()
        for item in source_items:
            if not isinstance(item, dict):
                continue
            candidates = item.get(child_list_key, []) if child_list_key else [item]
            if not isinstance(candidates, list):
                continue
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                raw_value = candidate.get(source_key)
                values = raw_value if isinstance(raw_value, list) else [raw_value]
                for value in values:
                    cleaned = clean_json_id(value)
                    if cleaned:
                        refs.add(cleaned)
        if not refs:
            continue

        if target_file in loaded_items:
            target_items = loaded_items[target_file]
        elif target_file in REQUIRED_DATA_FILES and target_file in missing_files:
            target_items = REQUIRED_DATA_FILES[target_file][1]
        elif target_file not in REQUIRED_DATA_FILES:
            default_target = load_default_config(target_file, {})
            target_items = default_target.get(target_root_key, []) if isinstance(default_target, dict) else []
        else:
            continue

        target_ids = {
            clean_json_id(item.get("id"))
            for item in target_items
            if isinstance(item, dict) and clean_json_id(item.get("id"))
        }
        unknown_refs = refs - target_ids
        if unknown_refs:
            values = sorted(unknown_refs)
            shown = ", ".join(values[:10])
            if len(values) > 10:
                shown += f", ... ({len(values)} insgesamt)"
            errors.append(f"{source_file} verweist auf unbekannte {label}: {shown}")
    return errors


def inspect_project_folder(data_dir: Path) -> ProjectFolderInspection:
    present: list[str] = []
    valid: list[str] = []
    missing: list[str] = []
    invalid: list[str] = []
    loaded_items: dict[str, list] = {}

    for filename, (root_key, default_items) in REQUIRED_DATA_FILES.items():
        path = data_dir / filename
        if not path.exists():
            missing.append(filename)
            continue

        present.append(filename)
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
            continue

        loaded_items[filename] = obj[root_key]
        valid.append(filename)

    invalid.extend(_reference_errors(loaded_items, missing))

    return ProjectFolderInspection(
        present_files=present,
        valid_files=valid,
        missing_files=missing,
        invalid_files=invalid,
    )


def initialize_missing_project_files(data_dir: Path, filenames: list[str]) -> list[str]:
    created: list[str] = []
    for filename in filenames:
        if filename not in REQUIRED_DATA_FILES:
            continue
        path = data_dir / filename
        if path.exists():
            continue
        root_key, default_items = REQUIRED_DATA_FILES[filename]
        write_json(path, {root_key: default_items})
        created.append(filename)
    return created


def validate_or_initialize_data_dir(data_dir: Path) -> tuple[list[str], list[str]]:
    inspection = inspect_project_folder(data_dir)
    if inspection.invalid_files:
        return [], inspection.invalid_files
    return initialize_missing_project_files(data_dir, inspection.missing_files), []
