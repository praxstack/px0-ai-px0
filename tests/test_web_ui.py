import os
import socketserver
import threading
import time
import urllib.request
import urllib.parse
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from px0 import (
    approvals as approvals_mod,
    authoring,
    config as config_mod,
    daemon as daemon_mod,
    inbox as inbox_mod,
    tools,
    workflow as workflow_mod,
)
from px0.web import server as web_server


@pytest.fixture
def web_test_env(tmp_path):
    home = tmp_path / ".px0"
    home.mkdir(parents=True)
    (home / "workflows").mkdir(parents=True)
    (home / "state").mkdir(parents=True)
    (home / "runs").mkdir(parents=True)
    (home / "logs").mkdir(parents=True)

    config = {
        "store": {"home": str(home)},
        "runs": {"storage": "filesystem", "path": str(home / "runs")},
        "logs": {"path": str(home / "logs")},
    }
    config_mod.save(home / "config.toml", config)

    # Create a test workflow
    wf_text = """---
description: Daily test workflow
trigger:
  schedule: "0 9 * * *"
enabled: true
---
echo "Hello from test"
"""
    (home / "workflows" / "daily-test.md").write_text(wf_text)

    # Pick an available port
    with socketserver.TCPServer(("127.0.0.1", 0), None) as s:
        port = s.server_address[1]

    handler = web_server.WebUIHandler
    handler.home = home
    handler.config = config

    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    time.sleep(0.1)

    base_url = f"http://127.0.0.1:{port}"
    yield {"home": home, "config": config, "base_url": base_url, "port": port}

    httpd.shutdown()
    httpd.server_close()


def test_static_assets(web_test_env):
    base_url = web_test_env["base_url"]
    
    # Test htmx.min.js
    with urllib.request.urlopen(f"{base_url}/static/htmx.min.js") as resp:
        assert resp.status == 200
        content = resp.read()
        assert len(content) > 1000
        assert resp.headers.get("Content-Type") == "application/javascript"

    # Test style.css
    with urllib.request.urlopen(f"{base_url}/static/style.css") as resp:
        assert resp.status == 200
        content = resp.read().decode()
        assert ":root" in content
        assert resp.headers.get("Content-Type") == "text/css"


def test_full_pages(web_test_env):
    base_url = web_test_env["base_url"]
    
    for path in ["/", "/needs-action", "/workflows", "/schedules", "/runs", "/daemon"]:
        with urllib.request.urlopen(f"{base_url}{path}") as resp:
            assert resp.status == 200
            html = resp.read().decode()
            assert "<!DOCTYPE html>" in html
            assert "px0" in html
            assert "/static/htmx.min.js" in html


def test_api_views(web_test_env):
    base_url = web_test_env["base_url"]

    # Dashboard view
    with urllib.request.urlopen(f"{base_url}/api/views/dashboard") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "Total Workflows" in html
        assert "daily-test" in html or "Active Schedules" in html

    # Workflows view
    with urllib.request.urlopen(f"{base_url}/api/views/workflows") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "daily-test" in html
        assert "ENABLED" in html

    # Schedules view
    with urllib.request.urlopen(f"{base_url}/api/views/schedules") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "0 9 * * *" in html
        assert "daily-test" in html

    # Daemon badge
    with urllib.request.urlopen(f"{base_url}/api/daemon/badge") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "daemon:" in html


def test_workflow_modals(web_test_env):
    base_url = web_test_env["base_url"]

    # Workflow detail modal
    with urllib.request.urlopen(f"{base_url}/api/workflows/daily-test") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "Daily test workflow" in html
        assert "modal-content" in html

    # Workflow run modal
    with urllib.request.urlopen(f"{base_url}/api/workflows/daily-test/run-modal") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "Run Workflow" in html

    # Schedule edit modal
    with urllib.request.urlopen(f"{base_url}/api/schedules/daily-test/edit") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "0 9 * * *" in html
        assert "Edit Schedule" in html


def test_workflow_toggle(web_test_env):
    base_url = web_test_env["base_url"]
    home = web_test_env["home"]

    # Toggle off
    req = urllib.request.Request(f"{base_url}/api/workflows/daily-test/toggle", method="POST", data=b"")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "DISABLED" in html

    wf = workflow_mod.load(home, "daily-test")
    assert wf.enabled is False

    # Toggle on
    req = urllib.request.Request(f"{base_url}/api/workflows/daily-test/toggle", method="POST", data=b"")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "ENABLED" in html

    wf = workflow_mod.load(home, "daily-test")
    assert wf.enabled is True


def test_schedule_update(web_test_env):
    base_url = web_test_env["base_url"]
    home = web_test_env["home"]

    data = urllib.parse.urlencode({"schedule": "*/15 * * * *"}).encode()
    req = urllib.request.Request(f"{base_url}/api/schedules/daily-test/update", method="POST", data=data)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "*/15 * * * *" in html

    wf = workflow_mod.load(home, "daily-test")
    assert wf.trigger.get("schedule") == "*/15 * * * *"


def test_daemon_tick(web_test_env):
    base_url = web_test_env["base_url"]
    req = urllib.request.Request(f"{base_url}/api/daemon/action?act=tick", method="POST", data=b"")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "Schedule tick completed" in html

def test_workflow_run_trigger(web_test_env):
    base_url = web_test_env["base_url"]
    data = urllib.parse.urlencode({}).encode()
    req = urllib.request.Request(f"{base_url}/api/workflows/daily-test/trigger", method="POST", data=data)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "Run initiated successfully" in html


def test_needs_action_view(web_test_env):
    """The single glance-view: a pending approval and a mix of needs_action
    and fyi inbox entries, grouped by source."""
    home, config = web_test_env["home"], web_test_env["config"]
    base_url = web_test_env["base_url"]

    approvals_mod.queue(home, run_id="r1", workflow_id="daily-test",
                        tool="slack.post_message", args={"channel": "#eng"})
    inbox_mod.deliver(home, config, workflow_id="daily-test", run_id="r2",
                      text="PR #42 waiting on your review", source="github",
                      attention=inbox_mod.NEEDS_ACTION)
    inbox_mod.deliver(home, config, workflow_id="daily-test", run_id="r3",
                      text="Friday digest posted", source="slack",
                      attention=inbox_mod.FYI)

    with urllib.request.urlopen(f"{base_url}/api/views/needs-action") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "Pending Approvals" in html
        assert "slack.post_message" in html
        assert "Needs your attention" in html
        assert "github" in html
        assert "FYI" in html

    with urllib.request.urlopen(f"{base_url}/api/needs-action/badge") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "needs action: 2" in html  # 1 pending approval + 1 needs_action entry


def test_needs_action_empty_state(web_test_env):
    base_url = web_test_env["base_url"]
    with urllib.request.urlopen(f"{base_url}/api/views/needs-action") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "Nothing waiting on you" in html


def test_approval_actions(web_test_env, monkeypatch):
    home, config = web_test_env["home"], web_test_env["config"]
    base_url = web_test_env["base_url"]
    monkeypatch.setattr(tools, "call", lambda *a: {"ok": True})

    approved = approvals_mod.queue(home, run_id="r1", workflow_id="daily-test",
                                   tool="slack.post_message", args={"channel": "#eng"})
    req = urllib.request.Request(
        f"{base_url}/api/approvals/{approved['id']}/approve", method="POST", data=b"")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
    assert approvals_mod.read(home, approved["id"])["status"] == approvals_mod.APPROVED

    rejected = approvals_mod.queue(home, run_id="r1", workflow_id="daily-test",
                                    tool="slack.post_message", args={"channel": "#eng"})
    data = urllib.parse.urlencode({"reason": "wrong channel"}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/approvals/{rejected['id']}/reject", method="POST", data=data)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
    resolved = approvals_mod.read(home, rejected["id"])
    assert resolved["status"] == approvals_mod.REJECTED
    assert resolved["detail"] == "wrong channel"


def test_inbox_mark_from_web(web_test_env):
    home, config = web_test_env["home"], web_test_env["config"]
    base_url = web_test_env["base_url"]
    entry = inbox_mod.deliver(home, config, workflow_id="daily-test", run_id="r1",
                              text="something", source="github",
                              attention=inbox_mod.NEEDS_ACTION)

    data = urllib.parse.urlencode({"status": "archived"}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/inbox/{entry['id']}/mark", method="POST", data=data)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
    assert inbox_mod.read_entry(home, entry["id"])["status"] == inbox_mod.ARCHIVED


def test_inbox_entry_detail_modal(web_test_env):
    home, config = web_test_env["home"], web_test_env["config"]
    base_url = web_test_env["base_url"]
    entry = inbox_mod.deliver(home, config, workflow_id="daily-test", run_id="r1",
                              text="something worth reading", source="github",
                              attention=inbox_mod.NEEDS_ACTION)

    with urllib.request.urlopen(f"{base_url}/api/inbox/{entry['id']}") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "something worth reading" in html
    # Opening it marks it read, same as `px0 inbox read`
    assert inbox_mod.read_entry(home, entry["id"])["status"] == inbox_mod.READ


def test_portal_route_returns_widgets(web_test_env, monkeypatch):
    """The deterministic-portal route (px0/portal.py) never touches a real
    network call in this test -- `tools.call` is monkeypatched, which also
    covers `portal.tools_mod.call` since it's the same module object."""
    base_url = web_test_env["base_url"]

    def fake_call(home, config, tool_id, args):
        if tool_id == "github.list_my_prs":
            return [{"title": "My open PR", "url": "https://x/1", "state": "open",
                     "updated_at": "2026-09-01T00:00:00Z"}]
        return []

    monkeypatch.setattr(tools, "call", fake_call)

    with urllib.request.urlopen(f"{base_url}/api/portal/github") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "Your open pull requests" in html
        assert "My open PR" in html
        assert "Needs your review" in html


def test_portal_route_persists_and_does_not_refetch(web_test_env, monkeypatch):
    """The whole point of the persistence layer: a first GET fetches live
    and writes output/portal/<app>.md; a second GET must read that file
    straight off disk, with no further tools.call."""
    home = web_test_env["home"]
    base_url = web_test_env["base_url"]
    call_count = {"n": 0}

    def fake_call(home_arg, config, tool_id, args):
        call_count["n"] += 1
        if tool_id == "linear.get_current_user":
            return {"id": "u1"}
        if tool_id == "linear.list_my_issues":
            return [{"title": "Fix bug"}]
        return []

    monkeypatch.setattr(tools, "call", fake_call)

    with urllib.request.urlopen(f"{base_url}/api/portal/linear") as resp:
        assert resp.status == 200
        first_html = resp.read().decode()
    assert "Fix bug" in first_html
    first_count = call_count["n"]
    assert first_count > 0
    assert (home / "output" / "portal" / "linear.md").exists()

    with urllib.request.urlopen(f"{base_url}/api/portal/linear") as resp:
        assert resp.status == 200
        second_html = resp.read().decode()
    assert call_count["n"] == first_count  # no new fetch
    assert "Fix bug" in second_html


def test_portal_refresh_route_forces_a_fresh_fetch(web_test_env, monkeypatch):
    home = web_test_env["home"]
    base_url = web_test_env["base_url"]
    responses = iter([
        [{"title": "First PR", "url": "https://x/1", "state": "open", "updated_at": "2026-09-01T00:00:00Z"}],
        [{"title": "Second PR", "url": "https://x/2", "state": "open", "updated_at": "2026-09-02T00:00:00Z"}],
    ])

    def fake_call(home_arg, config, tool_id, args):
        if tool_id == "github.list_my_prs":
            return next(responses)
        return []

    monkeypatch.setattr(tools, "call", fake_call)

    with urllib.request.urlopen(f"{base_url}/api/portal/github") as resp:
        assert "First PR" in resp.read().decode()

    req = urllib.request.Request(f"{base_url}/api/portal/github/refresh", method="POST", data=b"")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        html = resp.read().decode()
    assert "Second PR" in html
    assert "First PR" not in html
    assert "Second PR" in (home / "output" / "portal" / "github.md").read_text()


def test_portal_route_serves_a_workflow_written_file(web_test_env, monkeypatch):
    """A workflow writing output/portal/<app>.md directly must be served
    as-is, with no live tools.call at all."""
    home = web_test_env["home"]
    base_url = web_test_env["base_url"]

    def fail_call(*a, **k):
        raise AssertionError("tools.call must not be reached when the file already exists")

    portal_dir = home / "output" / "portal"
    portal_dir.mkdir(parents=True, exist_ok=True)
    (portal_dir / "slack.md").write_text("## Written by a workflow\n\n- hand-curated note\n")

    monkeypatch.setattr(tools, "call", fail_call)

    with urllib.request.urlopen(f"{base_url}/api/portal/slack") as resp:
        assert resp.status == 200
        html = resp.read().decode()
    assert "Written by a workflow" in html
    assert "hand-curated note" in html


def test_portal_route_unknown_app_404(web_test_env):
    base_url = web_test_env["base_url"]
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"{base_url}/api/portal/notarealapp")
    assert exc_info.value.code == 404


def test_needs_action_fragment_has_portal_placeholder(web_test_env):
    """The default-active app tab's live section fires eagerly on load; the
    placeholder + the JS that lazy-loads other tabs must both be present in
    the returned fragment, whether reached via `/` or the htmx partial."""
    base_url = web_test_env["base_url"]
    with urllib.request.urlopen(f"{base_url}/api/views/needs-action") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert 'id="portal-github"' in html
        assert "pxLoadPortal" in html
        assert "pxLoadPortal('github')" in html
    # "Other" never gets a portal placeholder -- it's scoped to the three
    # known apps px0 has real tooling for.
    assert 'id="portal-other"' not in html
