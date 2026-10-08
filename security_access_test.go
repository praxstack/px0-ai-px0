package main

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"regexp"
	"strings"
	"testing"
)

const testToken = "0123456789abcdef-test-token"

func doReq(s *Server, method, path, host string, hdr map[string]string, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	req.Host = host
	for k, v := range hdr {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	s.ServeHTTP(rec, req)
	return rec
}

func TestSuppliedTokenRequiredOnAnyBind(t *testing.T) {
	s, _ := newTestServer(t)
	tok := mustSecure(t, s, AccessConfig{BindHost: "127.0.0.1", Port: 7777, Token: testToken})
	if tok != testToken {
		t.Fatalf("Secure returned %q, want the supplied token", tok)
	}
	// A tunnel on a loopback bind sends its public name as Host; the token,
	// not the Host allowlist, admits it.
	if rec := doReq(s, "GET", "/api/meta", "px0.tunnel.example", nil, ""); rec.Code != http.StatusUnauthorized {
		t.Errorf("no token: got %d, want 401", rec.Code)
	}
	if rec := doReq(s, "GET", "/api/meta", "px0.tunnel.example", map[string]string{"Authorization": "Bearer " + testToken}, ""); rec.Code != http.StatusOK {
		t.Errorf("bearer over tunnel hostname: got %d, want 200", rec.Code)
	}
}

func TestSecureRejectsBadAccessConfig(t *testing.T) {
	s, _ := newTestServer(t)
	if _, err := s.Secure(AccessConfig{BindHost: "0.0.0.0", NoAuth: true, Token: testToken}); err == nil {
		t.Error("-no-auth with -token: want error")
	}
	if _, err := s.Secure(AccessConfig{BindHost: "0.0.0.0", Token: "short"}); err == nil {
		t.Error("short token: want error")
	}
}

func TestNoAuthOptOutKeepsHostGuard(t *testing.T) {
	s, _ := newTestServer(t)
	if tok := mustSecure(t, s, AccessConfig{BindHost: "0.0.0.0", NoAuth: true}); tok != "" {
		t.Fatalf("-no-auth generated a token")
	}
	if rec := doReq(s, "GET", "/api/meta", "10.0.0.5:7777", nil, ""); rec.Code != http.StatusOK {
		t.Errorf("no-auth over IP: got %d, want 200", rec.Code)
	}
	if rec := doReq(s, "GET", "/api/meta", "gateway.example", nil, ""); rec.Code != http.StatusForbidden {
		t.Errorf("no-auth, unlisted Host: got %d, want 403", rec.Code)
	}

	s2, _ := newTestServer(t)
	mustSecure(t, s2, AccessConfig{BindHost: "0.0.0.0", NoAuth: true, AllowedHosts: parseAllowedHosts("gateway.example")})
	if rec := doReq(s2, "GET", "/api/meta", "gateway.example", nil, ""); rec.Code != http.StatusOK {
		t.Errorf("no-auth, listed Host: got %d, want 200", rec.Code)
	}
}

func TestAllowedHostsForReverseProxy(t *testing.T) {
	s, _ := newTestServer(t)
	mustSecure(t, s, AccessConfig{BindHost: "127.0.0.1", Port: 7777, AllowedHosts: parseAllowedHosts(" PX0.Example.com , *.tunnel.dev")})
	for host, want := range map[string]int{
		"px0.example.com":      200,
		"px0.example.com:443":  200,
		"px0.example.com.":     200,
		"a.tunnel.dev":         200,
		"tunnel.dev":           403,
		"evil.example":         403,
		"px0.example.com.evil": 403,
		"127.0.0.1:7777":       200,
	} {
		if rec := doReq(s, "GET", "/api/meta", host, nil, ""); rec.Code != want {
			t.Errorf("Host %q: got %d, want %d", host, rec.Code, want)
		}
	}
	// POSTs through a listed Host pass localPost, but the Origin must still match.
	ok := doReq(s, "POST", "/api/session", "px0.example.com", map[string]string{"Origin": "https://px0.example.com"}, "{}")
	if ok.Code != http.StatusOK {
		t.Errorf("POST via allowed host: got %d (%s), want 200", ok.Code, ok.Body.String())
	}
	bad := doReq(s, "POST", "/api/session", "px0.example.com", map[string]string{"Origin": "https://evil.example"}, "{}")
	if bad.Code != http.StatusForbidden {
		t.Errorf("POST via allowed host, foreign Origin: got %d, want 403", bad.Code)
	}

	any, _ := newTestServer(t)
	mustSecure(t, any, AccessConfig{BindHost: "127.0.0.1", AllowedHosts: parseAllowedHosts("*")})
	if rec := doReq(any, "GET", "/api/meta", "whatever.example", nil, ""); rec.Code != http.StatusOK {
		t.Errorf("-allowed-hosts '*': got %d, want 200", rec.Code)
	}
}

// With a token, a POST over a hostname (mac.local) is admitted by localPost,
// as long as the Origin matches the Host.
func TestTokenPostOverHostname(t *testing.T) {
	s, _ := newTestServer(t)
	tok := mustSecure(t, s, AccessConfig{BindHost: "0.0.0.0", Port: 7777})
	auth := map[string]string{"Authorization": "Bearer " + tok, "Origin": "http://mac.local:7777"}
	if rec := doReq(s, "POST", "/api/session", "mac.local:7777", auth, "{}"); rec.Code != http.StatusOK {
		t.Errorf("token POST over hostname: got %d (%s), want 200", rec.Code, rec.Body.String())
	}
	auth["Origin"] = "http://evil.example"
	if rec := doReq(s, "POST", "/api/session", "mac.local:7777", auth, "{}"); rec.Code != http.StatusForbidden {
		t.Errorf("token POST with foreign Origin: got %d, want 403", rec.Code)
	}
}

func TestTokenCookieNameIsPerPort(t *testing.T) {
	a, _ := newTestServer(t)
	b, _ := newTestServer(t)
	ta := mustSecure(t, a, AccessConfig{BindHost: "0.0.0.0", Port: 7777})
	mustSecure(t, b, AccessConfig{BindHost: "0.0.0.0", Port: 7778})
	ca := doReq(a, "GET", "/api/meta?token="+ta, "10.0.0.5:7777", nil, "").Result().Cookies()
	if len(ca) != 1 || ca[0].Name != "px0_token_7777" {
		t.Fatalf("instance A cookie: %v", ca)
	}
	if a.tokenCookieName() == b.tokenCookieName() {
		t.Fatalf("instances on different ports share cookie name %q", a.tokenCookieName())
	}
}

// Cookies are not isolated by port, so the cookie name alone does not keep the
// token away from other services on the same hostname. The cookie Path must be
// the configured base path, so apps beside a -base-path deployment never get it
// and two deployments on one host and port do not overwrite each other.
func TestTokenCookieScopedToBasePath(t *testing.T) {
	cookieFor := func(s *Server, path, tok string) *http.Cookie {
		t.Helper()
		c := doReq(s, "GET", path+"?token="+tok, "10.0.0.5:7777", nil, "").Result().Cookies()
		if len(c) != 1 {
			t.Fatalf("GET %s: want one cookie, got %v", path, c)
		}
		return c[0]
	}

	root, _ := newTestServer(t)
	tok := mustSecure(t, root, AccessConfig{BindHost: "0.0.0.0", Port: 7777})
	if c := cookieFor(root, "/api/meta", tok); c.Path != "/" || !c.HttpOnly || c.SameSite != http.SameSiteStrictMode {
		t.Errorf("root deployment cookie = %+v, want Path=/ HttpOnly SameSite=Strict", c)
	}

	a, _ := newTestServer(t)
	a.SetBasePath("/rev-1")
	ta := mustSecure(t, a, AccessConfig{BindHost: "0.0.0.0", Port: 7777})
	ca := cookieFor(a, "/rev-1/api/meta", ta)
	if ca.Path != "/rev-1/" || !ca.HttpOnly || ca.SameSite != http.SameSiteStrictMode {
		t.Errorf("base-path cookie = %+v, want Path=/rev-1/ HttpOnly SameSite=Strict", ca)
	}

	b, _ := newTestServer(t)
	b.SetBasePath("/rev-10/")
	tb := mustSecure(t, b, AccessConfig{BindHost: "0.0.0.0", Port: 7777})
	cb := cookieFor(b, "/rev-10/api/meta", tb)
	if cb.Path == ca.Path {
		t.Errorf("deployments at /rev-1/ and /rev-10/ share cookie path %q", ca.Path)
	}
	if strings.HasPrefix("/rev-10/", ca.Path) {
		t.Errorf("cookie path %q of /rev-1/ also matches /rev-10/", ca.Path)
	}
}

func TestTokenStrippedFromNavigationURL(t *testing.T) {
	s, _ := newTestServer(t)
	tok := mustSecure(t, s, AccessConfig{BindHost: "0.0.0.0", Port: 7777})
	rec := doReq(s, "GET", "/?path=main.go&token="+tok, "10.0.0.5:7777", map[string]string{"Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "cross-site"}, "")
	// Not a 302: a redirect belongs to the incoming (possibly cross-site)
	// navigation, which may not carry the new SameSite=Strict cookie. A
	// same-origin page that replaces the URL itself starts a same-site one.
	if rec.Code != http.StatusOK {
		t.Fatalf("navigation with token: got %d, want 200 landing page", rec.Code)
	}
	if loc := rec.Header().Get("Location"); loc != "" {
		t.Errorf("landing page must not redirect, Location = %q", loc)
	}
	h := rec.Header()
	if ct := h.Get("Content-Type"); !strings.HasPrefix(ct, "text/html") {
		t.Errorf("Content-Type = %q, want text/html", ct)
	}
	if h.Get("Cache-Control") != "no-store" || h.Get("Referrer-Policy") != "no-referrer" {
		t.Errorf("landing page headers: Cache-Control=%q Referrer-Policy=%q", h.Get("Cache-Control"), h.Get("Referrer-Policy"))
	}
	body := rec.Body.String()
	if strings.Contains(body, tok) {
		t.Errorf("landing page body contains the token: %s", body)
	}
	if !strings.Contains(body, `location.replace("./?path=main.go")`) {
		t.Errorf("landing page does not replace the URL with the token-free one: %s", body)
	}
	if !strings.Contains(body, `href="./?path=main.go"`) {
		t.Errorf("landing page has no no-script fallback link: %s", body)
	}
	csp := h.Get("Content-Security-Policy")
	m := regexp.MustCompile(`script-src 'nonce-([A-Za-z0-9+/=_-]{16,})'`).FindStringSubmatch(csp)
	if m == nil || strings.Contains(csp, "unsafe-inline") || !strings.Contains(csp, "default-src 'none'") {
		t.Fatalf("landing page CSP = %q, want default-src 'none' and a script nonce", csp)
	}
	if !strings.Contains(body, `<script nonce="`+m[1]+`">`) {
		t.Errorf("script nonce does not match the CSP nonce %q: %s", m[1], body)
	}
	if again := doReq(s, "GET", "/?token="+tok, "10.0.0.5:7777", map[string]string{"Sec-Fetch-Mode": "navigate"}, ""); strings.Contains(again.Header().Get("Content-Security-Policy"), m[1]) {
		t.Error("landing page nonce is reused across responses")
	}
	for in, want := range map[string]string{
		"/rev-1/?token=x":         "./",
		"/rev-1/a.go?token=x&l=3": "./a.go?l=3",
		"/rev-1/a%20b.go?token=x": "./a%20b.go",
	} {
		u, _ := url.Parse(in)
		if got := locationWithoutToken(u); got != want {
			t.Errorf("locationWithoutToken(%q) = %q, want %q", in, got, want)
		}
	}
	if c := rec.Result().Cookies(); len(c) != 1 || c[0].Value != tok || c[0].SameSite != http.SameSiteStrictMode || !c[0].HttpOnly {
		t.Errorf("landing page must set the HttpOnly SameSite=Strict token cookie, got %v", c)
	}
	if again := doReq(s, "GET", "/a.go?token="+tok+"&l=3", "10.0.0.5:7777", map[string]string{"Sec-Fetch-Mode": "navigate"}, ""); !strings.Contains(again.Body.String(), `location.replace("./a.go?l=3")`) {
		t.Errorf("landing page for a file URL: %s", again.Body.String())
	}
	// Non-navigation requests (scripts, curl) are served directly.
	if rec := doReq(s, "GET", "/api/meta?token="+tok, "10.0.0.5:7777", nil, ""); rec.Code != http.StatusOK {
		t.Errorf("API request with token: got %d, want 200", rec.Code)
	}
}

func TestRedactTokenURI(t *testing.T) {
	got := redactTokenURI("/api/file?path=a.go&token=" + testToken)
	if strings.Contains(got, testToken) || !strings.Contains(got, "path=a.go") {
		t.Errorf("redactTokenURI = %q", got)
	}
	if got := redactTokenURI("/api/tree"); got != "/api/tree" {
		t.Errorf("redactTokenURI changed a URI without token: %q", got)
	}
}

func TestSettingsQueryTokenNotPersisted(t *testing.T) {
	isolateSettings(t)
	s, _ := newTestServer(t)
	tok := mustSecure(t, s, AccessConfig{BindHost: "0.0.0.0", Port: 7777})
	rec := doReq(s, "POST", "/api/settings?editor.tabSize=3&token="+tok, "10.0.0.5:7777", map[string]string{"Origin": "http://10.0.0.5:7777"}, "")
	if rec.Code != http.StatusOK {
		t.Fatalf("POST /api/settings: got %d (%s)", rec.Code, rec.Body.String())
	}
	if _, ok := readSettingsRawMap()["token"]; ok {
		t.Fatal("access token was persisted into settings.json")
	}
}

// guard admits localhost aliases (app.localhost, "localhost."), so localPost
// must too; a non-local name is still refused without a token or allow-list.
func TestLocalhostAliasPost(t *testing.T) {
	s, _ := newTestServer(t)
	mustSecure(t, s, AccessConfig{BindHost: "127.0.0.1", Port: 7777})
	for host, want := range map[string]int{
		"app.localhost:7777": http.StatusOK,
		"localhost.:7777":    http.StatusOK,
		"LOCALHOST:7777":     http.StatusOK,
		"[::1]:7777":         http.StatusOK,
		"evil.example:7777":  http.StatusForbidden,
	} {
		rec := doReq(s, "POST", "/api/session", host, map[string]string{"Origin": "http://" + host}, "{}")
		if rec.Code != want {
			t.Errorf("POST via Host %q: got %d (%s), want %d", host, rec.Code, rec.Body.String(), want)
		}
	}
	// Without Secure (embedders) guard is off, so localPost alone refuses the
	// rebinding name.
	plain, _ := newTestServer(t)
	if rec := doReq(plain, "POST", "/api/session", "evil.example", map[string]string{"Origin": "http://evil.example"}, "{}"); rec.Code != http.StatusForbidden {
		t.Errorf("unguarded POST via foreign Host: got %d, want 403", rec.Code)
	}
}

// A supplied token must survive http.SetCookie unchanged, or the browser is
// admitted by ?token= once and then gets 401 with the (sanitized) cookie.
func TestSuppliedTokenIsCookieSafe(t *testing.T) {
	for _, bad := range []string{"0123456789abcdef;x", "0123456789abcdef x", "0123456789abcdef,x", `0123456789abcdef"x`, `0123456789abcdef\x`, "0123456789abcdefé"} {
		s, _ := newTestServer(t)
		if _, err := s.Secure(AccessConfig{BindHost: "0.0.0.0", Port: 7777, Token: bad}); err == nil {
			t.Errorf("token %q: want error", bad)
		}
	}
	// Every other printable ASCII byte is kept by SetCookie and accepted back.
	const good = "Az09!#$%&'()*+-./:<=>?@[]^_`{|}~"
	s, _ := newTestServer(t)
	mustSecure(t, s, AccessConfig{BindHost: "0.0.0.0", Port: 7777, Token: good})
	cookies := doReq(s, "GET", "/api/meta?token="+url.QueryEscape(good), "10.0.0.5:7777", nil, "").Result().Cookies()
	if len(cookies) != 1 || cookies[0].Value != good {
		t.Fatalf("cookie after ?token= = %v, want value %q", cookies, good)
	}
	req := httptest.NewRequest("GET", "/api/meta", nil)
	req.Host = "10.0.0.5:7777"
	req.AddCookie(cookies[0])
	rec := httptest.NewRecorder()
	s.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("request with the cookie: got %d, want 200", rec.Code)
	}
}
