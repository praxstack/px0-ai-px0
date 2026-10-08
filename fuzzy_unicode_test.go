package main

import "testing"

func TestFuzzyFindLowerChangesLength(t *testing.T) {
	// U+023A and U+0130 lowercase to a different UTF-8 byte length.
	names := []string{"dir/Ⱥfile.go", "dir/İstanbul.go", "dir/plain.go"}
	var files []FileEntry
	for _, p := range names {
		ns := len(p) - len("file.go")
		files = append(files, FileEntry{Path: p, Name: p[4:], lower: asciiLowerString(p), nameStart: ns})
	}
	for _, q := range []string{"file", "go", "stan", "plain"} {
		for _, r := range FuzzyFind(files, q, 10) {
			for _, i := range r.Pos {
				if i < 0 || i >= len(r.Path) {
					t.Fatalf("pos %d out of range for %q", i, r.Path)
				}
			}
		}
	}
}
