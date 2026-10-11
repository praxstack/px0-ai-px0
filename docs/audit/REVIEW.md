# px0-ai-px0 review: branch fix/audit-2026-10

Reviewer: Opus (independent). Fix worktree, HEAD `22ae248`, merge-base with origin/master `4fc9eb2`. I left the branch untouched (status clean at the end). I made a throwaway base worktree for the before/after checks, then removed it.

## Verdict: request-changes

Status after this review: M1-M3, m1-m6 and n1-n4 were fixed by later commits on PR #1 (see FIXES.md). Remaining items are tracked privately by the owner and are omitted below.

The four commits fix the root causes they cite. I checked each one before and after: the fuzzy panic, the token leak over a foreign Host, the 0644 file mode and the wipe of an invalid file. Two things need work before merge:
1. The new access token has no opt-out. It breaks deployment modes that Dockerfile, README and docs/features/remote-workspaces.md still advertise.
2. The Host allowlist has no override. It breaks Host-preserving reverse proxies and tunnels on a loopback bind.

The fuzzy regression test also passes on the unfixed code.

Counts: blocker 0, major 3, minor 7, nit 6 (one minor and part of one nit omitted here).

## Per-commit verdicts

| Commit | Finding | Verdict | Notes |
|---|---|---|---|
| fab7a49 fuzzy ASCII fold | PX0-020 | approve-with-nits | Fix is correct. The committed test does not catch the bug (M3). Non-ASCII case-insensitive matching is gone (m1). |
| 160725c Host allowlist + token mask | PX0-001 | request-changes | Allowlist logic is sound and matches the existing `localPost`. Masking is correct. No override for proxies/tunnels (M2). Misplaced doc comment (n1). |
| 6ab1b96 access token on non-loopback | PX0-002 | request-changes | Constant-time compare, HttpOnly + SameSite=Strict cookie, good entropy. No opt-out and docs not updated (M1). Cookie collides across instances (m3). FIXES overstates hostname support (m2). |
| 22ae248 atomic 0600 settings write | PX0-014, PX0-021 | approve-with-nits | Strict read before write, temp+fsync+rename, .bak. Existing 0755 dir and 0644 file are not migrated until a write (m4). Symlinked settings.json gets replaced by a plain file (m5). |

## Focus questions

- **Does allowing any IP literal re-open DNS rebinding?** No. Rebinding needs a DNS name, and the browser then sends that name as Host. A Host that is an IP literal means the user typed an IP, so no DNS step happened. I probed `hostAllowed` directly:
  - Accepted: `[::1]`, `::1`, `[::ffff:127.0.0.1]:7`, `LOCALHOST:1`, `localhost.`, `evil.localhost`.
  - Rejected: `127.0.0.1.nip.io`, `0x7f000001`, `2130706433` (browsers normalise numeric hosts to dotted form anyway), `""`, `foo.local`.
  - Ports are not checked, which is fine for rebinding.
  - Zone-scoped IPv6 (`[fe80::1%25en0]`) is rejected. That is fail-closed and only a usability issue.
  - The rule is the same Host rule upstream already used in `localPost` (lspsetup.go:264).
  - IP literals are not a CSRF defence. Cross-site POSTs are still stopped by `localPost`'s Origin==Host check, which is unchanged.
- **Is every real entry point covered by the opt-in `Server.Secure`?** Yes, today. `NewServer` is called only at main.go:157, and `Secure(*host)` runs before `srv.Serve(ln)` (main.go:285). PR-review mode uses the same path. There is no second listener or handler. The guard is the first thing in `ServeHTTP`, before the mux. 
- **Constant-time compare:** yes, `subtle.ConstantTimeCompare` for cookie, Bearer and query. A length mismatch returns early, which leaks only the length. The token is a fixed 32 hex characters, so that is fine.
- **Cookie flags:** `Path=/; HttpOnly; SameSite=Strict` (confirmed from the Set-Cookie header). There is no `Secure` attribute, which is correct over plain HTTP. Cookies are scoped by host, not port, so:
  - another px0 instance on the same host overwrites the cookie (m3);
  - pages on other ports of the same host are same-site, but their POSTs still fail `localPost`'s Origin check.
- **Token in URL over HTTP:**
  - The token is printed in the URL and passed to `openBrowser` (visible in argv for a moment).
  - It is never stripped from the address bar, so it ends up in history and in any link the user copies (m6).
  - With `-verbose` it is logged via `RequestURI` (n3).
  - Referer leaks are limited by the browser's default `strict-origin-when-cross-origin` policy.
- **Host check skipped when a token is set:** this is acceptable. A rebinding page has no token, and the host-scoped cookie is not sent to the attacker's name. But `localPost` still enforces the IP/localhost Host on every POST. So in token mode, POSTs over a hostname (`mac.local`) still return 403. FIXES says "hostnames like mac.local work"; that is true only for GETs (m2).
- **Atomic write and 0600:**
  - The temp file is created in the same directory, chmod 0600, written, `Sync`ed, closed, then renamed, and cleaned up on every error path.
  - `.bak` is written 0600 and chmod'ed in case it already existed.
  - The strict read refuses to write over an unparsable file; whitespace-only and `null` count as empty.
  - `saveRawSettingsJSON` stays the explicit repair path and keeps a `.bak`.
  - Session file: also atomic and 0600. Its errors are ignored, as before. Note that on darwin `File.Sync` is F_FULLFSYNC and now runs on every tab or dir change (n5).
- **Fuzzy-find ASCII folding:** correct. The path's `lower` and the query are now byte-for-byte aligned with `Path`, so `pos` cannot go out of range. I confirmed with a real `Index.Build` over files named `ȺȺȺ…zz.go` and `İİİ…yy.go`:
  - base: `panic: index out of range [29] with length 25` (fuzzy.go:68);
  - HEAD: passes.

  The cost is that `über` no longer finds `Über.go` (m1).

## Findings

### Major

- **M1: the non-loopback token has no opt-out, and documented deployments break or are undocumented** (security.go:69-76, main.go:159).
  - Dockerfile `ENTRYPOINT ["px0","-host","0.0.0.0",...]` now needs a token that exists only in `docker logs`. The printed network URLs are container IPs, so the user has to rebuild the URL as `localhost:7777/?token=…` by hand.
  - docs/features/remote-workspaces.md §4 describes multi-tenant review pods behind an edge gateway with `-base-path … -host 0.0.0.0`. The gateway has no token, so every request returns 401.
  - README and remote-workspaces.md are not updated.
  - Fix: add a `-token` flag / `PX0_TOKEN` env to supply a known token, plus an explicit `-no-auth` (or `-insecure`) for an authenticating proxy. Document both, and print a token-only line that the user can append to any reachable host.
- **M2: the Host allowlist has no override, which breaks the advertised tunnel/reverse-proxy-on-loopback setup** (security.go:51-61, 115).
  - The README advertises "reverse proxy, or Cloudflare Tunnel".
  - Proxies that keep the client Host send the public hostname (Caddy `reverse_proxy` and cloudflared by default). With the default `-host 127.0.0.1` there is no token, so every GET now returns 403.
  - On base, GET/read-only browsing worked; only `localPost` mutations were refused.
  - Fix: add an `-allowed-hosts` flag / `server.allowedHosts` setting, or let a configured token replace the Host check on loopback too. Add a docs note.
- **M3: the committed fuzzy regression test passes on the unfixed code** (fuzzy_unicode_test.go:11).
  - The test builds `FileEntry.lower` itself with `asciiLowerString`, so it never exercises `index.go` `Build`, which is where the length-changing `strings.ToLower` was.
  - I ran it on base: `ok`. FIXES.md's "reproduced panic before" is not true of this test.
  - Fix: build an `Index` over a temp dir with `Ⱥ`/`İ`-prefixed names (several of them, so the byte shift exceeds the suffix) and call `FuzzyFind(ix.Files(), …)`. That fails on base with the panic above.

### Minor

- **m1:** fuzzy find is now ASCII-only case-insensitive. `über` no longer matches `Über.go`, and the same goes for Cyrillic, Greek and other scripts (verified). This is an acceptable trade-off from the finding's own options, but it is undocumented. Alternative: fold rune by rune with an offset map, or keep `ToLower` only when the length is unchanged.
- **m2:** FIXES.md says "hostnames like mac.local work on LAN binds". POSTs through a hostname still return 403 from `localPost` (I verified `/api/session` with a valid Bearer token and a matching Origin). Correct the claim, or relax `localPost`'s Host rule when a token is set (keep the Origin check).
- **m3:** the cookie name `px0_token` is shared by all instances on the same host (cookies ignore port). Opening a second `-host 0.0.0.0` instance makes the first one return 401 (verified). Fix: a per-port or per-token cookie name, e.g. `px0_token_<port>`.
- **m4:** `MkdirAll(dir, 0o700)` does not tighten an existing `~/.px0` (0755), and an existing 0644 `settings.json` stays 0644 until the next settings write. FIXES' "dir 0700" holds only for fresh installs, and the test only covers a fresh dir. Fix: a best-effort `os.Chmod(dir, 0o700)` and a chmod of the file at startup or on read.
- **m5:** temp+rename replaces a symlinked `settings.json` (dotfile managers like stow, or chezmoi in symlink mode) with a regular file. That silently detaches it from the dotfiles repo. Base `os.WriteFile` wrote through the link. Fix: `filepath.EvalSymlinks(p)` before choosing the temp dir and the rename target.
- **m6:** the `?token=` stays in the address bar and history after the cookie is set, so copied file links carry the credential. Fix: after setting the cookie on a top-level GET, 302 to the same URL without `token`.

### Nit

- **n1:** settings.go:496: the `// readMergedSettingsMap returns all settings…` line now sits on top of the `maskedSecret` const's doc, and `readMergedSettingsMap` has lost its doc comment.
- **n2:** search.go:413 `unindexedTarget` still builds `FileEntry.lower` with `strings.ToLower`. It is not reachable from FuzzyFind today; it is grep-only. Use `asciiLowerString` for consistency.
- **n3:** with `-verbose`, the request log prints `RequestURI`, including `?token=` (server.go:264).
- **n4:** a `POST /api/settings` with an empty body takes its payload from the URL query (server.go:1997-2003). In token mode, `?token=…` would then be persisted as a `token` key in settings.json. Strip `token` from the query payload.
- **n5:** `writeFileAtomic` fsyncs (F_FULLFSYNC on darwin) for every session update under `sm.mu`. It is cheap enough, but the session file is not critical data and could skip `Sync`.
- **n6:**
  - FIXES.md names the branch `fix/audit-2026-10-02`; the actual branch is `fix/audit-2026-10`.

## Check results (macOS arm64, Go 1.27.1, `TMPDIR` realpath as per SETUP.md)

| Check | Base 4fc9eb2 | HEAD 22ae248 |
|---|---|---|
| `go build ./...` | n/a | ok |
| `go vet ./...` | clean (per SETUP) | clean |
| `gofmt -l .` | 8 pre-existing files | same 8, no touched file listed |
| `go test -count=1 ./...` | ok (75.0s) | ok (87.7s) |
| `go test -race -count=1 ./...` | not run | ok (472s) |

Targeted before/after checks:

| Test | Base | HEAD |
|---|---|---|
| `TestSettingsFileIs0600AndAtomic` | FAIL (`-rw-r--r--`) | pass |
| `TestInvalidSettingsNotWipedByWrite` | FAIL | pass |
| `TestFuzzyFindLowerChangesLength` | **pass** (does not catch the bug, see M3) | pass |
| Reviewer real-index fuzzy repro | panic | pass |
| Reviewer GET `/api/settings` with a foreign Host | 200, token in body | 403; token masked on an allowed Host |

`security_test.go` does not compile on base, because `Secure`, `maskedSecret` and `tokenCookie` are new. The behaviour it targets is confirmed by the reviewer probe above.

## FIXES.md claims I could not confirm or found false

- "fuzzy_unicode_test.go: reproduced index out of range panic before": false for the committed test (it passes on base). The bug and the fix are real (my repro).
- "hostnames like mac.local work on LAN binds": GETs only; POSTs return 403.
- "dir 0700": fresh installs only; existing directories are not tightened.
- "Live smoke on 127.0.0.1 only … Servers stopped": not re-run by me. Equivalent behaviour is covered by httptest.
- "One full non-race run failed once with no captured detail": not reproduced; my non-race and race runs both passed.
