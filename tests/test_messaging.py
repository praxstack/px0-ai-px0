"""Unit tests for messaging tools (mocked & offline)."""

import pytest
from unittest.mock import MagicMock

from tpt.messaging import (
    BaseMessagingClient,
    Channel,
    Message,
    Thread,
    User,
    SlackMessaging,
    get_messaging_client,
    register_messaging_client,
    AuthenticationError,
    ValidationError,
    RateLimitExceededError,
)


def test_messaging_factory_instantiation():
    slack = get_messaging_client("slack", token="xoxb-fake-token")
    assert isinstance(slack, SlackMessaging)

    with pytest.raises(ValidationError):
        get_messaging_client("unsupported_provider")


def test_custom_messaging_provider_registration():
    class CustomClient(BaseMessagingClient):
        def get_current_user(self): return User(id="u1", name="alice")
        def list_channels(self, **kwargs): return []
        def post_message(self, channel_id, text, **kwargs):
            return Message(id="1", channel_id=channel_id, text=text)
        def get_thread(self, channel_id, thread_ts, **kwargs):
            return Thread(id=thread_ts, channel_id=channel_id, root_message=Message(id="1", channel_id=channel_id, text="hi"))
        def get_mentions(self, **kwargs): return []
        def search_messages(self, query, **kwargs): return []
        def add_reaction(self, channel_id, timestamp, emoji, **kwargs): return True

    register_messaging_client("custom_msg", CustomClient)
    inst = get_messaging_client("custom_msg")
    assert isinstance(inst, CustomClient)
    assert inst.get_current_user().name == "alice"


def test_slack_missing_token():
    with pytest.raises(AuthenticationError):
        SlackMessaging(token="")


def test_slack_get_current_user():
    slack = SlackMessaging(token="xoxb-fake")
    slack.session = MagicMock()

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ok": True,
        "user_id": "U12345",
        "user": "botuser",
    }
    slack.session.request.return_value = mock_resp

    user = slack.get_current_user()
    assert user.id == "U12345"
    assert user.name == "botuser"


def test_slack_post_message_and_thread():
    slack = SlackMessaging(token="xoxb-fake")
    slack.session = MagicMock()

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ok": True,
        "ts": "1700000000.000100",
        "message": {
            "text": "Hello world",
            "user": "U12345",
            "ts": "1700000000.000100",
        },
    }
    slack.session.request.return_value = mock_resp

    msg = slack.post_message(channel_id="C123", text="Hello world", thread_ts="1700000000.000000")
    assert msg.channel_id == "C123"
    assert msg.text == "Hello world"
    assert msg.id == "1700000000.000100"


def test_slack_get_thread():
    slack = SlackMessaging(token="xoxb-fake")
    slack.session = MagicMock()

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ok": True,
        "messages": [
            {"ts": "1700000000.000100", "text": "Root message", "user": "U1", "reply_count": 1},
            {"ts": "1700000000.000200", "text": "Reply 1", "user": "U2", "thread_ts": "1700000000.000100"},
        ],
    }
    slack.session.request.return_value = mock_resp

    thread = slack.get_thread(channel_id="C123", thread_ts="1700000000.000100")
    assert thread.id == "1700000000.000100"
    assert thread.root_message.text == "Root message"
    assert len(thread.replies) == 1
    assert thread.replies[0].text == "Reply 1"


def test_slack_search_messages():
    slack = SlackMessaging(token="xoxb-fake")
    slack.session = MagicMock()

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ok": True,
        "messages": {
            "matches": [
                {
                    "ts": "1700000000.000300",
                    "text": "Incident resolved",
                    "user": "U3",
                    "channel": {"id": "C999"},
                }
            ]
        },
    }
    slack.session.request.return_value = mock_resp

    results = slack.search_messages(query="Incident")
    assert len(results) == 1
    assert results[0].text == "Incident resolved"
    assert results[0].channel_id == "C999"


def test_slack_add_reaction():
    slack = SlackMessaging(token="xoxb-fake")
    slack.session = MagicMock()

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    slack.session.request.return_value = mock_resp

    ok = slack.add_reaction(channel_id="C123", timestamp="1700000000.000100", emoji=":white_check_mark:")
    assert ok is True


def test_slack_rate_limited():
    slack = SlackMessaging(token="xoxb-fake")
    slack.session = MagicMock()

    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "5"}
    mock_resp.json.return_value = {"ok": False, "error": "ratelimited"}
    slack.session.request.return_value = mock_resp

    with pytest.raises(RateLimitExceededError) as exc_info:
        slack.list_channels()
    assert exc_info.value.retry_after == 5
