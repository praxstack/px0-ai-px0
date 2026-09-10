"""Content for the store scaffolded by `px0 init`, and the ideas it offers.

px0 used to ship no workflows at all: a store full of things you did not ask
for is a store you have to read before you can trust it. That held for
anything that writes -- it still does, and always will, for `WORKFLOWS` below.
But it left day one silent for the handful of apps almost every engineer
already has open: GitHub, Linear, Slack. Those three get a small, deliberately
curated set of read-only, view-only starters instead of an empty `workflows/`
folder -- each one only looks, tells you what it found, and needs the matching
app connected before it can run. Nothing here ever posts, files, or sends
anything on its own; that line is still something you have to ask for
yourself, via `px0 workflows new`.

For everything past those three apps, px0 still ships *sentences*, not files.
Each recipe in `RECIPES` below is what you would say during the interview.
Picking one fills in the first answer and the interview proceeds exactly as
it would have if you had typed it -- which keeps every write-capable workflow
in the store something the user asked for, while removing the blank page.
"""

from px0.catalogue import CatalogueTool

GUIDELINES: dict[str, str] = {}

WORKFLOWS: dict[str, str] = {
    "github-review-queue.md": """\
---
id: github-review-queue
kind: workflow
version: 1
description: Pull requests waiting on my review
request: Show me pull requests where my review has been requested
trigger:
  schedule: "0 8 * * 1-5"
inputs:
  - id: prs
    tool: composio:GITHUB_SEARCH_ISSUES_AND_PULL_REQUESTS
    args:
      q: "is:pr review-requested:@me state:open"
      sort: updated
      order: desc
output:
  target: inbox
  attention: needs_action
timeout: 90s
---
Summarize `{{prs}}` as a short list: repo, title, how long it's been waiting,
and the link. Group anything waiting more than 2 days at the top. If there is
nothing waiting, say so in one line.
""",
    "linear-my-issues.md": """\
---
id: linear-my-issues
kind: workflow
version: 1
description: Linear issues assigned to me
request: Show me Linear issues assigned to me
trigger:
  schedule: "0 8 * * 1-5"
inputs:
  - id: me
    tool: composio:LINEAR_GET_CURRENT_USER
  - id: issues
    tool: composio:LINEAR_LIST_LINEAR_ISSUES
    args:
      assignee_id: "{{me.id}}"
output:
  target: inbox
  attention: needs_action
timeout: 90s
---
Summarize `{{issues}}` as a short list grouped by state, noting anything
overdue or high priority first. If nothing is assigned to me, say so in one
line.
""",
    "slack-recent-activity.md": """\
---
id: slack-recent-activity
kind: workflow
version: 1
description: What happened in my Slack channels and DMs recently
request: Show me recent activity in my Slack channels and DMs
trigger:
  schedule: "0 8 * * 1-5"
tools:
  - composio:SLACK_LIST_CONVERSATIONS
  - composio:SLACK_FETCH_CONVERSATION_HISTORY
output:
  target: inbox
  attention: fyi
timeout: 150s
---
List the channels and DMs I'm in, then pull messages from the last 24 hours in
each. Summarize what happened per channel in a few bullets -- do not claim
anything is "unread", just what's recent. Skip channels with no new activity.
If nothing happened anywhere, say so in one line.
""",
}


# (id, the sentence, what it touches). Drawn from docs/workflow_usecases.md and
# kept short: this is a nudge, not a catalogue. The full 120 are in the docs,
# and `px0 workflows recipes --all` points there. GitHub/Linear-review-attention
# and Slack-catch-up are covered by the pre-baked starters above, so they are
# not repeated here.
RECIPES: list[tuple[str, str, str]] = [
    ("friday-pr-digest",
     "Every Friday, summarize the pull requests I reviewed this week and post "
     "it to my team channel",
     "GitHub, Slack"),
    ("morning-brief",
     "Each weekday morning, brief me on today's meetings and the emails I have "
     "not replied to",
     "Google Calendar, Gmail"),
    ("error-to-ticket",
     "Turn last night's error spike into a triaged bug ticket",
     "Sentry, Linear"),
    ("release-notes",
     "Draft release notes from the commits since the last tag and file them as "
     "a page",
     "GitHub, Notion"),
    ("sprint-status",
     "Post a Monday sprint status from our issue tracker to the team channel",
     "Jira, Slack"),
    ("support-themes",
     "Group this week's support tickets by theme and open issues for the top "
     "three",
     "Zendesk, Linear"),
    ("reading-library",
     "Save every newsletter I star to my reading library",
     "Gmail, px0 brain"),
    ("deploy-report",
     "Run our deploy script and post what it printed",
     "shell, Slack"),
    ("weekly-reading",
     "Every Sunday, summarize what I read into my brain this week and write it "
     "to a file",
     "px0 brain, file"),
    ("standup",
     "Every weekday at 9am, draft my standup from yesterday's commits and hold "
     "it for me to approve before posting",
     "GitHub, Slack"),
    ("docs-attention",
     "Show me docs shared with me that need a read or a sign-off",
     "Notion, Google Docs"),
    ("pr-comment-nudge",
     "When one of my open pull requests has gone 2 days without a review, "
     "draft a friendly nudge comment and hold it for my approval before "
     "posting it",
     "GitHub"),
    ("linear-triage",
     "Turn new bug reports into triaged Linear issues, or update the "
     "matching issue when there's new information, holding each one for my "
     "approval before it writes",
     "Linear"),
]


# The Composio tool definitions WORKFLOWS above reference, pre-seeded into
# `.state/catalogue.json` by `store.init()` so the three starters validate
# and are ready to run offline, without waiting on a live catalogue search
# the moment they're written. Captured from Composio's own catalogue
# (`px0 tools search --toolkit <x> --json`); the params/description are its
# schema, not something px0 invented -- `catalogue.fetch()` would return the
# same shape from a live lookup.
CATALOGUE_SEED: list[CatalogueTool] = [
    CatalogueTool(
        slug="GITHUB_SEARCH_ISSUES_AND_PULL_REQUESTS",
        toolkit="github",
        name="Search issues and pull requests",
        description=(
            "Searches github for issues and pull requests. use qualifiers to scope "
            "searches: `repo:owner/name` for specific repos, `org:orgname` for "
            "organizations, `user:username` for personal repos, `assignee:@me` for "
            "your assignments. combine with `is:issue`, `is:pr`, `state:open`, "
            "`label:\"name\"` filters."
        ),
        is_write=False,
        params={"q": "string*", "order": "string", "page": "integer",
                "per_page": "integer", "raw_response": "boolean", "sort": "string"},
    ),
    CatalogueTool(
        slug="LINEAR_GET_CURRENT_USER",
        toolkit="linear",
        name="Get current user",
        description=(
            "Gets the currently authenticated user's id, name, email, and other "
            "profile information. use this to identify 'me' in other linear "
            "operations that require user id filtering."
        ),
        is_write=False,
        params={},
    ),
    CatalogueTool(
        slug="LINEAR_LIST_LINEAR_ISSUES",
        toolkit="linear",
        name="List Linear issues",
        description=(
            "Lists non-archived linear issues; if project id is not specified, "
            "issues from all accessible projects are returned. can also filter by "
            "assignee id to get issues assigned to a specific user."
        ),
        is_write=False,
        params={"after": "string", "assignee_id": "string",
                "first": "integer", "project_id": "string"},
    ),
    CatalogueTool(
        slug="SLACK_LIST_CONVERSATIONS",
        toolkit="slack",
        name="List conversations",
        description=(
            "Retrieves conversations accessible to a specified user (or the "
            "authenticated user if no user id is provided), respecting shared "
            "membership for non-public channels."
        ),
        is_write=False,
        params={"cursor": "string", "exclude_archived": "boolean",
                "limit": "integer", "types": "string", "user": "string"},
    ),
    CatalogueTool(
        slug="SLACK_FETCH_CONVERSATION_HISTORY",
        toolkit="slack",
        name="Fetch conversation history",
        description=(
            "Fetches a chronological list of messages and events from a specified "
            "slack conversation, accessible by the authenticated user/bot, with "
            "options for pagination and time range filtering."
        ),
        is_write=False,
        params={"channel": "string*", "cursor": "string", "inclusive": "boolean",
                "latest": "string", "limit": "integer", "oldest": "string"},
    ),
]
