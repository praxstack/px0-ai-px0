# Remote Workspaces & Cloud Inspection

px0 is architected from the ground up as a remote-first code reading environment. It allows you to run a single binary on any remote server, cloud instance, Docker container, or CI runner and browse the codebase directly in your local desktop browser without SSH keys, port forwarding setups, or heavy remote extension daemons.

---

## Overview & Core Purpose

Modern software development frequently takes place across cloud instances (AWS EC2, GCP Compute Engine), remote containers, Kubernetes pods, and devboxes. Traditional remote development setups (such as VS Code Remote-SSH, remote X11 forwarding, or VNC) require multi-step authentication setups, background server daemon installations, high CPU overhead, and significant network bandwidth.

px0 simplifies remote code inspection into a single shell command. Because the entire application—Go backend, HTTP server, assets, and frontend—is compiled into one static ~3.5 MB binary with zero external dependencies, you can copy px0 to any remote Linux, macOS, or BSD machine and spin it up instantly. Connecting via Tailscale, WireGuard, private VPCs, or reverse proxies gives you a fluid, graphical code inspection console in your browser.

---

## Key Capabilities

- **Zero Remote Daemons**: No Node.js runtime, no npm packages, no Electron layers, and no background extension churn on the remote machine.
- **Single Port Operation**: px0 serves all assets, JSON APIs, and search queries over a single HTTP port (default `7777`).
- **Flexible Network Binding**:
  - Bind to localhost for private tunnels (`-host 127.0.0.1`).
  - Bind to all interfaces for Tailscale/VPN access (`-host 0.0.0.0`).
- **Headless Server Mode (`-no-open`)**: Starts the server silently on remote machines or in Docker containers without attempting to invoke a local web browser.
- **Built-in Security & Sandboxing**:
  - **Path Traversal Protection**: Enforces strict path sandboxing; requests attempting to escape the workspace root using `../` or symlink cycle attacks are immediately blocked.
  - **Access Token on Network Binds**: On any bind other than loopback, every request must carry an access token (`?token=` once, then an HttpOnly cookie, or `Authorization: Bearer`). px0 generates one at startup unless you pass `-token` / `PX0_TOKEN`, or opt out with `-no-auth` behind a gateway that authenticates users. See [Access control](#access-control).
  - **DNS Rebinding Defense**: Without a token, px0 rejects requests whose `Host` header is not `localhost`, an IP address or a name listed in `-allowed-hosts` / `PX0_ALLOWED_HOSTS`.
  - **Agent Security Restrictions**: Agent editing, language-server installs and other machine-changing POSTs must come from px0's own page (`Origin` must match `Host`). Over a hostname they are allowed only when the request carries the token or the hostname is in `-allowed-hosts`.
- **Direct Terminal Ergonomics**: Launch px0 targeting specific files or line numbers directly from the command line:
  - `px0` (opens current directory)
  - `px0 ~/projects/kernel` (opens specified repository)
  - `px0 main.go:42` (opens directly to line 42)
- **Built-in Self-Updater (`px0 --update`)**: Checks GitHub releases and seamlessly upgrades the single binary in place.

---

## Developer Workflows & Setup Patterns

### 1. Cloud Devbox via Tailscale or WireGuard
Run px0 on your cloud instance bound to all interfaces:
```bash
px0 -host 0.0.0.0 -port 7777 ~/work/repo
```
Open the `network` URL px0 prints (for example `http://100.x.y.z:7777/?token=…`, your machine's private Tailscale IP). The token is in the URL; px0 also prints it on its own `token` line. You get full code reading, fuzzy search, and diff inspection with zero SSH lag.

### 2. Ephemeral Docker Container Inspection
Inspect code inside a running container or test environment:
```bash
docker run -e PX0_TOKEN=$(openssl rand -hex 16) -p 7777:7777 -v $(pwd):/workspace px0:latest /workspace
```
The image binds `0.0.0.0`, so a token is required. The `network` URLs px0 prints are container addresses. Open `http://localhost:7777/?token=<PX0_TOKEN>` instead. Without `PX0_TOKEN`, read the generated token from `docker logs`.

### 3. CI/CD Runner Debugging
When a build or test suite fails on a remote CI runner, download px0, run it in the background, and inspect generated artifacts, failure logs, and git status directly in your browser.

### 4. Reverse Proxy & Subpath Hosting (`-base-path`)
When hosting px0 behind a reverse proxy (Nginx, Traefik, Caddy), an API gateway, or a multi-tenant cloud platform (such as PR review pods at `https://tenant.px0.ai/rev-123/` or internal portals at `https://corp.internal/tools/px0/`), px0 is served from a URL subpath rather than the root domain (`/`).

Run px0 with `-base-path`. Then choose how requests are authenticated:
```bash
# The gateway authenticates users and forwards Host tenant.px0.ai
px0 -base-path /rev-123/ -host 0.0.0.0 -no-auth -allowed-hosts tenant.px0.ai ~/workspace

# The gateway forwards requests as-is; users carry px0's token
PX0_TOKEN=... px0 -base-path /rev-123/ -host 0.0.0.0 ~/workspace
```
With `-no-auth`, px0 checks only the `Host` header. Make sure the pod port is reachable only through the gateway. If the gateway rewrites `Host` to an internal service name, list that name in `-allowed-hosts`. Machine-changing POSTs also need the browser's `Origin` to match the `Host` px0 sees.

**When to use `-base-path`:**
- **Hosted/Multi-Tenant Review Platforms**: When each PR review environment runs in an isolated container/pod routed through an edge gateway under a subpath (e.g. `/rev-<id>/`). Subpaths on one hostname share an origin, so they do not isolate environments from each other in the browser: put environments that belong to different users or tenants on different hostnames (see [Access control](#access-control)).
- **Path-Based Ingress Routing**: When routing traffic through an existing domain or Kubernetes Ingress where the root `/` is reserved for another service.
- **Corporate Dev Portals & Reverse Proxies**: When proxying multiple developer tools behind paths like `/tools/code-review/`.

**What `-base-path` does:**
- Prefixes all Go HTTP multiplexer endpoints (`/<base-path>/api/...`, `/<base-path>/static/...`).
- Dynamically injects `<base href="/<base-path>/">` into the served `index.html`, allowing the browser to resolve all relative asset requests, WebSocket/SSE connections, and API calls correctly.
- Automatically handles redirects: requests to `/<base-path>` without a trailing slash redirect to `/<base-path>/`, and root `/` redirects to the configured base path.

### Access control

| Bind | Default | Override |
| :--- | :--- | :--- |
| loopback (`127.0.0.1`, `::1`, `localhost`) | no token; `Host` must be `localhost`, an IP or an `-allowed-hosts` name | `-token` / `PX0_TOKEN` requires a token here too, e.g. for a tunnel |
| anything else (`0.0.0.0`, a LAN IP) | random token printed at startup | `-token` / `PX0_TOKEN` to choose it; `-no-auth` to turn it off behind an authenticating gateway |

The token is sent once as `?token=`. px0 then sets an HttpOnly, SameSite=Strict cookie named `px0_token_<port>`, scoped to the `-base-path` (`Path=/rev-123/`), and answers with a small same-origin page that replaces the address with the same URL without the token (not a 302, so the Strict cookie is sent even when the link was opened from another site). API clients can send `Authorization: Bearer <token>`. Browsers do not separate cookies by port: the port in the name only avoids collisions. The cookie `Path` keeps the token out of requests to other paths, but it is not an isolation boundary: every page on the same origin (scheme, hostname and port) can make requests to px0's paths with the user's cookie and read the answers. Give each px0 instance its own hostname (for example `rev-123.reviews.example.com`) whenever other apps or other px0 instances under that hostname are not trusted as much as px0 itself; under `-no-auth`, the gateway's own session cookie has the same limit. px0 serves plain HTTP: use a VPN or a TLS-terminating proxy on networks you do not trust.

---

## CLI Flag Reference

| Flag | Default | Description |
| :--- | :--- | :--- |
| `-base-path P` | `"/"` | Base URL path prefix to serve endpoints and assets from (e.g. `/rev-123/`). Also configurable in settings via `server.basePath`. |
| `-port N` | `7777` | Port to listen on (`0` picks an ephemeral free port) |
| `-host H` | `127.0.0.1` | Network address to bind |
| `-token T` | `$PX0_TOKEN` | Access token (16+ printable ASCII characters; no spaces, `"`, `,`, `;` or `\`) required on every request. A random one is generated on non-loopback binds when unset |
| `-no-auth` | `false` | No access token on a non-loopback bind. Only behind a gateway that authenticates users |
| `-allowed-hosts H,…` | `$PX0_ALLOWED_HOSTS` | Extra `Host` names to accept besides `localhost` and IPs (`*.example.com` for subdomains, `*` for any) |
| `-no-open` | `false` | Suppress automatic browser launch (ideal for servers) |
| `-no-lsp` | `false` | Disable Language Server discovery |
| `-no-git` | `false` | Disable Git status checks and diff viewing |
| `-agent H` | none | Pin active coding agent harness for session |
| `-no-agent` | `false` | Disable coding agent editing features entirely |
| `-verbose` | `false` | Log every HTTP request, searches, symbols, and agent prompts to terminal |
| `-quiet` | `false` | Suppress CLI narration on stdout (a generated access token is still printed) |
| `-update` | `false` | Check for updates and install latest release |
| `-version` | `false` | Print version and architecture and exit |

---

## Technical Architecture Deep Dive

For an architectural breakdown of HTTP routing, gzip connection pooling, symlink cycle immunity, and memory scavenging pipelines, see [System Architecture & Runtime Lifecycle Internals](../internals/architecture.md).
