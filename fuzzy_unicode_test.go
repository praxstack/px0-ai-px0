package main

import (
	"fmt"
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

// Fuzzy find folds case for non-ASCII letters too, and match positions still
// index Path.
func TestFuzzyFindFoldsUnicodeCase(t *testing.T) {
	root := t.TempDir()
	for _, n := range []string{"École.go", "Über.go", "Ωmega.go", "ȺȺzz.go", "plain.go"} {
		if err := os.WriteFile(filepath.Join(root, n), []byte("package x\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	ix := NewIndex(root)
	ix.Build()
	files := ix.Files()
	for q, want := range map[string]string{"école": "École.go", "über": "Über.go", "ÜBER": "Über.go", "ωmega": "Ωmega.go", "ȺȺzz": "ȺȺzz.go"} {
		res := FuzzyFind(files, q, 10)
		found := false
		for _, r := range res {
			found = found || strings.HasSuffix(r.Path, want)
			for _, i := range r.Pos {
				if i < 0 || i >= len(r.Path) {
					t.Fatalf("query %q: pos %d out of range for %q", q, i, r.Path)
				}
			}
		}
		if !found {
			t.Errorf("query %q: %s not found in %v", q, want, res)
		}
	}
}

// Letters whose lowercase form has a different UTF-8 length (U+023A Ⱥ → U+2C65
// ⱥ grows from 2 to 3 bytes; U+0130 İ → i shrinks from 2 to 1) still fold, and
// match positions are mapped back to Path (as UTF-16 indices, see
// TestUTF16Positions).
func TestFuzzyFindFoldsLengthChangingCase(t *testing.T) {
	root := t.TempDir()
	for _, n := range []string{"ȺȺzz.go", "İİyy.go", "sub/ȺxİÉ.md", "plain.go"} {
		p := filepath.Join(root, filepath.FromSlash(n))
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte("x\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	ix := NewIndex(root)
	ix.Build()
	files := ix.Files()
	cases := []struct {
		q, want string
		pos     []int
	}{
		{"ⱥⱥzz", "ȺȺzz.go", []int{0, 1, 2, 3}},
		{"ȺȺZZ", "ȺȺzz.go", []int{0, 1, 2, 3}},
		{"iiyy", "İİyy.go", []int{0, 1, 2, 3}},
		{"İİyy", "İİyy.go", []int{0, 1, 2, 3}},
		{"ⱥxié", "sub/ȺxİÉ.md", []int{4, 5, 6, 7}},
	}
	for _, c := range cases {
		var got *FuzzyResult
		for _, r := range FuzzyFind(files, c.q, 10) {
			if r.Path == c.want {
				got = &r
				break
			}
		}
		if got == nil {
			t.Errorf("query %q: %s not found", c.q, c.want)
			continue
		}
		if fmt.Sprint(got.Pos) != fmt.Sprint(c.pos) {
			t.Errorf("query %q on %q: pos %v, want %v", c.q, got.Path, got.Pos, c.pos)
		}
	}
}

// FuzzyResult.Pos is consumed by the browser, which indexes strings in UTF-16
// code units, so byte offsets are converted: a 2- or 3-byte character is one
// unit, an astral (4-byte) character is a surrogate pair and both of its units
// are listed so a highlight never splits the pair.
func TestUTF16Positions(t *testing.T) {
	astral := string(rune(0x10400)) // DESERET CAPITAL LONG I: 4 UTF-8 bytes, 2 UTF-16 units
	cases := []struct {
		name, s string
		bytePos []int
		want    []int
	}{
		{"ascii", "src/main.go", []int{0, 4, 9}, []int{0, 4, 9}},
		{"2-byte", "é/xé.go", []int{0, 1, 3, 4}, []int{0, 2, 3}},
		{"3-byte", "ⱥ中z.go", []int{0, 2, 3, 6}, []int{0, 1, 2}},
		{"astral", "a" + astral + "b.go", []int{1, 2, 3, 4, 5}, []int{1, 2, 3}},
		{"astral after BMP", "é" + astral + "中" + astral + "x", []int{2, 6, 9, 13}, []int{1, 2, 3, 4, 5, 6}},
		{"invalid byte", "a\xffb", []int{1, 2}, []int{1, 2}},
		{"none", "é.go", nil, nil},
	}
	for _, c := range cases {
		if got := utf16Positions(c.s, c.bytePos); fmt.Sprint(got) != fmt.Sprint(c.want) {
			t.Errorf("%s: utf16Positions(%q, %v) = %v, want %v", c.name, c.s, c.bytePos, got, c.want)
		}
	}

	// End to end: FuzzyFind reports UTF-16 indices for an astral basename.
	files := []FileEntry{newFileEntry("d/"+astral+"x.go", astral+"x.go", 1)}
	lower := string(rune(0x10428)) // its lowercase, also astral
	res := FuzzyFind(files, lower+"x", 1)
	if len(res) != 1 || fmt.Sprint(res[0].Pos) != "[2 3 4]" {
		t.Fatalf("FuzzyFind(%q) = %+v, want Pos [2 3 4]", lower+"x", res)
	}
}
