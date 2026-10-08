package main

import (
	"net"
	"net/http"
	"strings"
)

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
// It must be called before the server starts serving.
func (s *Server) Secure() {
	s.hostGuard = true
}

// guard applies the Host allowlist to every route, GET included. It returns
// false after writing the rejection when the request must not proceed.
func (s *Server) guard(w http.ResponseWriter, r *http.Request) bool {
	if s.hostGuard && !hostAllowed(r.Host) {
		http.Error(w, "forbidden: open px0 by localhost or IP address", http.StatusForbidden)
		return false
	}
	return true
}
