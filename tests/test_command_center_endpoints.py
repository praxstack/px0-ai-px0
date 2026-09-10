"""Tests for Command Center views and HTMX endpoints."""

import socketserver
import threading
import time
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer
from unittest.mock import patch, MagicMock
import pytest
from px0.web import server as web_server
from px0.web import views
from px0 import inbox as inbox_mod, triage as triage_mod


@pytest.fixture
def cc_env(tmp_path):
    home = tmp_path / ".px0"
    home.mkdir(parents=True)
    (home / "workflows").mkdir(parents=True)
    (home / ".state").mkdir(parents=True)
    (home / "runs").mkdir(parents=True)

    config = {
        "runs": {"storage": "filesystem", "path": str(home / "runs"), "dir": str(home / "runs")},
        "store": {"home": str(home)},
    }

    with socketserver.TCPServer(("127.0.0.1", 0), None) as s:
        port = s.server_address[1]

    handler = web_server.WebUIHandler
    handler.home = home
    handler.config = config

    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)

    base_url = f"http://127.0.0.1:{port}"
    yield {"home": home, "config": config, "base_url": base_url}

    httpd.shutdown()
    httpd.server_close()


def test_command_center_render(cc_env):
    home = cc_env["home"]
    base_url = cc_env["base_url"]
    config = cc_env["config"]

    # Put a test inbox entry using deliver
    inbox_mod.deliver(
        home,
        config,
        workflow_id="wf-test",
        run_id="run-1",
        text="## Test PR Review\nPlease review PR #42",
        source="github",
        attention=inbox_mod.NEEDS_ACTION,
    )

    # Fetch Command Center HTML
    with urllib.request.urlopen(f"{base_url}/") as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "Action Stream" in html
        assert "Test PR Review" in html
        assert "✓ Done" in html
        assert "⏱ Snooze" in html
        assert "Knowledge Base" in html


def test_triage_htmx_endpoints(cc_env):
    home = cc_env["home"]
    base_url = cc_env["base_url"]

    # Test triage done endpoint
    req = urllib.request.Request(f"{base_url}/htmx/triage/done?item_id=github:pr:99", method="POST", data=b"")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200

    data = triage_mod.load(home)
    assert "github:pr:99" in data
    assert data["github:pr:99"]["status"] == "done"

    # Test triage snooze endpoint
    req2 = urllib.request.Request(f"{base_url}/htmx/triage/snooze?item_id=slack:msg:100", method="POST", data=b"")
    with urllib.request.urlopen(req2) as resp:
        assert resp.status == 200

    data = triage_mod.load(home)
    assert "slack:msg:100" in data
    assert data["slack:msg:100"]["status"] == "snoozed"


def test_brain_ask_endpoint(cc_env):
    base_url = cc_env["base_url"]

    with patch("px0.ask.ask") as mock_ask:
        mock_ask.return_value = {
            "answer": "Our auth policy requires JWT tokens.",
            "passages": [MagicMock(path="guidelines/auth.md", text="Always use JWT tokens.", anchor="auth")],
            "run_id": "run-123"
        }
        with urllib.request.urlopen(f"{base_url}/htmx/brain/ask?q=auth+policy") as resp:
            assert resp.status == 200
            output = resp.read().decode()
            assert "Our auth policy requires JWT tokens" in output
            assert "Insert into Draft" in output


def test_reply_dispatch_endpoint(cc_env):
    base_url = cc_env["base_url"]

    with patch("tpt.messaging.slack.SlackMessaging.post_message") as mock_post:
        mock_post.return_value = MagicMock(id="msg-1")
        data = urllib.parse.urlencode({
            "item_id": "inbox:123",
            "source": "slack",
            "message": "Looks good to me!"
        }).encode()
        req = urllib.request.Request(f"{base_url}/htmx/reply/dispatch", data=data, method="POST")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            output = resp.read().decode()
            assert "Reply dispatched" in output

