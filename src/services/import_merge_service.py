from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .free_day_id_service import free_day_entry_key


@dataclass(frozen=True)
class ImportFileSchema:
    list_key: str
    id_field: str = "id"
    key_func: Callable[[dict[str, Any]], str | None] | None = None


def get_entry_id(entry: dict[str, Any], id_field: str) -> str | None:
    value = entry.get(id_field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


IMPORT_FILE_SCHEMAS: dict[str, ImportFileSchema] = {
    "termine.json": ImportFileSchema("termine", "id"),
    "raeume.json": ImportFileSchema("raeume", "id"),
    "lehrveranstaltungen.json": ImportFileSchema("lehrveranstaltungen", "id"),
    "studienrichtungen.json": ImportFileSchema("studienrichtungen", "id"),
    "freie_tage.json": ImportFileSchema("freie_tage", key_func=free_day_entry_key),
}

KNOWN_IMPORT_KEYS = {
    schema.list_key: file_name for file_name, schema in IMPORT_FILE_SCHEMAS.items()
}


def get_entry_key(entry: dict[str, Any], schema: ImportFileSchema) -> str | None:
    if schema.key_func is not None:
        return schema.key_func(entry)
    return get_entry_id(entry, schema.id_field)


def payload_list(content: Any, schema: ImportFileSchema) -> list[dict[str, Any]]:
    if isinstance(content, list):
        items = content
    elif isinstance(content, dict):
        items = content.get(schema.list_key, [])
    else:
        items = []
    return [item for item in items if isinstance(item, dict)]


def normalize_import_payload(data: Any) -> dict[str, dict[str, list[dict[str, Any]]]]:
    normalized: dict[str, dict[str, list[dict[str, Any]]]] = {}

    def add_payload(file_name: str, value: Any) -> None:
        schema = IMPORT_FILE_SCHEMAS.get(file_name)
        if schema is None:
            return
        normalized[file_name] = {schema.list_key: payload_list(value, schema)}

    if isinstance(data, dict):
        if all(isinstance(k, str) and k.lower().endswith(".json") for k in data.keys()):
            for file_name, value in data.items():
                add_payload(file_name, value)
        else:
            for key, file_name in KNOWN_IMPORT_KEYS.items():
                if key in data:
                    add_payload(file_name, data[key])

            if not normalized:
                for raw_key, value in data.items():
                    low = str(raw_key).lower()
                    for key, file_name in KNOWN_IMPORT_KEYS.items():
                        if key in low or (
                            low.endswith(".json") and low.replace(".json", "") == key
                        ):
                            add_payload(file_name, value)

            if not normalized:

                def search_and_map(obj: Any) -> None:
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            file_name = KNOWN_IMPORT_KEYS.get(str(key))
                            if file_name:
                                add_payload(file_name, value)
                            else:
                                search_and_map(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            search_and_map(item)

                search_and_map(data)
    elif isinstance(data, list):
        add_payload("termine.json", data)

    return normalized


def load_existing_payload(data_dir: Path, file_name: str) -> dict[str, Any] | None:
    path = data_dir / file_name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def load_existing_entries(data_dir: Path, file_name: str) -> list[dict[str, Any]]:
    schema = IMPORT_FILE_SCHEMAS.get(file_name)
    if schema is None:
        return []
    return payload_list(load_existing_payload(data_dir, file_name), schema)


def existing_entry_map(data_dir: Path, file_name: str) -> dict[str, dict[str, Any]]:
    schema = IMPORT_FILE_SCHEMAS.get(file_name)
    if schema is None:
        return {}
    return {
        entry_key: entry
        for entry in load_existing_entries(data_dir, file_name)
        if (entry_key := get_entry_key(entry, schema)) is not None
    }


def classify_entry(
    entry: dict[str, Any], existing_by_id: dict[str, dict[str, Any]], id_field: str
) -> str:
    entry_id = get_entry_id(entry, id_field)
    existing = existing_by_id.get(entry_id or "")
    if existing is None:
        return "new"
    return "identical" if existing == effective_import_entry(existing, entry) else "changed"


def is_empty_import_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, dict):
        return all(is_empty_import_value(item) for item in value.values())
    return False


def effective_import_entry(
    existing: dict[str, Any] | None, incoming: dict[str, Any], file_name: str = ""
) -> dict[str, Any]:
    if existing is None:
        return dict(incoming)

    merged = dict(existing)
    for key, value in incoming.items():
        if key == "id":
            merged[key] = value
            continue
        if is_empty_import_value(value):
            continue
        merged[key] = value
    return merged


def build_payload(
    entries_by_file: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    payload: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for file_name, entries in entries_by_file.items():
        schema = IMPORT_FILE_SCHEMAS.get(file_name)
        if schema is not None and entries:
            payload[file_name] = {schema.list_key: entries}
    return payload


def payload_has_changes(data_dir: Path, incoming_payload: dict[str, Any]) -> bool:
    for file_name, incoming in (incoming_payload or {}).items():
        schema = IMPORT_FILE_SCHEMAS.get(file_name)
        if schema is None:
            continue
        existing = existing_entry_map(data_dir, file_name)
        for entry in payload_list(incoming, schema):
            entry_key = get_entry_key(entry, schema)
            current = existing.get(entry_key or "")
            if entry_key is None or current != effective_import_entry(current, entry, file_name):
                return True
    return False
