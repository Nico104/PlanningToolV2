import re
import json
from pathlib import Path


def fix_termine(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    term = data.get("termine", [])
    pattern = re.compile(r'^[A-Za-z0-9]+_([0-9a-fA-F]{6,8})(?:_r\d+)?$')
    changed = 0
    for t in term:
        sid = t.get("serien_id", "") or ""
        if sid:
            continue
        tid = t.get("id", "")
        m = pattern.match(tid)
        if m:
            t["serien_id"] = m.group(1)
            changed += 1

    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


if __name__ == "__main__":
    p = Path("data/termine.json")
    if not p.exists():
        print("File not found:", p)
    else:
        n = fix_termine(p)
        print(f"Updated {n} termine with inferred serien_id")
