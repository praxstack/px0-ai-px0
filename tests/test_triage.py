"""Tests for px0/triage.py."""

from datetime import datetime, timedelta, timezone
from px0 import triage


def test_triage_flow(tmp_path):
    assert triage.load(tmp_path) == {}

    # Test mark_done
    triage.mark_done(tmp_path, "github:pr:123")
    data = triage.load(tmp_path)
    assert "github:pr:123" in data
    assert data["github:pr:123"]["status"] == "done"
    assert not triage.is_visible("github:pr:123", data)
    assert triage.is_visible("github:pr:999", data)

    # Test snooze future
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    triage.snooze(tmp_path, "linear:issue:456", until_iso=future)
    data = triage.load(tmp_path)
    assert not triage.is_visible("linear:issue:456", data)

    # Test snooze past
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    triage.snooze(tmp_path, "slack:msg:789", until_iso=past)
    data = triage.load(tmp_path)
    assert triage.is_visible("slack:msg:789", data)
