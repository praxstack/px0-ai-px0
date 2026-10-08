package fuzzy

import (
	"fmt"
	"strings"
	"testing"
)

func subsequence(sub, s string) bool {
	si := 0
	for i := 0; i < len(s) && si < len(sub); i++ {
		if s[i] == sub[si] {
			si++
		}
	}
	return si == len(sub)
}

func TestFuzzyRanking(t *testing.T) {
	t.Parallel()

	paths := []string{
		"internal/server/http_server.go",
		"cmd/px0/main.go",
		"web/app.js",
		"pkg/util/strings.go",
		"vendor/github.com/x/http/server.go",
		"httpserver.go",
	}
	items := make([]Item, len(paths))
	for i, p := range paths {
		items[i] = NewItem(p)
	}

	got := Find(items, "httpserver", 10)
	if len(got) == 0 {
		t.Fatal("no matches for httpserver")
	}
	if got[0].Path != "httpserver.go" {
		t.Errorf("best match for httpserver = %q, want httpserver.go", got[0].Path)
	}

	for _, r := range got {
		if !subsequence("httpserver", strings.ToLower(r.Path)) {
			t.Errorf("%q is not a subsequence match", r.Path)
		}
		for _, p := range r.Pos {
			if p < 0 || p >= len(r.Path) {
				t.Errorf("%q: highlight position %d out of range", r.Path, p)
			}
		}
	}

	if got := Find(items, "zzqq", 10); len(got) != 0 {
		t.Errorf("expected no matches, got %v", got)
	}

	if got := Find(items, "appjs", 10); len(got) == 0 || got[0].Path != "web/app.js" {
		t.Errorf("expected web/app.js for appjs, got %v", got)
	}
}

func TestFuzzyCaseSensitivity(t *testing.T) {
	t.Parallel()

	items := []Item{
		NewItem("src/HTTPServer.go"),
		NewItem("src/httpserver.go"),
	}

	res := Find(items, "HTTPServer", 10)
	if len(res) < 2 {
		t.Fatalf("expected 2 results, got %d", len(res))
	}
	if res[0].Path != "src/HTTPServer.go" {
		t.Errorf("expected 'src/HTTPServer.go' to rank higher for query 'HTTPServer', got: %s", res[0].Path)
	}
}

func TestFuzzyEmptyQuery(t *testing.T) {
	t.Parallel()

	items := []Item{
		NewItem("a.go"),
		NewItem("b.go"),
		NewItem("c.go"),
	}
	got := Find(items, "", 2)
	if len(got) != 2 {
		t.Fatalf("expected 2 items for empty query limit 2, got %d", len(got))
	}
	if got[0].Path != "a.go" || got[1].Path != "b.go" {
		t.Errorf("unexpected results: %+v", got)
	}
}

func TestIsBoundary(t *testing.T) {
	t.Parallel()

	boundaries := []byte{'/', '_', '-', '.', ' ', '@'}
	for _, b := range boundaries {
		if !IsBoundary(b) {
			t.Errorf("expected byte %q to be boundary", b)
		}
	}
	nonBoundaries := []byte{'a', 'Z', '0', '!', ':'}
	for _, nb := range nonBoundaries {
		if IsBoundary(nb) {
			t.Errorf("expected byte %q not to be boundary", nb)
		}
	}
}

// Find over NewItem folds letters whose lowercase has a different UTF-8 length
// (U+023A grows, U+0130 shrinks) without positions running past Path, and
// reports positions as UTF-16 indices (an astral letter is two units).
func TestFindFoldsUnicodeAndReportsUTF16(t *testing.T) {
	t.Parallel()

	astral := string(rune(0x10400))
	items := []Item{
		NewItem(strings.Repeat("Ⱥ", 12) + "zz.go"),
		NewItem("İİyy.go"),
		NewItem("sub/ȺxİÉ.md"),
		NewItem("École.go"),
		NewItem("d/" + astral + "x.go"),
	}
	cases := []struct{ q, want, pos string }{
		{"ⱥⱥzz", "", ""}, // only checks bounds below
		{"iiyy", "İİyy.go", "[0 1 2 3]"},
		{"ⱥxié", "sub/ȺxİÉ.md", "[4 5 6 7]"},
		{"école", "École.go", "[0 1 2 3 4]"},
		{string(rune(0x10428)) + "x", "d/" + astral + "x.go", "[2 3 4]"},
	}
	for _, c := range cases {
		res := Find(items, c.q, 10)
		if len(res) == 0 {
			t.Errorf("query %q: no results", c.q)
			continue
		}
		for _, r := range res {
			for _, p := range r.Pos {
				if p < 0 || p >= len(r.Path) {
					t.Fatalf("query %q: pos %d out of range for %q", c.q, p, r.Path)
				}
			}
		}
		if c.want != "" && (res[0].Path != c.want || fmt.Sprint(res[0].Pos) != c.pos) {
			t.Errorf("query %q: got %q %v, want %q %s", c.q, res[0].Path, res[0].Pos, c.want, c.pos)
		}
	}
}

func TestUTF16Positions(t *testing.T) {
	t.Parallel()

	astral := string(rune(0x10400)) // 4 UTF-8 bytes, 2 UTF-16 units
	cases := []struct {
		name, s       string
		bytePos, want []int
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
		if got := UTF16Positions(c.s, c.bytePos); fmt.Sprint(got) != fmt.Sprint(c.want) {
			t.Errorf("%s: UTF16Positions(%q, %v) = %v, want %v", c.name, c.s, c.bytePos, got, c.want)
		}
	}
}
