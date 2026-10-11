package main

import (
	"px0/internal/fuzzy"
	"runtime"
	"sort"
	"strings"
	"sync"
)

// FuzzyResult represents a matched file path ranked by the fuzzy search engine.
// Re-exported from internal/fuzzy.Result; Pos holds UTF-16 indices into Path.
type FuzzyResult = fuzzy.Result

// isBoundary reports whether a byte acts as a word or segment boundary.
func isBoundary(b byte) bool {
	return fuzzy.IsBoundary(b)
}

// fuzzyScore delegates to internal/fuzzy.ScoreFolded. Positions are byte
// offsets in e.Path.
func fuzzyScore(q, origQ string, e *FileEntry, pos []int) (int, []int, bool) {
	return fuzzy.ScoreFolded(q, origQ, e.Path, e.lower, e.lowerOff, e.nameStart, e.lowerNameStart, pos)
}

// foldLower folds a query the way paths are folded (internal/fuzzy.FoldLower).
func foldLower(s string) string { return fuzzy.FoldLower(s) }

// utf16Positions converts byte offsets in s to UTF-16 indices
// (internal/fuzzy.UTF16Positions).
func utf16Positions(s string, pos []int) []int { return fuzzy.UTF16Positions(s, pos) }

// newFileEntry builds an index entry with its folded path cached.
func newFileEntry(rel, name string, size int64) FileEntry {
	e := FileEntry{Path: rel, Name: name, Size: size, nameStart: len(rel) - len(name)}
	e.lower, e.lowerOff, e.lowerNameStart = fuzzy.FoldItem(rel, e.nameStart)
	return e
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
				local = append(local, FuzzyResult{Path: files[i].Path, Name: files[i].Name, Pos: cp, Score: s})
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
		if all[i].Score != all[j].Score {
			return all[i].Score > all[j].Score
		}
		return all[i].Path < all[j].Path
	})
	if len(all) > limit {
		all = all[:limit]
	}
	return all
}
