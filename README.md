<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://px0.ai/logo/px0-logo-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="https://px0.ai/logo/px0-logo-light.png">
  <img alt="px0" src="https://px0.ai/logo/px0-logo-dark.png" width="120">
</picture>

---

px0 is an IDE built for reviewing AI-generated code, optimized for speed. It turns your browser into a zero-latency console with native Git and GitHub integrations, instant search across massive codebases, and seamless handoff to local AI coding harnesses.

As AI agents author more code directly from the terminal, engineering productivity is no longer constrained by how fast you type - it is constrained by how fast you can review, navigate, and verify changes. px0 replaces heavy, multi-gigabyte editing suites with an instant, distraction-free environment built specifically for this review loop.

- < 1 ms cold start
- ~20–30 MB server daemon RAM (~100–180 MB total with browser tab, vs. VS Code's ~1,440 MB)
- Single static Go binary with zero runtime dependencies (no Electron, no Node, no CGO)
- ~280 languages tokenized natively via Chroma

See full performance benchmarks and comparisons at [px0.ai/benchmarks](https://px0.ai/benchmarks).

## Features

- GitHub PR reviews & Git panel: Review pull requests directly (`px0 <pr-url>`), inspect scoped merge-base diffs, draft inline review comments, and stage, commit, or push from the browser.
- Unpushed commit review: Read the commits your branch is ahead of its tracking branch by, one file diff at a time, before you push them.
- AI coding harness integration: Dispatch edits directly to Claude Code, Gemini CLI, Cursor Agent, Antigravity, OpenCode, Codex, Aider, or Goose with live reloading.
- Fast navigation: Fuzzy file search, symbol outline, and workspace regex search in milliseconds.
- Remote-first: Run on any remote server, VM, or container and browse locally without SSH key setups or remote daemons.
- Virtual rendering: Opens 400,000-line files smoothly by mounting only visible rows; frees memory back to the OS after 15 seconds of inactivity.
- Rich code viewer: 14 built-in themes, rendered Markdown with Mermaid diagrams, CSV/TSV table view, image inspector, and optional zero-config LSP for Go-to-Definition and hover.

## Installation

Quick install (macOS, Linux, BSD):

```bash
curl -fsSL https://px0.ai/install.sh | sh
```

Build from source (requires Go 1.24+ and Node.js or Bun):

```bash
git clone https://github.com/px0-ai/px0.git
cd px0
make build
install -d ~/.local/bin && install px0 ~/.local/bin/
```

To update an existing installation:

```bash
px0 --update
```

## Usage

```bash
# Inspect current directory
px0

# Inspect a specific directory or file
px0 ~/workspace/project
px0 main.go:42

# Review a GitHub pull request
px0 https://github.com/owner/repo/pull/123

# Remote or headless server mode
px0 -host 0.0.0.0 -port 7777 ~/workspace

# Behind an authenticating gateway under a subpath
px0 -base-path /rev-123/ -host 0.0.0.0 -no-auth -allowed-hosts tenant.example.com ~/workspace
```

When px0 binds to `0.0.0.0`, it prints a `network` URL for every unique
non-loopback IPv4 address on the machine, using the port selected by the
listener:

```text
  url:        http://0.0.0.0:7777
  network:    http://10.0.0.15:7777
  network:    http://192.168.1.42:7777
```

Open the address that is reachable from your local machine. The list can
include LAN, VPN, and container-network addresses, depending on the remote
host's interfaces.

### Access token and allowed hosts

On any bind other than loopback (`127.0.0.1`, `::1`, `localhost`), px0
requires an access token on every request. By default it generates a random
one at startup and puts it in the printed URLs as `?token=…`. It also prints a
`token` line, so you can add `?token=…` to whatever address reaches px0 (a
Docker port mapping, a VPN name). The browser swaps the query parameter for an
HttpOnly cookie on first load and then drops it from the address bar. Scripts
can send `Authorization: Bearer <token>` instead.

| Flag | Env | Purpose |
| :--- | :--- | :--- |
| `-token T` | `PX0_TOKEN` | Use a known token (at least 16 printable ASCII characters, without spaces, `"`, `,`, `;` or `\`) instead of a random one. It is required on every bind, loopback included. Prefer the env var: flags are visible in `ps`. |
| `-no-auth` | | Turn the token off on a non-loopback bind. Use it only behind a gateway that authenticates users itself. |
| `-allowed-hosts H,…` | `PX0_ALLOWED_HOSTS` | Extra `Host` names to accept besides `localhost` and IP addresses, e.g. the public name of a reverse proxy or tunnel. `*.example.com` matches subdomains. `*` accepts any `Host` and turns DNS-rebinding protection off. |

Without a token, px0 rejects any request whose `Host` is not `localhost`, an IP
address or a name listed in `-allowed-hosts`. This blocks DNS rebinding. A
reverse proxy or Cloudflare Tunnel that keeps the public hostname therefore
needs either `-allowed-hosts px0.example.com` or a token:

```bash
# Cloudflare Tunnel / Caddy in front of a loopback px0
px0 -allowed-hosts px0.example.com ~/workspace

# Docker: pick the token so the URL is known up front
docker run -e PX0_TOKEN=$(openssl rand -hex 16) -p 7777:7777 -v "$PWD":/workspace px0
# then open http://localhost:7777/?token=<that token>
```

Traffic is plain HTTP, so on an untrusted network put px0 behind Tailscale,
WireGuard or a TLS proxy. Path traversal protection applies in every mode.

## Development

```bash
git clone https://github.com/px0-ai/px0.git
cd px0

# Run tests
make test

# Live frontend development (serves web/ assets directly from disk)
go run . -dev .

# Build binary
make build
```

## Benchmarks

```bash
# Clone the benchmark corpus (~3 GB: Linux, Kubernetes, TypeScript, etc.)
./benchmark.sh --clone

# Run benchmarks across the corpus
./benchmark.sh

# Compare px0 directly against VS Code on the current workspace
./benchmark.sh --vscode .

# Profile memory lifecycle (index, search, idle memory release)
./benchmark.sh --memory bench-repos/linux
```

> **Architecture & Memory Accounting**: px0 separates the lightweight native Go daemon from the browser-rendered UI. The Go server consumes ~20–30 MB resident RAM (RSS). The active browser tab allocates ~80–150 MB for DOM nodes, V8 JS runtime, and GPU compositing. Combined, the total local memory footprint is ~100–180 MB (~85–90% lighter than Electron IDEs like VS Code at ~1,440 MB, which bundle dedicated Chromium and Node runtimes). In remote or container environments (`px0 -host 0.0.0.0`), the remote host pays strictly the ~20–30 MB server cost. See [BENCHMARKS.md](BENCHMARKS.md) for full methodology and breakdowns.

## Documentation

- [Docs](https://px0.ai/docs)
- [Benchmarks](https://px0.ai/#bench)
- [Blog](https://px0.ai/blog)
- [Changelog](https://px0.ai/changelog)
- [Partners](https://px0.ai/design-partners)

## Design Partners

When AI coding agents generate large diffs across repositories every day, code authoring is no longer the bottleneck. Verification and review are.

We are looking for engineering teams (10+ engineers or teams running active agent workflows) as design partners. Partners receive direct Slack Connect access to the core team, rapid turnaround on custom harness integrations, and direct input on the roadmap.

Learn more on the [Design Partners page](https://px0.ai/design-partners).

## License

[MIT License](LICENSE) © Arpit Bhayani
