package main

import (
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"html"
	"net"
	"net/http"
	"net/url"
	"strings"
)

// minTokenLen is the shortest operator-supplied access token px0 accepts.
const minTokenLen = 16

// AccessConfig says how a server that is about to be exposed authenticates
// requests. It is built from -host, -port, -token / PX0_TOKEN, -no-auth and
// -allowed-hosts / PX0_ALLOWED_HOSTS.
type AccessConfig struct {
	BindHost string // address px0 listens on
	Port     int    // listen port; part of the cookie name so instances on one host do not collide (not an isolation boundary)

	// Token is an operator-supplied access token. When set it is required on
	// every request, whatever the bind. When empty, a non-loopback bind
	// generates a random one unless NoAuth is set.
	Token string

	// NoAuth turns the access token off on a non-loopback bind. It is for
	// deployments behind a gateway that authenticates users itself.
	NoAuth bool

	// AllowedHosts are extra Host names (port ignored) the DNS-rebinding guard
	// accepts besides localhost names and IP literals: the public name of a
	// Host-preserving reverse proxy or tunnel. "*.example.com" matches any
	// subdomain of example.com; "*" accepts every Host.
	AllowedHosts []string
}

// isLoopbackBind reports whether binding to host exposes px0 only to this machine.
func isLoopbackBind(host string) bool {
	h := strings.Trim(host, "[]")
	if h == "localhost" {
		return true
	}
	ip := net.ParseIP(h)
	return ip != nil && ip.IsLoopback()
}

// cookieSafeToken reports whether tok survives a round trip through the
// access-token cookie unchanged. http.SetCookie drops bytes that are not
// valid in a cookie value and quotes values with a space or comma, so such a
// token would authenticate the first ?token= request and then fail as a cookie.
func cookieSafeToken(tok string) bool {
	for i := 0; i < len(tok); i++ {
		switch b := tok[i]; {
		case b <= ' ' || b >= 0x7f, b == '"', b == ',', b == ';', b == '\\':
			return false
		}
	}
	return true
}

func newAccessToken() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		panic("px0: no secure random source: " + err.Error())
	}
	return hex.EncodeToString(b)
}

// withToken appends the access token to a viewer URL (no-op when token is empty).
func withToken(rawURL, token string) string {
	if token == "" {
		return rawURL
	}
	u, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}
	q := u.Query()
	q.Set("token", token)
	u.RawQuery = q.Encode()
	return u.String()
}

// parseAllowedHosts splits a comma-separated -allowed-hosts value.
func parseAllowedHosts(v string) []string {
	var out []string
	for _, h := range strings.Split(v, ",") {
		if h = normalizeHost(h); h != "" {
			out = append(out, h)
		}
	}
	return out
}

// normalizeHost strips the port, IPv6 brackets and a trailing dot, and lowercases.
func normalizeHost(hostHeader string) string {
	host := strings.TrimSpace(hostHeader)
	if h, _, err := net.SplitHostPort(host); err == nil {
		host = h
	}
	host = strings.Trim(host, "[]")
	return strings.ToLower(strings.TrimSuffix(host, "."))
}

// hostAllowed reports whether a request Host header names this machine rather
// than an attacker-controlled DNS name. A DNS-rebinding page reaches px0 with
// its own domain as Host, so only localhost names and literal IP addresses pass.
func hostAllowed(hostHeader string) bool {
	host := normalizeHost(hostHeader)
	if host == "localhost" || strings.HasSuffix(host, ".localhost") {
		return true
	}
	return net.ParseIP(host) != nil
}

// extraHostAllowed reports whether the Host is one the operator listed in
// -allowed-hosts.
func (s *Server) extraHostAllowed(hostHeader string) bool {
	host := normalizeHost(hostHeader)
	if host == "" {
		return false
	}
	for _, a := range s.allowedHosts {
		switch {
		case a == "*":
			return true
		case strings.HasPrefix(a, "*."):
			if strings.HasSuffix(host, a[1:]) {
				return true
			}
		case a == host:
			return true
		}
	}
	return false
}

// Secure turns on request guarding for a server that is about to be exposed.
// It must be called before the server starts serving. It returns the access
// token every request must present ("" when none is required) so the caller
// can print it in the URLs it hands to the user.
func (s *Server) Secure(cfg AccessConfig) (string, error) {
	if cfg.NoAuth && cfg.Token != "" {
		return "", errors.New("-no-auth and -token (or PX0_TOKEN) cannot be used together")
	}
	if cfg.Token != "" && len(cfg.Token) < minTokenLen {
		return "", fmt.Errorf("access token must be at least %d characters", minTokenLen)
	}
	if cfg.Token != "" && !cookieSafeToken(cfg.Token) {
		return "", errors.New(`access token may only contain printable ASCII without spaces, '"', ',', ';' or '\'`)
	}
	s.hostGuard = true
	s.allowedHosts = cfg.AllowedHosts
	s.cookieName = fmt.Sprintf("px0_token_%d", cfg.Port)
	switch {
	case cfg.Token != "":
		s.accessToken = cfg.Token
	case !cfg.NoAuth && !isLoopbackBind(cfg.BindHost):
		s.accessToken = newAccessToken()
	}
	return s.accessToken, nil
}

func (s *Server) tokenCookieName() string {
	if s.cookieName != "" {
		return s.cookieName
	}
	return "px0_token"
}

// tokenCookie is the access-token cookie set after a ?token= request. Its Path
// is the configured base path: browsers do not isolate cookies by port, so the
// per-port name only avoids collisions between instances; the Path keeps the
// cookie off requests to other apps' paths (the trailing slash keeps /rev-1/
// from matching /rev-10/). Path is not a security boundary: any page on the
// same origin can request px0's paths and the browser attaches this cookie, so
// instances that must be isolated from other apps need their own hostname.
func (s *Server) tokenCookie() *http.Cookie {
	return &http.Cookie{
		Name:     s.tokenCookieName(),
		Value:    s.accessToken,
		Path:     s.BasePath(),
		HttpOnly: true,
		SameSite: http.SameSiteStrictMode,
	}
}

func tokenEqual(a, b string) bool {
	return subtle.ConstantTimeCompare([]byte(a), []byte(b)) == 1
}

// tokenOK reports whether the request carries the access token, and whether it
// came in the query string (so the caller can set the cookie).
func (s *Server) tokenOK(r *http.Request) (ok, viaQuery bool) {
	if c, err := r.Cookie(s.tokenCookieName()); err == nil && tokenEqual(c.Value, s.accessToken) {
		return true, false
	}
	if h := r.Header.Get("Authorization"); strings.HasPrefix(h, "Bearer ") && tokenEqual(strings.TrimPrefix(h, "Bearer "), s.accessToken) {
		return true, false
	}
	if tokenEqual(r.URL.Query().Get("token"), s.accessToken) {
		return true, true
	}
	return false, false
}

type trustedHostKey struct{}

// hostTrusted reports whether guard already vouched for this request's Host
// (it presented the access token, or its Host is in -allowed-hosts), so
// localPost need not insist on a localhost name or IP literal.
func hostTrusted(r *http.Request) bool {
	v, _ := r.Context().Value(trustedHostKey{}).(bool)
	return v
}

func withTrustedHost(r *http.Request) *http.Request {
	return r.WithContext(context.WithValue(r.Context(), trustedHostKey{}, true))
}

// locationWithoutToken returns a relative reference to the same resource with
// the token query parameter removed. It is relative ("./name?query") so it
// stays correct behind a proxy that rewrites the path prefix.
func locationWithoutToken(u *url.URL) string {
	p := u.EscapedPath()
	loc := "./" + p[strings.LastIndexByte(p, '/')+1:]
	q := u.Query()
	q.Del("token")
	if enc := q.Encode(); enc != "" {
		loc += "?" + enc
	}
	return loc
}

// writeTokenLanding answers a browser navigation that carried ?token= (the
// caller has already set the cookie) with a page that swaps the address for
// loc, the token-free URL. It is not a 302 on purpose: a redirect is part of
// the navigation that brought the token, and when that came from another site
// browsers may leave the new SameSite=Strict cookie off the redirected request.
// A navigation started by this same-origin page is same-site, so the cookie is
// sent and Strict keeps its CSRF protection. location.replace also removes the
// token URL from history. The body never contains the token.
func writeTokenLanding(w http.ResponseWriter, loc string) {
	nonce := newAccessToken()
	js, _ := json.Marshal(loc) // escapes <, > and &, so it cannot close the script
	h := w.Header()
	h.Set("Content-Type", "text/html; charset=utf-8")
	h.Set("Cache-Control", "no-store")
	h.Set("Referrer-Policy", "no-referrer")
	h.Set("Content-Security-Policy", "default-src 'none'; script-src 'nonce-"+nonce+"'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `<!doctype html><meta charset="utf-8"><title>px0</title><script nonce="%s">location.replace(%s)</script><noscript><a href="%s">Continue to px0</a></noscript>`+"\n",
		nonce, js, html.EscapeString(loc))
}

// baseRedirect returns the base path for a request to the bare base path
// ("/rev") or, when a base path is set, the root ("/"): the paths the mux only
// redirects to the base path. guard answers them before the token check because
// the cookie is scoped to the base path and the browser does not send it there.
// The query is kept so a ?token= still reaches the base path, where the token
// landing page sets the cookie and strips it.
func (s *Server) baseRedirect(u *url.URL) (string, bool) {
	bp := s.BasePath()
	if bp == "/" || (u.Path != "/" && u.Path != strings.TrimSuffix(bp, "/")) {
		return "", false
	}
	if u.RawQuery != "" {
		return bp + "?" + u.RawQuery, true
	}
	return bp, true
}

// redactTokenURI hides a ?token= value in a request URI before it is logged.
func redactTokenURI(uri string) string {
	u, err := url.ParseRequestURI(uri)
	if err != nil || !u.Query().Has("token") {
		return uri
	}
	q := u.Query()
	q.Set("token", "REDACTED")
	u.RawQuery = q.Encode()
	return u.RequestURI()
}

// guard applies the access policy to every route, GET included. It returns
// false after writing the response when the request must not proceed;
// otherwise it returns the request to continue with.
//
// With an access token the token is the credential: a rebinding page has no
// token, so the Host allowlist is not needed and would only lock out
// legitimate hostnames. Otherwise the Host must be a localhost name, an IP
// literal, or a name listed in -allowed-hosts.
func (s *Server) guard(w http.ResponseWriter, r *http.Request) (*http.Request, bool) {
	if s.accessToken != "" {
		if loc, ok := s.baseRedirect(r.URL); ok {
			http.Redirect(w, r, loc, http.StatusFound)
			return r, false
		}
		ok, viaQuery := s.tokenOK(r)
		if !ok {
			http.Error(w, "unauthorized: open the URL printed by px0 (it carries an access token)", http.StatusUnauthorized)
			return r, false
		}
		if viaQuery {
			http.SetCookie(w, s.tokenCookie())
			// A browser navigation now has the cookie: drop the token from the
			// address bar so it does not linger in history or copied links.
			if r.Method == http.MethodGet && r.Header.Get("Sec-Fetch-Mode") == "navigate" {
				writeTokenLanding(w, locationWithoutToken(r.URL))
				return r, false
			}
		}
		return withTrustedHost(r), true
	}
	if !s.hostGuard || hostAllowed(r.Host) {
		return r, true
	}
	if s.extraHostAllowed(r.Host) {
		return withTrustedHost(r), true
	}
	http.Error(w, "forbidden: open px0 by localhost or IP address, or list this host in -allowed-hosts", http.StatusForbidden)
	return r, false
}
