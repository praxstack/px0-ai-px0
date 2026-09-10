"""Deterministic, non-LLM per-app snapshots for the needs-action dashboard,
persisted as markdown under `output/portal/<app>.md`.

Not every fact needs a workflow: `github_snapshot`/`linear_snapshot`/
`slack_snapshot` call `tools.call()` directly -- the same primitive
`approvals.approve()` uses to execute an approved write -- and normalize
whatever comes back into one small common shape. Nothing here mutates
anything (every tool called from this module is `is_write=False`) and
nothing here talks to an LLM.

`refresh()` fetches live and overwrites the app's markdown file; `load()`
reads whatever is already there without touching the network;
`load_or_refresh()` -- what a page view calls -- only fetches live the first
time a file doesn't exist yet, otherwise it's a plain file read. The file is
deliberately *not* px0's to own exclusively: a workflow can write the exact
same path itself (`output: {target: file, path: "output/portal/<app>.md"}`,
or the `file.write` tool) to replace the raw listing with something more
curated -- last write wins, the same contract every other file `output/`
already has. Workflows remain the way to get an *opinion* about this data (a
digest, a triage, a nudge); a fresh `refresh()` only ever answers "what does
the app say right now."
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from px0 import paths, tools as tools_mod


@dataclass
class PortalItem:
    title: str
    subtitle: str = ""
    url: str | None = None
    time: str | None = None


@dataclass
class PortalWidget:
    id: str
    title: str
    items: list[PortalItem] | None = None
    error: str | None = None
    connect_url: str | None = None
    empty_message: str = "Nothing here."


def _fetch(id: str, title: str, fn: Callable[[], list[PortalItem]],
           empty_message: str = "Nothing here.") -> PortalWidget:
    """Runs one widget's fetch, never letting it raise past this point -- a
    broken, unconnected, or under-scoped widget must not blank the rest of
    its app tab."""
    try:
        items = fn()
    except tools_mod.ConnectorNotConfigured as e:
        return PortalWidget(id, title, connect_url=e.redirect_url,
                             error=None if e.redirect_url else str(e))
    except tools_mod.ConnectorError as e:
        return PortalWidget(id, title, error=str(e))
    except Exception as e:
        return PortalWidget(id, title, error=f"unexpected error: {e}")
    return PortalWidget(id, title, items=items, empty_message=empty_message)


def _rel_time(iso: str) -> str | None:
    """A short "how long ago" label for a UTC ISO timestamp, or None if it
    doesn't parse -- callers render a missing time as simply absent."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    if secs < 3600:
        return f"{max(1, int(secs // 60))}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


# --- github ------------------------------------------------------------

_GITHUB_EVENT_LABELS: dict[str, Callable[[dict], str]] = {
    "PushEvent": lambda p: f"pushed {len(p.get('commits') or [])} commit(s)",
    "PullRequestEvent": lambda p: f"{p.get('action', 'updated')} PR #{(p.get('pull_request') or {}).get('number', '?')}",
    "IssuesEvent": lambda p: f"{p.get('action', 'updated')} issue #{(p.get('issue') or {}).get('number', '?')}",
    "IssueCommentEvent": lambda p: f"commented on #{(p.get('issue') or {}).get('number', '?')}",
    "PullRequestReviewEvent": lambda p: f"reviewed PR #{(p.get('pull_request') or {}).get('number', '?')}",
    "CreateEvent": lambda p: f"created {p.get('ref_type', 'ref')} {p.get('ref') or ''}".strip(),
    "WatchEvent": lambda p: "starred the repo",
    "ForkEvent": lambda p: "forked the repo",
}


def github_snapshot(home, config) -> list[PortalWidget]:
    def open_prs() -> list[PortalItem]:
        prs = tools_mod.call(home, config, "github.list_my_prs", {"since": "-30d"})
        return [
            PortalItem(pr["title"], url=pr["url"], time=_rel_time(pr.get("updated_at", "")))
            for pr in prs if pr.get("state") == "open"
        ]

    def needs_review() -> list[PortalItem]:
        prs = tools_mod.call(home, config, "github.list_review_requests", {})
        return [
            PortalItem(pr["title"], url=pr["url"], time=_rel_time(pr.get("updated_at", "")))
            for pr in prs
        ]

    # Recent commits and activity are two presentations of the same event
    # feed -- fetched once, cached in this closure for whichever widget asks
    # first. GitHub's REST API has no separate "just my commits" endpoint
    # short of the heavier /search/commits, so this is the one deliberate
    # case of two widgets sharing a fetch.
    _events_cache: dict[str, list[dict]] = {}

    def _events() -> list[dict]:
        if "data" not in _events_cache:
            _events_cache["data"] = tools_mod.call(home, config, "github.list_recent_activity", {"since": "-7d"})
        return _events_cache["data"]

    def recent_commits() -> list[PortalItem]:
        items = []
        for e in _events():
            if e.get("type") != "PushEvent":
                continue
            repo = e.get("repo", "")
            when = _rel_time(e.get("created_at", ""))
            for c in (e.get("payload") or {}).get("commits") or []:
                message = (c.get("message") or "(no message)").splitlines()[0]
                items.append(PortalItem(message, subtitle=repo, time=when))
        return items[:15]

    def activity() -> list[PortalItem]:
        items = []
        for e in _events():
            label_fn = _GITHUB_EVENT_LABELS.get(e.get("type", ""))
            label = label_fn(e.get("payload") or {}) if label_fn else e.get("type", "activity")
            items.append(PortalItem(f"{label} in {e.get('repo', '')}", time=_rel_time(e.get("created_at", ""))))
        return items[:20]

    return [
        _fetch("github.open_prs", "Your open pull requests", open_prs,
               empty_message="No open pull requests."),
        _fetch("github.needs_review", "Needs your review", needs_review,
               empty_message="Nothing waiting on your review."),
        _fetch("github.recent_commits", "Recent commits", recent_commits,
               empty_message="No commits in the last 7 days."),
        _fetch("github.activity", "Activity", activity,
               empty_message="No activity in the last 7 days."),
    ]


# --- linear --------------------------------------------------------------

def linear_snapshot(home, config) -> list[PortalWidget]:
    def assigned_to_you() -> list[PortalItem]:
        me = tools_mod.call(home, config, "linear.get_current_user", {})
        me_id = me.get("id") if isinstance(me, dict) else None
        if not me_id:
            raise tools_mod.ConnectorError("linear identity response had no user id")
        issues = tools_mod.call(home, config, "linear.list_my_issues", {"assignee_id": me_id})
        # Composio's list shape hasn't been pinned against a live response
        # (Linear wasn't connected when this was written) -- handle both a
        # bare list and a {"issues": [...]}-wrapped one defensively.
        if isinstance(issues, dict):
            issues = issues.get("issues", [])
        items = []
        for i in issues or []:
            state = i.get("state")
            state_label = state.get("name") if isinstance(state, dict) else state
            items.append(PortalItem(
                i.get("title", "(untitled)"), subtitle=state_label or "",
                url=i.get("url"), time=_rel_time(i.get("updatedAt") or i.get("updated_at") or ""),
            ))
        return items

    return [
        _fetch("linear.assigned_to_you", "Assigned to you", assigned_to_you,
               empty_message="Nothing assigned to you right now."),
    ]


# --- slack -----------------------------------------------------------------

_MENTIONS_SCOPE_MESSAGE = (
    "Can't show mentions -- px0's Slack connection doesn't have identity "
    "access. Reconnect Slack from the CLI (`px0 tools list --status`) and "
    "re-authorize, or check mentions directly in Slack for now."
)


def _slack_channel_label(c: dict) -> str:
    if not isinstance(c, dict):
        return "conversation"
    name = c.get("name")
    return f"#{name}" if name else (c.get("id") or "conversation")


def _slack_user_id(home, config) -> str:
    """The connected Slack account's own user id, for building a mention
    search query. Raises ConnectorNotConfigured verbatim (Slack isn't
    connected at all) or a ConnectorError with a specific, actionable
    message otherwise -- a bare Composio failure here is, in practice, the
    account being connected but missing the identity.basic scope, a real
    observed failure mode of px0's Composio-managed default Slack auth."""
    try:
        me = tools_mod.call(home, config, "slack.whoami", {})
    except tools_mod.ConnectorNotConfigured:
        raise
    except tools_mod.ConnectorError as e:
        raise tools_mod.ConnectorError(_MENTIONS_SCOPE_MESSAGE) from e
    uid = None
    if isinstance(me, dict):
        uid = (me.get("user") or {}).get("id") or me.get("user_id")
    if not uid:
        raise tools_mod.ConnectorError(_MENTIONS_SCOPE_MESSAGE)
    return uid


def slack_snapshot(home, config) -> list[PortalWidget]:
    def recent_activity() -> list[PortalItem]:
        convos = tools_mod.call(home, config, "slack.list_conversations", {
            "exclude_archived": True,
            "types": "public_channel,private_channel,im,mpim",
            "limit": 50,
        })
        if isinstance(convos, dict):
            convos = convos.get("channels", [])
        cutoff_ts = str((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())

        scored: list[tuple[float, PortalItem]] = []
        for c in (convos or [])[:8]:
            cid = c.get("id") if isinstance(c, dict) else None
            if not cid:
                continue
            try:
                history = tools_mod.call(home, config, "slack.fetch_conversation_history",
                                          {"channel": cid, "oldest": cutoff_ts, "limit": 20})
            except tools_mod.ConnectorError:
                # One inaccessible conversation (not a member, archived, a DM
                # the account can't read) must not blank the whole widget --
                # observed live: a channel_not_found on one of several
                # otherwise-fine conversations.
                continue
            messages = history.get("messages", []) if isinstance(history, dict) else history
            label = _slack_channel_label(c)
            for m in messages or []:
                text = (m.get("text") or "").strip()
                if not text:
                    continue
                try:
                    ts_val = float(m.get("ts"))
                except (TypeError, ValueError):
                    ts_val = 0.0
                when = _rel_time(datetime.fromtimestamp(ts_val, tz=timezone.utc).isoformat()) if ts_val else None
                scored.append((ts_val, PortalItem(text[:140], subtitle=label, time=when)))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:20]]

    def mentions() -> list[PortalItem]:
        uid = _slack_user_id(home, config)
        results = tools_mod.call(home, config, "slack.search_messages", {
            "query": f"<@{uid}>", "count": 20, "sort": "timestamp", "sort_dir": "desc",
        })
        matches = ((results or {}).get("messages") or {}).get("matches") or []
        items = []
        for m in matches:
            text = (m.get("text") or "").strip()
            channel = m.get("channel")
            label = channel.get("name", "") if isinstance(channel, dict) else ""
            items.append(PortalItem(text[:140] or "(no text)", subtitle=label, url=m.get("permalink")))
        return items

    return [
        _fetch("slack.recent_activity", "Recent activity (last 24h)", recent_activity,
               empty_message="No recent messages in your channels and DMs."),
        _fetch("slack.mentions", "Mentions", mentions,
               empty_message="No mentions in the last 7 days."),
    ]


_SNAPSHOTS: dict[str, Callable[..., list[PortalWidget]]] = {
    "github": github_snapshot,
    "linear": linear_snapshot,
    "slack": slack_snapshot,
}


def snapshot(app: str, home, config) -> list[PortalWidget]:
    """Dispatches to the named app's snapshot function. `server.py` is
    expected to pre-validate `app` against `views.APP_TABS`; this is a
    defensive fallback, not the primary gate."""
    fn = _SNAPSHOTS.get(app)
    if fn is None:
        raise ValueError(f"no portal for app: {app}")
    return fn(home, config)


# --- persistence -----------------------------------------------------------

def portal_dir(home) -> Path:
    return paths.output_dir(home) / "portal"


def portal_path(home, app: str) -> Path:
    """Where `<app>`'s live data lives -- inside `output/`, the same place
    every other workflow-written file lands, so it's already writable by a
    workflow's own `output.target: file` and by the `file.write` tool
    without any new plumbing, and already swept into px0's nightly
    checkpoint scan (a free history of what changed over time)."""
    return portal_dir(home) / f"{app}.md"


def to_markdown(widgets: list[PortalWidget]) -> str:
    """Renders a snapshot as plain markdown -- the exact format a workflow
    writing this same file by hand would produce, and the same subset
    `views.render_markdown` already knows how to render safely (headings,
    links, bullets, paragraphs). A "connect" state becomes a real link, since
    `render_markdown` turns `[text](url)` into a real anchor."""
    blocks = []
    for w in widgets:
        blocks.append(f"## {w.title}")
        if w.connect_url:
            blocks.append(f"Not connected yet. [Connect]({w.connect_url})")
        elif w.error:
            blocks.append(w.error)
        elif not w.items:
            blocks.append(w.empty_message)
        else:
            lines = []
            for it in w.items:
                label = f"[{it.title}]({it.url})" if it.url else it.title
                extra = " -- ".join(x for x in (it.subtitle, it.time) if x)
                lines.append(f"- {label}" + (f" ({extra})" if extra else ""))
            blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def refresh(app: str, home, config) -> str:
    """Fetches `app` live and overwrites its markdown file -- the same plain
    "last write wins" overwrite `route_output`'s file target already uses
    for every other workflow output, so a workflow writing the same path
    later simply replaces this. Returns the text written."""
    widgets = snapshot(app, home, config)
    text = to_markdown(widgets)
    path = portal_path(home, app)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return text


def load(app: str, home) -> tuple[str | None, float | None]:
    """Reads `app`'s persisted markdown without ever touching the network --
    (None, None) if nothing has been written yet, by a refresh() or by a
    workflow. The mtime is the file's own, not a separately tracked
    timestamp: whatever last wrote the file (px0's own refresh, or a
    workflow) is automatically "when this was last updated"."""
    path = portal_path(home, app)
    if not path.exists():
        return None, None
    return path.read_text(), path.stat().st_mtime


def load_or_refresh(app: str, home, config) -> tuple[str, float]:
    """The read path a page view uses: serve whatever is already on disk --
    from an earlier refresh, or a workflow that wrote here on its own -- and
    only make a live API call the first time, when nothing exists yet.
    Callers that want to force a fresh fetch call refresh() directly
    instead (the web UI's "Refresh" button)."""
    text, mtime = load(app, home)
    if text is not None:
        return text, mtime
    text = refresh(app, home, config)
    return text, portal_path(home, app).stat().st_mtime
