CONFLICT_CATEGORY_LABELS = {
    "room": "Raum",
    "lecturer": "Lehrperson",
    "holiday": "Feiertag",
    "lecture_free": "Vorlesungsfrei",
    "free_day": "Freier Tag",
    "time_period": "Zeitraum",
    "group": "Gruppe",
    "semester": "Studienplan",
    "incomplete": "Unvollstaendig",
    "duration": "Dauer",
    "saturday": "Samstag",
    "sunday": "Sonntag",
    "Kapazität Übung": "Kapazität Übung",
    "Kapazität Vorlesung": "Kapazität Vorlesung",
}


CONFLICT_CATEGORY_KINDS = {
    "room": "raum",
    "lecturer": "vortragende",
    "holiday": "zeitraum",
    "lecture_free": "zeitraum",
    "free_day": "zeitraum",
    "time_period": "zeitraum",
    "group": "gruppe",
    "semester": "semester",
    "incomplete": "unvollstaendig",
    "duration": "dauer",
    "saturday": "wochenende",
    "sunday": "wochenende",
    "Kapazität Übung": "kapazitaet",
    "Kapazität Vorlesung": "kapazitaet",
}


def conflict_category_label(category: str) -> str:
    category = str(category or "").strip()
    return CONFLICT_CATEGORY_LABELS.get(category, category)


def conflict_category_kind(category: str) -> str:
    category = str(category or "").strip()
    return CONFLICT_CATEGORY_KINDS.get(category, "default")
