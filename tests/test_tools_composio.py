import pytest
import argparse
from px0 import tools, connect, cli, credentials as creds_mod, builder as builder_mod, paths

def _setup_active_composio(home):
    connect.setup_composio(home, "test_api_key")
    creds = creds_mod.load(home)
    creds["composio"]["connected_accounts"] = {
        "calendar": "ca_testaccount",
        "gmail": "ca_testaccount",
        "slack": "ca_testaccount",
        "linear": "ca_testaccount",
    }
    creds_mod.save(home, creds)


# --- Unit Tests ---

def test_calendar_list_events_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"events": [{"summary": "Test Meeting"}]}

    res = tools.call(tmp_home, {}, "calendar.list_events", {"window": "yesterday"})
    assert res == {"events": [{"summary": "Test Meeting"}]}
    assert fake_composio.last_execute_slug == "GOOGLECALENDAR_EVENTS_LIST"
    assert "timeMin" in fake_composio.last_execute_args


def test_gmail_search_messages_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"messages": [{"id": "123"}]}

    res = tools.call(tmp_home, {}, "gmail.search_messages", {"query": "is:unread"})
    assert res == {"messages": [{"id": "123"}]}
    assert fake_composio.last_execute_slug == "GMAIL_FETCH_EMAILS"
    assert fake_composio.last_execute_args == {"query": "is:unread"}


def test_gmail_get_message_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"subject": "Hi"}

    res = tools.call(tmp_home, {}, "gmail.get_message", {"id": "123"})
    assert res == {"subject": "Hi"}
    assert fake_composio.last_execute_slug == "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID"
    assert fake_composio.last_execute_args == {"message_id": "123"}


def test_gmail_send_message_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"status": "sent"}

    res = tools.call(tmp_home, {}, "gmail.send_message", {"to": "a@b.com", "subject": "Hi", "body": "Hello"})
    assert res == {"status": "sent"}
    assert fake_composio.last_execute_slug == "GMAIL_SEND_EMAIL"
    assert fake_composio.last_execute_args == {
        "recipient_email": "a@b.com",
        "subject": "Hi",
        "body": "Hello"
    }


def test_slack_post_message_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"ok": True}

    res = tools.call(tmp_home, {}, "slack.post_message", {"channel": "#dev", "text": "Hi"})
    assert res == {"ok": True}
    assert fake_composio.last_execute_slug == "SLACK_SEND_MESSAGE"
    assert fake_composio.last_execute_args == {
        "channel": "#dev",
        "text": "Hi"
    }


def test_linear_create_issue_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"id": "issue_1", "url": "https://linear.app/x/issue/ENG-1"}

    res = tools.call(tmp_home, {}, "linear.create_issue",
                      {"team_id": "team_1", "title": "Fix bug", "priority": 2})
    assert res == {"id": "issue_1", "url": "https://linear.app/x/issue/ENG-1"}
    assert fake_composio.last_execute_slug == "LINEAR_CREATE_LINEAR_ISSUE"
    assert fake_composio.last_execute_args == {"team_id": "team_1", "title": "Fix bug", "priority": 2}


def test_linear_update_issue_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"id": "issue_1", "success": True}

    res = tools.call(tmp_home, {}, "linear.update_issue", {"issue_id": "issue_1", "title": "Fix bug (updated)"})
    assert res == {"id": "issue_1", "success": True}
    assert fake_composio.last_execute_slug == "LINEAR_UPDATE_ISSUE"
    assert fake_composio.last_execute_args == {"issue_id": "issue_1", "title": "Fix bug (updated)"}


def test_linear_get_current_user_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"id": "user_1", "name": "Arpit"}

    res = tools.call(tmp_home, {}, "linear.get_current_user", {})
    assert res == {"id": "user_1", "name": "Arpit"}
    assert fake_composio.last_execute_slug == "LINEAR_GET_CURRENT_USER"
    assert fake_composio.last_execute_args == {}


def test_linear_list_my_issues_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"issues": [{"title": "Fix bug"}]}

    res = tools.call(tmp_home, {}, "linear.list_my_issues", {"assignee_id": "user_1"})
    assert res == {"issues": [{"title": "Fix bug"}]}
    assert fake_composio.last_execute_slug == "LINEAR_LIST_LINEAR_ISSUES"
    assert fake_composio.last_execute_args == {"assignee_id": "user_1"}


def test_linear_list_my_issues_omits_unset_project(tmp_home, fake_composio):
    """project_id must not appear as an empty string when the caller didn't pass one."""
    _setup_active_composio(tmp_home)
    tools.call(tmp_home, {}, "linear.list_my_issues", {"assignee_id": "user_1"})
    assert "project_id" not in fake_composio.last_execute_args


def test_slack_list_conversations_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"channels": [{"id": "C1", "name": "eng"}]}

    res = tools.call(tmp_home, {}, "slack.list_conversations",
                      {"exclude_archived": True, "types": "public_channel", "limit": 50})
    assert res == {"channels": [{"id": "C1", "name": "eng"}]}
    assert fake_composio.last_execute_slug == "SLACK_LIST_CONVERSATIONS"
    assert fake_composio.last_execute_args == {
        "exclude_archived": True, "types": "public_channel", "limit": 50
    }


def test_slack_fetch_conversation_history_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"messages": [{"text": "hi", "ts": "1.0"}]}

    res = tools.call(tmp_home, {}, "slack.fetch_conversation_history",
                      {"channel": "C1", "oldest": "0", "limit": 20})
    assert res == {"messages": [{"text": "hi", "ts": "1.0"}]}
    assert fake_composio.last_execute_slug == "SLACK_FETCH_CONVERSATION_HISTORY"
    assert fake_composio.last_execute_args == {"channel": "C1", "oldest": "0", "limit": 20}


def test_slack_search_messages_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"messages": {"matches": [{"text": "hey <@U1>"}]}}

    res = tools.call(tmp_home, {}, "slack.search_messages", {"query": "<@U1>", "count": 20})
    assert res == {"messages": {"matches": [{"text": "hey <@U1>"}]}}
    assert fake_composio.last_execute_slug == "SLACK_SEARCH_MESSAGES"
    assert fake_composio.last_execute_args == {"query": "<@U1>", "count": 20}


def test_slack_whoami_happy_path(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.execute_response = {"user": {"id": "U1"}, "ok": True}

    res = tools.call(tmp_home, {}, "slack.whoami", {})
    assert res == {"user": {"id": "U1"}, "ok": True}
    assert fake_composio.last_execute_slug == "SLACK_RETRIEVE_A_USER_S_IDENTITY_DETAILS"


def test_slack_whoami_missing_scope_raises_connector_error(tmp_home, fake_composio):
    """Models the real, observed failure: a 200 response with successful:false,
    distinct from an HTTP-level failure (fail_status_code)."""
    _setup_active_composio(tmp_home)
    fake_composio.execute_successful = False
    fake_composio.execute_error = "Slack API error: missing_scope. Required scope: identity.basic"

    with pytest.raises(tools.ConnectorError, match="missing_scope"):
        tools.call(tmp_home, {}, "slack.whoami", {})


def test_unconfigured_raises_connector_not_configured(tmp_home, fake_composio):
    # No credentials at all
    with pytest.raises(tools.ConnectorNotConfigured):
        tools.call(tmp_home, {}, "slack.post_message", {"channel": "#dev", "text": "Hi"})


def test_unconnected_app_raises_connector_not_configured(tmp_home, fake_composio):
    # Credentials exist but app is not in connected_accounts
    connect.setup_composio(tmp_home, "test_api_key")
    with pytest.raises(tools.ConnectorNotConfigured):
        tools.call(tmp_home, {}, "slack.post_message", {"channel": "#dev", "text": "Hi"})


def test_initiated_connection_raises_connector_not_configured(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.status = "INITIATED"
    with pytest.raises(tools.ConnectorNotConfigured, match="never completed"):
        tools.call(tmp_home, {}, "slack.post_message", {"channel": "#dev", "text": "Hi"})


def test_failed_connection_raises_connector_not_configured(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.status = "FAILED"
    with pytest.raises(tools.ConnectorNotConfigured, match="is FAILED, not ACTIVE"):
        tools.call(tmp_home, {}, "slack.post_message", {"channel": "#dev", "text": "Hi"})


def test_tool_failure_raises_connector_error(tmp_home, fake_composio):
    _setup_active_composio(tmp_home)
    fake_composio.fail_status_code = 500
    with pytest.raises(tools.ConnectorError):
        tools.call(tmp_home, {}, "slack.post_message", {"channel": "#dev", "text": "Hi"})


# --- Integration Tests ---

def test_there_is_no_connect_command(tmp_home):
    """Apps authorize themselves, so no per-app connect verb should exist."""
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["connect", "gmail"])
    assert not hasattr(cli, "cmd_connect")


def test_unconnected_tool_call_mints_its_own_auth_link(tmp_home, fake_composio):
    """The replacement for `px0 connect gmail`: the tool that needs gmail
    prepares gmail's authorization itself and hands back the URL."""
    connect.setup_composio(tmp_home, "test_api_key")

    with pytest.raises(tools.ConnectorNotConfigured) as exc:
        tools.call(tmp_home, {}, "gmail.send_message",
                   {"to": "a@b.com", "subject": "Hi", "body": "Hello"})

    message = str(exc.value)
    assert "not connected yet" in message
    assert "https://backend.composio.dev/redirect-mock" in message
    assert "px0 connect" not in message

    # and the connected_account it created is cached for the follow-up call
    creds = creds_mod.load(tmp_home)
    assert creds["composio"]["connected_accounts"]["gmail"] == "ca_testaccount"


def test_auth_link_failure_is_reported_not_swallowed(tmp_home, fake_composio, monkeypatch):
    """If the link can't even be prepared, say why instead of dangling a dead URL."""
    connect.setup_composio(tmp_home, "test_api_key")
    monkeypatch.setattr(
        connect, "connect_composio_app",
        lambda h, app: (_ for _ in ()).throw(ValueError("403 insufficient permissions")),
    )

    with pytest.raises(tools.ConnectorNotConfigured, match="403 insufficient permissions"):
        tools.call(tmp_home, {}, "slack.post_message", {"channel": "#dev", "text": "Hi"})


def test_missing_api_key_points_at_config_composio(tmp_home):
    with pytest.raises(tools.ConnectorNotConfigured, match="px0 config composio"):
        tools.call(tmp_home, {}, "slack.post_message", {"channel": "#dev", "text": "Hi"})


def _new_args(**over):
    """Namespace for `cli._build_workflow`, defaulting to the non-interactive path."""
    base = dict(yes=True, id="test-id", no_clarify=True, no_discover=True)
    base.update(over)
    return argparse.Namespace(**base)


def test_cmd_new_authorizes_what_the_plan_needs_and_still_writes_it(
        tmp_home, fake_composio, monkeypatch, capsys):
    """A pending consent must not throw away the plan.

    Re-running `px0 workflows new` would repeat the clarify, search, selection, and
    planning passes to arrive at the same file, so the file is written and the
    pending authorization is reported.
    """
    monkeypatch.setattr(cli, "_ctx", lambda: (tmp_home, {}))
    connect.setup_composio(tmp_home, "test_api_key")

    fake_plan = builder_mod.Plan(
        trigger={"manual": True}, inputs=[], tools=["slack.post_message"],
        output={"target": "stdout"}, body="Send message", description="test flow",
        raw={"tools": ["slack.post_message"], "description": "test flow"},
    )
    monkeypatch.setattr(builder_mod, "generate_plan", lambda *a, **kw: fake_plan)

    cli._build_workflow(tmp_home, {}, "test description", _new_args(), existing_id=None)

    out = capsys.readouterr().out
    assert "authorization needed" in out
    assert "slack" in out
    assert "consent" in out
    assert "https://backend.composio.dev/redirect-mock" in out
    assert "authorization pending" in out
    assert (paths.workflows_dir(tmp_home) / "test-id.md").exists()


def test_cmd_new_skips_authorization_when_already_active(
        tmp_home, fake_composio, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_ctx", lambda: (tmp_home, {}))
    connect.setup_composio(tmp_home, "test_api_key")
    creds = creds_mod.load(tmp_home)
    creds["composio"]["connected_accounts"] = {"slack": "ca_testaccount"}
    creds_mod.save(tmp_home, creds)
    fake_composio.status = "ACTIVE"

    fake_plan = builder_mod.Plan(
        trigger={"manual": True}, inputs=[], tools=["slack.post_message"],
        output={"target": "stdout"}, body="Send message", description="test flow",
        raw={"tools": ["slack.post_message"]},
    )
    monkeypatch.setattr(builder_mod, "generate_plan", lambda *a, **kw: fake_plan)

    cli._build_workflow(tmp_home, {}, "test description", _new_args(), existing_id=None)

    out = capsys.readouterr().out
    assert "already authorized" in out
    assert "authorization needed" not in out
    assert "authorization pending" not in out


def test_tool_slugs_and_args_match_composio_schemas():
    """Guards the slug/argument names against silent drift.

    Every slug here was confirmed to return 200 from GET /api/v3/tools/{slug},
    and every argument key below appears in that tool's own input_parameters
    schema. GMAIL_GET_EMAIL and a slack `message` key both looked plausible and
    were both wrong -- the catalogue is the only authority. linear.* confirmed
    the same way on 2026-09-10 (LINEAR_CREATE_LINEAR_ISSUE requires team_id and
    title; LINEAR_UPDATE_ISSUE requires issue_id and at least one other field).
    The deterministic-portal reads (linear.get_current_user/list_my_issues,
    slack.list_conversations/fetch_conversation_history/search_messages/whoami)
    were confirmed the same way, also 2026-09-10 -- SLACK_RETRIEVE_A_USER_S_-
    IDENTITY_DETAILS's schema resolves fine but execution fails with
    missing_scope (identity.basic) on px0's default Composio-managed Slack
    auth; see px0/portal.py's mentions widget for how that's handled.
    """
    assert tools._TOOL_SLUGS == {
        "calendar.list_events": "GOOGLECALENDAR_EVENTS_LIST",
        "gmail.search_messages": "GMAIL_FETCH_EMAILS",
        "gmail.get_message": "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
        "gmail.send_message": "GMAIL_SEND_EMAIL",
        "slack.post_message": "SLACK_SEND_MESSAGE",
        "linear.create_issue": "LINEAR_CREATE_LINEAR_ISSUE",
        "linear.update_issue": "LINEAR_UPDATE_ISSUE",
        "linear.get_current_user": "LINEAR_GET_CURRENT_USER",
        "linear.list_my_issues": "LINEAR_LIST_LINEAR_ISSUES",
        "slack.list_conversations": "SLACK_LIST_CONVERSATIONS",
        "slack.fetch_conversation_history": "SLACK_FETCH_CONVERSATION_HISTORY",
        "slack.search_messages": "SLACK_SEARCH_MESSAGES",
        "slack.whoami": "SLACK_RETRIEVE_A_USER_S_IDENTITY_DETAILS",
    }
    # Every registry tool backed by Composio has a slug.
    composio_tools = {
        tid for tid, spec in tools.REGISTRY.items()
        if spec.provider in ("calendar", "gmail", "slack", "linear")
    }
    assert composio_tools == set(tools._TOOL_SLUGS)


def test_tools_list_works_without_an_initialized_store(monkeypatch, capsys):
    """`px0 tools list` is how you find out what px0 can do -- before `px0 init`."""
    import argparse
    monkeypatch.setattr(cli, "_ctx", lambda *a, **kw: pytest.fail("must not need a store"))

    cli.cmd_tools(argparse.Namespace(tools_cmd="list", service=None, status=False, json=False))

    out = capsys.readouterr().out
    assert "slack.post_message" in out
    assert "write" in out


def test_tools_list_status_reports_per_provider_authorization(tmp_home, fake_composio, monkeypatch, capsys):
    import argparse
    connect.setup_composio(tmp_home, "test_api_key")
    creds = creds_mod.load(tmp_home)
    creds["composio"]["connected_accounts"] = {"gmail": "ca_testaccount"}
    creds_mod.save(tmp_home, creds)
    fake_composio.status = "ACTIVE"
    monkeypatch.setattr(cli, "_ctx", lambda *a, **kw: (tmp_home, {}))

    cli.cmd_tools(argparse.Namespace(tools_cmd="list", service=None, status=True, json=False))

    out = capsys.readouterr().out
    assert "ready" in out                    # gmail is authorized
    assert "not authorized" in out           # slack/github/calendar are not
    assert "not authorized yet:" in out      # and the footer names them
