# Graph Report - px0-ai-px0  (2026-10-05)

## Corpus Check
- 148 files · ~217,949 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: .css 15, (none) 6, .mermaid 1)

## Summary
- 2381 nodes · 7602 edges · 121 communities (113 shown, 8 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 823 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4fc9eb25`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- agent.js
- $$
- main.js
- git_test.go
- Frontend Modules (`web/src/`)
- go_pkg_os
- testing.T
- tabs.js
- git.go
- markdown.js
- esc
- net/http.ResponseWriter
- context.Context
- pr.js
- .handleStatic
- selbar.js
- lspManager
- settings.go
- agent_test.go
- lspClient
- update.go
- markdown.go
- main
- writeJSON
- threadManager
- settings.js
- benchmark.sh
- table_test.go
- Index
- gitpanel.js
- diff.js
- highlight.go
- status.js
- bench_micro_test.go
- Git Forge PR Review & Provider Architecture
- agentManager
- Open
- telemetry.go
- mermaid.js
- .StartEdit
- bug_report.md
- 5. Security Model & Path Sandboxing
- Git Awareness, Diffing & Stage/Commit/Push/Pull
- mdSanitize
- ignore.go
- search.go
- build-web.js
- Pull Request Review & Agent Collaboration
- threadSink
- Performance Benchmarks & Methodology
- Editor Virtualization & Caret Engine
- .handleAgentSelect
- GitWatcher
- pr_test.go
- palette.js
- sync.Mutex
- Key Actions & Capabilities
- Filesystem Indexing & Ignore Engine
- imageview.js
- go_pkg_io
- Developer Workflows & Practical Value
- pr.go
- metrics.go
- theme.js
- Language Server Protocol (LSP) Architecture & Intelligence
- lspnav.go
- Language Server Protocol (LSP) & Code Intelligence
- Image Viewer & Asset Inspection Architecture
- Markdown Preview Implementation
- Styling & Theme Architecture
- Threads
- Workspace Search & Symbol Extraction
- session.go
- highlight_test.go
- install.sh
- compilerOptions
- .callNode
- lspRange
- Editing with Coding Agents
- Fuzzy File Search & Quick Open
- In-File Find & Caret Navigation
- Remote Workspaces & Cloud Inspection
- Workspace Text & Regex Search
- 3. Step-by-Step Implementation Mechanics
- symbols.go
- Publishing & Release Guide
- File Explorer & Workspace Management
- Image Viewer & Asset Inspection
- px0 Features Guide
- Symbol Outline & Navigation
- Syntax Highlighting & Language Support
- 5. Edge Cases & Resilience
- README.md
- Virtualized Editor & Memory Scavenger
- Rendered Markdown Preview
- Themes & Visual Customization
- Vim Keybindings & Modal Navigation
- Windowed Syntax Highlighting Engine
- Threads
- Fuzzy Path Matching Engine
- 10. Unpushed Commits (`@{u}..HEAD`)
- 9. Stage, Commit, Push, Pull
- 2. Documentation Directory
- .handleLSPStart
- Settings & Configuration System
- CSV & TSV Table View
- 3. Server Rendering
- Documentation Sections
- cardkeep.js
- AGENT.md
- .handleMarkdown
- .handleTable
- discoverHarnessModels
- shellCommand
- 8. HTTP Surface
- build.sh
- errFailed
- gzipBypasser
- .Error
- px0

## God Nodes (most connected - your core abstractions)
1. `$$` - 187 edges
2. `Frontend Modules (`web/src/`)` - 115 edges
3. `doc_()` - 111 edges
4. `api()` - 74 edges
5. `esc()` - 71 edges
6. `showToast()` - 71 edges
7. `Server` - 63 edges
8. `openFile()` - 61 edges
9. `writeJSON()` - 59 edges
10. `render()` - 53 edges

## Surprising Connections (you probably didn't know these)
- `A Second Dispatch Shape: Prompts With No File` --references--> `run()`  [INFERRED]
  docs/internals/agent-editing.md → scripts/build-web.js
- `Commit with AI` --references--> `run()`  [INFERRED]
  docs/internals/git-integration.md → scripts/build-web.js
- `Element Roles & Responsibilities` --references--> `layout()`  [INFERRED]
  docs/internals/editor-virtualization.md → web/src/renderer.js
- `7. Non-Destructive Inline DOM Decorations` --references--> `decorate()`  [INFERRED]
  docs/internals/editor-virtualization.md → web/src/renderer.js
- `3. Dual-Tier Refinement Architecture` --references--> `refineChunk()`  [INFERRED]
  docs/internals/syntax-highlighting.md → web/src/renderer.js

## Import Cycles
- 3-file cycle: `web/src/diff.js -> web/src/history.js -> web/src/tabs.js -> web/src/diff.js`
- 3-file cycle: `web/src/diff.js -> web/src/lsp.js -> web/src/tabs.js -> web/src/diff.js`
- 3-file cycle: `web/src/diff.js -> web/src/markdown.js -> web/src/tabs.js -> web/src/diff.js`
- 3-file cycle: `web/src/calls.js -> web/src/tabs.js -> web/src/hover.js -> web/src/calls.js`
- 3-file cycle: `web/src/hover.js -> web/src/lsp.js -> web/src/tabs.js -> web/src/hover.js`
- 3-file cycle: `web/src/lsp.js -> web/src/tabs.js -> web/src/selbar.js -> web/src/lsp.js`
- 3-file cycle: `web/src/markdown.js -> web/src/tabs.js -> web/src/selbar.js -> web/src/markdown.js`
- 3-file cycle: `web/src/markdown.js -> web/src/tree.js -> web/src/selbar.js -> web/src/markdown.js`
- 3-file cycle: `web/src/diff.js -> web/src/markdown.js -> web/src/tree.js -> web/src/diff.js`
- 4-file cycle: `web/src/cursor.js -> web/src/history.js -> web/src/tabs.js -> web/src/diff.js -> web/src/cursor.js`
- 4-file cycle: `web/src/cursor.js -> web/src/lsp.js -> web/src/tabs.js -> web/src/diff.js -> web/src/cursor.js`
- 4-file cycle: `web/src/calls.js -> web/src/tabs.js -> web/src/diff.js -> web/src/hover.js -> web/src/calls.js`
- 4-file cycle: `web/src/diff.js -> web/src/hover.js -> web/src/lsp.js -> web/src/tabs.js -> web/src/diff.js`
- 4-file cycle: `web/src/diff.js -> web/src/lsp.js -> web/src/search.js -> web/src/tabs.js -> web/src/diff.js`
- 4-file cycle: `web/src/diff.js -> web/src/markdown.js -> web/src/history.js -> web/src/tabs.js -> web/src/diff.js`
- 4-file cycle: `web/src/diff.js -> web/src/markdown.js -> web/src/panels.js -> web/src/tabs.js -> web/src/diff.js`
- 4-file cycle: `web/src/calls.js -> web/src/inspector.js -> web/src/tabs.js -> web/src/hover.js -> web/src/calls.js`
- 4-file cycle: `web/src/calls.js -> web/src/lsp.js -> web/src/tabs.js -> web/src/hover.js -> web/src/calls.js`
- 4-file cycle: `web/src/cursor.js -> web/src/history.js -> web/src/tabs.js -> web/src/hover.js -> web/src/cursor.js`
- 4-file cycle: `web/src/cursor.js -> web/src/lsp.js -> web/src/tabs.js -> web/src/hover.js -> web/src/cursor.js`

## Communities (121 total, 8 thin omitted)

### Community 0 - "agent.js"
Cohesion: 0.05
Nodes (89): 1. Core Architectural Tenets, 2. Mandatory Documentation Maintenance Protocol, 3. Checklist for Agents Prior to Submitting Work, 4. Version Bump & Release Verification Protocol, 5. Frontend Architecture & Code Map for Agents, Documentation Mapping Matrix, HTML Structure, Operational Guidelines for AI Agents (+81 more)

### Community 1 - "$$"
Cohesion: 0.10
Nodes (73): On-Demand Chunk Fetching (`ensureChunks`), caretToEdge(), clearSelection(), colAtPoint(), ensureAnchor(), initCursor(), moveCol(), moveCursor() (+65 more)

### Community 2 - "main.js"
Cohesion: 0.08
Nodes (61): on(), once(), registry, focusDiffScope(), connect(), disconnect(), initGitStream(), initPanels() (+53 more)

### Community 3 - "git_test.go"
Cohesion: 0.09
Nodes (56): gitStagedDiff(), gitStatus(), gitUnpushedCommits(), gitUpstreamRef(), BenchmarkGitStatus(), gitInstalled(), gitRepo(), gitTestRun() (+48 more)

### Community 4 - "Frontend Modules (`web/src/`)"
Cohesion: 0.11
Nodes (54): Frontend Modules (`web/src/`), draw(), expand(), explain(), flat, hint(), initCalls(), listEl() (+46 more)

### Community 5 - "go_pkg_os"
Cohesion: 0.13
Nodes (8): isErrFailed(), TestCrashedServerIsRespawned(), isWSL(), openBrowser(), agentPreset, lspSetup, lspSetupOption, lspSetupServer

### Community 6 - "testing.T"
Cohesion: 0.08
Nodes (50): TestAgentHarnessEndpointsRequireAvailability(), TestLanguageIDMapping(), TestLSPCloseDoc(), TestManagerDisabled(), TestPositionEncodings(), TestInstallRecipes(), TestLocalPost(), TestLSPServersEndpoint() (+42 more)

### Community 7 - "tabs.js"
Cohesion: 0.13
Nodes (53): 4. Performance Optimizations, 5. Markdown Preview Scroll Offset Preservation, Step 6: Active Document Resynchronization & Single-Pass Render, The Historical Limitation, View Synchronization, 2. Opening a Markdown Tab, emit(), diffScrollTop() (+45 more)

### Community 8 - "git.go"
Cohesion: 0.08
Nodes (49): gitAheadBehind(), gitAvailable(), gitCommit(), gitCommitDetail(), gitCommitFiles(), gitCommitsInRange(), gitCommitsSince(), gitCommitStat() (+41 more)

### Community 9 - "markdown.js"
Cohesion: 0.09
Nodes (51): 6. Keeping the Reader's Place, 7. Links and History, 8. Switch Controls, 9. Find, Select All and Keys, Block to Line (`previewTopLine`), Line to Block (`previewLine`), Rendering, Switching Views (+43 more)

### Community 10 - "esc"
Cohesion: 0.12
Nodes (47): reloadWorkspace(), cancelLspSetup(), drawSetup(), hintHtml(), job(), renderLspSetup(), start(), wire() (+39 more)

### Community 11 - "net/http.ResponseWriter"
Cohesion: 0.16
Nodes (6): fail(), Server, lspCtx(), setRawHeaders(), fmtDuration(), uiStatus()

### Community 12 - "context.Context"
Cohesion: 0.13
Nodes (20): checkPushAccess(), fetchComments(), fetchPRMeta(), githubGetAllPages(), githubRequest(), prComment, postIssueComment(), replyToReviewComment() (+12 more)

### Community 13 - "pr.js"
Cohesion: 0.12
Nodes (41): `prSession.Pull`: Fast-Forward Only, Same as Everywhere Else, setPRSyncHandler(), closeAllComposers(), comments, deleteDraft(), draftCardHtml(), ensureTracking(), expandedKeys (+33 more)

### Community 14 - ".handleStatic"
Cohesion: 0.07
Nodes (7): gzipWriter, memGzFile, statusRecorder, bypassGzip(), openOrFetchVendorAsset(), staticContentType(), vendorCacheDir()

### Community 15 - "selbar.js"
Cohesion: 0.10
Nodes (38): Whole-File Selection (`selectAll()`), diffLineInfo(), handleLineBtnClick(), initLineComment(), copyFullMarkdown(), getDocRaw(), getFragmentHtml(), getFragmentPlainText() (+30 more)

### Community 16 - "lspManager"
Cohesion: 0.09
Nodes (13): lspManager, lspServerDef, lookPathIn(), lspBinDirs(), shortLangName(), lspManager, lspServerDef, registryFor() (+5 more)

### Community 17 - "settings.go"
Cohesion: 0.11
Nodes (32): agentPresetNames(), newAgentManager(), resolveAgentSpec(), isolateSettings(), TestAgentBatchEditRejectsIntraBatchOverlap(), TestAgentDetectListsKnownHarnesses(), TestAgentModelSelectionAndDefaults(), TestAgentSelectPersistsOutsideWorkspace() (+24 more)

### Community 19 - "agent_test.go"
Cohesion: 0.19
Nodes (30): changedSinceMaps(), commitMessagePrompt(), agentPost(), agentPostJSON(), agentServer(), TestAgentAllowsEditOverUncommittedFileWithoutForce(), TestAgentAllowsIndividualAndBatchEditsConcurrently(), TestAgentAllowsNonOverlappingEditsInParallel() (+22 more)

### Community 20 - "lspClient"
Cohesion: 0.12
Nodes (11): callItem(), fakeCallServer(), siteRange(), TestCallTrail(), TestCallTrailForgedItem(), newLSPClient(), pathToURI(), readFrame() (+3 more)

### Community 21 - "update.go"
Cohesion: 0.14
Nodes (29): githubRelease, updateState, autoUpdate(), checksumFor(), compareSemver(), copyOrMove(), downloadAsset(), downloadVerifiedAsset() (+21 more)

### Community 22 - "markdown.go"
Cohesion: 0.07
Nodes (6): blockStart(), highlightFence(), renderFence(), fenceRenderer, headingIDs, lineMarker

### Community 23 - "main"
Cohesion: 0.16
Nodes (26): fatal(), listen(), main(), networkURLs(), networkURLsFromAddrs(), viewerURL(), cleanBasePath(), isTTY() (+18 more)

### Community 24 - "writeJSON"
Cohesion: 0.18
Nodes (6): localPost(), Server, writeJSON(), Server, Server, threadStatus()

### Community 25 - "threadManager"
Cohesion: 0.11
Nodes (16): threadEvent, threadManager, threadRun, threadStore, threadSummary, threadTurn, cleanThreadScope(), cloneThread() (+8 more)

### Community 26 - "settings.js"
Cohesion: 0.19
Nodes (26): setLayoutPref(), applyAllSettingsLive(), applySettingLive(), BUILTIN_SCHEMA, closeSettings(), COMMONLY_USED_KEYS, focusSettingCard(), getSettingCategories() (+18 more)

### Community 27 - "benchmark.sh"
Cohesion: 0.23
Nodes (24): bench_compare(), bench_editors(), bench_load(), bench_lsp(), bench_memory(), bench_micro(), bench_one(), bench_vscode() (+16 more)

### Community 28 - "table_test.go"
Cohesion: 0.13
Nodes (21): rowSource, tableResult, tableRow, renderTable(), sniffDelim(), mustTable(), TestTableBlankLinesAreSkippedButLineNumbersStayTrue(), TestTableDelimiterComesFromTheFileNotTheExtension() (+13 more)

### Community 29 - "Index"
Cohesion: 0.13
Nodes (6): readGitignore(), cleanupEmptyDirs(), injectDeletedNodes(), sortNodes(), Index, Node

### Community 30 - "gitpanel.js"
Cohesion: 0.24
Nodes (24): cleanCommitMessage(), commitWithMessage(), doCommit(), doCommitWithAI(), doGenerateMessage(), doPull(), doPush(), doStageAll() (+16 more)

### Community 31 - "diff.js"
Cohesion: 0.16
Nodes (23): anchor(), appendHunks(), codeCell(), createDiffSection(), currentDiffLine(), diffContent, diffview, drawDiff() (+15 more)

### Community 32 - "highlight.go"
Cohesion: 0.16
Nodes (10): classFor(), highlightDiff(), highlightLines(), pad(), plainFallback(), sizeOfLines(), DiffHunk, DiffRow (+2 more)

### Community 33 - "status.js"
Cohesion: 0.21
Nodes (22): closeLspMenu(), closeMetricsMenu(), drawLspStatus(), fmtBytes(), initLspMenu(), initMetrics(), initStatusFit(), installingServers (+14 more)

### Community 34 - "bench_micro_test.go"
Cohesion: 0.19
Nodes (16): BenchmarkDocCreation(), BenchmarkFuzzyFind_10K(), BenchmarkFuzzyFind_1K(), BenchmarkFuzzyFind_50K(), BenchmarkFuzzyScore(), BenchmarkHighlightLines_Go(), BenchmarkHighlightLines_Python(), BenchmarkIgnoreSetMatch() (+8 more)

### Community 35 - "Git Forge PR Review & Provider Architecture"
Cohesion: 0.10
Nodes (21): 1. Zero-Dependency, Process-Scoped Design, 2. Extensible Forge Architecture (`GitProvider`), 3. Checkout Lifecycle & Progress Narration, 4. Authentication & Push Access, 5. Merge-Base Diffing, 6. Draft Comments, Submission & Batch Apply, 7. Committing and Pushing Back to the PR, 8. Frontend Integration (+13 more)

### Community 36 - "agentManager"
Cohesion: 0.19
Nodes (5): changedSince(), worktreeSnapshot(), agentJob, agentManager, agentRange

### Community 37 - "Open"
Cohesion: 0.16
Nodes (8): Evict(), EvictAll(), Open(), TestEvictAllClearsCache(), TestEvictRemovesDocument(), lspManager, hlCache, NavHit

### Community 38 - "telemetry.go"
Cohesion: 0.16
Nodes (11): telemetryEvent, TelemetryService, filesBucket(), generateUUID(), getOrGenerateDistinctID(), isOptedOut(), NewTelemetryService(), TestFilesBucket() (+3 more)

### Community 39 - "mermaid.js"
Cohesion: 0.19
Nodes (18): getCachedSvg(), getFitScale(), getMermaidGlobal(), getSvgDimensions(), getThemeKey(), loadMermaidRuntime(), MERMAID_SECURE_KEYS, MERMAID_ZOOM_LEVELS (+10 more)

### Community 40 - ".StartEdit"
Cohesion: 0.15
Nodes (13): agentBatchPrompt(), agentPrompt(), lineRef(), readLineRange(), TestAgentBatchPromptFormatting(), TestLineRefAndPrompt(), TestReadLineRange(), agentBatchItem (+5 more)

### Community 41 - "bug_report.md"
Cohesion: 0.11
Nodes (15): AI-Driven Development and Contributions, Contributing to px0, How to Contribute, Report a Bug, Review and Implementation Process, Suggest a Feature or Improvement, Environment, Logs & Errors (+7 more)

### Community 42 - "5. Security Model & Path Sandboxing"
Cohesion: 0.11
Nodes (18): 1. High-Level Design Principles, 2. Startup Pipeline (<1 ms Critical Path), 3. HTTP Server & API Catalog, 4. Memory Management & Proactive Scavenging, 5. Security Model & Path Sandboxing, Base Path & Subpath Prefixing, Binary Size Optimization & Packaging Footprint, Client-Server Memory Split & Total Footprint (+10 more)

### Community 43 - "Git Awareness, Diffing & Stage/Commit/Push/Pull"
Cohesion: 0.11
Nodes (18): 1. Zero-Dependency Shell-Out Architecture, 2. Concurrent Status Generation, 3. In-Memory Status & Dirty Folder Propagation, 4. Diffing: One Git Call, Two Consumers, Three Views, 5. Real-Time Streaming & Adaptive Monitoring Engine, 6. How Git Detects Changes Under the Hood, 8. Diffing Against an Arbitrary Base, Ancestor Folder Dirty Propagation (`Node.Dirty`) (+10 more)

### Community 44 - "mdSanitize"
Cohesion: 0.13
Nodes (18): 4. Markdown Inline Images & Lightbox, Broken Image Handling, Interactive Lightbox Overlay, Lazy Loading & Decoding, Standalone Image Affordance, 4. Sanitization, Hostile Input Examples, Mermaid Diagrams (+10 more)

### Community 45 - "ignore.go"
Cohesion: 0.24
Nodes (12): classify(), compile(), compilePattern(), compilePatternRegex(), literalHead(), literalRun(), newIgnoreSet(), ignoreSet (+4 more)

### Community 46 - "search.go"
Cohesion: 0.25
Nodes (15): FileMatches, Match, searcher, SearchOpts, workBuf, TestAsciiLowerPreservesLength(), asciiLower(), asciiLowerString() (+7 more)

### Community 47 - "build-web.js"
Cohesion: 0.14
Nodes (12): buildWithBun(), buildWithNode(), visit(), compressVendorAssets(), __dirname, entryFile, __filename, hasBun() (+4 more)

### Community 48 - "Pull Request Review & Agent Collaboration"
Cohesion: 0.12
Nodes (17): 1. Merge-Base Diff View, 2. Live Agent Synchronization, 3. Line Comments & Hover Actions, 4. Batch Applying Comments Locally (`⚡ Batch Apply`), 5. Submitting Formal Reviews, 6. Editing, Committing, and Pushing Back, Authentication & Read-Only Review, Extensible Forge Architecture (`GitProvider`) (+9 more)

### Community 49 - "threadSink"
Cohesion: 0.21
Nodes (9): claudeEvent, threadSink, parseAgyEvent(), parseClaudeEvent(), parseGeminiEvent(), TestParseAgyEvent(), TestParseClaudeEvent(), TestParseGeminiEvent() (+1 more)

### Community 50 - "Performance Benchmarks & Methodology"
Cohesion: 0.12
Nodes (16): 1. Requirements, 2. Running Benchmarks, 3. Benchmark Corpus, 4.1 Benchmark Results (macOS arm64 / Apple Silicon), 4. Benchmark Results, 5. px0 vs. Editors Comparison, 6. Memory Scavenging Verification, Accounting for the Browser Tab (Client/Server Breakdown) (+8 more)

### Community 51 - "Editor Virtualization & Caret Engine"
Cohesion: 0.12
Nodes (16): 1. Why a Bespoke Virtualized Viewer?, 2. DOM Surface Hierarchy, 3. Virtualization & Recycling Pipeline (`paint()`), 4. Offscreen Sub-Pixel Font Measurement, 5. Selection Preservation Across Repaints, 6. Decoupled Overlay Caret (`placeCaret()`), 7. Non-Destructive Inline DOM Decorations, 8. Dynamic Chunk Streaming & Whole-File Selection (+8 more)

### Community 53 - "GitWatcher"
Cohesion: 0.24
Nodes (4): gitRecentCommits(), GitCommit, GitStatusPayload, GitWatcher

### Community 54 - "pr_test.go"
Cohesion: 0.18
Nodes (11): resolveGitHubToken(), TestCheckoutPRMergedAlwaysProceeds(), TestDetectPRURL(), TestFetchPRMetaMerged(), TestHTTPSRemoteURL(), TestParsePRURLUnsupported(), TestResolveGitHubTokenBlankSettingsFallsThrough(), TestResolveGitHubTokenNoneAvailable() (+3 more)

### Community 55 - "palette.js"
Cohesion: 0.19
Nodes (14): closePalette(), COMMANDS, drawPalette(), fuzzyHTML(), initPalette(), movePalette(), openPalette(), overlay (+6 more)

### Community 56 - "sync.Mutex"
Cohesion: 0.20
Nodes (4): newLineStreamer(), lineStreamer, tailBuffer, uiSpinner

### Community 57 - "Key Actions & Capabilities"
Cohesion: 0.14
Nodes (14): 1. Copy Source (`Mod+C` / `Ctrl+C`), 2. Copy Raw Markdown (`Alt+M` / Context Action), 3. Copy Formatted / Rich Text (`Mod+C` in Preview), 4. Copy Reference (`Alt+C`), 5. Copy for Agent / Copy with Context (`Alt+A`), 6. Find Usages (`Alt+U`), 7. Edit with Agent (`Alt+E`), Key Actions & Capabilities (+6 more)

### Community 58 - "Filesystem Indexing & Ignore Engine"
Cohesion: 0.14
Nodes (14): 1. Directory Traversal Architecture, 2. In-Memory Data Structures, 3. High-Performance `.gitignore` Engine, 4. Ignored Directory Semantics (Listing vs. Descent), Bounded Concurrency Semaphore, Fast-Path Evaluation, `FileEntry`, Filesystem Indexing & Ignore Engine (+6 more)

### Community 59 - "imageview.js"
Cohesion: 0.36
Nodes (13): actualSizeImage(), applyImageTransform(), cycleImageBg(), fitImage(), handleImageKey(), initImageViewer(), isImageViewing(), panImage() (+5 more)

### Community 60 - "go_pkg_io"
Cohesion: 0.18
Nodes (3): setProcessGroup(), setProcessGroup(), getProcessRusage()

### Community 61 - "Developer Workflows & Practical Value"
Cohesion: 0.15
Nodes (13): Catching Up With a Moving Remote, Configuration & Preferences, Continuous Auditing of AI Agent Edits, Developer Workflows & Practical Value, Git Awareness, Diff Viewer & Stage/Commit/Push/Pull, Key Capabilities, Keyboard Shortcuts & Controls, Overview & Core Purpose (+5 more)

### Community 62 - "pr.go"
Cohesion: 0.28
Nodes (6): checkoutPR(), computeDiffBase(), gitAuthCmd(), httpsRemoteURL(), redactToken(), prSession

### Community 63 - "metrics.go"
Cohesion: 0.24
Nodes (7): getProcessMetrics(), readProcessCPUTime(), readProcessRSS(), TestMetricsCollection(), getProcessRusage(), metricsCollector, ProcessMetrics

### Community 64 - "theme.js"
Cohesion: 0.33
Nodes (8): currentTheme(), cycleTheme(), getStoredTheme(), initTheme(), listThemes(), chooseThemePreference(), DEFAULT_THEME, setTheme()

### Community 65 - "Language Server Protocol (LSP) Architecture & Intelligence"
Cohesion: 0.17
Nodes (12): 1. Zero-Cost Lazy Architecture, 2. Server Registry & Extension Precedence, 3. Communication & Lifecycle Management, 4. External Path Boundary Sandboxing (`extAllowed`), 5. Stateless Call Hierarchy Trails ([`calls.go`](../../calls.go)), 6. In-App Setup & One-Click Installers, Concurrency & Serialization, Key Principles (+4 more)

### Community 66 - "lspnav.go"
Cohesion: 0.26
Nodes (8): TestUTF16ToByte(), highlightSnippet(), looksLikeDeclaration(), parseHoverContents(), splitMarkdown(), stripMarkdown(), utf16ToByte(), HoverInfo

### Community 67 - "Language Server Protocol (LSP) & Code Intelligence"
Cohesion: 0.18
Nodes (11): Configuration & Options, Deep Architectural Exploration via Call Trails, Developer Workflows & Practical Value, Instant Context via Hover Cards, Key Capabilities, Keyboard Shortcuts & Controls, Language Server Protocol (LSP) & Code Intelligence, Overview & Core Purpose (+3 more)

### Community 68 - "Image Viewer & Asset Inspection Architecture"
Cohesion: 0.18
Nodes (11): 1. Overview & Motivation, 2. Tab Lifecycle & Document Model, 3. Dedicated Image Viewer (`imageview.js`), 5. Keyboard & Interaction Reference, Background Contrast Modes, Image Viewer & Asset Inspection Architecture, Panning, Rendering Quality Modes (+3 more)

### Community 69 - "Markdown Preview Implementation"
Cohesion: 0.18
Nodes (11): 10. Limits and Known Gaps, 11. Tests, 12. Table Preview (CSV / TSV), 1. Request Flow, 5. Presentation, Caps, Endpoint, Markdown Preview Implementation (+3 more)

### Community 70 - "Styling & Theme Architecture"
Cohesion: 0.18
Nodes (11): 1. How Themes Load, 2. Built-in Themes, 3. Creating a Custom Theme, 4. Complete Token Reference, 5. Table Preview Styling, Borders, Accents & Selection, Minimal Working Theme Example, Styling & Theme Architecture (+3 more)

### Community 71 - "Threads"
Cohesion: 0.18
Nodes (11): 1. Model, 2. Session Continuity, 3. Output and Streaming, 4. Persistence, 5. Concurrency, 6. Inline and Batch Edits as Threads, 7. HTTP Surface, 8. Frontend (+3 more)

### Community 72 - "Workspace Search & Symbol Extraction"
Cohesion: 0.18
Nodes (11): 1. Search Engine Architecture, 2. Memory Optimization: `workBuf` Pooling, 3. Fast Rejection Fast Path, 4. Structured Snippet Elision (`{Pre, Mid, Post}`), 5. Regex Symbol Extraction ([`symbols.go`](../../symbols.go)), In-Place ASCII Lowercasing, Parallel Symbol Flagging, Snippet Constants (+3 more)

### Community 73 - "session.go"
Cohesion: 0.31
Nodes (5): sessionManager, SessionTab, WorkspaceSession, newSessionManager(), sessionFilePath()

### Community 74 - "highlight_test.go"
Cohesion: 0.29
Nodes (9): isBinary(), newDoc(), fixtures(), TestBackgroundPassIsExact(), TestConcurrentChunkAccess(), TestGiantLinesDoNotBlowUpTheWindow(), TestHighlightDiff(), TestWindowMatchesFullPass() (+1 more)

### Community 75 - "install.sh"
Cohesion: 0.36
Nodes (10): detect_shell_rc(), fetch(), fetch_file(), has_path_configured(), is_writable(), log_error(), log_info(), log_step() (+2 more)

### Community 76 - "compilerOptions"
Cohesion: 0.18
Nodes (10): compilerOptions, allowJs, checkJs, module, moduleResolution, noEmit, skipLibCheck, strict (+2 more)

### Community 77 - ".callNode"
Cohesion: 0.38
Nodes (5): firstSite(), lspManager, TestURIRoundTrip(), uriToPath(), CallNode

### Community 78 - "lspRange"
Cohesion: 0.22
Nodes (8): siteLines(), decodeRange(), lspCallItem, lspDocumentSymbol, lspLocation, lspLocationLink, lspPosition, lspRange

### Community 79 - "Editing with Coding Agents"
Cohesion: 0.20
Nodes (10): Batching Comments, Beyond Code: Commit Messages, Configuration Options, Editing with Coding Agents, How an Agent Edit Works, Keyboard Shortcuts & Controls, Multi-Edit Concurrency & Safety Guards, Overview & Core Purpose (+2 more)

### Community 80 - "Fuzzy File Search & Quick Open"
Cohesion: 0.20
Nodes (10): Configuration & Exclusions, Developer Workflows & Productivity Value, Disambiguating Duplicate Filenames, Fuzzy File Search & Quick Open, Key Capabilities, Keyboard-First Ergonomics, Keyboard Shortcuts & Controls, Overview & Core Purpose (+2 more)

### Community 81 - "In-File Find & Caret Navigation"
Cohesion: 0.20
Nodes (9): Auditing Variable Lifecycles, Configuration & Editor Options, Developer Workflows & Practical Value, In-File Find & Caret Navigation, Jumping Directly to Compiler or Linter Errors, Key Capabilities, Keyboard Shortcuts & Controls, Overview & Core Purpose (+1 more)

### Community 82 - "Remote Workspaces & Cloud Inspection"
Cohesion: 0.20
Nodes (10): 1. Cloud Devbox via Tailscale or WireGuard, 2. Ephemeral Docker Container Inspection, 3. CI/CD Runner Debugging, 4. Reverse Proxy & Subpath Hosting (`-base-path`), CLI Flag Reference, Developer Workflows & Setup Patterns, Key Capabilities, Overview & Core Purpose (+2 more)

### Community 83 - "Workspace Text & Regex Search"
Cohesion: 0.20
Nodes (10): Auditing Symbol Call Sites, Configuration & Tuning, Developer Workflows & Practical Value, Hunting Down Error Messages, Interactive Controls & Search Pane, Key Capabilities, Overview & Core Purpose, Pattern Matching with Regular Expressions (+2 more)

### Community 84 - "3. Step-by-Step Implementation Mechanics"
Cohesion: 0.20
Nodes (10): 1. Problem Statement & Motivation, 2. End-to-End Architectural Flow, 3. Step-by-Step Implementation Mechanics, 6. Related Documentation, File Updates & In-Place Tab Reloading, Step 1: Live State Snapshotting, Step 2: Virtualized Chunk Target Calculation, Step 3: Concurrent Non-Blocking Fetching (`Promise.allSettled`) (+2 more)

### Community 85 - "symbols.go"
Cohesion: 0.31
Nodes (7): Symbol, symRule, declPatterns(), familyFor(), isNoiseSymbol(), Outline(), r()

### Community 86 - "Publishing & Release Guide"
Cohesion: 0.20
Nodes (10): 1. Prerequisites, 2. Pre-Release Verification, 3. Release Methods, 4. Post-Release Verification, Method 1: Automated Release via Makefile (Recommended), Method 2: Manual Release via Git, Method 3: GitHub Actions Workflow Dispatch, Publishing & Release Guide (+2 more)

### Community 87 - "File Explorer & Workspace Management"
Cohesion: 0.22
Nodes (9): Configuration & Tuning, Developer Workflows & Practical Value, File Explorer & Workspace Management, Key Capabilities, Keyboard Shortcuts & Controls, Maximizing Screen Real Estate, Orientation in Unfamiliar Codebases, Overview & Core Purpose (+1 more)

### Community 88 - "Image Viewer & Asset Inspection"
Cohesion: 0.22
Nodes (9): Auditing Vector & Icon Assets, Developer Workflows & Practical Value, Image Viewer & Asset Inspection, Inspecting AI-Generated Diagrams, Key Capabilities, Keyboard Shortcuts & Controls, Overview & Core Purpose, Supported Formats (+1 more)

### Community 89 - "px0 Features Guide"
Cohesion: 0.22
Nodes (9): 1. Navigation & Search, 2. Code Intelligence & Structure, 3. Git Integration & Review, 4. Coding Agent Editing & Delegation, 5. Documentation & Media Viewing, 6. Ergonomics & Customization, 7. Performance & Remote Workspaces, Feature Matrix (+1 more)

### Community 90 - "Symbol Outline & Navigation"
Cohesion: 0.22
Nodes (9): Developer Workflows & Practical Value, Key Capabilities, Keyboard Shortcuts & Controls, Keyboard Workflow, Overview & Core Purpose, Rapid In-File Navigation, Symbol Outline & Navigation, Technical Architecture Deep Dive (+1 more)

### Community 91 - "Syntax Highlighting & Language Support"
Cohesion: 0.22
Nodes (9): Configuration & Tuning, Developer Workflows & Practical Value, Instant Opening of Massive Files, Key Capabilities, Overview & Core Purpose, Reading Multi-Language Repositories, Supported Languages & Formats, Syntax Highlighting & Language Support (+1 more)

### Community 92 - "5. Edge Cases & Resilience"
Cohesion: 0.22
Nodes (9): 1. Concurrent Tab Closure during In-Flight Network Requests, 2. File Shrinkage & Caret Out-of-Bounds Clamping, 3. File Deletion or Permission Revocation on Disk, 4. Diff View Preference & Dismissal Persistence, 5. Edge Cases & Resilience, 6. Binary & Image Tab Protection, 7. End-to-End Reactive Streaming Architecture, Auto-Closing Discarded / Reset Diff Tabs (+1 more)

### Community 93 - "README.md"
Cohesion: 0.22
Nodes (8): Benchmarks, Design Partners, Development, Documentation, Features, Installation, License, Usage

### Community 94 - "Virtualized Editor & Memory Scavenger"
Cohesion: 0.25
Nodes (8): Auditing Massive Datasets & Logs, Developer Workflows & Practical Value, Head-to-Head Performance Comparison, Key Capabilities, Overview & Core Purpose, Running on Constrained Hardware & Laptops, Technical Architecture Deep Dive, Virtualized Editor & Memory Scavenger

### Community 95 - "Rendered Markdown Preview"
Cohesion: 0.25
Nodes (8): Developer Workflows & Practical Value, Key Capabilities, Keyboard Shortcuts & Controls, Overview & Core Purpose, Rendered Markdown Preview, Reviewing Documentation & RFCs, Seamless Source Editing, Technical Architecture Deep Dive

### Community 96 - "Themes & Visual Customization"
Cohesion: 0.25
Nodes (8): Built-In Themes, Configuring via Settings UI, Developer Workflows & Switching Themes, Key Capabilities, Overview & Core Purpose, Quick Theme Switching via Command Palette, Technical Architecture Deep Dive, Themes & Visual Customization

### Community 97 - "Vim Keybindings & Modal Navigation"
Cohesion: 0.25
Nodes (7): 1. Normal Mode (Navigation), 2. Visual Mode (Selection), Enabling Vim Mode, Overview & Core Purpose, Status Bar Indicator, Supported Modes & Keybindings, Vim Keybindings & Modal Navigation

### Community 98 - "Windowed Syntax Highlighting Engine"
Cohesion: 0.25
Nodes (8): 1. The Syntax Highlighting Bottleneck, 2. Windowed Highlighting Architecture, 3. Dual-Tier Refinement Architecture, 4. Short-Class CSS Tokenization, 5. Byte-Budgeted LRU Memory Cache, Byte-Cap Protection (`hlWindowBytes`), Highlighting Parameters, Windowed Syntax Highlighting Engine

### Community 99 - "Threads"
Cohesion: 0.29
Nodes (7): Inline Edits Are Threads Too, Requirements, Starting a Thread, The Conversation, The Thread List, Threads, Threads in a PR Review

### Community 100 - "Fuzzy Path Matching Engine"
Cohesion: 0.29
Nodes (7): 1. The Fuzzy Matching Challenge, 2. Two-Pass Bounded Matching Algorithm, 3. Weighted Scoring Matrix, 4. Multi-Core Parallel Query Slicing, Concurrency Pipeline, Fuzzy Path Matching Engine, Step-by-Step Execution

### Community 101 - "10. Unpushed Commits (`@{u}..HEAD`)"
Cohesion: 0.29
Nodes (7): 10. Unpushed Commits (`@{u}..HEAD`), Frontend (`web/src/unpushed.js`), Hover Cards That Stay Open (`web/src/cardkeep.js`), HTTP Surface, Per-Commit Reads, The `ref` Parameter on `/api/diff` and `/api/gutter`, Which Commits, and Against What

### Community 102 - "9. Stage, Commit, Push, Pull"
Cohesion: 0.29
Nodes (7): 9. Stage, Commit, Push, Pull, Commit with AI, Fast-Forward-Only Pull, HTTP Surface, Push, Stage / Unstage / Commit, Staged-Path Tracking

### Community 103 - "2. Documentation Directory"
Cohesion: 0.29
Nodes (7): 1. Subsystem Architecture Map, 2. Documentation Directory, Core Architecture & Server Runtime, Frontend & UI Subsystems, Operations & Maintenance, px0 Internal Architecture & Design Documentation, Search & Intelligence Engines

### Community 105 - "Settings & Configuration System"
Cohesion: 0.33
Nodes (6): Accessing Settings, Direct JSON File Configuration, Key Capabilities, Key Configurable Settings, Overview & Core Purpose, Settings & Configuration System

### Community 106 - "CSV & TSV Table View"
Cohesion: 0.33
Nodes (5): CSV & TSV Table View, Key Capabilities, Keyboard Shortcuts & Controls, Overview & Core Purpose, Technical Architecture Deep Dive

### Community 107 - "3. Server Rendering"
Cohesion: 0.33
Nodes (6): 3. Server Rendering, Converter Configuration, Endpoint, Fenced Code Highlighting, Heading IDs, Source Line Anchors

### Community 108 - "Documentation Sections"
Cohesion: 0.33
Nodes (6): 1. [Feature Guides](features/README.md), 2. [Internal Architecture & Design](internals/README.md), 3. [AI Agent Operational Guidelines](agents/README.md), Documentation Sections, Performance & Comparative Benchmarks, px0 Documentation Hub

### Community 109 - "cardkeep.js"
Cohesion: 0.50
Nodes (4): CARD_GRACE, keepers, tickAll(), wirePointerTrack()

### Community 110 - "AGENT.md"
Cohesion: 0.50
Nodes (3): Operational Guidelines for AI Agents, Quick Reference, Version Bump & Release Verification Protocol

### Community 111 - ".handleMarkdown"
Cohesion: 0.50
Nodes (3): Server, isMarkdown(), renderMarkdown()

### Community 112 - ".handleTable"
Cohesion: 0.50
Nodes (3): Server, isTable(), tableDelim()

### Community 113 - "discoverHarnessModels"
Cohesion: 0.67
Nodes (3): discoverHarnessModels(), runModelDiscovery(), TestClaudeModelDiscovery()

### Community 114 - "shellCommand"
Cohesion: 0.67
Nodes (3): shellCommand(), shellQuote(), TestShellQuoteAndCommand()

### Community 115 - "8. HTTP Surface"
Cohesion: 0.67
Nodes (3): 8. HTTP Surface, A Second Dispatch Shape: Prompts With No File, Security Posture

## Knowledge Gaps
- **460 isolated node(s):** `agentPreset`, `build.sh script`, `px0`, `Server`, `__filename` (+455 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 568 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Frontend Modules (`web/src/`)` connect `Frontend Modules (`web/src/`)` to `agent.js`, `$$`, `status.js`, `theme.js`, `main.js`, `tabs.js`, `markdown.js`, `esc`, `pr.js`, `selbar.js`, `palette.js`, `gitpanel.js`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Are the 114 inferred relationships involving `Frontend Modules (`web/src/`)` (e.g. with `applyAgentMeta()` and `initAgent()`) actually correct?**
  _`Frontend Modules (`web/src/`)` has 114 INFERRED edges - model-reasoned connections that need verification._
- **What connects `agentPreset`, `build.sh script`, `px0` to the rest of the system?**
  _460 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `agent.js` be split into smaller, more focused modules?**
  _Cohesion score 0.054431960049937576 - nodes in this community are weakly interconnected._
- **Why does `Operational Guidelines for AI Agents` connect `agent.js` to `docs/README.md`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Should `$$` be split into smaller, more focused modules?**
  _Cohesion score 0.09574813372281726 - nodes in this community are weakly interconnected._
- **Why does `5. Frontend Architecture & Code Map for Agents` connect `agent.js` to `Frontend Modules (`web/src/`)`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._