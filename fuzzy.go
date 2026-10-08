package main

import (
	"runtime"
	"sort"
	"strings"
	"sync"
	"unicode"
	"unicode/utf8"
)

// FuzzyResult represents a matched file path ranked by the fuzzy search engine.
type FuzzyResult struct {
	Path  string `json:"path"` // Workspace-relative path to the matched file
	Name  string `json:"name"` // Basename of the file
	Pos   []int  `json:"pos"`  // Byte offsets in Path that matched, used by frontend for highlight badges
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
	if idx := strings.Index(e.lower[e.nameStart:], q); idx >= 0 {
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

// foldLower lowercases s for fuzzy matching without changing its byte length,
// so a byte offset in the result is the same offset in s. Each rune is
// lowercased only when its lowercase form encodes to the same number of bytes
// (É→é, Ü→ü, Ω→ω); a rune whose lowercase is longer or shorter (U+023A, U+0130)
// and any invalid byte are kept as they are.
func foldLower(s string) string {
	i := 0
	for i < len(s) && s[i] < utf8.RuneSelf {
		i++
	}
	if i == len(s) {
		return asciiLowerString(s)
	}
	b := make([]byte, 0, len(s))
	b = append(b, asciiLowerString(s[:i])...)
	for i < len(s) {
		r, size := utf8.DecodeRuneInString(s[i:])
		if r != utf8.RuneError || size > 1 {
			if l := unicode.ToLower(r); utf8.RuneLen(l) == size {
				b = utf8.AppendRune(b, l)
				i += size
				continue
			}
		}
		b = append(b, s[i:i+size]...)
		i += size
	}
	return string(b)
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
