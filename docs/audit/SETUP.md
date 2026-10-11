# px0-ai-px0 setup (macOS, arm64) - verified 2026-10-05

Repo: praxstack/px0-ai-px0 (branch master, v0.1.16, fork of px0-ai/px0). Go 1.27.1 (mise), Node/Bun present. Nothing extra installed.

## Install / build
    make build        # runs node/bun scripts/build-web.js (web/app.js, gitignored) then go build -> ./px0 (12M)
Deps (chroma v2.27.0, goldmark v1.8.6) are fetched by go automatically. No env vars needed.

## Lint / vet
    go vet ./...      # clean
    gofmt -l .        # 8 files unformatted (agent_test.go highlight.go highlight_test.go lsp.go lsp_test.go px0_test.go settings_test.go ui.go) - cosmetic

## Test
    make web && go test ./...                      # on macOS default TMPDIR: 3 FAIL
    TMPDIR=$(cd "$TMPDIR" && pwd -P) go test -count=1 ./...   # passes (ok px0 46s)
Failures with the default TMPDIR: TestPRReviewerChangesInIndex (git_test.go:1148), TestGitStagedFilesStatAndDiff (:1226), TestDeletedFileHandling (:1337).
Root cause: t.TempDir() returns /var/folders/..., git rev-parse --show-toplevel returns /private/var/...; repoRelKey (git.go:78) does filepath.Rel(toplevel, root), gets "../../.." and drops every path. Test-only on macOS: main.go:312 EvalSymlinks the served root, so the CLI is fine.

## Run (smoke verified)
    ./px0 -no-open -no-telemetry -no-update -no-agent -port 17777 .
    # then open http://127.0.0.1:17777 ; stop with Ctrl-C
Verified with curl: / 200 (44KB HTML), /api/meta, /api/tree, /api/file?path=go.mod, /api/find?q=server, /api/search?q=func+main, /api/outline?path=main.go all 200 with expected JSON; unknown path 404. Server stopped afterwards, nothing left listening.
Other: `./px0 --version` -> px0 0.1.16 (darwin/arm64). Use -no-telemetry -no-update to avoid network side effects. PR review (`px0 <pr-url>`) needs GitHub auth (token resolved from settings/gh; not tested). Agent harness editing needs claude/codex/etc. CLIs (not tested). Mermaid vendor JS is fetched on demand (web/vendor/*.min.js gitignored).

## Findings
- P3 test-gap/build-ci: 3 git tests fail on macOS default TMPDIR (symlinked /var). Fix: resolve t.TempDir via filepath.EvalSymlinks in test helper, or make repoRelKey compare resolved paths.
- P3 tech-debt: 8 files not gofmt-clean.
- Secrets: gitleaks working-tree scan on repo returned no findings.
- CI (.github/workflows/ci.yml) runs on ubuntu only, so the macOS failure is not caught.
