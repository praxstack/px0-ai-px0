package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sync"
)

// px0 keeps no state inside a workspace. The user's preferences and choices
// are stored with the other per-user files px0 writes (~/.px0/settings.json),
// never in the working tree.

// settings stores user configuration written to ~/.px0/settings.json (or XDG_CONFIG_HOME/px0/settings.json).
// All settings are optional pointers so omitted values fall back to application defaults.
type settings struct {
	Agent  string            `json:"agent,omitempty"`
	Models map[string]string `json:"models,omitempty"`

	EditorFontSize              *float64 `json:"editor.fontSize,omitempty"`
	EditorFontFamily            *string  `json:"editor.fontFamily,omitempty"`
	EditorLineHeight            *float64 `json:"editor.lineHeight,omitempty"`
	EditorTabSize               *int     `json:"editor.tabSize,omitempty"`
	EditorWordWrap              *string  `json:"editor.wordWrap,omitempty"`
	EditorLineNumbers           *string  `json:"editor.lineNumbers,omitempty"`
	EditorVimMode               *bool    `json:"editor.vimMode,omitempty"`
	EditorRenderWhitespace      *string  `json:"editor.renderWhitespace,omitempty"`
	EditorMinimapEnabled        *bool    `json:"editor.minimap.enabled,omitempty"`
	WorkbenchColorTheme         *string  `json:"workbench.colorTheme,omitempty"`
	DiffEditorRenderSideBySide  *bool    `json:"diffEditor.renderSideBySide,omitempty"`
	MarkdownPreviewOpen         *bool    `json:"markdown.preview.open,omitempty"`
	TablePreviewOpen            *bool    `json:"table.preview.open,omitempty"`
	TelemetryEnabled            *bool    `json:"telemetry.enabled,omitempty"`
	GitHubToken                 *string  `json:"github.token,omitempty"`
	GitCommitMessageInstruction *string  `json:"git.commitMessageInstruction,omitempty"`
	ServerBasePath              *string  `json:"server.basePath,omitempty"`
	ExplorerAutoReveal          *bool    `json:"explorer.autoReveal,omitempty"`
}

var settingsMu sync.Mutex

// settingsPath mirrors stateFilePath in update.go: honour the XDG location when
// it is set, otherwise fall back to ~/.px0.
func settingsPath() string {
	if xdg := os.Getenv("XDG_CONFIG_HOME"); xdg != "" {
		return filepath.Join(xdg, "px0", "settings.json")
	}
	home, err := os.UserHomeDir()
	if err != nil || home == "" {
		return ""
	}
	return filepath.Join(home, ".px0", "settings.json")
}

// settingSchemaItem describes a configurable setting for dynamic rendering in the settings modal.
type settingSchemaItem struct {
	Key         string   `json:"key"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	Category    string   `json:"category"`
	Type        string   `json:"type"` // "string", "number", "boolean", "select"
	Default     any      `json:"default"`
	Options     []string `json:"options,omitempty"`
	Min         *float64 `json:"min,omitempty"`
	Max         *float64 `json:"max,omitempty"`
	Step        *float64 `json:"step,omitempty"`
	Secret      bool     `json:"secret,omitempty"` // render as a masked input; /api/settings returns maskedSecret in its place
}

func numPtr(v float64) *float64 { return &v }

var settingsSchema = []settingSchemaItem{
	{
		Key:         "editor.fontSize",
		Title:       "Font Size",
		Description: "Controls the font size in pixels for the code viewer.",
		Category:    "Text Editor",
		Type:        "number",
		Default:     13.5,
		Min:         numPtr(9.0),
		Max:         numPtr(32.0),
		Step:        numPtr(0.5),
	},
	{
		Key:         "editor.fontFamily",
		Title:       "Font Family",
		Description: "Controls the font family used in the code viewer.",
		Category:    "Text Editor",
		Type:        "string",
		Default:     `"JetBrains Mono", "Fira Code", "Cascadia Code", "SF Mono", Menlo, Consolas, ui-monospace, monospace`,
	},
	{
		Key:         "editor.lineHeight",
		Title:       "Line Height",
		Description: "Controls the line height in pixels for the code viewer.",
		Category:    "Text Editor",
		Type:        "number",
		Default:     21.0,
		Min:         numPtr(14.0),
		Max:         numPtr(48.0),
		Step:        numPtr(1.0),
	},
	{
		Key:         "editor.tabSize",
		Title:       "Tab Size",
		Description: "The number of spaces a tab is equal to.",
		Category:    "Text Editor",
		Type:        "select",
		Default:     4,
		Options:     []string{"2", "4", "8"},
	},
	{
		Key:         "editor.wordWrap",
		Title:       "Word Wrap",
		Description: "Controls whether lines should wrap around or scroll horizontally.",
		Category:    "Text Editor",
		Type:        "select",
		Default:     "on",
		Options:     []string{"on", "off"},
	},
	{
		Key:         "editor.lineNumbers",
		Title:       "Line Numbers",
		Description: "Controls the display of line numbers in the gutter.",
		Category:    "Text Editor",
		Type:        "select",
		Default:     "on",
		Options:     []string{"on", "off"},
	},
	{
		Key:         "editor.vimMode",
		Title:       "Vim Keybindings",
		Description: "Enable Vim modal navigation (Normal mode, Visual mode, motions, search, and LSP shortcuts).",
		Category:    "Text Editor",
		Type:        "boolean",
		Default:     false,
	},
	{
		Key:         "editor.renderWhitespace",
		Title:       "Render Whitespace",
		Description: "Controls how whitespace characters are rendered in the viewer.",
		Category:    "Text Editor",
		Type:        "select",
		Default:     "selection",
		Options:     []string{"none", "boundary", "selection", "all"},
	},
	{
		Key:         "editor.minimap.enabled",
		Title:       "Minimap Hits",
		Description: "Controls whether search hit indicators are shown in the scroll minimap gutter.",
		Category:    "Text Editor",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "workbench.colorTheme",
		Title:       "Color Theme",
		Description: "Specifies the color theme used in the workbench.",
		Category:    "Workbench",
		Type:        "select",
		Default:     "catppuccin-mocha",
		Options: []string{
			"catppuccin-mocha", "catppuccin-latte",
			"github-dark", "dark", "light",
			"dracula", "gruvbox-dark", "gruvbox-light",
			"monokai", "nord", "one-dark", "rose-pine",
			"solarized-dark", "solarized-light",
		},
	},
	{
		Key:         "diffEditor.renderSideBySide",
		Title:       "Diff Side By Side",
		Description: "Controls whether the diff editor shows changes in split (side-by-side) or unified mode.",
		Category:    "Workbench",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "markdown.preview.open",
		Title:       "Markdown Preview",
		Description: "Controls whether Markdown files open in rendered preview by default.",
		Category:    "Workbench",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "table.preview.open",
		Title:       "Table View",
		Description: "Controls whether CSV and TSV files open as a table by default.",
		Category:    "Workbench",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "editor.cursorStyle",
		Title:       "Cursor Style",
		Description: "Controls the cursor style in the code viewer.",
		Category:    "Text Editor",
		Type:        "select",
		Default:     "line",
		Options:     []string{"line", "block", "underline"},
	},
	{
		Key:         "editor.cursorBlinking",
		Title:       "Cursor Blinking",
		Description: "Controls the cursor animation style.",
		Category:    "Text Editor",
		Type:        "select",
		Default:     "smooth",
		Options:     []string{"blink", "smooth", "solid"},
	},
	{
		Key:         "editor.renderLineHighlight",
		Title:       "Render Line Highlight",
		Description: "Controls how the editor should render the current line highlight.",
		Category:    "Text Editor",
		Type:        "select",
		Default:     "line",
		Options:     []string{"line", "none"},
	},
	{
		Key:         "editor.occurrencesHighlight",
		Title:       "Occurrences Highlight",
		Description: "Controls whether the editor should highlight occurrences of the selected word.",
		Category:    "Text Editor",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "editor.scrollBeyondLastLine",
		Title:       "Scroll Beyond Last Line",
		Description: "Controls whether the editor will scroll beyond the last line of the file.",
		Category:    "Text Editor",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "editor.bracketPairColorization",
		Title:       "Bracket Pair Colorization",
		Description: "Controls whether bracket pair colorization and matching is enabled.",
		Category:    "Text Editor",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "explorer.compactFolders",
		Title:       "Compact Folders",
		Description: "Controls whether the file tree renders single-child directory chains compactly.",
		Category:    "Files & Explorer",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "explorer.autoReveal",
		Title:       "Auto Reveal",
		Description: "Controls whether the file explorer automatically scrolls to and reveals active tabs.",
		Category:    "Files & Explorer",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "files.exclude",
		Title:       "Files Exclude Patterns",
		Description: "Configure glob patterns for excluding files and folders from search and trees.",
		Category:    "Files & Explorer",
		Type:        "string",
		Default:     "**/.git, **/node_modules, **/target, **/.DS_Store",
	},
	{
		Key:         "search.smartCase",
		Title:       "Smart Case Search",
		Description: "Searches case-insensitively when query is lowercase, and case-sensitively when uppercase characters exist.",
		Category:    "Search",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "search.maxResults",
		Title:       "Max Search Results",
		Description: "Controls the maximum number of results returned in workspace-wide searches.",
		Category:    "Search",
		Type:        "number",
		Default:     1000.0,
		Min:         numPtr(50.0),
		Max:         numPtr(10000.0),
		Step:        numPtr(50.0),
	},
	{
		Key:         "diffEditor.ignoreTrimWhitespace",
		Title:       "Diff: Ignore Trim Whitespace",
		Description: "Controls whether the diff viewer ignores changes in leading or trailing whitespace.",
		Category:    "Git & Diff",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "git.gutterIndicators",
		Title:       "Git Gutter Indicators",
		Description: "Controls whether changed line indicators are shown in the editor gutter.",
		Category:    "Git & Diff",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "lsp.enabled",
		Title:       "Language Server Protocol (LSP)",
		Description: "Master switch for language server integrations (definitions, references, diagnostics).",
		Category:    "LSP & Intelligence",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "lsp.hover.enabled",
		Title:       "Hover Documentation",
		Description: "Controls whether hovercards with documentation and type signatures appear on hover.",
		Category:    "LSP & Intelligence",
		Type:        "boolean",
		Default:     true,
	},
	{
		Key:         "agent.harness",
		Title:       "Coding Harness",
		Description: "Coding agent harness invoked for code edits (e.g. claude, gemini, cursor-agent, agy, opencode, codex, aider, goose).",
		Category:    "Agent / AI",
		Type:        "string",
		Default:     "",
	},
	{
		Key:         "agent.timeoutSeconds",
		Title:       "Agent Timeout (Seconds)",
		Description: "Controls the maximum execution time in seconds for agent edits before canceling.",
		Category:    "Agent / AI",
		Type:        "number",
		Default:     120.0,
		Min:         numPtr(10.0),
		Max:         numPtr(600.0),
		Step:        numPtr(10.0),
	},
	{
		Key:         "agent.autoAcceptEdits",
		Title:       "Auto Accept Agent Edits",
		Description: "Controls whether agent-generated code diffs are accepted without manual confirmation.",
		Category:    "Agent / AI",
		Type:        "boolean",
		Default:     false,
	},
	{
		Key:         "git.commitMessageInstruction",
		Title:       "Commit Message Instructions",
		Description: "Extra instructions given to the coding harness when it writes a commit message for the staged diff (e.g. \"Follow Conventional Commits\" or \"Reference the ticket number in the branch name\").",
		Category:    "Git & Diff",
		Type:        "textarea",
		Default:     "",
	},
	{
		Key:         "github.token",
		Title:       "GitHub Token",
		Description: "Personal access token used to check out and review pull requests (px0 <url>). Takes precedence over the GITHUB_TOKEN environment variable and 'gh auth token'.",
		Category:    "GitHub",
		Type:        "string",
		Default:     "",
		Secret:      true,
	},
	{
		Key:         "server.basePath",
		Title:       "Base Path",
		Description: "Base URL path prefix for the px0 server and web interface (e.g. /rev-123/).",
		Category:    "Server",
		Type:        "string",
		Default:     "/",
	},
}

func defaultSettingsMap() map[string]any {
	res := make(map[string]any, len(settingsSchema)+3)
	for _, item := range settingsSchema {
		res[item.Key] = item.Default
	}
	res["explorer.autoRelveal"] = true
	res["agent"] = ""
	res["models"] = map[string]string{}
	return res
}

// readSettingsRawMap returns the raw JSON contents unmarshaled into a map.
// It never fails: a missing or corrupt file returns an empty map.
func readSettingsRawMap() map[string]any {
	p := settingsPath()
	if p == "" {
		return map[string]any{}
	}
	data, err := os.ReadFile(p)
	if err != nil {
		return map[string]any{}
	}
	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil || m == nil {
		return map[string]any{}
	}
	return m
}

// readSettingsRawMapStrict is the read used before a write: a missing or empty
// file is an empty map, but a file that exists and does not parse is an error,
// so a typo in settings.json is never silently replaced by defaults.
func readSettingsRawMapStrict() (map[string]any, error) {
	p := settingsPath()
	if p == "" {
		return map[string]any{}, nil
	}
	data, err := os.ReadFile(p)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return map[string]any{}, nil
		}
		return nil, err
	}
	if len(bytes.TrimSpace(data)) == 0 {
		return map[string]any{}, nil
	}
	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, fmt.Errorf("%s is not valid JSON (fix or remove it; not overwriting): %w", p, err)
	}
	if m == nil {
		m = map[string]any{}
	}
	return m, nil
}

// readSettings never fails: a missing or corrupt file simply means no choice
// has been made yet, which is the same as a fresh install.
func readSettings() settings {
	settingsMu.Lock()
	defer settingsMu.Unlock()
	return readSettingsLocked()
}

func readSettingsLocked() settings {
	var s settings
	raw := readSettingsRawMap()
	if len(raw) == 0 {
		return s
	}

	// Unmarshal known typed fields
	if b, err := json.Marshal(raw); err == nil {
		_ = json.Unmarshal(b, &s)
	}

	// Bi-directional bridge between agent <-> agent.harness
	if s.Agent == "" {
		if h, ok := raw["agent.harness"].(string); ok && h != "" {
			s.Agent = h
		}
	}
	// Support server.basePath and basePath fallback
	if s.ServerBasePath == nil {
		if bp, ok := raw["server.basePath"].(string); ok && bp != "" {
			s.ServerBasePath = &bp
		} else if bp, ok := raw["basePath"].(string); ok && bp != "" {
			s.ServerBasePath = &bp
		}
	}
	// Bi-directional bridge between models <-> agent.models
	if s.Models == nil || len(s.Models) == 0 {
		if am, ok := raw["agent.models"].(map[string]any); ok {
			s.Models = make(map[string]string, len(am))
			for k, v := range am {
				if vs, ok := v.(string); ok {
					s.Models[k] = vs
				}
			}
		}
	}
	// Support explorer.autoReveal and explorer.autoRelveal
	if s.ExplorerAutoReveal == nil {
		if ar, ok := raw["explorer.autoReveal"].(bool); ok {
			s.ExplorerAutoReveal = &ar
		} else if ar, ok := raw["explorer.autoRelveal"].(bool); ok {
			s.ExplorerAutoReveal = &ar
		} else if ar, ok := raw["autoReveal"].(bool); ok {
			s.ExplorerAutoReveal = &ar
		} else if ar, ok := raw["autoRelveal"].(bool); ok {
			s.ExplorerAutoReveal = &ar
		}
	}

	return s
}

// maskedSecret stands in for secret values in anything sent to the browser.
// Writing it back leaves the stored secret untouched.
const maskedSecret = "********"

// jsonStringPairRe matches a "key": "string" pair in JSON text. It is used on a
// settings.json that does not parse, so it cannot rely on a decoder.
var jsonStringPairRe = regexp.MustCompile(`("(?:[^"\\]|\\.)*")\s*:\s*("(?:[^"\\]|\\.)*")`)

// githubTokenSpans returns the byte spans of the quoted string values in data
// whose key decodes to github.token, however the key is escaped.
func githubTokenSpans(data []byte) [][2]int {
	var out [][2]int
	for _, m := range jsonStringPairRe.FindAllSubmatchIndex(data, -1) {
		var k string
		if json.Unmarshal(data[m[2]:m[3]], &k) == nil && k == "github.token" {
			out = append(out, [2]int{m[4], m[5]})
		}
	}
	return out
}

// maskGitHubTokens replaces every github.token string value in data, which
// need not be valid JSON, with maskedSecret.
func maskGitHubTokens(data []byte) string {
	var b bytes.Buffer
	last := 0
	for _, sp := range githubTokenSpans(data) {
		b.Write(data[last:sp[0]])
		b.WriteString(`"` + maskedSecret + `"`)
		last = sp[1]
	}
	b.Write(data[last:])
	return b.String()
}

// storedGitHubToken returns the github.token in settings.json for a save that
// echoed maskedSecret back. A file that does not parse is the raw editor's
// repair case: its token was masked with maskGitHubTokens, so it is recovered the
// same way. When that is not possible (no unique string value) it is an error
// rather than a silent loss of the token.
func storedGitHubToken() (tok any, ok bool, err error) {
	m, err := readSettingsRawMapStrict()
	if err == nil {
		tok, ok = m["github.token"]
		return tok, ok, nil
	}
	data, rerr := os.ReadFile(settingsPath())
	if rerr != nil {
		return nil, false, rerr
	}
	values := map[string]bool{}
	for _, sp := range githubTokenSpans(data) {
		var v string
		if json.Unmarshal(data[sp[0]:sp[1]], &v) != nil {
			values = nil
			break
		}
		values[v] = true
	}
	if len(values) == 1 {
		for v := range values {
			if v != maskedSecret {
				return v, true, nil
			}
		}
	}
	return nil, false, errors.New("cannot recover the stored github.token from the invalid settings.json; enter the token again instead of " + maskedSecret)
}

// readMergedSettingsMap returns all settings, overlaying stored settings onto defaults.
func readMergedSettingsMap() map[string]any {
	settingsMu.Lock()
	defer settingsMu.Unlock()

	res := defaultSettingsMap()
	raw := readSettingsRawMap()

	for k, v := range raw {
		res[k] = v
	}
	if t, ok := res["github.token"].(string); ok && t != "" {
		res["github.token"] = maskedSecret
	}

	// Synchronize agent / agent.harness
	if ag, ok := raw["agent"].(string); ok && ag != "" {
		res["agent.harness"] = ag
	} else if ah, ok := raw["agent.harness"].(string); ok && ah != "" {
		res["agent"] = ah
	}

	// Synchronize models / agent.models
	if m, ok := raw["models"].(map[string]any); ok && len(m) > 0 {
		res["agent.models"] = m
	} else if am, ok := raw["agent.models"].(map[string]any); ok && len(am) > 0 {
		res["models"] = am
	}

	// Synchronize server.basePath / basePath
	if bp, ok := raw["server.basePath"].(string); ok && bp != "" {
		res["server.basePath"] = bp
	} else if bp, ok := raw["basePath"].(string); ok && bp != "" {
		res["server.basePath"] = bp
	}

	// Synchronize explorer.autoReveal / explorer.autoRelveal
	if ar, ok := raw["explorer.autoReveal"].(bool); ok {
		res["explorer.autoReveal"] = ar
		res["explorer.autoRelveal"] = ar
	} else if ar, ok := raw["explorer.autoRelveal"].(bool); ok {
		res["explorer.autoReveal"] = ar
		res["explorer.autoRelveal"] = ar
	} else if ar, ok := raw["autoReveal"].(bool); ok {
		res["explorer.autoReveal"] = ar
		res["explorer.autoRelveal"] = ar
	} else if ar, ok := raw["autoRelveal"].(bool); ok {
		res["explorer.autoReveal"] = ar
		res["explorer.autoRelveal"] = ar
	} else {
		res["explorer.autoReveal"] = true
		res["explorer.autoRelveal"] = true
	}

	return res
}

// readRawSettingsJSON returns formatted settings.json file content as string.
func readRawSettingsJSON() string {
	settingsMu.Lock()
	defer settingsMu.Unlock()

	p := settingsPath()
	if p == "" {
		return "{}\n"
	}
	data, err := os.ReadFile(p)
	if err != nil || len(data) == 0 {
		return "{\n}\n"
	}
	// Pretty format if possible
	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		return maskGitHubTokens(data)
	} else {
		if t, ok := raw["github.token"].(string); ok && t != "" {
			raw["github.token"] = maskedSecret
		}
		if formatted, err := json.MarshalIndent(raw, "", "  "); err == nil {
			return string(formatted) + "\n"
		}
	}
	return maskGitHubTokens(data)
}

// writeSettings saves the agent and models choices while preserving other settings.
func writeSettings(s settings) error {
	p := settingsPath()
	if p == "" {
		return errors.New("no home directory to save settings in")
	}
	settingsMu.Lock()
	defer settingsMu.Unlock()

	raw, err := readSettingsRawMapStrict()
	if err != nil {
		return err
	}
	if s.Agent != "" {
		raw["agent"] = s.Agent
		raw["agent.harness"] = s.Agent
	} else {
		delete(raw, "agent")
		delete(raw, "agent.harness")
	}

	if s.Models != nil && len(s.Models) > 0 {
		raw["models"] = s.Models
		raw["agent.models"] = s.Models
	} else if s.Agent == "" {
		delete(raw, "models")
		delete(raw, "agent.models")
	}

	return writeRawMapLocked(p, raw)
}

// updateSettingsMap merges key-value pairs into settings.json without losing existing keys.
func updateSettingsMap(updates map[string]any) error {
	p := settingsPath()
	if p == "" {
		return errors.New("no home directory to save settings in")
	}
	settingsMu.Lock()
	defer settingsMu.Unlock()

	raw, err := readSettingsRawMapStrict()
	if err != nil {
		return err
	}
	for k, v := range updates {
		if k == "github.token" && v == maskedSecret {
			continue // the browser echoed the mask back: keep the stored token
		}
		if v == nil {
			delete(raw, k)
		} else {
			raw[k] = v
		}

		// Keep agent / agent.harness in sync
		if k == "agent" {
			if v == nil || v == "" {
				delete(raw, "agent.harness")
			} else {
				raw["agent.harness"] = v
			}
		} else if k == "agent.harness" {
			if v == nil || v == "" {
				delete(raw, "agent")
			} else {
				raw["agent"] = v
			}
		}

		// Keep models / agent.models in sync
		if k == "models" {
			if v == nil {
				delete(raw, "agent.models")
			} else {
				raw["agent.models"] = v
			}
		} else if k == "agent.models" {
			if v == nil {
				delete(raw, "models")
			} else {
				raw["models"] = v
			}
		}

		// Keep server.basePath / basePath in sync
		if k == "server.basePath" {
			if v == nil || v == "" {
				delete(raw, "server.basePath")
				delete(raw, "basePath")
			} else {
				raw["server.basePath"] = v
			}
		} else if k == "basePath" {
			if v == nil || v == "" {
				delete(raw, "server.basePath")
				delete(raw, "basePath")
			} else {
				raw["server.basePath"] = v
				raw["basePath"] = v
			}
		}

		// Keep explorer.autoReveal / explorer.autoRelveal in sync
		if k == "explorer.autoReveal" || k == "explorer.autoRelveal" || k == "autoReveal" || k == "autoRelveal" {
			if v == nil {
				delete(raw, "explorer.autoReveal")
				delete(raw, "explorer.autoRelveal")
				delete(raw, "autoReveal")
				delete(raw, "autoRelveal")
			} else {
				raw["explorer.autoReveal"] = v
				raw["explorer.autoRelveal"] = v
			}
		}
	}

	return writeRawMapLocked(p, raw)
}

// saveRawSettingsJSON parses and validates raw JSON text and writes it formatted.
func saveRawSettingsJSON(rawJSON []byte) error {
	var m map[string]any
	if err := json.Unmarshal(rawJSON, &m); err != nil {
		return err
	}

	p := settingsPath()
	if p == "" {
		return errors.New("no home directory to save settings in")
	}
	settingsMu.Lock()
	defer settingsMu.Unlock()

	if m["github.token"] == maskedSecret {
		old, ok, err := storedGitHubToken()
		if err != nil {
			return err
		}
		if ok {
			m["github.token"] = old
		} else {
			delete(m, "github.token")
		}
	}

	// Sync agent bridges if present
	if ag, ok := m["agent"].(string); ok && ag != "" {
		m["agent.harness"] = ag
	} else if ah, ok := m["agent.harness"].(string); ok && ah != "" {
		m["agent"] = ah
	}

	return writeRawMapLocked(p, m)
}

// writeRawMapLocked replaces settings.json atomically (temp file in the same
// directory, then rename) with mode 0600 in a 0700 directory, because the file
// can hold a GitHub token. The previous contents are kept as settings.json.bak.
//
// A settings.json that is a symlink (stow, chezmoi in symlink mode) is written
// through: the link's target is replaced, so the link itself survives. The
// .bak stays next to the link, outside the dotfiles tree.
func writeRawMapLocked(p string, raw map[string]any) error {
	dir := filepath.Dir(p)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(raw, "", "  ")
	if err != nil {
		return err
	}
	target := p
	if resolved, err := filepath.EvalSymlinks(p); err == nil {
		target = resolved
	}
	return writeFileAtomic(target, append(data, '\n'), p+".bak")
}

// tightenSettingsPerms narrows an existing px0 config directory to 0700 and
// settings.json / settings.json.bak to 0600. Earlier versions created them
// 0755 / 0644, and the file can hold a GitHub token; without this they would
// stay readable by other users until the next settings write. Best effort.
func tightenSettingsPerms() {
	p := settingsPath()
	if p == "" {
		return
	}
	if fi, err := os.Lstat(filepath.Dir(p)); err == nil && fi.IsDir() && fi.Mode().Perm()&0o077 != 0 {
		_ = os.Chmod(filepath.Dir(p), 0o700)
	}
	for _, f := range []string{p, p + ".bak"} {
		if fi, err := os.Stat(f); err == nil && fi.Mode().IsRegular() && fi.Mode().Perm()&0o077 != 0 {
			_ = os.Chmod(f, 0o600)
		}
	}
}

// writeFileAtomic writes data to p via a temp file and rename, with mode 0600.
// When backupPath is non-empty, a non-empty existing file is first copied there.
func writeFileAtomic(p string, data []byte, backupPath string) error {
	if backupPath != "" {
		if old, err := os.ReadFile(p); err == nil && len(bytes.TrimSpace(old)) > 0 {
			if err := os.WriteFile(backupPath, old, 0o600); err != nil {
				return err
			}
			_ = os.Chmod(backupPath, 0o600)
		}
	}
	tmp, err := os.CreateTemp(filepath.Dir(p), filepath.Base(p)+".tmp-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	cleanup := func() { _ = os.Remove(tmpName) }
	if err := tmp.Chmod(0o600); err != nil {
		tmp.Close()
		cleanup()
		return err
	}
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		cleanup()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		cleanup()
		return err
	}
	if err := tmp.Close(); err != nil {
		cleanup()
		return err
	}
	if err := os.Rename(tmpName, p); err != nil {
		cleanup()
		return err
	}
	return nil
}
