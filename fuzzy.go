package main

import (
	"runtime"
	"sort"
	"strings"
	"sync"
	"unicode"
	"unicode/utf16"
	"unicode/utf8"
)

// FuzzyResult represents a matched file path ranked by the fuzzy search engine.
type FuzzyResult struct {
	Path  string `json:"path"` // Workspace-relative path to the matched file
	Name  string `json:"name"` // Basename of the file
	Pos   []int  `json:"pos"`  // Matched characters as UTF-16 indices into Path (JavaScript string indices), for the frontend highlights
	score int    // Computed match quality score (higher is better)
}

// isBoundary reports whether a byte acts as a word or segment boundary
// in file paths (e.g. slashes, underscores, dashes, dots, spaces, or at-symbols).
func isBoundary(b byte) bool {
	switch b {
	case '/', '_', '-', '.', ' ', '@':
		return true
	}
	return false
}

// fuzzyScore does a two-pass match: forward to prove every query rune is
// present, then backward from that endpoint to pull the matched positions as
// tightly together as possible. Tight matches score higher, which is what makes
// "fzf feel" work without an O(n*m) dynamic program.
func fuzzyScore(q, origQ string, e *FileEntry, pos []int) (int, []int, bool) {
	p, lp := e.Path, e.lower
	qi, end := 0, -1
	for i := 0; i < len(lp) && qi < len(q); i++ {
		if lp[i] == q[qi] {
			qi++
			end = i
		}
	}
	if qi < len(q) {
		return 0, nil, false
	}

	pos = pos[:0]
	qi = len(q) - 1
	for i := end; i >= 0 && qi >= 0; i-- {
		if lp[i] == q[qi] {
			pos = append(pos, i)
			qi--
		}
	}
	// Collected right-to-left; flip in place.
	for i, j := 0, len(pos)-1; i < j; i, j = i+1, j-1 {
		pos[i], pos[j] = pos[j], pos[i]
	}
	lowerNameStart := e.nameStart
	if e.lowerOff != nil {
		// Map positions in the folded path back to byte offsets in Path. Bytes
		// of one folded rune can map to the same Path byte; keep it once.
		lowerNameStart = e.lowerNameStart
		n := 0
		for _, i := range pos {
			o := int(e.lowerOff[i])
			if n == 0 || o != pos[n-1] {
				pos[n] = o
				n++
			}
		}
		pos = pos[:n]
	}

	score, prev := 0, -2
	for k, i := range pos {
		if i == prev+1 {
			score += 12 // consecutive run
		} else if k > 0 {
			score -= min(i-prev, 12) // gap penalty, bounded
		}
		if i >= e.nameStart {
			score += 14 // basename beats directory noise
		}
		if i == 0 || isBoundary(p[i-1]) {
			score += 16 // start of a path or word segment
		} else if p[i] >= 'A' && p[i] <= 'Z' && p[i-1] >= 'a' && p[i-1] <= 'z' {
			score += 14 // camelCase hump
		}
		if k < len(origQ) && p[i] == origQ[k] {
			score += 4 // exact case
		}
		prev = i
	}
	// Prefer the shallower, shorter of two otherwise-equal paths.
	score -= len(p) / 8
	score -= strings.Count(p, "/") * 2
	if idx := strings.Index(e.lower[lowerNameStart:], q); idx >= 0 {
		score += 40 // whole query appears verbatim in the basename
		if idx == 0 {
			score += 20
		}
	}
	return score, pos, true
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// foldPath lowercases s rune by rune for fuzzy matching. Every rune folds to
// exactly one rune, but not always to one of the same UTF-8 length (U+023A
// grows from 2 to 3 bytes, U+0130 shrinks from 2 to 1). While every rune keeps
// its length the result is byte-aligned with s and off is nil; otherwise off[j]
// is the byte offset in s that byte j of the result stands for, so match
// positions can be mapped back to s. An invalid byte is kept as it is.
func foldPath(s string) (string, []int32) {
	i := 0
	for i < len(s) && s[i] < utf8.RuneSelf {
		i++
	}
	if i == len(s) {
		return asciiLowerString(s), nil
	}
	b := make([]byte, 0, len(s)+8)
	b = append(b, asciiLowerString(s[:i])...)
	var off []int32
	for i < len(s) {
		r, size := utf8.DecodeRuneInString(s[i:])
		start := len(b)
		if r == utf8.RuneError && size == 1 {
			b = append(b, s[i])
		} else {
			b = utf8.AppendRune(b, unicode.ToLower(r))
		}
		n := len(b) - start
		if n != size && off == nil {
			off = make([]int32, start, cap(b))
			for j := range off {
				off[j] = int32(j) // every earlier rune kept its length
			}
		}
		if off != nil {
			for j := 0; j < n; j++ {
				off = append(off, int32(i+min(j, size-1)))
			}
		}
		i += size
	}
	return string(b), off
}

// foldLower is foldPath without the offset map, for queries.
func foldLower(s string) string {
	l, _ := foldPath(s)
	return l
}

// newFileEntry builds an index entry with its folded path cached.
func newFileEntry(rel, name string, size int64) FileEntry {
	lower, off := foldPath(rel)
	e := FileEntry{Path: rel, Name: name, Size: size, lower: lower, lowerOff: off, nameStart: len(rel) - len(name)}
	e.lowerNameStart = e.nameStart
	if off != nil {
		e.lowerNameStart = len(lower) - len(foldLower(name))
	}
	return e
}

// utf16Positions turns sorted byte offsets in s into the UTF-16 code unit
// indices of the characters they fall in, which is how the browser indexes
// strings. Every unit of a matched character is listed, so a surrogate pair is
// never split by a highlight. An invalid byte counts as one unit, as the JSON
// encoder sends it as U+FFFD. For ASCII s the offsets are already indices.
func utf16Positions(s string, pos []int) []int {
	if len(pos) == 0 {
		return pos
	}
	i := 0
	for i < len(s) && s[i] < utf8.RuneSelf {
		i++
	}
	if i == len(s) {
		return pos
	}
	out := make([]int, 0, len(pos)+2)
	k, u := 0, 0
	for b := 0; b < len(s) && k < len(pos); {
		r, size := utf8.DecodeRuneInString(s[b:])
		n := 1
		if !(r == utf8.RuneError && size == 1) {
			n = utf16.RuneLen(r)
		}
		hit := false
		for k < len(pos) && pos[k] < b+size {
			hit = hit || pos[k] >= b
			k++
		}
		if hit {
			for j := 0; j < n; j++ {
				out = append(out, u+j)
			}
		}
		b += size
		u += n
	}
	return out
}

// FuzzyFind ranks every indexed path against query and returns the best limit.
func FuzzyFind(files []FileEntry, query string, limit int) []FuzzyResult {
	origQ := strings.ReplaceAll(strings.TrimSpace(query), " ", "")
	q := foldLower(origQ)

	if q == "" {
		out := make([]FuzzyResult, 0, limit)
		for i := range files {
			if i == limit {
				break
			}
			out = append(out, FuzzyResult{Path: files[i].Path, Name: files[i].Name})
		}
		return out
	}

	workers := runtime.NumCPU()
	chunk := (len(files) + workers - 1) / workers
	if chunk == 0 {
		chunk = 1
	}
	parts := make([][]FuzzyResult, workers)
	var wg sync.WaitGroup
	for w := 0; w < workers; w++ {
		lo := w * chunk
		if lo >= len(files) {
			break
		}
		hi := min(lo+chunk, len(files))
		wg.Add(1)
		go func(w, lo, hi int) {
			defer wg.Done()
			local := make([]FuzzyResult, 0, 64)
			scratch := make([]int, 0, 64)
			for i := lo; i < hi; i++ {
				s, pos, ok := fuzzyScore(q, origQ, &files[i], scratch)
				if !ok {
					continue
				}
				cp := make([]int, len(pos))
				copy(cp, pos)
				cp = utf16Positions(files[i].Path, cp)
				local = append(local, FuzzyResult{Path: files[i].Path, Name: files[i].Name, Pos: cp, score: s})
			}
			parts[w] = local
		}(w, lo, hi)
	}
	wg.Wait()

	var all []FuzzyResult
	for _, p := range parts {
		all = append(all, p...)
	}
	sort.Slice(all, func(i, j int) bool {
		if all[i].score != all[j].score {
			return all[i].score > all[j].score
		}
		return all[i].Path < all[j].Path
	})
	if len(all) > limit {
		all = all[:limit]
	}
	return all
}
