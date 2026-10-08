package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestFuzzyFindLowerChangesLength goes through the real Index.Build, which is
// where FileEntry.lower is produced. U+023A (2 bytes) lowercases to U+2C65
// (3 bytes) and U+0130 (2 bytes) lowercases to "i̇" (3 bytes), so a
// strings.ToLower-built lower is longer than Path and match positions taken
// from it run past the end of Path (index out of range in fuzzy.go).
func TestFuzzyFindLowerChangesLength(t *testing.T) {
	root := t.TempDir()
	names := []string{
		strings.Repeat("Ⱥ", 12) + "zz.go",
		strings.Repeat("İ", 12) + "yy.go",
		"dir/" + strings.Repeat("Ⱥ", 8) + "file.go",
		"plain.go",
	}
	for _, n := range names {
		p := filepath.Join(root, filepath.FromSlash(n))
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte("package x\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	ix := NewIndex(root)
	ix.Build()
	files := ix.Files()
	if len(files) < len(names) {
		t.Fatalf("indexed %d files, want %d", len(files), len(names))
	}
	for _, q := range []string{"zz", "yy", "zzgo", "yygo", "file", "go", "plain"} {
		res := FuzzyFind(files, q, 10)
		if len(res) == 0 {
			t.Errorf("query %q: no results", q)
		}
		for _, r := range res {
			for _, i := range r.Pos {
				if i < 0 || i >= len(r.Path) {
					t.Fatalf("query %q: pos %d out of range for %q", q, i, r.Path)
				}
			}
		}
	}
}
