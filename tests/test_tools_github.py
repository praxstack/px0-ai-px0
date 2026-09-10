"""Unit coverage for the GitHub REST-proxy read tools added for the
deterministic portal (px0/portal.py). No existing test exercised
`_github_request`/`client.tools.proxy` before this file -- these tests
monkeypatch `tools._github_request` directly rather than extending
`FakeComposio` to fake the proxy's SDK response shape, since that shape
(`client.tools.proxy(...)`'s return type, distinct from `.execute()`'s) has
not been reverse-engineered against the installed Composio SDK yet."""

from datetime import datetime, timedelta, timezone

import pytest

from px0 import connect, credentials as creds_mod, tools


class _Stub:
    """Mimics the `.json()`/`.text` surface `_github_request`'s callers use."""

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def test_github_list_review_requests_happy_path(tmp_home, monkeypatch):
    calls = []

    def fake_request(ctx, method, path, **kw):
        calls.append((method, path, kw))
        if path == "/user":
            return _Stub({"login": "arpit"})
        if path == "/search/issues":
            return _Stub({"items": [
                {"title": "Fix bug", "html_url": "https://github.com/o/r/pull/1",
                 "state": "open", "updated_at": "2026-09-01T00:00:00Z"},
            ]})
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(tools, "_github_request", fake_request)

    result = tools.call(tmp_home, {}, "github.list_review_requests", {})
    assert result == [{"title": "Fix bug", "url": "https://github.com/o/r/pull/1",
                        "state": "open", "updated_at": "2026-09-01T00:00:00Z"}]

    _, search_path, search_kw = calls[1]
    assert search_path == "/search/issues"
    query = search_kw["params"]["q"]
    assert "review-requested:arpit" in query
    assert "state:open" in query
    assert "@me" not in query  # deliberately avoided -- see github_list_my_prs


def test_github_list_recent_activity_filters_by_since(tmp_home, monkeypatch):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def fake_request(ctx, method, path, **kw):
        if path == "/user":
            return _Stub({"login": "arpit"})
        if path == "/users/arpit/events":
            return _Stub([
                {"type": "PushEvent", "repo": {"name": "o/r"}, "created_at": recent,
                 "actor": {"login": "arpit"}, "payload": {"commits": [{"message": "fix"}]}},
                {"type": "PushEvent", "repo": {"name": "o/r"}, "created_at": old,
                 "actor": {"login": "arpit"}, "payload": {"commits": [{"message": "old fix"}]}},
            ])
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(tools, "_github_request", fake_request)

    result = tools.call(tmp_home, {}, "github.list_recent_activity", {"since": "-7d"})
    assert len(result) == 1
    assert result[0]["created_at"] == recent


def test_github_list_recent_activity_enriches_push_commits(tmp_home, monkeypatch):
    """The events feed's PushEvent carries before/head but no commit
    messages (a real, live-confirmed API gap) -- the tool recovers them via
    one compare call per push."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    compare_calls = []

    def fake_request(ctx, method, path, **kw):
        if path == "/user":
            return _Stub({"login": "arpit"})
        if path == "/users/arpit/events":
            return _Stub([
                {"type": "PushEvent", "repo": {"name": "o/r"}, "created_at": now,
                 "actor": {"login": "arpit"},
                 "payload": {"before": "aaa", "head": "bbb", "ref": "refs/heads/master"}},
            ])
        if path == "/repos/o/r/compare/aaa...bbb":
            compare_calls.append(path)
            return _Stub({"commits": [{"sha": "bbb", "commit": {"message": "fix bug"}}]})
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(tools, "_github_request", fake_request)

    result = tools.call(tmp_home, {}, "github.list_recent_activity", {})
    assert len(compare_calls) == 1
    assert result[0]["payload"]["commits"] == [{"sha": "bbb", "message": "fix bug"}]


def test_github_list_recent_activity_push_enrichment_failure_degrades_quietly(tmp_home, monkeypatch):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def fake_request(ctx, method, path, **kw):
        if path == "/user":
            return _Stub({"login": "arpit"})
        if path == "/users/arpit/events":
            return _Stub([
                {"type": "PushEvent", "repo": {"name": "o/r"}, "created_at": now,
                 "actor": {"login": "arpit"},
                 "payload": {"before": "0" * 40, "head": "bbb", "ref": "refs/heads/new-branch"}},
            ])
        if path.startswith("/repos/o/r/compare/"):
            raise tools.ConnectorError("github 404")
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(tools, "_github_request", fake_request)

    result = tools.call(tmp_home, {}, "github.list_recent_activity", {})
    assert result[0]["payload"]["commits"] == []  # degraded, not raised


def test_github_list_recent_activity_default_window(tmp_home, monkeypatch):
    def fake_request(ctx, method, path, **kw):
        if path == "/user":
            return _Stub({"login": "arpit"})
        if path == "/users/arpit/events":
            return _Stub([])
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(tools, "_github_request", fake_request)
    result = tools.call(tmp_home, {}, "github.list_recent_activity", {})
    assert result == []


def test_github_rest_tool_needs_connection(tmp_home, fake_composio):
    """No github connected_account: exercises `_github_request`'s own
    ConnectorNotConfigured path for real, not monkeypatched."""
    connect.setup_composio(tmp_home, "test_api_key")
    with pytest.raises(tools.ConnectorNotConfigured):
        tools.call(tmp_home, {}, "github.list_review_requests", {})
