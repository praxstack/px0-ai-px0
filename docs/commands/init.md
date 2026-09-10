# `px0 init`

Scaffold a store: create the folder layout, write `config.toml`, install the
starter workflows, take the first version snapshot, and offer to connect the
apps those starters use.

Implemented by `px0/store.py` (`store.init`) and `px0/starters.py` (the
starter content itself), driven by `cli.cmd_init` and `cli._connect_starter_apps`.

```
px0 init [dir] [--harness {claude,gemini,opencode,pi}] [--composio-key KEY]
```

## Arguments

### `dir`

Optional. Where to create the store.

- **Input:** a filesystem path.
- **Default:** `$PX0_HOME` if set, else `~/.px0`.
- Created if it does not exist. Running against an existing store is safe: it
  fills in anything missing and leaves everything else alone.

```shell
px0 init                      # ~/.px0
px0 init ~/work/px0-store     # somewhere else
PX0_HOME=/tmp/scratch px0 init
```

## Options

### `--harness {claude,gemini,opencode,pi}`

Which coding-agent CLI to use as the model backend. Written to
`model.harness_cmd` in the generated `config.toml`.

- **Input:** one of `claude`, `gemini`, `opencode`, `pi`. Each expands to that
  agent's full non-interactive invocation.
- **Default:** `claude`, which expands to `claude -p`.
- To use something not on the list, set the full command afterwards with
  `px0 config set model.harness_cmd "<command>"`.

```shell
px0 init --harness gemini
```

### `--composio-key KEY`

Composio API key, used to authorize the external apps workflows call. Verified
against Composio before being saved.

- **Input:** a Composio API key string.
- **Default:** none. If omitted, `init` prompts for one interactively; you can
  skip the prompt and add it later with `px0 config composio`.
- Stored in `connectors.composio_api_key`. `px0 store export` redacts it, along
  with its version history.

```shell
px0 init --composio-key ak_...
```

## What it creates

```
<store>/
  workflows/          the three starters below
  guidelines/         empty -- guidelines are still something you write
  brain/{docs,blogs,papers,work}/
  output/
  .state/{index,ingest}/
  .state/schema       the on-disk schema version
  .state/catalogue.json   pre-seeded with the Composio tools the starters use
  config.toml
```

Three read-only, view-only starter workflows are always written, whether or
not their app ends up connected in this run: `github-review-queue` (pull
requests waiting on your review), `linear-my-issues` (issues assigned to
you), and `slack-recent-activity` (recent channel/DM activity, summarized --
Composio exposes no unread state, so this is framed as "recent," not
"unread"). None of the three ever posts, files, or sends anything; writing a
workflow that does is still something you ask for with `px0 workflows new`.
Content lives in `starters.WORKFLOWS`; pass `starter_content=False` to
`store.init()` to scaffold a bare store without them (what the test suite
uses).

Once a Composio key is configured (existing, supplied, or just entered), init
prompts to connect an issue tracker and a messaging tool:

1. **Issue Tracker** (`Linear`, `GitHub`, or `None`):
   - **Linear:** Requires a personal API key. Create one at `https://linear.app/settings/account/api` under *Personal API keys*. Stored in `.state/credentials.toml` under `[linear]`.
   - **GitHub:** Requires a Personal Access Token (`repo` or `issues` scope). Generate one at `https://github.com/settings/tokens`. Stored in `.state/credentials.toml` under `[github]`.

2. **Messaging Tool** (`Slack`):
   - **Slack:** Requires a Bot User OAuth Token (`xoxb-...`) or User Token (`xoxp-...`). Create an app at `https://api.slack.com/apps`, add bot scopes (`chat:write`, `channels:read`, `channels:history`, `app_mentions:read`, `reactions:write`), install it to your workspace, and provide the token. Stored in `.state/credentials.toml` under `[slack]`.

Then init walks the three starter apps in turn: checks whether each is already connected,
offers to start authorization if not (prints a consent URL, waits for Enter,
rechecks), and -- the moment an app is `ACTIVE` -- runs its starter workflow
immediately via `runner.run(..., trigger="manual")` and prints the first line
of what it found. An app left unconnected (skipped, or the consent never
finished) has its workflow's `enabled` frontmatter key set to `false` rather
than left to fail on the daemon's first scheduled fire; `px0 tools connect
<app>` then `px0 workflows enable <id>` turns it back on later. No Composio
key at all skips this whole step with a hint, same as the key prompt itself
under non-interactive stdin.

## Output

Lists what was created, then points at the next step -- `px0 ui`, to see
whatever the connected starters found, ahead of `px0 workflows new`. It also
mentions that `brain.path` can point at an existing Markdown folder -- see
[`px0 brain`](brain.md#pointing-the-brain-at-an-existing-vault).

## Exit codes

| Code | When |
| ---- | ---- |
| `0` | Store created or already complete |
| `1` | The path is unusable, or a supplied Composio key was rejected |
