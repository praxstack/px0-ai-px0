package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSettingsFileIs0600AndAtomic(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", dir)
	if err := updateSettingsMap(map[string]any{"github.token": "ghp_x", "editor.tabSize": 3}); err != nil {
		t.Fatal(err)
	}
	p := settingsPath()
	if fi, err := os.Stat(p); err != nil || fi.Mode().Perm() != 0o600 {
		t.Fatalf("settings.json mode = %v err=%v, want 0600", fi.Mode().Perm(), err)
	}
	if fi, err := os.Stat(filepath.Dir(p)); err != nil || fi.Mode().Perm() != 0o700 {
		t.Fatalf("settings dir mode = %v, want 0700", fi.Mode().Perm())
	}
	// A second write backs up the previous version and leaves no temp files.
	if err := updateSettingsMap(map[string]any{"editor.tabSize": 4}); err != nil {
		t.Fatal(err)
	}
	if fi, err := os.Stat(p + ".bak"); err != nil || fi.Mode().Perm() != 0o600 {
		t.Fatalf(".bak missing or wrong mode: %v", err)
	}
	ents, _ := os.ReadDir(filepath.Dir(p))
	for _, e := range ents {
		if e.Name() != "settings.json" && e.Name() != "settings.json.bak" {
			t.Errorf("stray file %q left behind", e.Name())
		}
	}
}

func TestInvalidSettingsNotWipedByWrite(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", dir)
	p := settingsPath()
	os.MkdirAll(filepath.Dir(p), 0o700)
	bad := []byte(`{"github.token": "ghp_keepme", "editor.tabSize": 2,`) // truncated by a hand edit
	os.WriteFile(p, bad, 0o600)

	if err := updateSettingsMap(map[string]any{"editor.tabSize": 4}); err == nil {
		t.Fatal("updateSettingsMap should refuse to overwrite an unparsable settings.json")
	}
	if err := writeSettings(settings{Agent: "claude"}); err == nil {
		t.Fatal("writeSettings should refuse to overwrite an unparsable settings.json")
	}
	if got, _ := os.ReadFile(p); string(got) != string(bad) {
		t.Fatalf("settings.json was modified: %q", got)
	}
	// Explicit raw replacement is the repair path and keeps a backup.
	if err := saveRawSettingsJSON([]byte(`{"editor.tabSize": 5}`)); err != nil {
		t.Fatal(err)
	}
	if b, _ := os.ReadFile(p + ".bak"); string(b) != string(bad) {
		t.Fatalf("backup = %q", b)
	}
}

func TestExistingSettingsPermsTightened(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", dir)
	p := settingsPath()
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		t.Fatal(err)
	}
	os.Chmod(filepath.Dir(p), 0o755)
	for _, f := range []string{p, p + ".bak"} {
		if err := os.WriteFile(f, []byte(`{"github.token":"ghp_x"}`), 0o644); err != nil {
			t.Fatal(err)
		}
		os.Chmod(f, 0o644)
	}
	tightenSettingsPerms()
	if fi, _ := os.Stat(filepath.Dir(p)); fi.Mode().Perm() != 0o700 {
		t.Errorf("existing settings dir mode = %v, want 0700", fi.Mode().Perm())
	}
	for _, f := range []string{p, p + ".bak"} {
		if fi, _ := os.Stat(f); fi.Mode().Perm() != 0o600 {
			t.Errorf("%s mode = %v, want 0600", filepath.Base(f), fi.Mode().Perm())
		}
	}
}

func TestSymlinkedSettingsWrittenThrough(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", dir)
	dotfiles := filepath.Join(t.TempDir(), "dotfiles")
	if err := os.MkdirAll(dotfiles, 0o755); err != nil {
		t.Fatal(err)
	}
	real := filepath.Join(dotfiles, "settings.json")
	if err := os.WriteFile(real, []byte(`{"editor.tabSize":2}`), 0o600); err != nil {
		t.Fatal(err)
	}
	p := settingsPath()
	if err := os.MkdirAll(filepath.Dir(p), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(real, p); err != nil {
		t.Skipf("symlinks unavailable: %v", err)
	}
	if err := updateSettingsMap(map[string]any{"editor.tabSize": 5}); err != nil {
		t.Fatal(err)
	}
	if fi, err := os.Lstat(p); err != nil || fi.Mode()&os.ModeSymlink == 0 {
		t.Fatalf("settings.json symlink was replaced by a regular file (err=%v)", err)
	}
	data, _ := os.ReadFile(real)
	if !strings.Contains(string(data), `"editor.tabSize": 5`) {
		t.Fatalf("link target not updated: %s", data)
	}
	if _, err := os.Stat(p + ".bak"); err != nil {
		t.Errorf(".bak not kept next to the link: %v", err)
	}
	ents, _ := os.ReadDir(dotfiles)
	if len(ents) != 1 {
		var names []string
		for _, e := range ents {
			names = append(names, e.Name())
		}
		t.Errorf("dotfiles dir gained files: %v", names)
	}
}

// The raw editor masks the token of an unparsable settings.json with
// maskGitHubTokens; saving the repaired text with the mask echoed back must keep
// the stored token, not drop it because the old file did not parse.
func TestRawRepairOfInvalidSettingsKeepsMaskedToken(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", dir)
	p := settingsPath()
	os.MkdirAll(filepath.Dir(p), 0o700)
	os.WriteFile(p, []byte(`{"github.token": "ghp_keep\"me", "editor.tabSize": 2,}`), 0o600)

	shown := readRawSettingsJSON()
	if strings.Contains(shown, "ghp_keep") || !strings.Contains(shown, maskedSecret) {
		t.Fatalf("raw view did not mask the token: %q", shown)
	}
	fixed := strings.Replace(shown, ",}", "}", 1)
	if err := saveRawSettingsJSON([]byte(fixed)); err != nil {
		t.Fatal(err)
	}
	if got := readSettingsRawMap()["github.token"]; got != `ghp_keep"me` {
		t.Fatalf("github.token after repair = %v, want the stored token", got)
	}

	// No recoverable token: refuse instead of silently dropping it.
	os.WriteFile(p, []byte(`{"github.token": 5, "editor.tabSize": 2,}`), 0o600)
	if err := saveRawSettingsJSON([]byte(`{"github.token":"` + maskedSecret + `"}`)); err == nil {
		t.Fatal("masked save over an unrecoverable token: want error")
	}
}

// A malformed settings.json can spell the key with JSON escapes; the raw view
// must still mask the token, and a repair that echoes the mask keeps it.
func TestRawViewMasksEscapedTokenKey(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", dir)
	p := settingsPath()
	os.MkdirAll(filepath.Dir(p), 0o700)
	esc := func(hex string) string { return string(rune(92)) + "u00" + hex } // a JSON \u00XX escape
	key := "github" + esc("2e") + esc("74") + "oken"                         // decodes to github.token
	val := "ghp_esc" + esc("61") + "ped"                                     // decodes to ghp_escaped
	os.WriteFile(p, []byte(`{"note": "github.token", "`+key+`": "`+val+`", "editor.tabSize": 2,}`), 0o600)

	shown := readRawSettingsJSON()
	if strings.Contains(shown, "ghp_esc") || !strings.Contains(shown, maskedSecret) {
		t.Fatalf("raw view did not mask the escaped-key token: %q", shown)
	}
	if !strings.Contains(shown, `"note": "github.token"`) {
		t.Fatalf("raw view masked a value that is not the token: %q", shown)
	}
	fixed := strings.Replace(shown, ",}", "}", 1)
	if err := saveRawSettingsJSON([]byte(fixed)); err != nil {
		t.Fatal(err)
	}
	if got := readSettingsRawMap()["github.token"]; got != "ghp_escaped" {
		t.Fatalf("github.token after repair = %v, want the stored token", got)
	}
}

// A dotfile manager can link settings.json before its target exists; the
// first save must create the target, not replace the link.
func TestDanglingSettingsSymlinkWrittenThrough(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", dir)
	dotfiles := filepath.Join(t.TempDir(), "dotfiles")
	if err := os.MkdirAll(dotfiles, 0o755); err != nil {
		t.Fatal(err)
	}
	p := settingsPath()
	if err := os.MkdirAll(filepath.Dir(p), 0o700); err != nil {
		t.Fatal(err)
	}
	// Relative link through a second link, both resolved from their own directory.
	if err := os.Symlink(filepath.Join(dotfiles, "hop.json"), p); err != nil {
		t.Skipf("symlinks unavailable: %v", err)
	}
	if err := os.Symlink("settings.json", filepath.Join(dotfiles, "hop.json")); err != nil {
		t.Fatal(err)
	}
	if err := updateSettingsMap(map[string]any{"editor.tabSize": 3}); err != nil {
		t.Fatal(err)
	}
	if fi, err := os.Lstat(p); err != nil || fi.Mode()&os.ModeSymlink == 0 {
		t.Fatalf("settings.json symlink was replaced by a regular file (err=%v)", err)
	}
	data, err := os.ReadFile(filepath.Join(dotfiles, "settings.json"))
	if err != nil || !strings.Contains(string(data), `"editor.tabSize": 3`) {
		t.Fatalf("link target not created: %s (err=%v)", data, err)
	}
}
