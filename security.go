package main

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"net"
	"net/http"
	"net/url"
	"strings"
)

const tokenCookie = "px0_token"

// isLoopbackBind reports whether binding to host exposes px0 only to this machine.
func isLoopbackBind(host string) bool {
	h := strings.Trim(host, "[]")
	if h == "localhost" {
		return true
	}
	ip := net.ParseIP(h)
	return ip != nil && ip.IsLoopback()
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

// hostAllowed reports whether a request Host header names this machine rather
// than an attacker-controlled DNS name. A DNS-rebinding page reaches px0 with
// its own domain as Host, so only localhost names and literal IP addresses pass.
func hostAllowed(hostHeader string) bool {
	host := hostHeader
	if h, _, err := net.SplitHostPort(hostHeader); err == nil {
		host = h
	}
	host = strings.Trim(host, "[]")
	host = strings.ToLower(strings.TrimSuffix(host, "."))
	if host == "localhost" || strings.HasSuffix(host, ".localhost") {
		return true
	}
	return net.ParseIP(host) != nil
}

// Secure turns on request guarding for a server that is about to be exposed.
// It must be called before the server starts serving. bindHost is the address
// px0 listens on: a non-loopback bind makes every request present a freshly
// generated access token, which is returned so the caller can print it in the
// URLs it hands to the user. A loopback bind returns "".
func (s *Server) Secure(bindHost string) string {
	s.hostGuard = true
	if !isLoopbackBind(bindHost) {
		s.accessToken = newAccessToken()
	}
	return s.accessToken
}

func tokenEqual(a, b string) bool {
	return subtle.ConstantTimeCompare([]byte(a), []byte(b)) == 1
}

// tokenOK reports whether the request carries the access token, and whether it
// came in the query string (so the caller can set the cookie).
func (s *Server) tokenOK(r *http.Request) (ok, viaQuery bool) {
	if c, err := r.Cookie(tokenCookie); err == nil && tokenEqual(c.Value, s.accessToken) {
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

// guard applies the access policy to every route, GET included. It returns
// false after writing the rejection when the request must not proceed.
//
// With an access token (non-loopback bind) the token is the credential: a
// rebinding page has no token, so the Host allowlist is not needed and would
// only lock out legitimate hostnames. Otherwise the Host must be a localhost
// name or an IP literal.
func (s *Server) guard(w http.ResponseWriter, r *http.Request) bool {
	if s.accessToken != "" {
		ok, viaQuery := s.tokenOK(r)
		if !ok {
			http.Error(w, "unauthorized: open the URL printed by px0 (it carries an access token)", http.StatusUnauthorized)
			return false
		}
		if viaQuery {
			http.SetCookie(w, &http.Cookie{Name: tokenCookie, Value: s.accessToken, Path: "/", HttpOnly: true, SameSite: http.SameSiteStrictMode})
		}
		return true
	}
	if s.hostGuard && !hostAllowed(r.Host) {
		http.Error(w, "forbidden: open px0 by localhost or IP address", http.StatusForbidden)
		return false
	}
	return true
}
