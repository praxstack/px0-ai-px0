"""HTML views and HTMX partial templates for the px0 web dashboard."""

import html
import json
import re
from datetime import datetime
from typing import Any
from croniter import croniter

from px0 import (
    approvals as approvals_mod,
    ask as ask_mod,
    daemon as daemon_mod,
    inbox as inbox_mod,
    runs as runs_mod,
    tools as tools_mod,
    triage as triage_mod,
    workflow as workflow_mod,
)

# The needs-action home page's app tabs. Fixed and small on purpose -- these
# are the apps px0 has real tooling for today; anything else (calendar,
# gmail, custom tools, or a tool id that no longer resolves) falls into
# "other" rather than getting silently dropped.
APP_TABS: list[tuple[str, str]] = [
    ("github", "GitHub"),
    ("linear", "Linear"),
    ("slack", "Slack"),
]
APP_LABELS: dict[str, str] = dict(APP_TABS) | {"other": "Other"}


def _provider_of(home, tool_id: str) -> str:
    """Best-effort app name for a tool id, for bucketing an approval into its
    app tab. Never raises -- a stale approval referencing a since-removed
    tool must still render somewhere (the "other" tab) rather than break the
    page."""
    try:
        spec = tools_mod.resolve(tool_id, home)
        if spec and spec.provider:
            return spec.provider.lower()
    except Exception:
        pass
    raw = tool_id[len("composio:"):] if tool_id.startswith("composio:") else tool_id
    head = raw.split(".", 1)[0].split("_", 1)[0]
    return (head or "px0").lower()


def _escape(val: Any) -> str:
    return html.escape(str(val if val is not None else ""))


_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\((https?://[^\s()]+)\)')
_MD_BOLD_RE = re.compile(r'\*\*([^*\n]+)\*\*')
_MD_CODE_RE = re.compile(r'`([^`\n]+)`')
_MD_HEADING_RE = re.compile(r'^(#{1,3})\s+(.*)$')
_MD_BULLET_RE = re.compile(r'^[-*]\s+(.*)$')


def render_markdown(text: str) -> str:
    """Renders a small, safe subset of markdown -- headings, bold, inline
    code, http(s) links, bullet lists, paragraphs -- into HTML.

    A workflow's output is the model's own text wrapped around whatever a
    connector handed back: a PR title, a Slack message, an issue summary.
    None of that is trusted. This escapes the *entire* source first and only
    ever inserts tags this function itself writes, so a hostile title like
    `<img src=x onerror=...>` lands on the page as inert text, never as a
    live tag -- the same guarantee `_escape()` gives a `<pre>` block, just
    with structure on top instead of none. Links are restricted to http(s)
    so a `javascript:` URL from fetched content can't become clickable.
    """
    escaped = _escape(text)

    def inline(s: str) -> str:
        s = _MD_LINK_RE.sub(r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', s)
        s = _MD_BOLD_RE.sub(r'<strong>\1</strong>', s)
        s = _MD_CODE_RE.sub(r'<code>\1</code>', s)
        return s

    blocks: list[str] = []
    para: list[str] = []
    items: list[str] = []

    def flush_para():
        if para:
            blocks.append(f"<p>{' '.join(para)}</p>")
            para.clear()

    def flush_list():
        if items:
            blocks.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for raw_line in escaped.split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            flush_para()
            flush_list()
            continue
        heading = _MD_HEADING_RE.match(stripped)
        if heading:
            flush_para()
            flush_list()
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            continue
        bullet = _MD_BULLET_RE.match(stripped)
        if bullet:
            flush_para()
            items.append(inline(bullet.group(1)))
            continue
        flush_list()
        para.append(inline(stripped))

    flush_para()
    flush_list()
    return "\n".join(blocks) or "<p class=\"empty-state\">Nothing to show.</p>"


def page_shell(content: str, active_tab: str = "needs-action", daemon_status: dict | None = None,
               home=None, config=None) -> str:
    daemon_badge = render_daemon_badge(daemon_status or {})
    needs_action_badge = render_needs_action_badge(home, config) if home and config else ""

    t_stats = 'active' if active_tab == 'stats' else ''
    t_wf = 'active' if active_tab == 'workflows' else ''
    t_sched = 'active' if active_tab == 'schedules' else ''
    t_runs = 'active' if active_tab == 'runs' else ''
    t_daemon = 'active' if active_tab == 'daemon' else ''
    t_na = 'active' if active_tab == 'needs-action' else ''
    t_cc = 'active' if active_tab == 'command-center' else ''

    script_block = """
  <script>
    document.body.addEventListener('htmx:afterOnLoad', function(evt) {
      if (evt.detail.target.id === 'main-view') {
        const path = window.location.pathname;
        document.querySelectorAll('nav .nav-btn').forEach(function(el) {
          el.classList.toggle('active', el.getAttribute('href') === path);
        });
      }
    });
    function closeModal() {
      const container = document.getElementById('modal-container');
      if (container) container.innerHTML = '';
    }
  </script>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>px0 dashboard</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="/static/htmx.min.js"></script>
</head>
<body>
  <header>
    <div class="logo-area">
      <a href="/" class="brand" hx-get="/htmx/views/command-center" hx-target="#main-view" hx-push-url="/">px0<span>web</span></a>
      <nav>
        <a href="/" class="nav-btn {t_cc}" hx-get="/htmx/views/command-center" hx-target="#main-view" hx-push-url="/">Command Center</a>
        <a href="/needs-action" class="nav-btn {t_na}" hx-get="/htmx/views/needs-action" hx-target="#main-view" hx-push-url="/needs-action">Needs Action</a>
        <a href="/stats" class="nav-btn {t_stats}" hx-get="/htmx/views/dashboard" hx-target="#main-view" hx-push-url="/stats">Stats</a>
        <a href="/workflows" class="nav-btn {t_wf}" hx-get="/htmx/views/workflows" hx-target="#main-view" hx-push-url="/workflows">Workflows</a>
        <a href="/schedules" class="nav-btn {t_sched}" hx-get="/htmx/views/schedules" hx-target="#main-view" hx-push-url="/schedules">Schedules</a>
        <a href="/runs" class="nav-btn {t_runs}" hx-get="/htmx/views/runs" hx-target="#main-view" hx-push-url="/runs">Runs</a>
        <a href="/daemon" class="nav-btn {t_daemon}" hx-get="/htmx/views/daemon" hx-target="#main-view" hx-push-url="/daemon">Daemon</a>
      </nav>
    </div>
    <div class="header-status">
      <div id="global-spinner" class="htmx-indicator spinner"></div>
      {needs_action_badge}
      {daemon_badge}
    </div>
  </header>

  <main id="main-view">
    {content}
  </main>

  <div id="modal-container"></div>
  {script_block}
</body>
</html>"""


def render_daemon_badge(daemon_status: dict, start_failed: bool = False) -> str:
    """The header's daemon status pill. When the daemon is down it doubles as
    a start control: a button that asks the server to spawn it in the
    background (`/htmx/daemon/action?act=start&scope=header`), and, if that
    doesn't bring it up, the exact command (`daemon_mod.START_COMMAND`) to
    run by hand -- the same single source used by `px0 status` and the
    playlist-ingest hint, so it can't say something different from the CLI.
    """
    is_alive = daemon_status.get("alive", False)
    badge_cls = "badge-success" if is_alive else "badge-dim"
    dot_cls = "dot-green" if is_alive else "dot-red"
    status_str = "RUNNING" if is_alive else "STOPPED"
    start_btn = ""
    fallback = ""
    if not is_alive:
        start_btn = (
            '<button class="btn btn-primary btn-sm" style="margin-left:6px;" '
            'hx-post="/htmx/daemon/action?act=start&scope=header" '
            'hx-target="#header-daemon-badge" hx-swap="outerHTML">Start</button>'
        )
        if start_failed:
            fallback = (
                '<div style="margin-top:4px; font-size:11px; color: var(--text-dim);">'
                f'Could not start it here — run <code class="code-font">{_escape(daemon_mod.START_COMMAND)}</code>'
                '</div>'
            )
    return (
        '<div id="header-daemon-badge" hx-get="/htmx/daemon/badge" hx-trigger="every 5s" hx-swap="outerHTML">'
        '<div style="display:flex; align-items:center;">'
        f'<span class="badge {badge_cls}">'
        f'<span class="dot {dot_cls}"></span>'
        f'daemon: {status_str}'
        '</span>'
        f'{start_btn}'
        '</div>'
        f'{fallback}'
        '</div>'
    )


def render_needs_action_badge(home, config) -> str:
    """The self-polling header count of things waiting on you: pending
    approvals plus unread needs_action inbox entries. Mirrors the daemon
    badge's own hx-trigger idiom (`render_daemon_badge`, above), the only
    other place this app polls on a timer."""
    count = (approvals_mod.pending_count(home, config)
             + len(inbox_mod.listing(home, status=inbox_mod.UNREAD, attention=inbox_mod.NEEDS_ACTION)))
    badge_cls = "badge-info" if count else "badge-dim"
    label = f"needs action: {count}" if count else "needs action: 0"
    return (
        '<div id="header-needs-action-badge" hx-get="/htmx/needs-action/badge" '
        'hx-trigger="every 5s" hx-swap="outerHTML">'
        f'<a href="/" hx-get="/htmx/views/needs-action" hx-target="#main-view" '
        f'hx-push-url="/" style="text-decoration:none;">'
        f'<span class="badge {badge_cls}">'
        f'<span class="dot {"dot-amber" if count else "dot-green"}"></span>'
        f'{label}'
        '</span></a>'
        '</div>'
    )


def render_dashboard(home, config) -> str:
    all_wfs = workflow_mod.load_all(home)
    total_wfs = len(all_wfs)
    enabled_wfs = sum(1 for w in all_wfs.values() if w.enabled)
    scheduled_wfs = sum(1 for w in all_wfs.values() if (w.trigger or {}).get("schedule") and w.enabled)
    
    d_status = daemon_mod.status(home, config)
    recent_runs = runs_mod.list_records(config)[:5]

    runs_html = ""
    if recent_runs:
        rows = []
        for r in recent_runs:
            outcome = r.get("outcome", "unknown")
            badge_class = "badge-success" if outcome == "success" else ("badge-danger" if outcome == "failed" else "badge-dim")
            run_id = _escape(r.get('id', ''))
            wf_id = _escape(r.get('workflow_id', ''))
            st = _escape(r.get('start_time', '')[:19].replace('T', ' '))
            rows.append(
                f'<tr>'
                f'<td class="code-id">{run_id}</td>'
                f'<td><span class="code-font">{wf_id}</span></td>'
                f'<td><span class="badge {badge_class}">{_escape(outcome)}</span></td>'
                f'<td class="code-font">{st}</td>'
                f'<td><button class="btn btn-secondary btn-sm" hx-get="/htmx/runs/{run_id}" hx-target="#modal-container">Details</button></td>'
                f'</tr>'
            )
        runs_html = (
            '<div class="table-wrapper">'
            '<table>'
            '<thead><tr><th>Run ID</th><th>Workflow</th><th>Outcome</th><th>Started</th><th>Actions</th></tr></thead>'
            f'<tbody>{" ".join(rows)}</tbody>'
            '</table>'
            '</div>'
        )
    else:
        runs_html = '<div class="empty-state"><p>No historical runs found.</p></div>'

    daemon_state_text = f"Running (PID: {d_status.get('pid')})" if d_status.get('alive') else "Stopped"
    daemon_badge_class = "badge-success" if d_status.get('alive') else "badge-danger"

    return f"""
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">Total Workflows</div>
        <div class="metric-val">{total_wfs}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Enabled Workflows</div>
        <div class="metric-val">{enabled_wfs}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Active Schedules</div>
        <div class="metric-val">{scheduled_wfs}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Daemon Status</div>
        <div style="margin-top: 6px;">
          <span class="badge {daemon_badge_class}">{_escape(daemon_state_text)}</span>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">Recent Historical Runs</div>
        <a href="/runs" class="btn btn-secondary btn-sm" hx-get="/htmx/views/runs" hx-target="#main-view" hx-push-url="/runs">View All Runs</a>
      </div>
      {runs_html}
    </div>
    """


def _render_pending_approvals(pending: list[dict]) -> str:
    if not pending:
        return ""
    cards = []
    for a in pending:
        aid = _escape(a["id"])
        args_preview = _escape(json.dumps(a.get("args") or {})[:300])
        cards.append(f"""
        <div class="form-group" id="approval-{aid}" style="border:1px solid var(--panel-border); border-radius: var(--radius); padding:10px;">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
            <div>
              <span class="code-id">{aid}</span>
              <span class="code-font" style="margin-left:8px;">{_escape(a.get('tool'))}</span>
              <span style="color: var(--text-dim); margin-left:8px;">from {_escape(a.get('workflow_id'))}</span>
            </div>
            <div style="display:flex; gap:6px;">
              <button class="btn btn-primary btn-sm" hx-post="/htmx/approvals/{aid}/approve" hx-target="#approval-{aid}" hx-swap="outerHTML">Approve</button>
              <button class="btn btn-danger btn-sm" hx-post="/htmx/approvals/{aid}/reject" hx-target="#approval-{aid}" hx-swap="outerHTML">Reject</button>
            </div>
          </div>
          <div class="code-font" style="color: var(--text-dim); margin-top:6px;">args: {args_preview}</div>
          {f'<div style="margin-top:6px;">{_escape(a.get("output_preview", ""))[:300]}</div>' if a.get('output_preview') else ''}
        </div>
        """)
    return f"""
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">Pending Approvals ({len(pending)})</div>
      </div>
      {"".join(cards)}
    </div>
    """


def _render_inbox_group(home, config, title: str, entries: list[dict]) -> str:
    """One panel per attention level, one glance card per source app inside
    it. The card shows the *latest* entry's full rendered body inline --
    that is the "see everything at a glance" surface: no click needed to
    read what a starter workflow found. Older entries for the same source
    stay one click away, in a compact table under the card."""
    if not entries:
        return ""
    by_source: dict[str, list[dict]] = {}
    for e in entries:
        by_source.setdefault(e.get("source") or "px0", []).append(e)

    sections = []
    for source in sorted(by_source):
        group = sorted(by_source[source], key=lambda e: e.get("created", ""), reverse=True)
        latest, rest = group[0], group[1:]

        latest_id = _escape(latest["id"])
        latest_created = _escape(latest.get("created", "")[:19].replace("T", " "))
        latest_body = inbox_mod.body(home, config, latest)
        card = f"""
        <div class="source-card" id="inbox-row-{latest_id}">
          <div class="source-card-header">
            <span class="badge badge-dim">{_escape(source)}</span>
            <span class="code-font" style="color: var(--text-dim);">{latest_created}</span>
            <div style="flex:1;"></div>
            <button class="btn btn-secondary btn-sm" hx-post="/htmx/inbox/{latest_id}/mark" hx-vals='{{"status": "archived"}}' hx-target="#inbox-row-{latest_id}" hx-swap="outerHTML">Archive</button>
          </div>
          <div class="markdown-body">{render_markdown(latest_body)}</div>
        </div>
        """

        rest_html = ""
        if rest:
            rows = []
            for e in rest:
                eid = _escape(e["id"])
                created = _escape(e.get("created", "")[:19].replace("T", " "))
                rows.append(f"""
                <tr id="inbox-row-{eid}">
                  <td>{_escape(e.get('title', ''))}</td>
                  <td class="code-font" style="color: var(--text-dim);">{created}</td>
                  <td>
                    <div style="display:flex; gap:6px;">
                      <button class="btn btn-secondary btn-sm" hx-get="/htmx/inbox/{eid}" hx-target="#modal-container">Open</button>
                      <button class="btn btn-secondary btn-sm" hx-post="/htmx/inbox/{eid}/mark" hx-vals='{{"status": "archived"}}' hx-target="#inbox-row-{eid}" hx-swap="outerHTML">Archive</button>
                    </div>
                  </td>
                </tr>
                """)
            rest_html = f"""
            <div class="table-wrapper" style="margin-top:8px;">
              <table><thead><tr><th>Earlier</th><th>Delivered</th><th>Actions</th></tr></thead>
              <tbody>{"".join(rows)}</tbody></table>
            </div>
            """
        sections.append(card + rest_html)
    return f"""
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">{_escape(title)} ({len(entries)})</div>
      </div>
      {"".join(sections)}
    </div>
    """


def render_portal_section(app: str, text: str | None, updated_at: float | None) -> str:
    """The deterministic-portal card for one app tab: whatever is persisted
    at `output/portal/<app>.md` (px0/portal.py), rendered through the exact
    same `render_markdown` every workflow-produced body already goes
    through -- so a workflow that writes this same file instead of px0's own
    refresh() renders identically, no special-casing needed. Swapped into a
    `#portal-<app>` placeholder by `pxLoadPortal` in render_needs_action's
    script, below, and re-rendered in place by the Refresh button's POST."""
    when = (datetime.fromtimestamp(updated_at).strftime("%Y-%m-%d %H:%M")
            if updated_at else "never")
    body = render_markdown(text) if text and text.strip() else '<p class="empty-state">No live data yet.</p>'
    return f"""
    <div class="source-card" id="portal-card-{_escape(app)}">
      <div class="source-card-header">
        <span class="badge badge-dim">live</span>
        <span class="code-font" style="color: var(--text-dim);">updated {_escape(when)}</span>
        <div style="flex:1;"></div>
        <button class="btn btn-secondary btn-sm" hx-post="/htmx/portal/{_escape(app)}/refresh"
                hx-target="#portal-{_escape(app)}" hx-swap="innerHTML">Refresh</button>
      </div>
      <div class="markdown-body">{body}</div>
    </div>
    """


def render_needs_action(home, config) -> str:
    """The workbench's single "what needs me today" view, organized as one
    vertical tab per app. Each tab stacks two layers: pending write
    approvals and unread inbox entries first (workflow-delivered, actively
    waiting on a yes/no or a read), then a deterministic "live" section
    fetched by direct API call with no LLM/workflow involved (see
    px0/portal.py) -- what the app says right now, not what a scheduled
    workflow already told you. An app only shows what a workflow has
    actually delivered for it (an approval's tool, or an inbox entry's
    `source`); a tool/source that isn't github/linear/slack falls into
    "other" rather than being dropped -- "other" gets no live section, since
    the portal is scoped to the three apps px0 has real tooling for."""
    pending = approvals_mod.listing(home, config, status=approvals_mod.PENDING)
    needs_action = inbox_mod.listing(home, status=inbox_mod.UNREAD, attention=inbox_mod.NEEDS_ACTION)
    fyi = inbox_mod.listing(home, status=inbox_mod.UNREAD, attention=inbox_mod.FYI)

    known_apps = [app for app, _label in APP_TABS]
    buckets: dict[str, dict[str, list[dict]]] = {
        app: {"approvals": [], "needs_action": [], "fyi": []} for app in known_apps + ["other"]
    }
    for a in pending:
        app = _provider_of(home, a.get("tool", ""))
        buckets[app if app in buckets else "other"]["approvals"].append(a)
    for e in needs_action:
        app = e.get("source") or "px0"
        buckets[app if app in buckets else "other"]["needs_action"].append(e)
    for e in fyi:
        app = e.get("source") or "px0"
        buckets[app if app in buckets else "other"]["fyi"].append(e)

    order = list(known_apps)
    if any(buckets["other"].values()):
        order.append("other")
    # Prefer whichever tab actually has something queued; otherwise just land
    # on the first known app so its live portal data has somewhere to open.
    default_app = next((app for app in order if any(buckets[app].values())), order[0])

    nav_items, panels = [], []
    for app in order:
        b = buckets[app]
        count = len(b["approvals"]) + len(b["needs_action"]) + len(b["fyi"])
        label = _escape(APP_LABELS.get(app, app.title()))
        active = app == default_app
        count_html = f'<span class="app-tab-count">{count}</span>' if count else ""
        nav_items.append(
            f'<button type="button" class="app-tab-btn{" active" if active else ""}" '
            f'data-app-tab="{app}" onclick="pxSelectAppTab(\'{app}\')">{label}{count_html}</button>'
        )

        queue_html = (
            _render_pending_approvals(b["approvals"])
            + _render_inbox_group(home, config, "Needs your attention", b["needs_action"])
            + _render_inbox_group(home, config, "FYI", b["fyi"])
        )
        if not queue_html:
            queue_html = f'<div class="empty-state"><p>Nothing waiting on you in {label} right now.</p></div>'

        portal_html = ""
        if app in known_apps:
            portal_html = (
                f'<div id="portal-{app}" class="portal-widgets-loading">'
                f'<span class="spinner"></span> '
                f'<span style="color: var(--text-dim);">Loading live {label} data…</span></div>'
            )

        panels.append(
            f'<div class="app-tab-panel" data-app-panel="{app}"{"" if active else " hidden"}>'
            f'{queue_html}{portal_html}</div>'
        )

    return f"""
    <div class="app-tabs">
      <nav class="app-tab-nav">{"".join(nav_items)}</nav>
      <div class="app-tab-content">{"".join(panels)}</div>
    </div>
    <script>
      function pxSelectAppTab(app) {{
        document.querySelectorAll('.app-tab-btn').forEach(function(el) {{
          el.classList.toggle('active', el.getAttribute('data-app-tab') === app);
        }});
        document.querySelectorAll('.app-tab-panel').forEach(function(el) {{
          el.hidden = el.getAttribute('data-app-panel') !== app;
        }});
        pxLoadPortal(app);
      }}
      function pxLoadPortal(app) {{
        var el = document.getElementById('portal-' + app);
        if (!el || el.dataset.loaded === '1') return;
        el.dataset.loaded = '1';
        htmx.ajax('GET', '/htmx/portal/' + app, {{target: '#portal-' + app, swap: 'innerHTML'}});
      }}
      pxLoadPortal('{default_app}');
    </script>
    """


def render_command_center(home, config, active_item: dict | None = None) -> str:
    """The 3-column unified command center:
    1. Filtered activity stream with triage actions (Mark Done, Snooze)
    2. Active context inspection, manual workflow execution dropdown, & draft reply
    3. Knowledge base & Ask Brain panel
    """
    triage_map = triage_mod.load(home)

    # Gather items from inbox & approvals
    pending = approvals_mod.listing(home, config, status=approvals_mod.PENDING)
    needs_action = inbox_mod.listing(home, status=inbox_mod.UNREAD, attention=inbox_mod.NEEDS_ACTION)

    items = []
    for a in pending:
        items.append({
            "id": f"approval:{a['id']}",
            "type": "approval",
            "source": _provider_of(home, a.get("tool", "")),
            "title": f"Approve {a.get('tool', 'action')}",
            "created": a.get("created", ""),
            "payload": a,
        })
    for e in needs_action:
        items.append({
            "id": f"inbox:{e['id']}",
            "type": "inbox",
            "source": e.get("source") or "px0",
            "title": e.get("title") or "Notification",
            "created": e.get("created", ""),
            "payload": e,
        })

    # Filter out triaged items (done or snoozed)
    visible_items = [it for it in items if triage_mod.is_visible(it["id"], triage_map)]

    # Fallback to first item if none active
    curr_active = active_item or (visible_items[0] if visible_items else None)

    # 1. Render Left Column: Stream Cards
    stream_cards = []
    for it in visible_items:
        it_id = _escape(it["id"])
        is_sel = curr_active and curr_active["id"] == it["id"]
        source = _escape(it["source"])
        title = _escape(it["title"])
        created = _escape(it.get("created", "")[:16].replace("T", " "))
        stream_cards.append(f"""
        <div class="stream-card {'active' if is_sel else ''}" id="stream-card-{it_id}"
             hx-get="/htmx/command-center/inspect?item_id={it_id}"
             hx-target="#active-item-container" hx-swap="innerHTML">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
            <span class="badge badge-dim">{source}</span>
            <span class="code-font" style="font-size:11px; color:var(--text-dim);">{created}</span>
          </div>
          <div style="font-weight:500; font-size:13px; margin-bottom:6px;">{title}</div>
          <div class="triage-actions" onclick="event.stopPropagation();">
            <button class="btn-triage btn-triage-done"
                    hx-post="/htmx/triage/done?item_id={it_id}"
                    hx-target="#stream-card-{it_id}" hx-swap="outerHTML">
              ✓ Done
            </button>
            <button class="btn-triage"
                    hx-post="/htmx/triage/snooze?item_id={it_id}"
                    hx-target="#stream-card-{it_id}" hx-swap="outerHTML">
              ⏱ Snooze
            </button>
          </div>
        </div>
        """)

    stream_col = "".join(stream_cards) or '<div class="empty-state"><p>Inbox Zero! No pending action items.</p></div>'

    # 2. Render Middle Column: Active Item Context + Workflow Runner + Draft Reply
    active_html = render_active_item(home, config, curr_active)

    # 3. Render Right Column: Knowledge Base Panel
    kb_html = render_kb_panel(home, config)

    return f"""
    <div class="command-center">
      <!-- Column 1: Filtered Activity Stream -->
      <div class="command-center-stream">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
          <h3 style="font-size:14px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; color:var(--text-dim);">
            Action Stream ({len(visible_items)})
          </h3>
          <span class="badge badge-dim">Synced</span>
        </div>
        <div id="stream-list">
          {stream_col}
        </div>
      </div>

      <!-- Column 2: Active Context & Actions -->
      <div id="active-item-container">
        {active_html}
      </div>

      <!-- Column 3: Knowledge Base & Ask Brain -->
      <div class="command-center-kb">
        {kb_html}
      </div>
    </div>
    """


def render_active_item(home, config, item: dict | None) -> str:
    """Renders the middle column: context detail, workflow runner dropdown, and draft reply box."""
    if not item:
        return """
        <div class="active-item-panel">
          <div class="empty-state"><p>Select an item from the stream to inspect context and take action.</p></div>
        </div>
        """

    item_id = _escape(item["id"])
    source = _escape(item.get("source", "px0"))
    title = _escape(item.get("title", ""))
    payload = item.get("payload", {})

    body_md = ""
    if item["type"] == "inbox":
        body_md = inbox_mod.body(home, config, payload)
    elif item["type"] == "approval":
        body_md = f"**Tool**: `{_escape(payload.get('tool', ''))}`\n\n```json\n{json.dumps(payload.get('args', {}), indent=2)}\n```"

    # Available workflows for triggering
    all_wfs = workflow_mod.load_all(home)
    wf_options = []
    for wfid, wf in sorted(all_wfs.items()):
        wf_options.append(f'<option value="{_escape(wfid)}">{_escape(wf.description or wfid)}</option>')

    wf_options_html = "".join(wf_options)

    return f"""
    <div class="active-item-panel" id="active-panel-{item_id}">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <div>
          <span class="badge badge-info" style="margin-right:6px;">{source}</span>
          <span class="code-font" style="font-size:12px; color:var(--text-dim);">{item_id}</span>
        </div>
        <div class="triage-actions">
          <button class="btn btn-secondary btn-sm"
                  hx-post="/htmx/triage/done?item_id={item_id}"
                  hx-target="#stream-card-{item_id}" hx-swap="outerHTML">
            Mark Done
          </button>
          <button class="btn btn-secondary btn-sm"
                  hx-post="/htmx/triage/snooze?item_id={item_id}"
                  hx-target="#stream-card-{item_id}" hx-swap="outerHTML">
            Snooze
          </button>
        </div>
      </div>

      <h2 style="font-size:16px; margin-bottom:12px;">{title}</h2>

      <!-- Workflow Trigger Bar -->
      <div class="workflow-runner-bar">
        <span style="font-size:12px; font-weight:500; color:var(--text-dim);">Run Workflow:</span>
        <form hx-post="/htmx/workflows/run-on-item" hx-target="#wf-run-result" hx-swap="innerHTML" style="display:flex; gap:6px; flex:1;">
          <input type="hidden" name="item_id" value="{item_id}">
          <input type="hidden" name="source" value="{source}">
          <select name="workflow_id" class="input-select" style="flex:1; background:var(--bg); color:var(--text); border:1px solid var(--panel-border); padding:4px 8px; border-radius:var(--radius);">
            {wf_options_html}
          </select>
          <button type="submit" class="btn btn-primary btn-sm">▶ Run</button>
        </form>
      </div>
      <div id="wf-run-result" style="margin-bottom:12px;"></div>

      <!-- Item Context Body -->
      <div class="markdown-body" style="background:rgba(0,0,0,0.15); padding:12px; border-radius:var(--radius); margin-bottom:16px;">
        {render_markdown(body_md)}
      </div>

      <!-- Draft & Send Reply Box -->
      <div class="reply-box">
        <h4 style="font-size:13px; font-weight:600; margin-bottom:8px; color:var(--text-dim);">Draft & Send Reply</h4>
        <form hx-post="/htmx/reply/dispatch" hx-target="#reply-status" hx-swap="innerHTML">
          <input type="hidden" name="item_id" value="{item_id}">
          <input type="hidden" name="source" value="{source}">
          <textarea id="reply-text" name="message" class="reply-textarea" placeholder="Write markdown reply or use Knowledge Base to insert context..."></textarea>
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size:11px; color:var(--text-dim);">Supports Markdown. Dispatches via {source.title()} API.</span>
            <button type="submit" class="btn btn-primary btn-sm">Send Reply ↵</button>
          </div>
        </form>
        <div id="reply-status" style="margin-top:8px;"></div>
      </div>
    </div>
    """


def render_kb_panel(home, config) -> str:
    """Renders the Knowledge Base & Ask Brain sidebar panel."""
    return """
    <div class="kb-panel">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <h3 style="font-size:13px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; color:var(--text-dim);">
          🧠 Knowledge Base & Ask
        </h3>
      </div>
      <form hx-get="/htmx/brain/ask" hx-target="#kb-results" hx-swap="innerHTML" style="margin-bottom:10px;">
        <input type="text" name="q" class="kb-input" placeholder="Ask brain / search docs & guidelines..." required>
      </form>
      <div id="kb-results">
        <p style="color:var(--text-dim); font-size:12px;">Ask questions across your notes, guidelines, and memory.</p>
      </div>
    </div>
    """


def render_kb_results(question: str, answer: str, passages: list) -> str:
    """Renders retrieval results from px0 ask with an 'Insert into Draft' action."""
    passages_html = []
    for p in passages[:3]:
        p_path = _escape(getattr(p, "path", ""))
        p_text = _escape(getattr(p, "text", "")[:140] + "...")
        passages_html.append(f"""
        <div class="kb-result-card">
          <div style="font-weight:600; margin-bottom:2px;">{p_path}</div>
          <div style="color:var(--text-dim); margin-bottom:4px;">{p_text}</div>
          <button type="button" class="btn btn-secondary btn-sm" style="font-size:10px; padding:2px 6px;"
                  onclick="insertIntoDraft('{_escape(getattr(p, 'text', '').replace("'", "\\'").replace('\\n', ' '))}')">
            + Insert into Draft
          </button>
        </div>
        """)

    escaped_ans = _escape(answer)
    return f"""
    <div style="margin-top:10px;">
      <div style="font-size:12px; font-weight:600; color:var(--accent); margin-bottom:4px;">Q: {_escape(question)}</div>
      <div class="markdown-body" style="font-size:12px; margin-bottom:10px;">{render_markdown(answer)}</div>
      <button type="button" class="btn btn-secondary btn-sm" style="font-size:11px; margin-bottom:12px; width:100%;"
              onclick="insertIntoDraft('{escaped_ans.replace("'", "\\'").replace('\\n', ' ')}')">
        Quote Answer into Draft
      </button>
      <h5 style="font-size:11px; color:var(--text-dim); margin-bottom:6px; text-transform:uppercase;">Relevant Passages:</h5>
      {"".join(passages_html)}
    </div>
    <script>
      function insertIntoDraft(text) {{
        var el = document.getElementById('reply-text');
        if (el) {{
          el.value = (el.value ? el.value + '\\n\\n' : '') + text;
          el.focus();
        }}
      }}
    </script>
    """



def render_inbox_entry_detail_modal(home, config, entry_id: str) -> str:
    try:
        entry = inbox_mod.read_entry(home, entry_id)
    except inbox_mod.InboxError as e:
        return f"""
        <div class="modal-backdrop" onclick="if(event.target === this) closeModal();">
          <div class="modal-content">
            <div class="modal-header">
              <div class="panel-title">Inbox Error</div>
              <button class="btn btn-secondary btn-sm" onclick="closeModal()">Close</button>
            </div>
            <div class="modal-body"><p style="color: var(--danger);">{_escape(str(e))}</p></div>
          </div>
        </div>
        """
    if entry.get("status") == inbox_mod.UNREAD:
        entry = inbox_mod.mark(home, entry_id, inbox_mod.READ)
    body = inbox_mod.body(home, config, entry)
    attention = entry.get("attention", inbox_mod.FYI)
    badge_cls = "badge-info" if attention == inbox_mod.NEEDS_ACTION else "badge-dim"

    return f"""
    <div class="modal-backdrop" onclick="if(event.target === this) closeModal();">
      <div class="modal-content">
        <div class="modal-header">
          <div class="panel-title">{_escape(entry.get('title', entry_id))}</div>
          <button class="btn btn-secondary btn-sm" onclick="closeModal()">Close</button>
        </div>
        <div class="modal-body">
          <div style="display:flex; gap:8px; margin-bottom:12px;">
            <span class="badge {badge_cls}">{_escape(attention)}</span>
            <span class="badge badge-dim">{_escape(entry.get('source', ''))}</span>
            <span class="code-font" style="color: var(--text-dim);">from {_escape(entry.get('workflow_id', ''))}</span>
          </div>
          <div class="markdown-body">{render_markdown(body)}</div>
        </div>
      </div>
    </div>
    """


def render_workflows_list(home, config) -> str:
    all_wfs = workflow_mod.load_all(home)
    errors = workflow_mod.load_errors(home)

    alert_html = ""
    if errors:
        error_items = "".join(f"<li>{_escape(err)}</li>" for err in errors)
        alert_html = f"""
        <div class="panel" style="border-color: rgba(224, 108, 117, 0.4); background: var(--danger-bg);">
          <div class="panel-title" style="color: var(--danger); margin-bottom: 8px;">Workflow Parse Errors</div>
          <ul style="padding-left: 20px;">{error_items}</ul>
        </div>
        """

    rows = []
    for wf_id, wf in sorted(all_wfs.items()):
        status_badge = '<span class="badge badge-success">ENABLED</span>' if wf.enabled else '<span class="badge badge-dim">DISABLED</span>'
        schedule = (wf.trigger or {}).get("schedule")
        sched_html = f'<code class="code-font">{_escape(schedule)}</code>' if schedule else '<span style="color: var(--text-faint);">manual only</span>'
        tools_summary = ", ".join(wf.tools[:3]) + (", ..." if len(wf.tools) > 3 else "") if wf.tools else "none"
        toggle_label = 'Disable' if wf.enabled else 'Enable'

        rows.append(f"""
        <tr id="wf-row-{_escape(wf_id)}">
          <td><span class="code-id">{_escape(wf_id)}</span></td>
          <td>{status_badge}</td>
          <td>{sched_html}</td>
          <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-dim);" title="{_escape(wf.description)}">
            {_escape(wf.description or wf.request or '-')}
          </td>
          <td class="code-font" style="color: var(--text-dim);">{_escape(tools_summary)}</td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-primary btn-sm" hx-get="/htmx/workflows/{_escape(wf_id)}/run-modal" hx-target="#modal-container">Run</button>
              <button class="btn btn-secondary btn-sm" hx-get="/htmx/workflows/{_escape(wf_id)}" hx-target="#modal-container">View</button>
              <button class="btn btn-secondary btn-sm" 
                      hx-post="/htmx/workflows/{_escape(wf_id)}/toggle" 
                      hx-target="#wf-row-{_escape(wf_id)}" 
                      hx-swap="outerHTML">
                {toggle_label}
              </button>
            </div>
          </td>
        </tr>
        """)

    table_content = ""
    if rows:
        table_content = f"""
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Workflow ID</th>
                <th>Status</th>
                <th>Schedule</th>
                <th>Description</th>
                <th>Tools</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {''.join(rows)}
            </tbody>
          </table>
        </div>
        """
    else:
        table_content = '<div class="empty-state"><p>No workflows found in store.</p></div>'

    return f"""
    {alert_html}
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">Workflows ({len(all_wfs)})</div>
      </div>
      {table_content}
    </div>
    """


def render_workflow_row(wf) -> str:
    status_badge = '<span class="badge badge-success">ENABLED</span>' if wf.enabled else '<span class="badge badge-dim">DISABLED</span>'
    schedule = (wf.trigger or {}).get("schedule")
    sched_html = f'<code class="code-font">{_escape(schedule)}</code>' if schedule else '<span style="color: var(--text-faint);">manual only</span>'
    tools_summary = ", ".join(wf.tools[:3]) + (", ..." if len(wf.tools) > 3 else "") if wf.tools else "none"
    toggle_label = 'Disable' if wf.enabled else 'Enable'

    return f"""
    <tr id="wf-row-{_escape(wf.id)}">
      <td><span class="code-id">{_escape(wf.id)}</span></td>
      <td>{status_badge}</td>
      <td>{sched_html}</td>
      <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-dim);" title="{_escape(wf.description)}">
        {_escape(wf.description or wf.request or '-')}
      </td>
      <td class="code-font" style="color: var(--text-dim);">{_escape(tools_summary)}</td>
      <td>
        <div style="display: flex; gap: 6px;">
          <button class="btn btn-primary btn-sm" hx-get="/htmx/workflows/{_escape(wf.id)}/run-modal" hx-target="#modal-container">Run</button>
          <button class="btn btn-secondary btn-sm" hx-get="/htmx/workflows/{_escape(wf.id)}" hx-target="#modal-container">View</button>
          <button class="btn btn-secondary btn-sm" 
                  hx-post="/htmx/workflows/{_escape(wf.id)}/toggle" 
                  hx-target="#wf-row-{_escape(wf.id)}" 
                  hx-swap="outerHTML">
            {toggle_label}
          </button>
        </div>
      </td>
    </tr>
    """


def render_workflow_detail_modal(wf) -> str:
    tools_list = ", ".join(wf.tools) if wf.tools else "None"
    inputs_info = "None"
    if wf.inputs:
        inputs_info = "<ul style='padding-left: 20px;'>" + "".join(
            f"<li><code>{_escape(inp.id)}</code> ({_escape(inp.kind)})</li>" for inp in wf.inputs
        ) + "</ul>"
    
    vars_info = "None"
    if wf.vars:
        vars_info = "<ul style='padding-left: 20px;'>" + "".join(
            f"<li><code>{_escape(v.get('name'))}</code>: {_escape(v.get('description', ''))} (default: {_escape(v.get('default'))})</li>" 
            for v in wf.vars
        ) + "</ul>"

    trigger_info = json.dumps(wf.trigger, indent=2) if wf.trigger else "manual"

    return f"""
    <div class="modal-backdrop" onclick="if(event.target === this) closeModal();">
      <div class="modal-content">
        <div class="modal-header">
          <div class="panel-title code-id">{_escape(wf.id)}</div>
          <button class="btn btn-secondary btn-sm" onclick="closeModal()">Close</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <div class="form-label">Description</div>
            <div style="color: var(--text);">{_escape(wf.description or 'No description')}</div>
          </div>
          <div class="form-group">
            <div class="form-label">Path</div>
            <code class="code-font" style="color: var(--text-dim);">{_escape(str(wf.path))}</code>
          </div>
          <div class="form-group">
            <div class="form-label">Trigger</div>
            <pre class="code-view">{_escape(trigger_info)}</pre>
          </div>
          <div class="form-group">
            <div class="form-label">Tools</div>
            <div class="code-font">{_escape(tools_list)}</div>
          </div>
          <div class="form-group">
            <div class="form-label">Inputs</div>
            <div>{inputs_info}</div>
          </div>
          <div class="form-group">
            <div class="form-label">Template Vars</div>
            <div>{vars_info}</div>
          </div>
          <div class="form-group">
            <div class="form-label">Prompt Body</div>
            <pre class="code-view">{_escape(wf.body)}</pre>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" hx-get="/htmx/workflows/{_escape(wf.id)}/run-modal" hx-target="#modal-container">Run Workflow</button>
          <button class="btn btn-secondary" onclick="closeModal()">Close</button>
        </div>
      </div>
    </div>
    """


def render_schedules_list(home, config) -> str:
    all_wfs = workflow_mod.load_all(home)
    scheduled = [(wf_id, wf) for wf_id, wf in sorted(all_wfs.items()) if (wf.trigger or {}).get("schedule")]

    state = daemon_mod.load_schedule_state(home)
    now = datetime.now()

    rows = []
    for wf_id, wf in scheduled:
        cron_expr = wf.trigger.get("schedule", "")
        zone = daemon_mod.resolve_zone(config, wf)
        last_fire = state.get(wf_id, "Never")
        
        next_fire = "Unknown"
        try:
            zone_now = datetime.now(zone) if zone else now
            itr = croniter(cron_expr, zone_now)
            next_dt = itr.get_next(datetime)
            next_fire = next_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            next_fire = "Invalid cron syntax"

        status_badge = '<span class="badge badge-success">ENABLED</span>' if wf.enabled else '<span class="badge badge-dim">DISABLED</span>'
        toggle_label = 'Disable' if wf.enabled else 'Enable'

        rows.append(f"""
        <tr id="sched-row-{_escape(wf_id)}">
          <td><span class="code-id">{_escape(wf_id)}</span></td>
          <td><code class="code-font" style="font-weight: bold; color: var(--accent);">{_escape(cron_expr)}</code></td>
          <td><span class="code-font" style="color: var(--text-dim);">{_escape(str(zone) if zone else 'Local')}</span></td>
          <td class="code-font">{_escape(last_fire[:19].replace('T', ' '))}</td>
          <td class="code-font" style="color: var(--info);">{_escape(next_fire)}</td>
          <td>{status_badge}</td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-primary btn-sm" hx-get="/htmx/schedules/{_escape(wf_id)}/edit" hx-target="#modal-container">Edit Schedule</button>
              <button class="btn btn-secondary btn-sm" 
                      hx-post="/htmx/workflows/{_escape(wf_id)}/toggle" 
                      hx-target="#main-view" 
                      hx-get="/htmx/views/schedules">
                {toggle_label}
              </button>
            </div>
          </td>
        </tr>
        """)

    table_content = ""
    if rows:
        table_content = f"""
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Workflow</th>
                <th>Cron Schedule</th>
                <th>Timezone</th>
                <th>Last Fire</th>
                <th>Next Fire</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {''.join(rows)}
            </tbody>
          </table>
        </div>
        """
    else:
        table_content = '<div class="empty-state"><p>No scheduled workflows configured.</p></div>'

    return f"""
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">Workflow Schedules ({len(scheduled)})</div>
      </div>
      {table_content}
    </div>
    """


def render_schedule_edit_modal(wf) -> str:
    current_cron = (wf.trigger or {}).get("schedule", "")
    return f"""
    <div class="modal-backdrop" onclick="if(event.target === this) closeModal();">
      <div class="modal-content" style="max-width: 500px;">
        <div class="modal-header">
          <div class="panel-title">Edit Schedule: <span class="code-id">{_escape(wf.id)}</span></div>
          <button class="btn btn-secondary btn-sm" onclick="closeModal()">Close</button>
        </div>
        <form hx-post="/htmx/schedules/{_escape(wf.id)}/update" hx-target="#main-view">
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label">Cron Expression</label>
              <input type="text" name="schedule" class="form-input code-font" value="{_escape(current_cron)}" required />
              <div class="form-help">e.g. <code>0 9 * * 1-5</code> or <code>@daily</code></div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="submit" class="btn btn-primary">Save Changes</button>
            <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
          </div>
        </form>
      </div>
    </div>
    """


def render_runs_list(config) -> str:
    records = runs_mod.list_records(config)[:100]

    rows = []
    for r in records:
        outcome = r.get("outcome", "unknown")
        badge_class = "badge-success" if outcome == "success" else ("badge-danger" if outcome == "failed" else "badge-dim")
        trigger = r.get("trigger", "manual")
        duration = "-"
        if r.get("start_time") and r.get("end_time"):
            try:
                st = datetime.fromisoformat(r["start_time"])
                et = datetime.fromisoformat(r["end_time"])
                secs = (et - st).total_seconds()
                duration = f"{secs:.1f}s"
            except Exception:
                pass

        tool_calls_count = len(r.get("tool_calls", []))
        run_id = _escape(r.get('id', ''))
        wf_id = _escape(r.get('workflow_id', ''))
        st_str = _escape(r.get('start_time', '')[:19].replace('T', ' '))

        rows.append(f"""
        <tr>
          <td><span class="code-id">{run_id}</span></td>
          <td><span class="code-font">{wf_id}</span></td>
          <td><span class="badge {badge_class}">{_escape(outcome)}</span></td>
          <td><span class="badge badge-dim">{_escape(trigger)}</span></td>
          <td class="code-font">{_escape(duration)}</td>
          <td class="code-font">{tool_calls_count}</td>
          <td class="code-font">{st_str}</td>
          <td>
            <button class="btn btn-secondary btn-sm" hx-get="/htmx/runs/{run_id}" hx-target="#modal-container">Details</button>
          </td>
        </tr>
        """)

    table_content = ""
    if rows:
        table_content = f"""
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Workflow</th>
                <th>Outcome</th>
                <th>Trigger</th>
                <th>Duration</th>
                <th>Tool Calls</th>
                <th>Started</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {''.join(rows)}
            </tbody>
          </table>
        </div>
        """
    else:
        table_content = '<div class="empty-state"><p>No runs recorded yet.</p></div>'

    return f"""
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">Historical Runs ({len(records)})</div>
        <button class="btn btn-secondary btn-sm" hx-get="/htmx/views/runs" hx-target="#main-view">Refresh</button>
      </div>
      {table_content}
    </div>
    """


def render_run_detail_modal(config, run_id: str) -> str:
    try:
        record = runs_mod.read_record(config, run_id)
    except Exception as e:
        return f"""
        <div class="modal-backdrop" onclick="if(event.target === this) closeModal();">
          <div class="modal-content">
            <div class="modal-header">
              <div class="panel-title">Run Error</div>
              <button class="btn btn-secondary btn-sm" onclick="closeModal()">Close</button>
            </div>
            <div class="modal-body"><p style="color: var(--danger);">{_escape(str(e))}</p></div>
          </div>
        </div>
        """

    raw_log = runs_mod.read_raw_log(config, run_id)
    events = runs_mod.read_events(config, run_id)
    outcome = record.get("outcome", "unknown")
    badge_class = "badge-success" if outcome == "success" else ("badge-danger" if outcome == "failed" else "badge-dim")

    tool_calls = record.get("tool_calls", [])
    tools_html = "None"
    if tool_calls:
        tc_rows = []
        for tc in tool_calls:
            dur = tc.get('duration_seconds', 0)
            tc_rows.append(f"""
            <li style="margin-bottom: 6px;">
              <strong>{_escape(tc.get('tool'))}</strong>
              <div class="code-font" style="color: var(--text-dim); margin-top: 2px;">
                duration: {dur:.2f}s | write: {tc.get('is_write', False)}
              </div>
            </li>
            """)
        tools_html = f"<ul style='padding-left: 20px;'>{''.join(tc_rows)}</ul>"

    output_spec = record.get("output", {})
    output_text = output_spec.get("text", "")

    return f"""
    <div class="modal-backdrop" onclick="if(event.target === this) closeModal();">
      <div class="modal-content">
        <div class="modal-header">
          <div class="panel-title">Run: <span class="code-id">{_escape(run_id)}</span></div>
          <button class="btn btn-secondary btn-sm" onclick="closeModal()">Close</button>
        </div>
        <div class="modal-body">
          <div style="display: flex; gap: 12px; margin-bottom: 16px; align-items: center;">
            <span class="badge {badge_class}">{_escape(outcome)}</span>
            <span class="badge badge-dim">trigger: {_escape(record.get('trigger', 'manual'))}</span>
            <span class="code-font" style="color: var(--text-dim);">Workflow: {_escape(record.get('workflow_id', ''))}</span>
          </div>

          <div class="form-group">
            <div class="form-label">Output ({_escape(output_spec.get('target', 'stdout'))})</div>
            {f'<div class="markdown-body">{render_markdown(output_text)}</div>' if output_text else '<p class="empty-state">No output recorded</p>'}
          </div>

          <div class="form-group">
            <div class="form-label">Tool Calls ({len(tool_calls)})</div>
            <div>{tools_html}</div>
          </div>

          <div class="form-group">
            <div class="form-label">Raw Log</div>
            <pre class="code-view">{_escape(raw_log or 'No raw log available')}</pre>
          </div>

          <div class="form-group">
            <div class="form-label">Events JSON ({len(events)})</div>
            <pre class="code-view">{_escape(json.dumps(events, indent=2) if events else 'No event trace')}</pre>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="closeModal()">Close</button>
        </div>
      </div>
    </div>
    """


def render_run_modal(wf) -> str:
    declared_vars = workflow_mod.declared_vars(wf)
    vars_inputs_html = ""
    if declared_vars:
        fields = []
        for v in declared_vars:
            name = v["name"]
            req = v.get("required", False)
            default = v.get("default") or ""
            desc = v.get("description", "")
            req_label = "<span style='color: var(--danger);'>*</span>" if req else ""
            req_attr = 'required' if req else ''
            fields.append(f"""
            <div class="form-group">
              <label class="form-label">{_escape(name)} {req_label}</label>
              <input type="text" name="var_{_escape(name)}" value="{_escape(default)}" class="form-input" {req_attr} />
              <div class="form-help">{_escape(desc)}</div>
            </div>
            """)
        vars_inputs_html = f"""
        <div style="margin-top: 12px;">
          <div class="panel-title" style="font-size: 14px; margin-bottom: 8px;">Variables</div>
          {''.join(fields)}
        </div>
        """

    return f"""
    <div class="modal-backdrop" onclick="if(event.target === this) closeModal();">
      <div class="modal-content" style="max-width: 550px;">
        <div class="modal-header">
          <div class="panel-title">Run Workflow: <span class="code-id">{_escape(wf.id)}</span></div>
          <button class="btn btn-secondary btn-sm" onclick="closeModal()">Close</button>
        </div>
        <form hx-post="/htmx/workflows/{_escape(wf.id)}/trigger" hx-target="#run-status-result">
          <div class="modal-body">
            <p style="color: var(--text-dim); margin-bottom: 12px;">{_escape(wf.description or 'Execute this workflow immediately.')}</p>
            {vars_inputs_html}

            <div id="run-status-result" style="margin-top: 16px;"></div>
          </div>
          <div class="modal-footer">
            <button type="submit" class="btn btn-primary">
              <span class="htmx-indicator spinner" style="margin-right: 6px;"></span>
              Start Run
            </button>
            <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
          </div>
        </form>
      </div>
    </div>
    """


def render_daemon_view(home, config) -> str:
    status = daemon_mod.status(home, config)
    alive = status.get("alive", False)
    pid = status.get("pid")

    log_path = runs_mod.resolve_logs_path(config) / "daemon.log"
    daemon_log_tail = ""
    if log_path.exists():
        try:
            lines = log_path.read_text().splitlines()
            daemon_log_tail = "\n".join(lines[-40:])
        except Exception:
            daemon_log_tail = "Could not read daemon log."
    else:
        daemon_log_tail = "No daemon.log found yet."

    status_badge = f'<span class="badge badge-success"><span class="dot dot-green"></span> RUNNING (PID {pid})</span>' if alive else '<span class="badge badge-danger"><span class="dot dot-red"></span> STOPPED</span>'
    action_btn = '<button class="btn btn-danger btn-sm" hx-post="/htmx/daemon/action?act=stop" hx-target="#main-view">Stop Daemon</button>' if alive else '<button class="btn btn-primary btn-sm" hx-post="/htmx/daemon/action?act=start" hx-target="#main-view">Start Daemon</button>'

    return f"""
    <div id="daemon-panel" class="panel">
      <div class="panel-header">
        <div class="panel-title">Daemon Control & Observability</div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-secondary btn-sm" 
                  hx-post="/htmx/daemon/action?act=tick" 
                  hx-target="#daemon-action-result">
            Tick Now
          </button>
          {action_btn}
        </div>
      </div>

      <div style="display: flex; gap: 20px; align-items: center; margin-bottom: 20px;">
        <div>
          <span style="color: var(--text-dim); margin-right: 8px;">Current Status:</span>
          {status_badge}
        </div>
      </div>

      <div id="daemon-action-result"></div>

      <div class="form-group" style="margin-top: 16px;">
        <div class="panel-title" style="font-size: 14px; margin-bottom: 8px;">Daemon Logs (last 40 lines)</div>
        <pre class="code-view">{_escape(daemon_log_tail)}</pre>
      </div>
    </div>
    """
