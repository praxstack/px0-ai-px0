# px0-ai-px0 fixes (branch fix/audit-2026-10)

Final gate on HEAD 22ae248: `go vet ./...` clean, gofmt clean on all touched files, `TMPDIR=<realpath> go test -race -count=1 ./...` ok. Nothing pushed.

| ID | Status | Commit | Test evidence |
|---|---|---|---|
| PX0-020 fuzzy panic | fixed | fab7a49 | fuzzy_unicode_test.go: reproduced `index out of range` panic before (fuzzy.go:70) with U+023A/U+0130 paths; passes after (ASCII-only fold via existing asciiLowerString in index.go and fuzzy.go). |
| PX0-001 Host allowlist + token mask | fixed | 160725c | security_test.go TestHostGuardRejectsForeignHost (all GET/POST routes 403 on foreign Host, localhost/IP/::1 ok), TestSettingsMasksGitHubToken (GET /api/settings and raw JSON never contain token; echoing the mask back does not clobber it). Before: tests do not compile / would return 200 and the token. |
| PX0-002 token on non-loopback bind | fixed | 6ab1b96 | TestNonLoopbackBindRequiresToken, TestLoopbackBindNeedsNoToken. Bind other than 127.0.0.0/8, ::1, localhost generates a random 128-bit token required on every request (query -> HttpOnly SameSite=Strict cookie, or Bearer); startup URLs carry it. Live smoke on 127.0.0.1 only: -host 0.0.0.0 gave 401 without token, 200 with; default bind gave 403 for Host evil.example.com. Servers stopped. |
| PX0-014 0600 token file | fixed | 22ae248 | TestSettingsFileIs0600AndAtomic (file 0600, dir 0700, .bak 0600); failed before (0644). session.go also now 0600/0700. |
| PX0-021 atomic write / no wipe | fixed | 22ae248 | TestInvalidSettingsNotWipedByWrite (updateSettingsMap/writeSettings now error and leave an unparsable file untouched; explicit raw save keeps a .bak); failed before. Writes are temp+rename. |

PX0-014 and PX0-021 share writeRawMapLocked, so they are one commit.

## Notes
- Later commits on PR #1 added the `-token`/`PX0_TOKEN`, `-no-auth` and `-allowed-hosts` options, base-path-scoped and HTTPS-aware token cookies, a token-free landing page, symlink-preserving atomic writes, full Unicode folding in fuzzy find, UTF-16 highlight positions, and a fix for the git `index.lock` test flake. Each has a regression test.
- Remaining security follow-ups are tracked privately by the owner.
- A full `-race` run takes 2.5-7 min here; Go needs `make web` first (web/app.js is gitignored, built locally, not committed).
