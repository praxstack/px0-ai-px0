"""Unit coverage for px0/portal.py's deterministic, non-LLM per-app
snapshots. `tools_mod.call` (the primitive portal.py calls under the hood --
the same one approvals.approve() uses to execute an approved write) is
monkeypatched to canned per-tool-id data, so these tests never touch a real
network call."""

import pytest

from px0 import portal, tools


def _calls_recorder(monkeypatch, responses):
    """Monkeypatches portal.tools_mod.call to dispatch on tool_id, recording
    every (tool_id, args) call. `responses` maps tool_id -> a value, an
    exception instance to raise, or a callable(args) -> value/raises."""
    calls = []

    def fake_call(home, config, tool_id, args):
        calls.append((tool_id, args))
        resp = responses.get(tool_id)
        if isinstance(resp, Exception):
            raise resp
        if callable(resp):
            return resp(args)
        return resp

    monkeypatch.setattr(portal.tools_mod, "call", fake_call)
    return calls


# --- github ------------------------------------------------------------

def test_github_snapshot_widget_shape(monkeypatch):
    _calls_recorder(monkeypatch, {
        "github.list_my_prs": [
            {"title": "Open PR", "url": "https://x/1", "state": "open", "updated_at": "2026-09-01T00:00:00Z"},
            {"title": "Closed PR", "url": "https://x/2", "state": "closed", "updated_at": "2026-09-01T00:00:00Z"},
        ],
        "github.list_review_requests": [
            {"title": "Please review", "url": "https://x/3", "state": "open", "updated_at": "2026-09-01T00:00:00Z"},
        ],
        "github.list_recent_activity": [
            {"type": "PushEvent", "repo": "o/r", "created_at": "2026-09-01T00:00:00Z", "actor": "me",
             "payload": {"commits": [{"message": "fix bug\n\nmore detail"}]}},
            {"type": "SomeUnknownEvent", "repo": "o/r", "created_at": "2026-09-01T00:00:00Z", "actor": "me",
             "payload": {}},
        ],
    })

    widgets = portal.github_snapshot(None, {})
    assert [w.id for w in widgets] == [
        "github.open_prs", "github.needs_review", "github.recent_commits", "github.activity",
    ]

    open_prs = widgets[0]
    assert open_prs.error is None and open_prs.connect_url is None
    assert [i.title for i in open_prs.items] == ["Open PR"]  # closed PR filtered out

    needs_review = widgets[1]
    assert [i.title for i in needs_review.items] == ["Please review"]

    commits = widgets[2]
    assert [i.title for i in commits.items] == ["fix bug"]  # first line only

    activity = widgets[3]
    assert len(activity.items) == 2
    assert "pushed 1 commit(s)" in activity.items[0].title
    assert "SomeUnknownEvent" in activity.items[1].title  # unrecognized type falls back, not dropped


def test_github_snapshot_shares_one_activity_fetch(monkeypatch):
    calls = _calls_recorder(monkeypatch, {
        "github.list_my_prs": [],
        "github.list_review_requests": [],
        "github.list_recent_activity": [],
    })
    portal.github_snapshot(None, {})
    activity_calls = [c for c in calls if c[0] == "github.list_recent_activity"]
    assert len(activity_calls) == 1  # recent_commits and activity share the one fetch


def test_github_snapshot_one_widget_failing_does_not_blank_others(monkeypatch):
    _calls_recorder(monkeypatch, {
        "github.list_my_prs": tools.ConnectorNotConfigured("github is not connected yet",
                                                             redirect_url="https://connect/github"),
        "github.list_review_requests": [],
        "github.list_recent_activity": [],
    })
    widgets = portal.github_snapshot(None, {})
    assert len(widgets) == 4
    assert widgets[0].connect_url == "https://connect/github"
    assert widgets[0].items is None
    assert widgets[1].items == []  # unaffected by widget 0's failure


def test_widget_bare_exception_becomes_error_not_a_crash(monkeypatch):
    _calls_recorder(monkeypatch, {
        "github.list_my_prs": KeyError("boom"),
        "github.list_review_requests": [],
        "github.list_recent_activity": [],
    })
    widgets = portal.github_snapshot(None, {})
    assert len(widgets) == 4
    assert widgets[0].error is not None
    assert widgets[0].items is None


# --- linear --------------------------------------------------------------

def test_linear_snapshot_passes_resolved_assignee_id(monkeypatch):
    calls = _calls_recorder(monkeypatch, {
        "linear.get_current_user": {"id": "user_1", "name": "Arpit"},
        "linear.list_my_issues": {"issues": [
            {"title": "Fix bug", "state": {"name": "In Progress"}, "url": "https://linear/x", "updatedAt": "2026-09-01T00:00:00Z"},
        ]},
    })
    widgets = portal.linear_snapshot(None, {})
    assert len(widgets) == 1
    assert widgets[0].id == "linear.assigned_to_you"
    assert [i.title for i in widgets[0].items] == ["Fix bug"]
    assert widgets[0].items[0].subtitle == "In Progress"

    list_call = [c for c in calls if c[0] == "linear.list_my_issues"][0]
    assert list_call[1] == {"assignee_id": "user_1"}


def test_linear_snapshot_handles_bare_list_response(monkeypatch):
    _calls_recorder(monkeypatch, {
        "linear.get_current_user": {"id": "user_1"},
        "linear.list_my_issues": [{"title": "Bare list issue"}],
    })
    widgets = portal.linear_snapshot(None, {})
    assert [i.title for i in widgets[0].items] == ["Bare list issue"]


def test_linear_snapshot_not_connected(monkeypatch):
    _calls_recorder(monkeypatch, {
        "linear.get_current_user": tools.ConnectorNotConfigured(
            "linear is not connected yet", redirect_url="https://connect/linear"),
    })
    widgets = portal.linear_snapshot(None, {})
    assert widgets[0].connect_url == "https://connect/linear"


# --- slack -----------------------------------------------------------------

def test_slack_mentions_not_connected_shows_connect_prompt(monkeypatch):
    _calls_recorder(monkeypatch, {
        "slack.list_conversations": [],
        "slack.whoami": tools.ConnectorNotConfigured("slack is not connected yet",
                                                       redirect_url="https://connect/slack"),
    })
    widgets = portal.slack_snapshot(None, {})
    mentions = [w for w in widgets if w.id == "slack.mentions"][0]
    assert mentions.connect_url == "https://connect/slack"


def test_slack_mentions_missing_scope_shows_specific_message(monkeypatch):
    """The real, observed failure: connected, but missing identity.basic."""
    _calls_recorder(monkeypatch, {
        "slack.list_conversations": [],
        "slack.whoami": tools.ConnectorError("Composio execution failed -> missing_scope: identity.basic"),
    })
    widgets = portal.slack_snapshot(None, {})
    mentions = [w for w in widgets if w.id == "slack.mentions"][0]
    assert mentions.connect_url is None
    assert "identity access" in mentions.error
    assert "px0 tools list --status" in mentions.error


def test_slack_mentions_happy_path_queries_own_mention(monkeypatch):
    calls = _calls_recorder(monkeypatch, {
        "slack.list_conversations": [],
        "slack.whoami": {"user": {"id": "U123"}},
        "slack.search_messages": {"messages": {"matches": [
            {"text": "hey <@U123> check this", "channel": {"name": "eng"}, "permalink": "https://slack/x"},
        ]}},
    })
    widgets = portal.slack_snapshot(None, {})
    mentions = [w for w in widgets if w.id == "slack.mentions"][0]
    assert [i.title for i in mentions.items] == ["hey <@U123> check this"]

    search_call = [c for c in calls if c[0] == "slack.search_messages"][0]
    assert search_call[1]["query"] == "<@U123>"


def test_slack_recent_activity_sorted_newest_first(monkeypatch):
    _calls_recorder(monkeypatch, {
        "slack.list_conversations": [{"id": "C1", "name": "eng"}],
        "slack.fetch_conversation_history": {"messages": [
            {"text": "older", "ts": "1000.0"},
            {"text": "newer", "ts": "2000.0"},
        ]},
        "slack.whoami": {"user": {"id": "U1"}},
        "slack.search_messages": {"messages": {"matches": []}},
    })
    widgets = portal.slack_snapshot(None, {})
    activity = [w for w in widgets if w.id == "slack.recent_activity"][0]
    assert [i.title for i in activity.items] == ["newer", "older"]
    assert activity.items[0].subtitle == "#eng"


def test_slack_recent_activity_skips_blank_messages(monkeypatch):
    _calls_recorder(monkeypatch, {
        "slack.list_conversations": [{"id": "C1", "name": "eng"}],
        "slack.fetch_conversation_history": {"messages": [{"text": "   ", "ts": "1000.0"}]},
        "slack.whoami": {"user": {"id": "U1"}},
        "slack.search_messages": {"messages": {"matches": []}},
    })
    widgets = portal.slack_snapshot(None, {})
    activity = [w for w in widgets if w.id == "slack.recent_activity"][0]
    assert activity.items == []


def test_slack_recent_activity_one_bad_channel_does_not_blank_widget(monkeypatch):
    """Observed live: SLACK_FETCH_CONVERSATION_HISTORY can fail with
    channel_not_found for one conversation in an otherwise-fine list."""
    def history(args):
        if args["channel"] == "C_BAD":
            raise tools.ConnectorError("Composio execution failed -> Slack API error: channel_not_found")
        return {"messages": [{"text": "hello", "ts": "1000.0"}]}

    _calls_recorder(monkeypatch, {
        "slack.list_conversations": [{"id": "C_BAD", "name": "broken"}, {"id": "C1", "name": "eng"}],
        "slack.fetch_conversation_history": history,
        "slack.whoami": {"user": {"id": "U1"}},
        "slack.search_messages": {"messages": {"matches": []}},
    })
    widgets = portal.slack_snapshot(None, {})
    activity = [w for w in widgets if w.id == "slack.recent_activity"][0]
    assert activity.error is None
    assert [i.title for i in activity.items] == ["hello"]


# --- dispatch ----------------------------------------------------------

def test_snapshot_dispatches_by_app(monkeypatch):
    _calls_recorder(monkeypatch, {
        "linear.get_current_user": {"id": "u1"},
        "linear.list_my_issues": [],
    })
    widgets = portal.snapshot("linear", None, {})
    assert widgets[0].id == "linear.assigned_to_you"


def test_snapshot_unknown_app_raises():
    with pytest.raises(ValueError):
        portal.snapshot("notarealapp", None, {})


# --- persistence -------------------------------------------------------

def test_to_markdown_renders_each_widget_state():
    widgets = [
        portal.PortalWidget("app.items", "Some items",
                             items=[portal.PortalItem("Fix bug", url="https://x/1", time="2d ago")]),
        portal.PortalWidget("app.connect", "Needs connecting", connect_url="https://connect/x"),
        portal.PortalWidget("app.broken", "Broken", error="something failed"),
        portal.PortalWidget("app.empty", "Empty", items=[], empty_message="Nothing here."),
    ]
    md = portal.to_markdown(widgets)
    assert "## Some items" in md
    assert "[Fix bug](https://x/1) (2d ago)" in md
    assert "[Connect](https://connect/x)" in md
    assert "something failed" in md
    assert "Nothing here." in md


def test_portal_path_lives_under_output_portal(tmp_home):
    p = portal.portal_path(tmp_home, "github")
    assert p == tmp_home / "output" / "portal" / "github.md"


def test_load_returns_none_when_nothing_written_yet(tmp_home):
    text, mtime = portal.load("github", tmp_home)
    assert text is None and mtime is None


def test_refresh_writes_the_file_and_load_reads_it_back(monkeypatch, tmp_home):
    _calls_recorder(monkeypatch, {
        "linear.get_current_user": {"id": "u1"},
        "linear.list_my_issues": [{"title": "Fix bug"}],
    })
    written = portal.refresh("linear", tmp_home, {})
    assert "Fix bug" in written
    assert portal.portal_path(tmp_home, "linear").exists()

    text, mtime = portal.load("linear", tmp_home)
    assert text == written
    assert mtime == portal.portal_path(tmp_home, "linear").stat().st_mtime


def test_load_or_refresh_only_fetches_once(monkeypatch, tmp_home):
    """The whole point: a second call must not touch tools.call again."""
    calls = _calls_recorder(monkeypatch, {
        "linear.get_current_user": {"id": "u1"},
        "linear.list_my_issues": [],
    })
    text1, mtime1 = portal.load_or_refresh("linear", tmp_home, {})
    first_call_count = len(calls)
    assert first_call_count > 0  # the first open did fetch live

    text2, mtime2 = portal.load_or_refresh("linear", tmp_home, {})
    assert len(calls) == first_call_count  # the second did not
    assert text2 == text1
    assert mtime2 == mtime1


def test_load_or_refresh_picks_up_a_workflow_written_file(monkeypatch, tmp_home):
    """A workflow writing output/portal/<app>.md directly (the same path
    portal.refresh() uses) must be served as-is, with no live call at all --
    "let workflows write to them"."""
    calls = _calls_recorder(monkeypatch, {})  # tools.call must never be reached

    path = portal.portal_path(tmp_home, "slack")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("## Written by a workflow\n\n- something a workflow decided to say\n")

    text, mtime = portal.load_or_refresh("slack", tmp_home, {})
    assert "Written by a workflow" in text
    assert calls == []


def test_refresh_overwrites_a_workflow_written_file(monkeypatch, tmp_home):
    """Last write wins -- the same contract every other output/ file has."""
    path = portal.portal_path(tmp_home, "slack")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("## Old content\n")

    _calls_recorder(monkeypatch, {
        "slack.list_conversations": [],
        "slack.whoami": tools.ConnectorNotConfigured("slack is not connected yet"),
    })
    portal.refresh("slack", tmp_home, {})
    assert "Old content" not in path.read_text()
