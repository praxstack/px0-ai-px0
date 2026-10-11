# px0-ai-px0 — Understanding (comprehension lead)

Repo: praxstack/px0-ai-px0 ( PUBLIC fork of px0-ai/px0). Branch master, v0.1.16, HEAD 4fc9eb2. `git rev-list --left-right --count origin/master...upstream/master` = 0 0, so the fork is level with upstream; no local divergence, no extra branches.

## Purpose
px0 is a browser-based "IDE for reviewing AI-generated code": a single static Go binary (no CGO, no runtime deps) serving an embedded vanilla-JS UI on a local HTTP port. Reads-first design: file tree, fuzzy find, regex search, symbol outline, Chroma syntax highlighting (~280 langs), Markdown/Mermaid/CSV preview, LSP go-to-def/hover/call trails, Git panel (stage/commit/push/pull ff-only, unpushed commits), GitHub PR review (`px0 <pr-url>`), and delegated edits through installed coding harnesses (claude, gemini, cursor-agent, agy, opencode, codex, aider, goose) with multi-turn "threads". License file present; upstream is the real project (upstream issues/PRs shown by gh belong to px0-ai/px0 era, e.g. #207, #229).

## Authoritative vs historical docs
- Authoritative: AGENT.md -> docs/agents/README.md (rules, doc-sync matrix, code map), docs/internals/* (design), docs/features/* (user guides), README.md, PUBLISHING.md, BENCHMARKS.md, CONTRIBUTING.md.
- No SPEC/PLAN/HANDOFF/PROGRESS/CHANGELOG/openspec files exist. Release notes are GitHub-generated. Roadmap = open upstream issues.
- docs/README.md and README.md are marketing-ish and drift (see findings).

## Module map (Go, package main, 23.6k lines incl. tests)
- main.go: flags (-port 7777, -host 127.0.0.1, -no-open, -no-lsp, -no-git, -no-update, -no-telemetry, -agent, -no-agent, -base-path, -verbose, -quiet), target resolution (dir/file:line/PR URL), EvalSymlinks of root (main.go:312), listener walk-forward 100 ports (main.go:458).
- server.go (2037): http.ServeMux with ~69 routes under routePath(); gzip + CSP + no-store middleware; static embed; settings endpoints; git endpoints; idle FreeOSMemory.
- index.go, ignore.go, fuzzy.go, search.go, symbols.go: parallel tree walk (NumCPU*4), gitignore engine, fuzzy path match, parallel regex grep, regex symbol outline.
- highlight.go (Chroma windowed chunks, hlChunk=1000), markdown.go (goldmark + sanitizer mdSanitize), table.go (CSV/TSV).
- git.go, git_watcher.go: shell-outs to `git` (status porcelain v2, diff, add/reset/commit/push/pull/fetch), repoRelKey subtree mapping, watcher for live status.
- pr.go, github.go, provider.go: PR session (temp checkout/merge-base fetch), GitHub REST review comments/submit, token from env/gh; provider abstraction (Name()).
- agent.go (1541), agent_unix/windows.go, thread.go (1437): harness detection, command templates, job manager with overlap refusal, SSE streams, threads persisted to config dir.
- lsp.go, lspnav.go, lspservers.go, lspsetup.go, calls.go: LSP client/manager, registry of servers, auto-install via shell (`go install`, `npm i -g`), call-hierarchy trails.
- settings.go (JSON schema + merged defaults), session.go (workspace session state), update.go (self-update from GitHub releases with sha256 checksums.txt), telemetry.go (PostHog, key injected via ldflags), metrics*.go (process RSS/CPU), ui.go (terminal narration), tty_*.go.
- web/: index.html, style.css, themes/*.css, src/*.js (ES modules; main.js, state.js, renderer.js, tree.js, tabs.js, pr.js, thread.js, agent.js, gitpanel.js, mermaid.js, vim.js ...), scripts/build-web.js bundles to web/app.js (gitignored, regenerated; go:embed needs it so a plain `go build` on a fresh clone fails until `make web`).

## Flows
1. Start: parse args -> resolve root -> build Index (+git probe) -> listen -> print URL -> open browser; background auto-update unless -no-update; telemetry unless -no-telemetry or no key.
2. Browse: UI calls /api/tree, /api/file (windowed), /api/find, /api/search, /api/outline, /api/diff, /api/gutter; SSE /api/stream pushes file/git changes.
3. Edit: selection -> /api/agent/edit|batch -> harness subprocess in workspace -> reload changed files.
4. Threads: /api/threads/* store conversations; harness resumed per turn.
5. Git: /api/git/stage|unstage|commit|commit-message(AI)|push|pull(ff-only); /api/unpushed.
6. PR review: `px0 <url>` -> /api/pr/* comments/submit.
7. LSP: lazy start per language; setup/install endpoints.

## Data and persistence
Config dir `$XDG_CONFIG_HOME/px0/` or `~/.px0/`: settings.json, threads; sessions in `$XDG_STATE_HOME/px0/sessions` or `~/.px0/sessions`; vendor cache `~/.px0/cache/vendor/` (Mermaid fetched on demand). Nothing written into workspaces (by design; git panel is the explicit exception).

## Security model (as read, before the audit PR)
Mutating endpoints (POST) go through `localPost` (lspsetup.go:264): POST only, Origin==Host, Host is IP or localhost. 25 call sites. At audit time GET endpoints had no Host check and `-host 0.0.0.0` had no auth (upstream issue #207). PR #1 added a Host allowlist and an access token for non-loopback binds; see FIXES.md. Other security notes are kept privately by the owner.

## Build / run / test
- `make build` (web bundle via node/bun then go build), `make test`, `go run . -dev .`, `make dist`, `make publish <ver>`.
- Verified here: `node scripts/build-web.js` ok (249.9 KB), `go build` ok, `go vet` clean, `go test ./...` FAILS 3 tests on macOS default TMPDIR, passes (ok px0 41s) with a symlink-resolved TMPDIR. `gofmt -l` lists 8 files.
- Logs: go-test.log, go-test-isolated.log, go-test-resolvedtmp.log in this dir.

## CI
.github/workflows/ci.yml: ubuntu only, push to master + manual (NO pull_request trigger): bundle, go build, go test -v. release.yml: on tag v*, Go 1.24 pinned, node 20, cross-compile 14 targets, sha256 checksums, softprops release. gh run list: all master CI and Release runs green; one PR-branch CI run shows `action_required` (fork-PR approval gate).

## GitHub backlog
Open issues: 10 listed (#227 model version select, #224 auto theme, #222 upward diff context, #217 sidebar toggle, #216 pi harness, #215 committed diff view, #210 fixed URL, #209 lean memory $HOME, #207 BUG 0.0.0.0 unauthenticated, #205 BUG drag-select). Open PRs: #229 pi/omp harness, #226 Bitbucket, #225 auto theme, #223 fuzzy perf, #221 persist UI, #218 committed diff, #208 security consent for non-loopback (fixes #207). Merged #219. Cadence: 168 commits, ~147 by one author, bursts of 14-18 commits/day, first commits 2026-09-12, v0.1.16 on 2026-10-03 (about 3 weeks old, 16 releases).

## Roadmap vs reality (spot checks, all verified in code unless noted)
1. Mermaid support (docs/features/markdown-preview.md:25) -> web/src/mermaid.js exists, vendor LICENSE.mermaid present. OK.
2. Theme preference persisted (b6f9881) -> web/src/theme-preference.js + theme.test.js. OK (JS test not run by CI: no JS test step).
3. Content-Security-Policy header -> server.go:233,274. OK.
4. localPost on all mutating endpoints -> 25 call sites incl. git/agent/thread/pr/settings. OK.
5. /api/raw hardening -> commit bb69414; CSP object-src none. OK (not deeply tested).
6. ReDoS fix in markdown link parsing (26edf72) -> markdown.go mdSanitize + tests. Plausible, not fuzzed.
7. Unpushed commits review -> git.go + web/src/unpushed.js. OK.
8. Threads persisted -> thread.go, thread_test.go. OK.
9. Auto-update with sha256 verification -> update.go checksumFor. OK; note "Prompt user to restart" (665a00a) replaced re-exec.
10. UPX removed (d031cfe) -> docs/internals/architecture.md:218 says no packers. OK. But docs still claim ~3.5 MB binary; real release is 12.4-12.9 MB (gh release view v0.1.16). DRIFT.
11. "DNS rebinding checks" (README.md:89, docs/features/remote-workspaces.md:25, architecture.md:191) -> true only for POST; GET reads were not covered at audit time. DRIFT; addressed by PR #1.
12. "Master index of all 17 feature areas" (docs/README.md) -> docs/features has 20 guides (threads, github-pr-review, table-view not in that count/list). DRIFT.
13. README "Go 1.24+" vs go.mod `go 1.25`; release.yml pins go-version '1.24'. DRIFT; works only via GOTOOLCHAIN auto-download (release runs succeeded).

## Risk areas
- Network/HTTP surface: harness subprocess execution, LSP auto-install shell commands.
- git.go shell-outs: path/arg handling, symlinked roots (repoRelKey), global git config leakage (user gpg signing) in commit flow.
- Self-update: downloads and replaces its own binary.
- Agent/thread concurrency and process cleanup (agent.go, thread.go); SSE leaks.
- Telemetry (PostHog distinct_id) default behaviour.
- Frontend: 40 ES modules, no JS tests except theme.test.js, not run in CI
- Test portability: macOS symlink TMPDIR; tests depend on user git env only partly (helper isolates global config but code under test does not).
