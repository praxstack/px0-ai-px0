package main

import (
	"os"
	"path/filepath"
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
