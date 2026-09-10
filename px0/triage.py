"""Item triage state management (.state/triage.json) for the unified command center."""

import json
from datetime import datetime, timezone
from pathlib import Path
from px0 import paths


def triage_path(home: Path) -> Path:
    return home / ".state" / "triage.json"


def load(home: Path) -> dict[str, dict]:
    """Loads current triage state mapping item_id -> metadata."""
    p = triage_path(home)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save(home: Path, data: dict[str, dict]) -> None:
    """Persists triage state data to disk."""
    p = triage_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def mark_done(home: Path, item_id: str) -> None:
    """Marks an item as completed/done."""
    data = load(home)
    data[item_id] = {
        "status": "done",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save(home, data)


def snooze(home: Path, item_id: str, until_iso: str | None = None) -> None:
    """Snoozes an item until a specific ISO timestamp."""
    data = load(home)
    data[item_id] = {
        "status": "snoozed",
        "until": until_iso,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save(home, data)


def is_visible(item_id: str, triage_map: dict[str, dict]) -> bool:
    """Determines if an item should be visible in the active inbox stream."""
    entry = triage_map.get(item_id)
    if not entry:
        return True
    status = entry.get("status")
    if status == "done":
        return False
    if status == "snoozed":
        until = entry.get("until")
        if until:
            try:
                dt = datetime.fromisoformat(until)
                if datetime.now(timezone.utc) < dt:
                    return False
            except Exception:
                return False
        else:
            return False
    return True
