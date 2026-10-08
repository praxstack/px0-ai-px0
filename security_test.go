package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func reqHost(s *Server, method, path, host string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, nil)
	req.Host = host
	rec := httptest.NewRecorder()
	s.ServeHTTP(rec, req)
	return rec
}

func TestHostGuardRejectsForeignHost(t *testing.T) {
	s, _ := newTestServer(t)
	s.Secure("127.0.0.1")
	for _, p := range []string{"/api/tree", "/api/file?path=main.go", "/api/settings", "/api/git/log", "/"} {
		if rec := reqHost(s, http.MethodGet, p, "rebind.attacker.example:7777"); rec.Code != http.StatusForbidden {
			t.Errorf("GET %s with foreign Host: got %d, want 403", p, rec.Code)
		}
	}
	for _, h := range []string{"127.0.0.1:7777", "localhost:7777", "[::1]:7777", "192.168.1.5:7777", "app.localhost"} {
		if rec := reqHost(s, http.MethodGet, "/api/meta", h); rec.Code != http.StatusOK {
			t.Errorf("Host %q: got %d, want 200", h, rec.Code)
		}
	}
}

func TestSettingsMasksGitHubToken(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", dir)
	const secret = "ghp_supersecretvalue123"
	p := filepath.Join(dir, "px0", "settings.json")
	os.MkdirAll(filepath.Dir(p), 0o755)
	os.WriteFile(p, []byte(`{"github.token":"`+secret+`","editor.tabSize":2}`), 0o600)

	s, _ := newTestServer(t)
	rec := reqHost(s, http.MethodGet, "/api/settings", "127.0.0.1:7777")
	if rec.Code != 200 || strings.Contains(rec.Body.String(), secret) {
		t.Fatalf("GET /api/settings leaked the token (code %d): %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), maskedSecret) {
		t.Fatalf("expected mask in response: %s", rec.Body.String())
	}

	// Echoing the mask back (as the UI does) must not overwrite the stored token.
	if err := updateSettingsMap(map[string]any{"github.token": maskedSecret, "editor.tabSize": 4}); err != nil {
		t.Fatal(err)
	}
	if err := saveRawSettingsJSON([]byte(`{"github.token":"` + maskedSecret + `","editor.tabSize":8}`)); err != nil {
		t.Fatal(err)
	}
	if got := readSettingsRawMap()["github.token"]; got != secret {
		t.Fatalf("stored token clobbered: %v", got)
	}
}

func TestNonLoopbackBindRequiresToken(t *testing.T) {
	s, _ := newTestServer(t)
	tok := s.Secure("0.0.0.0")
	if tok == "" {
		t.Fatal("non-loopback bind must generate an access token")
	}
	for _, p := range []string{"/api/tree", "/api/settings", "/"} {
		if rec := reqHost(s, http.MethodGet, p, "192.168.1.5:7777"); rec.Code != http.StatusUnauthorized {
			t.Errorf("GET %s without token: got %d, want 401", p, rec.Code)
		}
	}
	if rec := reqHost(s, http.MethodPost, "/api/agent/edit", "192.168.1.5:7777"); rec.Code != http.StatusUnauthorized {
		t.Errorf("POST without token: got %d, want 401", rec.Code)
	}
	if rec := reqHost(s, http.MethodGet, "/api/meta?token=wrong", "192.168.1.5:7777"); rec.Code != http.StatusUnauthorized {
		t.Errorf("wrong token: got %d, want 401", rec.Code)
	}
	rec := reqHost(s, http.MethodGet, "/api/meta?token="+tok, "192.168.1.5:7777")
	if rec.Code != http.StatusOK {
		t.Fatalf("valid token: got %d", rec.Code)
	}
	cookies := rec.Result().Cookies()
	if len(cookies) != 1 || cookies[0].Name != tokenCookie || !cookies[0].HttpOnly {
		t.Fatalf("expected HttpOnly token cookie, got %v", cookies)
	}
	req := httptest.NewRequest(http.MethodGet, "/api/tree", nil)
	req.AddCookie(cookies[0])
	rec2 := httptest.NewRecorder()
	s.ServeHTTP(rec2, req)
	if rec2.Code != http.StatusOK {
		t.Errorf("cookie auth: got %d", rec2.Code)
	}
	req = httptest.NewRequest(http.MethodGet, "/api/tree", nil)
	req.Header.Set("Authorization", "Bearer "+tok)
	rec3 := httptest.NewRecorder()
	s.ServeHTTP(rec3, req)
	if rec3.Code != http.StatusOK {
		t.Errorf("bearer auth: got %d", rec3.Code)
	}
}

func TestLoopbackBindNeedsNoToken(t *testing.T) {
	for _, h := range []string{"127.0.0.1", "localhost", "::1", "[::1]"} {
		s, _ := newTestServer(t)
		if tok := s.Secure(h); tok != "" {
			t.Errorf("bind %q: unexpected token", h)
		}
	}
	for _, h := range []string{"0.0.0.0", "", "::", "192.168.1.5"} {
		s, _ := newTestServer(t)
		if tok := s.Secure(h); tok == "" {
			t.Errorf("bind %q: expected token", h)
		}
	}
	if got := withToken("http://1.2.3.4:7/?path=a", "abc"); !strings.Contains(got, "token=abc") || !strings.Contains(got, "path=a") {
		t.Errorf("withToken = %q", got)
	}
}
