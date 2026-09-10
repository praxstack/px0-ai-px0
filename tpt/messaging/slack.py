"""
Slack Messaging Tool integration.

Implements BaseMessagingClient using Slack Web API via HTTP requests.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from tpt.messaging.base import (
    BaseMessagingClient,
    Channel,
    Message,
    Thread,
    User,
)
from tpt.messaging.exceptions import (
    AuthenticationError,
    ChannelNotFoundError,
    MessageNotFoundError,
    MessagingError,
    PermissionDeniedError,
    ProviderAPIError,
    RateLimitExceededError,
    ValidationError,
)

SLACK_API_BASE = "https://slack.com/api"


def _get_default_slack_token() -> Optional[str]:
    """Retrieve Slack token from environment, user config, or px0 credentials."""
    token = os.getenv("SLACK_BOT_TOKEN") or os.getenv("SLACK_TOKEN")
    if token:
        return token

    # Check local config file if present
    cfg_file = os.path.expanduser("~/.config/tpt_tokens.env")
    if os.path.isfile(cfg_file):
        try:
            with open(cfg_file) as f:
                for line in f:
                    if line.strip().startswith("export SLACK_BOT_TOKEN=") or line.strip().startswith("export SLACK_TOKEN="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass

    # Check px0 credentials file
    px0_creds = Path(os.getenv("PX0_HOME", "~/.px0")).expanduser() / ".state" / "credentials.toml"
    if px0_creds.is_file():
        try:
            import tomllib
            with open(px0_creds, "rb") as f:
                data = tomllib.load(f)
            slack_entry = data.get("slack", {})
            return slack_entry.get("token") or slack_entry.get("bot_token")
        except Exception:
            pass

    return None


def _parse_slack_timestamp(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        epoch = float(ts)
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    except (ValueError, TypeError):
        return None


class SlackMessaging(BaseMessagingClient):
    """Slack messaging client implementing BaseMessagingClient."""

    def __init__(
        self,
        token: Optional[str] = None,
        api_base: str = SLACK_API_BASE,
        timeout: int = 30,
    ):
        """
        Initialize SlackMessaging client.

        :param token: Slack Bot User OAuth Token or User OAuth Token (xoxb-... or xoxp-...).
        :param api_base: Base URL for Slack Web API.
        :param timeout: HTTP request timeout in seconds.
        """
        self.token = token or _get_default_slack_token()
        if not self.token:
            raise AuthenticationError(
                "Slack token is required. Set SLACK_BOT_TOKEN / SLACK_TOKEN or pass token parameter.",
                provider="Slack",
            )
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json; charset=utf-8",
            }
        )
        self._current_user: Optional[User] = None

    def _request(
        self,
        endpoint: str,
        method: str = "POST",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        headers = {}
        if method.upper() == "GET":
            # For GET requests Slack expects Content-Type not to force json body
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        try:
            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data if method.upper() != "GET" else None,
                headers=headers if headers else None,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise ProviderAPIError(f"Network error communicating with Slack: {e}", provider="Slack") from e

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            seconds = int(retry_after) if retry_after and retry_after.isdigit() else 1
            raise RateLimitExceededError(
                f"Slack rate limit exceeded. Retry after {seconds} seconds.",
                provider="Slack",
                retry_after=seconds,
                status_code=429,
            )

        try:
            data = resp.json()
        except ValueError as e:
            raise ProviderAPIError(
                f"Invalid JSON response from Slack: {resp.text[:200]}",
                provider="Slack",
                status_code=resp.status_code,
            ) from e

        if not data.get("ok"):
            err_code = data.get("error", "unknown_error")
            self._handle_slack_error(err_code, resp.status_code, data)

        return data

    def _handle_slack_error(self, err_code: str, status_code: int, data: Dict[str, Any]) -> None:
        msg = f"Slack API error: {err_code}"
        if err_code in ("not_authed", "invalid_auth", "account_inactive", "token_revoked", "token_expired"):
            raise AuthenticationError(msg, provider="Slack", status_code=status_code)
        if err_code in ("missing_scope", "not_allowed_token_type", "restricted_action", "user_is_restricted"):
            needed = data.get("needed", "")
            if needed:
                msg += f" (Missing scope: {needed})"
            raise PermissionDeniedError(msg, provider="Slack", status_code=status_code)
        if err_code in ("channel_not_found",):
            raise ChannelNotFoundError(msg, provider="Slack", status_code=status_code)
        if err_code in ("message_not_found", "thread_not_found"):
            raise MessageNotFoundError(msg, provider="Slack", status_code=status_code)
        if err_code in ("invalid_arguments", "invalid_form_data"):
            raise ValidationError(msg, provider="Slack", status_code=status_code)
        if err_code == "ratelimited":
            raise RateLimitExceededError(msg, provider="Slack", status_code=429)
        raise ProviderAPIError(msg, provider="Slack", status_code=status_code)

    def _parse_message(self, raw: Dict[str, Any], channel_id: str) -> Message:
        ts = raw.get("ts") or raw.get("timestamp") or ""
        text = raw.get("text", "")
        user_id = raw.get("user") or raw.get("bot_id")
        thread_id = raw.get("thread_ts")
        reactions = raw.get("reactions", [])
        permalink = raw.get("permalink")

        return Message(
            id=ts,
            channel_id=channel_id,
            text=text,
            user_id=user_id,
            thread_id=thread_id,
            timestamp=ts,
            created_at=_parse_slack_timestamp(ts),
            reactions=reactions,
            permalink=permalink,
            raw=raw,
        )

    def get_current_user(self) -> User:
        """Fetch authenticated user / bot identity via auth.test."""
        if self._current_user:
            return self._current_user

        data = self._request("auth.test")
        user_id = data.get("user_id") or data.get("bot_id") or ""
        user_name = data.get("user") or ""

        self._current_user = User(
            id=user_id,
            name=user_name,
            raw=data,
        )
        return self._current_user

    def list_channels(
        self,
        types: str = "public_channel,private_channel",
        limit: int = 100,
        **kwargs: Any,
    ) -> List[Channel]:
        """List accessible channels via conversations.list."""
        params = {
            "types": types,
            "limit": min(limit, 1000),
            "exclude_archived": True,
        }
        params.update(kwargs)

        data = self._request("conversations.list", method="GET", params=params)
        channels = []
        for ch in data.get("channels", []):
            channels.append(
                Channel(
                    id=ch.get("id", ""),
                    name=ch.get("name", ""),
                    is_private=ch.get("is_private", False),
                    is_im=ch.get("is_im", False),
                    topic=(ch.get("topic") or {}).get("value"),
                    member_count=ch.get("num_members"),
                    raw=ch,
                )
            )
        return channels

    def post_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: Optional[str] = None,
        **kwargs: Any,
    ) -> Message:
        """Post a message or reply in a thread via chat.postMessage."""
        payload: Dict[str, Any] = {
            "channel": channel_id,
            "text": text,
        }
        if thread_ts:
            payload["thread_ts"] = thread_ts
        payload.update(kwargs)

        data = self._request("chat.postMessage", method="POST", json_data=payload)
        raw_msg = data.get("message", {})
        # ensure channel is populated
        if "channel" not in raw_msg:
            raw_msg["channel"] = channel_id
        if "ts" not in raw_msg and "ts" in data:
            raw_msg["ts"] = data["ts"]

        return self._parse_message(raw_msg, channel_id)

    def get_thread(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 100,
        **kwargs: Any,
    ) -> Thread:
        """Follow and read all messages in a thread via conversations.replies."""
        params = {
            "channel": channel_id,
            "ts": thread_ts,
            "limit": min(limit, 1000),
        }
        params.update(kwargs)

        data = self._request("conversations.replies", method="GET", params=params)
        messages_raw = data.get("messages", [])
        if not messages_raw:
            raise MessageNotFoundError(f"Thread {thread_ts} not found in channel {channel_id}", provider="Slack")

        root_raw = messages_raw[0]
        root_msg = self._parse_message(root_raw, channel_id)

        replies = [self._parse_message(m, channel_id) for m in messages_raw[1:]]
        reply_count = root_raw.get("reply_count", len(replies))

        return Thread(
            id=thread_ts,
            channel_id=channel_id,
            root_message=root_msg,
            replies=replies,
            reply_count=reply_count,
            raw=data,
        )

    def get_mentions(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> List[Message]:
        """
        Get messages mentioning the specified user (or authenticated user).
        Uses search.messages or channel history scanning.
        """
        target_uid = user_id or self.get_current_user().id
        query = f"<@{target_uid}>"

        try:
            return self.search_messages(query=query, limit=limit, **kwargs)
        except (PermissionDeniedError, ProviderAPIError):
            # If search:read scope is unavailable, fall back to searching channels
            # the bot/user belongs to
            mentions: List[Message] = []
            channels = self.list_channels(limit=20)
            for ch in channels:
                if len(mentions) >= limit:
                    break
                try:
                    hist = self._request(
                        "conversations.history",
                        method="GET",
                        params={"channel": ch.id, "limit": 50},
                    )
                    for m in hist.get("messages", []):
                        if f"<@{target_uid}>" in m.get("text", ""):
                            mentions.append(self._parse_message(m, ch.id))
                            if len(mentions) >= limit:
                                break
                except Exception:
                    continue
            return mentions

    def search_messages(
        self,
        query: str,
        limit: int = 50,
        **kwargs: Any,
    ) -> List[Message]:
        """Search messages across workspace via search.messages."""
        params = {
            "query": query,
            "count": min(limit, 100),
            "sort": "timestamp",
            "sort_dir": "desc",
        }
        params.update(kwargs)

        data = self._request("search.messages", method="GET", params=params)
        matches = (data.get("messages") or {}).get("matches", [])

        out = []
        for match in matches:
            ch_id = (match.get("channel") or {}).get("id") or ""
            out.append(self._parse_message(match, ch_id))
            if len(out) >= limit:
                break
        return out

    def add_reaction(
        self,
        channel_id: str,
        timestamp: str,
        emoji: str,
        **kwargs: Any,
    ) -> bool:
        """Add emoji reaction via reactions.add."""
        clean_emoji = emoji.strip(":")
        payload = {
            "channel": channel_id,
            "timestamp": timestamp,
            "name": clean_emoji,
        }
        payload.update(kwargs)

        try:
            self._request("reactions.add", method="POST", json_data=payload)
            return True
        except MessagingError as e:
            if "already_reacted" in str(e):
                return True
            raise


# Alias
Slack = SlackMessaging
